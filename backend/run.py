from app import create_app
from app.extensions import db
import os

app = create_app()


if __name__ == '__main__':
    with app.app_context():
        # Create all tables
        db.create_all()
        print("Database tables created successfully!")

    # Use PORT environment variable if available (for Render), otherwise default to 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
