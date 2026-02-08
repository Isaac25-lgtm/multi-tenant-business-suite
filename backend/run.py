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
    def add_column_if_missing(table, column, col_type):
        """Safely add a column to a table if it doesn't exist."""
        try:
            insp = inspect(db.engine)
            existing = [c['name'] for c in insp.get_columns(table)]
            if column not in existing:
                with db.engine.connect() as conn:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {col_type}'))
                    conn.commit()
                print(f"  Added {column} to {table}")
                return True
        except Exception as e:
            print(f"  Warning: Could not add {column} to {table}: {e}")
        return False

    print("Running schema migrations...")

    # ── Users table ──
    add_column_if_missing('users', 'last_login', 'TIMESTAMP')
    add_column_if_missing('users', 'full_name', 'VARCHAR(100)')
    add_column_if_missing('users', 'email', 'VARCHAR(100)')
    add_column_if_missing('users', 'phone', 'VARCHAR(20)')
    add_column_if_missing('users', 'profile_picture', 'VARCHAR(255)')
    add_column_if_missing('users', 'can_access_boutique', 'BOOLEAN DEFAULT FALSE')
    add_column_if_missing('users', 'can_access_hardware', 'BOOLEAN DEFAULT FALSE')
    add_column_if_missing('users', 'can_access_finance', 'BOOLEAN DEFAULT FALSE')
    add_column_if_missing('users', 'can_access_customers', 'BOOLEAN DEFAULT FALSE')
    add_column_if_missing('users', 'boutique_branch', 'VARCHAR(10)')
    add_column_if_missing('users', 'created_by', 'INTEGER')

    # ── Audit logs table ──
    add_column_if_missing('audit_logs', 'username', 'VARCHAR(50)')
    add_column_if_missing('audit_logs', 'section', 'VARCHAR(50)')
    add_column_if_missing('audit_logs', 'action', 'VARCHAR(50)')
    add_column_if_missing('audit_logs', 'entity', 'VARCHAR(50)')
    add_column_if_missing('audit_logs', 'entity_id', 'INTEGER')
    add_column_if_missing('audit_logs', 'details', 'TEXT')
    add_column_if_missing('audit_logs', 'ip_address', 'VARCHAR(45)')

    # ── Customers table ──
    add_column_if_missing('customers', 'address', 'VARCHAR(255)')
    add_column_if_missing('customers', 'nin', 'VARCHAR(20)')

    # ── Boutique stock table ──
    add_column_if_missing('boutique_stock', 'branch', 'VARCHAR(10)')
    add_column_if_missing('boutique_stock', 'image_url', 'VARCHAR(500)')
    add_column_if_missing('boutique_stock', 'initial_quantity', 'INTEGER DEFAULT 0')
    add_column_if_missing('boutique_stock', 'unit', "VARCHAR(20) DEFAULT 'pieces'")
    add_column_if_missing('boutique_stock', 'low_stock_threshold', 'INTEGER')
    add_column_if_missing('boutique_stock', 'updated_at', 'TIMESTAMP')

    # ── Boutique sales table ──
    add_column_if_missing('boutique_sales', 'branch', 'VARCHAR(10)')
    add_column_if_missing('boutique_sales', 'is_deleted', 'BOOLEAN DEFAULT FALSE')
    add_column_if_missing('boutique_sales', 'updated_at', 'TIMESTAMP')
    add_column_if_missing('boutique_sales', 'deleted_at', 'TIMESTAMP')

    # ── Boutique sale items table ──
    add_column_if_missing('boutique_sale_items', 'is_other_item', 'BOOLEAN DEFAULT FALSE')

    # ── Boutique credit payments table ──
    add_column_if_missing('boutique_credit_payments', 'remaining_balance', 'NUMERIC(12,2)')

    # ── Hardware stock table ──
    add_column_if_missing('hardware_stock', 'initial_quantity', 'INTEGER DEFAULT 0')
    add_column_if_missing('hardware_stock', 'unit', "VARCHAR(20) DEFAULT 'pieces'")
    add_column_if_missing('hardware_stock', 'low_stock_threshold', 'INTEGER')
    add_column_if_missing('hardware_stock', 'updated_at', 'TIMESTAMP')

    # ── Hardware sales table ──
    add_column_if_missing('hardware_sales', 'is_deleted', 'BOOLEAN DEFAULT FALSE')
    add_column_if_missing('hardware_sales', 'updated_at', 'TIMESTAMP')
    add_column_if_missing('hardware_sales', 'deleted_at', 'TIMESTAMP')

    # ── Hardware sale items table ──
    add_column_if_missing('hardware_sale_items', 'is_other_item', 'BOOLEAN DEFAULT FALSE')

    # ── Hardware credit payments table ──
    add_column_if_missing('hardware_credit_payments', 'remaining_balance', 'NUMERIC(12,2)')

    # ── Loan clients table ──
    add_column_if_missing('loan_clients', 'nin', 'VARCHAR(20)')
    add_column_if_missing('loan_clients', 'address', 'VARCHAR(200)')
    add_column_if_missing('loan_clients', 'is_active', 'BOOLEAN DEFAULT TRUE')

    # ── Loans table ──
    add_column_if_missing('loans', 'interest_amount', 'NUMERIC(12,2)')
    add_column_if_missing('loans', 'total_amount', 'NUMERIC(12,2)')
    add_column_if_missing('loans', 'amount_paid', 'NUMERIC(12,2) DEFAULT 0')
    add_column_if_missing('loans', 'balance', 'NUMERIC(12,2)')
    add_column_if_missing('loans', 'duration_weeks', 'INTEGER')
    add_column_if_missing('loans', 'due_date', 'DATE')
    add_column_if_missing('loans', 'is_deleted', 'BOOLEAN DEFAULT FALSE')
    add_column_if_missing('loans', 'updated_at', 'TIMESTAMP')
    add_column_if_missing('loans', 'deleted_at', 'TIMESTAMP')

    # ── Loan payments table ──
    add_column_if_missing('loan_payments', 'balance_after', 'NUMERIC(12,2)')
    add_column_if_missing('loan_payments', 'notes', 'VARCHAR(200)')
    add_column_if_missing('loan_payments', 'is_deleted', 'BOOLEAN DEFAULT FALSE')

    # ── Group loans table ──
    add_column_if_missing('group_loans', 'members_json', 'TEXT')
    add_column_if_missing('group_loans', 'principal', 'NUMERIC(12,2) DEFAULT 0')
    add_column_if_missing('group_loans', 'interest_rate', 'NUMERIC(5,2) DEFAULT 0')
    add_column_if_missing('group_loans', 'interest_amount', 'NUMERIC(12,2) DEFAULT 0')
    add_column_if_missing('group_loans', 'amount_per_period', 'NUMERIC(12,2)')
    add_column_if_missing('group_loans', 'total_periods', 'INTEGER')
    add_column_if_missing('group_loans', 'period_type', "VARCHAR(20) DEFAULT 'monthly'")
    add_column_if_missing('group_loans', 'periods_paid', 'INTEGER DEFAULT 0')
    add_column_if_missing('group_loans', 'amount_paid', 'NUMERIC(12,2) DEFAULT 0')
    add_column_if_missing('group_loans', 'issue_date', 'DATE')
    add_column_if_missing('group_loans', 'due_date', 'DATE')
    add_column_if_missing('group_loans', 'is_deleted', 'BOOLEAN DEFAULT FALSE')
    add_column_if_missing('group_loans', 'updated_at', 'TIMESTAMP')

    # ── Group loan payments table ──
    add_column_if_missing('group_loan_payments', 'periods_covered', 'INTEGER DEFAULT 1')
    add_column_if_missing('group_loan_payments', 'balance_after', 'NUMERIC(12,2)')
    add_column_if_missing('group_loan_payments', 'notes', 'VARCHAR(200)')
    add_column_if_missing('group_loan_payments', 'is_deleted', 'BOOLEAN DEFAULT FALSE')

    # ── Loan documents table ──
    add_column_if_missing('loan_documents', 'group_loan_id', 'INTEGER')
    add_column_if_missing('loan_documents', 'file_type', 'VARCHAR(50)')
    add_column_if_missing('loan_documents', 'is_deleted', 'BOOLEAN DEFAULT FALSE')

    print("Schema migrations complete!")


if __name__ == '__main__':
    # Use PORT environment variable if available (for Render), otherwise default to 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
