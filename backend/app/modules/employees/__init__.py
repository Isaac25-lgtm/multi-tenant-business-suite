from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.extensions import db
from app.utils.helpers import manager_required, log_audit

employees_bp = Blueprint('employees', __name__)


@employees_bp.route('', methods=['GET'])
@jwt_required()
@manager_required
def get_employees():
    """Get all employees (Manager only)"""
    employees = User.query.filter_by(role='employee').all()
    return jsonify({
        'employees': [emp.to_dict() for emp in employees]
    }), 200


@employees_bp.route('', methods=['POST'])
@jwt_required()
@manager_required
def create_employee():
    """Create new employee (Manager only)"""
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['username', 'password', 'name', 'assigned_business']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400
    
    # Check if username already exists
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 400
    
    # Create new employee
    employee = User(
        username=data['username'],
        name=data['name'],
        role='employee',
        assigned_business=data['assigned_business'],
        can_backdate=data.get('can_backdate', False),
        backdate_limit=data.get('backdate_limit', 1),
        can_edit=data.get('can_edit', True),
        can_delete=data.get('can_delete', True),
        can_clear_credits=data.get('can_clear_credits', True),
        is_active=True
    )
    employee.set_password(data['password'])
    
    db.session.add(employee)
    db.session.commit()
    
    # Log the action
    user_id = int(get_jwt_identity())
    log_audit(
        user_id=user_id,
        action='create',
        module='settings',
        entity_type='employee',
        entity_id=employee.id,
        description=f"Created employee {employee.name}",
        new_values=employee.to_dict()
    )
    
    return jsonify({
        'message': 'Employee created successfully',
        'employee': employee.to_dict()
    }), 201


@employees_bp.route('/<int:id>', methods=['GET'])
@jwt_required()
@manager_required
def get_employee(id):
    """Get employee details (Manager only)"""
    employee = User.query.get(id)
    
    if not employee or employee.role != 'employee':
        return jsonify({'error': 'Employee not found'}), 404
    
    return jsonify({'employee': employee.to_dict()}), 200


@employees_bp.route('/<int:id>', methods=['PUT'])
@jwt_required()
@manager_required
def update_employee(id):
    """Update employee (Manager only)"""
    employee = User.query.get(id)
    
    if not employee or employee.role != 'employee':
        return jsonify({'error': 'Employee not found'}), 404
    
    data = request.get_json()
    old_values = employee.to_dict()
    
    # Update allowed fields
    if 'name' in data:
        employee.name = data['name']
    if 'assigned_business' in data:
        employee.assigned_business = data['assigned_business']
    if 'can_backdate' in data:
        employee.can_backdate = data['can_backdate']
    if 'backdate_limit' in data:
        employee.backdate_limit = data['backdate_limit']
    if 'can_edit' in data:
        employee.can_edit = data['can_edit']
    if 'can_delete' in data:
        employee.can_delete = data['can_delete']
    if 'can_clear_credits' in data:
        employee.can_clear_credits = data['can_clear_credits']
    if 'is_active' in data:
        employee.is_active = data['is_active']
    
    # Update password if provided
    if data.get('password'):
        employee.set_password(data['password'])
    
    db.session.commit()
    
    # Log the action
    user_id = int(get_jwt_identity())
    log_audit(
        user_id=user_id,
        action='update',
        module='settings',
        entity_type='employee',
        entity_id=employee.id,
        description=f"Updated employee {employee.name}",
        old_values=old_values,
        new_values=employee.to_dict()
    )
    
    return jsonify({
        'message': 'Employee updated successfully',
        'employee': employee.to_dict()
    }), 200


@employees_bp.route('/<int:id>', methods=['DELETE'])
@jwt_required()
@manager_required
def deactivate_employee(id):
    """Deactivate employee (Manager only)"""
    employee = User.query.get(id)
    
    if not employee or employee.role != 'employee':
        return jsonify({'error': 'Employee not found'}), 404
    
    employee.is_active = False
    db.session.commit()
    
    # Log the action
    user_id = int(get_jwt_identity())
    log_audit(
        user_id=user_id,
        action='delete',
        module='settings',
        entity_type='employee',
        entity_id=employee.id,
        description=f"Deactivated employee {employee.name}"
    )
    
    return jsonify({'message': 'Employee deactivated successfully'}), 200


@employees_bp.route('/<int:id>/permissions', methods=['PUT'])
@jwt_required()
@manager_required
def update_permissions(id):
    """Update employee permissions (Manager only)"""
    employee = User.query.get(id)
    
    if not employee or employee.role != 'employee':
        return jsonify({'error': 'Employee not found'}), 404
    
    data = request.get_json()
    
    employee.can_backdate = data.get('can_backdate', employee.can_backdate)
    employee.backdate_limit = data.get('backdate_limit', employee.backdate_limit)
    employee.can_edit = data.get('can_edit', employee.can_edit)
    employee.can_delete = data.get('can_delete', employee.can_delete)
    employee.can_clear_credits = data.get('can_clear_credits', employee.can_clear_credits)
    
    db.session.commit()
    
    # Log the action
    user_id = int(get_jwt_identity())
    log_audit(
        user_id=user_id,
        action='update',
        module='settings',
        entity_type='employee',
        entity_id=employee.id,
        description=f"Updated permissions for {employee.name}"
    )
    
    return jsonify({
        'message': 'Permissions updated successfully',
        'employee': employee.to_dict()
    }), 200
