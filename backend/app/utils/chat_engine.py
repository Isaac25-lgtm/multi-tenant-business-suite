"""Manager AI chatbot — intent-based query engine.

Instead of text-to-SQL, we classify the user's message into a known intent,
run a safe pre-built query, and optionally use the LLM to narrate the results.

Supported intents:
  overdue_loans       — list overdue loans with balances
  low_stock           — list items below restock threshold
  yesterday_summary   — revenue/sales summary for yesterday
  branch_comparison   — compare boutique branches
  user_activity       — who logged in and what they did
  loan_search         — search loans above a threshold
  top_transactions    — biggest sales this week
  general             — fallback: answer from pre-computed context
"""

import json
import logging
import re
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func

from app.extensions import db
from app.models.boutique import BoutiqueSale, BoutiqueStock
from app.models.hardware import HardwareSale, HardwareStock
from app.models.finance import Loan, GroupLoan, LoanPayment, GroupLoanPayment, LoanClient
from app.models.user import User, AuditLog
from app.models.website import WebsiteLoanInquiry, WebsiteOrderRequest
from app.utils.timezone import get_local_today

logger = logging.getLogger(__name__)

SUGGESTED_PROMPTS = [
    "Summarise yesterday's performance by section",
    "Show all overdue loans",
    "Which stock items need restocking?",
    "Compare boutique branches this week",
    "Who logged in yesterday and what did they do?",
    "Show the biggest transactions this week",
    "How many new loan inquiries are pending?",
]


def _float(val):
    if val is None:
        return 0.0
    return float(val)


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------

_INTENT_PATTERNS = [
    ('overdue_loans', re.compile(r'overdue|past\s*due|late\s*(loan|payment)', re.I)),
    ('low_stock', re.compile(r'low.stock|out.of.stock|restock|replenish|stock.*(low|need|run)', re.I)),
    ('yesterday_summary', re.compile(r'yesterday|summary|performance|recap', re.I)),
    ('branch_comparison', re.compile(r'branch|compar|kapchorwa|mbale', re.I)),
    ('user_activity', re.compile(r'(who|user|staff).*(log|activ|did)|log.*in.*yesterday', re.I)),
    ('loan_search', re.compile(r'loan.*(above|over|more\s*than|greater|>\s*\d)', re.I)),
    ('top_transactions', re.compile(r'(big|top|large|major)\s*(transact|sale)', re.I)),
    ('pending_inquiries', re.compile(r'(inquir|order|request).*(pending|new|review)', re.I)),
]


def classify_intent(message):
    """Classify a user message into a known intent string."""
    for intent, pattern in _INTENT_PATTERNS:
        if pattern.search(message):
            return intent
    return 'general'


def _extract_number(message, default=0):
    """Pull the first number from a message string."""
    match = re.search(r'[\d,]+', message.replace(',', ''))
    if match:
        try:
            return int(match.group().replace(',', ''))
        except ValueError:
            pass
    return default


# ---------------------------------------------------------------------------
# Intent handlers — each returns a dict of structured data
# ---------------------------------------------------------------------------

def handle_overdue_loans():
    today = get_local_today()
    loans = Loan.query.filter(
        Loan.is_deleted == False, Loan.status == 'overdue'
    ).order_by(Loan.balance.desc()).limit(20).all()
    groups = GroupLoan.query.filter(
        GroupLoan.is_deleted == False, GroupLoan.status == 'overdue'
    ).order_by(GroupLoan.balance.desc()).limit(10).all()

    items = []
    for l in loans:
        client = LoanClient.query.get(l.client_id)
        items.append({
            'type': 'individual',
            'client': client.name if client else 'Unknown',
            'principal': _float(l.principal),
            'balance': _float(l.balance),
            'due_date': l.due_date.isoformat() if l.due_date else None,
            'link': f'/finance/loans/{l.id}',
        })
    for g in groups:
        items.append({
            'type': 'group',
            'client': g.group_name,
            'principal': _float(g.principal),
            'balance': _float(g.balance),
            'due_date': g.due_date.isoformat() if g.due_date else None,
            'link': f'/finance/group-loans/{g.id}',
        })

    total_balance = sum(i['balance'] for i in items)
    return {
        'intent': 'overdue_loans',
        'count': len(items),
        'total_balance': total_balance,
        'items': items,
        'summary': f"{len(items)} overdue loans with total outstanding balance of UGX {total_balance:,.0f}.",
    }


def handle_low_stock():
    boutique = BoutiqueStock.query.filter(
        BoutiqueStock.is_active == True,
        BoutiqueStock.quantity <= BoutiqueStock.low_stock_threshold,
    ).order_by(BoutiqueStock.quantity.asc()).limit(20).all()
    hardware = HardwareStock.query.filter(
        HardwareStock.is_active == True,
        HardwareStock.quantity <= HardwareStock.low_stock_threshold,
    ).order_by(HardwareStock.quantity.asc()).limit(20).all()

    items = [
        {'section': 'Boutique', 'name': s.item_name, 'qty': s.quantity, 'unit': s.unit,
         'threshold': s.low_stock_threshold, 'link': '/boutique/stock'}
        for s in boutique
    ] + [
        {'section': 'Hardware', 'name': s.item_name, 'qty': s.quantity, 'unit': s.unit,
         'threshold': s.low_stock_threshold, 'link': '/hardware/stock'}
        for s in hardware
    ]
    return {
        'intent': 'low_stock',
        'count': len(items),
        'items': items,
        'summary': f"{len(items)} items are below their restock threshold.",
    }


def handle_yesterday_summary():
    today = get_local_today()
    yesterday = today - timedelta(days=1)

    bq = _float(db.session.query(func.sum(BoutiqueSale.amount_paid)).filter(
        BoutiqueSale.sale_date == yesterday, BoutiqueSale.is_deleted == False).scalar())
    hw = _float(db.session.query(func.sum(HardwareSale.amount_paid)).filter(
        HardwareSale.sale_date == yesterday, HardwareSale.is_deleted == False).scalar())
    repay = _float(db.session.query(func.sum(LoanPayment.amount)).filter(
        LoanPayment.payment_date == yesterday, LoanPayment.is_deleted == False).scalar())
    repay += _float(db.session.query(func.sum(GroupLoanPayment.amount)).filter(
        GroupLoanPayment.payment_date == yesterday, GroupLoanPayment.is_deleted == False).scalar())

    total = bq + hw + repay
    return {
        'intent': 'yesterday_summary',
        'date': yesterday.isoformat(),
        'boutique_revenue': bq,
        'hardware_revenue': hw,
        'finance_repayments': repay,
        'total': total,
        'summary': (
            f"Yesterday ({yesterday.strftime('%a %d %b')}): "
            f"Boutique UGX {bq:,.0f}, Hardware UGX {hw:,.0f}, "
            f"Finance repayments UGX {repay:,.0f}. Total UGX {total:,.0f}."
        ),
    }


def handle_branch_comparison():
    today = get_local_today()
    week_start = today - timedelta(days=7)

    branches = db.session.query(
        BoutiqueSale.branch,
        func.sum(BoutiqueSale.amount_paid),
        func.count(BoutiqueSale.id),
    ).filter(
        BoutiqueSale.sale_date >= week_start,
        BoutiqueSale.sale_date < today,
        BoutiqueSale.is_deleted == False,
    ).group_by(BoutiqueSale.branch).all()

    items = [
        {'branch': b or 'unassigned', 'revenue': _float(r), 'count': c}
        for b, r, c in branches
    ]
    return {
        'intent': 'branch_comparison',
        'period': f'{week_start.isoformat()} to {today.isoformat()}',
        'branches': items,
        'items': items,
        'summary': f"Boutique branch comparison for the past 7 days: {len(items)} branches active.",
    }


def handle_user_activity():
    today = get_local_today()
    yesterday = today - timedelta(days=1)

    logs = AuditLog.query.filter(
        func.date(AuditLog.created_at) == yesterday
    ).order_by(AuditLog.created_at.desc()).limit(50).all()

    users_seen = {}
    for log in logs:
        if log.username not in users_seen:
            users_seen[log.username] = {'actions': 0, 'sections': set()}
        users_seen[log.username]['actions'] += 1
        users_seen[log.username]['sections'].add(log.section)

    items = [
        {'username': u, 'actions': d['actions'], 'sections': list(d['sections'])}
        for u, d in users_seen.items()
    ]
    return {
        'intent': 'user_activity',
        'date': yesterday.isoformat(),
        'user_count': len(items),
        'items': items,
        'summary': f"{len(items)} users were active yesterday with {len(logs)} total actions.",
    }


def handle_loan_search(message):
    threshold = _extract_number(message, 500000)
    loans = Loan.query.filter(
        Loan.is_deleted == False, Loan.balance > threshold
    ).order_by(Loan.balance.desc()).limit(20).all()

    items = []
    for l in loans:
        client = LoanClient.query.get(l.client_id)
        items.append({
            'client': client.name if client else 'Unknown',
            'balance': _float(l.balance),
            'status': l.status,
            'link': f'/finance/loans/{l.id}',
        })
    return {
        'intent': 'loan_search',
        'threshold': threshold,
        'count': len(items),
        'items': items,
        'summary': f"{len(items)} loans with balance above UGX {threshold:,.0f}.",
    }


def handle_top_transactions():
    today = get_local_today()
    week_start = today - timedelta(days=7)

    bq = db.session.query(
        BoutiqueSale.reference_number, BoutiqueSale.total_amount, BoutiqueSale.sale_date
    ).filter(
        BoutiqueSale.sale_date >= week_start, BoutiqueSale.is_deleted == False
    ).order_by(BoutiqueSale.total_amount.desc()).limit(5).all()

    hw = db.session.query(
        HardwareSale.reference_number, HardwareSale.total_amount, HardwareSale.sale_date
    ).filter(
        HardwareSale.sale_date >= week_start, HardwareSale.is_deleted == False
    ).order_by(HardwareSale.total_amount.desc()).limit(5).all()

    items = sorted(
        [{'ref': r, 'amount': _float(a), 'date': d.isoformat(), 'section': 'Boutique'} for r, a, d in bq] +
        [{'ref': r, 'amount': _float(a), 'date': d.isoformat(), 'section': 'Hardware'} for r, a, d in hw],
        key=lambda x: x['amount'], reverse=True,
    )[:10]

    return {
        'intent': 'top_transactions',
        'items': items,
        'summary': f"Top {len(items)} transactions this week.",
    }


def handle_pending_inquiries():
    inquiries = WebsiteLoanInquiry.query.filter(
        WebsiteLoanInquiry.status == 'new', WebsiteLoanInquiry.is_active == True
    ).order_by(WebsiteLoanInquiry.submitted_at.desc()).limit(10).all()
    orders = WebsiteOrderRequest.query.filter(
        WebsiteOrderRequest.status == 'new', WebsiteOrderRequest.is_active == True
    ).order_by(WebsiteOrderRequest.submitted_at.desc()).limit(10).all()

    return {
        'intent': 'pending_inquiries',
        'inquiry_count': len(inquiries),
        'order_count': len(orders),
        'inquiries': [
            {'name': i.full_name, 'phone': i.phone, 'amount': i.requested_amount,
             'link': f'/website/loan-inquiries/{i.id}'}
            for i in inquiries
        ],
        'orders': [
            {'name': o.customer_name, 'phone': o.customer_phone,
             'link': f'/website/order-requests/{o.id}'}
            for o in orders
        ],
        'items': (
            [{'type': 'loan_inquiry', 'name': i.full_name, 'phone': i.phone, 'amount': i.requested_amount,
              'link': f'/website/loan-inquiries/{i.id}'} for i in inquiries] +
            [{'type': 'order_request', 'name': o.customer_name, 'phone': o.customer_phone,
              'link': f'/website/order-requests/{o.id}'} for o in orders]
        ),
        'summary': f"{len(inquiries)} pending loan inquiries, {len(orders)} pending order requests.",
    }


# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------

INTENT_HANDLERS = {
    'overdue_loans': lambda msg: handle_overdue_loans(),
    'low_stock': lambda msg: handle_low_stock(),
    'yesterday_summary': lambda msg: handle_yesterday_summary(),
    'branch_comparison': lambda msg: handle_branch_comparison(),
    'user_activity': lambda msg: handle_user_activity(),
    'loan_search': handle_loan_search,
    'top_transactions': lambda msg: handle_top_transactions(),
    'pending_inquiries': lambda msg: handle_pending_inquiries(),
}


def process_chat_message(message):
    """Process a manager chat message. Returns structured response dict."""
    intent = classify_intent(message)
    handler = INTENT_HANDLERS.get(intent)

    if handler:
        try:
            data = handler(message)
        except Exception as exc:
            logger.warning('Chat intent handler %s failed: %s', intent, exc)
            return {
                'intent': intent,
                'error': True,
                'summary': 'Sorry, I encountered an error fetching that data. Please try again.',
            }
    else:
        data = None

    # For known intents, optionally use AI to provide a richer narration
    if data and not data.get('error'):
        try:
            from app.utils.ai_client import is_chat_enabled, ai_chat
            if is_chat_enabled():
                ai_response = ai_chat(
                    f"User asked: {message}\n\nHere is the data:\n{json.dumps(data, default=str)}\n\n"
                    "Provide a concise, helpful natural-language answer based on this data. "
                    "Reference specific numbers. Keep it to 2-4 sentences. Currency is UGX.",
                    system=(
                        "You are a business data assistant for a Ugandan retail and microfinance company called Denove. "
                        "You answer manager questions using only the provided data. Never invent numbers. "
                        "Be direct and actionable. Do not use markdown formatting."
                    ),
                )
                if ai_response:
                    data['ai_narrative'] = ai_response
        except Exception:
            pass  # AI narration is optional

        return data

    # General / unknown intent — try AI with business context if available
    try:
        from app.utils.ai_client import is_chat_enabled, ai_chat
        if is_chat_enabled():
            # Give AI some context
            context = handle_yesterday_summary()
            ai_response = ai_chat(
                f"User question: {message}\n\n"
                f"Business context (yesterday's data):\n{json.dumps(context, default=str)}\n\n"
                "Answer the question helpfully if possible, or say you can help with: "
                "overdue loans, stock levels, yesterday's summary, branch comparisons, "
                "user activity, loan searches, top transactions, and pending inquiries.",
                system=(
                    "You are a business data assistant for Denove, a Ugandan retail and microfinance company. "
                    "You can only answer from provided data. Never invent data. Be concise. No markdown."
                ),
            )
            if ai_response:
                return {
                    'intent': 'general',
                    'summary': ai_response,
                    'ai_narrative': ai_response,
                }
    except Exception:
        pass

    return {
        'intent': 'general',
        'summary': (
            "I can help you with: overdue loans, stock levels, yesterday's summary, "
            "branch comparisons, user activity, loan searches, top transactions, "
            "and pending inquiries. Try asking about one of these topics!"
        ),
    }
