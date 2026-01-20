from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.models.customer import Customer
from app.models.boutique import (
    BoutiqueCategory, BoutiqueStock, BoutiqueSale,
    BoutiqueSaleItem, BoutiqueCreditPayment
)
from app.extensions import db
from app.utils.helpers import (
    manager_required, business_access_required,
    get_date_filter_for_user, validate_date_for_user,
    log_audit, generate_reference_number
)
from datetime import datetime, date, timedelta
from sqlalchemy import and_, or_

boutique_bp = Blueprint('boutique', __name__)


# ============= CATEGORIES =============

@boutique_bp.route('/categories', methods=['GET'])
@jwt_required()
@business_access_required('boutique')
def get_categories():
    """Get all boutique categories"""
    categories = BoutiqueCategory.query.all()
    return jsonify({
        'categories': [cat.to_dict() for cat in categories]
    }), 200


@boutique_bp.route('/categories', methods=['POST'])
@jwt_required()
@manager_required
@business_access_required('boutique')
def create_category():
    """Create new boutique category (Manager only)"""
    data = request.get_json()
    
    if not data.get('name'):
        return jsonify({'error': 'Category name is required'}), 400
    
    category = BoutiqueCategory(name=data['name'])
    db.session.add(category)
    db.session.commit()
    
    return jsonify({
        'message': 'Category created successfully',
        'category': category.to_dict()
    }), 201


# ============= STOCK =============

@boutique_bp.route('/stock', methods=['GET'])
@jwt_required()
@business_access_required('boutique')
def get_stock():
    """Get all stock items"""
    show_inactive = request.args.get('show_inactive', 'false').lower() == 'true'
    
    query = BoutiqueStock.query
    if not show_inactive:
        query = query.filter_by(is_active=True)
    
    stock_items = query.all()
    return jsonify({
        'stock': [item.to_dict() for item in stock_items]
    }), 200


@boutique_bp.route('/stock', methods=['POST'])
@jwt_required()
@manager_required
@business_access_required('boutique')
def add_stock():
    """Add new stock item (Manager only)"""
    data = request.get_json()
    user_id = int(get_jwt_identity())
    
    # Validate required fields
    required = ['item_name', 'category_id', 'quantity', 'cost_price', 
                'min_selling_price', 'max_selling_price']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400
    
    # Calculate low stock threshold (25% of initial quantity)
    quantity = int(data['quantity'])
    low_stock_threshold = int(quantity * 0.25)
    
    stock = BoutiqueStock(
        item_name=data['item_name'],
        category_id=data['category_id'],
        quantity=quantity,
        initial_quantity=quantity,
        unit=data.get('unit', 'pieces'),
        cost_price=data['cost_price'],
        min_selling_price=data['min_selling_price'],
        max_selling_price=data['max_selling_price'],
        low_stock_threshold=low_stock_threshold,
        created_by=user_id
    )
    
    db.session.add(stock)
    db.session.commit()
    
    log_audit(
        user_id=user_id,
        action='create',
        module='boutique',
        entity_type='stock',
        entity_id=stock.id,
        description=f"Added stock item: {stock.item_name}",
        new_values=stock.to_dict()
    )
    
    return jsonify({
        'message': 'Stock item added successfully',
        'stock': stock.to_dict()
    }), 201


@boutique_bp.route('/stock/<int:id>', methods=['PUT'])
@jwt_required()
@manager_required
@business_access_required('boutique')
def update_stock(id):
    """Update stock item (Manager only)"""
    stock = BoutiqueStock.query.get(id)
    
    if not stock:
        return jsonify({'error': 'Stock item not found'}), 404
    
    data = request.get_json()
    user_id = int(get_jwt_identity())
    old_values = stock.to_dict()
    
    # Update fields
    if 'item_name' in data:
        stock.item_name = data['item_name']
    if 'category_id' in data:
        stock.category_id = data['category_id']
    if 'unit' in data:
        stock.unit = data['unit']
    if 'cost_price' in data:
        stock.cost_price = data['cost_price']
    if 'min_selling_price' in data:
        stock.min_selling_price = data['min_selling_price']
    if 'max_selling_price' in data:
        stock.max_selling_price = data['max_selling_price']
    if 'is_active' in data:
        stock.is_active = data['is_active']
    
    db.session.commit()
    
    log_audit(
        user_id=user_id,
        action='update',
        module='boutique',
        entity_type='stock',
        entity_id=stock.id,
        description=f"Updated stock item: {stock.item_name}",
        old_values=old_values,
        new_values=stock.to_dict()
    )
    
    return jsonify({
        'message': 'Stock item updated successfully',
        'stock': stock.to_dict()
    }), 200


@boutique_bp.route('/stock/<int:id>/quantity', methods=['PUT'])
@jwt_required()
@manager_required
@business_access_required('boutique')
def adjust_stock_quantity(id):
    """Adjust stock quantity (Manager only)"""
    stock = BoutiqueStock.query.get(id)
    
    if not stock:
        return jsonify({'error': 'Stock item not found'}), 404
    
    data = request.get_json()
    user_id = int(get_jwt_identity())
    
    if 'quantity' not in data:
        return jsonify({'error': 'Quantity is required'}), 400
    
    old_quantity = stock.quantity
    new_quantity = int(data['quantity'])
    
    stock.quantity = new_quantity
    
    # Update initial quantity and threshold if increasing
    if new_quantity > stock.initial_quantity:
        stock.initial_quantity = new_quantity
        stock.low_stock_threshold = int(new_quantity * 0.25)
    
    db.session.commit()
    
    log_audit(
        user_id=user_id,
        action='update',
        module='boutique',
        entity_type='stock',
        entity_id=stock.id,
        description=f"Adjusted quantity for {stock.item_name} from {old_quantity} to {new_quantity}"
    )
    
    return jsonify({
        'message': 'Stock quantity adjusted successfully',
        'stock': stock.to_dict()
    }), 200


@boutique_bp.route('/stock/<int:id>', methods=['DELETE'])
@jwt_required()
@manager_required
@business_access_required('boutique')
def delete_stock(id):
    """Delete stock item (Manager only)"""
    stock = BoutiqueStock.query.get(id)
    
    if not stock:
        return jsonify({'error': 'Stock item not found'}), 404
    
    user_id = int(get_jwt_identity())
    
    # Soft delete - just deactivate
    stock.is_active = False
    db.session.commit()
    
    log_audit(
        user_id=user_id,
        action='delete',
        module='boutique',
        entity_type='stock',
        entity_id=stock.id,
        description=f"Deleted stock item: {stock.item_name}"
    )
    
    return jsonify({'message': 'Stock item deleted successfully'}), 200


# ============= SALES =============

@boutique_bp.route('/sales', methods=['GET'])
@jwt_required()
@business_access_required('boutique')
def get_sales():
    """Get all sales"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    # Get date filter
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    created_by = request.args.get('created_by')
    
    query = BoutiqueSale.query.filter_by(is_deleted=False)
    
    # Apply date filter based on user role
    if user.role == 'employee':
        # Employees see only today and yesterday
        date_filter = get_date_filter_for_user(user)
        if date_filter:
            query = query.filter(BoutiqueSale.sale_date.in_(date_filter))
        # Employees see only their own sales
        query = query.filter_by(created_by=user_id)
    else:
        # Manager can filter by date range
        if start_date:
            query = query.filter(BoutiqueSale.sale_date >= start_date)
        if end_date:
            query = query.filter(BoutiqueSale.sale_date <= end_date)
        if created_by:
            query = query.filter_by(created_by=created_by)
    
    sales = query.order_by(BoutiqueSale.sale_date.desc()).all()
    
    return jsonify({
        'sales': [sale.to_dict() for sale in sales]
    }), 200


@boutique_bp.route('/sales/<int:id>', methods=['GET'])
@jwt_required()
@business_access_required('boutique')
def get_sale(id):
    """Get sale details"""
    sale = BoutiqueSale.query.get(id)
    
    if not sale or sale.is_deleted:
        return jsonify({'error': 'Sale not found'}), 404
    
    # Check access
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if user.role == 'employee' and sale.created_by != user_id:
        return jsonify({'error': 'Access denied'}), 403
    
    return jsonify({
        'sale': sale.to_dict(include_items=True)
    }), 200


@boutique_bp.route('/sales', methods=['POST'])
@jwt_required()
@business_access_required('boutique')
def create_sale():
    """Create new sale"""
    data = request.get_json()
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    # Validate required fields
    if not data.get('items') or len(data['items']) == 0:
        return jsonify({'error': 'At least one item is required'}), 400
    
    if not data.get('payment_type'):
        return jsonify({'error': 'Payment type is required'}), 400
    
    # Parse and validate sale date
    sale_date_str = data.get('sale_date', date.today().isoformat())
    sale_date = datetime.strptime(sale_date_str, '%Y-%m-%d').date()
    
    # Validate date for user
    can_use_date, error_msg = validate_date_for_user(user, sale_date)
    if not can_use_date:
        return jsonify({'error': error_msg}), 400
    
    # Calculate total
    total_amount = 0
    items_data = []
    has_other_items = False
    
    for item_data in data['items']:
        quantity = int(item_data['quantity'])
        unit_price = float(item_data['unit_price'])
        subtotal = quantity * unit_price
        
        # Validate stock item
        if item_data.get('stock_id'):
            stock = BoutiqueStock.query.get(item_data['stock_id'])
            if not stock:
                return jsonify({'error': f"Stock item not found"}), 404
            
            # Check quantity
            if stock.quantity < quantity:
                return jsonify({'error': f"Insufficient stock for {stock.item_name}"}), 400
            
            # Validate price range (only for employees)
            if user.role == 'employee':
                if unit_price < float(stock.min_selling_price) or unit_price > float(stock.max_selling_price):
                    return jsonify({
                        'error': f"Price for {stock.item_name} must be between {stock.min_selling_price} and {stock.max_selling_price}"
                    }), 400
            
            items_data.append({
                'stock_id': stock.id,
                'item_name': stock.item_name,
                'quantity': quantity,
                'unit_price': unit_price,
                'subtotal': subtotal,
                'is_other_item': False,
                'stock_obj': stock
            })
        else:
            # Other item
            has_other_items = True
            items_data.append({
                'stock_id': None,
                'item_name': item_data['item_name'],
                'quantity': quantity,
                'unit_price': unit_price,
                'subtotal': subtotal,
                'is_other_item': True,
                'stock_obj': None
            })
        
        total_amount += subtotal
    
    # Validate payment
    amount_paid = float(data.get('amount_paid', 0))
    payment_type = data['payment_type']
    
    if payment_type == 'full':
        if amount_paid != total_amount:
            amount_paid = total_amount
    
    balance = total_amount - amount_paid
    
    # If part payment, customer info is required
    customer = None
    if payment_type == 'part':
        if not data.get('customer_name') or not data.get('customer_phone'):
            return jsonify({'error': 'Customer name and phone required for part payment'}), 400
        
        # Check if customer exists
        customer = Customer.query.filter_by(
            phone=data['customer_phone'],
            business_type='boutique'
        ).first()
        
        if not customer:
            # Create new customer
            customer = Customer(
                name=data['customer_name'],
                phone=data['customer_phone'],
                address=data.get('customer_address'),
                business_type='boutique',
                created_by=user_id
            )
            db.session.add(customer)
            db.session.flush()
    
    # Generate reference number
    reference_number = generate_reference_number('DNV-B-', BoutiqueSale)
    
    # Create sale
    sale = BoutiqueSale(
        reference_number=reference_number,
        sale_date=sale_date,
        customer_id=customer.id if customer else None,
        payment_type=payment_type,
        total_amount=total_amount,
        amount_paid=amount_paid,
        balance=balance,
        is_credit_cleared=(balance == 0),
        created_by=user_id
    )
    
    db.session.add(sale)
    db.session.flush()
    
    # Add sale items and update stock
    for item_data in items_data:
        sale_item = BoutiqueSaleItem(
            sale_id=sale.id,
            stock_id=item_data['stock_id'],
            item_name=item_data['item_name'],
            quantity=item_data['quantity'],
            unit_price=item_data['unit_price'],
            subtotal=item_data['subtotal'],
            is_other_item=item_data['is_other_item']
        )
        db.session.add(sale_item)
        
        # Update stock quantity
        if item_data['stock_obj']:
            item_data['stock_obj'].quantity -= item_data['quantity']
    
    db.session.commit()
    
    # Log audit
    log_audit(
        user_id=user_id,
        action='create',
        module='boutique',
        entity_type='sale',
        entity_id=sale.id,
        description=f"Created sale {reference_number} for UGX {total_amount:,.0f}",
        is_flagged=has_other_items,
        flag_reason="Sale contains 'Other' items" if has_other_items else None
    )
    
    return jsonify({
        'message': 'Sale created successfully',
        'sale': sale.to_dict(include_items=True)
    }), 201


@boutique_bp.route('/sales/<int:id>', methods=['DELETE'])
@jwt_required()
@business_access_required('boutique')
def delete_sale(id):
    """Soft delete sale"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user.can_delete:
        return jsonify({'error': 'You do not have permission to delete sales'}), 403
    
    sale = BoutiqueSale.query.get(id)
    
    if not sale or sale.is_deleted:
        return jsonify({'error': 'Sale not found'}), 404
    
    # Check access for employees
    if user.role == 'employee' and sale.created_by != user_id:
        return jsonify({'error': 'You can only delete your own sales'}), 403
    
    # Validate date for employees
    if user.role == 'employee':
        can_delete, error_msg = validate_date_for_user(user, sale.sale_date)
        if not can_delete:
            return jsonify({'error': 'You can only delete recent sales'}), 403
    
    # Soft delete
    sale.is_deleted = True
    sale.deleted_at = datetime.utcnow()
    sale.deleted_by = user_id
    
    # Restore stock quantities
    for item in sale.items:
        if item.stock_id and not item.is_other_item:
            stock = BoutiqueStock.query.get(item.stock_id)
            if stock:
                stock.quantity += item.quantity
    
    db.session.commit()
    
    log_audit(
        user_id=user_id,
        action='delete',
        module='boutique',
        entity_type='sale',
        entity_id=sale.id,
        description=f"Deleted sale {sale.reference_number}",
        is_flagged=True,
        flag_reason="Sale deleted"
    )
    
    return jsonify({'message': 'Sale deleted successfully'}), 200


# ============= CREDITS =============

@boutique_bp.route('/credits', methods=['GET'])
@jwt_required()
@business_access_required('boutique')
def get_credits():
    """Get pending credits"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    query = BoutiqueSale.query.filter_by(
        payment_type='part',
        is_credit_cleared=False,
        is_deleted=False
    ).filter(BoutiqueSale.balance > 0)
    
    # Employees see only their own credits
    if user.role == 'employee':
        query = query.filter_by(created_by=user_id)
    
    credits = query.order_by(BoutiqueSale.sale_date.desc()).all()
    
    return jsonify({
        'credits': [credit.to_dict() for credit in credits]
    }), 200


@boutique_bp.route('/credits/cleared', methods=['GET'])
@jwt_required()
@manager_required
@business_access_required('boutique')
def get_cleared_credits():
    """Get cleared credits (Manager only)"""
    credits = BoutiqueSale.query.filter_by(
        payment_type='part',
        is_credit_cleared=True,
        is_deleted=False
    ).order_by(BoutiqueSale.updated_at.desc()).all()
    
    return jsonify({
        'credits': [credit.to_dict() for credit in credits]
    }), 200


@boutique_bp.route('/credits/<int:id>', methods=['GET'])
@jwt_required()
@business_access_required('boutique')
def get_credit_details(id):
    """Get credit details with payment history"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    sale = BoutiqueSale.query.get(id)
    
    if not sale or sale.is_deleted or sale.payment_type != 'part':
        return jsonify({'error': 'Credit not found'}), 404
    
    # Check access for employees
    if user.role == 'employee' and sale.created_by != user_id:
        return jsonify({'error': 'Access denied'}), 403
    
    # Get payment history
    payments = BoutiqueCreditPayment.query.filter_by(
        sale_id=sale.id
    ).order_by(BoutiqueCreditPayment.payment_date.desc()).all()
    
    return jsonify({
        'sale': sale.to_dict(include_items=True),
        'payments': [payment.to_dict() for payment in payments]
    }), 200


@boutique_bp.route('/credits/<int:id>/payment', methods=['POST'])
@jwt_required()
@business_access_required('boutique')
def record_credit_payment(id):
    """Record credit payment"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user.can_clear_credits:
        return jsonify({'error': 'You do not have permission to clear credits'}), 403
    
    sale = BoutiqueSale.query.get(id)
    
    if not sale or sale.is_deleted or sale.payment_type != 'part':
        return jsonify({'error': 'Credit not found'}), 404
    
    if sale.is_credit_cleared:
        return jsonify({'error': 'Credit already cleared'}), 400
    
    data = request.get_json()
    
    if not data.get('amount'):
        return jsonify({'error': 'Payment amount is required'}), 400
    
    amount = float(data['amount'])
    
    if amount <= 0:
        return jsonify({'error': 'Payment amount must be greater than zero'}), 400
    
    if amount > float(sale.balance):
        return jsonify({'error': 'Payment amount exceeds balance'}), 400
    
    # Parse payment date
    payment_date_str = data.get('payment_date', date.today().isoformat())
    payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d').date()
    
    # Update sale
    sale.amount_paid = float(sale.amount_paid) + amount
    sale.balance = float(sale.balance) - amount
    
    if sale.balance <= 0:
        sale.is_credit_cleared = True
        sale.balance = 0
    
    # Record payment
    payment = BoutiqueCreditPayment(
        sale_id=sale.id,
        payment_date=payment_date,
        amount=amount,
        remaining_balance=sale.balance,
        created_by=user_id
    )
    
    db.session.add(payment)
    db.session.commit()
    
    log_audit(
        user_id=user_id,
        action='create',
        module='boutique',
        entity_type='credit_payment',
        entity_id=payment.id,
        description=f"Recorded credit payment of UGX {amount:,.0f} for sale {sale.reference_number}"
    )
    
    return jsonify({
        'message': 'Payment recorded successfully',
        'sale': sale.to_dict(),
        'payment': payment.to_dict()
    }), 201
