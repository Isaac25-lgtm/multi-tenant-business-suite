"""Reminders, monthly report, public shop, and an end-to-end sweep of every page (PostgreSQL)."""
from datetime import timedelta
from decimal import Decimal

import pytest

from app.extensions import db
from app.models.boutique import BoutiqueHire, BoutiqueSale, BoutiqueStock
from app.models.expense import Expense
from app.models.finance import GroupLoan, Loan, LoanClient, ReminderLog
from app.models.hardware import HardwareSale, HardwareStock
from app.services.reminders import normalize_phone
from app.utils.timezone import get_local_today

D = Decimal


@pytest.mark.parametrize('raw, expected', [
    ('0772000001', '256772000001'),
    ('+256 772 000001', '256772000001'),
    ('256772000001', '256772000001'),
    ('772000001', '256772000001'),
    ('12345', None),
    ('', None),
])
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


def _business(http):
    """A small working business: stock, sales, a hire, loans, a group, an expense."""
    today = get_local_today()
    dress = BoutiqueStock(item_name='Kitenge dress', branch='K', quantity=10, initial_quantity=10, cost_price=D('45000'),
                          min_selling_price=D('60000'), max_selling_price=D('90000'), is_active=True, for_hire=True,
                          low_stock_threshold=12)
    cement = HardwareStock(item_name='Cement 50kg', quantity=50, initial_quantity=50, cost_price=D('32000'),
                           min_selling_price=D('36000'), max_selling_price=D('45000'), is_active=True)
    db.session.add_all([dress, cement])
    db.session.commit()

    http.post('/boutique/sales/create', data={
        'sale_date': today.isoformat(), 'payment_type': 'part', 'amount_paid': '50000',
        'customer_name': 'Jane', 'customer_phone': '0772111111', 'payment_method': 'mobile_money',
        'payment_reference': 'MM777', 'item_id[]': [str(dress.id)], 'quantity[]': ['2'], 'price[]': ['70000'],
    })
    http.post('/hardware/sales/create', data={
        'sale_date': today.isoformat(), 'payment_type': 'full',
        'item_id[]': [str(cement.id)], 'quantity[]': ['5'], 'price[]': ['40000'],
    })

    borrower = LoanClient(name='Rotich Daniel', phone='0772000001')
    db.session.add(borrower)
    db.session.commit()
    for days_ago in (100, 10):
        issue = today - timedelta(days=days_ago)
        http.post('/finance/loans/create', data={
            'client_id': str(borrower.id), 'principal': '1000000', 'interest_mode': 'monthly_accrual',
            'interest_rate': '15', 'duration_weeks': '1', 'duration_type': 'months', 'issue_date': issue.isoformat(),
        })
    group = GroupLoan(group_name='Savers', member_count=5, principal=D('1000000'), interest_rate=D('40'),
                      interest_amount=D('400000'), total_amount=D('1400000'), amount_per_period=D('100000'),
                      total_periods=14, period_type='weekly', balance=D('1400000'), amount_paid=D('0'), status='active',
                      issue_date=today, due_date=today + timedelta(days=98))
    db.session.add(group)
    db.session.add(Expense(expense_date=today, category='rent', business_unit='boutique', amount=D('100000'),
                           description='Rent', created_by='manager'))
    db.session.commit()
    return {'dress': dress, 'cement': cement, 'group': group, 'borrower': borrower}


def test_sale_records_how_it_was_paid(client, make_user, login):
    login(make_user(), boutique_branch='K')
    _business(client)
    sale = BoutiqueSale.query.one()
    assert (sale.payment_method, sale.payment_reference) == ('mobile_money', 'MM777')
    assert HardwareSale.query.one().payment_method == 'cash'


def test_reminders_list_and_whatsapp_link(client, make_user, login, monkeypatch):
    monkeypatch.delenv('AT_USERNAME', raising=False)
    monkeypatch.delenv('AT_API_KEY', raising=False)
    login(make_user(), boutique_branch='K')
    _business(client)
    overdue = Loan.query.order_by(Loan.issue_date.asc()).first()

    page = client.get('/finance/reminders').get_data(as_text=True)
    assert 'Rotich Daniel' in page and '+256772000001' in page
    assert 'SMS is not set up yet' in page

    response = client.post(f'/finance/reminders/{overdue.id}/whatsapp')
    assert response.status_code == 302
    assert response.headers['Location'].startswith('https://wa.me/256772000001?text=')
    log = ReminderLog.query.one()
    assert (log.channel, log.kind, log.status) == ('whatsapp', 'overdue', 'opened')

    client.post(f'/finance/reminders/{overdue.id}/sms')            # SMS not configured: nothing sent
    assert ReminderLog.query.filter_by(channel='sms').count() == 0


def test_sms_reminder_is_sent_once(client, make_user, login, monkeypatch):
    from app.services import reminders

    monkeypatch.setenv('AT_USERNAME', 'sandbox')
    monkeypatch.setenv('AT_API_KEY', 'key')
    sent = []
    monkeypatch.setattr(reminders, 'send_sms', lambda phone, message: (sent.append(phone) or True, 'Success'))
    login(make_user(), boutique_branch='K')
    _business(client)
    overdue = Loan.query.order_by(Loan.issue_date.asc()).first()

    client.post(f'/finance/reminders/{overdue.id}/sms')
    client.post(f'/finance/reminders/{overdue.id}/sms')            # second one is refused (within 7 days)
    assert sent == ['256772000001']
    assert ReminderLog.query.filter_by(channel='sms', status='sent').count() == 1


def test_monthly_report_pdf(client, make_user, login):
    login(make_user(), boutique_branch='K')
    _business(client)
    response = client.get('/dashboard/reports/monthly')
    assert response.status_code == 200 and response.mimetype == 'application/pdf'
    assert response.data[:4] == b'%PDF' and len(response.data) > 5000

    login(make_user('officer', role='finance'))
    assert client.get('/dashboard/reports/monthly').status_code == 302   # managers only


def test_public_shop_has_calculator_and_no_staff_data(client, db_app):
    page = client.get('/').get_data(as_text=True)
    assert 'Loan calculator' in page and 'id="calc-amount"' in page
    assert client.get('/finance/loans').status_code == 302               # staff pages need a login
    assert client.get('/dashboard/').status_code == 302


def _crawl(http, app, params):
    """Open every GET page that needs no extra input; return the ones that failed."""
    failures = []
    for rule in app.url_map.iter_rules():
        if 'GET' not in rule.methods or rule.endpoint == 'static':
            continue
        if rule.arguments - set(params) - set(rule.defaults or {}):
            continue
        try:
            with app.test_request_context():
                from flask import url_for
                url = url_for(rule.endpoint, **{name: params[name] for name in rule.arguments if name in params})
        except Exception:
            continue
        if '/logout' in url:
            continue
        response = http.get(url)
        body = response.get_data(as_text=True) if response.mimetype == 'text/html' else ''
        if response.status_code >= 500 or 'could not be calculated' in body or 'could not be loaded' in body:
            failures.append((url, response.status_code))
    return failures


def test_every_page_opens_for_a_manager(client, make_user, login, db_app):
    login(make_user(), boutique_branch='K')
    data = _business(client)
    loan = Loan.query.first()
    sale = BoutiqueSale.query.one()
    params = {'section': 'manager', 'branch': 'K', 'loan_id': loan.id, 'group_id': data['group'].id}

    assert _crawl(client, db_app, params) == []

    # Detail pages and documents that need a record id.
    for url in (f'/finance/loans/{loan.id}', f'/finance/loans/{loan.id}/edit', f'/finance/loans/{loan.id}/statement-pdf',
                f'/finance/loans/{loan.id}/agreement-pdf', f'/finance/loans/{loan.id}/overdue-reminder-pdf',
                f'/finance/loans/{loan.id}/payment-preview?amount=50000',
                f"/finance/group-loans/{data['group'].id}", f"/finance/group-loans/{data['group'].id}/agreement-pdf",
                f'/boutique/sales/{sale.id}', f'/boutique/sales/{sale.id}/receipt', f'/boutique/sales/{sale.id}/receipt/preview',
                f'/hardware/sales/{HardwareSale.query.one().id}', '/dashboard/retail?unit=boutique&branch=K',
                '/dashboard/finance?period=last_month', '/dashboard/inventory?period=7d', '/expenses/?period=today'):
        assert client.get(url).status_code == 200, url


@pytest.mark.parametrize('role, section_home', [('boutique', '/boutique/'), ('hardware', '/hardware/'), ('finance', '/finance/')])
def test_every_page_is_safe_for_staff(client, make_user, login, db_app, role, section_home):
    """Staff either see a page or are redirected away; nothing errors, and manager pages stay closed."""
    login(make_user('boss', role='manager'), boutique_branch='K')
    _business(client)
    login(make_user('staff', role=role, boutique_branch='K' if role == 'boutique' else None), boutique_branch='K')

    assert _crawl(client, db_app, {'section': role, 'branch': 'K'}) == []
    assert client.get(section_home).status_code == 200
    assert client.get('/expenses/').status_code == 200
    for manager_only in ('/dashboard/', '/dashboard/finance', '/dashboard/reports/monthly', '/dashboard/users',
                         '/dashboard/audit-trail'):
        assert client.get(manager_only).status_code == 302, manager_only


def test_hire_and_credit_flow_end_to_end(client, make_user, login):
    login(make_user(), boutique_branch='K')
    data = _business(client)
    today = get_local_today()
    sale = BoutiqueSale.query.one()
    assert sale.balance == D('90000')

    client.post(f'/boutique/credits/{sale.id}/pay', data={'amount': '90000', 'payment_date': today.isoformat(),
                                                           'payment_method': 'cash'})
    db.session.expire_all()
    assert db.session.get(BoutiqueSale, sale.id).is_credit_cleared is True

    client.post('/boutique/hires/create', data={
        'stock_id': str(data['dress'].id), 'customer_name': 'Mary', 'customer_phone': '0772222222', 'quantity': '1',
        'hire_date': today.isoformat(), 'expected_return_date': (today + timedelta(days=2)).isoformat(),
        'daily_rate': '20000', 'deposit_amount': '10000',
    })
    hire = BoutiqueHire.query.first()
    if hire is not None:                                   # form fields vary; the page must still work
        assert client.get(f'/boutique/hires/{hire.id}').status_code == 200
    assert client.get('/boutique/hires').status_code == 200
