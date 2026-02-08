from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from app.models.boutique import BoutiqueSale, BoutiqueStock, BoutiqueSaleItem
from app.models.hardware import HardwareSale, HardwareStock, HardwareSaleItem
from app.models.finance import Loan, GroupLoan, LoanPayment, GroupLoanPayment
from app.models.user import User, AuditLog
from app.modules.auth import manager_required, log_action
from app.extensions import db
from datetime import timedelta
from app.utils.timezone import get_local_today
from sqlalchemy import func
from werkzeug.utils import secure_filename
import os

dashboard_bp = Blueprint('dashboard', __name__)

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def allowed_image(filename):
    """Check if file is an allowed image type"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


@dashboard_bp.route('/')
@manager_required
def index():
    """Unified dashboard view"""
    today = get_local_today()
    yesterday = today - timedelta(days=1)

    # ============ BOUTIQUE STATS ============
    boutique_today_query = db.session.query(
        func.sum(BoutiqueSale.amount_paid),
        func.count(BoutiqueSale.id)
    ).filter(
        BoutiqueSale.sale_date == today,
        BoutiqueSale.is_deleted == False
    ).first()
    boutique_today = float(boutique_today_query[0] or 0)
    boutique_today_count = boutique_today_query[1] or 0

    boutique_yesterday = float(db.session.query(
        func.sum(BoutiqueSale.amount_paid)
    ).filter(
        BoutiqueSale.sale_date == yesterday,
        BoutiqueSale.is_deleted == False
    ).scalar() or 0)

    boutique_credits = float(db.session.query(
        func.sum(BoutiqueSale.balance)
    ).filter(
        BoutiqueSale.is_credit_cleared == False,
        BoutiqueSale.payment_type == 'part',
        BoutiqueSale.is_deleted == False
    ).scalar() or 0)

    boutique_low_stock = BoutiqueStock.query.filter(
        BoutiqueStock.is_active == True,
        BoutiqueStock.quantity <= BoutiqueStock.low_stock_threshold
    ).count()

    # ============ HARDWARE STATS ============
    hardware_today_query = db.session.query(
        func.sum(HardwareSale.amount_paid),
        func.count(HardwareSale.id)
    ).filter(
        HardwareSale.sale_date == today,
        HardwareSale.is_deleted == False
    ).first()
    hardware_today = float(hardware_today_query[0] or 0)
    hardware_today_count = hardware_today_query[1] or 0

    hardware_yesterday = float(db.session.query(
        func.sum(HardwareSale.amount_paid)
    ).filter(
        HardwareSale.sale_date == yesterday,
        HardwareSale.is_deleted == False
    ).scalar() or 0)

    hardware_credits = float(db.session.query(
        func.sum(HardwareSale.balance)
    ).filter(
        HardwareSale.is_credit_cleared == False,
        HardwareSale.payment_type == 'part',
        HardwareSale.is_deleted == False
    ).scalar() or 0)

    hardware_low_stock = HardwareStock.query.filter(
        HardwareStock.is_active == True,
        HardwareStock.quantity <= HardwareStock.low_stock_threshold
    ).count()

    # ============ FINANCE STATS ============
    today_repayments = float(db.session.query(func.sum(LoanPayment.amount)).filter(
        LoanPayment.payment_date == today,
        LoanPayment.is_deleted == False
    ).scalar() or 0)

    today_group_repayments = float(db.session.query(func.sum(GroupLoanPayment.amount)).filter(
        GroupLoanPayment.payment_date == today,
        GroupLoanPayment.is_deleted == False
    ).scalar() or 0)

    active_loans_balance = float(db.session.query(func.sum(Loan.balance)).filter(
        Loan.is_deleted == False,
        Loan.balance > 0
    ).scalar() or 0)

    active_group_balance = float(db.session.query(func.sum(GroupLoan.balance)).filter(
        GroupLoan.is_deleted == False,
        GroupLoan.balance > 0
    ).scalar() or 0)

    overdue_loans_count = Loan.query.filter(
        Loan.is_deleted == False,
        Loan.status == 'overdue'
    ).count()

    overdue_groups_count = GroupLoan.query.filter(
        GroupLoan.is_deleted == False,
        GroupLoan.status == 'overdue'
    ).count()

    # ============ INVENTORY VALUE (COST) ============
    boutique_inventory_value = float(db.session.query(
        func.sum(BoutiqueStock.cost_price * BoutiqueStock.quantity)
    ).filter(
        BoutiqueStock.is_active == True
    ).scalar() or 0)

    hardware_inventory_value = float(db.session.query(
        func.sum(HardwareStock.cost_price * HardwareStock.quantity)
    ).filter(
        HardwareStock.is_active == True
    ).scalar() or 0)

    total_inventory_value = boutique_inventory_value + hardware_inventory_value

    # ============ PROFIT (TODAY) ============
    boutique_profit_today = float(db.session.query(
        func.sum(
            (BoutiqueSaleItem.unit_price - func.coalesce(BoutiqueStock.cost_price, 0)) *
            BoutiqueSaleItem.quantity
        )
    ).join(
        BoutiqueSale, BoutiqueSaleItem.sale_id == BoutiqueSale.id
    ).outerjoin(
        BoutiqueStock, BoutiqueSaleItem.stock_id == BoutiqueStock.id
    ).filter(
        BoutiqueSale.sale_date == today,
        BoutiqueSale.is_deleted == False
    ).scalar() or 0)

    hardware_profit_today = float(db.session.query(
        func.sum(
            (HardwareSaleItem.unit_price - func.coalesce(HardwareStock.cost_price, 0)) *
            HardwareSaleItem.quantity
        )
    ).join(
        HardwareSale, HardwareSaleItem.sale_id == HardwareSale.id
    ).outerjoin(
        HardwareStock, HardwareSaleItem.stock_id == HardwareStock.id
    ).filter(
        HardwareSale.sale_date == today,
        HardwareSale.is_deleted == False
    ).scalar() or 0)

    total_profit_today = boutique_profit_today + hardware_profit_today

    # ============ TOTALS ============
    total_today = boutique_today + hardware_today + today_repayments + today_group_repayments
    total_yesterday = boutique_yesterday + hardware_yesterday
    total_credits = boutique_credits + hardware_credits
    total_outstanding_loans = active_loans_balance + active_group_balance
    total_low_stock = boutique_low_stock + hardware_low_stock
    total_transactions = boutique_today_count + hardware_today_count

    # ============ SALES TREND (LAST 7 DAYS) ============
    sales_trend = []
    for i in range(6, -1, -1):
        target_date = today - timedelta(days=i)

        daily_boutique = float(db.session.query(
            func.sum(BoutiqueSale.amount_paid)
        ).filter(
            BoutiqueSale.sale_date == target_date,
            BoutiqueSale.is_deleted == False
        ).scalar() or 0)

        daily_hardware = float(db.session.query(
            func.sum(HardwareSale.amount_paid)
        ).filter(
            HardwareSale.sale_date == target_date,
            HardwareSale.is_deleted == False
        ).scalar() or 0)

        daily_finance = float(db.session.query(
            func.sum(LoanPayment.amount)
        ).filter(
            LoanPayment.payment_date == target_date,
            LoanPayment.is_deleted == False
        ).scalar() or 0)

        daily_group_finance = float(db.session.query(
            func.sum(GroupLoanPayment.amount)
        ).filter(
            GroupLoanPayment.payment_date == target_date,
            GroupLoanPayment.is_deleted == False
        ).scalar() or 0)

        sales_trend.append({
            'date': target_date.strftime('%a'),
            'boutique': daily_boutique,
            'hardware': daily_hardware,
            'finance': daily_finance + daily_group_finance,
            'total': daily_boutique + daily_hardware + daily_finance + daily_group_finance
        })

    # ============ LOW STOCK ALERTS ============
    low_stock_items = []

    boutique_low = BoutiqueStock.query.filter(
        BoutiqueStock.is_active == True,
        BoutiqueStock.quantity <= BoutiqueStock.low_stock_threshold
    ).limit(5).all()
    for item in boutique_low:
        low_stock_items.append({
            'business': 'Boutique',
            'item': item.item_name,
            'quantity': item.quantity,
            'unit': item.unit
        })

    hardware_low = HardwareStock.query.filter(
        HardwareStock.is_active == True,
        HardwareStock.quantity <= HardwareStock.low_stock_threshold
    ).limit(5).all()
    for item in hardware_low:
        low_stock_items.append({
            'business': 'Hardware',
            'item': item.item_name,
            'quantity': item.quantity,
            'unit': item.unit
        })

    return render_template('dashboard.html',
        today=today,
        stats={
            'today_revenue': total_today,
            'yesterday_revenue': total_yesterday,
            'credits_outstanding': total_credits,
            'loans_outstanding': total_outstanding_loans,
            'low_stock_alerts': total_low_stock,
            'transactions_today': total_transactions,
            'overdue_loans': overdue_loans_count + overdue_groups_count,
            'inventory_value': total_inventory_value,
            'profit_today': total_profit_today
        },
        by_business={
            'boutique': {
                'today': boutique_today,
                'yesterday': boutique_yesterday,
                'credits': boutique_credits,
                'transactions': boutique_today_count,
                'low_stock': boutique_low_stock,
                'inventory_value': boutique_inventory_value,
                'profit_today': boutique_profit_today
            },
            'hardware': {
                'today': hardware_today,
                'yesterday': hardware_yesterday,
                'credits': hardware_credits,
                'transactions': hardware_today_count,
                'low_stock': hardware_low_stock,
                'inventory_value': hardware_inventory_value,
                'profit_today': hardware_profit_today
            },
            'finance': {
                'outstanding': total_outstanding_loans,
                'repayments_today': today_repayments + today_group_repayments,
                'overdue_count': overdue_loans_count + overdue_groups_count
            }
        },
        sales_trend=sales_trend,
        low_stock_items=low_stock_items
    )


@dashboard_bp.route('/audit-trail')
@manager_required
def audit_trail():
    """View audit trail - manager only"""
    # Get filter parameters
    username_filter = request.args.get('username', '')
    section_filter = request.args.get('section', '')
    action_filter = request.args.get('action', '')
    page = request.args.get('page', 1, type=int)
    per_page = 50

    # Build query
    query = AuditLog.query

    if username_filter:
        query = query.filter(AuditLog.username.ilike(f'%{username_filter}%'))
    if section_filter:
        query = query.filter(AuditLog.section == section_filter)
    if action_filter:
        query = query.filter(AuditLog.action == action_filter)

    # Order by most recent first
    query = query.order_by(AuditLog.created_at.desc())

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    logs = pagination.items

    # Get unique values for filters
    sections = db.session.query(AuditLog.section).distinct().all()
    sections = [s[0] for s in sections]

    actions = db.session.query(AuditLog.action).distinct().all()
    actions = [a[0] for a in actions]

    usernames = db.session.query(AuditLog.username).distinct().all()
    usernames = [u[0] for u in usernames]

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

        # Set password if provided
        if password:
            user.set_password(password)

        # Handle profile picture upload
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename and allowed_image(file.filename):
                filename = secure_filename(file.filename)
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'profiles')
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, f'user_{username}_{filename}')
                file.save(file_path)
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

        # Update password if provided
        password = request.form.get('password', '').strip()
        if password:
            user.set_password(password)

        # Handle profile picture upload
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename and allowed_image(file.filename):
                filename = secure_filename(file.filename)
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'profiles')
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, f'user_{user.username}_{filename}')
                file.save(file_path)
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
