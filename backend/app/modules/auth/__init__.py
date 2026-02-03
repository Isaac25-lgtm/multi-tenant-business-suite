from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.models.user import User, AuditLog
from app.extensions import db
from app.utils.timezone import get_local_now
from functools import wraps
import json

auth_bp = Blueprint('auth', __name__)


def log_action(username, section, action, entity, entity_id=None, details=None):
    """Log an action to the audit trail"""
    log = AuditLog(
        username=username,
        section=section,
        action=action,
        entity=entity,
        entity_id=entity_id,
        details=json.dumps(details) if details else None,
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()


def get_current_user():
    """Get the current logged in user from session"""
    return session.get('username')


def get_current_section():
    """Get the current section from session"""
    return session.get('section')


def login_required(section):
    """Decorator to require login for a specific section"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'username' not in session:
                flash('Please login to access this section', 'error')
                return redirect(url_for('auth.login', section=section))

            # TESTING MODE: Allow any logged-in user to access any section
            # user_section = session.get('section')
            # if user_section != 'manager' and user_section != section:
            #     flash(f'You do not have access to the {section} section', 'error')
            #     return redirect(url_for('auth.login', section=section))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def manager_required(f):
    """Decorator to require manager access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please login as manager', 'error')
            return redirect(url_for('auth.login', section='manager'))

        # TESTING MODE: Allow any logged-in user to access manager features
        # if session.get('section') != 'manager':
        #     flash('Manager access required', 'error')
        #     user_section = session.get('section')
        #     if user_section == 'boutique':
        #         return redirect(url_for('boutique.index'))
        #     elif user_section == 'hardware':
        #         return redirect(url_for('hardware.index'))
        #     elif user_section == 'finance':
        #         return redirect(url_for('finance.index'))
        #     return redirect(url_for('auth.login', section='manager'))

        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route('/login')
@auth_bp.route('/login/<section>')
def login(section='boutique'):
    """Show login page for a section with existing accounts"""
    if section not in ['manager', 'boutique', 'hardware', 'finance']:
        section = 'boutique'

    # TESTING MODE: Show ALL users (including deactivated) regardless of section
    existing_users = User.query.order_by(User.full_name).all()

    return render_template('auth/login.html', section=section, existing_users=existing_users)


@auth_bp.route('/login/<section>', methods=['POST'])
def do_login(section='boutique'):
    """Process login with password verification"""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    user_id = request.form.get('user_id', type=int)

    # If user_id provided, get user directly
    if user_id:
        user = User.query.get(user_id)
        if user:
            username = user.username
    else:
        # Check if username exists
        user = User.query.filter_by(username=username).first()

    if not user:
        # For backwards compatibility, allow creating new users
        # But only if it's not a password-protected system
        if username:
            user = User(username=username, role=section)
            db.session.add(user)
        else:
            flash('Please select an account or enter a username', 'error')
            return redirect(url_for('auth.login', section=section))

    # TESTING MODE: Skip active check - allow deactivated accounts to login
    # if not user.is_active:
    #     flash('This account has been deactivated. Contact your manager.', 'error')
    #     return redirect(url_for('auth.login', section=section))

    # Verify password if user has one set
    if user.password_hash:
        if not user.check_password(password):
            flash('Incorrect password', 'error')
            return redirect(url_for('auth.login', section=section))

    # TESTING MODE: Skip section access check - allow any account to access any section
    # if not user.has_access_to(section):
    #     flash(f'You do not have access to the {section} section', 'error')
    #     return redirect(url_for('auth.login', section=section))

    user.last_login = get_local_now()
    db.session.commit()

    # Set session
    session['username'] = user.username
    session['section'] = section
    session['user_id'] = user.id

    # Log the login
    log_action(user.username, section, 'login', 'session')

    flash(f'Welcome, {user.full_name or user.username}!', 'success')

    # Redirect to appropriate section
    if section == 'manager':
        return redirect(url_for('dashboard.index'))
    elif section == 'boutique':
        return redirect(url_for('boutique.index'))
    elif section == 'hardware':
        return redirect(url_for('hardware.index'))
    elif section == 'finance':
        return redirect(url_for('finance.index'))

    return redirect(url_for('dashboard.index'))


@auth_bp.route('/logout')
def logout():
    """Logout and clear session"""
    username = session.get('username', 'unknown')
    section = session.get('section', 'unknown')

    if username != 'unknown':
        log_action(username, section, 'logout', 'session')

    session.clear()
    flash('You have been logged out', 'success')
    return redirect(url_for('auth.login'))
