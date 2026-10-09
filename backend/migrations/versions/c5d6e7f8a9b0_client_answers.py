"""client answers: payment method, registration details, reminders, drop chat history

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-10-09 12:00:00.000000

- payment_method / payment_reference on every payment table and on sales
- registration_number / postal_address on website settings (printed on documents)
- reminder_logs for SMS / WhatsApp loan reminders
- drops chat_messages: the AI chat assistant was removed and the client asked
  for its history to be deleted (irreversible; downgrade recreates it empty)

No loan balance is changed by this migration. Converting open flat-rate loans
to monthly interest is a separate, reviewed step: `flask finance-convert-flat-loans`.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c5d6e7f8a9b0'
down_revision = 'b4c5d6e7f8a9'
branch_labels = None
depends_on = None

PAYMENT_TABLES = (
    'loan_payments', 'group_loan_payments', 'boutique_credit_payments', 'hardware_credit_payments',
    'boutique_hire_payments', 'boutique_sales', 'hardware_sales',
)


def upgrade():
    for table in PAYMENT_TABLES:
        op.add_column(table, sa.Column('payment_method', sa.String(length=20), nullable=True))
        op.add_column(table, sa.Column('payment_reference', sa.String(length=100), nullable=True))

    op.add_column('website_settings', sa.Column('registration_number', sa.String(length=60), nullable=True))
    op.add_column('website_settings', sa.Column('postal_address', sa.String(length=160), nullable=True))
    op.get_bind().execute(sa.text("""
        UPDATE website_settings
        SET registration_number = COALESCE(NULLIF(registration_number, ''), '80041359477794'),
            postal_address = COALESCE(NULLIF(postal_address, ''), 'P.O. Box, Barawa, Kapchorwa')
    """))

    op.alter_column('expenses', 'business_unit', server_default=None)

    op.create_table(
        'reminder_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('loan_id', sa.Integer(), sa.ForeignKey('loans.id'), nullable=True),
        sa.Column('group_loan_id', sa.Integer(), sa.ForeignKey('group_loans.id'), nullable=True),
        sa.Column('reminder_date', sa.Date(), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('channel', sa.String(length=20), nullable=False),
        sa.Column('phone', sa.String(length=30), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('detail', sa.String(length=255), nullable=True),
        sa.Column('sent_by', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_reminder_logs_loan_date', 'reminder_logs', ['loan_id', 'reminder_date'])

    op.execute('DROP TABLE IF EXISTS chat_messages')


def downgrade():
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('intent', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.drop_index('ix_reminder_logs_loan_date', table_name='reminder_logs')
    op.drop_table('reminder_logs')
    op.alter_column('expenses', 'business_unit', server_default='shared')
    op.drop_column('website_settings', 'postal_address')
    op.drop_column('website_settings', 'registration_number')
    for table in reversed(PAYMENT_TABLES):
        op.drop_column(table, 'payment_reference')
        op.drop_column(table, 'payment_method')
