"""add AI feature tables (briefing, chat, OCR)

Revision ID: a1b2c3d4e5f6
Revises: 9d3a2b1c4e5f
Create Date: 2026-04-02 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '9d3a2b1c4e5f'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'daily_briefings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('briefing_date', sa.Date(), nullable=False),
        sa.Column('scope', sa.String(length=30), nullable=False),
        sa.Column('branch', sa.String(length=10), nullable=True),
        sa.Column('metrics_json', sa.Text(), nullable=False),
        sa.Column('ai_narrative', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('briefing_date', 'scope', 'branch', name='uq_briefing_date_scope_branch'),
    )

    op.create_table(
        'briefing_dismissals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('briefing_date', sa.Date(), nullable=False),
        sa.Column('dismissed_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('user_id', 'briefing_date', name='uq_user_briefing_date'),
    )

    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('intent', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'ocr_extractions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('uploaded_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=512), nullable=False),
        sa.Column('file_type', sa.String(length=20), nullable=True),
        sa.Column('document_type', sa.String(length=50), nullable=True),
        sa.Column('raw_ocr_text', sa.Text(), nullable=True),
        sa.Column('extracted_fields_json', sa.Text(), nullable=True),
        sa.Column('corrected_fields_json', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=True),
        sa.Column('reviewed_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('linked_entity', sa.String(length=50), nullable=True),
        sa.Column('linked_entity_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table('ocr_extractions')
    op.drop_table('chat_messages')
    op.drop_table('briefing_dismissals')
    op.drop_table('daily_briefings')
