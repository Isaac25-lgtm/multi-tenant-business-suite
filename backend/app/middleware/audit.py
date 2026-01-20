from flask import request
from flask_jwt_extended import get_jwt_identity
from app.models.user import User
from app.utils.helpers import log_audit
from functools import wraps


def audit_middleware(action, module, entity_type):
    """Middleware decorator to automatically log actions"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Execute the function first
            result = f(*args, **kwargs)
            
            # Get user ID from JWT
            try:
                user_id = int(get_jwt_identity())
                if user_id:
                    # Extract entity ID from kwargs or result
                    entity_id = kwargs.get('id', 0)
                    
                    # Create description
                    user = User.query.get(user_id)
                    description = f"{user.name if user else 'Unknown'} {action}d {entity_type}"
                    
                    # Log the audit
                    log_audit(
                        user_id=user_id,
                        action=action,
                        module=module,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        description=description
                    )
            except Exception as e:
                print(f"Audit middleware error: {str(e)}")
            
            return result
        return decorated_function
    return decorator
