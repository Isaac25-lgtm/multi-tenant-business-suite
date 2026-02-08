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
    inspector = inspect(db.engine)

    # Check and add columns to boutique_stock
    boutique_stock_columns = [col['name'] for col in inspector.get_columns('boutique_stock')]
    with db.engine.connect() as conn:
        if 'image_url' not in boutique_stock_columns:
            conn.execute(text('ALTER TABLE boutique_stock ADD COLUMN image_url VARCHAR(500)'))
            conn.commit()
            print("Added image_url column to boutique_stock table")

        if 'branch' not in boutique_stock_columns:
            conn.execute(text('ALTER TABLE boutique_stock ADD COLUMN branch VARCHAR(10)'))
            conn.commit()
            print("Added branch column to boutique_stock table")

    # Check and add columns to boutique_sales
    boutique_sales_columns = [col['name'] for col in inspector.get_columns('boutique_sales')]
    with db.engine.connect() as conn:
        if 'branch' not in boutique_sales_columns:
            conn.execute(text('ALTER TABLE boutique_sales ADD COLUMN branch VARCHAR(10)'))
            conn.commit()
            print("Added branch column to boutique_sales table")

    # Check and add columns to users
    users_columns = [col['name'] for col in inspector.get_columns('users')]
    with db.engine.connect() as conn:
        if 'last_login' not in users_columns:
            conn.execute(text('ALTER TABLE users ADD COLUMN last_login TIMESTAMP'))
            conn.commit()
            print("Added last_login column to users table")


if __name__ == '__main__':
    # Use PORT environment variable if available (for Render), otherwise default to 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
