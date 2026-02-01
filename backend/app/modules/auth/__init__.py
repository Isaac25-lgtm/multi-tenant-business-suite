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

            # Check if user has access to this section
            user_section = session.get('section')
            if user_section != 'manager' and user_section != section:
                flash(f'You do not have access to the {section} section', 'error')
                return redirect(url_for('auth.login', section=section))

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

        if session.get('section') != 'manager':
            flash('Manager access required', 'error')
            # Redirect to their own section, not dashboard (to avoid loop)
            user_section = session.get('section')
            if user_section == 'boutique':
                return redirect(url_for('boutique.index'))
            elif user_section == 'hardware':
                return redirect(url_for('hardware.index'))
            elif user_section == 'finance':
                return redirect(url_for('finance.index'))
            # If unknown section, send to login
            return redirect(url_for('auth.login', section='manager'))

        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route('/login')
@auth_bp.route('/login/<section>')
def login(section='boutique'):
    """Show login page for a section"""
    if section not in ['manager', 'boutique', 'hardware', 'finance']:
        section = 'boutique'
    return render_template('auth/login.html', section=section)


@auth_bp.route('/login/<section>', methods=['POST'])
def do_login(section='boutique'):
    """Process login - for now, any username works"""
    username = request.form.get('username', '').strip()

    if not username:
        flash('Username is required', 'error')
        return redirect(url_for('auth.login', section=section))

    # Create user if doesn't exist
    user = User.query.filter_by(username=username).first()
    if not user:
        user = User(username=username, role=section)
        db.session.add(user)

    user.last_login = get_local_now()
    db.session.commit()

    # Set session
    session['username'] = username
    session['section'] = section
    session['user_id'] = user.id

    # Log the login
    log_action(username, section, 'login', 'session')

    flash(f'Welcome, {username}!', 'success')

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
