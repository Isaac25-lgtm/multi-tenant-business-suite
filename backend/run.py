from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash
from flask import jsonify

app = create_app()

@app.route('/seed_db')
def seed_db():
    try:
        with app.app_context():
            db.create_all()
            
            created = []
            
            # Manager
            if not User.query.filter_by(username='manager').first():
                manager = User(username='manager', email='manager@example.com', role='manager', password_hash=generate_password_hash('admin123'), name='General Manager', assigned_business='all')
                db.session.add(manager)
                created.append('manager')
                
            # Sarah (Boutique)
            if not User.query.filter_by(username='sarah').first():
                sarah = User(username='sarah', email='sarah@example.com', role='employee', assigned_business='boutique', password_hash=generate_password_hash('pass123'), name='Sarah Jenkins')
                db.session.add(sarah)
                created.append('sarah')

            # David (Hardware)
            if not User.query.filter_by(username='david').first():
                david = User(username='david', email='david@example.com', role='employee', assigned_business='hardware', password_hash=generate_password_hash('pass123'), name='David Miller')
                db.session.add(david)
                created.append('david')
                
            # Grace (Finances)
            if not User.query.filter_by(username='grace').first():
                grace = User(username='grace', email='grace@example.com', role='employee', assigned_business='finances', password_hash=generate_password_hash('pass123'), name='Grace A.')
                db.session.add(grace)
                created.append('grace')

            db.session.commit()
            return jsonify({"status": "success", "message": "Database seeded!", "created_users": created}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        # Create all tables
        db.create_all()
        print("Database tables created successfully!")
    
    app.run(debug=True, host='127.0.0.1', port=5000)
