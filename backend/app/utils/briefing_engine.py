"""Deterministic metrics engine for daily morning briefings.

Computes all metrics from the database — the AI layer is optional narration
on top.  If AI is unavailable, the briefing still renders with real numbers.
"""

import json
import logging
from datetime import datetime, time, timedelta

from sqlalchemy import func, or_

from app.extensions import db
from app.models.boutique import BoutiqueSale, BoutiqueStock, BoutiqueSaleItem
from app.models.hardware import HardwareSale, HardwareStock, HardwareSaleItem
from app.models.finance import Loan, GroupLoan, LoanPayment, GroupLoanPayment, LoanClient
from app.models.user import User, AuditLog
from app.models.website import WebsiteLoanInquiry, WebsiteOrderRequest
from app.models.ai import DailyBriefing
from app.utils.timezone import EAT_TIMEZONE, get_local_today

logger = logging.getLogger(__name__)


def _float(val):
    """Safely convert Decimal/None to float."""
    if val is None:
        return 0.0
    return float(val)


def _local_day_window(day):
    """Return timezone-aware start/end datetimes for a local business day."""
    start = datetime.combine(day, time.min, tzinfo=EAT_TIMEZONE)
    end = start + timedelta(days=1)
    return start, end


def _coerce_number(value, *, integer=False):
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0.0
    return int(number) if integer else number


def _coerce_list(value):
    return value if isinstance(value, list) else []


def sanitize_briefing_metrics(scope, metrics, branch=None, target_date=None):
    """Normalize cached or computed briefing metrics into a template-safe shape."""
    today = target_date or get_local_today()
    yesterday = today - timedelta(days=1)
    incoming = metrics if isinstance(metrics, dict) else {}

    if scope == 'manager':
        return {
            'date': str(incoming.get('date') or today.isoformat()),
            'yesterday': str(incoming.get('yesterday') or yesterday.isoformat()),
            'boutique_yesterday_revenue': _coerce_number(incoming.get('boutique_yesterday_revenue')),
            'boutique_yesterday_count': _coerce_number(incoming.get('boutique_yesterday_count'), integer=True),
            'hardware_yesterday_revenue': _coerce_number(incoming.get('hardware_yesterday_revenue')),
            'hardware_yesterday_count': _coerce_number(incoming.get('hardware_yesterday_count'), integer=True),
            'finance_yesterday_repayments': _coerce_number(incoming.get('finance_yesterday_repayments')),
            'finance_loans_issued_yesterday': _coerce_number(incoming.get('finance_loans_issued_yesterday'), integer=True),
            'overdue_loans': _coerce_number(incoming.get('overdue_loans'), integer=True),
            'overdue_balance': _coerce_number(incoming.get('overdue_balance')),
            'low_stock_count': _coerce_number(incoming.get('low_stock_count'), integer=True),
            'new_loan_inquiries': _coerce_number(incoming.get('new_loan_inquiries'), integer=True),
            'new_order_requests': _coerce_number(incoming.get('new_order_requests'), integer=True),
            'login_count_yesterday': _coerce_number(incoming.get('login_count_yesterday'), integer=True),
            'users_logged_in_yesterday': _coerce_list(incoming.get('users_logged_in_yesterday')),
            'boutique_branches': _coerce_list(incoming.get('boutique_branches')),
            'low_stock_items': _coerce_list(incoming.get('low_stock_items')),
            'major_transactions': _coerce_list(incoming.get('major_transactions')),
            'attention_flags': _coerce_list(incoming.get('attention_flags')),
            'activity_summary': incoming.get('activity_summary') if isinstance(incoming.get('activity_summary'), dict) else {},
        }

    if scope == 'boutique':
        return {
            'date': str(incoming.get('date') or today.isoformat()),
            'yesterday': str(incoming.get('yesterday') or yesterday.isoformat()),
            'branch': incoming.get('branch') or branch,
            'yesterday_revenue': _coerce_number(incoming.get('yesterday_revenue')),
            'yesterday_count': _coerce_number(incoming.get('yesterday_count'), integer=True),
            'outstanding_credits': _coerce_number(incoming.get('outstanding_credits')),
            'low_stock_count': _coerce_number(incoming.get('low_stock_count'), integer=True),
            'low_stock_items': _coerce_list(incoming.get('low_stock_items')),
        }

    if scope == 'hardware':
        return {
            'date': str(incoming.get('date') or today.isoformat()),
            'yesterday': str(incoming.get('yesterday') or yesterday.isoformat()),
            'yesterday_revenue': _coerce_number(incoming.get('yesterday_revenue')),
            'yesterday_count': _coerce_number(incoming.get('yesterday_count'), integer=True),
            'outstanding_credits': _coerce_number(incoming.get('outstanding_credits')),
            'low_stock_count': _coerce_number(incoming.get('low_stock_count'), integer=True),
            'low_stock_items': _coerce_list(incoming.get('low_stock_items')),
        }

    if scope == 'finance':
        return {
            'date': str(incoming.get('date') or today.isoformat()),
            'yesterday': str(incoming.get('yesterday') or yesterday.isoformat()),
            'yesterday_repayments': _coerce_number(incoming.get('yesterday_repayments')),
            'loans_issued_yesterday': _coerce_number(incoming.get('loans_issued_yesterday'), integer=True),
            'overdue_count': _coerce_number(incoming.get('overdue_count'), integer=True),
            'pending_inquiries': _coerce_number(incoming.get('pending_inquiries'), integer=True),
        }

    return {}


# ---------------------------------------------------------------------------
# Manager briefing — full business overview
# ---------------------------------------------------------------------------

def compute_manager_metrics(target_date=None):
    """Compute organisation-wide metrics for the manager morning briefing."""
    today = target_date or get_local_today()
    yesterday = today - timedelta(days=1)
    start_dt, end_dt = _local_day_window(yesterday)

    metrics = {
        'date': today.isoformat(),
        'yesterday': yesterday.isoformat(),
    }

    # --- Boutique yesterday ---
    bq_yest = db.session.query(
        func.sum(BoutiqueSale.amount_paid),
        func.count(BoutiqueSale.id),
    ).filter(BoutiqueSale.sale_date == yesterday, BoutiqueSale.is_deleted == False).first()
    metrics['boutique_yesterday_revenue'] = _float(bq_yest[0])
    metrics['boutique_yesterday_count'] = bq_yest[1] or 0

    # Boutique by branch
    bq_branches = db.session.query(
        BoutiqueSale.branch,
        func.sum(BoutiqueSale.amount_paid),
        func.count(BoutiqueSale.id),
    ).filter(
        BoutiqueSale.sale_date == yesterday, BoutiqueSale.is_deleted == False
    ).group_by(BoutiqueSale.branch).all()
    metrics['boutique_branches'] = [
        {'branch': b or 'unassigned', 'revenue': _float(r), 'count': c}
        for b, r, c in bq_branches
    ]

    # --- Hardware yesterday ---
    hw_yest = db.session.query(
        func.sum(HardwareSale.amount_paid),
        func.count(HardwareSale.id),
    ).filter(HardwareSale.sale_date == yesterday, HardwareSale.is_deleted == False).first()
    metrics['hardware_yesterday_revenue'] = _float(hw_yest[0])
    metrics['hardware_yesterday_count'] = hw_yest[1] or 0

    # --- Finance yesterday ---
    loan_repay = _float(db.session.query(func.sum(LoanPayment.amount)).filter(
        LoanPayment.payment_date == yesterday, LoanPayment.is_deleted == False
    ).scalar())
    group_repay = _float(db.session.query(func.sum(GroupLoanPayment.amount)).filter(
        GroupLoanPayment.payment_date == yesterday, GroupLoanPayment.is_deleted == False
    ).scalar())
    metrics['finance_yesterday_repayments'] = loan_repay + group_repay

    loans_issued_yest = Loan.query.filter(
        Loan.issue_date == yesterday, Loan.is_deleted == False
    ).count()
    metrics['finance_loans_issued_yesterday'] = loans_issued_yest

    # --- Overdue loans ---
    overdue_individual = Loan.query.filter(Loan.is_deleted == False, Loan.status == 'overdue').count()
    overdue_group = GroupLoan.query.filter(GroupLoan.is_deleted == False, GroupLoan.status == 'overdue').count()
    metrics['overdue_loans'] = overdue_individual + overdue_group

    overdue_balance = _float(db.session.query(func.sum(Loan.balance)).filter(
        Loan.is_deleted == False, Loan.status == 'overdue'
    ).scalar()) + _float(db.session.query(func.sum(GroupLoan.balance)).filter(
        GroupLoan.is_deleted == False, GroupLoan.status == 'overdue'
    ).scalar())
    metrics['overdue_balance'] = overdue_balance

    # --- Low stock ---
    boutique_low = BoutiqueStock.query.filter(
        BoutiqueStock.is_active == True,
        BoutiqueStock.quantity <= BoutiqueStock.low_stock_threshold
    ).all()
    hardware_low = HardwareStock.query.filter(
        HardwareStock.is_active == True,
        HardwareStock.quantity <= HardwareStock.low_stock_threshold
    ).all()
    metrics['low_stock_count'] = len(boutique_low) + len(hardware_low)
    metrics['low_stock_items'] = [
        {'section': 'Boutique', 'name': s.item_name, 'qty': s.quantity, 'unit': s.unit}
        for s in boutique_low[:10]
    ] + [
        {'section': 'Hardware', 'name': s.item_name, 'qty': s.quantity, 'unit': s.unit}
        for s in hardware_low[:10]
    ]

    # --- Website inquiries & orders (new since yesterday start) ---
    new_inquiries = WebsiteLoanInquiry.query.filter(
        WebsiteLoanInquiry.submitted_at >= start_dt,
        WebsiteLoanInquiry.submitted_at < end_dt,
        WebsiteLoanInquiry.is_active == True,
    ).count()
    new_orders = WebsiteOrderRequest.query.filter(
        WebsiteOrderRequest.submitted_at >= start_dt,
        WebsiteOrderRequest.submitted_at < end_dt,
        WebsiteOrderRequest.is_active == True,
    ).count()
    metrics['new_loan_inquiries'] = new_inquiries
    metrics['new_order_requests'] = new_orders

    # --- Who logged in yesterday ---
    login_logs = AuditLog.query.filter(
        AuditLog.action == 'login',
        func.date(AuditLog.created_at) == yesterday,
    ).all()
    unique_users = list({log.username for log in login_logs})
    metrics['users_logged_in_yesterday'] = unique_users
    metrics['login_count_yesterday'] = len(login_logs)

    # --- Audit activity summary ---
    activity = db.session.query(
        AuditLog.action, func.count(AuditLog.id)
    ).filter(
        func.date(AuditLog.created_at) == yesterday
    ).group_by(AuditLog.action).all()
    metrics['activity_summary'] = {action: count for action, count in activity}

    # --- Major transactions (top 5 by amount) ---
    big_boutique = db.session.query(
        BoutiqueSale.reference_number, BoutiqueSale.total_amount
    ).filter(
        BoutiqueSale.sale_date == yesterday, BoutiqueSale.is_deleted == False
    ).order_by(BoutiqueSale.total_amount.desc()).limit(5).all()
    big_hardware = db.session.query(
        HardwareSale.reference_number, HardwareSale.total_amount
    ).filter(
        HardwareSale.sale_date == yesterday, HardwareSale.is_deleted == False
    ).order_by(HardwareSale.total_amount.desc()).limit(5).all()
    transactions = [
        {'ref': ref, 'amount': _float(amt), 'section': 'Boutique'}
        for ref, amt in big_boutique
    ] + [
        {'ref': ref, 'amount': _float(amt), 'section': 'Hardware'}
        for ref, amt in big_hardware
    ]
    metrics['major_transactions'] = sorted(
        transactions,
        key=lambda tx: tx['amount'],
        reverse=True,
    )[:5]

    # --- Anomaly flags (deterministic rules) ---
    flags = []
    total_yest = metrics['boutique_yesterday_revenue'] + metrics['hardware_yesterday_revenue']
    if metrics['overdue_loans'] > 5:
        flags.append(f"{metrics['overdue_loans']} overdue loans totalling UGX {metrics['overdue_balance']:,.0f}")
    if metrics['low_stock_count'] > 3:
        flags.append(f"{metrics['low_stock_count']} items below restock threshold")
    if new_inquiries > 0:
        flags.append(f"{new_inquiries} new loan inquiries need review")
    if new_orders > 0:
        flags.append(f"{new_orders} new order requests need follow-up")
    metrics['attention_flags'] = flags

    return metrics


# ---------------------------------------------------------------------------
# Scoped briefings for non-manager roles
# ---------------------------------------------------------------------------

def compute_boutique_metrics(branch=None, target_date=None):
    today = target_date or get_local_today()
    yesterday = today - timedelta(days=1)

    base_filter = [BoutiqueSale.is_deleted == False, BoutiqueSale.sale_date == yesterday]
    stock_filter = [BoutiqueStock.is_active == True]
    if branch:
        base_filter.append(BoutiqueSale.branch == branch)
        stock_filter.append(BoutiqueStock.branch == branch)

    yest = db.session.query(
        func.sum(BoutiqueSale.amount_paid), func.count(BoutiqueSale.id)
    ).filter(*base_filter).first()

    credits = _float(db.session.query(func.sum(BoutiqueSale.balance)).filter(
        BoutiqueSale.is_deleted == False, BoutiqueSale.is_credit_cleared == False,
        BoutiqueSale.payment_type == 'part',
        *([BoutiqueSale.branch == branch] if branch else [])
    ).scalar())

    low_stock = BoutiqueStock.query.filter(
        *stock_filter, BoutiqueStock.quantity <= BoutiqueStock.low_stock_threshold
    ).all()

    return {
        'date': today.isoformat(),
        'yesterday': yesterday.isoformat(),
        'branch': branch,
        'yesterday_revenue': _float(yest[0]),
        'yesterday_count': yest[1] or 0,
        'outstanding_credits': credits,
        'low_stock_count': len(low_stock),
        'low_stock_items': [
            {'name': s.item_name, 'qty': s.quantity, 'unit': s.unit}
            for s in low_stock[:10]
        ],
    }


def compute_hardware_metrics(target_date=None):
    today = target_date or get_local_today()
    yesterday = today - timedelta(days=1)

    yest = db.session.query(
        func.sum(HardwareSale.amount_paid), func.count(HardwareSale.id)
    ).filter(HardwareSale.sale_date == yesterday, HardwareSale.is_deleted == False).first()

    credits = _float(db.session.query(func.sum(HardwareSale.balance)).filter(
        HardwareSale.is_deleted == False, HardwareSale.is_credit_cleared == False,
        HardwareSale.payment_type == 'part',
    ).scalar())

    low_stock = HardwareStock.query.filter(
        HardwareStock.is_active == True,
        HardwareStock.quantity <= HardwareStock.low_stock_threshold,
    ).all()

    return {
        'date': today.isoformat(),
        'yesterday': yesterday.isoformat(),
        'yesterday_revenue': _float(yest[0]),
        'yesterday_count': yest[1] or 0,
        'outstanding_credits': credits,
        'low_stock_count': len(low_stock),
        'low_stock_items': [
            {'name': s.item_name, 'qty': s.quantity, 'unit': s.unit}
            for s in low_stock[:10]
        ],
    }


def compute_finance_metrics(target_date=None):
    today = target_date or get_local_today()
    yesterday = today - timedelta(days=1)

    repayments = _float(db.session.query(func.sum(LoanPayment.amount)).filter(
        LoanPayment.payment_date == yesterday, LoanPayment.is_deleted == False
    ).scalar()) + _float(db.session.query(func.sum(GroupLoanPayment.amount)).filter(
        GroupLoanPayment.payment_date == yesterday, GroupLoanPayment.is_deleted == False
    ).scalar())

    loans_issued = Loan.query.filter(
        Loan.issue_date == yesterday, Loan.is_deleted == False
    ).count()

    overdue = Loan.query.filter(Loan.is_deleted == False, Loan.status == 'overdue').count()
    overdue += GroupLoan.query.filter(GroupLoan.is_deleted == False, GroupLoan.status == 'overdue').count()

    new_inquiries = WebsiteLoanInquiry.query.filter(
        WebsiteLoanInquiry.status == 'new', WebsiteLoanInquiry.is_active == True
    ).count()

    return {
        'date': today.isoformat(),
        'yesterday': yesterday.isoformat(),
        'yesterday_repayments': repayments,
        'loans_issued_yesterday': loans_issued,
        'overdue_count': overdue,
        'pending_inquiries': new_inquiries,
    }


# ---------------------------------------------------------------------------
# Cache / retrieve briefing
# ---------------------------------------------------------------------------

def get_or_create_briefing(scope, branch=None, target_date=None):
    """Get cached briefing or compute + cache it.  Returns (metrics_dict, ai_narrative)."""
    today = target_date or get_local_today()
    cache_branch = branch or '__all__'

    existing = DailyBriefing.query.filter(
        DailyBriefing.briefing_date == today,
        DailyBriefing.scope == scope,
        or_(DailyBriefing.branch == cache_branch, DailyBriefing.branch.is_(None))
    ).first()
    if existing:
        try:
            cached_metrics = json.loads(existing.metrics_json)
        except (TypeError, ValueError, json.JSONDecodeError):
            logger.warning('Invalid cached briefing JSON for %s/%s; recomputing', scope, cache_branch)
            cached_metrics = None
        if cached_metrics is not None:
            return sanitize_briefing_metrics(scope, cached_metrics, branch, today), existing.ai_narrative

    # Compute metrics
    if scope == 'manager':
        metrics = compute_manager_metrics(today)
    elif scope == 'boutique':
        metrics = compute_boutique_metrics(branch, today)
    elif scope == 'hardware':
        metrics = compute_hardware_metrics(today)
    elif scope == 'finance':
        metrics = compute_finance_metrics(today)
    else:
        metrics = {}

    # Attempt AI narration (non-blocking, short timeout)
    ai_narrative = None
    try:
        from app.utils.ai_client import is_briefing_ai_enabled, ai_chat
        if is_briefing_ai_enabled() and metrics:
            prompt = _build_narration_prompt(scope, metrics)
            ai_narrative = ai_chat(prompt, system=_narration_system_prompt(scope))
    except Exception as exc:
        logger.warning('AI narration failed for %s briefing: %s', scope, exc.__class__.__name__)

    # Cache
    try:
        briefing = DailyBriefing(
            briefing_date=today,
            scope=scope,
            branch=cache_branch,
            metrics_json=json.dumps(metrics, default=str),
            ai_narrative=ai_narrative,
        )
        db.session.add(briefing)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.warning('Failed to cache briefing for %s/%s', scope, branch)

    return sanitize_briefing_metrics(scope, metrics, branch, today), ai_narrative


def _build_narration_prompt(scope, metrics):
    """Build a compact prompt from metrics for AI narration."""
    lines = [f"Daily briefing for {scope} scope:"]
    for key, value in metrics.items():
        if key in ('date', 'yesterday'):
            continue
        if isinstance(value, list) and len(value) > 3:
            lines.append(f"  {key}: {len(value)} items (showing first 3: {value[:3]})")
        else:
            lines.append(f"  {key}: {value}")
    lines.append("\nSummarise the key takeaways in 3-4 sentences for the morning standup.")
    return '\n'.join(lines)


def _narration_system_prompt(scope):
    audience = {
        'manager': 'a manager overseeing all branches and business sections',
        'boutique': 'a boutique staff member starting the work day',
        'hardware': 'a hardware staff member starting the work day',
        'finance': 'a finance staff member starting the work day',
    }.get(scope, 'a staff member starting the work day')
    return (
        "You are a concise business analyst for a Ugandan retail and microfinance company. "
        f"Write a 3-4 sentence morning summary for {audience}. "
        "Be direct, mention key numbers, and flag what needs attention today. "
        "Currency is UGX. Do not use markdown."
    )
