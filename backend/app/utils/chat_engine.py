"""Manager AI chatbot intent engine.

Instead of free-form text-to-SQL, the assistant classifies messages into
supported business questions, runs safe ORM queries, and optionally lets the
LLM narrate the structured results.
"""

import json
import logging
import re
from datetime import timedelta

from sqlalchemy import func

from app.extensions import db
from app.models.boutique import BoutiqueSale, BoutiqueStock
from app.models.finance import GroupLoan, GroupLoanPayment, Loan, LoanClient, LoanPayment
from app.models.hardware import HardwareSale, HardwareStock
from app.models.user import AuditLog
from app.models.website import WebsiteLoanInquiry, WebsiteOrderRequest
from app.utils.timezone import get_local_today

logger = logging.getLogger(__name__)

SUGGESTED_PROMPTS = [
    "Summarise yesterday's performance by section",
    "How much stock do I have right now?",
    "Which stock items need restocking?",
    "Show all overdue loans",
    "Compare boutique branches this week",
    "Who logged in yesterday and what did they do?",
    "Explain projections",
]

CAPABILITY_FALLBACK = (
    "I can help with current stock on hand, low-stock alerts, overdue loans, "
    "yesterday's performance, branch comparisons, staff activity, top transactions, "
    "and pending website inquiries. Try asking: 'How much stock do I have right now?'"
)


def _float(value):
    if value is None:
        return 0.0
    return float(value)


def _branch_label(raw_value):
    value = (raw_value or "").strip().upper()
    if value == "K":
        return "Kapchorwa"
    if value == "B":
        return "Mbale"
    if value:
        return value
    return "Shared / Unassigned"


_INTENT_PATTERNS = [
    ("overdue_loans", re.compile(r"overdue|past\s*due|late\s*(loan|payment)", re.I)),
    (
        "inventory_overview",
        re.compile(
            r"how\s*(much|many).*(stock|inventory)|"
            r"(stock|inventory).*(do\s*i|do\s*we)\s*ha\w+|"
            r"total\s*(stock|inventory)|"
            r"(stock|inventory)\s*(overview|summary|position|on\s*hand|available|levels?)",
            re.I,
        ),
    ),
    (
        "low_stock",
        re.compile(
            r"low.stock|out.of.stock|restock|replenish|stock.*(low|need|run)|"
            r"inventory.*(reorder|restock|critical)",
            re.I,
        ),
    ),
    ("yesterday_summary", re.compile(r"yesterday|summary|performance|recap", re.I)),
    ("branch_comparison", re.compile(r"branch|compar|kapchorwa|mbale", re.I)),
    ("user_activity", re.compile(r"(who|user|staff).*(log|activ|did)|log.*in.*yesterday", re.I)),
    ("loan_search", re.compile(r"loan.*(above|over|more\s*than|greater|>\s*\d)", re.I)),
    ("top_transactions", re.compile(r"(big|top|large|major)\s*(transact|sale)", re.I)),
    ("pending_inquiries", re.compile(r"(inquir|order|request).*(pending|new|review)", re.I)),
    ("projection_guidance", re.compile(r"projection|forecast|predict|outlook|trend", re.I)),
]


def classify_intent(message):
    """Classify a user message into a supported intent."""
    for intent, pattern in _INTENT_PATTERNS:
        if pattern.search(message):
            return intent
    return "general"


def _extract_number(message, default=0):
    match = re.search(r"[\d,]+", message.replace(",", ""))
    if not match:
        return default
    try:
        return int(match.group().replace(",", ""))
    except ValueError:
        return default


def handle_overdue_loans():
    loans = Loan.query.filter(
        Loan.is_deleted == False,
        Loan.status == "overdue",
    ).order_by(Loan.balance.desc()).limit(20).all()
    groups = GroupLoan.query.filter(
        GroupLoan.is_deleted == False,
        GroupLoan.status == "overdue",
    ).order_by(GroupLoan.balance.desc()).limit(10).all()

    items = []
    for loan in loans:
        client = LoanClient.query.get(loan.client_id)
        items.append(
            {
                "type": "individual",
                "client": client.name if client else "Unknown",
                "principal": _float(loan.principal),
                "balance": _float(loan.balance),
                "due_date": loan.due_date.isoformat() if loan.due_date else None,
                "link": f"/finance/loans/{loan.id}",
            }
        )
    for group in groups:
        items.append(
            {
                "type": "group",
                "client": group.group_name,
                "principal": _float(group.principal),
                "balance": _float(group.balance),
                "due_date": group.due_date.isoformat() if group.due_date else None,
                "link": f"/finance/group-loans/{group.id}",
            }
        )

    total_balance = sum(item["balance"] for item in items)
    return {
        "intent": "overdue_loans",
        "count": len(items),
        "total_balance": total_balance,
        "items": items,
        "summary": f"{len(items)} overdue loans with total outstanding balance of UGX {total_balance:,.0f}.",
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
        {
            "section": "Boutique",
            "name": item.item_name,
            "qty": item.quantity,
            "unit": item.unit,
            "threshold": item.low_stock_threshold,
            "link": "/boutique/stock",
        }
        for item in boutique
    ] + [
        {
            "section": "Hardware",
            "name": item.item_name,
            "qty": item.quantity,
            "unit": item.unit,
            "threshold": item.low_stock_threshold,
            "link": "/hardware/stock",
        }
        for item in hardware
    ]

    summary = (
        "All tracked stock is currently above its configured restock threshold."
        if not items
        else f"{len(items)} items are below their restock threshold and need attention."
    )
    return {
        "intent": "low_stock",
        "count": len(items),
        "items": items,
        "summary": summary,
    }


def handle_inventory_overview():
    boutique_rows = BoutiqueStock.query.filter(BoutiqueStock.is_active == True).all()
    hardware_rows = HardwareStock.query.filter(HardwareStock.is_active == True).all()

    boutique_skus = len(boutique_rows)
    hardware_skus = len(hardware_rows)
    boutique_units = sum(int(item.quantity or 0) for item in boutique_rows)
    hardware_units = sum(int(item.quantity or 0) for item in hardware_rows)
    boutique_low = sum(
        1
        for item in boutique_rows
        if item.low_stock_threshold is not None and item.quantity <= item.low_stock_threshold
    )
    hardware_low = sum(
        1
        for item in hardware_rows
        if item.low_stock_threshold is not None and item.quantity <= item.low_stock_threshold
    )

    branch_rows = db.session.query(
        BoutiqueStock.branch,
        func.count(BoutiqueStock.id),
        func.sum(BoutiqueStock.quantity),
    ).filter(
        BoutiqueStock.is_active == True
    ).group_by(BoutiqueStock.branch).all()

    items = [
        {
            "section": "Boutique",
            "name": "Current stock on hand",
            "skus": boutique_skus,
            "units_on_hand": boutique_units,
            "low_stock_items": boutique_low,
            "link": "/boutique/stock",
        },
        {
            "section": "Hardware",
            "name": "Current stock on hand",
            "skus": hardware_skus,
            "units_on_hand": hardware_units,
            "low_stock_items": hardware_low,
            "link": "/hardware/stock",
        },
    ]

    for branch, sku_count, units in branch_rows:
        items.append(
            {
                "section": "Boutique branch",
                "name": _branch_label(branch),
                "skus": int(sku_count or 0),
                "units_on_hand": int(units or 0),
                "low_stock_items": "",
            }
        )

    total_skus = boutique_skus + hardware_skus
    total_units = boutique_units + hardware_units
    total_low = boutique_low + hardware_low

    return {
        "intent": "inventory_overview",
        "count": len(items),
        "total_skus": total_skus,
        "total_units": total_units,
        "low_stock_count": total_low,
        "items": items,
        "summary": (
            f"You currently have {total_skus} active stock lines holding {total_units:,.0f} units in total. "
            f"Boutique has {boutique_skus} stock lines with {boutique_units:,.0f} units, and hardware has "
            f"{hardware_skus} stock lines with {hardware_units:,.0f} units. "
            f"{total_low} item{'s' if total_low != 1 else ''} are low on stock."
        ),
    }


def handle_yesterday_summary():
    today = get_local_today()
    yesterday = today - timedelta(days=1)

    boutique_revenue = _float(
        db.session.query(func.sum(BoutiqueSale.amount_paid)).filter(
            BoutiqueSale.sale_date == yesterday,
            BoutiqueSale.is_deleted == False,
        ).scalar()
    )
    hardware_revenue = _float(
        db.session.query(func.sum(HardwareSale.amount_paid)).filter(
            HardwareSale.sale_date == yesterday,
            HardwareSale.is_deleted == False,
        ).scalar()
    )
    finance_repayments = _float(
        db.session.query(func.sum(LoanPayment.amount)).filter(
            LoanPayment.payment_date == yesterday,
            LoanPayment.is_deleted == False,
        ).scalar()
    )
    finance_repayments += _float(
        db.session.query(func.sum(GroupLoanPayment.amount)).filter(
            GroupLoanPayment.payment_date == yesterday,
            GroupLoanPayment.is_deleted == False,
        ).scalar()
    )

    total = boutique_revenue + hardware_revenue + finance_repayments
    return {
        "intent": "yesterday_summary",
        "date": yesterday.isoformat(),
        "boutique_revenue": boutique_revenue,
        "hardware_revenue": hardware_revenue,
        "finance_repayments": finance_repayments,
        "total": total,
        "summary": (
            f"Yesterday ({yesterday.strftime('%a %d %b')}): Boutique UGX {boutique_revenue:,.0f}, "
            f"Hardware UGX {hardware_revenue:,.0f}, Finance repayments UGX {finance_repayments:,.0f}. "
            f"Total UGX {total:,.0f}."
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
        {
            "branch": _branch_label(branch),
            "revenue": _float(revenue),
            "sales_count": int(count or 0),
        }
        for branch, revenue, count in branches
    ]
    summary = (
        "No boutique branch sales were recorded in the past 7 days."
        if not items
        else f"Boutique branch comparison for the past 7 days across {len(items)} active branch records."
    )
    return {
        "intent": "branch_comparison",
        "period": f"{week_start.isoformat()} to {today.isoformat()}",
        "branches": items,
        "items": items,
        "summary": summary,
    }


def handle_user_activity():
    today = get_local_today()
    yesterday = today - timedelta(days=1)

    logs = AuditLog.query.filter(
        func.date(AuditLog.created_at) == yesterday
    ).order_by(AuditLog.created_at.desc()).limit(75).all()

    users_seen = {}
    for log in logs:
        if log.username not in users_seen:
            users_seen[log.username] = {"actions": 0, "sections": set()}
        users_seen[log.username]["actions"] += 1
        if log.section:
            users_seen[log.username]["sections"].add(log.section)

    items = [
        {
            "username": username,
            "actions": data["actions"],
            "sections": ", ".join(sorted(data["sections"])) if data["sections"] else "-",
        }
        for username, data in users_seen.items()
    ]
    return {
        "intent": "user_activity",
        "date": yesterday.isoformat(),
        "user_count": len(items),
        "items": items,
        "summary": f"{len(items)} users were active yesterday with {len(logs)} recorded actions.",
    }


def handle_loan_search(message):
    threshold = _extract_number(message, 500000)
    loans = Loan.query.filter(
        Loan.is_deleted == False,
        Loan.balance > threshold,
    ).order_by(Loan.balance.desc()).limit(20).all()

    items = []
    for loan in loans:
        client = LoanClient.query.get(loan.client_id)
        items.append(
            {
                "client": client.name if client else "Unknown",
                "balance": _float(loan.balance),
                "status": loan.status,
                "link": f"/finance/loans/{loan.id}",
            }
        )
    return {
        "intent": "loan_search",
        "threshold": threshold,
        "count": len(items),
        "items": items,
        "summary": f"{len(items)} loans with balance above UGX {threshold:,.0f}.",
    }


def handle_top_transactions():
    today = get_local_today()
    week_start = today - timedelta(days=7)

    boutique_rows = db.session.query(
        BoutiqueSale.reference_number,
        BoutiqueSale.total_amount,
        BoutiqueSale.sale_date,
    ).filter(
        BoutiqueSale.sale_date >= week_start,
        BoutiqueSale.is_deleted == False,
    ).order_by(BoutiqueSale.total_amount.desc()).limit(5).all()

    hardware_rows = db.session.query(
        HardwareSale.reference_number,
        HardwareSale.total_amount,
        HardwareSale.sale_date,
    ).filter(
        HardwareSale.sale_date >= week_start,
        HardwareSale.is_deleted == False,
    ).order_by(HardwareSale.total_amount.desc()).limit(5).all()

    items = sorted(
        [
            {
                "ref": reference,
                "amount": _float(amount),
                "date": sale_date.isoformat(),
                "section": "Boutique",
            }
            for reference, amount, sale_date in boutique_rows
        ]
        + [
            {
                "ref": reference,
                "amount": _float(amount),
                "date": sale_date.isoformat(),
                "section": "Hardware",
            }
            for reference, amount, sale_date in hardware_rows
        ],
        key=lambda row: row["amount"],
        reverse=True,
    )[:10]

    return {
        "intent": "top_transactions",
        "items": items,
        "summary": f"Top {len(items)} transactions from the last 7 days.",
    }


def handle_pending_inquiries():
    inquiries = WebsiteLoanInquiry.query.filter(
        WebsiteLoanInquiry.status == "new",
        WebsiteLoanInquiry.is_active == True,
    ).order_by(WebsiteLoanInquiry.submitted_at.desc()).limit(10).all()
    orders = WebsiteOrderRequest.query.filter(
        WebsiteOrderRequest.status == "new",
        WebsiteOrderRequest.is_active == True,
    ).order_by(WebsiteOrderRequest.submitted_at.desc()).limit(10).all()

    items = [
        {
            "type": "loan inquiry",
            "name": inquiry.full_name,
            "phone": inquiry.phone,
            "amount": _float(inquiry.requested_amount),
            "link": f"/website/loan-inquiries/{inquiry.id}",
        }
        for inquiry in inquiries
    ] + [
        {
            "type": "order request",
            "name": order.customer_name,
            "phone": order.customer_phone,
            "amount": "",
            "link": f"/website/order-requests/{order.id}",
        }
        for order in orders
    ]

    return {
        "intent": "pending_inquiries",
        "inquiry_count": len(inquiries),
        "order_count": len(orders),
        "items": items,
        "summary": f"{len(inquiries)} pending loan inquiries and {len(orders)} pending order requests are waiting for review.",
    }


def handle_projection_guidance():
    return {
        "intent": "projection_guidance",
        "items": [
            {
                "topic": "Available now",
                "status": "Live",
                "detail": "Yesterday summaries, current stock on hand, low stock alerts, overdue loans, branch comparisons, and pending leads.",
            },
            {
                "topic": "Forecasting",
                "status": "Not live yet",
                "detail": "Future sales, repayment forecasts, and automated demand projections are not enabled in the current build.",
            },
            {
                "topic": "Best next step",
                "status": "Ask this",
                "detail": "Use the assistant for today's operational questions, then we can add true projections as a separate feature.",
            },
        ],
        "summary": (
            "The assistant is currently strongest on live operational insight, not future forecasting. "
            "I can explain yesterday's business, current stock on hand, low stock risk, overdue exposure, "
            "branch performance, and pending website leads. Forecasting and projection models are not live yet."
        ),
    }


def build_snapshot_context():
    """Compact deterministic snapshot used for broader AI narration."""
    yesterday = handle_yesterday_summary()
    inventory = handle_inventory_overview()
    overdue = handle_overdue_loans()
    inquiries = handle_pending_inquiries()
    return {
        "yesterday_summary": {
            "date": yesterday["date"],
            "boutique_revenue": yesterday["boutique_revenue"],
            "hardware_revenue": yesterday["hardware_revenue"],
            "finance_repayments": yesterday["finance_repayments"],
            "total": yesterday["total"],
        },
        "inventory": {
            "total_skus": inventory["total_skus"],
            "total_units": inventory["total_units"],
            "low_stock_count": inventory["low_stock_count"],
        },
        "overdue_loans": {
            "count": overdue["count"],
            "total_balance": overdue["total_balance"],
        },
        "pending_items": {
            "loan_inquiries": inquiries["inquiry_count"],
            "order_requests": inquiries["order_count"],
        },
    }


INTENT_HANDLERS = {
    "overdue_loans": lambda message: handle_overdue_loans(),
    "inventory_overview": lambda message: handle_inventory_overview(),
    "low_stock": lambda message: handle_low_stock(),
    "yesterday_summary": lambda message: handle_yesterday_summary(),
    "branch_comparison": lambda message: handle_branch_comparison(),
    "user_activity": lambda message: handle_user_activity(),
    "loan_search": handle_loan_search,
    "top_transactions": lambda message: handle_top_transactions(),
    "pending_inquiries": lambda message: handle_pending_inquiries(),
    "projection_guidance": lambda message: handle_projection_guidance(),
}


def process_chat_message(message):
    """Process a manager chat message and return a structured response."""
    intent = classify_intent(message)
    handler = INTENT_HANDLERS.get(intent)

    if handler:
        try:
            data = handler(message)
        except Exception as exc:
            logger.warning("Chat intent handler %s failed: %s", intent, exc)
            return {
                "intent": intent,
                "error": True,
                "summary": "Sorry, I ran into a problem fetching that business data. Please try again.",
            }
    else:
        data = None

    if data and not data.get("error"):
        try:
            from app.utils.ai_client import ai_chat, is_chat_enabled

            if is_chat_enabled():
                ai_response = ai_chat(
                    (
                        f"User asked: {message}\n\n"
                        f"Here is the structured business data:\n{json.dumps(data, default=str)}\n\n"
                        "Give a concise, practical answer in 2 to 4 sentences. "
                        "Reference exact numbers from the data and mention only what is actually present. "
                        "Currency is UGX."
                    ),
                    system=(
                        "You are Denove Assistant, a business copilot for a Ugandan retail and microfinance company. "
                        "Answer only from the supplied data. Never invent figures. Keep answers direct, clear, and actionable. "
                        "Do not use markdown."
                    ),
                )
                if ai_response:
                    data["ai_narrative"] = ai_response
        except Exception:
            pass
        return data

    try:
        from app.utils.ai_client import ai_chat, is_chat_enabled

        if is_chat_enabled():
            ai_response = ai_chat(
                (
                    f"User question: {message}\n\n"
                    f"Business snapshot:\n{json.dumps(build_snapshot_context(), default=str)}\n\n"
                    "Answer helpfully if the question can be answered from this snapshot. "
                    "If not, explain what you can help with next."
                ),
                system=(
                    "You are Denove Assistant. Use only the provided business snapshot. "
                    "Never invent facts. Keep the answer short, natural, and practical. Do not use markdown."
                ),
            )
            if ai_response:
                return {
                    "intent": "general",
                    "summary": ai_response,
                    "ai_narrative": ai_response,
                }
    except Exception:
        pass

    return {
        "intent": "general",
        "summary": CAPABILITY_FALLBACK,
    }
