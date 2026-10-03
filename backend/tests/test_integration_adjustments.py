"""Adjustments ledger, receipt integrity and group period tracking (PostgreSQL)."""
from datetime import timedelta
from decimal import Decimal

from app.extensions import db
from app.models.boutique import BoutiqueSale, BoutiqueStock
from app.models.finance import GroupLoan, Loan, LoanAdjustment, LoanClient
from app.models.user import AuditLog
from app.utils.timezone import get_local_today

D = Decimal


def _monthly_loan(days_ago=65):
    client = LoanClient(name='Borrower', phone='0700000001')
    db.session.add(client)
    db.session.flush()
    issue = get_local_today() - timedelta(days=days_ago)
    loan = Loan(
        client_id=client.id, principal=D('1000000'), interest_rate=D('10'),
        interest_mode='monthly_accrual', monthly_interest_amount=D('100000'),
        interest_amount=D('0'), total_amount=D('1000000'), amount_paid=D('0'),
        balance=D('1000000'), duration_weeks=1, duration_type='months',
        issue_date=issue, due_date=issue + timedelta(days=30), status='active',
    )
    db.session.add(loan)
    db.session.commit()
    return loan


def _group():
    group = GroupLoan(group_name='Savers', member_count=5, principal=D('500000'), interest_rate=D('20'),
                      interest_amount=D('100000'), total_amount=D('600000'), amount_per_period=D('100000'),
                      total_periods=6, balance=D('600000'), amount_paid=D('0'), periods_paid=0, status='active',
                      issue_date=get_local_today(), due_date=get_local_today() + timedelta(days=180))
    db.session.add(group)
    db.session.commit()
    return group


def _adjust(client, url, adjustment_type, amount, reason='Agreed with management'):
    return client.post(url, data={'adjustment_type': adjustment_type, 'amount': str(amount),
                                  'reason': reason, 'effective_date': get_local_today().isoformat()})


def test_interest_discount_reduces_balance_and_is_reversible(client, make_user, login):
    login(make_user())
    loan = _monthly_loan()  # two charges: owes 1,200,000
    _adjust(client, f'/finance/loans/{loan.id}/adjustments', 'interest_discount', 50000)
    db.session.expire_all()
    loan = db.session.get(Loan, loan.id)
    assert loan.balance == D('1150000')
    assert loan.outstanding_interest == D('150000')
    assert loan.total_amount == D('1200000')      # current due is unchanged by a discount

    adjustment = LoanAdjustment.query.one()
    client.post(f'/finance/adjustments/{adjustment.id}/reverse', data={'reason': 'entered on wrong loan'})
    db.session.expire_all()
    assert db.session.get(Loan, loan.id).balance == D('1200000')
    assert db.session.get(LoanAdjustment, adjustment.id).is_reversed is True


def test_discount_cannot_exceed_interest_owed(client, make_user, login):
    login(make_user())
    loan = _monthly_loan()
    _adjust(client, f'/finance/loans/{loan.id}/adjustments', 'interest_waiver', 250000)
    assert LoanAdjustment.query.count() == 0
    db.session.expire_all()
    assert db.session.get(Loan, loan.id).balance == D('1200000')


def test_full_waiver_and_write_off_settle_the_loan(client, make_user, login):
    login(make_user())
    loan = _monthly_loan()
    _adjust(client, f'/finance/loans/{loan.id}/adjustments', 'interest_waiver', 200000)
    _adjust(client, f'/finance/loans/{loan.id}/adjustments', 'principal_write_off', 1000000)
    db.session.expire_all()
    loan = db.session.get(Loan, loan.id)
    assert loan.balance == 0
    assert loan.status == 'paid'
    assert loan.settled_on == get_local_today()


def test_charge_increases_balance(client, make_user, login):
    login(make_user())
    loan = _monthly_loan()
    _adjust(client, f'/finance/loans/{loan.id}/adjustments', 'charge', 30000)
    db.session.expire_all()
    loan = db.session.get(Loan, loan.id)
    assert loan.balance == D('1230000')
    assert loan.total_amount == D('1230000')


def test_adjustments_are_manager_only(client, make_user, login):
    login(make_user('officer', role='finance'))
    loan = _monthly_loan()
    _adjust(client, f'/finance/loans/{loan.id}/adjustments', 'interest_discount', 50000)
    assert LoanAdjustment.query.count() == 0


def test_group_adjustment(client, make_user, login):
    login(make_user())
    group = _group()
    _adjust(client, f'/finance/group-loans/{group.id}/adjustments', 'interest_discount', 40000)
    db.session.expire_all()
    group = db.session.get(GroupLoan, group.id)
    assert group.balance == D('560000')


def test_group_periods_follow_money_paid(client, make_user, login):
    login(make_user())
    group = _group()
    today = get_local_today().isoformat()

    client.post(f'/finance/group-loans/{group.id}/pay', data={'amount': '50000', 'payment_date': today})
    db.session.expire_all()
    assert db.session.get(GroupLoan, group.id).periods_paid == 0      # half a period is not a period

    client.post(f'/finance/group-loans/{group.id}/pay', data={'amount': '200000', 'payment_date': today})
    db.session.expire_all()
    assert db.session.get(GroupLoan, group.id).periods_paid == 2


def _boutique_sale(client):
    stock = BoutiqueStock(item_name='Dress', branch='K', quantity=5, initial_quantity=5, cost_price=D('50000'),
                          min_selling_price=D('60000'), max_selling_price=D('90000'), is_active=True)
    db.session.add(stock)
    db.session.commit()
    client.post('/boutique/sales/create', data={
        'sale_date': get_local_today().isoformat(), 'payment_type': 'full',
        'item_id[]': [str(stock.id)], 'quantity[]': ['1'], 'price[]': ['80000'],
    })
    return BoutiqueSale.query.one()


def test_staff_cannot_issue_receipt_with_different_amounts(client, make_user, login):
    login(make_user('shop', role='boutique', boutique_branch='K'), boutique_branch='K')
    sale = _boutique_sale(client)
    form = {'item_name[]': ['Dress'], 'quantity[]': ['1'], 'price[]': ['20000'], 'amount_paid': '20000'}
    response = client.post(f'/boutique/sales/{sale.id}/receipt', data=form)
    assert response.status_code == 302                     # redirected back, no PDF
    renamed = {'item_name[]': ['Evening dress'], 'quantity[]': ['1'], 'price[]': ['80000'], 'amount_paid': '80000'}
    response = client.post(f'/boutique/sales/{sale.id}/receipt', data=renamed)
    assert response.mimetype == 'application/pdf'          # descriptions may change


def test_manager_edited_receipt_is_audited(client, make_user, login):
    login(make_user(), boutique_branch='K')
    sale = _boutique_sale(client)
    form = {'item_name[]': ['Dress'], 'quantity[]': ['1'], 'price[]': ['70000'], 'amount_paid': '70000'}
    response = client.post(f'/boutique/sales/{sale.id}/receipt', data=form)
    assert response.mimetype == 'application/pdf'
    assert AuditLog.query.filter_by(entity='receipt', action='edit', entity_id=sale.id).count() == 1


def test_stock_photo_upload_works(client, make_user, login, db_app):
    """Regression: uploading a product photo on stock edit used to crash (NameError)."""
    import io
    import os

    from PIL import Image

    from app.models.website import ProductImage

    login(make_user(), boutique_branch='K')
    stock = BoutiqueStock(item_name='Dress', branch='K', quantity=5, initial_quantity=5, cost_price=D('50000'),
                          min_selling_price=D('60000'), max_selling_price=D('90000'), is_active=True)
    db.session.add(stock)
    db.session.commit()

    image = io.BytesIO()
    Image.new('RGB', (8, 8), (200, 50, 50)).save(image, format='PNG')
    image.seek(0)
    client.post(f'/boutique/stock/{stock.id}/edit', data={
        'item_name': 'Dress', 'unit': 'pieces', 'product_images': (image, 'dress.png'),
    }, content_type='multipart/form-data')

    saved = ProductImage.query.filter_by(product_type='boutique', product_id=stock.id).all()
    assert len(saved) == 1
    path = os.path.join(db_app.static_folder, saved[0].image_url.split('/static/', 1)[1])
    assert os.path.exists(path)
    os.remove(path)
