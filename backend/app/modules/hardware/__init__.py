from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.models.customer import Customer
from app.models.hardware import (
    HardwareCategory, HardwareStock, HardwareSale,
    HardwareSaleItem, HardwareCreditPayment
)
from app.extensions import db
from app.utils.helpers import (
    manager_required, business_access_required,
    get_date_filter_for_user, validate_date_for_user,
    log_audit, generate_reference_number
)
from datetime import datetime, date, timedelta

hardware_bp = Blueprint('hardware', __name__)


# ============= CATEGORIES =============

@hardware_bp.route('/categories', methods=['GET'])
@jwt_required()
@business_access_required('hardware')
def get_categories():
    """Get all hardware categories"""
    categories = HardwareCategory.query.all()
    return jsonify({
        'categories': [cat.to_dict() for cat in categories]
    }), 200


@hardware_bp.route('/categories', methods=['POST'])
@jwt_required()
@manager_required
@business_access_required('hardware')
def create_category():
    """Create new hardware category (Manager only)"""
    data = request.get_json()
    
    if not data.get('name'):
        return jsonify({'error': 'Category name is required'}), 400
    
    category = HardwareCategory(name=data['name'])
    db.session.add(category)
    db.session.commit()
    
    return jsonify({
        'message': 'Category created successfully',
        'category': category.to_dict()
    }), 201


# ============= STOCK =============

@hardware_bp.route('/stock', methods=['GET'])
@jwt_required()
@business_access_required('hardware')
def get_stock():
    """Get all stock items"""
    show_inactive = request.args.get('show_inactive', 'false').lower() == 'true'
    
    query = HardwareStock.query
    if not show_inactive:
        query = query.filter_by(is_active=True)
    
    stock_items = query.all()
    return jsonify({
        'stock': [item.to_dict() for item in stock_items]
    }), 200


@hardware_bp.route('/stock', methods=['POST'])
@jwt_required()
@manager_required
@business_access_required('hardware')
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
    
    stock = HardwareStock(
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
        module='hardware',
        entity_type='stock',
        entity_id=stock.id,
        description=f"Added stock item: {stock.item_name}",
        new_values=stock.to_dict()
    )
    
    return jsonify({
        'message': 'Stock item added successfully',
        'stock': stock.to_dict()
    }), 201


@hardware_bp.route('/stock/<int:id>', methods=['PUT'])
@jwt_required()
@manager_required
@business_access_required('hardware')
def update_stock(id):
    """Update stock item (Manager only)"""
    stock = HardwareStock.query.get(id)
    
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
        module='hardware',
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


@hardware_bp.route('/stock/<int:id>/quantity', methods=['PUT'])
@jwt_required()
@manager_required
@business_access_required('hardware')
def adjust_stock_quantity(id):
    """Adjust stock quantity (Manager only)"""
    stock = HardwareStock.query.get(id)
    
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
        module='hardware',
        entity_type='stock',
        entity_id=stock.id,
        description=f"Adjusted quantity for {stock.item_name} from {old_quantity} to {new_quantity}"
    )
    
    return jsonify({
        'message': 'Stock quantity adjusted successfully',
        'stock': stock.to_dict()
    }), 200


@hardware_bp.route('/stock/<int:id>', methods=['DELETE'])
@jwt_required()
@manager_required
@business_access_required('hardware')
def delete_stock(id):
    """Delete stock item (Manager only)"""
    stock = HardwareStock.query.get(id)
    
    if not stock:
        return jsonify({'error': 'Stock item not found'}), 404
    
    user_id = int(get_jwt_identity())
    
    # Soft delete - just deactivate
    stock.is_active = False
    db.session.commit()
    
    log_audit(
        user_id=user_id,
        action='delete',
        module='hardware',
        entity_type='stock',
        entity_id=stock.id,
        description=f"Deleted stock item: {stock.item_name}"
    )
    
    return jsonify({'message': 'Stock item deleted successfully'}), 200


# Due to length, sales and credits endpoints follow the same pattern as boutique
# For brevity, I'll create a shared function approach

def create_sale_handler(business_type, SaleModel, SaleItemModel, StockModel, reference_prefix):
    """Shared sale creation logic"""
    data = request.get_json()
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not data.get('items') or len(data['items']) == 0:
        return jsonify({'error': 'At least one item is required'}), 400
    
    if not data.get('payment_type'):
        return jsonify({'error': 'Payment type is required'}), 400
    
    sale_date_str = data.get('sale_date', date.today().isoformat())
    sale_date = datetime.strptime(sale_date_str, '%Y-%m-%d').date()
    
    can_use_date, error_msg = validate_date_for_user(user, sale_date)
    if not can_use_date:
        return jsonify({'error': error_msg}), 400
    
    total_amount = 0
    items_data = []
    has_other_items = False
    
    for item_data in data['items']:
        quantity = int(item_data['quantity'])
        unit_price = float(item_data['unit_price'])
        subtotal = quantity * unit_price
        
        if item_data.get('stock_id'):
            stock = StockModel.query.get(item_data['stock_id'])
            if not stock:
                return jsonify({'error': f"Stock item not found"}), 404
            
            if stock.quantity < quantity:
                return jsonify({'error': f"Insufficient stock for {stock.item_name}"}), 400
            
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
    
    amount_paid = float(data.get('amount_paid', 0))
    payment_type = data['payment_type']
    
    if payment_type == 'full':
        amount_paid = total_amount
    
    balance = total_amount - amount_paid
    
    customer = None
    if payment_type == 'part':
        if not data.get('customer_name') or not data.get('customer_phone'):
            return jsonify({'error': 'Customer name and phone required for part payment'}), 400
        
        customer = Customer.query.filter_by(
            phone=data['customer_phone'],
            business_type=business_type
        ).first()
        
        if not customer:
            customer = Customer(
                name=data['customer_name'],
                phone=data['customer_phone'],
                address=data.get('customer_address'),
                business_type=business_type,
                created_by=user_id
            )
            db.session.add(customer)
            db.session.flush()
    
    reference_number = generate_reference_number(reference_prefix, SaleModel)
    
    sale = SaleModel(
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
    
    for item_data in items_data:
        sale_item = SaleItemModel(
            sale_id=sale.id,
            stock_id=item_data['stock_id'],
            item_name=item_data['item_name'],
            quantity=item_data['quantity'],
            unit_price=item_data['unit_price'],
            subtotal=item_data['subtotal'],
            is_other_item=item_data['is_other_item']
        )
        db.session.add(sale_item)
        
        if item_data['stock_obj']:
            item_data['stock_obj'].quantity -= item_data['quantity']
    
    db.session.commit()
    
    log_audit(
        user_id=user_id,
        action='create',
        module=business_type,
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


@hardware_bp.route('/sales', methods=['POST'])
@jwt_required()
@business_access_required('hardware')
def create_hardware_sale():
    """Create new hardware sale"""
    return create_sale_handler('hardware', HardwareSale, HardwareSaleItem, HardwareStock, 'DNV-H-')


# Additional hardware endpoints follow the same pattern as boutique
# Omitted for brevity - they would be identical with hardware models
