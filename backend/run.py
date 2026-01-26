from app import create_app, db
from app.models import User
from flask import jsonify
import os

app = create_app()

@app.route('/seed_db')
def seed_db():
    """Seed database with initial users (for production deployment)"""
    try:
        with app.app_context():
            db.create_all()
            
            created = []
            
            # Manager
            if not User.query.filter_by(username='manager').first():
                manager = User(
                    username='manager',
                    name='General Manager',
                    role='manager',
                    assigned_business='all'
                )
                manager.set_password('admin123')
                db.session.add(manager)
                created.append('manager')
                
            # Sarah (Boutique)
            if not User.query.filter_by(username='sarah').first():
                sarah = User(
                    username='sarah',
                    name='Sarah Jenkins',
                    role='employee',
                    assigned_business='boutique'
                )
                sarah.set_password('pass123')
                db.session.add(sarah)
                created.append('sarah')

            # David (Hardware)
            if not User.query.filter_by(username='david').first():
                david = User(
                    username='david',
                    name='David Miller',
                    role='employee',
                    assigned_business='hardware'
                )
                david.set_password('pass123')
                db.session.add(david)
                created.append('david')
                
            # Grace (Finances)
            if not User.query.filter_by(username='grace').first():
                grace = User(
                    username='grace',
                    name='Grace A.',
                    role='employee',
                    assigned_business='finances'
                )
                grace.set_password('pass123')
                db.session.add(grace)
                created.append('grace')

            db.session.commit()
            return jsonify({"status": "success", "message": "Database seeded!", "created_users": created}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Development mode
    with app.app_context():
        # Create all tables
        db.create_all()
        print("Database tables created successfully!")
    
    # Use PORT environment variable if available (for Render), otherwise default to 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
