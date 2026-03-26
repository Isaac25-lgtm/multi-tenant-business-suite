"""
Storefront Module - Public E-commerce Frontend

This module provides read-only public access to PUBLISHED products only.
No authentication required.

ALLOWED WRITES: WebsiteLoanInquiry, WebsiteOrderRequest (demand capture only)
FORBIDDEN: Inventory, Sales, Loans, Finance tables
"""
import re

from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from app.extensions import csrf
from app.extensions import db
from app.models.boutique import BoutiqueStock, BoutiqueCategory
from app.models.hardware import HardwareStock, HardwareCategory
from app.models.website import PublishedProduct, WebsiteLoanInquiry, WebsiteOrderRequest
from app.utils.branding import get_site_settings
from app.utils.rate_limit import consume_limit

storefront_bp = Blueprint('storefront', __name__, template_folder='../../templates/storefront')
EMAIL_PATTERN = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


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


def _client_ip():
    forwarded_for = request.headers.get('X-Forwarded-For', '')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.remote_addr or 'unknown'


def _is_valid_phone(value):
    digits = ''.join(ch for ch in str(value or '') if ch.isdigit())
    return 9 <= len(digits) <= 15


def _is_valid_email(value):
    return bool(EMAIL_PATTERN.match(str(value or '').strip()))


def _order_items_are_valid(items):
    if not isinstance(items, list) or not items:
        return False

    for item in items:
        if not isinstance(item, dict):
            return False
        if (item.get('product_type') or item.get('type')) not in ('boutique', 'hardware'):
            return False
        try:
            quantity = int(item.get('quantity', 1))
            price = float(item.get('price', 0))
        except (TypeError, ValueError):
            return False
        if quantity <= 0 or quantity > 100:
            return False
        if price < 0 or price > 1_000_000_000:
            return False
        if not str(item.get('name', '')).strip():
            return False
    return True


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
    settings = get_site_settings()
    
    return render_template('storefront/index.html',
        boutique_products=boutique_products,
        hardware_products=hardware_products,
        featured_products=featured_products,
        settings=settings,
    )


@storefront_bp.route('/hardware')
def hardware():
    """
    Public hardware listing page.
    Displays ONLY hardware items published by managers.
    """
    return redirect(f"{url_for('storefront.home')}#hardware")


@storefront_bp.route('/boutique')
def boutique():
    """
    Public boutique listing page.
    Displays ONLY boutique items published by managers.
    """
    return redirect(f"{url_for('storefront.home')}#boutique")


@storefront_bp.route('/shop')
def shop():
    """
    Full product listings page.
    Shows all published products.
    """
    boutique_products = get_safe_boutique_products()
    hardware_products = get_safe_hardware_products()
    settings = get_site_settings()
    
    return render_template('storefront/index.html',
        boutique_products=boutique_products,
        hardware_products=hardware_products,
        show_all=True,
        settings=settings,
    )


@storefront_bp.route('/loans')
def loans():
    """
    Public loan inquiry page.
    Displays form to capture loan interest.
    """
    return redirect(f"{url_for('storefront.home')}#loans")


@storefront_bp.route('/contact')
def contact():
    """
    Public contact page.
    """
    return redirect(f"{url_for('storefront.home')}#contact")


# ============ DEMAND CAPTURE ROUTES ============

@storefront_bp.route('/api/loan-inquiry', methods=['POST'])
@csrf.exempt
def submit_loan_inquiry():
    """
    Capture loan interest from public website.
    
    ALLOWED: Creates WebsiteLoanInquiry record only.
    DOES NOT create actual loan records - that's done by managers.
    """
    try:
        allowed, retry_after = consume_limit('public_loan_inquiry', _client_ip(), 5, 900, 1800)
        if not allowed:
            return jsonify({
                'success': False,
                'error': f'Too many submissions. Please try again in about {max((retry_after + 59) // 60, 1)} minute(s).'
            }), 429

        data = request.get_json()
        
        # Validate required fields
        if not data.get('full_name') or not data.get('phone') or not data.get('email'):
            return jsonify({'success': False, 'error': 'Name, phone, and email are required'}), 400
        if not _is_valid_phone(data.get('phone')):
            return jsonify({'success': False, 'error': 'Please enter a valid phone number'}), 400
        if not _is_valid_email(data.get('email')):
            return jsonify({'success': False, 'error': 'Please enter a valid email address'}), 400
        if data.get('loan_type') not in (None, '', 'individual', 'group'):
            return jsonify({'success': False, 'error': 'Invalid loan type selected'}), 400
        
        # Create inquiry record (demand signal, not a loan)
        inquiry = WebsiteLoanInquiry(
            full_name=data.get('full_name', '').strip(),
            phone=data.get('phone', '').strip(),
            email=data.get('email', '').strip(),
            requested_amount=str(data.get('requested_amount', '')).strip()[:100],
            loan_type=data.get('loan_type', 'individual'),
            message=str(data.get('message', '') or '').strip()[:1000],
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
@csrf.exempt
def submit_order_request():
    """
    Capture cart checkout intent from public website.
    
    ALLOWED: Creates WebsiteOrderRequest record only.
    DOES NOT create sales, deduct inventory, or process payment.
    Staff converts to POS sale after confirmation.
    """
    try:
        allowed, retry_after = consume_limit('public_order_request', _client_ip(), 5, 900, 1800)
        if not allowed:
            return jsonify({
                'success': False,
                'error': f'Too many submissions. Please try again in about {max((retry_after + 59) // 60, 1)} minute(s).'
            }), 429

        data = request.get_json()
        
        # Validate required fields
        if not data.get('customer_name') or not data.get('customer_phone'):
            return jsonify({'success': False, 'error': 'Name and phone are required'}), 400
        if not _is_valid_phone(data.get('customer_phone')):
            return jsonify({'success': False, 'error': 'Please enter a valid phone number'}), 400
        if data.get('customer_email') and not _is_valid_email(data.get('customer_email')):
            return jsonify({'success': False, 'error': 'Please enter a valid email address'}), 400

        if not _order_items_are_valid(data.get('items')):
            return jsonify({'success': False, 'error': 'Cart items are invalid'}), 400
        
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
