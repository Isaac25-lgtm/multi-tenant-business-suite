from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session, Response, send_file
from app.models.finance import LoanClient, Loan, LoanPayment, GroupLoan, GroupLoanPayment, LoanDocument
from app.modules.auth import login_required, log_action
from app.extensions import db
from app.utils.timezone import get_local_now, get_local_today
from app.utils.pdf_generator import generate_group_agreement_pdf
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from dateutil.relativedelta import relativedelta
from werkzeug.utils import secure_filename
import json
import os
import io

finance_bp = Blueprint('finance', __name__)

PERIOD_DAYS = {'weekly': 7, 'bi-weekly': 14, 'monthly': 30, 'bi-monthly': 60}
CLIENT_PAYER_STATUSES = {'neutral', 'good', 'bad'}
MAX_PRINCIPAL = Decimal('1000000000')
MAX_INTEREST_RATE = Decimal('100')
MAX_MONTHLY_INTEREST = Decimal('100000000')
MAX_DURATION_UNITS = 120
MAX_GROUP_PERIODS = 240
from app.utils.uploads import allowed_file, validate_and_save


def safe_decimal(value, default='0'):
    """Safely convert a value to Decimal, handling empty strings and invalid values"""
    if value is None or value == '':
        return Decimal(default)
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return Decimal(default)


def get_form_value(source, key, default=None, cast=None):
    if hasattr(source, 'get'):
        if cast is not None:
            try:
                return source.get(key, default, type=cast)
            except TypeError:
                pass
        value = source.get(key, default)
    else:
        value = default

    if cast is None or value in (None, ''):
        return value

    try:
        return cast(value)
    except (TypeError, ValueError):
        return default


def normalize_payer_status(value):
    status = str(value or 'neutral').strip().lower()
    if status not in CLIENT_PAYER_STATUSES:
        return 'neutral'
    return status


def check_date_permission(entry_date, user_section):
    """Check if user has permission to enter data for the given date"""
    today = get_local_today()
    yesterday = today - timedelta(days=1)
    if user_section == 'manager':
        return True
    return yesterday <= entry_date <= today


def calculate_due_date(issue_date, duration_units, duration_type):
    if duration_type == 'months':
        return issue_date + relativedelta(months=duration_units)
    return issue_date + timedelta(weeks=duration_units)


def elapsed_full_months(issue_date, reference_date):
    if not issue_date or not reference_date or reference_date <= issue_date:
        return 0
    delta = relativedelta(reference_date, issue_date)
    months = (delta.years * 12) + delta.months
    return max(months, 0)


def refresh_loan_state(loan, as_of_date=None):
    as_of_date = as_of_date or get_local_today()
    changed = False

    principal = Decimal(str(loan.principal or 0))
    amount_paid = Decimal(str(loan.amount_paid or 0))
    interest_mode = loan.interest_mode or 'flat_rate'

    if interest_mode == 'monthly_accrual':
        monthly_interest_amount = Decimal(str(loan.monthly_interest_amount or 0))
        accrued_months = elapsed_full_months(loan.issue_date, as_of_date)
        interest_amount = monthly_interest_amount * accrued_months
    else:
        interest_amount = Decimal(str(loan.interest_amount or 0))

    total_amount = principal + interest_amount
    balance = total_amount - amount_paid
    if balance < 0:
        balance = Decimal('0')

    if balance <= 0:
        status = 'paid'
    elif loan.due_date and loan.due_date < as_of_date:
        status = 'overdue'
    else:
        status = 'active'

    if Decimal(str(loan.interest_amount or 0)) != interest_amount:
        loan.interest_amount = interest_amount
        changed = True
    if Decimal(str(loan.total_amount or 0)) != total_amount:
        loan.total_amount = total_amount
        changed = True
    if Decimal(str(loan.balance or 0)) != balance:
        loan.balance = balance
        changed = True
    if (loan.status or 'active') != status:
        loan.status = status
        changed = True
    return changed


def refresh_active_loans():
    changed = False
    loans = Loan.query.filter_by(is_deleted=False).all()
    for loan in loans:
        changed = refresh_loan_state(loan) or changed
    if changed:
        db.session.commit()
    return changed


def parse_individual_loan_form(form):
    client_id = get_form_value(form, 'client_id', cast=int)
    principal = safe_decimal(get_form_value(form, 'principal', '0'))
    interest_mode = get_form_value(form, 'interest_mode', 'flat_rate')
    interest_rate = safe_decimal(get_form_value(form, 'interest_rate', '0'))
    monthly_interest_amount = safe_decimal(get_form_value(form, 'monthly_interest_amount', '0'))
    duration_weeks = get_form_value(form, 'duration_weeks', cast=int)
    duration_type = get_form_value(form, 'duration_type', 'weeks')
    issue_date = date.fromisoformat(get_form_value(form, 'issue_date', str(get_local_today())))

    if not client_id:
        raise ValueError('Client is required.')
    if principal <= 0 or principal > MAX_PRINCIPAL:
        raise ValueError('Principal must be between 1 and 1,000,000,000.')
    if not duration_weeks or duration_weeks <= 0 or duration_weeks > MAX_DURATION_UNITS:
        raise ValueError('Duration must be between 1 and 120.')
    if duration_type not in ('weeks', 'months'):
        raise ValueError('Invalid loan period selected.')
    if interest_mode not in ('flat_rate', 'monthly_accrual'):
        raise ValueError('Invalid interest mode selected.')

    if interest_mode == 'monthly_accrual':
        if duration_type != 'months':
            raise ValueError('Monthly accrual loans must use a monthly duration.')
        if monthly_interest_amount <= 0 or monthly_interest_amount > MAX_MONTHLY_INTEREST:
            raise ValueError('Monthly interest must be between 1 and 100,000,000.')
        interest_rate = (monthly_interest_amount / principal) * Decimal('100')
        interest_amount = Decimal('0')
        total_amount = principal
    else:
        if interest_rate < 0 or interest_rate > MAX_INTEREST_RATE:
            raise ValueError('Interest rate must be between 0 and 100.')
        monthly_interest_amount = None
        interest_amount = principal * (interest_rate / Decimal('100'))
        total_amount = principal + interest_amount

    return {
        'client_id': client_id,
        'principal': principal,
        'interest_mode': interest_mode,
        'interest_rate': interest_rate,
        'monthly_interest_amount': monthly_interest_amount,
        'interest_amount': interest_amount,
        'total_amount': total_amount,
        'duration_weeks': duration_weeks,
        'duration_type': duration_type,
        'issue_date': issue_date,
        'due_date': calculate_due_date(issue_date, duration_weeks, duration_type),
    }


def parse_group_loan_form(form):
    group_name = str(get_form_value(form, 'group_name', '') or '').strip()
    member_count = get_form_value(form, 'member_count', 1, int) or 1
    principal = safe_decimal(get_form_value(form, 'principal', '0'))
    interest_rate = safe_decimal(get_form_value(form, 'interest_rate', '0'))
    total_periods = get_form_value(form, 'total_periods', cast=int)
    period_type = get_form_value(form, 'period_type', 'monthly')
    issue_date = date.fromisoformat(get_form_value(form, 'issue_date', str(get_local_today())))

    if not group_name:
        raise ValueError('Group name is required.')
    if member_count <= 0 or member_count > 500:
        raise ValueError('Member count must be between 1 and 500.')
    if principal <= 0 or principal > MAX_PRINCIPAL:
        raise ValueError('Principal must be between 1 and 1,000,000,000.')
    if interest_rate < 0 or interest_rate > MAX_INTEREST_RATE:
        raise ValueError('Interest rate must be between 0 and 100.')
    if not total_periods or total_periods <= 0 or total_periods > MAX_GROUP_PERIODS:
        raise ValueError('Total periods must be between 1 and 240.')
    if period_type not in PERIOD_DAYS:
        raise ValueError('Invalid repayment period selected.')

    interest_amount = principal * (interest_rate / Decimal('100'))
    total_amount = principal + interest_amount
    amount_per_period = total_amount / total_periods
    period_days = PERIOD_DAYS.get(period_type, 30)
    due_date = issue_date + timedelta(days=period_days * total_periods)

    return {
        'group_name': group_name,
        'member_count': member_count,
        'principal': principal,
        'interest_rate': interest_rate,
        'interest_amount': interest_amount,
        'total_amount': total_amount,
        'amount_per_period': amount_per_period,
        'total_periods': total_periods,
        'period_type': period_type,
        'issue_date': issue_date,
        'due_date': due_date,
    }


@finance_bp.route('/')
@login_required('finance')
def index():
    """Finance overview"""
    today = get_local_today()

    try:
        refresh_active_loans()

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

        total_interest_expected = float(db.session.query(db.func.sum(Loan.interest_amount)).filter(
            Loan.is_deleted == False, Loan.balance > 0).scalar() or 0)
        total_interest_expected += float(db.session.query(db.func.sum(GroupLoan.interest_amount)).filter(
            GroupLoan.is_deleted == False, GroupLoan.balance > 0).scalar() or 0)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Finance dashboard calculation failed: %s', exc)
        active_loans = active_groups = overdue_loans = overdue_groups = 0
        total_outstanding = total_interest_expected = 0

    return render_template('finance/index.html',
        active_loans=active_loans, active_groups=active_groups,
        overdue_loans=overdue_loans, overdue_groups=overdue_groups,
        total_outstanding=total_outstanding,
        total_interest_expected=total_interest_expected
    )


# ============ CLIENTS ============

@finance_bp.route('/clients')
@login_required('finance')
def clients():
    raw_payer_status = str(request.args.get('payer_status', 'all') or 'all').strip().lower()
    payer_status_filter = 'all' if raw_payer_status == 'all' else normalize_payer_status(raw_payer_status)

    base_query = LoanClient.query.filter_by(is_active=True)
    query = base_query
    if payer_status_filter != 'all':
        query = query.filter_by(payer_status=payer_status_filter)

    all_clients = query.order_by(LoanClient.name).all()
    status_counts = {
        'all': base_query.count(),
        'good': base_query.filter_by(payer_status='good').count(),
        'bad': base_query.filter_by(payer_status='bad').count(),
        'neutral': base_query.filter_by(payer_status='neutral').count(),
    }
    return render_template(
        'finance/clients.html',
        clients=all_clients,
        payer_status_filter=payer_status_filter,
        status_counts=status_counts,
    )


@finance_bp.route('/clients/add', methods=['POST'])
@login_required('finance')
def add_client():
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    if not name or not phone:
        flash('Name and phone required', 'error')
        return redirect(url_for('finance.clients'))

    client = LoanClient(
        name=name,
        phone=phone,
        address=request.form.get('address', '').strip(),
        payer_status=normalize_payer_status(request.form.get('payer_status'))
    )
    client.nin = request.form.get('nin', '').strip()
    db.session.add(client)
    db.session.commit()

    log_action(session['username'], 'finance', 'create', 'client', client.id,
               {'name': name, 'phone': phone, 'payer_status': client.payer_status})
    flash(f'Client "{name}" added', 'success')
    return redirect(url_for('finance.clients'))


@finance_bp.route('/clients/<int:id>/edit', methods=['POST'])
@login_required('finance')
def edit_client(id):
    """Edit a client's details"""
    client = LoanClient.query.get_or_404(id)
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()

    if not name or not phone:
        flash('Name and phone required', 'error')
        return redirect(url_for('finance.clients'))

    old_name = client.name
    client.ensure_nin_encrypted()
    client.name = name
    client.phone = phone
    client.nin = request.form.get('nin', '').strip()
    client.address = request.form.get('address', '').strip()
    client.payer_status = normalize_payer_status(request.form.get('payer_status'))

    db.session.commit()

    log_action(session['username'], 'finance', 'update', 'client', client.id,
               {'old_name': old_name, 'new_name': name, 'phone': phone, 'payer_status': client.payer_status})
    flash(f'Client "{name}" updated', 'success')
    return redirect(url_for('finance.clients'))


@finance_bp.route('/clients/<int:id>/delete', methods=['POST'])
@login_required('finance')
def delete_client(id):
    """Deactivate a client (soft delete)"""
    client = LoanClient.query.get_or_404(id)

    # Check if client has active loans
    active_loans = client.loans.filter_by(is_deleted=False).count()
    if active_loans > 0:
        flash(f'Cannot delete client with {active_loans} active loans', 'error')
        return redirect(url_for('finance.clients'))

    client.is_active = False
    db.session.commit()

    log_action(session['username'], 'finance', 'deactivate', 'client', client.id,
               {'name': client.name})
    flash(f'Client "{client.name}" deactivated', 'success')
    return redirect(url_for('finance.clients'))


# ============ INDIVIDUAL LOANS ============

@finance_bp.route('/loans')
@login_required('finance')
def loans():
    refresh_active_loans()
    all_loans = Loan.query.filter_by(is_deleted=False).order_by(Loan.issue_date.desc()).all()
    clients = LoanClient.query.filter_by(is_active=True).order_by(LoanClient.name).all()
    return render_template('finance/loans.html', loans=all_loans, clients=clients, today=get_local_today())


@finance_bp.route('/loans/create', methods=['POST'])
@login_required('finance')
def create_loan():
    try:
        loan_data = parse_individual_loan_form(request.form)

        loan = Loan(
            client_id=loan_data['client_id'],
            principal=loan_data['principal'],
            interest_rate=loan_data['interest_rate'],
            interest_mode=loan_data['interest_mode'],
            monthly_interest_amount=loan_data['monthly_interest_amount'],
            interest_amount=loan_data['interest_amount'],
            total_amount=loan_data['total_amount'],
            amount_paid=Decimal('0'),
            balance=loan_data['total_amount'],
            duration_weeks=loan_data['duration_weeks'],
            duration_type=loan_data['duration_type'],
            issue_date=loan_data['issue_date'],
            due_date=loan_data['due_date'],
            status='active'
        )
        db.session.add(loan)
        db.session.commit()

        client = LoanClient.query.get(loan_data['client_id'])
        log_action(session['username'], 'finance', 'create', 'loan', loan.id,
                   {'client': client.name if client else 'Unknown', 'principal': float(loan_data['principal']),
                    'total_amount': float(loan.total_amount), 'interest_mode': loan.interest_mode})
        flash('Loan created', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('finance.loans'))


@finance_bp.route('/loans/<int:id>')
@login_required('finance')
def view_loan(id):
    loan = Loan.query.get_or_404(id)
    if refresh_loan_state(loan):
        db.session.commit()
    payments = loan.payments.filter_by(is_deleted=False).order_by(LoanPayment.payment_date.desc()).all()
    return render_template('finance/loan_detail.html', loan=loan, payments=payments, today=get_local_today())


@finance_bp.route('/loans/<int:id>/pay', methods=['POST'])
@login_required('finance')
def pay_loan(id):
    loan = Loan.query.get_or_404(id)
    try:
        amount = safe_decimal(request.form.get('amount', '0'))
        payment_date = date.fromisoformat(request.form.get('payment_date', str(get_local_today())))
        notes = request.form.get('notes', '').strip()
        user_section = session.get('section', '')

        if amount <= 0:
            flash('Amount must be greater than 0', 'error')
            return redirect(url_for('finance.view_loan', id=id))
        if amount > MAX_PRINCIPAL:
            flash('Payment amount is too large.', 'error')
            return redirect(url_for('finance.view_loan', id=id))
        if not check_date_permission(payment_date, user_section):
            flash('You can only enter payments for today or yesterday. Contact a manager for older entries.', 'error')
            return redirect(url_for('finance.view_loan', id=id))

        refresh_loan_state(loan, payment_date)
        if amount > loan.balance:
            flash(f'Payment cannot exceed the current balance of UGX {loan.balance:,.0f}.', 'error')
            return redirect(url_for('finance.view_loan', id=id))

        loan.amount_paid = Decimal(str(loan.amount_paid or 0)) + amount
        refresh_loan_state(loan, payment_date)
        balance_after_payment = loan.balance

        payment = LoanPayment(
            loan_id=loan.id, payment_date=payment_date,
            amount=amount, balance_after=balance_after_payment, notes=notes
        )
        db.session.add(payment)
        refresh_loan_state(loan)
        db.session.commit()

        log_action(session['username'], 'finance', 'create', 'loan_payment', payment.id,
                   {'loan_id': loan.id, 'client': loan.client.name if loan.client else 'Unknown',
                    'amount': float(amount), 'balance_after': float(balance_after_payment)})
        flash('Payment recorded', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('finance.view_loan', id=id))


@finance_bp.route('/loans/<int:id>/renew', methods=['POST'])
@login_required('finance')
def renew_loan(id):
    """Renew a loan by paying interest and creating a new loan with revised or same terms"""
    try:
        old_loan = Loan.query.get_or_404(id)
        refresh_loan_state(old_loan)

        # Calculate interest owed on old loan
        interest_owed = Decimal(str(old_loan.interest_amount or 0))

        # Update old loan - mark as paid
        old_loan.amount_paid = Decimal(str(old_loan.amount_paid)) + interest_owed
        refresh_loan_state(old_loan)

        # Record interest payment on old loan
        interest_payment = LoanPayment(
            loan_id=old_loan.id,
            amount=interest_owed,
            payment_date=get_local_today(),
            balance_after=old_loan.balance
        )
        db.session.add(interest_payment)

        # Get new terms from form (may be revised or same as old)
        renewal_issue_date = old_loan.due_date or get_local_today()
        renewal_form = {
            'client_id': old_loan.client_id,
            'principal': request.form.get('principal', str(old_loan.principal)),
            'interest_mode': request.form.get('interest_mode', old_loan.interest_mode or 'flat_rate'),
            'interest_rate': request.form.get('interest_rate', str(old_loan.interest_rate)),
            'monthly_interest_amount': request.form.get(
                'monthly_interest_amount',
                str(old_loan.monthly_interest_amount or 0)
            ),
            'duration_weeks': request.form.get('duration_weeks', old_loan.duration_weeks),
            'duration_type': request.form.get('duration_type', old_loan.duration_type or 'weeks'),
            # Preserve the loan cycle by starting the renewed loan from the prior due date.
            'issue_date': str(renewal_issue_date),
        }
        new_loan_data = parse_individual_loan_form(renewal_form)

        # Create new loan with (possibly revised) terms
        new_loan = Loan(
            client_id=old_loan.client_id,
            principal=new_loan_data['principal'],
            interest_rate=new_loan_data['interest_rate'],
            interest_mode=new_loan_data['interest_mode'],
            monthly_interest_amount=new_loan_data['monthly_interest_amount'],
            interest_amount=new_loan_data['interest_amount'],
            duration_weeks=new_loan_data['duration_weeks'],
            duration_type=new_loan_data['duration_type'],
            total_amount=new_loan_data['total_amount'],
            issue_date=new_loan_data['issue_date'],
            due_date=new_loan_data['due_date'],
            amount_paid=0,
            balance=new_loan_data['total_amount'],
            status='active'
        )
        db.session.add(new_loan)
        db.session.commit()

        # Log the renewal action
        log_action(session['username'], 'finance', 'renew', 'loan', old_loan.id,
                   {'client': old_loan.client.name if old_loan.client else 'Unknown',
                    'interest_paid': float(interest_owed),
                    'new_loan_id': new_loan.id,
                    'new_principal': float(new_loan_data['principal']),
                    'new_rate': float(new_loan_data['interest_rate']),
                    'new_weeks': new_loan_data['duration_weeks'],
                    'interest_mode': new_loan_data['interest_mode']})

        flash(f'Loan renewed! Interest of {interest_owed:,.0f} paid. New loan of {float(new_loan.total_amount):,.0f} created.', 'success')
        return redirect(url_for('finance.view_loan', id=new_loan.id))

    except Exception as e:
        db.session.rollback()
        flash(f'Error renewing loan: {str(e)}', 'error')
        return redirect(url_for('finance.loans'))


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


@finance_bp.route('/loans/<int:id>/edit', methods=['GET', 'POST'])
@login_required('finance')
def edit_loan(id):
    """Edit loan - manager only can edit dates"""
    loan = Loan.query.get_or_404(id)
    user_section = session.get('section', '')

    if request.method == 'POST':
        # Only managers can edit loan dates
        if user_section != 'manager':
            flash('Only managers can edit loan dates', 'error')
            return redirect(url_for('finance.view_loan', id=id))

        try:
            issue_date = date.fromisoformat(request.form.get('issue_date', str(loan.issue_date)))
            due_date = date.fromisoformat(request.form.get('due_date', str(loan.due_date)))

            old_issue_date = loan.issue_date
            old_due_date = loan.due_date

            loan.issue_date = issue_date
            loan.due_date = due_date

            # Recalculate duration_weeks
            delta = due_date - issue_date
            loan.duration_weeks = delta.days // 7

            # Update status based on new due date
            today = get_local_today()
            if loan.balance <= 0:
                loan.status = 'paid'
            elif due_date < today:
                loan.status = 'overdue'
            else:
                loan.status = 'active'

            db.session.commit()

            log_action(session['username'], 'finance', 'update', 'loan', loan.id,
                       {'action': 'edit_dates',
                        'old_issue_date': str(old_issue_date),
                        'new_issue_date': str(issue_date),
                        'old_due_date': str(old_due_date),
                        'new_due_date': str(due_date)})

            flash('Loan dates updated successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating loan: {str(e)}', 'error')

        return redirect(url_for('finance.view_loan', id=id))

    # GET request - show edit form
    if refresh_loan_state(loan):
        db.session.commit()
    clients = LoanClient.query.filter_by(is_active=True).order_by(LoanClient.name).all()
    return render_template('finance/edit_loan.html', loan=loan, clients=clients,
                          is_manager=(user_section == 'manager'))


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
        group_data = parse_group_loan_form(request.form)
        user_section = session.get('section', '')
        if not check_date_permission(group_data['issue_date'], user_section):
            flash('You can only create loans for today or yesterday. Contact a manager for older entries.', 'error')
            return redirect(url_for('finance.group_loans'))

        group = GroupLoan(
            group_name=group_data['group_name'],
            member_count=group_data['member_count'],
            principal=group_data['principal'],
            interest_rate=group_data['interest_rate'],
            interest_amount=group_data['interest_amount'],
            total_amount=group_data['total_amount'],
            amount_per_period=group_data['amount_per_period'],
            total_periods=group_data['total_periods'],
            period_type=group_data['period_type'],
            periods_paid=0,
            amount_paid=Decimal('0'),
            balance=group_data['total_amount'],
            issue_date=group_data['issue_date'],
            due_date=group_data['due_date'],
            status='active'
        )
        db.session.add(group)
        db.session.commit()

        log_action(session['username'], 'finance', 'create', 'group_loan', group.id,
                   {'group_name': group.group_name, 'principal': float(group.principal),
                    'total_amount': float(group.total_amount), 'member_count': group.member_count})
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
        amount = safe_decimal(request.form.get('amount', '0'))
        periods_covered = request.form.get('periods_covered', type=int, default=1)
        payment_date = date.fromisoformat(request.form.get('payment_date', str(get_local_today())))
        notes = request.form.get('notes', '').strip()
        user_section = session.get('section', '')

        if amount <= 0:
            flash('Amount must be greater than 0', 'error')
            return redirect(url_for('finance.view_group_loan', id=id))
        if amount > MAX_PRINCIPAL:
            flash('Payment amount is too large.', 'error')
            return redirect(url_for('finance.view_group_loan', id=id))
        if periods_covered <= 0:
            flash('Periods covered must be at least 1.', 'error')
            return redirect(url_for('finance.view_group_loan', id=id))
        if periods_covered > max(group.total_periods - group.periods_paid, 1):
            flash('Periods covered cannot exceed the remaining repayment periods.', 'error')
            return redirect(url_for('finance.view_group_loan', id=id))
        if not check_date_permission(payment_date, user_section):
            flash('You can only enter payments for today or yesterday. Contact a manager for older entries.', 'error')
            return redirect(url_for('finance.view_group_loan', id=id))
        if amount > group.balance:
            flash(f'Payment cannot exceed the current balance of UGX {group.balance:,.0f}.', 'error')
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


@finance_bp.route('/group-loans/<int:id>/edit', methods=['GET', 'POST'])
@login_required('finance')
def edit_group_loan(id):
    """Edit group loan - manager only can edit dates"""
    group = GroupLoan.query.get_or_404(id)
    user_section = session.get('section', '')

    if request.method == 'POST':
        # Only managers can edit dates
        if user_section != 'manager':
            flash('Only managers can edit loan dates', 'error')
            return redirect(url_for('finance.view_group_loan', id=id))

        try:
            issue_date = date.fromisoformat(request.form.get('issue_date', str(group.issue_date)))
            due_date = date.fromisoformat(request.form.get('due_date', str(group.due_date)))

            old_issue_date = group.issue_date
            old_due_date = group.due_date

            group.issue_date = issue_date
            group.due_date = due_date

            # Update status based on new due date
            today = get_local_today()
            if group.balance <= 0:
                group.status = 'paid'
            elif due_date < today:
                group.status = 'overdue'
            else:
                group.status = 'active'

            db.session.commit()

            log_action(session['username'], 'finance', 'update', 'group_loan', group.id,
                       {'action': 'edit_dates',
                        'old_issue_date': str(old_issue_date),
                        'new_issue_date': str(issue_date),
                        'old_due_date': str(old_due_date),
                        'new_due_date': str(due_date)})

            flash('Group loan dates updated successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating group loan: {str(e)}', 'error')

        return redirect(url_for('finance.view_group_loan', id=id))

    # GET request - show edit form
    return render_template('finance/edit_group_loan.html', group=group,
                          is_manager=(user_section == 'manager'))


# ============ PAYMENTS HISTORY ============

@finance_bp.route('/payments')
@login_required('finance')
def payments():
    loan_payments = LoanPayment.query.filter_by(is_deleted=False).order_by(LoanPayment.payment_date.desc()).limit(50).all()
    group_payments = GroupLoanPayment.query.filter_by(is_deleted=False).order_by(GroupLoanPayment.payment_date.desc()).limit(50).all()
    return render_template('finance/payments.html', loan_payments=loan_payments, group_payments=group_payments)


# ============ LOAN AGREEMENT ============

@finance_bp.route('/loans/preview-agreement', methods=['POST'])
@login_required('finance')
def preview_loan_agreement():
    """Preview individual loan agreement before issuing"""
    try:
        loan_data = parse_individual_loan_form(request.form)
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('finance.loans'))

    client = LoanClient.query.get(loan_data['client_id'])
    if not client:
        flash('Client not found', 'error')
        return redirect(url_for('finance.loans'))
    projected_interest_amount = loan_data['interest_amount']
    projected_total_amount = loan_data['total_amount']
    if loan_data['interest_mode'] == 'monthly_accrual':
        projected_interest_amount = loan_data['monthly_interest_amount'] * loan_data['duration_weeks']
        projected_total_amount = loan_data['principal'] + projected_interest_amount

    # Default agreement terms that can be edited
    default_terms = [
        "The Borrower agrees to repay the loan amount plus interest as specified above.",
        "Payments shall be made on or before the due date to avoid penalties.",
        "Late payments may result in additional charges of 5% per week on the outstanding balance.",
        "The Borrower may repay the loan early without any prepayment penalties.",
        "In case of default, the Lender reserves the right to take legal action to recover the debt.",
        "The Borrower agrees that all information provided is true and accurate.",
        "This agreement is binding upon signing by both parties.",
        "Any disputes arising from this agreement shall be resolved through arbitration."
    ]

    return render_template('finance/loan_agreement_preview.html',
        client=client,
        principal=float(loan_data['principal']),
        interest_rate=float(loan_data['interest_rate']),
        interest_mode=loan_data['interest_mode'],
        monthly_interest_amount=float(loan_data['monthly_interest_amount'] or 0),
        interest_amount=float(loan_data['interest_amount']),
        projected_interest_amount=float(projected_interest_amount),
        total_amount=float(loan_data['total_amount']),
        projected_total_amount=float(projected_total_amount),
        duration_weeks=loan_data['duration_weeks'],
        duration_type=loan_data['duration_type'],
        issue_date=loan_data['issue_date'],
        due_date=loan_data['due_date'],
        default_terms=default_terms,
        today=get_local_today()
    )


@finance_bp.route('/loans/create-with-agreement', methods=['POST'])
@login_required('finance')
def create_loan_with_agreement():
    """Create loan after agreement review"""
    try:
        loan_data = parse_individual_loan_form(request.form)

        # Check date permission
        user_section = session.get('section', '')
        if not check_date_permission(loan_data['issue_date'], user_section):
            flash('You can only create loans for today or yesterday. Contact a manager for older entries.', 'error')
            return redirect(url_for('finance.loans'))

        loan = Loan(
            client_id=loan_data['client_id'],
            principal=loan_data['principal'],
            interest_rate=loan_data['interest_rate'],
            interest_mode=loan_data['interest_mode'],
            monthly_interest_amount=loan_data['monthly_interest_amount'],
            interest_amount=loan_data['interest_amount'],
            total_amount=loan_data['total_amount'],
            amount_paid=Decimal('0'),
            balance=loan_data['total_amount'],
            duration_weeks=loan_data['duration_weeks'],
            duration_type=loan_data['duration_type'],
            issue_date=loan_data['issue_date'],
            due_date=loan_data['due_date'],
            status='active'
        )
        db.session.add(loan)
        db.session.flush()

        # Handle collateral document upload
        if 'collateral_file' in request.files:
            file = request.files['collateral_file']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'collateral')
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, f'loan_{loan.id}_{filename}')
                if validate_and_save(file, file_path):
                    doc = LoanDocument(
                        loan_id=loan.id,
                        filename=filename,
                        file_path=file_path,
                        file_type=filename.rsplit('.', 1)[1].lower() if '.' in filename else 'unknown'
                    )
                    db.session.add(doc)

        db.session.commit()

        client = LoanClient.query.get(loan_data['client_id'])
        log_action(session['username'], 'finance', 'create', 'loan', loan.id,
                   {'client': client.name if client else 'Unknown', 'principal': float(loan_data['principal']),
                    'total_amount': float(loan.total_amount), 'interest_mode': loan.interest_mode})
        flash('Loan created successfully', 'success')
        return redirect(url_for('finance.view_loan', id=loan.id))
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('finance.loans'))


@finance_bp.route('/loans/<int:id>/agreement-pdf')
@login_required('finance')
def download_loan_agreement_pdf(id):
    """Download individual loan agreement as PDF"""
    loan = Loan.query.get_or_404(id)
    if refresh_loan_state(loan):
        db.session.commit()

    buffer = io.BytesIO()
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from app.utils.branding import get_company_display_name
    from app.utils.pdf_generator import draw_logo_header

    brand_display_name = get_company_display_name()
    projected_interest = float(loan.interest_amount)
    projected_total = float(loan.total_amount)
    if loan.interest_mode == 'monthly_accrual':
        projected_interest = float((loan.monthly_interest_amount or 0) * loan.duration_weeks)
        projected_total = float(loan.principal) + projected_interest

    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 26
    y = draw_logo_header(c, width, y)

    y -= 8
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width/2, y, "INDIVIDUAL LOAN AGREEMENT")
    y -= 30
    c.line(50, y, width-50, y)

    y -= 30
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "BORROWER INFORMATION")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Name: {loan.client.name if loan.client else 'N/A'}")
    y -= 15
    c.drawString(50, y, f"Phone: {loan.client.phone if loan.client else 'N/A'}")
    y -= 15
    c.drawString(50, y, f"NIN: {loan.client.nin if loan.client and loan.client.nin else 'N/A'}")
    y -= 15
    c.drawString(50, y, f"Address: {loan.client.address if loan.client and loan.client.address else 'N/A'}")

    y -= 30
    c.line(50, y, width-50, y)
    y -= 25
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "LOAN DETAILS")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Principal Amount: UGX {float(loan.principal):,.0f}")
    y -= 15
    c.drawString(50, y, f"Interest Plan: {'Monthly Accrual' if loan.interest_mode == 'monthly_accrual' else 'Flat Rate'}")
    y -= 15
    c.drawString(50, y, f"Equivalent Rate: {float(loan.interest_rate):,.2f}%")
    y -= 15

    if loan.interest_mode == 'monthly_accrual':
        c.drawString(50, y, f"Monthly Interest: UGX {float(loan.monthly_interest_amount or 0):,.0f}")
        y -= 15
        c.drawString(50, y, f"Accrued Interest To Date: UGX {float(loan.interest_amount):,.0f}")
        y -= 15
        c.drawString(50, y, f"Projected Interest By Due Date: UGX {projected_interest:,.0f}")
        y -= 15
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, f"Current Amount Due: UGX {float(loan.total_amount):,.0f}")
        c.setFont("Helvetica", 10)
        y -= 15
        c.drawString(50, y, f"Projected Amount By Due Date: UGX {projected_total:,.0f}")
    else:
        c.drawString(50, y, f"Interest Amount: UGX {float(loan.interest_amount):,.0f}")
        y -= 15
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, f"Total Repayment: UGX {float(loan.total_amount):,.0f}")
        c.setFont("Helvetica", 10)

    y -= 15
    duration_label = loan.duration_type or 'weeks'
    c.drawString(50, y, f"Duration: {loan.duration_weeks} {duration_label}")
    y -= 15
    c.drawString(50, y, f"Issue Date: {loan.issue_date.strftime('%B %d, %Y')}")
    y -= 15
    c.drawString(50, y, f"Due Date: {loan.due_date.strftime('%B %d, %Y')}")

    y -= 30
    c.line(50, y, width-50, y)
    y -= 25
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "TERMS AND CONDITIONS")
    y -= 20
    c.setFont("Helvetica", 9)
    terms = [
        "1. The Borrower agrees to repay the loan amount plus interest as specified above.",
        "2. Payments shall be made on or before the due date to avoid penalties.",
        "3. Late payments may result in additional charges.",
        "4. Early repayment is allowed without penalty.",
        "5. This agreement is binding upon signing by both parties."
    ]
    for term in terms:
        c.drawString(50, y, term)
        y -= 15

    y -= 40
    c.line(50, y, width-50, y)
    y -= 30
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "BORROWER:")
    c.drawString(320, y, f"LENDER ({brand_display_name.upper()}):")
    y -= 40
    c.line(50, y, 200, y)
    c.line(320, y, 500, y)
    y -= 15
    c.setFont("Helvetica", 9)
    c.drawString(50, y, "Signature & Date")
    c.drawString(320, y, "Signature & Date")

    c.save()
    buffer.seek(0)

    return Response(
        buffer.getvalue(),
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename=loan_agreement_{loan.id}.pdf'}
    )


@finance_bp.route('/group-loans/preview-agreement', methods=['POST'])
@login_required('finance')
def preview_group_loan_agreement():
    """Preview group loan agreement before issuing"""
    try:
        group_data = parse_group_loan_form(request.form)
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('finance.group_loans'))

    # Pre-calculate payment schedule (first 6 periods)
    payment_schedule = []
    period_days = PERIOD_DAYS.get(group_data['period_type'], 30)
    for i in range(1, min(group_data['total_periods'] + 1, 7)):
        payment_date = group_data['issue_date'] + timedelta(days=period_days * i)
        payment_schedule.append({
            'period': i,
            'due_date': payment_date,
            'amount': float(group_data['amount_per_period'])
        })

    # Default agreement terms that can be edited
    default_terms = [
        "All members of the group are jointly and severally liable for the loan repayment.",
        "Payments shall be made according to the schedule specified in this agreement.",
        "Late payments may result in additional charges and affect future loan eligibility.",
        "The group may repay the loan early without any prepayment penalties.",
        "In case of default by any member, other members are responsible for covering the payment.",
        "All group members agree to attend mandatory group meetings as required.",
        "The group leader is responsible for collecting and submitting payments on behalf of the group.",
        "Any disputes shall be resolved through mediation before legal action."
    ]

    return render_template('finance/group_loan_agreement_preview.html',
        group_name=group_data['group_name'],
        member_count=group_data['member_count'],
        principal=float(group_data['principal']),
        interest_rate=float(group_data['interest_rate']),
        interest_amount=float(group_data['interest_amount']),
        total_amount=float(group_data['total_amount']),
        total_periods=group_data['total_periods'],
        period_type=group_data['period_type'],
        amount_per_period=float(group_data['amount_per_period']),
        issue_date=group_data['issue_date'],
        due_date=group_data['due_date'],
        payment_schedule=payment_schedule,
        default_terms=default_terms,
        today=get_local_today()
    )


@finance_bp.route('/group-loans/create-with-agreement', methods=['POST'])
@login_required('finance')
def create_group_loan_with_agreement():
    """Create group loan after agreement review"""
    try:
        group_data = parse_group_loan_form(request.form)
        members_data = request.form.get('members_data', '')

        # Check date permission
        user_section = session.get('section', '')
        if not check_date_permission(group_data['issue_date'], user_section):
            flash('You can only create loans for today or yesterday. Contact a manager for older entries.', 'error')
            return redirect(url_for('finance.group_loans'))

        group = GroupLoan(
            group_name=group_data['group_name'],
            member_count=group_data['member_count'],
            principal=group_data['principal'],
            interest_rate=group_data['interest_rate'],
            interest_amount=group_data['interest_amount'],
            total_amount=group_data['total_amount'],
            amount_per_period=group_data['amount_per_period'],
            total_periods=group_data['total_periods'],
            period_type=group_data['period_type'],
            periods_paid=0,
            amount_paid=Decimal('0'),
            balance=group_data['total_amount'],
            issue_date=group_data['issue_date'],
            due_date=group_data['due_date'],
            status='active'
        )
        if members_data:
            try:
                group.set_members(json.loads(members_data))
            except (TypeError, ValueError, json.JSONDecodeError):
                flash('Member data is invalid. Please review the group members and try again.', 'error')
                return redirect(url_for('finance.group_loans'))
        db.session.add(group)
        db.session.flush()

        # Handle collateral document upload
        if 'collateral_file' in request.files:
            file = request.files['collateral_file']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'collateral')
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, f'group_{group.id}_{filename}')
                if validate_and_save(file, file_path):
                    doc = LoanDocument(
                        group_loan_id=group.id,
                        filename=filename,
                        file_path=file_path,
                        file_type=filename.rsplit('.', 1)[1].lower() if '.' in filename else 'unknown'
                    )
                    db.session.add(doc)

        db.session.commit()

        log_action(session['username'], 'finance', 'create', 'group_loan', group.id,
                   {'group_name': group.group_name, 'principal': float(group.principal),
                    'total_amount': float(group.total_amount), 'member_count': group.member_count,
                    'has_members_data': bool(members_data)})
        flash('Group loan created successfully', 'success')
        return redirect(url_for('finance.view_group_loan', id=group.id))
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('finance.group_loans'))


@finance_bp.route('/group-loans/<int:id>/agreement-pdf')
@login_required('finance')
def download_group_agreement_pdf(id):
    """Download group loan agreement as PDF"""
    group = GroupLoan.query.get_or_404(id)
    buffer = generate_group_agreement_pdf(group)

    return Response(
        buffer.getvalue(),
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename=group_loan_agreement_{group.id}.pdf'}
    )


# ============ COLLATERAL DOCUMENTS ============

@finance_bp.route('/loans/<int:id>/upload-collateral', methods=['POST'])
@login_required('finance')
def upload_loan_collateral(id):
    """Upload collateral document for individual loan"""
    loan = Loan.query.get_or_404(id)

    if 'collateral_file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('finance.view_loan', id=id))

    file = request.files['collateral_file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('finance.view_loan', id=id))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'collateral')
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, f'loan_{loan.id}_{filename}')
        if validate_and_save(file, file_path):
            doc = LoanDocument(
                loan_id=loan.id,
                filename=filename,
                file_path=file_path,
                file_type=filename.rsplit('.', 1)[1].lower() if '.' in filename else 'unknown'
            )
            db.session.add(doc)
            db.session.commit()

            log_action(session['username'], 'finance', 'upload', 'collateral', doc.id,
                       {'loan_id': loan.id, 'filename': filename})
            flash('Collateral document uploaded successfully', 'success')
        else:
            flash('Invalid file content. The file appears corrupted or is not the claimed type.', 'error')
    else:
        flash('Invalid file type. Allowed: PDF, PNG, JPG, JPEG, GIF, WebP', 'error')

    return redirect(url_for('finance.view_loan', id=id))


@finance_bp.route('/group-loans/<int:id>/upload-collateral', methods=['POST'])
@login_required('finance')
def upload_group_loan_collateral(id):
    """Upload collateral document for group loan"""
    group = GroupLoan.query.get_or_404(id)

    if 'collateral_file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('finance.view_group_loan', id=id))

    file = request.files['collateral_file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('finance.view_group_loan', id=id))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'collateral')
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, f'group_{group.id}_{filename}')
        if validate_and_save(file, file_path):
            doc = LoanDocument(
                group_loan_id=group.id,
                filename=filename,
                file_path=file_path,
                file_type=filename.rsplit('.', 1)[1].lower() if '.' in filename else 'unknown'
            )
            db.session.add(doc)
            db.session.commit()

            log_action(session['username'], 'finance', 'upload', 'collateral', doc.id,
                       {'group_loan_id': group.id, 'filename': filename})
            flash('Collateral document uploaded successfully', 'success')
        else:
            flash('Invalid file content. The file appears corrupted or is not the claimed type.', 'error')
    else:
        flash('Invalid file type. Allowed: PDF, PNG, JPG, JPEG, GIF, WebP', 'error')

    return redirect(url_for('finance.view_group_loan', id=id))


@finance_bp.route('/documents/<int:id>/download')
@login_required('finance')
def download_document(id):
    """Download a collateral document"""
    doc = LoanDocument.query.get_or_404(id)
    if os.path.exists(doc.file_path):
        return send_file(doc.file_path, as_attachment=True, download_name=doc.filename)
    flash('File not found', 'error')
    return redirect(url_for('finance.index'))


@finance_bp.route('/documents/<int:id>/delete', methods=['POST'])
@login_required('finance')
def delete_document(id):
    """Delete a collateral document"""
    doc = LoanDocument.query.get_or_404(id)
    loan_id = doc.loan_id
    group_loan_id = doc.group_loan_id

    # Try to delete the file
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    doc.is_deleted = True
    db.session.commit()

    log_action(session['username'], 'finance', 'delete', 'collateral', doc.id,
               {'filename': doc.filename})
    flash('Document deleted', 'success')

    if loan_id:
        return redirect(url_for('finance.view_loan', id=loan_id))
    elif group_loan_id:
        return redirect(url_for('finance.view_group_loan', id=group_loan_id))
    return redirect(url_for('finance.index'))
