"""add OCR quota tracking fields

Revision ID: b4d7e9f1a2c3
Revises: a1b2c3d4e5f6
Create Date: 2026-04-02 18:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b4d7e9f1a2c3'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('ocr_extractions', sa.Column('client_reference', sa.String(length=255), nullable=True))
    op.add_column('ocr_extractions', sa.Column('used_ai', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('ocr_extractions', sa.Column('fallback_reason', sa.String(length=100), nullable=True))


def downgrade():
    op.drop_column('ocr_extractions', 'fallback_reason')
    op.drop_column('ocr_extractions', 'used_ai')
    op.drop_column('ocr_extractions', 'client_reference')
