from flask import Blueprint, render_template, request
from app.models.boutique import BoutiqueSale, BoutiqueStock
from app.models.hardware import HardwareSale, HardwareStock
from app.models.finance import Loan, GroupLoan, LoanPayment, GroupLoanPayment
from app.models.user import AuditLog
from app.modules.auth import manager_required
from app.extensions import db
from datetime import date, timedelta
from sqlalchemy import func

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@manager_required
def index():
    """Unified dashboard view"""
    today = date.today()
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
            'overdue_loans': overdue_loans_count + overdue_groups_count
        },
        by_business={
            'boutique': {
                'today': boutique_today,
                'yesterday': boutique_yesterday,
                'credits': boutique_credits,
                'transactions': boutique_today_count,
                'low_stock': boutique_low_stock
            },
            'hardware': {
                'today': hardware_today,
                'yesterday': hardware_yesterday,
                'credits': hardware_credits,
                'transactions': hardware_today_count,
                'low_stock': hardware_low_stock
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
