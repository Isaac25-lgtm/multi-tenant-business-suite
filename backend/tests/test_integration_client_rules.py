"""Rules confirmed by the client in the October 2026 questionnaire (PostgreSQL)."""
from datetime import timedelta
from decimal import Decimal

from app.extensions import db
from app.models.finance import GroupLoan, Loan, LoanClient, LoanPayment
from app.utils.timezone import get_local_today

D = Decimal


def _client(name='Borrower'):
    client = LoanClient(name=name, phone='0700000001')
    db.session.add(client)
    db.session.commit()
    return client


def _issue(http, client_id, days_ago=0, mode='monthly_accrual', rate='10', principal='1000000', **extra):
    issue = get_local_today() - timedelta(days=days_ago)
    http.post('/finance/loans/create', data={
        'client_id': str(client_id), 'principal': principal, 'interest_mode': mode, 'interest_rate': rate,
        'duration_weeks': '1', 'duration_type': 'months', 'issue_date': issue.isoformat(), **extra,
    })
    return Loan.query.order_by(Loan.id.desc()).first()


def test_new_loan_charges_first_month_on_issue_day(client, make_user, login):
    login(make_user())
    loan = _issue(client, _client().id)
    assert loan.interest_mode == 'monthly_accrual'
    assert loan.monthly_interest_amount == D('100000')
    assert loan.interest_amount == D('100000')            # Option B: owed from day one
    assert loan.balance == D('1100000')


def test_flat_rate_request_becomes_a_monthly_interest_loan(client, make_user, login):
    """"All loans must accumulate": the rate entered is always a monthly rate."""
    login(make_user())
    loan = _issue(client, _client().id, mode='flat_rate', rate='15')
    assert loan.interest_mode == 'monthly_accrual'
    assert loan.monthly_interest_amount == D('150000')


def test_backdated_payment_re_splits_later_payments(client, make_user, login):
    login(make_user())
    today = get_local_today()
    loan = _issue(client, _client().id, days_ago=100)     # 4 charges so far: owes 1,400,000

    client.post(f'/finance/loans/{loan.id}/pay', data={'amount': '400000', 'payment_date': today.isoformat()})
    db.session.expire_all()
    first = LoanPayment.query.one()
    assert (first.interest_amount, first.principal_amount) == (D('400000'), D('0'))

    # The manager then records an older payment: 500,000 received 20 days after issue.
    older_date = today - timedelta(days=80)
    client.post(f'/finance/loans/{loan.id}/pay', data={'amount': '500000', 'payment_date': older_date.isoformat()})
    db.session.expire_all()
    older = LoanPayment.query.filter_by(payment_date=older_date).one()
    later = LoanPayment.query.filter_by(payment_date=today).one()
    loan = db.session.get(Loan, loan.id)

    assert (older.interest_amount, older.principal_amount) == (D('100000'), D('400000'))
    # Interest after that is charged on 600,000: three months at 60,000.
    assert loan.interest_amount == D('280000')
    assert (later.interest_amount, later.principal_amount) == (D('180000'), D('220000'))
    assert loan.balance == D('380000')
    assert loan.outstanding_principal == D('380000')


def test_only_managers_can_delete_loans(client, make_user, login):
    officer = make_user('officer', role='finance')
    manager = make_user('boss', role='manager')
    login(manager)
    loan = _issue(client, _client().id)
    group = GroupLoan(group_name='Savers', member_count=5, principal=D('500000'), interest_rate=D('20'),
                      interest_amount=D('100000'), total_amount=D('600000'), amount_per_period=D('100000'),
                      total_periods=6, balance=D('600000'), amount_paid=D('0'), status='active',
                      issue_date=get_local_today(), due_date=get_local_today() + timedelta(days=180))
    db.session.add(group)
    db.session.commit()

    login(officer)
    client.post(f'/finance/loans/{loan.id}/delete')
    client.post(f'/finance/group-loans/{group.id}/delete')
    db.session.expire_all()
    assert db.session.get(Loan, loan.id).is_deleted is False
    assert db.session.get(GroupLoan, group.id).is_deleted is False

    login(manager)
    client.post(f'/finance/loans/{loan.id}/delete')
    db.session.expire_all()
    assert db.session.get(Loan, loan.id).is_deleted is True


def test_convert_open_flat_loans_to_monthly_interest(db_app):
    today = get_local_today()
    borrower = _client()

    def flat_loan(days_ago, status, balance, paid=D('0')):
        issue = today - timedelta(days=days_ago)
        loan = Loan(client_id=borrower.id, principal=D('1000000'), interest_rate=D('15'), interest_mode='flat_rate',
                    interest_amount=D('150000'), total_amount=D('1150000'), amount_paid=paid,
                    principal_paid=min(paid, D('1000000')), interest_paid=max(paid - D('1000000'), D('0')),
                    balance=balance, duration_weeks=4, duration_type='weeks', issue_date=issue,
                    due_date=issue + timedelta(days=28), status=status,
                    settled_on=today - timedelta(days=5) if status == 'paid' else None)
        db.session.add(loan)
        db.session.flush()
        return loan

    open_loan = flat_loan(70, 'overdue', D('1000000'), paid=D('150000'))
    # Its one payment was migrated long ago as "all principal".
    db.session.add(LoanPayment(loan_id=open_loan.id, payment_date=today - timedelta(days=40), amount=D('150000'),
                               principal_amount=D('150000'), interest_amount=D('0'), payment_type='legacy',
                               balance_after=D('1000000')))
    paid_loan = flat_loan(200, 'paid', D('0'), paid=D('1150000'))
    db.session.commit()

    runner = db_app.test_cli_runner()
    dry = runner.invoke(args=['finance-convert-flat-loans'])
    assert 'Dry run' in dry.output
    db.session.expire_all()
    assert db.session.get(Loan, open_loan.id).interest_mode == 'flat_rate'      # nothing saved

    applied = runner.invoke(args=['finance-convert-flat-loans', '--apply'])
    assert 'Applied.' in applied.output
    db.session.expire_all()
    converted = db.session.get(Loan, open_loan.id)
    payment = LoanPayment.query.filter_by(loan_id=open_loan.id).one()

    assert converted.interest_mode == 'monthly_accrual'
    assert converted.monthly_interest_amount == D('150000')
    assert (payment.interest_amount, payment.principal_amount) == (D('150000'), D('0'))   # interest first
    assert converted.interest_amount == D('450000')       # issue + two monthly dates at 15%
    assert converted.balance == D('1300000')

    untouched = db.session.get(Loan, paid_loan.id)
    assert (untouched.interest_mode, untouched.status, untouched.balance) == ('flat_rate', 'paid', D('0'))
