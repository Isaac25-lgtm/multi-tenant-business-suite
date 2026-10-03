"""PostgreSQL integration tests for the Phase 1 accounting and integrity fixes.

Skipped unless TEST_DATABASE_URL points at a dedicated test database.
"""
from datetime import timedelta
from decimal import Decimal

from app.extensions import db
from app.models.boutique import (
    BoutiqueCreditPayment, BoutiqueSale, BoutiqueSaleItem, BoutiqueStock,
)
from app.models.finance import GroupLoan, GroupLoanPayment, Loan, LoanClient, LoanPayment
from app.services.business_metrics import growth_pct, period_summary
from app.services.loan_accounting import summarize_portfolio
from app.utils.timezone import get_local_today

D = Decimal


def _stock(cost='50000', qty=10, branch='K'):
    item = BoutiqueStock(
        item_name='Dress', branch=branch, quantity=qty, initial_quantity=qty,
        cost_price=D(cost), min_selling_price=D('60000'), max_selling_price=D('90000'),
        is_active=True,
    )
    db.session.add(item)
    db.session.commit()
    return item


def _sell(client, stock, qty=2, price='80000', payment_type='full', amount_paid=None, sale_date=None):
    data = {
        'sale_date': (sale_date or get_local_today()).isoformat(),
        'payment_type': payment_type,
        'item_id[]': [str(stock.id)],
        'quantity[]': [str(qty)],
        'price[]': [price],
    }
    if payment_type == 'part':
        data.update({'amount_paid': amount_paid or '0', 'customer_name': 'Jane', 'customer_phone': '0700000000'})
    return client.post('/boutique/sales/create', data=data)


def _monthly_loan(issue_date):
    client = LoanClient(name='Borrower', phone='0700000001')
    db.session.add(client)
    db.session.flush()
    loan = Loan(
        client_id=client.id, principal=D('1000000'), interest_rate=D('10'),
        interest_mode='monthly_accrual', monthly_interest_amount=D('100000'),
        interest_amount=D('0'), total_amount=D('1000000'), amount_paid=D('0'),
        balance=D('1000000'), duration_weeks=1, duration_type='months',
        issue_date=issue_date, due_date=issue_date + timedelta(days=30), status='active',
    )
    db.session.add(loan)
    db.session.commit()
    return loan


# --- Retail -------------------------------------------------------------------

def test_part_credit_sale_counts_full_sale_but_only_cash_received(client, make_user, login):
    manager = make_user()
    login(manager, boutique_branch='K')
    stock = _stock()
    today = get_local_today()

    _sell(client, stock, qty=2, price='80000', payment_type='part', amount_paid='60000')
    summary = period_summary(today, today)
    assert summary['sales_value'] == D('160000')
    assert summary['cash_breakdown']['retail_at_sale'] == D('60000')
    assert summary['boutique']['credit_sales'] == D('100000')

    # A later credit payment is cash on its own date and is not a new sale.
    sale = BoutiqueSale.query.one()
    tomorrow = today + timedelta(days=1)
    db.session.add(BoutiqueCreditPayment(sale_id=sale.id, payment_date=tomorrow, amount=D('40000'),
                                         remaining_balance=D('60000')))
    sale.amount_paid = D('100000')
    sale.balance = D('60000')
    db.session.commit()

    again_today = period_summary(today, today)
    assert again_today['cash_breakdown']['retail_at_sale'] == D('60000')   # unchanged by the later payment
    next_day = period_summary(tomorrow, tomorrow)
    assert next_day['sales_value'] == 0
    assert next_day['cash_breakdown']['retail_credit_collections'] == D('40000')


def test_profit_uses_cost_recorded_at_sale(client, make_user, login):
    manager = make_user()
    login(manager, boutique_branch='K')
    stock = _stock(cost='50000')
    today = get_local_today()

    _sell(client, stock, qty=2, price='80000')
    item = BoutiqueSaleItem.query.one()
    assert item.unit_cost_at_sale == D('50000')
    assert period_summary(today, today)['gross_profit'] == D('60000')

    stock.cost_price = D('65000')
    db.session.commit()
    assert period_summary(today, today)['gross_profit'] == D('60000')


def test_items_missing_from_stock_do_not_inflate_the_sale_total(client, make_user, login):
    manager = make_user()
    login(manager, boutique_branch='K')
    good = _stock()
    other_branch = _stock(branch='M')

    client.post('/boutique/sales/create', data={
        'sale_date': get_local_today().isoformat(), 'payment_type': 'full',
        'item_id[]': [str(good.id), str(other_branch.id)],
        'quantity[]': ['1', '1'], 'price[]': ['80000', '80000'],
    })
    sale = BoutiqueSale.query.one()
    assert sale.total_amount == D('80000')
    assert sale.items.count() == 1


def test_deleting_a_sale_twice_restores_stock_once(client, make_user, login):
    manager = make_user()
    login(manager, boutique_branch='K')
    stock = _stock(qty=10)
    _sell(client, stock, qty=3)
    sale = BoutiqueSale.query.one()
    assert db.session.get(BoutiqueStock, stock.id).quantity == 7

    client.post(f'/boutique/sales/{sale.id}/delete')
    client.post(f'/boutique/sales/{sale.id}/delete')
    db.session.expire_all()
    assert db.session.get(BoutiqueStock, stock.id).quantity == 10


def test_duplicate_credit_payment_is_rejected(client, make_user, login):
    manager = make_user()
    login(manager, boutique_branch='K')
    stock = _stock()
    _sell(client, stock, qty=2, price='80000', payment_type='part', amount_paid='0')
    sale = BoutiqueSale.query.one()

    form = {'amount': '10000', 'payment_date': get_local_today().isoformat()}
    client.post(f'/boutique/credits/{sale.id}/pay', data=form)
    client.post(f'/boutique/credits/{sale.id}/pay', data=form)
    assert BoutiqueCreditPayment.query.filter_by(sale_id=sale.id).count() == 1
    db.session.expire_all()
    assert db.session.get(BoutiqueSale, sale.id).balance == D('150000')


# --- Finance ------------------------------------------------------------------

def test_duplicate_loan_payment_is_rejected_and_reversal_restores_balance(client, make_user, login):
    manager = make_user()
    login(manager)
    loan = _monthly_loan(get_local_today() - timedelta(days=65))  # two charges so far
    form = {'amount': '50000', 'payment_date': get_local_today().isoformat()}

    client.post(f'/finance/loans/{loan.id}/pay', data=form)
    client.post(f'/finance/loans/{loan.id}/pay', data=form)
    payments = LoanPayment.query.filter_by(loan_id=loan.id, is_deleted=False).all()
    assert len(payments) == 1
    db.session.expire_all()
    assert db.session.get(Loan, loan.id).balance == D('1150000')

    client.post(f'/finance/loans/{loan.id}/payments/{payments[0].id}/reverse', data={'reason': 'entered twice'})
    db.session.expire_all()
    reversed_payment = db.session.get(LoanPayment, payments[0].id)
    assert reversed_payment.is_deleted is True
    assert reversed_payment.reversed_by == 'manager'
    assert db.session.get(Loan, loan.id).balance == D('1200000')


def test_reversal_is_manager_only(client, make_user, login):
    staff = make_user('officer', role='finance')
    login(staff)
    loan = _monthly_loan(get_local_today() - timedelta(days=40))
    client.post(f'/finance/loans/{loan.id}/pay', data={'amount': '50000',
                                                        'payment_date': get_local_today().isoformat()})
    payment = LoanPayment.query.filter_by(loan_id=loan.id).one()

    client.post(f'/finance/loans/{loan.id}/payments/{payment.id}/reverse', data={'reason': 'trying anyway'})
    db.session.expire_all()
    assert db.session.get(LoanPayment, payment.id).is_deleted is False


def test_paid_loan_stays_paid_after_months_pass(client, make_user, login):
    manager = make_user()
    login(manager)
    loan = _monthly_loan(get_local_today() - timedelta(days=40))  # one charge: owes 1,100,000
    client.post(f'/finance/loans/{loan.id}/pay', data={'amount': '1100000',
                                                        'payment_date': get_local_today().isoformat()})
    db.session.expire_all()
    loan = db.session.get(Loan, loan.id)
    assert loan.status == 'paid' and loan.settled_on == get_local_today()

    from app.services.loan_accounting import refresh_loan_state
    refresh_loan_state(loan, get_local_today() + timedelta(days=200))
    assert loan.balance == 0 and loan.status == 'paid'


def test_overview_combines_individual_and_group_principal(db_app):
    _monthly_loan(get_local_today())
    group = GroupLoan(group_name='Savers', member_count=5, principal=D('500000'), interest_rate=D('20'),
                      interest_amount=D('100000'), total_amount=D('600000'), amount_per_period=D('100000'),
                      total_periods=6, balance=D('600000'), amount_paid=D('0'), status='active',
                      issue_date=get_local_today(), due_date=get_local_today() + timedelta(days=180))
    db.session.add(group)
    db.session.commit()

    portfolio = summarize_portfolio()
    assert portfolio['individual_principal'] == D('1000000')
    assert portfolio['group_principal'] == D('500000')
    assert portfolio['combined_principal'] == D('1500000')


def test_loan_list_shows_subtotals(client, make_user, login):
    manager = make_user()
    login(manager)
    _monthly_loan(get_local_today())
    _monthly_loan(get_local_today())
    page = client.get('/finance/loans').get_data(as_text=True)
    assert 'Subtotal' in page
    assert '2,000,000' in page


def test_group_payment_duplicate_and_reversal(client, make_user, login):
    manager = make_user()
    login(manager)
    group = GroupLoan(group_name='Savers', member_count=5, principal=D('500000'), interest_rate=D('20'),
                      interest_amount=D('100000'), total_amount=D('600000'), amount_per_period=D('100000'),
                      total_periods=6, balance=D('600000'), amount_paid=D('0'), periods_paid=0, status='active',
                      issue_date=get_local_today(), due_date=get_local_today() + timedelta(days=180))
    db.session.add(group)
    db.session.commit()

    form = {'amount': '100000', 'periods_covered': '1', 'payment_date': get_local_today().isoformat()}
    client.post(f'/finance/group-loans/{group.id}/pay', data=form)
    client.post(f'/finance/group-loans/{group.id}/pay', data=form)
    payments = GroupLoanPayment.query.filter_by(group_loan_id=group.id).all()
    assert len(payments) == 1

    client.post(f'/finance/group-loans/{group.id}/payments/{payments[0].id}/reverse', data={'reason': 'wrong group'})
    db.session.expire_all()
    group = db.session.get(GroupLoan, group.id)
    assert group.balance == D('600000') and group.periods_paid == 0


# --- Dashboard and privacy ----------------------------------------------------

def test_growth_never_divides_by_zero():
    assert growth_pct(100, 0) is None
    assert growth_pct(0, 0) is None
    assert growth_pct(150, 100) == 50.0


def test_dashboard_renders_with_real_figures(client, make_user, login):
    manager = make_user()
    login(manager, boutique_branch='K')
    _sell(client, _stock(), qty=1, price='80000')
    page = client.get('/dashboard/').get_data(as_text=True)
    assert 'Sales today' in page and 'Cash received today' in page
    assert 'UGX 80,000' in page
    assert 'could not be calculated' not in page


def test_private_uploads_are_not_publicly_served(client, db_app):
    import os

    folder = os.path.join(db_app.root_path, 'static', 'uploads', 'collateral')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, 'loan_999_test_id.pdf')
    with open(path, 'wb') as handle:
        handle.write(b'%PDF-1.4 test')
    try:
        for url in ('/static/uploads/collateral/loan_999_test_id.pdf',
                    '/static/uploads/./collateral/loan_999_test_id.pdf',
                    '/static/uploads//collateral/loan_999_test_id.pdf',
                    '/static/uploads/Collateral/loan_999_test_id.pdf'):
            assert client.get(url).status_code == 404, url
        assert client.get('/static/images/norongir-logo.png').status_code == 200
    finally:
        os.remove(path)
