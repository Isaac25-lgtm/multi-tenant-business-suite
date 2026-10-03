"""loan settlement dates, payment reversals, sale cost snapshots

Revision ID: e1f2a3b4c5d6
Revises: d8e9f0a1b2c3
Create Date: 2026-10-03 15:00:00.000000

Backfill policy (no live balance is changed by this migration):
- settled_on is set only for loans that are *currently* paid or renewed, using
  the date their balance actually reached zero. This freezes them so monthly
  interest can no longer reopen them. Loans that were wrongly reopened by the
  old accrual bug are left untouched; review them with
  `flask finance-audit` and fix them with `flask finance-backfill-settlement`.
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


def upgrade():
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


def downgrade():
    op.drop_column('hardware_sale_items', 'unit_cost_at_sale')
    op.drop_column('boutique_sale_items', 'unit_cost_at_sale')

    for table in ('group_loan_payments', 'loan_payments'):
        op.drop_column(table, 'reversal_reason')
        op.drop_column(table, 'reversed_by')
        op.drop_column(table, 'reversed_at')

    op.drop_column('loans', 'settled_on')
