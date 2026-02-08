from app import create_app
from app.extensions import db
import os
from sqlalchemy import inspect, text

app = create_app()

# Create tables on startup (works with both direct run and Gunicorn)
with app.app_context():
    db.create_all()
    print("Database tables created successfully!")

    is_postgres = 'postgresql' in str(db.engine.url)

    # ============ FIX INCOMPATIBLE TABLE SCHEMAS ============
    print("Checking for incompatible table schemas...")
    try:
        inspector = inspect(db.engine)
        actual_tables = inspector.get_table_names()

        # audit_logs: old schema may have user_id NOT NULL that conflicts with new model
        if 'audit_logs' in actual_tables:
            actual_cols = {col['name'] for col in inspector.get_columns('audit_logs')}
            model_cols = {col.name for col in db.metadata.tables['audit_logs'].columns}
            extra_cols = actual_cols - model_cols
            if extra_cols:
                print(f"  audit_logs has extra columns {extra_cols}, dropping and recreating...")
                with db.engine.connect() as conn:
                    conn.execute(text('DROP TABLE audit_logs CASCADE'))
                    conn.commit()
                db.create_all()
                print("  audit_logs table recreated with correct schema")
                inspector = inspect(db.engine)
                actual_tables = inspector.get_table_names()
    except Exception as e:
        print(f"  Schema fix warning: {e}")

    # ============ CONVERT POSTGRESQL ENUM COLUMNS TO VARCHAR ============
    # Models now use String instead of Enum, but existing PostgreSQL columns
    # may still be enum types which cause LookupError on unknown values
    if is_postgres:
        print("Checking for PostgreSQL enum columns that need conversion to VARCHAR...")
        enum_columns_to_fix = [
            ('users', 'role', 'VARCHAR(20)'),
            ('customers', 'business_type', 'VARCHAR(20)'),
            ('boutique_sales', 'payment_type', 'VARCHAR(10)'),
            ('hardware_sales', 'payment_type', 'VARCHAR(10)'),
            ('loans', 'status', 'VARCHAR(20)'),
            ('group_loans', 'status', 'VARCHAR(20)'),
        ]
        try:
            inspector = inspect(db.engine)
            actual_tables = inspector.get_table_names()
            for table_name, col_name, new_type in enum_columns_to_fix:
                if table_name not in actual_tables:
                    continue
                # Check if the column exists and its type
                columns = inspector.get_columns(table_name)
                for col_info in columns:
                    if col_info['name'] == col_name:
                        col_type = str(col_info['type'])
                        # If it's an enum type (not VARCHAR/TEXT), convert it
                        if 'VARCHAR' not in col_type.upper() and 'TEXT' not in col_type.upper() and 'CHAR' not in col_type.upper():
                            print(f"  Converting {table_name}.{col_name} from {col_type} to {new_type}...")
                            try:
                                with db.engine.connect() as conn:
                                    conn.execute(text(
                                        f'ALTER TABLE {table_name} ALTER COLUMN {col_name} TYPE {new_type} USING {col_name}::text'
                                    ))
                                    conn.commit()
                                print(f"    + Converted {table_name}.{col_name} to {new_type}")
                            except Exception as e:
                                print(f"    ! Failed to convert {table_name}.{col_name}: {e}")
                        break
            # Drop orphaned enum types (optional cleanup)
            try:
                with db.engine.connect() as conn:
                    for enum_name in ['user_role', 'customer_business_type', 'payment_type',
                                      'hardware_payment_type', 'loan_status', 'group_loan_status']:
                        try:
                            conn.execute(text(f'DROP TYPE IF EXISTS {enum_name}'))
                        except Exception:
                            pass
                    conn.commit()
                print("  Cleaned up orphaned enum types")
            except Exception:
                pass
        except Exception as e:
            print(f"  Enum conversion warning: {e}")

    # ============ AUTO-MIGRATE: ADD MISSING COLUMNS ============
    print("Running auto schema migration...")
    try:
        inspector = inspect(db.engine)
        actual_tables = inspector.get_table_names()

        for table_name, model_table in db.metadata.tables.items():
            if table_name not in actual_tables:
                continue

            actual_columns = {col['name'] for col in inspector.get_columns(table_name)}
            model_columns = {col.name for col in model_table.columns}
            missing = model_columns - actual_columns

            if missing:
                print(f"  Table '{table_name}' missing columns: {missing}")
                for col_name in missing:
                    col = model_table.columns[col_name]
                    try:
                        col_type_str = col.type.compile(dialect=db.engine.dialect)
                    except Exception:
                        col_type_str = str(col.type)

                    default = ""
                    if col.default is not None:
                        if hasattr(col.default, 'arg'):
                            default_val = col.default.arg
                            if isinstance(default_val, bool):
                                default = f" DEFAULT {'true' if default_val else 'false'}"
                            elif isinstance(default_val, (int, float)):
                                default = f" DEFAULT {default_val}"
                            elif isinstance(default_val, str):
                                default = f" DEFAULT '{default_val}'"

                    sql = f'ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type_str}'
                    if default:
                        sql += default

                    try:
                        with db.engine.connect() as conn:
                            conn.execute(text(sql))
                            conn.commit()
                        print(f"    + Added '{col_name}' ({col_type_str}) to '{table_name}'")
                    except Exception as e:
                        print(f"    ! Failed to add '{col_name}' to '{table_name}': {e}")

        print("Auto schema migration complete!")
    except Exception as e:
        print(f"Migration error (non-fatal): {e}")
        print("App will continue starting...")

    # ============ SEED DEFAULT MANAGER USER ============
    print("Checking for default manager account...")
    try:
        from app.models.user import User
        manager = User.query.filter_by(role='manager').first()
        if not manager:
            print("  No manager account found, creating default...")
            manager = User(
                username='admin',
                full_name='System Admin',
                role='manager',
                is_active=True,
                can_access_boutique=True,
                can_access_hardware=True,
                can_access_finance=True,
                can_access_customers=True,
            )
            manager.set_password('admin123')
            db.session.add(manager)
            db.session.commit()
            print("  + Created default manager: admin / admin123")
        else:
            print(f"  Manager account exists: {manager.username}")
    except Exception as e:
        print(f"  Seed user warning: {e}")
        db.session.rollback()

    print("Startup complete!")


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
