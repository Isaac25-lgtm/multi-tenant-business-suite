"""fix loan renewal accounting and branch stock separation

Revision ID: d8e9f0a1b2c3
Revises: b4d7e9f1a2c3
Create Date: 2026-05-23 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd8e9f0a1b2c3'
down_revision = 'b4d7e9f1a2c3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('loans', sa.Column('principal_paid', sa.Numeric(12, 2), server_default='0', nullable=False))
    op.add_column('loans', sa.Column('interest_paid', sa.Numeric(12, 2), server_default='0', nullable=False))
    op.add_column('loans', sa.Column('principal_rolled', sa.Numeric(12, 2), server_default='0', nullable=False))
    op.add_column('loans', sa.Column('renewal_parent_id', sa.Integer(), nullable=True))
    op.add_column('loans', sa.Column('renewed_to_loan_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_loans_renewal_parent_id_loans', 'loans', 'loans', ['renewal_parent_id'], ['id'])
    op.create_foreign_key('fk_loans_renewed_to_loan_id_loans', 'loans', 'loans', ['renewed_to_loan_id'], ['id'])

    op.add_column('loan_payments', sa.Column('principal_amount', sa.Numeric(12, 2), server_default='0', nullable=False))
    op.add_column('loan_payments', sa.Column('interest_amount', sa.Numeric(12, 2), server_default='0', nullable=False))
    op.add_column('loan_payments', sa.Column('payment_type', sa.String(length=30), server_default='regular', nullable=False))

    bind = op.get_bind()
    bind.execute(sa.text("""
        UPDATE loan_payments
        SET principal_amount = amount,
            interest_amount = 0,
            payment_type = 'legacy'
        WHERE principal_amount = 0 AND interest_amount = 0
    """))
    bind.execute(sa.text("""
        UPDATE loans
        SET principal_paid = LEAST(COALESCE(amount_paid, 0), COALESCE(principal, 0)),
            interest_paid = GREATEST(COALESCE(amount_paid, 0) - COALESCE(principal, 0), 0),
            principal_rolled = 0
    """))
    bind.execute(sa.text("""
        UPDATE boutique_stock
        SET branch = 'K'
        WHERE branch IS NULL OR branch = ''
    """))
    bind.execute(sa.text("""
        UPDATE boutique_sales
        SET branch = 'K'
        WHERE branch IS NULL OR branch = ''
    """))
    bind.execute(sa.text("""
        UPDATE boutique_hires
        SET branch = 'K'
        WHERE branch IS NULL OR branch = ''
    """))


def downgrade():
    op.drop_column('loan_payments', 'payment_type')
    op.drop_column('loan_payments', 'interest_amount')
    op.drop_column('loan_payments', 'principal_amount')

    op.drop_constraint('fk_loans_renewed_to_loan_id_loans', 'loans', type_='foreignkey')
    op.drop_constraint('fk_loans_renewal_parent_id_loans', 'loans', type_='foreignkey')
    op.drop_column('loans', 'renewed_to_loan_id')
    op.drop_column('loans', 'renewal_parent_id')
    op.drop_column('loans', 'principal_rolled')
    op.drop_column('loans', 'interest_paid')
    op.drop_column('loans', 'principal_paid')
