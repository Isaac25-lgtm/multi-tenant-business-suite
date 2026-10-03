"""loan adjustments ledger (discounts, waivers, write-offs, charges)

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-10-03 17:00:00.000000

Adds the loan_adjustments table and running-total columns on loans and
group_loans. All new totals start at zero, so no balance changes.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3b4c5d6e7f8'
down_revision = 'f2a3b4c5d6e7'
branch_labels = None
depends_on = None

TOTAL_COLUMNS = ('interest_waived', 'principal_written_off', 'charges_added')


def upgrade():
    for table in ('loans', 'group_loans'):
        for column in TOTAL_COLUMNS:
            op.add_column(table, sa.Column(column, sa.Numeric(12, 2), server_default='0', nullable=False))

    op.create_table(
        'loan_adjustments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('loan_id', sa.Integer(), sa.ForeignKey('loans.id'), nullable=True),
        sa.Column('group_loan_id', sa.Integer(), sa.ForeignKey('group_loans.id'), nullable=True),
        sa.Column('adjustment_type', sa.String(length=30), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.String(length=500), nullable=False),
        sa.Column('created_by', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('is_reversed', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('reversed_by', sa.String(length=50), nullable=True),
        sa.Column('reversed_at', sa.DateTime(), nullable=True),
        sa.Column('reversal_reason', sa.String(length=255), nullable=True),
        sa.CheckConstraint('(loan_id IS NULL) <> (group_loan_id IS NULL)', name='ck_loan_adjustments_one_target'),
        sa.CheckConstraint('amount > 0', name='ck_loan_adjustments_positive_amount'),
    )
    op.create_index('ix_loan_adjustments_loan_id', 'loan_adjustments', ['loan_id'])
    op.create_index('ix_loan_adjustments_group_loan_id', 'loan_adjustments', ['group_loan_id'])


def downgrade():
    op.drop_index('ix_loan_adjustments_group_loan_id', table_name='loan_adjustments')
    op.drop_index('ix_loan_adjustments_loan_id', table_name='loan_adjustments')
    op.drop_table('loan_adjustments')
    for table in ('group_loans', 'loans'):
        for column in reversed(TOTAL_COLUMNS):
            op.drop_column(table, column)
