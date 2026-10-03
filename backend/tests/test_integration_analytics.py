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
                                       'description': 'Future', 'category': 'other', 'business_unit': 'shared'})
    client.post('/expenses/add', data={'expense_date': today.isoformat(), 'amount': '0',
                                       'description': 'Zero', 'category': 'other', 'business_unit': 'shared'})
    assert Expense.query.count() == 0

    client.post('/expenses/add', data={'expense_date': today.isoformat(), 'amount': '5000',
                                       'description': 'Airtime', 'category': 'communications', 'business_unit': 'shared'})
    expense = Expense.query.one()
    client.post(f'/expenses/{expense.id}/delete', data={'reason': 'duplicate entry'})
    db.session.expire_all()
    assert db.session.get(Expense, expense.id).is_deleted is True
    assert period_summary(today, today)['expenses'] == 0


def test_expenses_are_manager_only(client, make_user, login):
    login(make_user('shop', role='boutique'))
    response = client.post('/expenses/add', data={'expense_date': get_local_today().isoformat(), 'amount': '5000',
                                                   'description': 'Airtime', 'category': 'other', 'business_unit': 'shared'})
    assert response.status_code == 302
    assert Expense.query.count() == 0


def test_group_payments_count_as_interest_only_after_principal(db_app):
    today = get_local_today()
    group = GroupLoan(group_name='Savers', member_count=5, principal=D('500000'), interest_rate=D('20'),
                      interest_amount=D('100000'), total_amount=D('600000'), amount_per_period=D('100000'),
                      total_periods=6, balance=D('600000'), amount_paid=D('0'), periods_paid=0, status='active',
                      issue_date=today - timedelta(days=60), due_date=today + timedelta(days=120))
    db.session.add(group)
    db.session.flush()
    db.session.add(GroupLoanPayment(group_loan_id=group.id, payment_date=today - timedelta(days=10),
                                    amount=D('450000'), balance_after=D('150000')))
    db.session.add(GroupLoanPayment(group_loan_id=group.id, payment_date=today,
                                    amount=D('100000'), balance_after=D('50000')))
    db.session.commit()

    assert group_interest_collected(today, today) == D('50000')               # 450k+100k crosses 500k principal
    assert group_interest_collected(today - timedelta(days=10), today - timedelta(days=10)) == 0


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
