from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app
from app.models.customer import Customer
from app.modules.auth import login_required, get_session_user
from app.extensions import db
from sqlalchemy import or_

customers_bp = Blueprint('customers', __name__)


def _get_customer_scope(user):
    """Return the business_type filter for this user's role.
    Managers see all customers. Section workers see only their section's customers."""
    if user.role == 'manager':
        return None  # No filter — see all
    # Map role to business_type
    if user.role in ('boutique', 'hardware', 'finance'):
        return user.role
    return user.role


@customers_bp.route('/')
@login_required('customers')
def index():
    """List customers scoped to the user's section"""
    user = get_session_user()
    scope = _get_customer_scope(user)
    business_type = request.args.get('business_type')

    try:
        query = Customer.query
        if scope:
            # Non-managers only see their section's customers
            query = query.filter_by(business_type=scope)
        elif business_type:
            # Managers can optionally filter by business_type
            query = query.filter_by(business_type=business_type)
        customers = query.order_by(Customer.name).all()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Customer listing failed: %s', exc)
        customers = []
    return render_template('customers/index.html',
                           customers=customers,
                           business_type=scope or business_type,
                           is_manager=(user.role == 'manager'))


@customers_bp.route('/add', methods=['POST'])
@login_required('customers')
def add():
    """Add new customer, scoped to user's section"""
    user = get_session_user()
    scope = _get_customer_scope(user)

    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()

    if not name or not phone:
        flash('Name and phone required', 'error')
        return redirect(url_for('customers.index'))

    # Non-managers: business_type is forced to their section
    # Managers: use form input
    if scope:
        business_type = scope
    else:
        business_type = request.form.get('business_type')

    customer = Customer(
        name=name,
        phone=phone,
        address=request.form.get('address', '').strip(),
        business_type=business_type
    )
    customer.nin = request.form.get('nin', '').strip()
    db.session.add(customer)
    db.session.commit()
    flash(f'Customer "{name}" added', 'success')
    return redirect(url_for('customers.index'))


@customers_bp.route('/<int:id>/edit', methods=['POST'])
@login_required('customers')
def edit(id):
    """Update customer — only if within user's scope"""
    user = get_session_user()
    scope = _get_customer_scope(user)
    customer = Customer.query.get_or_404(id)

    # Non-managers can only edit customers in their section
    if scope and customer.business_type != scope:
        flash('You do not have permission to edit this customer', 'error')
        return redirect(url_for('customers.index'))

    customer.name = request.form.get('name', customer.name).strip()
    customer.phone = request.form.get('phone', customer.phone).strip()
    customer.address = request.form.get('address', '').strip()
    customer.ensure_nin_encrypted()
    customer.nin = request.form.get('nin', '').strip()

    db.session.commit()
    flash('Customer updated', 'success')
    return redirect(url_for('customers.index'))


@customers_bp.route('/search')
@login_required('customers')
def search():
    """Search customers scoped to user's section (AJAX endpoint)"""
    user = get_session_user()
    scope = _get_customer_scope(user)

    search_term = request.args.get('q', '').strip()
    business_type = request.args.get('business_type')

    if not search_term:
        return jsonify({'customers': []})

    query = Customer.query.filter(
        or_(
            Customer.name.ilike(f'%{search_term}%'),
            Customer.phone.ilike(f'%{search_term}%')
        )
    )

    if scope:
        # Non-managers: always scoped to their section
        query = query.filter_by(business_type=scope)
    elif business_type:
        # Managers: optional filter
        query = query.filter_by(business_type=business_type)

    customers = query.limit(10).all()
    return jsonify({'customers': [c.to_dict() for c in customers]})
