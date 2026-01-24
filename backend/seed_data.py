"""
Seed demo data for Denove APS
Run this after initial database setup
"""
from app import create_app, db
from app.models.user import User
from app.models.customer import Customer
from app.models.boutique import BoutiqueCategory, BoutiqueStock
from app.models.hardware import HardwareCategory, HardwareStock
from app.models.finance import LoanClient, Loan, LoanPayment, GroupLoan, GroupLoanPayment
from datetime import datetime, date, timedelta


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
        
        # Sample Customers (for boutique/hardware)
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
        
        # ============= FINANCE DATA (DELETABLE) =============
        
        # Loan Clients
        loan_clients = [
            LoanClient(
                name='John Mukasa',
                nin='CM1234567890',
                phone='0701234567',
                address='Kawempe, Kampala',
                created_by=manager.id
            ),
            LoanClient(
                name='Grace Auma',
                nin='CF9876543210',
                phone='0751112222',
                address='Ntinda, Kampala',
                created_by=manager.id
            ),
            LoanClient(
                name='Peter Okello',
                nin='CM5566778899',
                phone='0781234999',
                address='Mukono Town',
                created_by=manager.id
            )
        ]
        db.session.add_all(loan_clients)
        db.session.commit()
        print("[OK] Loan clients created")
        
        # Individual Loans
        today = date.today()
        loans = [
            Loan(
                client_id=1,
                principal=500000,
                interest_rate=10,
                interest_amount=50000,
                total_amount=550000,
                amount_paid=100000,
                balance=450000,
                duration_weeks=4,
                issue_date=today - timedelta(weeks=2),
                due_date=today + timedelta(weeks=2),
                status='active',
                created_by=manager.id
            ),
            Loan(
                client_id=2,
                principal=300000,
                interest_rate=10,
                interest_amount=30000,
                total_amount=330000,
                amount_paid=0,
                balance=330000,
                duration_weeks=4,
                issue_date=today - timedelta(weeks=5),
                due_date=today - timedelta(weeks=1),
                status='overdue',
                created_by=manager.id
            ),
            Loan(
                client_id=3,
                principal=1000000,
                interest_rate=12,
                interest_amount=120000,
                total_amount=1120000,
                amount_paid=200000,
                balance=920000,
                duration_weeks=8,
                issue_date=today - timedelta(weeks=2),
                due_date=today + timedelta(weeks=6),
                status='active',
                created_by=manager.id
            )
        ]
        db.session.add_all(loans)
        db.session.commit()
        print("[OK] Individual loans created")
        
        # Loan Payments
        loan_payments = [
            LoanPayment(
                loan_id=1,
                payment_date=today - timedelta(days=7),
                amount=50000,
                balance_after=500000,
                notes='First payment',
                created_by=grace.id
            ),
            LoanPayment(
                loan_id=1,
                payment_date=today,
                amount=50000,
                balance_after=450000,
                notes='Second payment',
                created_by=grace.id
            ),
            LoanPayment(
                loan_id=3,
                payment_date=today - timedelta(days=3),
                amount=200000,
                balance_after=920000,
                notes='Partial payment',
                created_by=manager.id
            )
        ]
        db.session.add_all(loan_payments)
        db.session.commit()
        print("[OK] Loan payments created")
        
        # Group Loans
        group_loans = [
            GroupLoan(
                group_name='Kyebando Women Group',
                member_count=5,
                total_amount=2750000,
                amount_per_period=275000,
                total_periods=10,
                periods_paid=2,
                amount_paid=550000,
                balance=2200000,
                status='active',
                created_by=manager.id
            ),
            GroupLoan(
                group_name='Kawempe Traders Association',
                member_count=8,
                total_amount=4400000,
                amount_per_period=550000,
                total_periods=8,
                periods_paid=2,
                amount_paid=1100000,
                balance=3300000,
                status='active',
                created_by=manager.id
            )
        ]
        db.session.add_all(group_loans)
        db.session.commit()
        print("[OK] Group loans created")
        
        # Group Loan Payments
        group_payments = [
            GroupLoanPayment(
                group_loan_id=1,
                payment_date=today - timedelta(weeks=2),
                amount=275000,
                periods_covered=1,
                balance_after=2475000,
                notes='Week 1 payment',
                created_by=grace.id
            ),
            GroupLoanPayment(
                group_loan_id=1,
                payment_date=today - timedelta(weeks=1),
                amount=275000,
                periods_covered=1,
                balance_after=2200000,
                notes='Week 2 payment',
                created_by=grace.id
            ),
            GroupLoanPayment(
                group_loan_id=2,
                payment_date=today - timedelta(weeks=1),
                amount=1100000,
                periods_covered=2,
                balance_after=3300000,
                notes='First 2 weeks combined',
                created_by=manager.id
            )
        ]
        db.session.add_all(group_payments)
        db.session.commit()
        print("[OK] Group loan payments created")
        
        print("\n[SUCCESS] Database seeding completed successfully!")
        print("\nDemo Users:")
        print("  Manager: username='manager', password='admin123'")
        print("  Sarah (Boutique): username='sarah', password='pass123'")
        print("  David (Hardware): username='david', password='pass123'")
        print("  Grace (Finances): username='grace', password='pass123'")
        print("\nSample Finance Data:")
        print("  3 Loan Clients (deletable)")
        print("  3 Individual Loans (1 overdue, 2 active)")
        print("  2 Group Loans (active)")
        print("  Sample payments recorded")


if __name__ == '__main__':
    seed_data()

