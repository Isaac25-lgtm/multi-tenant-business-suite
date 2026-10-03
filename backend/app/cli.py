"""Operational CLI commands for reconciliation and maintenance.

Run with:  python -m flask --app run:app <command>
"""
import csv
import json
import sys

import click
from sqlalchemy import func

from app.extensions import db


def register_cli(app):
    app.cli.add_command(finance_audit)
    app.cli.add_command(finance_backfill_settlement)
    app.cli.add_command(refresh_loans)
    app.cli.add_command(pii_reencrypt)


def _first_zero_payment(loan):
    from app.models.finance import LoanPayment

    return LoanPayment.query.filter(
        LoanPayment.loan_id == loan.id,
        LoanPayment.is_deleted == False,  # noqa: E712
        LoanPayment.balance_after <= 0,
    ).order_by(LoanPayment.payment_date.asc(), LoanPayment.id.asc()).first()


def _paid_after(loan, payment):
    from app.models.finance import LoanPayment

    return LoanPayment.query.filter(
        LoanPayment.loan_id == loan.id,
        LoanPayment.is_deleted == False,  # noqa: E712
        LoanPayment.id != payment.id,
        LoanPayment.payment_date >= payment.payment_date,
        LoanPayment.created_at > payment.created_at,
    ).with_entities(func.coalesce(func.sum(LoanPayment.amount), 0)).scalar()


@click.command('finance-audit')
@click.option('--csv', 'csv_path', default=None, help='Write the report to this CSV file instead of the screen.')
def finance_audit(csv_path):
    """Report every loan with flags that need management review.

    Read-only. Flags:
      reopened_after_settlement  balance went to zero, then interest reopened it
      flat_rate_monthly_term     flat-rate loan on a monthly term; confirm the
                                 contract was not really monthly interest
      legacy_payment_split       has payments migrated as principal-only
      interest_overpaid          more interest paid than has been charged
    """
    from app.models.finance import Loan, LoanPayment
    from app.services.loan_accounting import accrued_interest
    from app.utils.timezone import get_local_today

    today = get_local_today()
    rows = []
    for loan in Loan.query.filter(Loan.is_deleted == False).order_by(Loan.id).all():  # noqa: E712
        flags = []
        zero = _first_zero_payment(loan)
        if zero and loan.settled_on is None and (loan.balance or 0) > 0:
            flags.append('reopened_after_settlement')
        if (loan.interest_mode or 'flat_rate') == 'flat_rate' and (loan.duration_type or 'weeks') == 'months':
            flags.append('flat_rate_monthly_term')
        legacy = LoanPayment.query.filter_by(loan_id=loan.id, is_deleted=False, payment_type='legacy').count()
        if legacy:
            flags.append('legacy_payment_split')
        if (loan.interest_paid or 0) > accrued_interest(loan, today):
            flags.append('interest_overpaid')

        rows.append({
            'loan_id': loan.id,
            'client': loan.client.name if loan.client else '',
            'interest_mode': loan.interest_mode or 'flat_rate',
            'principal': float(loan.principal or 0),
            'interest_rate': float(loan.interest_rate or 0),
            'monthly_interest_amount': float(loan.monthly_interest_amount or 0),
            'interest_amount': float(loan.interest_amount or 0),
            'total_amount': float(loan.total_amount or 0),
            'principal_paid': float(loan.principal_paid or 0),
            'interest_paid': float(loan.interest_paid or 0),
            'balance': float(loan.balance or 0),
            'issue_date': loan.issue_date.isoformat() if loan.issue_date else '',
            'due_date': loan.due_date.isoformat() if loan.due_date else '',
            'status': loan.status,
            'settled_on': loan.settled_on.isoformat() if loan.settled_on else '',
            'flags': ';'.join(flags),
        })

    if not rows:
        click.echo('No loans found.')
        return

    out = open(csv_path, 'w', newline='', encoding='utf-8') if csv_path else sys.stdout
    try:
        writer = csv.DictWriter(out, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if csv_path:
            out.close()

    flagged = [row for row in rows if row['flags']]
    click.echo(f'\n{len(rows)} loans, {len(flagged)} flagged for review.', err=True)
    if csv_path:
        click.echo(f'Report written to {csv_path}', err=True)


@click.command('finance-backfill-settlement')
@click.option('--apply', 'apply_changes', is_flag=True, help='Write the changes. Without this flag nothing is saved.')
def finance_backfill_settlement(apply_changes):
    """Fix loans that were cleared but later reopened by monthly interest.

    Sets settled_on to the date the balance first reached zero, which stops
    interest from accruing after that date. Loans that received further
    payments after reaching zero are listed for manual review and never
    changed automatically.
    """
    from app.models.finance import Loan
    from app.modules.auth import log_action
    from app.services.loan_accounting import refresh_loan_state

    fixed, review = [], []
    candidates = Loan.query.filter(
        Loan.is_deleted == False,  # noqa: E712
        Loan.settled_on.is_(None),
        Loan.status != 'renewed',
    ).all()
    for loan in candidates:
        zero = _first_zero_payment(loan)
        if not zero:
            continue
        later = _paid_after(loan, zero)
        before = float(loan.balance or 0)
        if later and float(later) > 0:
            review.append((loan, zero.payment_date, before, float(later)))
            continue
        loan.settled_on = zero.payment_date
        refresh_loan_state(loan)
        fixed.append((loan, zero.payment_date, before, float(loan.balance or 0)))

    for loan, settled, before, after in fixed:
        click.echo(f'Loan {loan.id} ({loan.client.name if loan.client else "?"}): settled {settled}, '
                   f'balance {before:,.0f} -> {after:,.0f}')
    for loan, settled, before, later in review:
        click.echo(f'REVIEW loan {loan.id} ({loan.client.name if loan.client else "?"}): reached zero on {settled}, '
                   f'then received {later:,.0f} more; balance now {before:,.0f}. Not changed.')

    if apply_changes and fixed:
        db.session.commit()
        for loan, settled, before, after in fixed:
            log_action('system', 'finance', 'correct', 'loan', loan.id,
                       {'action': 'backfill_settled_on', 'settled_on': str(settled),
                        'balance_before': before, 'balance_after': after})
        click.echo(f'\nApplied {len(fixed)} fix(es). {len(review)} loan(s) need manual review.')
    else:
        db.session.rollback()
        click.echo(f'\nDry run: {len(fixed)} loan(s) would be fixed, {len(review)} need manual review. '
                   'Re-run with --apply to save.')


@click.command('refresh-loans')
def refresh_loans():
    """Recalculate every open loan's balance and status. Safe to run repeatedly."""
    from app.services.loan_accounting import refresh_active_loans, refresh_open_group_loans

    changed = refresh_active_loans()
    changed = refresh_open_group_loans() or changed
    click.echo('Loans refreshed (changes saved).' if changed else 'Loans refreshed (no changes).')


@click.command('pii-reencrypt')
@click.option('--apply', 'apply_changes', is_flag=True, help='Write the changes. Without this flag nothing is saved.')
def pii_reencrypt(apply_changes):
    """Re-encrypt stored ID numbers under PII_ENCRYPTION_KEY.

    Run once after setting PII_ENCRYPTION_KEY. Keep SECRET_KEY unchanged until
    this has been applied successfully.
    """
    from flask import current_app

    from app.models.customer import Customer
    from app.models.finance import GroupLoan, LoanClient
    from app.utils.pii import encrypt_value, reencrypt_value

    if not current_app.config.get('PII_ENCRYPTION_KEY'):
        click.echo('PII_ENCRYPTION_KEY is not set. Nothing to do.', err=True)
        raise SystemExit(1)

    counts = {'rewritten': 0, 'unreadable': 0}

    def _rotate(record):
        if record._nin_plaintext and not record.nin_encrypted:
            record.nin_encrypted = encrypt_value(record._nin_plaintext)
            record._nin_plaintext = None
            counts['rewritten'] += 1
        elif record.nin_encrypted:
            rotated = reencrypt_value(record.nin_encrypted)
            if rotated is None:
                counts['unreadable'] += 1
            else:
                record.nin_encrypted = rotated
                counts['rewritten'] += 1

    for model in (Customer, LoanClient):
        for record in model.query.all():
            _rotate(record)

    for group in GroupLoan.query.filter(GroupLoan.members_json.isnot(None)).all():
        try:
            members = json.loads(group.members_json)
        except (TypeError, ValueError):
            continue
        changed = False
        for member in members:
            token = member.get('nin_encrypted')
            if token:
                rotated = reencrypt_value(token)
                if rotated is None:
                    counts['unreadable'] += 1
                else:
                    member['nin_encrypted'] = rotated
                    changed = True
                    counts['rewritten'] += 1
        if changed:
            group.members_json = json.dumps(members)

    if apply_changes:
        db.session.commit()
        click.echo(f"Re-encrypted {counts['rewritten']} value(s); {counts['unreadable']} could not be read.")
    else:
        db.session.rollback()
        click.echo(f"Dry run: {counts['rewritten']} value(s) would be re-encrypted; "
                   f"{counts['unreadable']} could not be read. Re-run with --apply to save.")
