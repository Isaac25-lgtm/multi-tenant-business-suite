from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
from app.models.finance import LoanClient, Loan, LoanPayment, GroupLoan, GroupLoanPayment, LoanDocument
from app.modules.auth import login_required, log_action
from app.extensions import db
from app.utils.timezone import get_local_today
from datetime import date, timedelta
from decimal import Decimal
from werkzeug.utils import secure_filename
import os

finance_bp = Blueprint('finance', __name__)

PERIOD_DAYS = {'weekly': 7, 'bi-weekly': 14, 'monthly': 30, 'bi-monthly': 60}


@finance_bp.route('/')
@login_required('finance')
def index():
    """Finance overview"""
    today = get_local_today()

    # Update loan statuses
    Loan.query.filter(
        Loan.is_deleted == False, Loan.status.in_(['active', 'due_soon']),
        Loan.due_date < today, Loan.balance > 0
    ).update({'status': 'overdue'}, synchronize_session=False)

    GroupLoan.query.filter(
        GroupLoan.is_deleted == False, GroupLoan.status == 'active',
        GroupLoan.due_date < today, GroupLoan.balance > 0
    ).update({'status': 'overdue'}, synchronize_session=False)
    db.session.commit()

    active_loans = Loan.query.filter(Loan.is_deleted == False, Loan.balance > 0).count()
    active_groups = GroupLoan.query.filter(GroupLoan.is_deleted == False, GroupLoan.balance > 0).count()
    overdue_loans = Loan.query.filter(Loan.is_deleted == False, Loan.status == 'overdue').count()
    overdue_groups = GroupLoan.query.filter(GroupLoan.is_deleted == False, GroupLoan.status == 'overdue').count()

    total_outstanding = float(db.session.query(db.func.sum(Loan.balance)).filter(
        Loan.is_deleted == False, Loan.balance > 0).scalar() or 0)
    total_outstanding += float(db.session.query(db.func.sum(GroupLoan.balance)).filter(
        GroupLoan.is_deleted == False, GroupLoan.balance > 0).scalar() or 0)

    return render_template('finance/index.html',
        active_loans=active_loans, active_groups=active_groups,
        overdue_loans=overdue_loans, overdue_groups=overdue_groups,
        total_outstanding=total_outstanding
    )


# ============ CLIENTS ============

@finance_bp.route('/clients')
@login_required('finance')
def clients():
    all_clients = LoanClient.query.filter_by(is_active=True).order_by(LoanClient.name).all()
    return render_template('finance/clients.html', clients=all_clients)


@finance_bp.route('/clients/add', methods=['POST'])
@login_required('finance')
def add_client():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    if not name or not phone:
        flash('Name and phone required', 'error')
        return redirect(url_for('finance.clients'))

    client = LoanClient(
        name=name, phone=phone,
        nin=request.form.get('nin', '').strip(),
        address=request.form.get('address', '').strip()
    )
    db.session.add(client)
    db.session.commit()

    log_action(session['username'], 'finance', 'create', 'client', client.id,
               {'name': name, 'phone': phone})
    flash(f'Client "{name}" added', 'success')
    return redirect(url_for('finance.clients'))


# ============ INDIVIDUAL LOANS ============

@finance_bp.route('/loans')
@login_required('finance')
def loans():
    all_loans = Loan.query.filter_by(is_deleted=False).order_by(Loan.issue_date.desc()).all()
    clients = LoanClient.query.filter_by(is_active=True).order_by(LoanClient.name).all()
    return render_template('finance/loans.html', loans=all_loans, clients=clients, today=get_local_today())


@finance_bp.route('/loans/create', methods=['POST'])
@login_required('finance')
def create_loan():
    try:
        client_id = request.form.get('client_id', type=int)
        principal = Decimal(request.form.get('principal', '0'))
        interest_rate = Decimal(request.form.get('interest_rate', '0'))
        duration_weeks = request.form.get('duration_weeks', type=int)
        issue_date = date.fromisoformat(request.form.get('issue_date', str(get_local_today())))

        if not client_id or principal <= 0 or duration_weeks <= 0:
            flash('Client, principal, and duration required', 'error')
            return redirect(url_for('finance.loans'))

        interest_amount = principal * (interest_rate / 100)
        total_amount = principal + interest_amount
        due_date = issue_date + timedelta(weeks=duration_weeks)

        loan = Loan(
            client_id=client_id, principal=principal, interest_rate=interest_rate,
            interest_amount=interest_amount, total_amount=total_amount,
            amount_paid=Decimal('0'), balance=total_amount,
            duration_weeks=duration_weeks, issue_date=issue_date, due_date=due_date,
            status='active'
        )
        db.session.add(loan)
        db.session.commit()

        client = LoanClient.query.get(client_id)
        log_action(session['username'], 'finance', 'create', 'loan', loan.id,
                   {'client': client.name if client else 'Unknown', 'principal': float(principal),
                    'total_amount': float(total_amount)})
        flash('Loan created', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('finance.loans'))


@finance_bp.route('/loans/<int:id>')
@login_required('finance')
def view_loan(id):
    loan = Loan.query.get_or_404(id)
    payments = loan.payments.filter_by(is_deleted=False).order_by(LoanPayment.payment_date.desc()).all()
    return render_template('finance/loan_detail.html', loan=loan, payments=payments, today=get_local_today())


@finance_bp.route('/loans/<int:id>/pay', methods=['POST'])
@login_required('finance')
def pay_loan(id):
    loan = Loan.query.get_or_404(id)
    try:
        amount = Decimal(request.form.get('amount', '0'))
        payment_date = date.fromisoformat(request.form.get('payment_date', str(get_local_today())))
        notes = request.form.get('notes', '').strip()

        if amount <= 0:
            flash('Amount must be greater than 0', 'error')
            return redirect(url_for('finance.view_loan', id=id))

        loan.amount_paid += amount
        loan.balance = loan.total_amount - loan.amount_paid
        if loan.balance <= 0:
            loan.balance = Decimal('0')
            loan.status = 'paid'

        payment = LoanPayment(
            loan_id=loan.id, payment_date=payment_date,
            amount=amount, balance_after=loan.balance, notes=notes
        )
        db.session.add(payment)
        db.session.commit()

        log_action(session['username'], 'finance', 'create', 'loan_payment', payment.id,
                   {'loan_id': loan.id, 'client': loan.client.name if loan.client else 'Unknown',
                    'amount': float(amount), 'balance_after': float(loan.balance)})
        flash('Payment recorded', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('finance.view_loan', id=id))


@finance_bp.route('/loans/<int:id>/delete', methods=['POST'])
@login_required('finance')
def delete_loan(id):
    loan = Loan.query.get_or_404(id)
    loan.is_deleted = True
    loan.deleted_at = db.func.now()
    db.session.commit()

    log_action(session['username'], 'finance', 'delete', 'loan', loan.id,
               {'client': loan.client.name if loan.client else 'Unknown',
                'total_amount': float(loan.total_amount)})
    flash('Loan deleted', 'success')
    return redirect(url_for('finance.loans'))


# ============ GROUP LOANS ============

@finance_bp.route('/group-loans')
@login_required('finance')
def group_loans():
    all_groups = GroupLoan.query.filter_by(is_deleted=False).order_by(GroupLoan.created_at.desc()).all()
    return render_template('finance/group_loans.html', groups=all_groups, today=get_local_today())


@finance_bp.route('/group-loans/create', methods=['POST'])
@login_required('finance')
def create_group_loan():
    try:
        group_name = request.form.get('group_name', '').strip()
        member_count = request.form.get('member_count', type=int)
        principal = Decimal(request.form.get('principal', '0'))
        interest_rate = Decimal(request.form.get('interest_rate', '0'))
        total_periods = request.form.get('total_periods', type=int)
        period_type = request.form.get('period_type', 'monthly')
        issue_date = date.fromisoformat(request.form.get('issue_date', str(get_local_today())))

        if not group_name or principal <= 0 or total_periods <= 0:
            flash('Group name, principal, and periods required', 'error')
            return redirect(url_for('finance.group_loans'))

        interest_amount = principal * (interest_rate / 100)
        total_amount = principal + interest_amount
        amount_per_period = total_amount / total_periods
        period_days = PERIOD_DAYS.get(period_type, 30)
        due_date = issue_date + timedelta(days=period_days * total_periods)

        group = GroupLoan(
            group_name=group_name, member_count=member_count or 1,
            principal=principal, interest_rate=interest_rate,
            interest_amount=interest_amount, total_amount=total_amount,
            amount_per_period=amount_per_period, total_periods=total_periods,
            period_type=period_type, periods_paid=0,
            amount_paid=Decimal('0'), balance=total_amount,
            issue_date=issue_date, due_date=due_date, status='active'
        )
        db.session.add(group)
        db.session.commit()

        log_action(session['username'], 'finance', 'create', 'group_loan', group.id,
                   {'group_name': group_name, 'principal': float(principal),
                    'total_amount': float(total_amount), 'member_count': member_count})
        flash('Group loan created', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('finance.group_loans'))


@finance_bp.route('/group-loans/<int:id>')
@login_required('finance')
def view_group_loan(id):
    group = GroupLoan.query.get_or_404(id)
    payments = group.payments.filter_by(is_deleted=False).order_by(GroupLoanPayment.payment_date.desc()).all()
    return render_template('finance/group_loan_detail.html', group=group, payments=payments, today=get_local_today())


@finance_bp.route('/group-loans/<int:id>/pay', methods=['POST'])
@login_required('finance')
def pay_group_loan(id):
    group = GroupLoan.query.get_or_404(id)
    try:
        amount = Decimal(request.form.get('amount', '0'))
        periods_covered = request.form.get('periods_covered', type=int, default=1)
        payment_date = date.fromisoformat(request.form.get('payment_date', str(get_local_today())))
        notes = request.form.get('notes', '').strip()

        if amount <= 0:
            flash('Amount must be greater than 0', 'error')
            return redirect(url_for('finance.view_group_loan', id=id))

        group.amount_paid += amount
        group.balance = group.total_amount - group.amount_paid
        group.periods_paid += periods_covered
        if group.balance <= 0:
            group.balance = Decimal('0')
            group.status = 'paid'

        payment = GroupLoanPayment(
            group_loan_id=group.id, payment_date=payment_date,
            amount=amount, periods_covered=periods_covered,
            balance_after=group.balance, notes=notes
        )
        db.session.add(payment)
        db.session.commit()

        log_action(session['username'], 'finance', 'create', 'group_loan_payment', payment.id,
                   {'group_name': group.group_name, 'amount': float(amount),
                    'periods_covered': periods_covered, 'balance_after': float(group.balance)})
        flash('Payment recorded', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('finance.view_group_loan', id=id))


@finance_bp.route('/group-loans/<int:id>/delete', methods=['POST'])
@login_required('finance')
def delete_group_loan(id):
    group = GroupLoan.query.get_or_404(id)
    group.is_deleted = True
    db.session.commit()

    log_action(session['username'], 'finance', 'delete', 'group_loan', group.id,
               {'group_name': group.group_name, 'total_amount': float(group.total_amount)})
    flash('Group loan deleted', 'success')
    return redirect(url_for('finance.group_loans'))


# ============ PAYMENTS HISTORY ============

@finance_bp.route('/payments')
@login_required('finance')
def payments():
    loan_payments = LoanPayment.query.filter_by(is_deleted=False).order_by(LoanPayment.payment_date.desc()).limit(50).all()
    group_payments = GroupLoanPayment.query.filter_by(is_deleted=False).order_by(GroupLoanPayment.payment_date.desc()).limit(50).all()
    return render_template('finance/payments.html', loan_payments=loan_payments, group_payments=group_payments)
