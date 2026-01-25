from app import create_app, db
from app.models.auth import User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    print("Creating database tables...")
    db.create_all()
    print("Tables created.")

    # Create Manager User
    if not User.query.filter_by(username='manager').first():
        print("Creating manager user...")
        manager = User(
            username='manager',
            email='manager@example.com',
            role='Manager',
            password_hash=generate_password_hash('admin123'),
            name='General Manager'
        )
        db.session.add(manager)
        print("Manager user created.")

    # Create Boutique Staff (Sarah)
    if not User.query.filter_by(username='sarah').first():
        print("Creating boutique staff (Sarah)...")
        sarah = User(
            username='sarah',
            email='sarah@example.com',
            role='Employee',
            assigned_business='boutique',
            password_hash=generate_password_hash('pass123'),
            name='Sarah Jenkins'
        )
        db.session.add(sarah)
        print("Boutique staff created.")

    # Create Hardware Staff (David)
    if not User.query.filter_by(username='david').first():
        print("Creating hardware staff (David)...")
        david = User(
            username='david',
            email='david@example.com',
            role='Employee',
            assigned_business='hardware',
            password_hash=generate_password_hash('pass123'),
            name='David Miller'
        )
        db.session.add(david)
        print("Hardware staff created.")

    # Create Finance Staff (Grace)
    if not User.query.filter_by(username='grace').first():
        print("Creating finance staff (Grace)...")
        grace = User(
            username='grace',
            email='grace@example.com',
            role='Employee',
            assigned_business='finances',
            password_hash=generate_password_hash('pass123'),
            name='Grace A.'
        )
        db.session.add(grace)
        print("Finance staff created.")

    db.session.commit()
    print("All seed users created successfully!")
