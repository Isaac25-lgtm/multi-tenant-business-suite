"""
Production Database Migration Script
Adds missing columns to production PostgreSQL database
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def run_migration():
    """Add missing columns to production database"""
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("ERROR: DATABASE_URL not found in environment")
        return False

    # Fix postgres:// to postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    print("Connecting to production database...")
    engine = create_engine(database_url)

    migrations = [
        {
            'name': 'Add branch column to boutique_stock',
            'sql': '''
                ALTER TABLE boutique_stock
                ADD COLUMN IF NOT EXISTS branch VARCHAR(10);
            '''
        },
        {
            'name': 'Add branch column to boutique_sales',
            'sql': '''
                ALTER TABLE boutique_sales
                ADD COLUMN IF NOT EXISTS branch VARCHAR(10);
            '''
        },
        {
            'name': 'Add last_login column to users',
            'sql': '''
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS last_login TIMESTAMP;
            '''
        },
        {
            'name': 'Add image_url column to boutique_stock',
            'sql': '''
                ALTER TABLE boutique_stock
                ADD COLUMN IF NOT EXISTS image_url VARCHAR(500);
            '''
        }
    ]

    try:
        with engine.connect() as conn:
            for migration in migrations:
                print(f"Running: {migration['name']}...")
                conn.execute(text(migration['sql']))
                conn.commit()
                print(f"✓ {migration['name']} completed")

        print("\n✅ All migrations completed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        return False
    finally:
        engine.dispose()

if __name__ == '__main__':
    print("=" * 60)
    print("Production Database Migration")
    print("=" * 60)
    run_migration()
