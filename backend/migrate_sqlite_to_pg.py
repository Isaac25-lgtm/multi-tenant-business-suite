#!/usr/bin/env python
"""One-time migration of local SQLite data into PostgreSQL.

Usage:
    1. Ensure your .env points DATABASE_URL at the target PostgreSQL database.
    2. Run migrations first:  flask db upgrade
    3. Run this script:       python migrate_sqlite_to_pg.py [path/to/denove.db]

The default SQLite path is  backend/instance/denove.db  (Flask's default
instance-relative location), but you can pass an explicit path.

This script is idempotent for tables that are empty in PostgreSQL — it skips
any table that already contains rows.  It will NOT overwrite production data.
"""

import os
import sys
import sqlite3
from pathlib import Path

# Ensure the backend directory is on sys.path so `app` can be imported.
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

os.chdir(BACKEND_DIR)

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.extensions import db
from sqlalchemy import text, inspect as sa_inspect

PREFERRED_TABLE_ORDER = [
    'users',
    'audit_logs',
    'customers',
    'loan_clients',
    'loans',
    'loan_payments',
    'group_loans',
    'group_loan_payments',
    'loan_documents',
    'boutique_categories',
    'boutique_stock',
    'boutique_sales',
    'boutique_sale_items',
    'boutique_credit_payments',
    'boutique_hires',
    'boutique_hire_payments',
    'hardware_categories',
    'hardware_stock',
    'hardware_sales',
    'hardware_sale_items',
    'hardware_credit_payments',
    'published_products',
    'product_images',
    'website_images',
    'website_loan_inquiries',
    'website_order_requests',
    'website_settings',
    'rate_limit_states',
]


def order_tables(table_names):
    preferred = [table for table in PREFERRED_TABLE_ORDER if table in table_names]
    remainder = sorted(table for table in table_names if table not in PREFERRED_TABLE_ORDER)
    return preferred + remainder


def find_sqlite_db(explicit_path=None):
    """Locate the old SQLite database file."""
    candidates = [
        explicit_path,
        BACKEND_DIR / 'instance' / 'denove.db',
        BACKEND_DIR / 'denove.db',
        BACKEND_DIR / 'app' / 'denove.db',
    ]
    for p in candidates:
        if p and Path(p).is_file():
            return str(Path(p).resolve())
    return None


def migrate(sqlite_path):
    app = create_app()
    with app.app_context():
        # Verify target is PostgreSQL
        url = str(db.engine.url)
        if 'sqlite' in url.lower():
            print('ERROR: Target database is SQLite. Set DATABASE_URL to PostgreSQL.')
            sys.exit(1)

        pg_inspector = sa_inspect(db.engine)
        pg_tables = set(pg_inspector.get_table_names())

        conn_lite = sqlite3.connect(sqlite_path)
        conn_lite.row_factory = sqlite3.Row
        cursor = conn_lite.cursor()

        # Get SQLite tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'")
        sqlite_tables = order_tables([row[0] for row in cursor.fetchall()])

        migrated = 0
        skipped_nonempty = 0
        skipped_missing = 0

        for table in sqlite_tables:
            if table not in pg_tables:
                print(f'  SKIP  {table:40s} (not in PostgreSQL schema)')
                skipped_missing += 1
                continue

            # Skip if PG table already has data
            count = db.session.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
            if count > 0:
                print(f'  SKIP  {table:40s} ({count} rows already in PostgreSQL)')
                skipped_nonempty += 1
                continue

            cursor.execute(f'SELECT * FROM "{table}"')
            rows = cursor.fetchall()
            if not rows:
                print(f'  SKIP  {table:40s} (empty in SQLite)')
                continue

            columns = [desc[0] for desc in cursor.description]
            col_list = ', '.join(f'"{c}"' for c in columns)
            param_list = ', '.join(f':{c}' for c in columns)

            # Identify boolean columns in PostgreSQL so we can cast SQLite 0/1 → bool
            pg_cols = {c['name']: c for c in pg_inspector.get_columns(table)}
            bool_cols = {
                name for name, info in pg_cols.items()
                if str(info['type']).upper() == 'BOOLEAN'
            }

            batch = []
            for row in rows:
                record = dict(zip(columns, row))
                for col in bool_cols:
                    if col in record and record[col] is not None:
                        record[col] = bool(record[col])
                batch.append(record)

            db.session.execute(text(f'INSERT INTO "{table}" ({col_list}) VALUES ({param_list})'), batch)
            db.session.commit()

            # Reset the auto-increment sequence for this table
            try:
                db.session.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                    f"(SELECT COALESCE(MAX(id), 0) FROM \"{table}\"), true)"
                ))
                db.session.commit()
            except Exception:
                db.session.rollback()  # table may not have an 'id' serial

            print(f'  OK    {table:40s} ({len(rows)} rows copied)')
            migrated += 1

        conn_lite.close()

        print('')
        print(f'Done. {migrated} tables migrated, '
              f'{skipped_nonempty} skipped (already have data), '
              f'{skipped_missing} skipped (not in PG schema).')


def main():
    explicit = sys.argv[1] if len(sys.argv) > 1 else None
    sqlite_path = find_sqlite_db(explicit)
    if not sqlite_path:
        print('No SQLite database found. Searched:')
        print('  backend/instance/denove.db')
        print('  backend/denove.db')
        print('  backend/app/denove.db')
        print('')
        print('Pass an explicit path:  python migrate_sqlite_to_pg.py /path/to/denove.db')
        sys.exit(1)

    print(f'SQLite source: {sqlite_path}')
    print(f'PostgreSQL target: {os.getenv("DATABASE_URL", "(from PG* vars)")}')
    print('')
    migrate(sqlite_path)


if __name__ == '__main__':
    main()
