from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.models.customer import Customer
from app.extensions import db
from sqlalchemy import or_

customers_bp = Blueprint('customers', __name__)


@customers_bp.route('', methods=['GET'])
@jwt_required()
def get_customers():
    """Get all customers"""
    business_type = request.args.get('business_type')
    
    query = Customer.query
    if business_type:
        query = query.filter_by(business_type=business_type)
    
    customers = query.all()
    return jsonify({
        'customers': [customer.to_dict() for customer in customers]
    }), 200


@customers_bp.route('/search', methods=['GET'])
@jwt_required()
def search_customers():
    """Search customers by name or phone (for autocomplete)"""
    search_term = request.args.get('q', '').strip()
    business_type = request.args.get('business_type')
    
    if not search_term:
        return jsonify({'customers': []}), 200
    
    query = Customer.query.filter(
        or_(
            Customer.name.ilike(f'%{search_term}%'),
            Customer.phone.ilike(f'%{search_term}%')
        )
    )
    
    if business_type:
        query = query.filter_by(business_type=business_type)
    
    customers = query.limit(10).all()
    
    return jsonify({
        'customers': [customer.to_dict() for customer in customers]
    }), 200


@customers_bp.route('', methods=['POST'])
@jwt_required()
def create_customer():
    """Create new customer"""
    from flask_jwt_extended import get_jwt_identity
    
    data = request.get_json()
    
    if not data.get('name') or not data.get('phone'):
        return jsonify({'error': 'Name and phone are required'}), 400
    
    customer = Customer(
        name=data['name'],
        phone=data['phone'],
        address=data.get('address'),
        nin=data.get('nin'),
        business_type=data.get('business_type'),
        created_by=get_jwt_identity()
    )
    
    db.session.add(customer)
    db.session.commit()
    
    return jsonify({
        'message': 'Customer created successfully',
        'customer': customer.to_dict()
    }), 201


@customers_bp.route('/<int:id>', methods=['GET'])
@jwt_required()
def get_customer(id):
    """Get customer details"""
    customer = Customer.query.get(id)
    
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404
    
    return jsonify({'customer': customer.to_dict()}), 200


@customers_bp.route('/<int:id>', methods=['PUT'])
@jwt_required()
def update_customer(id):
    """Update customer"""
    customer = Customer.query.get(id)
    
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404
    
    data = request.get_json()
    
    if 'name' in data:
        customer.name = data['name']
    if 'phone' in data:
        customer.phone = data['phone']
    if 'address' in data:
        customer.address = data['address']
    if 'nin' in data:
        customer.nin = data['nin']
    
    db.session.commit()
    
    return jsonify({
        'message': 'Customer updated successfully',
        'customer': customer.to_dict()
    }), 200
