"""add client reputation and inquiry linking

Revision ID: 9d3a2b1c4e5f
Revises: c5f2c1d7a8b4
Create Date: 2026-03-26 20:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9d3a2b1c4e5f'
down_revision = 'c5f2c1d7a8b4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('loan_clients') as batch_op:
        batch_op.add_column(sa.Column('payer_status', sa.String(length=20), nullable=True))

    with op.batch_alter_table('website_loan_inquiries') as batch_op:
        batch_op.add_column(sa.Column('finance_client_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_website_loan_inquiries_finance_client_id',
            'loan_clients',
            ['finance_client_id'],
            ['id'],
        )

    loan_clients = sa.table(
        'loan_clients',
        sa.column('id', sa.Integer),
        sa.column('payer_status', sa.String),
        sa.column('phone', sa.String),
        sa.column('is_active', sa.Boolean),
    )
    inquiries = sa.table(
        'website_loan_inquiries',
        sa.column('id', sa.Integer),
        sa.column('phone', sa.String),
        sa.column('status', sa.String),
        sa.column('finance_client_id', sa.Integer),
    )

    bind = op.get_bind()
    bind.execute(
        loan_clients.update()
        .where(loan_clients.c.payer_status.is_(None))
        .values(payer_status='neutral')
    )

    approved_inquiries = bind.execute(
        sa.select(inquiries.c.id, inquiries.c.phone)
        .where(inquiries.c.status == 'approved')
        .where(inquiries.c.finance_client_id.is_(None))
    ).fetchall()
    for inquiry in approved_inquiries:
        matched_client = bind.execute(
            sa.select(loan_clients.c.id)
            .where(loan_clients.c.phone == inquiry.phone)
            .limit(1)
        ).fetchone()
        if matched_client:
            bind.execute(
                inquiries.update()
                .where(inquiries.c.id == inquiry.id)
                .values(finance_client_id=matched_client.id)
            )

    with op.batch_alter_table('loan_clients') as batch_op:
        batch_op.alter_column('payer_status', existing_type=sa.String(length=20), nullable=False)


def downgrade():
    with op.batch_alter_table('website_loan_inquiries') as batch_op:
        batch_op.drop_constraint('fk_website_loan_inquiries_finance_client_id', type_='foreignkey')
        batch_op.drop_column('finance_client_id')

    with op.batch_alter_table('loan_clients') as batch_op:
        batch_op.drop_column('payer_status')
