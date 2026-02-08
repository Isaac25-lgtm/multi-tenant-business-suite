from app import create_app
from app.extensions import db
import os
from sqlalchemy import inspect, text, MetaData

app = create_app()

# Create tables on startup (works with both direct run and Gunicorn)
with app.app_context():
    db.create_all()
    print("Database tables created successfully!")

    # Auto-migrate: compare model schema vs actual DB and add missing columns
    print("Running auto schema migration...")
    try:
        inspector = inspect(db.engine)
        actual_tables = inspector.get_table_names()

        for table_name, model_table in db.metadata.tables.items():
            if table_name not in actual_tables:
                print(f"  Table {table_name} does not exist yet, skipping (create_all should handle it)")
                continue

            # Get actual columns in the database
            actual_columns = {col['name'] for col in inspector.get_columns(table_name)}
            # Get expected columns from SQLAlchemy model
            model_columns = {col.name for col in model_table.columns}
            # Find missing columns
            missing = model_columns - actual_columns

            if missing:
                print(f"  Table '{table_name}' missing columns: {missing}")
                for col_name in missing:
                    col = model_table.columns[col_name]
                    # Map SQLAlchemy type to PostgreSQL type
                    try:
                        col_type_str = col.type.compile(dialect=db.engine.dialect)
                    except Exception:
                        col_type_str = str(col.type)

                    # Build ALTER TABLE statement
                    nullable = "NULL" if col.nullable else "NOT NULL"
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

                    # For nullable columns without explicit default, just add the column
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


if __name__ == '__main__':
    # Use PORT environment variable if available (for Render), otherwise default to 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
