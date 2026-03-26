from flask import Flask, render_template, flash, redirect, request, url_for, jsonify
from flask_wtf.csrf import CSRFError
from app.extensions import db, migrate, csrf
from app.config import Config
from werkzeug.middleware.proxy_fix import ProxyFix
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
    for subdir in ('products', 'profiles', 'website', 'collateral'):
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

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(boutique_bp, url_prefix='/boutique')
    app.register_blueprint(hardware_bp, url_prefix='/hardware')
    app.register_blueprint(customers_bp, url_prefix='/customers')
    app.register_blueprint(finance_bp, url_prefix='/finance')
    app.register_blueprint(website_bp, url_prefix='/website')
    
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
        from app.utils.timezone import convert_to_dual_timezone
        site_settings = get_site_settings()
        return {
            'current_user': session.get('username'),
            'current_section': session.get('section'),
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

    # CLI commands
    @app.cli.command('db-ensure')
    def db_ensure():
        """Ensure database is ready for Alembic migrations.

        If the DB already has app tables but no alembic_version,
        stamps the current migration head so 'db upgrade' won't
        try to recreate existing tables.
        Safe to run multiple times — does nothing if already versioned.
        """
        from sqlalchemy import inspect as sa_inspect
        from flask_migrate import stamp
        inspector = sa_inspect(db.engine)
        tables = inspector.get_table_names()
        has_app_tables = 'users' in tables
        has_alembic = 'alembic_version' in tables

        if has_app_tables and not has_alembic:
            click.echo('Existing unversioned database detected. Stamping migration head...')
            stamp()
            click.echo('Done. Database is now tracked by Alembic.')
        elif has_app_tables and has_alembic:
            click.echo('Database already tracked by Alembic. Nothing to do.')
        else:
            click.echo('Empty database. Run "flask db upgrade" to create tables.')

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
