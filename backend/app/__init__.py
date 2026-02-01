from flask import Flask, render_template
from app.extensions import db, migrate
from app.config import Config
import os


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Create upload folder if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Register blueprints
    from app.modules.auth import auth_bp
    from app.modules.boutique import boutique_bp
    from app.modules.hardware import hardware_bp
    from app.modules.customers import customers_bp
    from app.modules.dashboard import dashboard_bp
    from app.modules.finance import finance_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(boutique_bp, url_prefix='/boutique')
    app.register_blueprint(hardware_bp, url_prefix='/hardware')
    app.register_blueprint(customers_bp, url_prefix='/customers')
    app.register_blueprint(finance_bp, url_prefix='/finance')

    # Make current user available in templates
    @app.context_processor
    def inject_user():
        from flask import session
        return {
            'current_user': session.get('username'),
            'current_section': session.get('section')
        }

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    return app
