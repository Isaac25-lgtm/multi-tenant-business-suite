"""rebrand saved site settings to NoRongir Investments Limited

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-10-03 15:30:00.000000

The client asked for the business name and contact email to change, so those
are set unconditionally. Free-text fields have the old name replaced in place.
A logo the manager uploaded is kept; only the retired built-in logos are
pointed at the new default. Downgrade does not restore the old brand.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2a3b4c5d6e7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None

TEXT_COLUMNS = ('tagline', 'announcement_text', 'hero_title', 'hero_description', 'footer_description')
RETIRED_LOGOS = ('images/denove-logo.svg', 'images/denovo.png', 'images/denove.jpg', 'images/devs.png')


def upgrade():
    bind = op.get_bind()
    bind.execute(sa.text("""
        UPDATE website_settings
        SET company_name = 'NoRongir',
            company_suffix = 'Investments Limited',
            contact_email = 'norongir@gmail.com'
    """))
    for column in TEXT_COLUMNS:
        bind.execute(sa.text(f"""
            UPDATE website_settings
            SET {column} = REPLACE(REPLACE(REPLACE({column},
                'Denove APS', 'NoRongir Investments Limited'),
                'Devs APS', 'NoRongir Investments Limited'),
                'Denove', 'NoRongir')
            WHERE {column} IS NOT NULL
        """))
    bind.execute(
        sa.text("""
            UPDATE website_settings
            SET logo_path = 'images/norongir-logo.png'
            WHERE logo_path IS NULL OR logo_path = '' OR logo_path IN :retired
        """).bindparams(sa.bindparam('retired', expanding=True)),
        {'retired': list(RETIRED_LOGOS)},
    )


def downgrade():
    # Branding data is intentionally not reverted.
    pass
