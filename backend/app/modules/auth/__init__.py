from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.models.user import User, AuditLog
from app.extensions import db
from app.utils.rate_limit import consume_limit, clear_limit
from app.utils.timezone import get_local_now
from functools import wraps
from urllib.parse import urlparse
import json

auth_bp = Blueprint('auth', __name__)
LOGIN_ATTEMPT_LIMIT = 5
LOGIN_WINDOW_SECONDS = 300
LOGIN_BLOCK_SECONDS = 900


def log_action(username, section, action, entity, entity_id=None, details=None):
    """Log an action to the audit trail. Never crashes the app."""
    try:
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
    except Exception:
        db.session.rollback()


def get_session_user():
    """Load the current logged-in user from DB using session user_id.
    Returns User or None. This is the single source of truth for auth checks."""
    user_id = session.get('user_id')
    if not user_id:
        return None
    return db.session.get(User, user_id)


def get_current_user():
    """Get the current logged in username from session"""
    return session.get('username')


def get_current_section():
    """Get the current section from session"""
    return session.get('section')


def _client_ip():
    forwarded_for = request.headers.get('X-Forwarded-For', '')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.remote_addr or 'unknown'


def _login_rate_identifier(username):
    normalized_username = (username or '').strip().lower() or 'unknown'
    return f'{_client_ip()}:{normalized_username}'


def _get_home_redirect(user):
    """Redirect user to their primary section"""
    if user.role == 'manager':
        return url_for('dashboard.index')
    if user.role == 'boutique':
        return url_for('boutique.index')
    if user.role == 'hardware':
        return url_for('hardware.index')
    if user.role == 'finance':
        return url_for('finance.index')
    return url_for('auth.login')


def _safe_next_url():
    """Build a safe next URL preserving the full path + query string."""
    full = request.full_path.rstrip('?')  # full_path adds trailing ? even without query
    return full if full.startswith('/') else request.path


def _get_login_users(section=None):
    """Return active accounts visible in the chosen portal."""
    query = User.query.filter_by(is_active=True).order_by(User.full_name.asc(), User.username.asc())
    users = query.all()
    if not section:
        return users
    return [user for user in users if user.has_access_to(section)]


def login_required(section):
    """Decorator to require login for a specific section.
    Loads user from DB, verifies active status and section access.
    For cross-cutting sections like 'customers', redirects to neutral /auth/login."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_session_user()

            # Sections with their own portal get directed there;
            # shared modules (customers, etc.) go to neutral /auth/login
            is_portal_section = section in ('manager', 'boutique', 'hardware', 'finance')
            next_url = _safe_next_url()

            if not user:
                session.clear()
                flash('Please login to access this section', 'error')
                if is_portal_section:
                    return redirect(url_for('auth.login', section=section, next=next_url))
                return redirect(url_for('auth.login', next=next_url))

            if not user.is_active:
                session.clear()
                flash('Your account is inactive. Contact your manager.', 'error')
                if is_portal_section:
                    return redirect(url_for('auth.login', section=section, next=next_url))
                return redirect(url_for('auth.login', next=next_url))

            if not user.has_access_to(section):
                flash(f'You do not have access to the {section} section', 'error')
                return redirect(_get_home_redirect(user))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def manager_required(f):
    """Decorator to require manager access.
    Loads user from DB, verifies active status and role == 'manager'."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_session_user()

        if not user:
            session.clear()
            flash('Please login as manager', 'error')
            return redirect(url_for('auth.login', section='manager'))

        if not user.is_active:
            session.clear()
            flash('Your account is inactive. Contact your manager.', 'error')
            return redirect(url_for('auth.login', section='manager'))

        if user.role != 'manager':
            flash('Manager access required', 'error')
            return redirect(_get_home_redirect(user))

        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route('/login')
@auth_bp.route('/login/<section>')
def login(section=None):
    """Show login page. Section-specific portals for boutique/hardware/finance/manager.
    Neutral login (section=None) for shared modules like customers."""
    if section and section not in ('manager', 'boutique', 'hardware', 'finance'):
        section = None

    selected_username = request.args.get('username', '').strip()
    return render_template(
        'auth/login.html',
        section=section,
        login_users=_get_login_users(section),
        selected_username=selected_username,
    )


@auth_bp.route('/login', methods=['POST'])
@auth_bp.route('/login/<section>', methods=['POST'])
def do_login(section=None):
    """Process login with password verification.
    Never creates accounts. Validates active status, password, and section access.
    If section is None (neutral login), derives section from user's DB role."""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    # Preserve next for redirect-back on error
    next_url = request.form.get('next', '')
    error_redirect_args = {'section': section} if section else {}
    if next_url:
        error_redirect_args['next'] = next_url
    if username:
        error_redirect_args['username'] = username

    if not username:
        flash('Please select your account', 'error')
        return redirect(url_for('auth.login', **error_redirect_args))

    allowed, retry_after = consume_limit(
        'auth_login',
        _login_rate_identifier(username),
        LOGIN_ATTEMPT_LIMIT,
        LOGIN_WINDOW_SECONDS,
        LOGIN_BLOCK_SECONDS,
    )
    if not allowed:
        wait_minutes = max((retry_after + 59) // 60, 1)
        flash(f'Too many login attempts. Try again in about {wait_minutes} minute(s).', 'error')
        return redirect(url_for('auth.login', **error_redirect_args))

    # Look up user by username — never auto-create
    user = User.query.filter_by(username=username).first()

    if not user:
        flash('Invalid username or password', 'error')
        return redirect(url_for('auth.login', **error_redirect_args))

    if not user.is_active:
        flash('This account has been deactivated. Contact your manager.', 'error')
        return redirect(url_for('auth.login', **error_redirect_args))

    # Verify password — always required
    if not user.password_hash:
        flash('This account has no password set. Contact your manager.', 'error')
        return redirect(url_for('auth.login', **error_redirect_args))

    if not user.check_password(password):
        flash('Invalid username or password', 'error')
        return redirect(url_for('auth.login', **error_redirect_args))

    # Determine effective section: use URL section if specified, else user's DB role
    effective_section = section if section else user.role

    # Verify section access from DB permissions (only for section-specific logins)
    if section and not user.has_access_to(section):
        flash(f'You do not have access to the {section} section', 'error')
        return redirect(url_for('auth.login', **error_redirect_args))

    # All checks passed — clear old session, set new one
    session.clear()
    user.last_login = get_local_now()
    db.session.commit()

    session['username'] = user.username
    session['section'] = effective_section
    session['user_id'] = user.id
    session.permanent = True
    clear_limit('auth_login', _login_rate_identifier(username))

    log_action(user.username, effective_section, 'login', 'session')

    flash(f'Welcome, {user.full_name or user.username}!', 'success')

    # Honor next parameter if it's a safe internal path
    if next_url:
        parsed = urlparse(next_url)
        if not parsed.scheme and not parsed.netloc and next_url.startswith('/'):
            return redirect(next_url)

    # Default: redirect to user's home section based on DB role
    return redirect(_get_home_redirect(user))


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Logout and clear session. POST-only to prevent CSRF logout attacks."""
    username = session.get('username', 'unknown')
    section = session.get('section', 'unknown')

    if username != 'unknown':
        log_action(username, section, 'logout', 'session')

    session.clear()
    flash('You have been logged out', 'success')
    return redirect(url_for('auth.login'))
