from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity
)
from app.models.user import User
from app.utils.helpers import log_audit
from app.extensions import db

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    """User login endpoint"""
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Username and password required'}), 400
    
    username = data.get('username')
    password = data.get('password')
    assigned_business = data.get('assigned_business')  # Optional for employees
    
    # Find user
    user = User.query.filter_by(username=username).first()
    
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid username or password'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Account is deactivated'}), 403
    
    # For employees, validate business assignment
    if user.role == 'employee' and assigned_business:
        if user.assigned_business != assigned_business and user.assigned_business != 'all':
            return jsonify({'error': 'You do not have access to this business'}), 403
    
    # Generate tokens (identity must be a string)
    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))
    
    # Log the login
    log_audit(
        user_id=user.id,
        action='login',
        module='auth',
        entity_type='user',
        entity_id=user.id,
        description=f"{user.name} logged in"
    )
    
    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user.to_dict()
    }), 200


@auth_bp.route('/demo-login', methods=['POST'])
def demo_login():
    """One-click demo login - bypasses password for demo users"""
    data = request.get_json()

    if not data or not data.get('role'):
        return jsonify({'error': 'Role parameter required'}), 400

    role = data.get('role').lower()

    # Map role to demo username
    demo_users = {
        'manager': 'manager',
        'boutique': 'sarah',
        'hardware': 'david',
        'finance': 'grace'  # Note: grace has 'finances' business
    }

    if role not in demo_users:
        return jsonify({'error': 'Invalid role'}), 400

    username = demo_users[role]

    # Find user directly by username (skip password check for demo)
    user = User.query.filter_by(username=username).first()

    if not user:
        return jsonify({'error': 'Demo user not found'}), 404

    if not user.is_active:
        return jsonify({'error': 'Account is deactivated'}), 403

    # Generate tokens (same as regular login)
    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    # Log the demo login
    log_audit(
        user_id=user.id,
        action='login',
        module='auth',
        entity_type='user',
        entity_id=user.id,
        description=f"{user.name} logged in (demo mode)"
    )

    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user.to_dict()
    }), 200


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """User logout endpoint"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if user:
        log_audit(
            user_id=user.id,
            action='logout',
            module='auth',
            entity_type='user',
            entity_id=user.id,
            description=f"{user.name} logged out"
        )
    
    return jsonify({'message': 'Successfully logged out'}), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current user profile"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({'user': user.to_dict()}), 200


@auth_bp.route('/change-password', methods=['PUT'])
@jwt_required()
def change_password():
    """Change user password"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.get_json()
    old_password = data.get('old_password')
    new_password = data.get('new_password')
    
    if not old_password or not new_password:
        return jsonify({'error': 'Old and new passwords required'}), 400
    
    if not user.check_password(old_password):
        return jsonify({'error': 'Current password is incorrect'}), 401
    
    if len(new_password) < 6:
        return jsonify({'error': 'New password must be at least 6 characters'}), 400
    
    user.set_password(new_password)
    db.session.commit()
    
    log_audit(
        user_id=user.id,
        action='update',
        module='auth',
        entity_type='user',
        entity_id=user.id,
        description=f"{user.name} changed password"
    )
    
    return jsonify({'message': 'Password changed successfully'}), 200


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token"""
    user_id = int(get_jwt_identity())
    access_token = create_access_token(identity=user_id)
    return jsonify({'access_token': access_token}), 200
