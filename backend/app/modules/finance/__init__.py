from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.models.finance import (
    LoanClient, Loan, LoanPayment,
    GroupLoan, GroupLoanPayment, LoanDocument
)
from app.extensions import db
from datetime import datetime, date, timedelta
from sqlalchemy import and_, or_
from werkzeug.utils import secure_filename
import os

finance_bp = Blueprint('finance', __name__)


# ============= CLIENTS =============

@finance_bp.route('/clients', methods=['GET'])
@jwt_required()
def get_clients():
    """Get all loan clients"""
    clients = LoanClient.query.filter_by(is_active=True).order_by(LoanClient.name).all()
    return jsonify([c.to_dict() for c in clients])


@finance_bp.route('/clients', methods=['POST'])
@jwt_required()
def create_client():
    """Create a new loan client"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    # Manager or finance employee can create clients
    if user.role != 'manager' and user.assigned_business != 'finances':
        return jsonify({'error': 'Only managers or finance employees can create loan clients'}), 403
    
    data = request.get_json()
    
    if not data.get('name') or not data.get('phone'):
        return jsonify({'error': 'Name and phone are required'}), 400
    
    client = LoanClient(
        name=data['name'],
        nin=data.get('nin'),
        phone=data['phone'],
        address=data.get('address'),
        created_by=current_user_id
    )
    
    db.session.add(client)
    db.session.commit()
    
    return jsonify(client.to_dict()), 201


# ============= INDIVIDUAL LOANS =============

@finance_bp.route('/loans', methods=['GET'])
@jwt_required()
def get_loans():
    """Get all loans"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    # Update overdue status
    today = date.today()
    overdue_loans = Loan.query.filter(
        Loan.is_deleted == False,
        Loan.status.in_(['active', 'due_soon']),
        Loan.due_date < today,
        Loan.balance > 0
    ).all()
    for loan in overdue_loans:
        loan.status = 'overdue'
    
    due_soon_loans = Loan.query.filter(
        Loan.is_deleted == False,
        Loan.status == 'active',
        Loan.due_date >= today,
        Loan.due_date <= today + timedelta(days=7),
        Loan.balance > 0
    ).all()
    for loan in due_soon_loans:
        loan.status = 'due_soon'
    
    db.session.commit()
    
    # Get loans
    query = Loan.query.filter_by(is_deleted=False).order_by(Loan.due_date)
    loans = query.all()
    
    return jsonify([loan.to_dict() for loan in loans])


@finance_bp.route('/loans', methods=['POST'])
@jwt_required()
def create_loan():
    """Create a new loan"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    # Manager or finance employee can create loans
    if user.role != 'manager' and user.assigned_business != 'finances':
        return jsonify({'error': 'Only managers or finance employees can issue loans'}), 403
    
    data = request.get_json()
    
    # Validate required fields
    required = ['client_id', 'principal', 'interest_rate', 'duration_weeks']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400
    
    # Check client exists
    client = LoanClient.query.get(data['client_id'])
    if not client:
        return jsonify({'error': 'Client not found'}), 404
    
    # Calculate loan details
    principal = float(data['principal'])
    interest_rate = float(data['interest_rate'])
    interest_amount = principal * (interest_rate / 100)
    total_amount = principal + interest_amount
    duration_weeks = int(data['duration_weeks'])
    issue_date = date.today()
    due_date = issue_date + timedelta(weeks=duration_weeks)
    
    loan = Loan(
        client_id=data['client_id'],
        principal=principal,
        interest_rate=interest_rate,
        interest_amount=interest_amount,
        total_amount=total_amount,
        amount_paid=0,
        balance=total_amount,
        duration_weeks=duration_weeks,
        issue_date=issue_date,
        due_date=due_date,
        status='active',
        created_by=current_user_id
    )
    
    db.session.add(loan)
    db.session.commit()
    
    return jsonify(loan.to_dict()), 201


@finance_bp.route('/loans/<int:id>', methods=['PUT'])
@jwt_required()
def update_loan(id):
    """Update loan details"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if user.role != 'manager' and user.assigned_business != 'finances':
        return jsonify({'error': 'Only managers or finance employees can update loans'}), 403
    
    loan = Loan.query.get(id)
    if not loan or loan.is_deleted:
        return jsonify({'error': 'Loan not found'}), 404
        
    data = request.get_json()
    
    if 'principal' in data:
        loan.principal = float(data['principal'])
    if 'interest_rate' in data:
        loan.interest_rate = float(data['interest_rate'])
    if 'duration_weeks' in data:
        loan.duration_weeks = int(data['duration_weeks'])
        
    # Recalculate totals if needed
    if 'principal' in data or 'interest_rate' in data:
        loan.interest_amount = float(loan.principal) * (float(loan.interest_rate) / 100)
        loan.total_amount = float(loan.principal) + loan.interest_amount
        loan.balance = loan.total_amount - float(loan.amount_paid)
        
    db.session.commit()
    return jsonify(loan.to_dict())


@finance_bp.route('/loans/<int:id>', methods=['GET'])
@jwt_required()
def get_loan(id):
    """Get loan details with payment history"""
    loan = Loan.query.get(id)
    if not loan or loan.is_deleted:
        return jsonify({'error': 'Loan not found'}), 404
    
    return jsonify(loan.to_dict(include_payments=True))


@finance_bp.route('/loans/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_loan(id):
    """Delete a loan (soft delete)"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    # Only manager can delete loans
    if user.role != 'manager':
        return jsonify({'error': 'Only managers can delete loans'}), 403
    
    loan = Loan.query.get(id)
    if not loan or loan.is_deleted:
        return jsonify({'error': 'Loan not found'}), 404
    
    loan.is_deleted = True
    loan.deleted_at = datetime.utcnow()
    loan.deleted_by = current_user_id
    db.session.commit()
    
    return jsonify({'message': 'Loan deleted successfully'})


@finance_bp.route('/loans/<int:id>/payment', methods=['POST'])
@jwt_required()
def record_loan_payment(id):
    """Record a payment for a loan"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    # Only manager or finance employee can record payments
    if user.role != 'manager' and user.assigned_business != 'finances':
        return jsonify({'error': 'Not authorized to record loan payments'}), 403
    
    loan = Loan.query.get(id)
    if not loan or loan.is_deleted:
        return jsonify({'error': 'Loan not found'}), 404
    
    data = request.get_json()
    
    if not data.get('amount'):
        return jsonify({'error': 'Payment amount is required'}), 400
    
    amount = float(data['amount'])
    
    if amount <= 0:
        return jsonify({'error': 'Payment amount must be positive'}), 400
    
    if amount > float(loan.balance):
        return jsonify({'error': f'Payment amount cannot exceed balance of {loan.balance}'}), 400
    
    # Determine payment date
    payment_date = date.today()
    if data.get('payment_date') == 'yesterday':
        payment_date = date.today() - timedelta(days=1)
    
    # Calculate new balance
    new_balance = float(loan.balance) - amount
    
    # Create payment record
    payment = LoanPayment(
        loan_id=id,
        payment_date=payment_date,
        amount=amount,
        balance_after=new_balance,
        notes=data.get('notes'),
        created_by=current_user_id
    )
    
    # Update loan
    loan.amount_paid = float(loan.amount_paid) + amount
    loan.balance = new_balance
    
    if new_balance <= 0:
        loan.status = 'paid'
    
    db.session.add(payment)
    db.session.commit()
    
    return jsonify({
        'message': 'Payment recorded successfully',
        'payment': payment.to_dict(),
        'loan': loan.to_dict()
    })


# ============= GROUP LOANS =============

@finance_bp.route('/group-loans', methods=['GET'])
@jwt_required()
def get_group_loans():
    """Get all group loans"""
    loans = GroupLoan.query.filter_by(is_deleted=False).order_by(GroupLoan.group_name).all()
    return jsonify([loan.to_dict() for loan in loans])


@finance_bp.route('/group-loans', methods=['POST'])
@jwt_required()
def create_group_loan():
    """Create a new group loan with interest rate and period type"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    # Manager or finance employee can create group loans
    if user.role != 'manager' and user.assigned_business != 'finances':
        return jsonify({'error': 'Only managers or finance employees can create group loans'}), 403

    data = request.get_json()

    required = ['group_name', 'member_count', 'principal', 'total_periods']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    # Get values
    principal = float(data['principal'])
    interest_rate = float(data.get('interest_rate', 0))
    total_periods = int(data['total_periods'])
    period_type = data.get('period_type', 'monthly')

    # Calculate interest and total
    interest_amount = principal * (interest_rate / 100)
    total_amount = principal + interest_amount

    # Calculate amount per period (can be overridden)
    amount_per_period = float(data.get('amount_per_period', 0))
    if amount_per_period == 0:
        amount_per_period = total_amount / total_periods

    # Calculate due date based on period type
    issue_date = date.today()
    period_days = {
        'weekly': 7,
        'bi-weekly': 14,
        'monthly': 30,
        'bi-monthly': 60
    }
    days_to_add = period_days.get(period_type, 30) * total_periods
    due_date = issue_date + timedelta(days=days_to_add)

    loan = GroupLoan(
        group_name=data['group_name'],
        member_count=int(data['member_count']),
        principal=principal,
        interest_rate=interest_rate,
        interest_amount=interest_amount,
        total_amount=total_amount,
        amount_per_period=amount_per_period,
        total_periods=total_periods,
        period_type=period_type,
        periods_paid=0,
        amount_paid=0,
        balance=total_amount,
        issue_date=issue_date,
        due_date=due_date,
        status='active',
        created_by=current_user_id
    )

    db.session.add(loan)
    db.session.commit()

    return jsonify(loan.to_dict()), 201


@finance_bp.route('/group-loans/<int:id>', methods=['PUT'])
@jwt_required()
def update_group_loan(id):
    """Update group loan details"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if user.role != 'manager' and user.assigned_business != 'finances':
        return jsonify({'error': 'Only managers or finance employees can update group loans'}), 403
    
    loan = GroupLoan.query.get(id)
    if not loan or loan.is_deleted:
        return jsonify({'error': 'Group loan not found'}), 404
        
    data = request.get_json()
    
    if 'group_name' in data:
        loan.group_name = data['group_name']
    if 'member_count' in data:
        loan.member_count = int(data['member_count'])
    if 'total_amount' in data:
        loan.total_amount = float(data['total_amount'])
        loan.balance = loan.total_amount - float(loan.amount_paid)
    if 'amount_per_period' in data:
        loan.amount_per_period = float(data['amount_per_period'])
    if 'total_periods' in data:
        loan.total_periods = int(data['total_periods'])
        loan.periods_left = loan.total_periods - loan.periods_paid

    db.session.commit()
    return jsonify(loan.to_dict())


@finance_bp.route('/group-loans/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_group_loan(id):
    """Delete a group loan (soft delete)"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if user.role != 'manager':
        return jsonify({'error': 'Only managers can delete group loans'}), 403
    
    loan = GroupLoan.query.get(id)
    if not loan or loan.is_deleted:
        return jsonify({'error': 'Group loan not found'}), 404
    
    loan.is_deleted = True
    db.session.commit()
    
    return jsonify({'message': 'Group loan deleted successfully'})


@finance_bp.route('/group-loans/<int:id>/payment', methods=['POST'])
@jwt_required()
def record_group_payment(id):
    """Record a payment for a group loan"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if user.role != 'manager' and user.assigned_business != 'finances':
        return jsonify({'error': 'Not authorized to record group payments'}), 403
    
    loan = GroupLoan.query.get(id)
    if not loan or loan.is_deleted:
        return jsonify({'error': 'Group loan not found'}), 404
    
    data = request.get_json()
    
    if not data.get('amount'):
        return jsonify({'error': 'Payment amount is required'}), 400
    
    amount = float(data['amount'])
    periods_covered = int(data.get('periods_covered', 1))
    
    payment_date = date.today()
    if data.get('payment_date') == 'yesterday':
        payment_date = date.today() - timedelta(days=1)
    
    new_balance = float(loan.balance) - amount
    
    payment = GroupLoanPayment(
        group_loan_id=id,
        payment_date=payment_date,
        amount=amount,
        periods_covered=periods_covered,
        balance_after=new_balance,
        notes=data.get('notes'),
        created_by=current_user_id
    )
    
    loan.amount_paid = float(loan.amount_paid) + amount
    loan.periods_paid += periods_covered
    loan.balance = new_balance
    
    if new_balance <= 0:
        loan.status = 'paid'
    
    db.session.add(payment)
    db.session.commit()
    
    return jsonify({
        'message': 'Payment recorded successfully',
        'payment': payment.to_dict(),
        'group_loan': loan.to_dict()
    })


# ============= ALL PAYMENTS =============

@finance_bp.route('/payments', methods=['GET'])
@jwt_required()
def get_all_payments():
    """Get all loan payments (individual + group)"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    # Get individual loan payments
    individual_payments = LoanPayment.query.filter_by(is_deleted=False).order_by(LoanPayment.payment_date.desc()).all()
    
    # Get group loan payments
    group_payments = GroupLoanPayment.query.filter_by(is_deleted=False).order_by(GroupLoanPayment.payment_date.desc()).all()
    
    # Combine and format
    all_payments = []
    
    for p in individual_payments:
        all_payments.append({
            'id': f'ind_{p.id}',
            'type': 'individual',
            'date': p.payment_date.isoformat(),
            'client': p.loan.client.name if p.loan and p.loan.client else 'Unknown',
            'amount': float(p.amount),
            'balance_after': float(p.balance_after),
            'received_by': p.creator.name if p.creator else 'Unknown'
        })
    
    for p in group_payments:
        all_payments.append({
            'id': f'grp_{p.id}',
            'type': 'group',
            'date': p.payment_date.isoformat(),
            'client': p.group_loan.group_name if p.group_loan else 'Unknown',
            'amount': float(p.amount),
            'balance_after': float(p.balance_after),
            'received_by': p.creator.name if p.creator else 'Unknown'
        })
    
    # Sort by date
    all_payments.sort(key=lambda x: x['date'], reverse=True)
    
    return jsonify(all_payments)


# ============= DASHBOARD STATS =============

@finance_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_finance_stats():
    """Get finance dashboard statistics"""
    today = date.today()
    
    # Total outstanding loans
    total_outstanding = db.session.query(db.func.sum(Loan.balance)).filter(
        Loan.is_deleted == False,
        Loan.status.in_(['active', 'due_soon', 'overdue'])
    ).scalar() or 0
    
    # Overdue count
    overdue_count = Loan.query.filter(
        Loan.is_deleted == False,
        Loan.status == 'overdue'
    ).count()
    
    # Today's payments
    today_payments = db.session.query(db.func.sum(LoanPayment.amount)).filter(
        LoanPayment.is_deleted == False,
        LoanPayment.payment_date == today
    ).scalar() or 0
    
    today_group_payments = db.session.query(db.func.sum(GroupLoanPayment.amount)).filter(
        GroupLoanPayment.is_deleted == False,
        GroupLoanPayment.payment_date == today
    ).scalar() or 0
    
    # Active loans count
    active_loans = Loan.query.filter(
        Loan.is_deleted == False,
        Loan.status.in_(['active', 'due_soon', 'overdue'])
    ).count()
    
    # Group loans outstanding
    group_outstanding = db.session.query(db.func.sum(GroupLoan.balance)).filter(
        GroupLoan.is_deleted == False,
        GroupLoan.status.in_(['active', 'overdue'])
    ).scalar() or 0
    
    return jsonify({
        'total_outstanding': float(total_outstanding) + float(group_outstanding),
        'individual_outstanding': float(total_outstanding),
        'group_outstanding': float(group_outstanding),
        'overdue_count': overdue_count,
        'today_payments': float(today_payments) + float(today_group_payments),
        'active_loans': active_loans
    })


# ============= DOCUMENTS =============

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx'}

@finance_bp.route('/loans/<int:id>/documents', methods=['POST'])
@jwt_required()
def upload_loan_documents(id):
    """Upload documents for a loan"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if user.role != 'manager' and user.assigned_business != 'finances':
        return jsonify({'error': 'Not authorized'}), 403
        
    loan = Loan.query.get(id)
    if not loan:
        return jsonify({'error': 'Loan not found'}), 404
        
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
        
    files = request.files.getlist('files')
    uploaded_docs = []
    
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'documents')
    os.makedirs(upload_dir, exist_ok=True)
    
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(f"loan_{id}_{int(datetime.now().timestamp())}_{file.filename}")
            file_path = os.path.join(upload_dir, filename)
            file.save(file_path)
            
            doc = LoanDocument(
                loan_id=id,
                filename=filename,
                file_path=f"/static/uploads/documents/{filename}",
                file_type=filename.rsplit('.', 1)[1].lower(),
                created_by=current_user_id
            )
            db.session.add(doc)
            uploaded_docs.append(doc)
            
    db.session.commit()
    
    return jsonify([doc.to_dict() for doc in uploaded_docs]), 201


@finance_bp.route('/group-loans/<int:id>/documents', methods=['POST'])
@jwt_required()
def upload_group_loan_documents(id):
    """Upload documents for a group loan"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if user.role != 'manager' and user.assigned_business != 'finances':
        return jsonify({'error': 'Not authorized'}), 403
        
    loan = GroupLoan.query.get(id)
    if not loan:
        return jsonify({'error': 'Group loan not found'}), 404
        
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
        
    files = request.files.getlist('files')
    uploaded_docs = []
    
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'documents')
    os.makedirs(upload_dir, exist_ok=True)
    
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(f"grouploan_{id}_{int(datetime.now().timestamp())}_{file.filename}")
            file_path = os.path.join(upload_dir, filename)
            file.save(file_path)
            
            doc = LoanDocument(
                group_loan_id=id,
                filename=filename,
                file_path=f"/static/uploads/documents/{filename}",
                file_type=filename.rsplit('.', 1)[1].lower(),
                created_by=current_user_id
            )
            db.session.add(doc)
            uploaded_docs.append(doc)

    db.session.commit()

    return jsonify([doc.to_dict() for doc in uploaded_docs]), 201


@finance_bp.route('/group-loans/<int:id>', methods=['GET'])
@jwt_required()
def get_group_loan(id):
    """Get group loan details with payment history and documents"""
    loan = GroupLoan.query.get(id)
    if not loan or loan.is_deleted:
        return jsonify({'error': 'Group loan not found'}), 404

    return jsonify(loan.to_dict(include_payments=True, include_documents=True))


@finance_bp.route('/group-loans/<int:id>/agreement', methods=['GET'])
@jwt_required()
def get_group_loan_agreement(id):
    """Generate PDF agreement for a group loan"""
    from flask import send_file
    from app.utils.pdf_generator import generate_group_agreement_pdf

    loan = GroupLoan.query.get(id)
    if not loan or loan.is_deleted:
        return jsonify({'error': 'Group loan not found'}), 404

    # Generate PDF
    pdf_buffer = generate_group_agreement_pdf(loan)

    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'group_agreement_{loan.group_name.replace(" ", "_")}_{loan.id}.pdf'
    )


@finance_bp.route('/group-loans/<int:id>/documents', methods=['GET'])
@jwt_required()
def get_group_loan_documents(id):
    """Get all documents for a group loan"""
    loan = GroupLoan.query.get(id)
    if not loan or loan.is_deleted:
        return jsonify({'error': 'Group loan not found'}), 404

    documents = LoanDocument.query.filter_by(group_loan_id=id, is_deleted=False).all()
    return jsonify([doc.to_dict() for doc in documents])
