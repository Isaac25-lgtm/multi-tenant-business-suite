from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models.customer import Customer
from app.extensions import db
from sqlalchemy import or_

customers_bp = Blueprint('customers', __name__)


@customers_bp.route('/')
def index():
    """List all customers"""
    business_type = request.args.get('business_type')
    try:
        query = Customer.query
        if business_type:
            query = query.filter_by(business_type=business_type)
        customers = query.order_by(Customer.name).all()
    except Exception:
        db.session.rollback()
        customers = []
    return render_template('customers/index.html', customers=customers, business_type=business_type)


@customers_bp.route('/add', methods=['POST'])
def add():
    """Add new customer"""
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()

    if not name or not phone:
        flash('Name and phone required', 'error')
        return redirect(url_for('customers.index'))

    customer = Customer(
        name=name,
        phone=phone,
        address=request.form.get('address', '').strip(),
        nin=request.form.get('nin', '').strip(),
        business_type=request.form.get('business_type')
    )
    db.session.add(customer)
    db.session.commit()
    flash(f'Customer "{name}" added', 'success')
    return redirect(url_for('customers.index'))


@customers_bp.route('/<int:id>/edit', methods=['POST'])
def edit(id):
    """Update customer"""
    customer = Customer.query.get_or_404(id)

    customer.name = request.form.get('name', customer.name).strip()
    customer.phone = request.form.get('phone', customer.phone).strip()
    customer.address = request.form.get('address', '').strip()
    customer.nin = request.form.get('nin', '').strip()

    db.session.commit()
    flash('Customer updated', 'success')
    return redirect(url_for('customers.index'))


@customers_bp.route('/search')
def search():
    """Search customers (AJAX endpoint for autocomplete)"""
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

    if business_type:
        query = query.filter_by(business_type=business_type)

    customers = query.limit(10).all()
    return jsonify({'customers': [c.to_dict() for c in customers]})
