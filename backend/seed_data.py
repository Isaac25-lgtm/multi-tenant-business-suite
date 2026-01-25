from app import create_app, db
from app.models.auth import User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    print("Creating database tables...")
    db.create_all()
    print("Tables created.")

    # Check if admin user exists
    if not User.query.filter_by(username='admin').first():
        print("Creating admin user...")
        admin = User(
            username='admin',
            email='admin@example.com',
            role='Manager',
            password_hash=generate_password_hash('admin123'),
            name='System Admin'
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin user created: username='admin', password='admin123'")
    else:
        print("Admin user already exists.")
