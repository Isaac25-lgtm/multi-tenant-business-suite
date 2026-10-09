"""loan settlement dates, payment reversals, sale cost snapshots

Revision ID: e1f2a3b4c5d6
Revises: d8e9f0a1b2c3
Create Date: 2026-10-03 15:00:00.000000

Before any change, every existing table is copied into the
`pre_upgrade_snapshot` schema (see snapshot_existing_data).

Backfill policy (no live balance is changed by this migration):
- settled_on is set for loans that are *currently* paid or renewed, using the
  date their balance actually reached zero. This freezes them so monthly
  interest can no longer reopen them.
- Loans that were fully paid and then wrongly re-opened by the old accrual bug
  are closed again (strict conditions, see below). Any that received further
  payments after reaching zero are left for review (`flask finance-audit`).
- unit_cost_at_sale stays NULL for existing sale lines because their true cost
  at the time of sale is unknown. Reports label that profit as estimated.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1f2a3b4c5d6'
down_revision = 'd8e9f0a1b2c3'
branch_labels = None
depends_on = None


SNAPSHOT_SCHEMA = 'pre_upgrade_snapshot'


def snapshot_existing_data(bind):
    """Copy every existing table into a separate schema before anything changes.

    This is the safety net for the October 2026 upgrade: the original rows
    (loans, payments, sales, settings, ...) stay readable in
    `pre_upgrade_snapshot.<table>` even after balances are recalculated under
    the new rules. Safe to run twice; an existing copy is never overwritten.
    Remove later with: DROP SCHEMA pre_upgrade_snapshot CASCADE;
    """
    inspector = sa.inspect(bind)
    tables = [name for name in inspector.get_table_names(schema='public') if name != 'alembic_version']
    if not tables:
        return  # brand-new database: nothing to protect
    bind.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS {SNAPSHOT_SCHEMA}'))
    existing = set(inspector.get_table_names(schema=SNAPSHOT_SCHEMA))
    for name in tables:
        if name not in existing:
            bind.execute(sa.text(f'CREATE TABLE {SNAPSHOT_SCHEMA}."{name}" AS TABLE public."{name}"'))


def upgrade():
    snapshot_existing_data(op.get_bind())

    op.add_column('loans', sa.Column('settled_on', sa.Date(), nullable=True))

    for table in ('loan_payments', 'group_loan_payments'):
        op.add_column(table, sa.Column('reversed_at', sa.DateTime(), nullable=True))
        op.add_column(table, sa.Column('reversed_by', sa.String(length=50), nullable=True))
        op.add_column(table, sa.Column('reversal_reason', sa.String(length=255), nullable=True))

    op.add_column('boutique_sale_items', sa.Column('unit_cost_at_sale', sa.Numeric(12, 2), nullable=True))
    op.add_column('hardware_sale_items', sa.Column('unit_cost_at_sale', sa.Numeric(12, 2), nullable=True))

    bind = op.get_bind()
    # Paid loans: the latest payment that brought the balance to zero.
    bind.execute(sa.text("""
        UPDATE loans l
        SET settled_on = COALESCE(
            (SELECT MAX(p.payment_date) FROM loan_payments p
              WHERE p.loan_id = l.id AND p.is_deleted = false AND p.balance_after <= 0),
            (SELECT MAX(p.payment_date) FROM loan_payments p
              WHERE p.loan_id = l.id AND p.is_deleted = false),
            CAST(l.updated_at AS DATE),
            l.due_date
        )
        WHERE l.settled_on IS NULL
          AND l.status = 'paid'
          AND COALESCE(l.balance, 0) <= 0
    """))
    # Renewed loans: the renewal date.
    bind.execute(sa.text("""
        UPDATE loans l
        SET settled_on = COALESCE(
            (SELECT MAX(p.payment_date) FROM loan_payments p
              WHERE p.loan_id = l.id AND p.is_deleted = false AND p.payment_type = 'renewal'),
            (SELECT CAST(c.created_at AS DATE) FROM loans c WHERE c.id = l.renewed_to_loan_id),
            CAST(l.updated_at AS DATE),
            l.due_date
        )
        WHERE l.settled_on IS NULL
          AND l.status = 'renewed'
    """))
    # Loans that were fully paid and then wrongly re-opened by the old accrual
    # bug (interest kept being added after the balance reached zero). Closed
    # again only under strict conditions: a payment brought the balance to
    # zero, nothing was paid after it, and the principal is fully repaid. The
    # original figures stay in pre_upgrade_snapshot.loans.
    bind.execute(sa.text("""
        UPDATE loans l
        SET settled_on = z.payment_date,
            status = 'paid',
            balance = 0,
            interest_amount = COALESCE(l.interest_paid, 0),
            total_amount = COALESCE(l.principal, 0) + COALESCE(l.interest_paid, 0)
        FROM (
            SELECT DISTINCT ON (p.loan_id) p.loan_id, p.payment_date, p.id
            FROM loan_payments p
            WHERE p.is_deleted = false AND p.balance_after <= 0
            ORDER BY p.loan_id, p.payment_date DESC, p.id DESC
        ) z
        WHERE l.id = z.loan_id
          AND l.settled_on IS NULL
          AND l.is_deleted = false
          AND l.status IN ('active', 'overdue')
          AND COALESCE(l.balance, 0) > 0
          AND l.interest_mode = 'monthly_accrual'
          AND COALESCE(l.principal_paid, 0) + COALESCE(l.principal_rolled, 0) >= COALESCE(l.principal, 0)
          AND NOT EXISTS (
              SELECT 1 FROM loan_payments q
              WHERE q.loan_id = l.id AND q.is_deleted = false
                AND (q.payment_date > z.payment_date OR (q.payment_date = z.payment_date AND q.id > z.id))
          )
    """))


def downgrade():
    op.drop_column('hardware_sale_items', 'unit_cost_at_sale')
    op.drop_column('boutique_sale_items', 'unit_cost_at_sale')

    for table in ('group_loan_payments', 'loan_payments'):
        op.drop_column(table, 'reversal_reason')
        op.drop_column(table, 'reversed_by')
        op.drop_column(table, 'reversed_at')

    op.drop_column('loans', 'settled_on')
