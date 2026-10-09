"""Expenses, net profit, group interest income and manager analytics pages (PostgreSQL)."""
from datetime import timedelta
from decimal import Decimal

from app.extensions import db
from app.models.boutique import BoutiqueStock
from app.models.expense import Expense
from app.models.finance import GroupLoan, GroupLoanPayment, Loan, LoanClient
from app.services.business_metrics import group_interest_collected, manager_dashboard, period_summary
from app.utils.timezone import get_local_today

D = Decimal


def _sale(client, qty=1, price='80000', cost='50000'):
    stock = BoutiqueStock(item_name='Dress', branch='K', quantity=10, initial_quantity=10, cost_price=D(cost),
                          min_selling_price=D('60000'), max_selling_price=D('90000'), is_active=True,
                          low_stock_threshold=12)
    db.session.add(stock)
    db.session.commit()
    client.post('/boutique/sales/create', data={
        'sale_date': get_local_today().isoformat(), 'payment_type': 'full',
        'item_id[]': [str(stock.id)], 'quantity[]': [str(qty)], 'price[]': [price],
    })


def test_net_profit_hidden_until_expenses_exist_then_exact(client, make_user, login):
    login(make_user(), boutique_branch='K')
    today = get_local_today()
    _sale(client, qty=2, price='80000', cost='50000')        # gross profit 60,000
    assert manager_dashboard(today)['show_net_profit'] is False

    client.post('/expenses/add', data={'expense_date': today.isoformat(), 'amount': '15000', 'description': 'Transport',
                                       'category': 'transport', 'business_unit': 'boutique', 'payment_method': 'cash'})
    summary = period_summary(today, today)
    assert summary['expenses'] == D('15000')
    assert summary['net_profit'] == D('45000')
    assert manager_dashboard(today)['show_net_profit'] is True


def test_expense_validation_and_soft_delete(client, make_user, login):
    login(make_user())
    today = get_local_today()
    client.post('/expenses/add', data={'expense_date': (today + timedelta(days=1)).isoformat(), 'amount': '5000',
                                       'description': 'Future', 'category': 'other', 'business_unit': 'finance'})
    client.post('/expenses/add', data={'expense_date': today.isoformat(), 'amount': '0',
                                       'description': 'Zero', 'category': 'other', 'business_unit': 'finance'})
    client.post('/expenses/add', data={'expense_date': today.isoformat(), 'amount': '5000',
                                       'description': 'No shared pool', 'category': 'other', 'business_unit': 'shared'})
    assert Expense.query.count() == 0

    client.post('/expenses/add', data={'expense_date': today.isoformat(), 'amount': '5000',
                                       'description': 'Airtime', 'category': 'communications', 'business_unit': 'finance'})
    expense = Expense.query.one()
    client.post(f'/expenses/{expense.id}/delete', data={'reason': 'duplicate entry'})
    db.session.expire_all()
    assert db.session.get(Expense, expense.id).is_deleted is True
    assert period_summary(today, today)['expenses'] == 0


def test_staff_record_expenses_for_their_own_unit_only(client, make_user, login):
    login(make_user('shop', role='boutique'))
    today = get_local_today()
    base = {'expense_date': today.isoformat(), 'amount': '5000', 'description': 'Airtime', 'category': 'communications'}

    client.post('/expenses/add', data={**base, 'business_unit': 'hardware'})       # not their unit
    assert Expense.query.count() == 0
    client.post('/expenses/add', data={**base, 'expense_date': (today - timedelta(days=5)).isoformat(),
                                       'business_unit': 'boutique'})               # too old for staff
    assert Expense.query.count() == 0

    client.post('/expenses/add', data={**base, 'business_unit': 'boutique'})
    expense = Expense.query.one()
    assert expense.business_unit == 'boutique'
    assert client.get('/expenses/').status_code == 200

    client.post(f'/expenses/{expense.id}/delete', data={'reason': 'staff cannot delete'})
    db.session.expire_all()
    assert db.session.get(Expense, expense.id).is_deleted is False


def test_each_unit_carries_its_own_expenses(client, make_user, login):
    login(make_user(), boutique_branch='K')
    today = get_local_today()
    _sale(client, qty=2, price='80000', cost='50000')                              # boutique gross profit 60,000
    for unit, amount in (('boutique', '10000'), ('hardware', '4000')):
        client.post('/expenses/add', data={'expense_date': today.isoformat(), 'amount': amount, 'description': 'Cost',
                                           'category': 'other', 'business_unit': unit})
    summary = period_summary(today, today)
    assert summary['unit_profit']['boutique'] == D('50000')
    assert summary['unit_profit']['hardware'] == D('-4000')
    assert summary['net_profit'] == D('46000')


def test_group_payment_is_a_sum_of_principal_and_interest(db_app):
    today = get_local_today()
    group = GroupLoan(group_name='Savers', member_count=5, principal=D('1000000'), interest_rate=D('40'),
                      interest_amount=D('400000'), total_amount=D('1400000'), amount_per_period=D('100000'),
                      total_periods=14, balance=D('1100000'), amount_paid=D('300000'), periods_paid=3, status='active',
                      issue_date=today - timedelta(days=21), due_date=today + timedelta(days=77))
    db.session.add(group)
    db.session.flush()
    db.session.add(GroupLoanPayment(group_loan_id=group.id, payment_date=today - timedelta(days=7),
                                    amount=D('200000'), balance_after=D('1200000')))
    db.session.add(GroupLoanPayment(group_loan_id=group.id, payment_date=today,
                                    amount=D('100000'), balance_after=D('1100000')))
    db.session.commit()

    # Each 100,000 instalment carries 400/1400 interest = 28,571.
    assert group_interest_collected(today, today) == D('28571')
    assert group.outstanding_principal == D('785714')          # 1,000,000 - 300,000 x 1000/1400
    assert group.outstanding_principal + group.outstanding_interest == group.balance


def test_analytics_pages_render_with_data(client, make_user, login):
    login(make_user(), boutique_branch='K')
    _sale(client)
    loan_client = LoanClient(name='Borrower', phone='0700000001')
    db.session.add(loan_client)
    db.session.flush()
    issue = get_local_today() - timedelta(days=100)
    db.session.add(Loan(client_id=loan_client.id, principal=D('1000000'), interest_rate=D('10'),
                        interest_mode='flat_rate', interest_amount=D('100000'), total_amount=D('1100000'),
                        amount_paid=D('0'), balance=D('1100000'), duration_weeks=4, duration_type='weeks',
                        issue_date=issue, due_date=issue + timedelta(days=28), status='active'))
    db.session.commit()

    for url in ('/dashboard/', '/dashboard/summary', '/dashboard/retail?period=7d', '/dashboard/retail?unit=boutique&branch=K',
                '/dashboard/finance', '/dashboard/inventory', '/expenses/'):
        response = client.get(url)
        page = response.get_data(as_text=True)
        assert response.status_code == 200, url
        assert 'could not be calculated' not in page, url

    finance_page = client.get('/dashboard/finance').get_data(as_text=True)
    assert 'Over 90 days overdue' in finance_page
    assert '100.0%' in finance_page                      # PAR30: the only loan is 72 days late
    assert 'Borrower' in finance_page


def test_analytics_pages_are_manager_only(client, make_user, login):
    login(make_user('officer', role='finance'))
    for url in ('/dashboard/retail', '/dashboard/finance', '/dashboard/inventory', '/dashboard/summary'):
        assert client.get(url).status_code == 302, url
