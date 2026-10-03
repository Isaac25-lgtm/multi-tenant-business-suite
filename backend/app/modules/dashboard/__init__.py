from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from app.models.user import User, AuditLog
from app.modules.auth import manager_required, log_action
from app.extensions import db
from app.utils.timezone import get_local_today
from werkzeug.utils import secure_filename
import os

dashboard_bp = Blueprint('dashboard', __name__)

from app.utils.uploads import allowed_image, validate_and_save_image


@dashboard_bp.route('/')
@manager_required
def index():
    """Manager dashboard. All figures come from app.services.business_metrics."""
    from app.services.business_metrics import manager_dashboard
    from app.services.loan_accounting import refresh_active_loans, refresh_open_group_loans

    today = get_local_today()
    try:
        refresh_active_loans()
        refresh_open_group_loans()
        metrics = manager_dashboard(today)
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Manager dashboard calculation failed')
        # Show an explicit "unavailable" state; never zeros that look like real figures.
        return render_template('dashboard.html', today=today, load_error=True, metrics=None)

    return render_template('dashboard.html', today=today, load_error=False, metrics=metrics)


@dashboard_bp.route('/summary')
@manager_required
def summary_fragment():
    """Dashboard figures only, for the in-page auto refresh (same service as the page)."""
    from app.services.business_metrics import manager_dashboard
    from app.services.loan_accounting import refresh_active_loans, refresh_open_group_loans

    today = get_local_today()
    try:
        refresh_active_loans()
        refresh_open_group_loans()
        metrics = manager_dashboard(today)
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Dashboard refresh failed')
        return render_template('dashboard/_content.html', today=today, load_error=True, metrics=None), 503
    return render_template('dashboard/_content.html', today=today, load_error=False, metrics=metrics)


def _analytics_page(template, builder):
    from app.services.periods import resolve_period

    today = get_local_today()
    period = resolve_period(request.args, today)
    try:
        data = builder(period, today)
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Analytics page failed: %s', template)
        return render_template(template, period=period, data=None, load_error=True, today=today)
    return render_template(template, period=period, data=data, load_error=False, today=today)


@dashboard_bp.route('/retail')
@manager_required
def retail_analytics():
    from app.services.analytics import retail_analytics as build

    unit = request.args.get('unit')
    branch = request.args.get('branch')
    return _analytics_page('analytics/retail.html', lambda period, today: build(period, unit, branch))


@dashboard_bp.route('/finance')
@manager_required
def finance_analytics():
    from app.services.analytics import finance_analytics as build
    from app.services.loan_accounting import refresh_active_loans, refresh_open_group_loans

    refresh_active_loans()
    refresh_open_group_loans()
    return _analytics_page('analytics/finance.html', build)


@dashboard_bp.route('/inventory')
@manager_required
def inventory_analytics():
    from app.services.analytics import inventory_analytics as build

    return _analytics_page('analytics/inventory.html', lambda period, today: build(period))


@dashboard_bp.route('/audit-trail')
@manager_required
def audit_trail():
    """View audit trail - manager only"""
    username_filter = request.args.get('username', '')
    section_filter = request.args.get('section', '')
    action_filter = request.args.get('action', '')
    page = request.args.get('page', 1, type=int)
    per_page = 50

    try:
        query = AuditLog.query
        if username_filter:
            query = query.filter(AuditLog.username.ilike(f'%{username_filter}%'))
        if section_filter:
            query = query.filter(AuditLog.section == section_filter)
        if action_filter:
            query = query.filter(AuditLog.action == action_filter)

        query = query.order_by(AuditLog.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        logs = pagination.items
        sections = [s[0] for s in db.session.query(AuditLog.section).distinct().all()]
        actions = [a[0] for a in db.session.query(AuditLog.action).distinct().all()]
        usernames = [u[0] for u in db.session.query(AuditLog.username).distinct().all()]
    except Exception:
        db.session.rollback()
        logs = []
        pagination = None
        sections = actions = usernames = []

    return render_template('audit_trail.html',
        logs=logs,
        pagination=pagination,
        sections=sections,
        actions=actions,
        usernames=usernames,
        filters={
            'username': username_filter,
            'section': section_filter,
            'action': action_filter
        }
    )


# ============ USER MANAGEMENT ============

@dashboard_bp.route('/users')
@manager_required
def users():
    """List all users"""
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template('users/list.html', users=all_users)


@dashboard_bp.route('/users/create', methods=['GET', 'POST'])
@manager_required
def create_user():
    """Create a new employee account"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        role = request.form.get('role', 'boutique')
        password = request.form.get('password', '').strip()
        boutique_branch = request.form.get('boutique_branch', '')

        # Access permissions
        can_access_boutique = 'can_access_boutique' in request.form
        can_access_hardware = 'can_access_hardware' in request.form
        can_access_finance = 'can_access_finance' in request.form
        can_access_customers = 'can_access_customers' in request.form

        if not username:
            flash('Username is required', 'error')
            return redirect(url_for('dashboard.create_user'))

        if not password:
            flash('A password is required for every account.', 'error')
            return redirect(url_for('dashboard.create_user'))

        # Check if username exists
        existing = User.query.filter_by(username=username).first()
        if existing:
            flash('Username already exists', 'error')
            return redirect(url_for('dashboard.create_user'))

        # Create user
        user = User(
            username=username,
            full_name=full_name or username,
            email=email or None,
            phone=phone or None,
            role=role,
            can_access_boutique=can_access_boutique,
            can_access_hardware=can_access_hardware,
            can_access_finance=can_access_finance,
            can_access_customers=can_access_customers,
            boutique_branch=boutique_branch if boutique_branch else None,
            created_by=session.get('user_id'),
            is_active=True
        )

        try:
            user.set_password(password)
        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(url_for('dashboard.create_user'))

        # Handle profile picture upload
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename and allowed_image(file.filename):
                filename = secure_filename(file.filename)
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'profiles')
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, f'user_{username}_{filename}')
                if validate_and_save_image(file, file_path):
                    user.profile_picture = f'uploads/profiles/user_{username}_{filename}'

        db.session.add(user)
        db.session.commit()

        log_action(session['username'], 'manager', 'create', 'user', user.id,
                   {'username': username, 'role': role, 'full_name': full_name})

        flash(f'User "{username}" created successfully', 'success')
        return redirect(url_for('dashboard.users'))

    return render_template('users/create.html')


@dashboard_bp.route('/users/<int:id>')
@manager_required
def view_user(id):
    """View user details"""
    user = User.query.get_or_404(id)
    # Get recent activity
    recent_logs = AuditLog.query.filter_by(username=user.username).order_by(
        AuditLog.created_at.desc()
    ).limit(20).all()
    return render_template('users/view.html', user=user, recent_logs=recent_logs)


@dashboard_bp.route('/users/<int:id>/edit', methods=['GET', 'POST'])
@manager_required
def edit_user(id):
    """Edit user account"""
    user = User.query.get_or_404(id)

    if request.method == 'POST':
        user.full_name = request.form.get('full_name', '').strip() or user.username
        user.email = request.form.get('email', '').strip() or None
        user.phone = request.form.get('phone', '').strip() or None
        user.role = request.form.get('role', user.role)
        user.boutique_branch = request.form.get('boutique_branch', '') or None
        user.is_active = 'is_active' in request.form

        # Access permissions
        user.can_access_boutique = 'can_access_boutique' in request.form
        user.can_access_hardware = 'can_access_hardware' in request.form
        user.can_access_finance = 'can_access_finance' in request.form
        user.can_access_customers = 'can_access_customers' in request.form

        password = request.form.get('password', '').strip()
        if not user.password_hash and not password:
            flash('This account has no password yet. Please set one now.', 'error')
            return redirect(url_for('dashboard.edit_user', id=id))
        if password:
            try:
                user.set_password(password)
            except ValueError as exc:
                flash(str(exc), 'error')
                return redirect(url_for('dashboard.edit_user', id=id))

        # Handle profile picture upload
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename and allowed_image(file.filename):
                filename = secure_filename(file.filename)
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'profiles')
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, f'user_{user.username}_{filename}')
                if validate_and_save_image(file, file_path):
                    user.profile_picture = f'uploads/profiles/user_{user.username}_{filename}'

        db.session.commit()

        log_action(session['username'], 'manager', 'update', 'user', user.id,
                   {'username': user.username, 'role': user.role})

        flash(f'User "{user.username}" updated successfully', 'success')
        return redirect(url_for('dashboard.view_user', id=id))

    return render_template('users/edit.html', user=user)


@dashboard_bp.route('/users/<int:id>/toggle-active', methods=['POST'])
@manager_required
def toggle_user_active(id):
    """Toggle user active status"""
    user = User.query.get_or_404(id)
    user.is_active = not user.is_active
    db.session.commit()

    status = 'activated' if user.is_active else 'deactivated'
    log_action(session['username'], 'manager', 'update', 'user', user.id,
               {'action': status, 'username': user.username})

    flash(f'User "{user.username}" has been {status}', 'success')
    return redirect(url_for('dashboard.users'))


@dashboard_bp.route('/users/<int:id>/delete', methods=['POST'])
@manager_required
def delete_user(id):
    """Delete user account"""
    user = User.query.get_or_404(id)

    # Don't allow deleting yourself
    if user.id == session.get('user_id'):
        flash('You cannot delete your own account', 'error')
        return redirect(url_for('dashboard.users'))

    username = user.username
    db.session.delete(user)
    db.session.commit()

    log_action(session['username'], 'manager', 'delete', 'user', id,
               {'username': username})

    flash(f'User "{username}" has been deleted', 'success')
    return redirect(url_for('dashboard.users'))
