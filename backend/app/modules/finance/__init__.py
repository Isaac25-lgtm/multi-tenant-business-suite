from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session, Response, send_file
from app.models.finance import LoanClient, Loan, LoanPayment, GroupLoan, GroupLoanPayment, LoanDocument
from app.modules.auth import login_required, log_action
from app.extensions import db
from app.utils.timezone import get_local_today
from app.utils.pdf_generator import generate_group_agreement_pdf
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from werkzeug.utils import secure_filename
import os
import io

finance_bp = Blueprint('finance', __name__)

PERIOD_DAYS = {'weekly': 7, 'bi-weekly': 14, 'monthly': 30, 'bi-monthly': 60}
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx'}


def safe_decimal(value, default='0'):
    """Safely convert a value to Decimal, handling empty strings and invalid values"""
    if value is None or value == '':
        return Decimal(default)
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return Decimal(default)


def check_date_permission(entry_date, user_section):
    """Check if user has permission to enter data for the given date"""
    today = get_local_today()
    yesterday = today - timedelta(days=1)
    if user_section == 'manager':
        return True
    return yesterday <= entry_date <= today


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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

    total_interest_expected = float(db.session.query(db.func.sum(Loan.interest_amount)).filter(
        Loan.is_deleted == False, Loan.balance > 0).scalar() or 0)
    total_interest_expected += float(db.session.query(db.func.sum(GroupLoan.interest_amount)).filter(
        GroupLoan.is_deleted == False, GroupLoan.balance > 0).scalar() or 0)

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
    client_id = request.form.get('client_id', type=int)
    principal = safe_decimal(request.form.get('principal', '0'))
    interest_rate = safe_decimal(request.form.get('interest_rate', '0'))
    duration_weeks = request.form.get('duration_weeks', type=int, default=4)
    issue_date = date.fromisoformat(request.form.get('issue_date', str(get_local_today())))

    if not client_id or principal <= 0:
        flash('Client and principal required for agreement preview', 'error')
        return redirect(url_for('finance.loans'))

    client = LoanClient.query.get(client_id)
    if not client:
        flash('Client not found', 'error')
        return redirect(url_for('finance.loans'))

    interest_amount = principal * (interest_rate / 100)
    total_amount = principal + interest_amount
    due_date = issue_date + timedelta(weeks=duration_weeks)

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
        principal=float(principal),
        interest_rate=float(interest_rate),
        interest_amount=float(interest_amount),
        total_amount=float(total_amount),
        duration_weeks=duration_weeks,
        issue_date=issue_date,
        due_date=due_date,
        default_terms=default_terms,
        today=get_local_today()
    )


@finance_bp.route('/loans/create-with-agreement', methods=['POST'])
@login_required('finance')
def create_loan_with_agreement():
    """Create loan after agreement review"""
    try:
        client_id = request.form.get('client_id', type=int)
        principal = safe_decimal(request.form.get('principal', '0'))
        interest_rate = safe_decimal(request.form.get('interest_rate', '0'))
        duration_weeks = request.form.get('duration_weeks', type=int)
        issue_date = date.fromisoformat(request.form.get('issue_date', str(get_local_today())))

        # Check date permission
        user_section = session.get('section', '')
        if not check_date_permission(issue_date, user_section):
            flash('You can only create loans for today or yesterday. Contact a manager for older entries.', 'error')
            return redirect(url_for('finance.loans'))

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
        db.session.flush()

        # Handle collateral document upload
        if 'collateral_file' in request.files:
            file = request.files['collateral_file']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'collateral')
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, f'loan_{loan.id}_{filename}')
                file.save(file_path)

                doc = LoanDocument(
                    loan_id=loan.id,
                    filename=filename,
                    file_path=file_path,
                    file_type=filename.rsplit('.', 1)[1].lower() if '.' in filename else 'unknown'
                )
                db.session.add(doc)

        db.session.commit()

        client = LoanClient.query.get(client_id)
        log_action(session['username'], 'finance', 'create', 'loan', loan.id,
                   {'client': client.name if client else 'Unknown', 'principal': float(principal),
                    'total_amount': float(total_amount)})
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

    # Generate a simple PDF for individual loans
    buffer = io.BytesIO()
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from app.utils.pdf_generator import draw_logo_header

    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Header with logo
    y = height - 20
    y = draw_logo_header(c, width, y)

    y -= 10
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width/2, y, "INDIVIDUAL LOAN AGREEMENT")
    y -= 30
    c.line(50, y, width-50, y)

    # Client Information
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

    # Loan Details
    y -= 30
    c.line(50, y, width-50, y)
    y -= 25
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "LOAN DETAILS")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Principal Amount: UGX {float(loan.principal):,.0f}")
    y -= 15
    c.drawString(50, y, f"Interest Rate: {float(loan.interest_rate)}%")
    y -= 15
    c.drawString(50, y, f"Interest Amount: UGX {float(loan.interest_amount):,.0f}")
    y -= 15
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, f"Total Repayment: UGX {float(loan.total_amount):,.0f}")
    c.setFont("Helvetica", 10)
    y -= 15
    c.drawString(50, y, f"Duration: {loan.duration_weeks} weeks")
    y -= 15
    c.drawString(50, y, f"Issue Date: {loan.issue_date.strftime('%B %d, %Y')}")
    y -= 15
    c.drawString(50, y, f"Due Date: {loan.due_date.strftime('%B %d, %Y')}")

    # Terms
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

    # Signatures
    y -= 40
    c.line(50, y, width-50, y)
    y -= 30
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "BORROWER:")
    c.drawString(320, y, "LENDER:")
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
    group_name = request.form.get('group_name', '').strip()
    member_count = request.form.get('member_count', type=int, default=1)
    principal = safe_decimal(request.form.get('principal', '0'))
    interest_rate = safe_decimal(request.form.get('interest_rate', '0'))
    total_periods = request.form.get('total_periods', type=int, default=12)
    period_type = request.form.get('period_type', 'monthly')
    issue_date = date.fromisoformat(request.form.get('issue_date', str(get_local_today())))

    if not group_name or principal <= 0:
        flash('Group name and principal required for agreement preview', 'error')
        return redirect(url_for('finance.group_loans'))

    interest_amount = principal * (interest_rate / 100)
    total_amount = principal + interest_amount
    amount_per_period = total_amount / total_periods if total_periods > 0 else total_amount
    period_days = PERIOD_DAYS.get(period_type, 30)
    due_date = issue_date + timedelta(days=period_days * total_periods)

    # Pre-calculate payment schedule (first 6 periods)
    payment_schedule = []
    for i in range(1, min(total_periods + 1, 7)):
        payment_date = issue_date + timedelta(days=period_days * i)
        payment_schedule.append({
            'period': i,
            'due_date': payment_date,
            'amount': float(amount_per_period)
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
        group_name=group_name,
        member_count=member_count,
        principal=float(principal),
        interest_rate=float(interest_rate),
        interest_amount=float(interest_amount),
        total_amount=float(total_amount),
        total_periods=total_periods,
        period_type=period_type,
        amount_per_period=float(amount_per_period),
        issue_date=issue_date,
        due_date=due_date,
        payment_schedule=payment_schedule,
        default_terms=default_terms,
        today=get_local_today()
    )


@finance_bp.route('/group-loans/create-with-agreement', methods=['POST'])
@login_required('finance')
def create_group_loan_with_agreement():
    """Create group loan after agreement review"""
    try:
        group_name = request.form.get('group_name', '').strip()
        member_count = request.form.get('member_count', type=int)
        principal = safe_decimal(request.form.get('principal', '0'))
        interest_rate = safe_decimal(request.form.get('interest_rate', '0'))
        total_periods = request.form.get('total_periods', type=int)
        period_type = request.form.get('period_type', 'monthly')
        issue_date = date.fromisoformat(request.form.get('issue_date', str(get_local_today())))
        members_data = request.form.get('members_data', '')

        # Check date permission
        user_section = session.get('section', '')
        if not check_date_permission(issue_date, user_section):
            flash('You can only create loans for today or yesterday. Contact a manager for older entries.', 'error')
            return redirect(url_for('finance.group_loans'))

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
            members_json=members_data if members_data else None,
            principal=principal, interest_rate=interest_rate,
            interest_amount=interest_amount, total_amount=total_amount,
            amount_per_period=amount_per_period, total_periods=total_periods,
            period_type=period_type, periods_paid=0,
            amount_paid=Decimal('0'), balance=total_amount,
            issue_date=issue_date, due_date=due_date, status='active'
        )
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
                file.save(file_path)

                doc = LoanDocument(
                    group_loan_id=group.id,
                    filename=filename,
                    file_path=file_path,
                    file_type=filename.rsplit('.', 1)[1].lower() if '.' in filename else 'unknown'
                )
                db.session.add(doc)

        db.session.commit()

        log_action(session['username'], 'finance', 'create', 'group_loan', group.id,
                   {'group_name': group_name, 'principal': float(principal),
                    'total_amount': float(total_amount), 'member_count': member_count,
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
        file.save(file_path)

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
        flash('Invalid file type. Allowed: PDF, PNG, JPG, DOC, DOCX', 'error')

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
        file.save(file_path)

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
        flash('Invalid file type. Allowed: PDF, PNG, JPG, DOC, DOCX', 'error')

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
