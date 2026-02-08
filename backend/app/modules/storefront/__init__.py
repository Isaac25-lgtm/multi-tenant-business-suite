"""
Storefront Module - Public E-commerce Frontend

This module provides read-only public access to PUBLISHED products only.
No authentication required.

ALLOWED WRITES: WebsiteLoanInquiry, WebsiteOrderRequest (demand capture only)
FORBIDDEN: Inventory, Sales, Loans, Finance tables
"""
from flask import Blueprint, render_template, request, jsonify
from app.extensions import db
from app.models.boutique import BoutiqueStock, BoutiqueCategory
from app.models.hardware import HardwareStock, HardwareCategory
from app.models.website import PublishedProduct, WebsiteLoanInquiry, WebsiteOrderRequest

storefront_bp = Blueprint('storefront', __name__, template_folder='../../templates/storefront')


def get_published_products(product_type=None, limit=None, featured_only=False):
    """
    Get products from PublishedProduct table - the ONLY source of truth for public visibility.
    
    This ensures managers control what appears publicly.
    Never queries raw inventory directly.
    """
    query = PublishedProduct.query.filter_by(is_published=True, is_active=True)
    
    if product_type:
        query = query.filter_by(product_type=product_type)
    
    if featured_only:
        query = query.filter_by(is_featured=True)
    
    query = query.order_by(PublishedProduct.display_order)
    
    if limit:
        query = query.limit(limit)
    
    products = []
    for item in query.all():
        public_data = item.to_public_dict()
        if public_data:  # Only include if inventory item still exists
            products.append(public_data)
    
    return products


def get_safe_boutique_products(limit=None):
    """
    Get boutique products that are PUBLISHED by managers.
    Returns only public-safe fields.
    """
    return get_published_products(product_type='boutique', limit=limit)


def get_safe_hardware_products(limit=None):
    """
    Get hardware products that are PUBLISHED by managers.
    Returns only public-safe fields.
    """
    return get_published_products(product_type='hardware', limit=limit)


# ============ PUBLIC ROUTES (READ-ONLY) ============

@storefront_bp.route('/')
def home():
    """
    Public storefront homepage.
    Displays PUBLISHED products only - controlled by managers.
    """
    boutique_products = get_safe_boutique_products(limit=4)
    hardware_products = get_safe_hardware_products(limit=4)
    featured_products = get_published_products(featured_only=True, limit=6)
    
    return render_template('storefront/index.html',
        boutique_products=boutique_products,
        hardware_products=hardware_products,
        featured_products=featured_products
    )


@storefront_bp.route('/hardware')
def hardware():
    """
    Public hardware listing page.
    Displays ONLY hardware items published by managers.
    """
    products = get_safe_hardware_products()
    
    return render_template('storefront/hardware.html',
        products=products
    )


@storefront_bp.route('/boutique')
def boutique():
    """
    Public boutique listing page.
    Displays ONLY boutique items published by managers.
    """
    products = get_safe_boutique_products()
    
    return render_template('storefront/boutique.html',
        products=products
    )


@storefront_bp.route('/shop')
def shop():
    """
    Full product listings page.
    Shows all published products.
    """
    boutique_products = get_safe_boutique_products()
    hardware_products = get_safe_hardware_products()
    
    return render_template('storefront/index.html',
        boutique_products=boutique_products,
        hardware_products=hardware_products,
        show_all=True
    )


@storefront_bp.route('/loans')
def loans():
    """
    Public loan inquiry page.
    Displays form to capture loan interest.
    """
    return render_template('storefront/loans.html')


@storefront_bp.route('/contact')
def contact():
    """
    Public contact page.
    """
    return render_template('storefront/contact.html')


# ============ DEMAND CAPTURE ROUTES ============

@storefront_bp.route('/api/loan-inquiry', methods=['POST'])
def submit_loan_inquiry():
    """
    Capture loan interest from public website.
    
    ALLOWED: Creates WebsiteLoanInquiry record only.
    DOES NOT create actual loan records - that's done by managers.
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('full_name') or not data.get('phone') or not data.get('email'):
            return jsonify({'success': False, 'error': 'Name, phone, and email are required'}), 400
        
        # Create inquiry record (demand signal, not a loan)
        inquiry = WebsiteLoanInquiry(
            full_name=data.get('full_name', '').strip(),
            phone=data.get('phone', '').strip(),
            email=data.get('email', '').strip(),
            requested_amount=data.get('requested_amount', ''),
            loan_type=data.get('loan_type', 'individual'),
            message=data.get('message', ''),
            status='new'
        )
        
        db.session.add(inquiry)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Your loan inquiry has been submitted. Our team will contact you soon.'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Failed to submit inquiry'}), 500


@storefront_bp.route('/api/order-request', methods=['POST'])
def submit_order_request():
    """
    Capture cart checkout intent from public website.
    
    ALLOWED: Creates WebsiteOrderRequest record only.
    DOES NOT create sales, deduct inventory, or process payment.
    Staff converts to POS sale after confirmation.
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('customer_name') or not data.get('customer_phone'):
            return jsonify({'success': False, 'error': 'Name and phone are required'}), 400
        
        if not data.get('items') or not isinstance(data['items'], list) or len(data['items']) == 0:
            return jsonify({'success': False, 'error': 'Cart is empty'}), 400
        
        # Create order request (demand signal, not a sale)
        order = WebsiteOrderRequest(
            customer_name=data.get('customer_name', '').strip(),
            customer_phone=data.get('customer_phone', '').strip(),
            customer_email=data.get('customer_email', '').strip() if data.get('customer_email') else None,
            items=data.get('items'),  # JSON array
            preferred_branch=data.get('preferred_branch'),
            source='website',
            status='new'
        )
        
        db.session.add(order)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Your order request has been submitted. Our team will contact you to confirm.'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Failed to submit order'}), 500
