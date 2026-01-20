"""
Seed demo data for Denove APS
Run this after initial database setup
"""
from app import create_app, db
from app.models.user import User
from app.models.customer import Customer
from app.models.boutique import BoutiqueCategory, BoutiqueStock
from app.models.hardware import HardwareCategory, HardwareStock
from datetime import datetime


def seed_data():
    app = create_app()
    
    with app.app_context():
        print("Starting database seed...")
        
        # Clear existing data (optional - remove in production)
        db.drop_all()
        db.create_all()
        
        # Create Manager
        manager = User(
            username='manager',
            name='Manager',
            role='manager',
            assigned_business='all',
            is_active=True,
            can_backdate=True,
            backdate_limit=365,
            can_edit=True,
            can_delete=True,
            can_clear_credits=True
        )
        manager.set_password('admin123')
        db.session.add(manager)
        
        # Create Employees
        sarah = User(
            username='sarah',
            name='Sarah Nakato',
            role='employee',
            assigned_business='boutique',
            is_active=True,
            can_backdate=False,
            backdate_limit=1,
            can_edit=True,
            can_delete=True,
            can_clear_credits=True
        )
        sarah.set_password('pass123')
        db.session.add(sarah)
        
        david = User(
            username='david',
            name='David Okello',
            role='employee',
            assigned_business='hardware',
            is_active=True,
            can_backdate=False,
            backdate_limit=1,
            can_edit=True,
            can_delete=True,
            can_clear_credits=True
        )
        david.set_password('pass123')
        db.session.add(david)
        
        grace = User(
            username='grace',
            name='Grace Nambi',
            role='employee',
            assigned_business='finances',
            is_active=True,
            can_backdate=False,
            backdate_limit=1,
            can_edit=True,
            can_delete=False,
            can_clear_credits=True
        )
        grace.set_password('pass123')
        db.session.add(grace)
        
        db.session.commit()
        print("[OK] Users created")
        
        # Boutique Categories
        boutique_categories = [
            BoutiqueCategory(name='Dresses'),
            BoutiqueCategory(name='Shoes'),
            BoutiqueCategory(name='Perfumes'),
            BoutiqueCategory(name='Bags'),
            BoutiqueCategory(name='Shirts')
        ]
        db.session.add_all(boutique_categories)
        db.session.commit()
        print("[OK] Boutique categories created")
        
        # Boutique Stock
        boutique_stock = [
            BoutiqueStock(
                item_name='Ladies Dress - Floral',
                category_id=1,
                quantity=20,
                initial_quantity=20,
                unit='pieces',
                cost_price=45000,
                min_selling_price=80000,
                max_selling_price=95000,
                low_stock_threshold=5,
                created_by=manager.id
            ),
            BoutiqueStock(
                item_name='Kids Shoes - Sneakers',
                category_id=2,
                quantity=30,
                initial_quantity=30,
                unit='pairs',
                cost_price=25000,
                min_selling_price=40000,
                max_selling_price=55000,
                low_stock_threshold=7,
                created_by=manager.id
            ),
            BoutiqueStock(
                item_name='Perfume - Designer',
                category_id=3,
                quantity=15,
                initial_quantity=15,
                unit='bottles',
                cost_price=60000,
                min_selling_price=100000,
                max_selling_price=130000,
                low_stock_threshold=4,
                created_by=manager.id
            ),
            BoutiqueStock(
                item_name='Hand Bag - Leather',
                category_id=4,
                quantity=12,
                initial_quantity=12,
                unit='pieces',
                cost_price=35000,
                min_selling_price=65000,
                max_selling_price=85000,
                low_stock_threshold=3,
                created_by=manager.id
            ),
            BoutiqueStock(
                item_name='Mens Shirt - Formal',
                category_id=5,
                quantity=25,
                initial_quantity=25,
                unit='pieces',
                cost_price=20000,
                min_selling_price=35000,
                max_selling_price=50000,
                low_stock_threshold=6,
                created_by=manager.id
            )
        ]
        db.session.add_all(boutique_stock)
        db.session.commit()
        print("[OK] Boutique stock created")
        
        # Hardware Categories
        hardware_categories = [
            HardwareCategory(name='Building Materials'),
            HardwareCategory(name='Roofing'),
            HardwareCategory(name='Fasteners'),
            HardwareCategory(name='Steel'),
            HardwareCategory(name='Fencing')
        ]
        db.session.add_all(hardware_categories)
        db.session.commit()
        print("[OK] Hardware categories created")
        
        # Hardware Stock
        hardware_stock = [
            HardwareStock(
                item_name='Cement',
                category_id=1,
                quantity=200,
                initial_quantity=200,
                unit='bags',
                cost_price=32000,
                min_selling_price=36000,
                max_selling_price=40000,
                low_stock_threshold=50,
                created_by=manager.id
            ),
            HardwareStock(
                item_name='Iron Sheets - G32',
                category_id=2,
                quantity=150,
                initial_quantity=150,
                unit='pieces',
                cost_price=38000,
                min_selling_price=42000,
                max_selling_price=48000,
                low_stock_threshold=37,
                created_by=manager.id
            ),
            HardwareStock(
                item_name='Nails - 4 inch',
                category_id=3,
                quantity=100,
                initial_quantity=100,
                unit='kgs',
                cost_price=6000,
                min_selling_price=8000,
                max_selling_price=10000,
                low_stock_threshold=25,
                created_by=manager.id
            ),
            HardwareStock(
                item_name='Y12 Steel Bars',
                category_id=4,
                quantity=80,
                initial_quantity=80,
                unit='pieces',
                cost_price=22000,
                min_selling_price=25000,
                max_selling_price=30000,
                low_stock_threshold=20,
                created_by=manager.id
            ),
            HardwareStock(
                item_name='Barbed Wire',
                category_id=5,
                quantity=50,
                initial_quantity=50,
                unit='rolls',
                cost_price=75000,
                min_selling_price=85000,
                max_selling_price=95000,
                low_stock_threshold=12,
                created_by=manager.id
            )
        ]
        db.session.add_all(hardware_stock)
        db.session.commit()
        print("[OK] Hardware stock created")
        
        # Sample Customers
        customers = [
            Customer(
                name='John Okello',
                phone='0700123456',
                address='Kampala',
                business_type='boutique',
                created_by=sarah.id
            ),
            Customer(
                name='Mary Namara',
                phone='0750987654',
                address='Entebbe',
                business_type='hardware',
                created_by=david.id
            ),
            Customer(
                name='Peter Mugisha',
                phone='0780555111',
                address='Jinja',
                business_type='boutique',
                created_by=sarah.id
            )
        ]
        db.session.add_all(customers)
        db.session.commit()
        print("[OK] Sample customers created")
        
        print("\n[SUCCESS] Database seeding completed successfully!")
        print("\nDemo Users:")
        print("  Manager: username='manager', password='admin123'")
        print("  Sarah (Boutique): username='sarah', password='pass123'")
        print("  David (Hardware): username='david', password='pass123'")
        print("  Grace (Finances): username='grace', password='pass123'")


if __name__ == '__main__':
    seed_data()
