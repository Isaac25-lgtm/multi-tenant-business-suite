"""Loan repayment reminders by SMS and WhatsApp.

SMS is sent through Africa's Talking and is only active when AT_USERNAME and
AT_API_KEY are configured. WhatsApp uses click-to-chat links (wa.me) that open
the conversation with the message filled in, so no paid API is needed; fully
automatic WhatsApp sending would require the WhatsApp Business API.

Every reminder is recorded in reminder_logs so a borrower is not reminded
twice on the same day, and overdue SMS reminders repeat at most weekly.
"""
import logging
import os
import re
from datetime import timedelta
from urllib.parse import quote

import requests

from app.extensions import db
from app.models.finance import Loan, ReminderLog
from app.utils.branding import get_company_display_name, get_site_settings

logger = logging.getLogger(__name__)

DUE_SOON_DAYS = 3
OVERDUE_REPEAT_DAYS = 7
AT_URL = 'https://api.africastalking.com/version1/messaging'


def normalize_phone(phone, country_code='256'):
    """Uganda-style numbers to international digits (2567XXXXXXXX), or None."""
    digits = re.sub(r'\D', '', str(phone or ''))
    if digits.startswith('00'):
        digits = digits[2:]
    if digits.startswith(country_code) and len(digits) == len(country_code) + 9:
        return digits
    if digits.startswith('0') and len(digits) == 10:
        return country_code + digits[1:]
    if len(digits) == 9:
        return country_code + digits
    return None


def sms_enabled():
    return bool(os.getenv('AT_USERNAME') and os.getenv('AT_API_KEY'))


def build_message(loan, kind, today):
    settings = get_site_settings()
    company = get_company_display_name(settings)
    name = (loan.client.name if loan.client else 'Customer').split()[0]
    balance = f"UGX {float(loan.balance or 0):,.0f}"
    due = loan.due_date.strftime('%d %b %Y')
    contact = (settings.contact_phone or '').strip()
    if kind == 'due_soon':
        days = (loan.due_date - today).days
        when = 'today' if days == 0 else ('tomorrow' if days == 1 else f'on {due}')
        text = f"Dear {name}, your {company} loan balance of {balance} is due {when}. Please pay on time. Thank you."
    else:
        days = (today - loan.due_date).days
        text = (f"Dear {name}, your {company} loan of {balance} was due on {due} and is {days} day"
                f"{'' if days == 1 else 's'} late. Interest is added every month until it is cleared. Please pay"
                f"{' or call ' + contact if contact else ''}.")
    return text


def due_reminders(today):
    """Open individual loans that are due within a few days or already overdue."""
    loans = Loan.query.filter(
        Loan.is_deleted == False,  # noqa: E712
        Loan.status.in_(['active', 'overdue']),
        Loan.balance > 0,
        Loan.due_date <= today + timedelta(days=DUE_SOON_DAYS),
    ).order_by(Loan.due_date.asc()).all()

    recent = {}
    for log in ReminderLog.query.filter(
        ReminderLog.loan_id.in_([loan.id for loan in loans] or [0]),
        ReminderLog.reminder_date >= today - timedelta(days=OVERDUE_REPEAT_DAYS),
    ).order_by(ReminderLog.created_at.asc()).all():
        recent.setdefault(log.loan_id, []).append(log)

    rows = []
    for loan in loans:
        kind = 'overdue' if loan.due_date < today else 'due_soon'
        phone = normalize_phone(loan.client.phone if loan.client else None)
        message = build_message(loan, kind, today)
        logs = recent.get(loan.id, [])
        sms_recent = [log for log in logs if log.channel == 'sms' and log.status == 'sent']
        rows.append({
            'loan': loan,
            'kind': kind,
            'days': (today - loan.due_date).days,
            'phone': phone,
            'message': message,
            'whatsapp_url': f"https://wa.me/{phone}?text={quote(message)}" if phone else None,
            'last': logs[-1] if logs else None,
            # due-soon: once; overdue: at most weekly
            'sms_allowed': bool(phone) and not sms_recent,
        })
    return rows


def record(loan, kind, channel, phone, message, status, today, sent_by=None, detail=None):
    db.session.add(ReminderLog(
        loan_id=loan.id, reminder_date=today, kind=kind, channel=channel, phone=phone,
        message=message, status=status, detail=(detail or '')[:255] or None, sent_by=sent_by,
    ))
    db.session.commit()


def send_sms(phone, message):
    """Send one SMS via Africa's Talking. Returns (ok, detail)."""
    if not sms_enabled():
        return False, 'SMS is not configured'
    data = {'username': os.getenv('AT_USERNAME'), 'to': f'+{phone}', 'message': message}
    if os.getenv('AT_SENDER_ID'):
        data['from'] = os.getenv('AT_SENDER_ID')
    try:
        response = requests.post(
            AT_URL, data=data, timeout=15,
            headers={'apiKey': os.getenv('AT_API_KEY'), 'Accept': 'application/json'},
        )
        if response.status_code >= 400:
            return False, f'provider returned {response.status_code}'
        recipients = (response.json().get('SMSMessageData') or {}).get('Recipients') or []
        status = recipients[0].get('status') if recipients else 'no recipient'
        return status == 'Success', status
    except (requests.RequestException, ValueError) as exc:
        logger.warning('SMS reminder failed: %s', exc.__class__.__name__)
        return False, exc.__class__.__name__


def send_reminder_sms(row, today, sent_by=None):
    ok, detail = send_sms(row['phone'], row['message'])
    record(row['loan'], row['kind'], 'sms', row['phone'], row['message'], 'sent' if ok else 'failed',
           today, sent_by=sent_by, detail=detail)
    return ok, detail
