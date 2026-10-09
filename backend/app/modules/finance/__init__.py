from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash, current_app, session, Response, send_file
from app.models.finance import LoanClient, Loan, LoanPayment, GroupLoan, GroupLoanPayment, LoanDocument, LoanAdjustment
from app.modules.auth import login_required, log_action, manager_required
from app.utils.integrity import DUPLICATE_MESSAGE, find_recent_duplicate
from app.utils.payments import read_payment_details
from app.extensions import db
from app.utils.timezone import get_local_now, get_local_today
from app.utils.pdf_generator import (
    generate_group_agreement_pdf,
    generate_clearance_pdf,
    generate_group_clearance_pdf,
    generate_loan_statement_pdf,
    generate_payment_plan_pdf,
    generate_overdue_reminder_pdf,
)
from app.utils.payment_plan import calculate_manager_payment_plan
from app.services.loan_accounting import (
    adjustment_limit,
    allocate_loan_payment,
    apply_adjustment,
    calculate_due_date,
    calculate_reducing_balance_schedule,
    get_loan_payment_schedule,
    group_table_totals,
    loan_table_totals,
    preview_loan_payment,
    refresh_active_loans,
    refresh_group_loan_state,
    refresh_loan_state,
    refresh_open_group_loans,
    replay_loan_payments,
    reverse_loan_payment_allocation,
    round_money,
    summarize_portfolio,
)
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from dateutil.relativedelta import relativedelta
from werkzeug.utils import secure_filename
import json
import os
import io

finance_bp = Blueprint('finance', __name__)

PERIOD_DAYS = {'weekly': 7, 'bi-weekly': 14, 'monthly': 30, 'bi-monthly': 60}
CLIENT_PAYER_STATUSES = {'neutral', 'good', 'bad'}
MAX_PRINCIPAL = Decimal('1000000000')
MAX_INTEREST_RATE = Decimal('100')
MAX_MONTHLY_INTEREST = Decimal('100000000')
MAX_DURATION_UNITS = 120
MAX_GROUP_PERIODS = 240
MONEY_QUANT = Decimal('1')
INDIVIDUAL_INTEREST_MODES = {'flat_rate', 'monthly_accrual', 'reducing_balance_equal'}
WRITE_OFF_MIN_DAYS_OVERDUE = 180  # business rule: write off only after 6 months unpaid
# Loan list filters: '' = all except renewed.
LOAN_LIST_FILTERS = {
    '': 'Open & paid',
    'active': 'Active',
    'overdue': 'Overdue',
    'paid': 'Paid',
    'renewed': 'Renewed',
    'everything': 'Everything',
}
from app.utils.uploads import allowed_file, validate_and_save


def safe_decimal(value, default='0'):
    """Safely convert a value to Decimal, handling empty strings and invalid values"""
    if value is None or value == '':
        return Decimal(default)
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return Decimal(default)


def get_form_value(source, key, default=None, cast=None):
    if hasattr(source, 'get'):
        if cast is not None:
            try:
                return source.get(key, default, type=cast)
            except TypeError:
                pass
        value = source.get(key, default)
    else:
        value = default

    if cast is None or value in (None, ''):
        return value

    try:
        return cast(value)
    except (TypeError, ValueError):
        return default


def normalize_payer_status(value):
    status = str(value or 'neutral').strip().lower()
    if status not in CLIENT_PAYER_STATUSES:
        return 'neutral'
    return status


def check_date_permission(entry_date, user_section):
    """Check if user has permission to enter data for the given date"""
    today = get_local_today()
    yesterday = today - timedelta(days=1)
    if user_section == 'manager':
        return True
    return yesterday <= entry_date <= today


def parse_individual_loan_form(form):
    client_id = get_form_value(form, 'client_id', cast=int)
    principal = safe_decimal(get_form_value(form, 'principal', '0'))
    interest_mode = get_form_value(form, 'interest_mode', 'monthly_accrual') or 'monthly_accrual'
    # Every individual loan accumulates monthly interest (business rule), so a
    # legacy "flat rate" request is issued as a monthly-interest loan.
    if interest_mode == 'flat_rate':
        interest_mode = 'monthly_accrual'
    interest_rate = safe_decimal(get_form_value(form, 'interest_rate', '0'))
    monthly_interest_amount = safe_decimal(get_form_value(form, 'monthly_interest_amount', '0'))
    duration_weeks = get_form_value(form, 'duration_weeks', cast=int)
    duration_type = get_form_value(form, 'duration_type', 'weeks')
    issue_date = date.fromisoformat(get_form_value(form, 'issue_date', str(get_local_today())))

    if not client_id:
        raise ValueError('Client is required.')
    if principal <= 0 or principal > MAX_PRINCIPAL:
        raise ValueError('Principal must be between 1 and 1,000,000,000.')
    if not duration_weeks or duration_weeks <= 0 or duration_weeks > MAX_DURATION_UNITS:
        raise ValueError('Duration must be between 1 and 120.')
    if duration_type not in ('weeks', 'months'):
        raise ValueError('Invalid loan period selected.')
    if interest_mode not in INDIVIDUAL_INTEREST_MODES:
        raise ValueError('Invalid interest mode selected.')

    if interest_mode == 'monthly_accrual':
        # The rate is per month. An explicit monthly amount is still accepted
        # (older forms) and converted to its rate.
        if interest_rate > 0:
            if interest_rate > MAX_INTEREST_RATE:
                raise ValueError('Monthly interest rate must be between 0 and 100.')
            monthly_interest_amount = round_money(principal * interest_rate / Decimal('100'))
        elif monthly_interest_amount > 0:
            interest_rate = (monthly_interest_amount / principal) * Decimal('100')
        else:
            raise ValueError('Enter the monthly interest rate.')
        if monthly_interest_amount <= 0 or monthly_interest_amount > MAX_MONTHLY_INTEREST:
            raise ValueError('Monthly interest must be between 1 and 100,000,000.')
        # refresh_loan_state charges the first month according to the timing rule.
        interest_amount = Decimal('0')
        total_amount = principal
    elif interest_mode == 'reducing_balance_equal':
        if duration_type != 'months':
            raise ValueError('Reducing-balance loans must use a monthly duration.')
        if interest_rate < 0 or interest_rate > MAX_INTEREST_RATE:
            raise ValueError('Monthly interest rate must be between 0 and 100.')
        schedule = calculate_reducing_balance_schedule(principal, interest_rate, duration_weeks, issue_date)
        if not schedule:
            raise ValueError('Unable to calculate reducing-balance schedule.')
        monthly_interest_amount = schedule[0]['payment']
        interest_amount = sum((row['interest'] for row in schedule), Decimal('0'))
        total_amount = sum((row['payment'] for row in schedule), Decimal('0'))
    else:
        if interest_rate < 0 or interest_rate > MAX_INTEREST_RATE:
            raise ValueError('Interest rate must be between 0 and 100.')
        monthly_interest_amount = None
        interest_amount = principal * (interest_rate / Decimal('100'))
        total_amount = principal + interest_amount

    return {
        'client_id': client_id,
        'principal': principal,
        'interest_mode': interest_mode,
        'interest_rate': interest_rate,
        'monthly_interest_amount': monthly_interest_amount,
        'interest_amount': interest_amount,
        'total_amount': total_amount,
        'duration_weeks': duration_weeks,
        'duration_type': duration_type,
        'issue_date': issue_date,
        'due_date': calculate_due_date(issue_date, duration_weeks, duration_type),
    }


def parse_group_loan_form(form):
    group_name = str(get_form_value(form, 'group_name', '') or '').strip()
    member_count = get_form_value(form, 'member_count', 1, int) or 1
    principal = safe_decimal(get_form_value(form, 'principal', '0'))
    interest_rate = safe_decimal(get_form_value(form, 'interest_rate', '0'))
    total_periods = get_form_value(form, 'total_periods', cast=int)
    period_type = get_form_value(form, 'period_type', 'monthly')
    issue_date = date.fromisoformat(get_form_value(form, 'issue_date', str(get_local_today())))

    if not group_name:
        raise ValueError('Group name is required.')
    if member_count <= 0 or member_count > 500:
        raise ValueError('Member count must be between 1 and 500.')
    if principal <= 0 or principal > MAX_PRINCIPAL:
        raise ValueError('Principal must be between 1 and 1,000,000,000.')
    if interest_rate < 0 or interest_rate > MAX_INTEREST_RATE:
        raise ValueError('Interest rate must be between 0 and 100.')
    if not total_periods or total_periods <= 0 or total_periods > MAX_GROUP_PERIODS:
        raise ValueError('Total periods must be between 1 and 240.')
    if period_type not in PERIOD_DAYS:
        raise ValueError('Invalid repayment period selected.')

    interest_amount = principal * (interest_rate / Decimal('100'))
    total_amount = principal + interest_amount
    amount_per_period = total_amount / total_periods
    period_days = PERIOD_DAYS.get(period_type, 30)
    due_date = issue_date + timedelta(days=period_days * total_periods)

    return {
        'group_name': group_name,
        'member_count': member_count,
        'principal': principal,
        'interest_rate': interest_rate,
        'interest_amount': interest_amount,
        'total_amount': total_amount,
        'amount_per_period': amount_per_period,
        'total_periods': total_periods,
        'period_type': period_type,
        'issue_date': issue_date,
        'due_date': due_date,
    }


@finance_bp.route('/')
@login_required('finance')
def index():
    """Finance overview"""
    load_error = False
    try:
        refresh_active_loans()
        refresh_open_group_loans()

        active_loans = Loan.query.filter(Loan.is_deleted == False, Loan.status != 'renewed', Loan.balance > 0).count()
        active_groups = GroupLoan.query.filter(GroupLoan.is_deleted == False, GroupLoan.balance > 0).count()
        overdue_loans = Loan.query.filter(Loan.is_deleted == False, Loan.status == 'overdue', Loan.balance > 0).count()
        overdue_groups = GroupLoan.query.filter(GroupLoan.is_deleted == False, GroupLoan.status == 'overdue', GroupLoan.balance > 0).count()

        portfolio = summarize_portfolio()
        from app.services.loan_conversion import count_open_flat_loans
        open_flat_loans = count_open_flat_loans()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Finance dashboard calculation failed: %s', exc)
        load_error = True
        active_loans = active_groups = overdue_loans = overdue_groups = 0
        portfolio = None
        open_flat_loans = 0

    return render_template('finance/index.html',
        load_error=load_error,
        active_loans=active_loans, active_groups=active_groups,
        overdue_loans=overdue_loans, overdue_groups=overdue_groups,
        portfolio=portfolio,
        open_flat_loans=open_flat_loans,
        total_outstanding=portfolio['combined_principal'] if portfolio else 0,
        total_interest_expected=portfolio['combined_interest'] if portfolio else 0,
    )


# ============ CLIENTS ============

@finance_bp.route('/clients')
@login_required('finance')
def clients():
    raw_payer_status = str(request.args.get('payer_status', 'all') or 'all').strip().lower()
    payer_status_filter = 'all' if raw_payer_status == 'all' else normalize_payer_status(raw_payer_status)

    base_query = LoanClient.query.filter_by(is_active=True)
    query = base_query
    if payer_status_filter != 'all':
        query = query.filter_by(payer_status=payer_status_filter)

    all_clients = query.order_by(LoanClient.name).all()
    status_counts = {
        'all': base_query.count(),
        'good': base_query.filter_by(payer_status='good').count(),
        'bad': base_query.filter_by(payer_status='bad').count(),
        'neutral': base_query.filter_by(payer_status='neutral').count(),
    }
    return render_template(
        'finance/clients.html',
        clients=all_clients,
        payer_status_filter=payer_status_filter,
        status_counts=status_counts,
    )


@finance_bp.route('/clients/add', methods=['POST'])
@login_required('finance')
def add_client():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    if not name or not phone:
        flash('Name and phone required', 'error')
        return redirect(url_for('finance.clients'))

    client = LoanClient(
        name=name,
        phone=phone,
        address=request.form.get('address', '').strip(),
        payer_status=normalize_payer_status(request.form.get('payer_status'))
    )
    client.nin = request.form.get('nin', '').strip()
    db.session.add(client)
    db.session.commit()

    log_action(session['username'], 'finance', 'create', 'client', client.id,
               {'name': name, 'phone': phone, 'payer_status': client.payer_status})
    flash(f'Client "{name}" added', 'success')
    return redirect(url_for('finance.clients'))


@finance_bp.route('/clients/<int:id>/edit', methods=['POST'])
@login_required('finance')
def edit_client(id):
    """Edit a client's details"""
    client = LoanClient.query.get_or_404(id)
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()

    if not name or not phone:
        flash('Name and phone required', 'error')
        return redirect(url_for('finance.clients'))

    old_name = client.name
    client.ensure_nin_encrypted()
    client.name = name
    client.phone = phone
    client.nin = request.form.get('nin', '').strip()
    client.address = request.form.get('address', '').strip()
    client.payer_status = normalize_payer_status(request.form.get('payer_status'))

    db.session.commit()

    log_action(session['username'], 'finance', 'update', 'client', client.id,
               {'old_name': old_name, 'new_name': name, 'phone': phone, 'payer_status': client.payer_status})
    flash(f'Client "{name}" updated', 'success')
    return redirect(url_for('finance.clients'))


@finance_bp.route('/clients/<int:id>/delete', methods=['POST'])
@login_required('finance')
def delete_client(id):
    """Deactivate a client (soft delete)"""
    client = LoanClient.query.get_or_404(id)

    # Check if client has active loans
    active_loans = client.loans.filter_by(is_deleted=False).count()
    if active_loans > 0:
        flash(f'Cannot delete client with {active_loans} active loans', 'error')
        return redirect(url_for('finance.clients'))

    client.is_active = False
    db.session.commit()

    log_action(session['username'], 'finance', 'deactivate', 'client', client.id,
               {'name': client.name})
    flash(f'Client "{client.name}" deactivated', 'success')
    return redirect(url_for('finance.clients'))


# ============ INDIVIDUAL LOANS ============

@finance_bp.route('/loans')
@login_required('finance')
def loans():
    refresh_active_loans()
    status = (request.args.get('status') or '').strip().lower()
    if request.args.get('show_renewed') == '1':  # older links
        status = 'everything'
    if status not in LOAN_LIST_FILTERS:
        status = ''
    search = (request.args.get('q') or '').strip()

    query = Loan.query.filter(Loan.is_deleted == False)  # noqa: E712
    if status == '':
        query = query.filter(Loan.status != 'renewed')
    elif status != 'everything':
        query = query.filter(Loan.status == status)
    if search:
        like = f'%{search}%'
        query = query.join(LoanClient, Loan.client_id == LoanClient.id).filter(
            db.or_(LoanClient.name.ilike(like), LoanClient.phone.ilike(like))
        )
    all_loans = query.order_by(Loan.issue_date.desc()).all()
    clients = LoanClient.query.filter_by(is_active=True).order_by(LoanClient.name).all()
    return render_template(
        'finance/loans.html',
        loans=all_loans,
        totals=loan_table_totals(all_loans),
        clients=clients,
        today=get_local_today(),
        status=status,
        search=search,
        filters=LOAN_LIST_FILTERS,
        show_renewed=status in ('renewed', 'everything'),
    )


@finance_bp.route('/loans/create', methods=['POST'])
@login_required('finance')
def create_loan():
    try:
        loan_data = parse_individual_loan_form(request.form)

        loan = Loan(
            client_id=loan_data['client_id'],
            principal=loan_data['principal'],
            interest_rate=loan_data['interest_rate'],
            interest_mode=loan_data['interest_mode'],
            monthly_interest_amount=loan_data['monthly_interest_amount'],
            interest_amount=loan_data['interest_amount'],
            total_amount=loan_data['total_amount'],
            amount_paid=Decimal('0'),
            balance=loan_data['total_amount'],
            duration_weeks=loan_data['duration_weeks'],
            duration_type=loan_data['duration_type'],
            issue_date=loan_data['issue_date'],
            due_date=loan_data['due_date'],
            status='active'
        )
        db.session.add(loan)
        db.session.flush()
        refresh_loan_state(loan)  # charges the first month where the rule says so
        db.session.commit()

        client = LoanClient.query.get(loan_data['client_id'])
        log_action(session['username'], 'finance', 'create', 'loan', loan.id,
                   {'client': client.name if client else 'Unknown', 'principal': float(loan_data['principal']),
                    'total_amount': float(loan.total_amount), 'interest_mode': loan.interest_mode})
        flash('Loan created', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('finance.loans'))


@finance_bp.route('/loans/<int:id>')
@login_required('finance')
def view_loan(id):
    loan = Loan.query.get_or_404(id)
    if refresh_loan_state(loan):
        db.session.commit()
    payments = loan.payments.filter_by(is_deleted=False).order_by(LoanPayment.payment_date.desc()).all()
    return render_template(
        'finance/loan_detail.html',
        loan=loan,
        payments=payments,
        adjustments=loan.adjustments.order_by(LoanAdjustment.created_at.desc()).all(),
        payment_schedule=get_loan_payment_schedule(loan),
        today=get_local_today(),
    )


@finance_bp.route('/loans/<int:id>/pay', methods=['POST'])
@login_required('finance')
def pay_loan(id):
    # Lock the loan row so simultaneous submissions are processed one at a time.
    loan = Loan.query.filter_by(id=id).with_for_update().first_or_404()
    try:
        amount = safe_decimal(request.form.get('amount', '0'))
        payment_date = date.fromisoformat(request.form.get('payment_date', str(get_local_today())))
        notes = request.form.get('notes', '').strip()
        user_section = session.get('section', '')

        if find_recent_duplicate(LoanPayment, loan_id=loan.id, amount=amount, payment_date=payment_date):
            db.session.rollback()
            flash(DUPLICATE_MESSAGE, 'warning')
            return redirect(url_for('finance.view_loan', id=id))
        if amount <= 0:
            flash('Amount must be greater than 0', 'error')
            return redirect(url_for('finance.view_loan', id=id))
        if amount > MAX_PRINCIPAL:
            flash('Payment amount is too large.', 'error')
            return redirect(url_for('finance.view_loan', id=id))
        if not check_date_permission(payment_date, user_section):
            flash('You can only enter payments for today or yesterday. Contact a manager for older entries.', 'error')
            return redirect(url_for('finance.view_loan', id=id))

        refresh_loan_state(loan, payment_date)
        if amount > loan.balance:
            flash(f'Payment cannot exceed the current balance of UGX {loan.balance:,.0f}.', 'error')
            return redirect(url_for('finance.view_loan', id=id))

        principal_amount, interest_amount = allocate_loan_payment(loan, amount)
        refresh_loan_state(loan, payment_date)
        balance_after_payment = loan.balance
        payment_method, payment_reference = read_payment_details(request.form)

        payment = LoanPayment(
            loan_id=loan.id, payment_date=payment_date,
            amount=amount,
            principal_amount=principal_amount,
            interest_amount=interest_amount,
            payment_type='regular',
            payment_method=payment_method,
            payment_reference=payment_reference,
            balance_after=balance_after_payment,
            notes=notes
        )
        db.session.add(payment)
        db.session.flush()
        entered_out_of_order = LoanPayment.query.filter(
            LoanPayment.loan_id == loan.id,
            LoanPayment.is_deleted == False,  # noqa: E712
            LoanPayment.id != payment.id,
            LoanPayment.payment_date > payment_date,
        ).count() > 0
        if entered_out_of_order:
            # A backdated payment changes what later payments should have covered.
            replay_loan_payments(loan)
            balance_after_payment = payment.balance_after
        else:
            refresh_loan_state(loan)
        db.session.commit()

        log_action(session['username'], 'finance', 'create', 'loan_payment', payment.id,
                   {'loan_id': loan.id, 'client': loan.client.name if loan.client else 'Unknown',
                    'amount': float(amount), 'balance_after': float(balance_after_payment)})
        flash('Payment recorded', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('finance.view_loan', id=id))


@finance_bp.route('/loans/<int:id>/payment-preview')
@login_required('finance')
def preview_loan_payment_split(id):
    """Read-only: how a payment would split into interest and principal."""
    loan = Loan.query.get_or_404(id)
    amount = safe_decimal(request.args.get('amount', '0'))
    try:
        payment_date = date.fromisoformat(request.args.get('date') or str(get_local_today()))
    except ValueError:
        payment_date = get_local_today()
    if amount <= 0:
        return jsonify({'ok': False})
    preview = preview_loan_payment(loan, amount, payment_date)
    db.session.rollback()  # the preview never writes
    return jsonify({
        'ok': True,
        'interest': f"{preview['interest']:,.0f}",
        'principal': f"{preview['principal']:,.0f}",
        'balance_before': f"{preview['balance_before']:,.0f}",
        'balance_after': f"{preview['balance_after']:,.0f}",
        'exceeds_balance': amount > preview['balance_before'],
        'settles_loan': preview['settles_loan'],
    })


@finance_bp.route('/loans/<int:loan_id>/payments/<int:payment_id>/reverse', methods=['POST'])
@manager_required
def reverse_loan_payment(loan_id, payment_id):
    """Reverse a mistaken payment. Manager only; the record is kept for audit."""
    loan = Loan.query.filter_by(id=loan_id).with_for_update().first_or_404()
    payment = LoanPayment.query.filter_by(id=payment_id, loan_id=loan.id).first_or_404()
    reason = (request.form.get('reason') or '').strip()

    if payment.is_deleted:
        flash('This payment has already been reversed.', 'warning')
        return redirect(url_for('finance.view_loan', id=loan.id))
    if (payment.payment_type or 'regular') == 'renewal':
        flash('Renewal settlements cannot be reversed here.', 'error')
        return redirect(url_for('finance.view_loan', id=loan.id))
    if (loan.status or '') == 'renewed':
        flash('Payments on a renewed loan cannot be reversed.', 'error')
        return redirect(url_for('finance.view_loan', id=loan.id))
    if len(reason) < 5:
        flash('Give a reason for the reversal (at least 5 characters).', 'error')
        return redirect(url_for('finance.view_loan', id=loan.id))

    try:
        before = {'balance': float(loan.balance or 0), 'principal_paid': float(loan.principal_paid or 0),
                  'interest_paid': float(loan.interest_paid or 0), 'status': loan.status}
        reverse_loan_payment_allocation(loan, payment)
        payment.is_deleted = True
        payment.reversed_at = get_local_now()
        payment.reversed_by = session.get('username')
        payment.reversal_reason = reason[:255]
        db.session.flush()
        replay_loan_payments(loan)  # later payments are re-split without this one
        db.session.commit()

        log_action(session['username'], 'finance', 'reverse', 'loan_payment', payment.id,
                   {'loan_id': loan.id, 'client': loan.client.name if loan.client else 'Unknown',
                    'amount': float(payment.amount), 'principal_amount': float(payment.principal_amount or 0),
                    'interest_amount': float(payment.interest_amount or 0), 'reason': reason,
                    'before': before,
                    'after': {'balance': float(loan.balance or 0), 'status': loan.status}})
        flash(f'Payment of UGX {payment.amount:,.0f} reversed. Balance is now UGX {loan.balance:,.0f}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error reversing payment: {str(e)}', 'error')
    return redirect(url_for('finance.view_loan', id=loan.id))


@finance_bp.route('/loans/<int:id>/renew', methods=['POST'])
@login_required('finance')
def renew_loan(id):
    """Renew a loan by clearing old dues and rolling remaining principal."""
    try:
        old_loan = Loan.query.get_or_404(id)
        refresh_loan_state(old_loan)

        interest_owed = Decimal(str(old_loan.outstanding_interest or 0))
        principal_due = Decimal(str(old_loan.outstanding_principal or 0))
        if principal_due <= 0 and interest_owed <= 0:
            flash('This loan has no remaining balance to renew.', 'warning')
            return redirect(url_for('finance.view_loan', id=id))

        # Get new terms from form (may be revised or same as old)
        renewal_issue_date = old_loan.due_date or get_local_today()
        renewal_form = {
            'client_id': old_loan.client_id,
            'principal': request.form.get('principal', str(principal_due)),
            'interest_mode': request.form.get('interest_mode', old_loan.interest_mode or 'flat_rate'),
            'interest_rate': request.form.get('interest_rate', str(old_loan.interest_rate)),
            'monthly_interest_amount': request.form.get(
                'monthly_interest_amount',
                str(old_loan.monthly_interest_amount or 0)
            ),
            'duration_weeks': request.form.get('duration_weeks', old_loan.duration_weeks),
            'duration_type': request.form.get('duration_type', old_loan.duration_type or 'weeks'),
            # Preserve the loan cycle by starting the renewed loan from the prior due date.
            'issue_date': str(renewal_issue_date),
        }
        new_loan_data = parse_individual_loan_form(renewal_form)
        new_principal = Decimal(str(new_loan_data['principal']))

        principal_paid_at_renewal = Decimal('0')
        principal_rolled = principal_due
        top_up_principal = Decimal('0')
        if new_principal < principal_due:
            principal_paid_at_renewal = principal_due - new_principal
            principal_rolled = new_principal
        elif new_principal > principal_due:
            top_up_principal = new_principal - principal_due

        old_loan.interest_paid = Decimal(str(old_loan.interest_paid or 0)) + interest_owed
        old_loan.principal_paid = Decimal(str(old_loan.principal_paid or 0)) + principal_paid_at_renewal
        old_loan.principal_rolled = Decimal(str(old_loan.principal_rolled or 0)) + principal_rolled
        old_loan.amount_paid = Decimal(str(old_loan.amount_paid or 0)) + interest_owed + principal_paid_at_renewal
        old_loan.status = 'renewed'
        refresh_loan_state(old_loan)

        total_cash_paid = interest_owed + principal_paid_at_renewal
        if total_cash_paid > 0:
            renewal_payment = LoanPayment(
                loan_id=old_loan.id,
                amount=total_cash_paid,
                principal_amount=principal_paid_at_renewal,
                interest_amount=interest_owed,
                payment_type='renewal',
                payment_date=get_local_today(),
                balance_after=old_loan.balance,
                notes='Cleared during loan renewal'
            )
            db.session.add(renewal_payment)

        # Create new loan with (possibly revised) terms
        new_loan = Loan(
            client_id=old_loan.client_id,
            principal=new_loan_data['principal'],
            interest_rate=new_loan_data['interest_rate'],
            interest_mode=new_loan_data['interest_mode'],
            monthly_interest_amount=new_loan_data['monthly_interest_amount'],
            interest_amount=new_loan_data['interest_amount'],
            duration_weeks=new_loan_data['duration_weeks'],
            duration_type=new_loan_data['duration_type'],
            total_amount=new_loan_data['total_amount'],
            issue_date=new_loan_data['issue_date'],
            due_date=new_loan_data['due_date'],
            amount_paid=0,
            balance=new_loan_data['total_amount'],
            status='active',
            renewal_parent_id=old_loan.id
        )
        db.session.add(new_loan)
        db.session.flush()
        old_loan.renewed_to_loan_id = new_loan.id
        refresh_loan_state(new_loan)
        db.session.commit()

        # Log the renewal action
        log_action(session['username'], 'finance', 'renew', 'loan', old_loan.id,
                   {'client': old_loan.client.name if old_loan.client else 'Unknown',
                    'interest_paid': float(interest_owed),
                    'principal_paid': float(principal_paid_at_renewal),
                    'principal_rolled': float(principal_rolled),
                    'top_up_principal': float(top_up_principal),
                    'new_loan_id': new_loan.id,
                    'new_principal': float(new_loan_data['principal']),
                    'new_rate': float(new_loan_data['interest_rate']),
                    'new_weeks': new_loan_data['duration_weeks'],
                    'interest_mode': new_loan_data['interest_mode']})

        flash(
            f'Loan renewed. Interest paid: UGX {interest_owed:,.0f}; '
            f'principal rolled: UGX {principal_rolled:,.0f}. '
            f'New loan principal: UGX {new_principal:,.0f}.',
            'success'
        )
        return redirect(url_for('finance.view_loan', id=new_loan.id))

    except Exception as e:
        db.session.rollback()
        flash(f'Error renewing loan: {str(e)}', 'error')
        return redirect(url_for('finance.loans'))


@finance_bp.route('/loans/<int:id>/delete', methods=['POST'])
@manager_required
def delete_loan(id):
    loan = Loan.query.get_or_404(id)
    loan.is_deleted = True
    loan.deleted_at = db.func.now()
    db.session.commit()

    log_action(session['username'], 'finance', 'delete', 'loan', loan.id,
               {'client': loan.client.name if loan.client else 'Unknown',
                'total_amount': float(loan.total_amount)})
    flash('Loan deleted', 'success')
    return redirect(url_for('finance.loans'))


@finance_bp.route('/loans/<int:id>/edit', methods=['GET', 'POST'])
@login_required('finance')
def edit_loan(id):
    """Edit loan - manager only can edit dates"""
    loan = Loan.query.get_or_404(id)
    user_section = session.get('section', '')

    if request.method == 'POST':
        # Only managers can edit loan dates
        if user_section != 'manager':
            flash('Only managers can edit loan dates', 'error')
            return redirect(url_for('finance.view_loan', id=id))

        try:
            issue_date = date.fromisoformat(request.form.get('issue_date', str(loan.issue_date)))
            due_date = date.fromisoformat(request.form.get('due_date', str(loan.due_date)))

            old_issue_date = loan.issue_date
            old_due_date = loan.due_date

            loan.issue_date = issue_date
            loan.due_date = due_date

            # Recalculate the stored duration unit without forcing monthly loans into weeks.
            if (loan.duration_type or 'weeks') == 'months':
                delta = relativedelta(due_date, issue_date)
                loan.duration_weeks = max((delta.years * 12) + delta.months, 1)
            else:
                delta = due_date - issue_date
                loan.duration_weeks = max(delta.days // 7, 1)

            # New dates change accrued interest and status; recompute centrally.
            refresh_loan_state(loan)

            db.session.commit()

            log_action(session['username'], 'finance', 'update', 'loan', loan.id,
                       {'action': 'edit_dates',
                        'old_issue_date': str(old_issue_date),
                        'new_issue_date': str(issue_date),
                        'old_due_date': str(old_due_date),
                        'new_due_date': str(due_date)})

            flash('Loan dates updated successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating loan: {str(e)}', 'error')

        return redirect(url_for('finance.view_loan', id=id))

    # GET request - show edit form
    if refresh_loan_state(loan):
        db.session.commit()
    clients = LoanClient.query.filter_by(is_active=True).order_by(LoanClient.name).all()
    return render_template('finance/edit_loan.html', loan=loan, clients=clients,
                          is_manager=(user_section == 'manager'))


# ============ GROUP LOANS ============

@finance_bp.route('/group-loans')
@login_required('finance')
def group_loans():
    refresh_open_group_loans()
    all_groups = GroupLoan.query.filter_by(is_deleted=False).order_by(GroupLoan.created_at.desc()).all()
    return render_template(
        'finance/group_loans.html',
        groups=all_groups,
        totals=group_table_totals(all_groups),
        today=get_local_today(),
    )


@finance_bp.route('/group-loans/create', methods=['POST'])
@login_required('finance')
def create_group_loan():
    try:
        group_data = parse_group_loan_form(request.form)
        user_section = session.get('section', '')
        if not check_date_permission(group_data['issue_date'], user_section):
            flash('You can only create loans for today or yesterday. Contact a manager for older entries.', 'error')
            return redirect(url_for('finance.group_loans'))

        group = GroupLoan(
            group_name=group_data['group_name'],
            member_count=group_data['member_count'],
            principal=group_data['principal'],
            interest_rate=group_data['interest_rate'],
            interest_amount=group_data['interest_amount'],
            total_amount=group_data['total_amount'],
            amount_per_period=group_data['amount_per_period'],
            total_periods=group_data['total_periods'],
            period_type=group_data['period_type'],
            periods_paid=0,
            amount_paid=Decimal('0'),
            balance=group_data['total_amount'],
            issue_date=group_data['issue_date'],
            due_date=group_data['due_date'],
            status='active'
        )
        db.session.add(group)
        db.session.commit()

        log_action(session['username'], 'finance', 'create', 'group_loan', group.id,
                   {'group_name': group.group_name, 'principal': float(group.principal),
                    'total_amount': float(group.total_amount), 'member_count': group.member_count})
        flash('Group loan created', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('finance.group_loans'))


@finance_bp.route('/group-loans/<int:id>')
@login_required('finance')
def view_group_loan(id):
    group = GroupLoan.query.get_or_404(id)
    if refresh_group_loan_state(group):
        db.session.commit()
    payments = group.payments.filter_by(is_deleted=False).order_by(GroupLoanPayment.payment_date.desc()).all()
    adjustments = group.adjustments.order_by(LoanAdjustment.created_at.desc()).all()
    return render_template('finance/group_loan_detail.html', group=group, payments=payments,
                           adjustments=adjustments, today=get_local_today())


@finance_bp.route('/group-loans/<int:id>/pay', methods=['POST'])
@login_required('finance')
def pay_group_loan(id):
    group = GroupLoan.query.filter_by(id=id).with_for_update().first_or_404()
    try:
        amount = safe_decimal(request.form.get('amount', '0'))
        payment_date = date.fromisoformat(request.form.get('payment_date', str(get_local_today())))
        notes = request.form.get('notes', '').strip()
        user_section = session.get('section', '')

        if find_recent_duplicate(GroupLoanPayment, group_loan_id=group.id, amount=amount, payment_date=payment_date):
            db.session.rollback()
            flash(DUPLICATE_MESSAGE, 'warning')
            return redirect(url_for('finance.view_group_loan', id=id))
        if amount <= 0:
            flash('Amount must be greater than 0', 'error')
            return redirect(url_for('finance.view_group_loan', id=id))
        if amount > MAX_PRINCIPAL:
            flash('Payment amount is too large.', 'error')
            return redirect(url_for('finance.view_group_loan', id=id))
        if not check_date_permission(payment_date, user_section):
            flash('You can only enter payments for today or yesterday. Contact a manager for older entries.', 'error')
            return redirect(url_for('finance.view_group_loan', id=id))
        if amount > group.balance:
            flash(f'Payment cannot exceed the current balance of UGX {group.balance:,.0f}.', 'error')
            return redirect(url_for('finance.view_group_loan', id=id))

        periods_before = group.periods_paid or 0
        group.amount_paid += amount
        refresh_group_loan_state(group)  # also derives periods paid from the money paid
        periods_covered = (group.periods_paid or 0) - periods_before
        payment_method, payment_reference = read_payment_details(request.form)

        payment = GroupLoanPayment(
            group_loan_id=group.id, payment_date=payment_date,
            amount=amount, periods_covered=periods_covered,
            payment_method=payment_method, payment_reference=payment_reference,
            balance_after=group.balance, notes=notes
        )
        db.session.add(payment)
        db.session.commit()

        log_action(session['username'], 'finance', 'create', 'group_loan_payment', payment.id,
                   {'group_name': group.group_name, 'amount': float(amount),
                    'periods_covered': periods_covered, 'balance_after': float(group.balance)})
        flash('Payment recorded', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('finance.view_group_loan', id=id))


@finance_bp.route('/group-loans/<int:group_id>/payments/<int:payment_id>/reverse', methods=['POST'])
@manager_required
def reverse_group_loan_payment(group_id, payment_id):
    """Reverse a mistaken group payment. Manager only; the record is kept for audit."""
    group = GroupLoan.query.filter_by(id=group_id).with_for_update().first_or_404()
    payment = GroupLoanPayment.query.filter_by(id=payment_id, group_loan_id=group.id).first_or_404()
    reason = (request.form.get('reason') or '').strip()

    if payment.is_deleted:
        flash('This payment has already been reversed.', 'warning')
        return redirect(url_for('finance.view_group_loan', id=group.id))
    if len(reason) < 5:
        flash('Give a reason for the reversal (at least 5 characters).', 'error')
        return redirect(url_for('finance.view_group_loan', id=group.id))

    try:
        before = {'balance': float(group.balance or 0), 'amount_paid': float(group.amount_paid or 0),
                  'periods_paid': group.periods_paid, 'status': group.status}
        group.amount_paid = max(Decimal(str(group.amount_paid or 0)) - Decimal(str(payment.amount or 0)), Decimal('0'))
        payment.is_deleted = True
        payment.reversed_at = get_local_now()
        payment.reversed_by = session.get('username')
        payment.reversal_reason = reason[:255]
        refresh_group_loan_state(group)
        db.session.commit()

        log_action(session['username'], 'finance', 'reverse', 'group_loan_payment', payment.id,
                   {'group_loan_id': group.id, 'group_name': group.group_name,
                    'amount': float(payment.amount), 'periods_covered': payment.periods_covered,
                    'reason': reason, 'before': before,
                    'after': {'balance': float(group.balance or 0), 'status': group.status}})
        flash(f'Payment of UGX {payment.amount:,.0f} reversed. Balance is now UGX {group.balance:,.0f}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error reversing payment: {str(e)}', 'error')
    return redirect(url_for('finance.view_group_loan', id=group.id))


# ============ CONVERT OLD FLAT-RATE LOANS (manager) ============

@finance_bp.route('/convert-flat-loans', methods=['GET', 'POST'])
@manager_required
def convert_flat_loans():
    """Preview, then apply, the conversion of open flat-rate loans to monthly interest."""
    from app.services.loan_conversion import convert_open_flat_loans

    if request.method == 'POST':
        if request.form.get('confirm') != 'CONVERT':
            flash('Type CONVERT in the box to confirm.', 'error')
            return redirect(url_for('finance.convert_flat_loans'))
        try:
            rows, skipped = convert_open_flat_loans()
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception('Flat-rate loan conversion failed')
            flash('The conversion could not be completed. Nothing was changed.', 'error')
            return redirect(url_for('finance.convert_flat_loans'))
        for row in rows:
            log_action(session['username'], 'finance', 'correct', 'loan', row['loan_id'],
                       {'action': 'convert_flat_to_monthly', 'rate_per_month': row['rate_per_month'],
                        'balance_before': row['balance_before'], 'balance_after': row['balance_after']})
        flash(f'{len(rows)} loan(s) now accumulate monthly interest.', 'success')
        return redirect(url_for('finance.loans'))

    # Preview: run the conversion, capture the figures, then undo it.
    try:
        rows, skipped = convert_open_flat_loans()
    finally:
        db.session.rollback()
    return render_template(
        'finance/convert_flat_loans.html',
        rows=rows,
        skipped=skipped,
        total_before=sum(row['balance_before'] for row in rows),
        total_after=sum(row['balance_after'] for row in rows),
    )


# ============ REMINDERS (SMS / WhatsApp) ============

@finance_bp.route('/reminders')
@login_required('finance')
def reminders():
    from app.services import reminders as reminder_service

    refresh_active_loans()
    today = get_local_today()
    rows = reminder_service.due_reminders(today)
    return render_template(
        'finance/reminders.html',
        rows=rows,
        due_soon=[row for row in rows if row['kind'] == 'due_soon'],
        overdue=[row for row in rows if row['kind'] == 'overdue'],
        sms_enabled=reminder_service.sms_enabled(),
        today=today,
    )


def _reminder_row(loan_id):
    from app.services import reminders as reminder_service

    today = get_local_today()
    for row in reminder_service.due_reminders(today):
        if row['loan'].id == loan_id:
            return row, today, reminder_service
    return None, today, reminder_service


@finance_bp.route('/reminders/<int:loan_id>/whatsapp', methods=['POST'])
@login_required('finance')
def reminder_whatsapp(loan_id):
    """Log the reminder, then open WhatsApp with the message filled in."""
    row, today, reminder_service = _reminder_row(loan_id)
    if not row or not row['whatsapp_url']:
        flash('This borrower has no valid phone number for WhatsApp.', 'error')
        return redirect(url_for('finance.reminders'))
    reminder_service.record(row['loan'], row['kind'], 'whatsapp', row['phone'], row['message'], 'opened',
                            today, sent_by=session.get('username'))
    return redirect(row['whatsapp_url'])


@finance_bp.route('/reminders/<int:loan_id>/sms', methods=['POST'])
@login_required('finance')
def reminder_sms(loan_id):
    row, today, reminder_service = _reminder_row(loan_id)
    if not row or not row['phone']:
        flash('This borrower has no valid phone number.', 'error')
    elif not reminder_service.sms_enabled():
        flash('SMS is not set up yet. Use the WhatsApp button, or ask the administrator to add the SMS account.', 'error')
    elif not row['sms_allowed']:
        flash('An SMS reminder was already sent to this borrower in the last 7 days.', 'warning')
    else:
        ok, detail = reminder_service.send_reminder_sms(row, today, sent_by=session.get('username'))
        flash('SMS reminder sent.' if ok else f'SMS could not be sent ({detail}).', 'success' if ok else 'error')
    return redirect(url_for('finance.reminders'))


# ============ ADJUSTMENTS (discounts, waivers, write-offs, charges) ============

def _adjustment_redirect(adjustment_or_target):
    group_id = getattr(adjustment_or_target, 'group_loan_id', None)
    if isinstance(adjustment_or_target, GroupLoan) or group_id:
        return redirect(url_for('finance.view_group_loan', id=group_id or adjustment_or_target.id))
    loan_id = getattr(adjustment_or_target, 'loan_id', None) or adjustment_or_target.id
    return redirect(url_for('finance.view_loan', id=loan_id))


def _create_adjustment(target, kind):
    adjustment_type = (request.form.get('adjustment_type') or '').strip()
    amount = round_money(safe_decimal(request.form.get('amount', '0')))
    reason = (request.form.get('reason') or '').strip()
    try:
        effective_date = date.fromisoformat(request.form.get('effective_date') or str(get_local_today()))
    except ValueError:
        effective_date = get_local_today()

    if adjustment_type not in LoanAdjustment.TYPES:
        flash('Choose an adjustment type.', 'error')
        return _adjustment_redirect(target)
    if amount <= 0 or amount > MAX_PRINCIPAL:
        flash('Enter an amount greater than 0.', 'error')
        return _adjustment_redirect(target)
    if len(reason) < 5:
        flash('Give a reason for the adjustment (at least 5 characters).', 'error')
        return _adjustment_redirect(target)
    if (kind == 'loan' and (target.interest_mode or 'flat_rate') == 'reducing_balance_equal'
            and adjustment_type in ('interest_discount', 'interest_waiver')):
        flash('Interest discounts are not yet supported on reducing-balance loans.', 'error')
        return _adjustment_redirect(target)
    if kind == 'loan' and (target.status or '') == 'renewed':
        flash('A renewed loan cannot be adjusted; adjust the new loan instead.', 'error')
        return _adjustment_redirect(target)
    if adjustment_type == 'principal_write_off':
        days_overdue = (get_local_today() - target.due_date).days if target.due_date else 0
        if days_overdue < WRITE_OFF_MIN_DAYS_OVERDUE:
            flash('Principal can only be written off once a loan is 6 months overdue. '
                  'Use an interest discount instead.', 'error')
            return _adjustment_redirect(target)

    if kind == 'loan':
        refresh_loan_state(target)
    else:
        refresh_group_loan_state(target)
    limit = adjustment_limit(target, adjustment_type)
    if limit is not None and amount > limit:
        flash(f'{LoanAdjustment.TYPES[adjustment_type]} cannot exceed UGX {limit:,.0f} outstanding.', 'error')
        return _adjustment_redirect(target)

    before = float(target.balance or 0)
    adjustment = LoanAdjustment(
        loan_id=target.id if kind == 'loan' else None,
        group_loan_id=target.id if kind == 'group' else None,
        adjustment_type=adjustment_type,
        amount=amount,
        effective_date=effective_date,
        reason=reason[:500],
        created_by=session.get('username'),
    )
    db.session.add(adjustment)
    apply_adjustment(target, adjustment)
    db.session.flush()
    if kind == 'loan':
        replay_loan_payments(target)
    else:
        refresh_group_loan_state(target)
    db.session.commit()

    log_action(session['username'], 'finance', 'create', 'loan_adjustment', adjustment.id,
               {'kind': kind, 'target_id': target.id, 'type': adjustment_type, 'amount': float(amount),
                'reason': reason, 'balance_before': before, 'balance_after': float(target.balance or 0)})
    flash(f'{adjustment.type_label} of UGX {amount:,.0f} recorded. Balance is now UGX {target.balance:,.0f}.', 'success')
    return _adjustment_redirect(target)


@finance_bp.route('/loans/<int:id>/adjustments', methods=['POST'])
@manager_required
def create_loan_adjustment(id):
    loan = Loan.query.filter_by(id=id).with_for_update().first_or_404()
    return _create_adjustment(loan, 'loan')


@finance_bp.route('/group-loans/<int:id>/adjustments', methods=['POST'])
@manager_required
def create_group_loan_adjustment(id):
    group = GroupLoan.query.filter_by(id=id).with_for_update().first_or_404()
    return _create_adjustment(group, 'group')


@finance_bp.route('/adjustments/<int:id>/reverse', methods=['POST'])
@manager_required
def reverse_adjustment(id):
    adjustment = LoanAdjustment.query.get_or_404(id)
    reason = (request.form.get('reason') or '').strip()
    if adjustment.is_reversed:
        flash('This adjustment has already been reversed.', 'warning')
        return _adjustment_redirect(adjustment)
    if len(reason) < 5:
        flash('Give a reason for the reversal (at least 5 characters).', 'error')
        return _adjustment_redirect(adjustment)

    if adjustment.loan_id:
        target = Loan.query.filter_by(id=adjustment.loan_id).with_for_update().first_or_404()
    else:
        target = GroupLoan.query.filter_by(id=adjustment.group_loan_id).with_for_update().first_or_404()
    before = float(target.balance or 0)
    apply_adjustment(target, adjustment, reverse=True)
    adjustment.is_reversed = True
    adjustment.reversed_by = session.get('username')
    adjustment.reversed_at = get_local_now()
    adjustment.reversal_reason = reason[:255]
    db.session.flush()
    if adjustment.loan_id:
        replay_loan_payments(target)
    else:
        refresh_group_loan_state(target)
    db.session.commit()

    log_action(session['username'], 'finance', 'reverse', 'loan_adjustment', adjustment.id,
               {'type': adjustment.adjustment_type, 'amount': float(adjustment.amount), 'reason': reason,
                'balance_before': before, 'balance_after': float(target.balance or 0)})
    flash(f'{adjustment.type_label} reversed. Balance is now UGX {target.balance:,.0f}.', 'success')
    return _adjustment_redirect(adjustment)


@finance_bp.route('/group-loans/<int:id>/delete', methods=['POST'])
@manager_required
def delete_group_loan(id):
    group = GroupLoan.query.get_or_404(id)
    group.is_deleted = True
    db.session.commit()

    log_action(session['username'], 'finance', 'delete', 'group_loan', group.id,
               {'group_name': group.group_name, 'total_amount': float(group.total_amount)})
    flash('Group loan deleted', 'success')
    return redirect(url_for('finance.group_loans'))


@finance_bp.route('/group-loans/<int:id>/edit', methods=['GET', 'POST'])
@login_required('finance')
def edit_group_loan(id):
    """Edit group loan - manager only can edit dates"""
    group = GroupLoan.query.get_or_404(id)
    user_section = session.get('section', '')

    if request.method == 'POST':
        # Only managers can edit dates
        if user_section != 'manager':
            flash('Only managers can edit loan dates', 'error')
            return redirect(url_for('finance.view_group_loan', id=id))

        try:
            issue_date = date.fromisoformat(request.form.get('issue_date', str(group.issue_date)))
            due_date = date.fromisoformat(request.form.get('due_date', str(group.due_date)))

            old_issue_date = group.issue_date
            old_due_date = group.due_date

            group.issue_date = issue_date
            group.due_date = due_date

            # Update status based on new due date
            today = get_local_today()
            if group.balance <= 0:
                group.status = 'paid'
            elif due_date < today:
                group.status = 'overdue'
            else:
                group.status = 'active'

            db.session.commit()

            log_action(session['username'], 'finance', 'update', 'group_loan', group.id,
                       {'action': 'edit_dates',
                        'old_issue_date': str(old_issue_date),
                        'new_issue_date': str(issue_date),
                        'old_due_date': str(old_due_date),
                        'new_due_date': str(due_date)})

            flash('Group loan dates updated successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating group loan: {str(e)}', 'error')

        return redirect(url_for('finance.view_group_loan', id=id))

    # GET request - show edit form
    return render_template('finance/edit_group_loan.html', group=group,
                          is_manager=(user_section == 'manager'))


# ============ PAYMENTS HISTORY ============

@finance_bp.route('/payments')
@login_required('finance')
def payments():
    loan_payments = LoanPayment.query.filter_by(is_deleted=False).order_by(LoanPayment.payment_date.desc()).limit(50).all()
    group_payments = GroupLoanPayment.query.filter_by(is_deleted=False).order_by(GroupLoanPayment.payment_date.desc()).limit(50).all()
    return render_template('finance/payments.html', loan_payments=loan_payments, group_payments=group_payments)


# ============ LOAN AGREEMENT ============

@finance_bp.route('/loans/preview-agreement', methods=['POST'])
@login_required('finance')
def preview_loan_agreement():
    """Preview individual loan agreement before issuing"""
    try:
        loan_data = parse_individual_loan_form(request.form)
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('finance.loans'))

    client = LoanClient.query.get(loan_data['client_id'])
    if not client:
        flash('Client not found', 'error')
        return redirect(url_for('finance.loans'))
    projected_interest_amount = loan_data['interest_amount']
    projected_total_amount = loan_data['total_amount']
    payment_schedule = []
    if loan_data['interest_mode'] == 'monthly_accrual':
        projected_interest_amount = loan_data['monthly_interest_amount'] * loan_data['duration_weeks']
        projected_total_amount = loan_data['principal'] + projected_interest_amount
    elif loan_data['interest_mode'] == 'reducing_balance_equal':
        payment_schedule = calculate_reducing_balance_schedule(
            loan_data['principal'],
            loan_data['interest_rate'],
            loan_data['duration_weeks'],
            loan_data['issue_date'],
        )

    # Default agreement terms that can be edited
    default_terms = [
        "The Borrower agrees to repay the loan amount plus interest as specified above.",
        "Interest is charged every month on the unpaid principal, starting on the issue date, and reduces as principal is repaid.",
        "If the loan is not fully repaid by the due date, monthly interest continues to be charged until it is cleared.",
        "Payments are applied to interest first and then to principal.",
        "The Borrower may repay the loan early without any prepayment penalties.",
        "In case of default, the Lender reserves the right to take legal action to recover the debt.",
        "The Borrower agrees that all information provided is true and accurate.",
        "This agreement is binding upon signing by both parties.",
        "Any disputes arising from this agreement shall be resolved through arbitration."
    ]

    return render_template('finance/loan_agreement_preview.html',
        client=client,
        principal=float(loan_data['principal']),
        interest_rate=float(loan_data['interest_rate']),
        interest_mode=loan_data['interest_mode'],
        monthly_interest_amount=float(loan_data['monthly_interest_amount'] or 0),
        interest_amount=float(loan_data['interest_amount']),
        projected_interest_amount=float(projected_interest_amount),
        total_amount=float(loan_data['total_amount']),
        projected_total_amount=float(projected_total_amount),
        payment_schedule=payment_schedule,
        duration_weeks=loan_data['duration_weeks'],
        duration_type=loan_data['duration_type'],
        issue_date=loan_data['issue_date'],
        due_date=loan_data['due_date'],
        default_terms=default_terms,
        today=get_local_today()
    )


@finance_bp.route('/loans/create-with-agreement', methods=['POST'])
@login_required('finance')
def create_loan_with_agreement():
    """Create loan after agreement review"""
    try:
        loan_data = parse_individual_loan_form(request.form)

        # Check date permission
        user_section = session.get('section', '')
        if not check_date_permission(loan_data['issue_date'], user_section):
            flash('You can only create loans for today or yesterday. Contact a manager for older entries.', 'error')
            return redirect(url_for('finance.loans'))

        loan = Loan(
            client_id=loan_data['client_id'],
            principal=loan_data['principal'],
            interest_rate=loan_data['interest_rate'],
            interest_mode=loan_data['interest_mode'],
            monthly_interest_amount=loan_data['monthly_interest_amount'],
            interest_amount=loan_data['interest_amount'],
            total_amount=loan_data['total_amount'],
            amount_paid=Decimal('0'),
            balance=loan_data['total_amount'],
            duration_weeks=loan_data['duration_weeks'],
            duration_type=loan_data['duration_type'],
            issue_date=loan_data['issue_date'],
            due_date=loan_data['due_date'],
            status='active'
        )
        db.session.add(loan)
        db.session.flush()
        refresh_loan_state(loan)  # charges the first month where the rule says so

        # Handle collateral document upload
        if 'collateral_file' in request.files:
            file = request.files['collateral_file']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'collateral')
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, f'loan_{loan.id}_{filename}')
                if validate_and_save(file, file_path):
                    doc = LoanDocument(
                        loan_id=loan.id,
                        filename=filename,
                        file_path=file_path,
                        file_type=filename.rsplit('.', 1)[1].lower() if '.' in filename else 'unknown'
                    )
                    db.session.add(doc)

        db.session.commit()

        client = LoanClient.query.get(loan_data['client_id'])
        log_action(session['username'], 'finance', 'create', 'loan', loan.id,
                   {'client': client.name if client else 'Unknown', 'principal': float(loan_data['principal']),
                    'total_amount': float(loan.total_amount), 'interest_mode': loan.interest_mode})
        flash('Loan created successfully', 'success')
        return redirect(url_for('finance.view_loan', id=loan.id))
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('finance.loans'))


@finance_bp.route('/loans/<int:id>/agreement-pdf')
@login_required('finance')
def download_loan_agreement_pdf(id):
    """Download individual loan agreement as PDF"""
    loan = Loan.query.get_or_404(id)
    if refresh_loan_state(loan):
        db.session.commit()

    buffer = io.BytesIO()
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from app.utils.branding import get_company_display_name
    from app.utils.pdf_generator import draw_logo_header

    brand_display_name = get_company_display_name()
    projected_interest = float(loan.interest_amount)
    projected_total = float(loan.total_amount)
    if loan.interest_mode == 'monthly_accrual':
        projected_interest = float((loan.monthly_interest_amount or 0) * loan.duration_weeks)
        projected_total = float(loan.principal) + projected_interest
    payment_schedule = get_loan_payment_schedule(loan)

    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 26
    y = draw_logo_header(c, width, y)

    y -= 8
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width/2, y, "INDIVIDUAL LOAN AGREEMENT")
    y -= 30
    c.line(50, y, width-50, y)

    y -= 30
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "BORROWER INFORMATION")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Name: {loan.client.name if loan.client else 'N/A'}")
    y -= 15
    c.drawString(50, y, f"Phone: {loan.client.phone if loan.client else 'N/A'}")
    y -= 15
    c.drawString(50, y, f"NIN: {loan.client.nin if loan.client and loan.client.nin else 'N/A'}")
    y -= 15
    c.drawString(50, y, f"Address: {loan.client.address if loan.client and loan.client.address else 'N/A'}")

    y -= 30
    c.line(50, y, width-50, y)
    y -= 25
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "LOAN DETAILS")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Principal Amount: UGX {float(loan.principal):,.0f}")
    y -= 15
    plan_label = 'Monthly Accrual'
    if loan.interest_mode == 'reducing_balance_equal':
        plan_label = 'Reducing Balance - Equal Monthly Payments'
    elif loan.interest_mode != 'monthly_accrual':
        plan_label = 'Flat Rate'
    c.drawString(50, y, f"Interest Plan: {plan_label}")
    y -= 15
    c.drawString(50, y, f"Equivalent Rate: {float(loan.interest_rate):,.2f}%")
    y -= 15

    if loan.interest_mode == 'monthly_accrual':
        c.drawString(50, y, f"Monthly Interest: UGX {float(loan.monthly_interest_amount or 0):,.0f}")
        y -= 15
        c.drawString(50, y, f"Accrued Interest To Date: UGX {float(loan.interest_amount):,.0f}")
        y -= 15
        c.drawString(50, y, f"Projected Interest By Due Date: UGX {projected_interest:,.0f}")
        y -= 15
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, f"Current Amount Due: UGX {float(loan.total_amount):,.0f}")
        c.setFont("Helvetica", 10)
        y -= 15
        c.drawString(50, y, f"Projected Amount By Due Date: UGX {projected_total:,.0f}")
    elif loan.interest_mode == 'reducing_balance_equal':
        c.drawString(50, y, f"Monthly Payment: UGX {float(loan.monthly_interest_amount or 0):,.0f}")
        y -= 15
        c.drawString(50, y, f"Total Scheduled Interest: UGX {float(loan.interest_amount):,.0f}")
        y -= 15
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, f"Total Scheduled Repayment: UGX {float(loan.total_amount):,.0f}")
        c.setFont("Helvetica", 10)
    else:
        c.drawString(50, y, f"Interest Amount: UGX {float(loan.interest_amount):,.0f}")
        y -= 15
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, f"Total Repayment: UGX {float(loan.total_amount):,.0f}")
        c.setFont("Helvetica", 10)

    y -= 15
    duration_label = loan.duration_type or 'weeks'
    c.drawString(50, y, f"Duration: {loan.duration_weeks} {duration_label}")
    y -= 15
    c.drawString(50, y, f"Issue Date: {loan.issue_date.strftime('%B %d, %Y')}")
    y -= 15
    c.drawString(50, y, f"Due Date: {loan.due_date.strftime('%B %d, %Y')}")

    if payment_schedule:
        y -= 28
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, "REDUCING BALANCE REPAYMENT SCHEDULE")
        y -= 18
        c.setFont("Helvetica-Bold", 8)
        c.drawString(50, y, "Month")
        c.drawRightString(170, y, "Payment")
        c.drawRightString(270, y, "Interest")
        c.drawRightString(380, y, "Principal")
        c.drawRightString(500, y, "Balance")
        y -= 12
        c.setFont("Helvetica", 8)
        for row in payment_schedule:
            if y < 120:
                c.showPage()
                y = height - 60
            c.drawString(50, y, str(row['period']))
            c.drawRightString(170, y, f"{float(row['payment']):,.0f}")
            c.drawRightString(270, y, f"{float(row['interest']):,.0f}")
            c.drawRightString(380, y, f"{float(row['principal']):,.0f}")
            c.drawRightString(500, y, f"{float(row['balance_after']):,.0f}")
            y -= 12

    y -= 30
    c.line(50, y, width-50, y)
    y -= 25
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "TERMS AND CONDITIONS")
    y -= 20
    c.setFont("Helvetica", 9)
    terms = [
        "1. The Borrower agrees to repay the loan amount plus interest as specified above.",
        "2. Interest is charged monthly on the unpaid principal from the issue date.",
        "3. If not fully repaid by the due date, monthly interest continues until cleared.",
        "4. Payments are applied to interest first, then principal. Early repayment is allowed.",
        "5. This agreement is binding upon signing by both parties."
    ]
    for term in terms:
        c.drawString(50, y, term)
        y -= 15

    y -= 40
    c.line(50, y, width-50, y)
    y -= 30
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "BORROWER:")
    c.drawString(320, y, f"LENDER ({brand_display_name.upper()}):")
    y -= 40
    c.line(50, y, 200, y)
    c.line(320, y, 500, y)
    y -= 15
    c.setFont("Helvetica", 9)
    c.drawString(50, y, "Signature & Date")
    c.drawString(320, y, "Signature & Date")

    c.save()
    buffer.seek(0)

    return Response(
        buffer.getvalue(),
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename=loan_agreement_{loan.id}.pdf'}
    )


@finance_bp.route('/loans/<int:id>/statement-pdf')
@login_required('finance')
def download_loan_statement_pdf(id):
    """Download a printable/shareable statement for an individual loan."""
    loan = Loan.query.get_or_404(id)
    if refresh_loan_state(loan):
        db.session.commit()

    payments = loan.payments.filter_by(is_deleted=False).order_by(LoanPayment.payment_date.asc()).all()
    adjustments = loan.adjustments.order_by(LoanAdjustment.effective_date.asc()).all()
    buffer = generate_loan_statement_pdf(loan, payments, get_loan_payment_schedule(loan), adjustments)

    log_action(session.get('username'), 'finance', 'view', 'loan_statement', loan.id,
               {'client': loan.client.name if loan.client else 'Unknown'})

    return Response(
        buffer.getvalue(),
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename=loan_statement_{loan.id}.pdf'}
    )


@finance_bp.route('/loans/<int:id>/payment-plan-pdf', methods=['GET', 'POST'])
@login_required('finance')
def download_payment_plan_pdf(id):
    """Let a manager author and print an exact client-specific payment plan."""
    loan = Loan.query.get_or_404(id)
    if refresh_loan_state(loan):
        db.session.commit()

    if session.get('section') != 'manager':
        flash('Only a manager can prepare and issue a payment plan.', 'error')
        return redirect(url_for('finance.view_loan', id=id))
    if round_money(loan.balance) <= 0:
        flash('A payment plan can only be prepared for a loan with an outstanding balance.', 'error')
        return redirect(url_for('finance.view_loan', id=id))

    defaults = {
        'plan_title': 'Proposed Payment Plan',
        'plan_amount': str(round_money(loan.balance)),
        'deposit': '0',
        'interest_method': 'reducing_balance',
        'rate_percent': '31',
        'rate_basis': 'annum',
        'frequency': 'monthly',
        'installments': '3',
        'first_due_date': str(get_local_today() + relativedelta(months=1)),
        'manager_notes': '',
        'plan_terms': (
            'Payments must be made on or before each due date. '
            'Any changes to this plan must be approved by management in writing.'
        ),
    }

    if request.method == 'GET':
        return render_template(
            'finance/payment_plan_builder.html',
            loan=loan,
            form_values=defaults,
            today=get_local_today(),
        )

    form_values = {key: request.form.get(key, value) for key, value in defaults.items()}
    try:
        plan_amount = safe_decimal(form_values['plan_amount'])
        current_balance = round_money(loan.balance)
        if plan_amount > current_balance:
            raise ValueError(
                f'Plan amount cannot exceed the current balance of UGX {current_balance:,.0f}.'
            )
        installments = int(form_values['installments'])
        first_due_date = date.fromisoformat(form_values['first_due_date'])
        if first_due_date < get_local_today():
            raise ValueError('The first payment date cannot be in the past.')

        plan = calculate_manager_payment_plan(
            plan_amount=plan_amount,
            deposit=safe_decimal(form_values['deposit']),
            interest_method=form_values['interest_method'],
            rate_percent=safe_decimal(form_values['rate_percent']),
            rate_basis=form_values['rate_basis'],
            frequency=form_values['frequency'],
            installments=installments,
            first_due_date=first_due_date,
        )
        title = str(form_values['plan_title'] or '').strip()
        if not title or len(title) > 100:
            raise ValueError('Plan title is required and must not exceed 100 characters.')
        notes = str(form_values['manager_notes'] or '').strip()
        terms = str(form_values['plan_terms'] or '').strip()
        if len(notes) > 2000 or len(terms) > 3000:
            raise ValueError('Notes or terms are too long for the payment-plan report.')

        plan.update({
            'title': title,
            'manager_notes': notes,
            'plan_terms': terms,
            'prepared_by': session.get('username') or 'Manager',
            'prepared_on': get_local_today(),
            'current_balance': current_balance,
            'unplanned_balance': current_balance - plan_amount,
        })
    except (ValueError, TypeError, InvalidOperation) as exc:
        flash(str(exc) or 'Please review the payment-plan details.', 'error')
        return render_template(
            'finance/payment_plan_builder.html',
            loan=loan,
            form_values=form_values,
            today=get_local_today(),
        ), 400

    payments = loan.payments.filter_by(is_deleted=False).order_by(LoanPayment.payment_date.asc()).all()
    buffer = generate_payment_plan_pdf(loan, payments, plan)

    log_action(session.get('username'), 'finance', 'view', 'payment_plan', loan.id,
               {
                   'client': loan.client.name if loan.client else 'Unknown',
                   'plan_amount': float(plan['plan_amount']),
                   'interest_method': plan['interest_method'],
                   'rate_percent': float(plan['rate_percent']),
                   'rate_basis': plan['rate_basis'],
                   'frequency': plan['frequency'],
                   'installments': plan['installments'],
               })

    return Response(
        buffer.getvalue(),
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename=payment_plan_{loan.id}.pdf'}
    )


@finance_bp.route('/loans/<int:id>/overdue-reminder-pdf')
@login_required('finance')
def download_overdue_reminder_pdf(id):
    """Download a reminder letter with the borrower's current financial summary."""
    loan = Loan.query.get_or_404(id)
    if refresh_loan_state(loan):
        db.session.commit()

    payments = loan.payments.filter_by(is_deleted=False).order_by(LoanPayment.payment_date.asc()).all()
    buffer = generate_overdue_reminder_pdf(loan, payments, get_loan_payment_schedule(loan))

    log_action(session.get('username'), 'finance', 'view', 'overdue_reminder', loan.id,
               {'client': loan.client.name if loan.client else 'Unknown'})

    return Response(
        buffer.getvalue(),
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename=overdue_reminder_{loan.id}.pdf'}
    )


@finance_bp.route('/group-loans/preview-agreement', methods=['POST'])
@login_required('finance')
def preview_group_loan_agreement():
    """Preview group loan agreement before issuing"""
    try:
        group_data = parse_group_loan_form(request.form)
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('finance.group_loans'))

    # Pre-calculate payment schedule (first 6 periods)
    payment_schedule = []
    period_days = PERIOD_DAYS.get(group_data['period_type'], 30)
    for i in range(1, min(group_data['total_periods'] + 1, 7)):
        payment_date = group_data['issue_date'] + timedelta(days=period_days * i)
        payment_schedule.append({
            'period': i,
            'due_date': payment_date,
            'amount': float(group_data['amount_per_period'])
        })

    # Default agreement terms that can be edited
    default_terms = [
        "All members of the group are jointly and severally liable for the loan repayment.",
        "Payments shall be made according to the schedule specified in this agreement.",
        "The total repayable is fixed; late payments may affect future loan eligibility.",
        "The group may repay the loan early without any prepayment penalties.",
        "In case of default by any member, other members are responsible for covering the payment.",
        "All group members agree to attend mandatory group meetings as required.",
        "The group leader is responsible for collecting and submitting payments on behalf of the group.",
        "Any disputes shall be resolved through mediation before legal action."
    ]

    return render_template('finance/group_loan_agreement_preview.html',
        group_name=group_data['group_name'],
        member_count=group_data['member_count'],
        principal=float(group_data['principal']),
        interest_rate=float(group_data['interest_rate']),
        interest_amount=float(group_data['interest_amount']),
        total_amount=float(group_data['total_amount']),
        total_periods=group_data['total_periods'],
        period_type=group_data['period_type'],
        amount_per_period=float(group_data['amount_per_period']),
        issue_date=group_data['issue_date'],
        due_date=group_data['due_date'],
        payment_schedule=payment_schedule,
        default_terms=default_terms,
        today=get_local_today()
    )


@finance_bp.route('/group-loans/create-with-agreement', methods=['POST'])
@login_required('finance')
def create_group_loan_with_agreement():
    """Create group loan after agreement review"""
    try:
        group_data = parse_group_loan_form(request.form)
        members_data = request.form.get('members_data', '')

        # Check date permission
        user_section = session.get('section', '')
        if not check_date_permission(group_data['issue_date'], user_section):
            flash('You can only create loans for today or yesterday. Contact a manager for older entries.', 'error')
            return redirect(url_for('finance.group_loans'))

        group = GroupLoan(
            group_name=group_data['group_name'],
            member_count=group_data['member_count'],
            principal=group_data['principal'],
            interest_rate=group_data['interest_rate'],
            interest_amount=group_data['interest_amount'],
            total_amount=group_data['total_amount'],
            amount_per_period=group_data['amount_per_period'],
            total_periods=group_data['total_periods'],
            period_type=group_data['period_type'],
            periods_paid=0,
            amount_paid=Decimal('0'),
            balance=group_data['total_amount'],
            issue_date=group_data['issue_date'],
            due_date=group_data['due_date'],
            status='active'
        )
        if members_data:
            try:
                group.set_members(json.loads(members_data))
            except (TypeError, ValueError, json.JSONDecodeError):
                flash('Member data is invalid. Please review the group members and try again.', 'error')
                return redirect(url_for('finance.group_loans'))
        db.session.add(group)
        db.session.flush()

        # Handle collateral document upload
        if 'collateral_file' in request.files:
            file = request.files['collateral_file']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'collateral')
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, f'group_{group.id}_{filename}')
                if validate_and_save(file, file_path):
                    doc = LoanDocument(
                        group_loan_id=group.id,
                        filename=filename,
                        file_path=file_path,
                        file_type=filename.rsplit('.', 1)[1].lower() if '.' in filename else 'unknown'
                    )
                    db.session.add(doc)

        db.session.commit()

        log_action(session['username'], 'finance', 'create', 'group_loan', group.id,
                   {'group_name': group.group_name, 'principal': float(group.principal),
                    'total_amount': float(group.total_amount), 'member_count': group.member_count,
                    'has_members_data': bool(members_data)})
        flash('Group loan created successfully', 'success')
        return redirect(url_for('finance.view_group_loan', id=group.id))
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('finance.group_loans'))


@finance_bp.route('/group-loans/<int:id>/agreement-pdf')
@login_required('finance')
def download_group_agreement_pdf(id):
    """Download group loan agreement as PDF"""
    group = GroupLoan.query.get_or_404(id)
    buffer = generate_group_agreement_pdf(group)

    return Response(
        buffer.getvalue(),
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename=group_loan_agreement_{group.id}.pdf'}
    )


# ============ CLEARANCE CERTIFICATES ============

@finance_bp.route('/loans/<int:id>/clearance-pdf')
@login_required('finance')
def download_loan_clearance_pdf(id):
    """Download clearance certificate for a fully paid individual loan."""
    loan = Loan.query.get_or_404(id)
    # Always refresh so monthly-accrual interest is current before the check
    if refresh_loan_state(loan):
        db.session.commit()

    # Guard on both status flag AND calculated balance — a monthly-accrual loan
    # can transition back to a non-zero balance if interest keeps accruing after
    # the status was last saved as 'paid'.
    if loan.status != 'paid' or Decimal(str(loan.balance or 0)) > 0:
        flash('Clearance certificate is only available for loans with a zero balance.', 'error')
        return redirect(url_for('finance.view_loan', id=id))

    payments = loan.payments.filter_by(is_deleted=False).order_by(LoanPayment.payment_date.desc()).all()
    buffer = generate_clearance_pdf(loan, payments)

    log_action(session.get('username'), 'finance', 'view', 'clearance_certificate', loan.id,
               {'client': loan.client.name if loan.client else 'Unknown'})

    return Response(
        buffer.getvalue(),
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename=clearance_LCC-{loan.id:05d}.pdf'}
    )


@finance_bp.route('/group-loans/<int:id>/clearance-pdf')
@login_required('finance')
def download_group_clearance_pdf(id):
    """Download clearance certificate for a fully paid group loan."""
    group = GroupLoan.query.get_or_404(id)

    if group.status != 'paid' or Decimal(str(group.balance or 0)) > 0:
        flash('Clearance certificate is only available for group loans with a zero balance.', 'error')
        return redirect(url_for('finance.view_group_loan', id=id))

    payments = group.payments.filter_by(is_deleted=False).order_by(GroupLoanPayment.payment_date.desc()).all()
    buffer = generate_group_clearance_pdf(group, payments)

    log_action(session.get('username'), 'finance', 'view', 'group_clearance_certificate', group.id,
               {'group_name': group.group_name})

    return Response(
        buffer.getvalue(),
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename=clearance_GLCC-{group.id:05d}.pdf'}
    )


# ============ COLLATERAL DOCUMENTS ============

@finance_bp.route('/loans/<int:id>/upload-collateral', methods=['POST'])
@login_required('finance')
def upload_loan_collateral(id):
    """Upload collateral document for individual loan"""
    loan = Loan.query.get_or_404(id)

    if 'collateral_file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('finance.view_loan', id=id))

    file = request.files['collateral_file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('finance.view_loan', id=id))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'collateral')
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, f'loan_{loan.id}_{filename}')
        if validate_and_save(file, file_path):
            doc = LoanDocument(
                loan_id=loan.id,
                filename=filename,
                file_path=file_path,
                file_type=filename.rsplit('.', 1)[1].lower() if '.' in filename else 'unknown'
            )
            db.session.add(doc)
            db.session.commit()

            log_action(session['username'], 'finance', 'upload', 'collateral', doc.id,
                       {'loan_id': loan.id, 'filename': filename})
            flash('Collateral document uploaded successfully', 'success')
        else:
            flash('Invalid file content. The file appears corrupted or is not the claimed type.', 'error')
    else:
        flash('Invalid file type. Allowed: PDF, PNG, JPG, JPEG, GIF, WebP', 'error')

    return redirect(url_for('finance.view_loan', id=id))


@finance_bp.route('/group-loans/<int:id>/upload-collateral', methods=['POST'])
@login_required('finance')
def upload_group_loan_collateral(id):
    """Upload collateral document for group loan"""
    group = GroupLoan.query.get_or_404(id)

    if 'collateral_file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('finance.view_group_loan', id=id))

    file = request.files['collateral_file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('finance.view_group_loan', id=id))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'collateral')
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, f'group_{group.id}_{filename}')
        if validate_and_save(file, file_path):
            doc = LoanDocument(
                group_loan_id=group.id,
                filename=filename,
                file_path=file_path,
                file_type=filename.rsplit('.', 1)[1].lower() if '.' in filename else 'unknown'
            )
            db.session.add(doc)
            db.session.commit()

            log_action(session['username'], 'finance', 'upload', 'collateral', doc.id,
                       {'group_loan_id': group.id, 'filename': filename})
            flash('Collateral document uploaded successfully', 'success')
        else:
            flash('Invalid file content. The file appears corrupted or is not the claimed type.', 'error')
    else:
        flash('Invalid file type. Allowed: PDF, PNG, JPG, JPEG, GIF, WebP', 'error')

    return redirect(url_for('finance.view_group_loan', id=id))


@finance_bp.route('/documents/<int:id>/download')
@login_required('finance')
def download_document(id):
    """Download a collateral document"""
    doc = LoanDocument.query.get_or_404(id)
    if os.path.exists(doc.file_path):
        return send_file(doc.file_path, as_attachment=True, download_name=doc.filename)
    flash('File not found', 'error')
    return redirect(url_for('finance.index'))


@finance_bp.route('/documents/<int:id>/delete', methods=['POST'])
@login_required('finance')
def delete_document(id):
    """Delete a collateral document"""
    doc = LoanDocument.query.get_or_404(id)
    loan_id = doc.loan_id
    group_loan_id = doc.group_loan_id

    # Try to delete the file
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    doc.is_deleted = True
    db.session.commit()

    log_action(session['username'], 'finance', 'delete', 'collateral', doc.id,
               {'filename': doc.filename})
    flash('Document deleted', 'success')

    if loan_id:
        return redirect(url_for('finance.view_loan', id=loan_id))
    elif group_loan_id:
        return redirect(url_for('finance.view_group_loan', id=group_loan_id))
    return redirect(url_for('finance.index'))
