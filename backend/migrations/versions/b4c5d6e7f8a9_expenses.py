"""operating expenses ledger

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-10-03 17:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b4c5d6e7f8a9'
down_revision = 'a3b4c5d6e7f8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'expenses',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('expense_date', sa.Date(), nullable=False),
        sa.Column('category', sa.String(length=40), nullable=False),
        sa.Column('business_unit', sa.String(length=20), nullable=False, server_default='shared'),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('payment_method', sa.String(length=20), nullable=True),
        sa.Column('reference', sa.String(length=100), nullable=True),
        sa.Column('created_by', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('deleted_by', sa.String(length=50), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('deletion_reason', sa.String(length=255), nullable=True),
        sa.CheckConstraint('amount > 0', name='ck_expenses_positive_amount'),
    )
    op.create_index('ix_expenses_expense_date', 'expenses', ['expense_date'])


def downgrade():
    op.drop_index('ix_expenses_expense_date', table_name='expenses')
    op.drop_table('expenses')
