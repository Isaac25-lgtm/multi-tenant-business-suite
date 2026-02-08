from app import create_app
from app.extensions import db
import os
from sqlalchemy import inspect, text

app = create_app()

# Create tables on startup (works with both direct run and Gunicorn)
with app.app_context():
    db.create_all()
    print("Database tables created successfully!")

    # Add new columns to existing tables if they don't exist yet
    # (db.create_all() only creates new tables, not new columns)
    def add_column_if_missing(table, column, col_type):
        """Safely add a column to a table if it doesn't exist."""
        try:
            insp = inspect(db.engine)
            existing = [c['name'] for c in insp.get_columns(table)]
            if column not in existing:
                with db.engine.connect() as conn:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {col_type}'))
                    conn.commit()
                print(f"  Added {column} to {table}")
                return True
        except Exception as e:
            print(f"  Warning: Could not add {column} to {table}: {e}")
        return False

    print("Running schema migrations...")

    # Users table - all potentially missing columns
    add_column_if_missing('users', 'last_login', 'TIMESTAMP')
    add_column_if_missing('users', 'full_name', 'VARCHAR(100)')
    add_column_if_missing('users', 'email', 'VARCHAR(100)')
    add_column_if_missing('users', 'phone', 'VARCHAR(20)')
    add_column_if_missing('users', 'profile_picture', 'VARCHAR(255)')
    add_column_if_missing('users', 'can_access_boutique', 'BOOLEAN DEFAULT FALSE')
    add_column_if_missing('users', 'can_access_hardware', 'BOOLEAN DEFAULT FALSE')
    add_column_if_missing('users', 'can_access_finance', 'BOOLEAN DEFAULT FALSE')
    add_column_if_missing('users', 'can_access_customers', 'BOOLEAN DEFAULT FALSE')
    add_column_if_missing('users', 'boutique_branch', 'VARCHAR(10)')
    add_column_if_missing('users', 'created_by', 'INTEGER')

    # Boutique stock table
    add_column_if_missing('boutique_stock', 'branch', 'VARCHAR(10)')
    add_column_if_missing('boutique_stock', 'image_url', 'VARCHAR(500)')

    # Boutique sales table
    add_column_if_missing('boutique_sales', 'branch', 'VARCHAR(10)')

    print("Schema migrations complete!")


if __name__ == '__main__':
    # Use PORT environment variable if available (for Render), otherwise default to 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
