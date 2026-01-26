from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    print("Creating database tables...")
    db.create_all()
    print("Tables created.")

    created = []

    # Create Manager User
    if not User.query.filter_by(username='manager').first():
        print("Creating manager user...")
        manager = User(
            username='manager',
            name='General Manager',
            role='manager',
            assigned_business='all'
        )
        manager.set_password('admin123')
        db.session.add(manager)
        created.append('manager')
        print("Manager user created.")

    # Create Boutique Staff (Sarah)
    if not User.query.filter_by(username='sarah').first():
        print("Creating boutique staff (Sarah)...")
        sarah = User(
            username='sarah',
            name='Sarah Jenkins',
            role='employee',
            assigned_business='boutique'
        )
        sarah.set_password('pass123')
        db.session.add(sarah)
        created.append('sarah')
        print("Boutique staff created.")

    # Create Hardware Staff (David)
    if not User.query.filter_by(username='david').first():
        print("Creating hardware staff (David)...")
        david = User(
            username='david',
            name='David Miller',
            role='employee',
            assigned_business='hardware'
        )
        david.set_password('pass123')
        db.session.add(david)
        created.append('david')
        print("Hardware staff created.")

    # Create Finance Staff (Grace)
    if not User.query.filter_by(username='grace').first():
        print("Creating finance staff (Grace)...")
        grace = User(
            username='grace',
            name='Grace A.',
            role='employee',
            assigned_business='finances'
        )
        grace.set_password('pass123')
        db.session.add(grace)
        created.append('grace')
        print("Finance staff created.")

    db.session.commit()
    print(f"All seed users created successfully! Created: {', '.join(created)}")
