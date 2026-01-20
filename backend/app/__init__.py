from flask import Flask
from flask_cors import CORS
from app.extensions import db, jwt, migrate
from app.config import Config
import os


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    CORS(app)
    
    # Create upload folder if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Register blueprints
    from app.modules.auth import auth_bp
    from app.modules.employees import employees_bp
    from app.modules.boutique import boutique_bp
    from app.modules.hardware import hardware_bp
    from app.modules.customers import customers_bp
    from app.modules.dashboard import dashboard_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(employees_bp, url_prefix='/api/employees')
    app.register_blueprint(boutique_bp, url_prefix='/api/boutique')
    app.register_blueprint(hardware_bp, url_prefix='/api/hardware')
    app.register_blueprint(customers_bp, url_prefix='/api/customers')
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
    
    return app
