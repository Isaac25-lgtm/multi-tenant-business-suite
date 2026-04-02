from flask import Flask, render_template, flash, redirect, request, url_for, jsonify
from flask_wtf.csrf import CSRFError
from app.extensions import db, migrate, csrf
from app.config import Config
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy.exc import SQLAlchemyError, OperationalError, ProgrammingError
import os
import json
import click


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Normalize and create upload folders so Render can mount a persistent disk there.
    upload_root = app.config['UPLOAD_FOLDER']
    if not os.path.isabs(upload_root):
        upload_root = os.path.join(app.root_path, upload_root)
    upload_root = os.path.normpath(upload_root)
    app.config['UPLOAD_FOLDER'] = upload_root
    os.makedirs(upload_root, exist_ok=True)
    for subdir in ('products', 'profiles', 'website', 'collateral', 'ocr'):
        os.makedirs(os.path.join(upload_root, subdir), exist_ok=True)

    # Register blueprints
    from app.modules.auth import auth_bp
    from app.modules.boutique import boutique_bp
    from app.modules.hardware import hardware_bp
    from app.modules.customers import customers_bp
    from app.modules.dashboard import dashboard_bp
    from app.modules.finance import finance_bp
    from app.modules.storefront import storefront_bp
    from app.modules.website_management import website_bp
    from app.modules.ai import ai_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(boutique_bp, url_prefix='/boutique')
    app.register_blueprint(hardware_bp, url_prefix='/hardware')
    app.register_blueprint(customers_bp, url_prefix='/customers')
    app.register_blueprint(finance_bp, url_prefix='/finance')
    app.register_blueprint(website_bp, url_prefix='/website')
    app.register_blueprint(ai_bp, url_prefix='/ai')
    
    # Public storefront at root - no authentication required
    app.register_blueprint(storefront_bp)

    # Register custom Jinja2 filters
    @app.template_filter('from_json')
    def from_json_filter(value):
        """Parse JSON string to dict/list"""
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None

    # Make current user and timezone utilities available in templates
    @app.context_processor
    def inject_utilities():
        from flask import session
        from app.utils.branding import get_company_display_name, get_site_settings
        from app.utils.ai_client import is_chat_enabled
        from app.utils.timezone import convert_to_dual_timezone
        site_settings = get_site_settings()
        return {
            'current_user': session.get('username'),
            'current_section': session.get('section'),
            'ai_chat_enabled': is_chat_enabled(),
            'convert_to_dual_timezone': convert_to_dual_timezone,
            'site_settings': site_settings,
            'brand_display_name': get_company_display_name(site_settings),
        }

    @app.get('/healthz')
    def healthz():
        """Lightweight health endpoint for Render health checks."""
        return jsonify({'status': 'ok'}), 200

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        flash('Your session expired or the form is invalid. Please try again.', 'error')
        return redirect(request.referrer or url_for('auth.login'))

    def _is_api_request():
        path = (request.path or '').lower()
        accept = request.accept_mimetypes
        return (
            request.is_json
            or path.startswith('/api/')
            or '/api/' in path
            or accept.accept_json and not accept.accept_html
        )

    @app.errorhandler(OperationalError)
    @app.errorhandler(ProgrammingError)
    @app.errorhandler(SQLAlchemyError)
    def handle_database_error(exc):
        # Keep production logs concise so Render doesn't get flooded with SQL traces
        # for known schema/config issues. We still surface enough context to debug.
        if app.debug:
            app.logger.exception('Database request failed on %s %s', request.method, request.path)
        else:
            app.logger.error(
                'Database request failed on %s %s (%s)',
                request.method,
                request.path,
                exc.__class__.__name__,
            )

        if _is_api_request():
            return jsonify({
                'error': 'service_unavailable',
                'message': 'A database problem prevented this request from completing.',
            }), 503

        return render_template('errors/500.html'), 500

    # CLI commands
    @app.cli.command('db-ensure')
    def db_ensure():
        """Safely prepare the database for Alembic migrations.

        Behaviour:
        - Empty DB (no app tables, no alembic_version): safe — do nothing,
          let 'flask db upgrade' create everything from scratch.
        - Already versioned (alembic_version exists): safe — do nothing.
        - Non-empty but unversioned (app tables exist, no alembic_version):
          UNSAFE to auto-stamp — the schema may be behind HEAD.
          Fail loudly with remediation instructions.
        """
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(db.engine)
        tables = inspector.get_table_names()
        app_tables = {
            'users',
            'audit_logs',
            'customers',
            'loan_clients',
            'loans',
            'loan_payments',
            'group_loans',
            'group_loan_payments',
            'loan_documents',
            'boutique_categories',
            'boutique_stock',
            'boutique_sales',
            'boutique_sale_items',
            'boutique_credit_payments',
            'boutique_hires',
            'boutique_hire_payments',
            'hardware_categories',
            'hardware_stock',
            'hardware_sales',
            'hardware_sale_items',
            'hardware_credit_payments',
            'published_products',
            'product_images',
            'website_images',
            'website_loan_inquiries',
            'website_order_requests',
            'website_settings',
            'rate_limit_states',
            'daily_briefings',
            'briefing_dismissals',
            'chat_messages',
            'ocr_extractions',
        }
        has_app_tables = bool(app_tables.intersection(tables))
        has_alembic = 'alembic_version' in tables

        if has_app_tables and not has_alembic:
            click.echo('ERROR: Database has app tables but no Alembic version tracking.', err=True)
            click.echo('', err=True)
            click.echo('This means the schema may be out of date. Auto-stamping HEAD', err=True)
            click.echo('would hide missing columns/tables and cause 500 errors.', err=True)
            click.echo('', err=True)
            click.echo('To fix this safely:', err=True)
            click.echo('  1. Run: python -m flask --app run:app db-doctor', err=True)
            click.echo('     (check what is missing)', err=True)
            click.echo('  2. If everything passes, run:', err=True)
            click.echo('     python -m flask --app run:app db stamp head', err=True)
            click.echo('     (mark as current)', err=True)
            click.echo('  3. If db-doctor reports missing items, run:', err=True)
            click.echo('     python -m flask --app run:app db stamp <last-applied>', err=True)
            click.echo('     python -m flask --app run:app db upgrade', err=True)
            click.echo('     (apply remaining migrations)', err=True)
            raise SystemExit(1)
        elif has_app_tables and has_alembic:
            click.echo('Database already tracked by Alembic. Nothing to do.')
        else:
            click.echo('Empty database. Run "python -m flask --app run:app db upgrade" to create tables.')

    @app.cli.command('db-doctor')
    def db_doctor():
        """Verify the PostgreSQL schema has all expected tables and columns.

        Checks for production-critical objects introduced by migrations.
        Exits 0 if everything is present, 1 if anything is missing.
        """
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(db.engine)
        tables = inspector.get_table_names()

        # Required tables
        required_tables = [
            'users',
            'website_settings',
            'rate_limit_states',
            'customers',
            'loan_clients',
            'loans',
            'website_loan_inquiries',
            'boutique_stock',
            'boutique_sales',
            'hardware_stock',
            'hardware_sales',
            'daily_briefings',
            'briefing_dismissals',
            'chat_messages',
            'ocr_extractions',
        ]

        # Required columns  (table, column)
        required_columns = [
            ('customers', 'nin_encrypted'),
            ('loan_clients', 'nin_encrypted'),
            ('loan_clients', 'payer_status'),
            ('loans', 'interest_mode'),
            ('loans', 'monthly_interest_amount'),
            ('website_loan_inquiries', 'finance_client_id'),
        ]

        missing_tables = []
        missing_columns = []
        ok_count = 0

        for table in required_tables:
            if table in tables:
                ok_count += 1
                click.echo(click.style(f'  OK   table  {table}', fg='green'))
            else:
                missing_tables.append(table)
                click.echo(click.style(f'  MISS table  {table}', fg='red'))

        for table, column in required_columns:
            if table not in tables:
                missing_columns.append((table, column))
                click.echo(click.style(f'  MISS column {table}.{column} (table missing)', fg='red'))
                continue
            cols = [c['name'] for c in inspector.get_columns(table)]
            if column in cols:
                ok_count += 1
                click.echo(click.style(f'  OK   column {table}.{column}', fg='green'))
            else:
                missing_columns.append((table, column))
                click.echo(click.style(f'  MISS column {table}.{column}', fg='red'))

        # Check Alembic version
        click.echo('')
        if 'alembic_version' in tables:
            from sqlalchemy import text
            row = db.session.execute(text('SELECT version_num FROM alembic_version')).fetchone()
            if row:
                click.echo(f'Alembic version: {row[0]}')
            else:
                click.echo(click.style('Alembic version table exists but is empty!', fg='yellow'))
        else:
            click.echo(click.style('No alembic_version table — migrations have never run.', fg='yellow'))

        click.echo('')
        total = len(required_tables) + len(required_columns)
        if missing_tables or missing_columns:
            click.echo(click.style(
                f'FAIL: {len(missing_tables)} tables and {len(missing_columns)} columns missing '
                f'({ok_count}/{total} checks passed).',
                fg='red', bold=True,
            ))
            click.echo('')
            click.echo('Run "python -m flask --app run:app db upgrade" to apply pending migrations.')
            raise SystemExit(1)
        else:
            click.echo(click.style(
                f'ALL OK: {ok_count}/{total} checks passed.',
                fg='green', bold=True,
            ))

    @app.cli.command('create-admin')
    @click.option('--username', prompt=True, help='Admin username')
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Admin password')
    @click.option('--full-name', prompt='Full name', default='', help='Admin full name')
    def create_admin(username, password, full_name):
        """Create a manager account with full access."""
        if len(password) < 8:
            click.echo('Error: Password must be at least 8 characters.')
            raise SystemExit(1)

        from app.models.user import User
        existing = User.query.filter_by(username=username).first()
        if existing:
            click.echo(f'Error: Username "{username}" already exists.')
            raise SystemExit(1)

        user = User(
            username=username,
            full_name=full_name or None,
            role='manager',
            is_active=True,
            can_access_boutique=True,
            can_access_hardware=True,
            can_access_finance=True,
            can_access_customers=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f'Manager account "{username}" created successfully.')

    return app
