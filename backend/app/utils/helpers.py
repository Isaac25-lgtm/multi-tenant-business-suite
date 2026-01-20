from functools import wraps
from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity
from app.models.user import User
from app.models.audit import AuditLog
from app.extensions import db
from datetime import datetime, date, timedelta


def manager_required(f):
    """Decorator to require manager role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        if not user or user.role != 'manager':
            return jsonify({'error': 'Manager access required'}), 403
        return f(*args, **kwargs)
    return decorated_function


def business_access_required(business_type):
    """Decorator to check if user has access to specific business"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = int(get_jwt_identity())
            user = User.query.get(user_id)
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            # Manager has access to all businesses
            if user.role == 'manager' or user.assigned_business == 'all':
                return f(*args, **kwargs)
            
            # Check if employee has access to this business
            if user.assigned_business != business_type:
                return jsonify({'error': 'Access denied to this business'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_date_filter_for_user(user):
    """Get date filter based on user role and permissions"""
    if user.role == 'manager':
        # Manager can see all dates
        return None
    
    # Employees can only see today and yesterday
    today = date.today()
    yesterday = today - timedelta(days=1)
    return [today, yesterday]


def validate_date_for_user(user, target_date):
    """Validate if user can create/edit records for the target date"""
    if user.role == 'manager':
        return True, None
    
    today = date.today()
    yesterday = today - timedelta(days=1)
    
    # Check if date is within allowed range
    days_diff = (today - target_date).days
    
    if days_diff < 0:
        return False, "Cannot create entries for future dates"
    
    if days_diff == 0:  # Today
        return True, None
    
    if days_diff <= user.backdate_limit:
        return True, None
    
    return False, f"You can only backdate up to {user.backdate_limit} day(s)"


def log_audit(user_id, action, module, entity_type, entity_id, description, 
              old_values=None, new_values=None, is_flagged=False, flag_reason=None):
    """Create an audit log entry"""
    try:
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            module=module,
            entity_type=entity_type,
            entity_id=entity_id,
            old_values=old_values,
            new_values=new_values,
            description=description,
            ip_address=request.remote_addr if request else None,
            is_flagged=is_flagged,
            flag_reason=flag_reason
        )
        db.session.add(audit_log)
        db.session.commit()
    except Exception as e:
        print(f"Error logging audit: {str(e)}")
        db.session.rollback()


def format_currency(amount):
    """Format amount as UGX with thousand separators"""
    return f"UGX {amount:,.0f}"


def generate_reference_number(prefix, model_class):
    """Generate unique reference number"""
    # Get the last reference number
    last_record = model_class.query.filter(
        model_class.reference_number.like(f'{prefix}%')
    ).order_by(model_class.id.desc()).first()
    
    if last_record and last_record.reference_number:
        last_number = int(last_record.reference_number.split('-')[-1])
        new_number = last_number + 1
    else:
        new_number = 1
    
    return f"{prefix}{new_number:05d}"
