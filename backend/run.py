from app import create_app, db
from app.models import *

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        # Create all tables
        db.create_all()
        print("Database tables created successfully!")
    
    app.run(debug=True, host='127.0.0.1', port=5000)
