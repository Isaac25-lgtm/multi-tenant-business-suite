from flask import Flask, jsonify
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

    # Configure CORS to allow all origins and headers for now to fix the issue
    CORS(app, resources={
        r"/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

    # JWT error handlers
    @jwt.invalid_token_loader
    def invalid_token_callback(error_string):
        return jsonify({'error': 'Invalid token', 'message': error_string}), 401

    @jwt.unauthorized_loader
    def unauthorized_callback(error_string):
        return jsonify({'error': 'Missing authorization token'}), 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({'error': 'Token has expired'}), 401

    # Create upload folder if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Register blueprints
    from app.modules.auth import auth_bp
    from app.modules.employees import employees_bp
    from app.modules.boutique import boutique_bp
    from app.modules.hardware import hardware_bp
    from app.modules.customers import customers_bp
    from app.modules.dashboard import dashboard_bp
    from app.modules.finance import finance_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(employees_bp, url_prefix='/api/employees')
    app.register_blueprint(boutique_bp, url_prefix='/api/boutique')
    app.register_blueprint(hardware_bp, url_prefix='/api/hardware')
    app.register_blueprint(customers_bp, url_prefix='/api/customers')
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
    app.register_blueprint(finance_bp, url_prefix='/api/finance')
    
    return app
