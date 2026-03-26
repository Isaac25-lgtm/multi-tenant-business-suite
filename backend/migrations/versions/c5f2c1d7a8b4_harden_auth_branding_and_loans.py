"""harden auth, branding, and loan settings

Revision ID: c5f2c1d7a8b4
Revises: 4694bf24ca95
Create Date: 2026-03-26 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

import base64
import hashlib
import json
import os

from cryptography.fernet import Fernet, InvalidToken


# revision identifiers, used by Alembic.
revision = 'c5f2c1d7a8b4'
down_revision = '4694bf24ca95'
branch_labels = None
depends_on = None


WEAK_SECRETS = {
    None,
    '',
    'dev-secret-key-change-in-production',
    'dev-secret-key-change-in-production-12345',
}


def _get_secret_key():
    env = os.getenv('FLASK_ENV', 'development')
    key = os.getenv('SECRET_KEY')

    if env == 'production':
        if key in WEAK_SECRETS or (key and len(key) < 32):
            raise RuntimeError(
                'SECRET_KEY must be set to a strong value (32+ chars) in production '
                'before running this migration.'
            )
        return key

    return key or 'local-dev-only-not-for-production'


def _cipher():
    digest = hashlib.sha256(_get_secret_key().encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encrypt_value(value):
    normalized = str(value or '').strip()
    if not normalized:
        return None
    return _cipher().encrypt(normalized.encode('utf-8')).decode('utf-8')


def _decrypt_value(value):
    token = str(value or '').strip()
    if not token:
        return None
    try:
        return _cipher().decrypt(token.encode('utf-8')).decode('utf-8')
    except InvalidToken:
        return token


def _backfill_nin_columns(bind, table_name):
    table = sa.table(
        table_name,
        sa.column('id', sa.Integer),
        sa.column('nin', sa.String),
        sa.column('nin_encrypted', sa.Text),
    )

    rows = bind.execute(sa.select(table.c.id, table.c.nin, table.c.nin_encrypted)).fetchall()
    for row in rows:
        if row.nin and not row.nin_encrypted:
            bind.execute(
                table.update()
                .where(table.c.id == row.id)
                .values(nin_encrypted=_encrypt_value(row.nin), nin=None)
            )


def _restore_plaintext_nin(bind, table_name):
    table = sa.table(
        table_name,
        sa.column('id', sa.Integer),
        sa.column('nin', sa.String),
        sa.column('nin_encrypted', sa.Text),
    )

    rows = bind.execute(sa.select(table.c.id, table.c.nin_encrypted)).fetchall()
    for row in rows:
        if row.nin_encrypted:
            bind.execute(
                table.update()
                .where(table.c.id == row.id)
                .values(nin=_decrypt_value(row.nin_encrypted))
            )


def _backfill_group_member_nins(bind):
    group_loans = sa.table(
        'group_loans',
        sa.column('id', sa.Integer),
        sa.column('members_json', sa.Text),
    )

    rows = bind.execute(sa.select(group_loans.c.id, group_loans.c.members_json)).fetchall()
    for row in rows:
        if not row.members_json:
            continue
        try:
            members = json.loads(row.members_json)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(members, list):
            continue

        changed = False
        serialized = []
        for member in members:
            if not isinstance(member, dict):
                serialized.append(member)
                continue

            member_copy = dict(member)
            encrypted_nin = member_copy.get('nin_encrypted')
            raw_nin = str(member_copy.pop('nin', '') or '').strip()
            if raw_nin and not encrypted_nin:
                member_copy['nin_encrypted'] = _encrypt_value(raw_nin)
                changed = True
            elif 'nin' in member:
                changed = True
            serialized.append(member_copy)

        if changed:
            bind.execute(
                group_loans.update()
                .where(group_loans.c.id == row.id)
                .values(members_json=json.dumps(serialized))
            )


def _restore_group_member_nins(bind):
    group_loans = sa.table(
        'group_loans',
        sa.column('id', sa.Integer),
        sa.column('members_json', sa.Text),
    )

    rows = bind.execute(sa.select(group_loans.c.id, group_loans.c.members_json)).fetchall()
    for row in rows:
        if not row.members_json:
            continue
        try:
            members = json.loads(row.members_json)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(members, list):
            continue

        changed = False
        serialized = []
        for member in members:
            if not isinstance(member, dict):
                serialized.append(member)
                continue

            member_copy = dict(member)
            encrypted_nin = member_copy.pop('nin_encrypted', None)
            if encrypted_nin:
                member_copy['nin'] = _decrypt_value(encrypted_nin)
                changed = True
            serialized.append(member_copy)

        if changed:
            bind.execute(
                group_loans.update()
                .where(group_loans.c.id == row.id)
                .values(members_json=json.dumps(serialized))
            )


def upgrade():
    bind = op.get_bind()

    op.create_table(
        'rate_limit_states',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scope', sa.String(length=50), nullable=False),
        sa.Column('identifier', sa.String(length=255), nullable=False),
        sa.Column('request_count', sa.Integer(), nullable=False),
        sa.Column('window_started_at', sa.DateTime(), nullable=False),
        sa.Column('blocked_until', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scope', 'identifier', name='uq_rate_limit_scope_identifier'),
    )

    op.create_table(
        'website_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=120), nullable=False),
        sa.Column('company_suffix', sa.String(length=40), nullable=True),
        sa.Column('tagline', sa.String(length=255), nullable=True),
        sa.Column('announcement_text', sa.String(length=255), nullable=True),
        sa.Column('hero_title', sa.String(length=255), nullable=True),
        sa.Column('hero_description', sa.Text(), nullable=True),
        sa.Column('contact_phone', sa.String(length=50), nullable=True),
        sa.Column('whatsapp_number', sa.String(length=50), nullable=True),
        sa.Column('contact_email', sa.String(length=120), nullable=True),
        sa.Column('headquarters', sa.String(length=120), nullable=True),
        sa.Column('service_area', sa.String(length=120), nullable=True),
        sa.Column('loan_min_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('loan_max_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('loan_interest_rate', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('loan_interest_rate_label', sa.String(length=80), nullable=True),
        sa.Column('loan_repayment_note', sa.String(length=255), nullable=True),
        sa.Column('loan_approval_hours', sa.Integer(), nullable=True),
        sa.Column('footer_description', sa.Text(), nullable=True),
        sa.Column('logo_path', sa.String(length=255), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    with op.batch_alter_table('customers') as batch_op:
        batch_op.add_column(sa.Column('nin_encrypted', sa.Text(), nullable=True))

    with op.batch_alter_table('loan_clients') as batch_op:
        batch_op.add_column(sa.Column('nin_encrypted', sa.Text(), nullable=True))

    with op.batch_alter_table('loans') as batch_op:
        batch_op.add_column(sa.Column('interest_mode', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('monthly_interest_amount', sa.Numeric(precision=12, scale=2), nullable=True))

    _backfill_nin_columns(bind, 'customers')
    _backfill_nin_columns(bind, 'loan_clients')
    _backfill_group_member_nins(bind)

    loans = sa.table(
        'loans',
        sa.column('id', sa.Integer),
        sa.column('interest_mode', sa.String),
    )
    bind.execute(
        loans.update()
        .where(loans.c.interest_mode.is_(None))
        .values(interest_mode='flat_rate')
    )


def downgrade():
    bind = op.get_bind()

    _restore_plaintext_nin(bind, 'customers')
    _restore_plaintext_nin(bind, 'loan_clients')
    _restore_group_member_nins(bind)

    with op.batch_alter_table('loans') as batch_op:
        batch_op.drop_column('monthly_interest_amount')
        batch_op.drop_column('interest_mode')

    with op.batch_alter_table('loan_clients') as batch_op:
        batch_op.drop_column('nin_encrypted')

    with op.batch_alter_table('customers') as batch_op:
        batch_op.drop_column('nin_encrypted')

    op.drop_table('website_settings')
    op.drop_table('rate_limit_states')
