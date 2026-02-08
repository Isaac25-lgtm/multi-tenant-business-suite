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
    columns = [col['name'] for col in inspector.get_columns('boutique_stock')]
    if 'image_url' not in columns:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE boutique_stock ADD COLUMN image_url VARCHAR(500)'))
            conn.commit()
        print("Added image_url column to boutique_stock table")


if __name__ == '__main__':
    # Use PORT environment variable if available (for Render), otherwise default to 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
