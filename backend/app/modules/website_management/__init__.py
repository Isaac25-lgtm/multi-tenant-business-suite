"""
Website Management Module - Manager-Only Control Plane

This module provides managers with full control over:
- Published products (what appears on public website)
- Website images (banners, product images)
- Loan inquiry inbox (demand signals)
- Order request inbox (cart submissions)

CRITICAL: This module is accessible ONLY to managers.
"""
from functools import wraps
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, current_app
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models.user import User, AuditLog
from app.models.website import WebsiteLoanInquiry, WebsiteOrderRequest, PublishedProduct, WebsiteImage
from app.models.boutique import BoutiqueStock, BoutiqueCategory
from app.models.hardware import HardwareStock, HardwareCategory
import os

website_bp = Blueprint('website', __name__, template_folder='../../templates/website_management')

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def staff_required(f):
    """Decorator to require login for website management.

    All authenticated staff can access, but views are filtered by section:
    - Manager: full access to all products
    - Boutique worker: boutique products only
    - Hardware worker: hardware products only
    - Finance worker: view-only (no products to publish)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please login to access this section', 'error')
            return redirect(url_for('auth.login', section='manager'))

        return f(*args, **kwargs)
    return decorated_function


def get_user_section():
    """Get current user's section for filtering."""
    return session.get('section', '')


def can_publish_type(product_type):
    """Check if current user can publish a given product type.

    - Manager: can publish any type
    - Boutique worker: boutique only
    - Hardware worker: hardware only
    - Finance worker: cannot publish products (only handles loan inquiries)
    """
    section = get_user_section()
    if section == 'manager':
        return True
    if section == 'boutique' and product_type == 'boutique':
        return True
    if section == 'hardware' and product_type == 'hardware':
        return True
    return False


def can_view_orders_for_type(product_type):
    """Check if user should see orders containing a given product type."""
    section = get_user_section()
    if section == 'manager':
        return True
    if section == 'boutique' and product_type == 'boutique':
        return True
    if section == 'hardware' and product_type == 'hardware':
        return True
    return False


def filter_orders_by_section(orders):
    """Filter order list so workers only see orders containing their product types."""
    section = get_user_section()
    if section == 'manager':
        return orders
    if section == 'finance':
        return []  # Finance doesn't handle product orders
    # For boutique/hardware, only show orders that contain items of their type
    filtered = []
    for order in orders:
        if order.items:
            for item in order.items:
                if item.get('type') == section or item.get('product_type') == section:
                    filtered.append(order)
                    break
    return filtered


def log_action(action, details=None):
    """Log manager actions for audit trail."""
    try:
        user = User.query.filter_by(username=session.get('username')).first()
        log = AuditLog(
            user_id=user.id if user else None,
            action=action,
            details=details,
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Audit log error: {e}")


# ============ DASHBOARD ============

@website_bp.route('/')
@staff_required
def dashboard():
    """Website Management Dashboard - Overview of website activity.

    Filtered by section:
    - Manager: sees everything
    - Boutique: published boutique products + boutique order requests
    - Hardware: published hardware products + hardware order requests
    - Finance: loan inquiries only (no products, no product orders)
    """
    section = get_user_section()

    # Count published products (filtered by section)
    pub_query = PublishedProduct.query.filter_by(is_published=True, is_active=True)
    if section == 'boutique':
        pub_query = pub_query.filter_by(product_type='boutique')
    elif section == 'hardware':
        pub_query = pub_query.filter_by(product_type='hardware')
    elif section == 'finance':
        pub_query = pub_query.filter(db.false())  # Finance sees no products
    published_count = pub_query.count()

    # Count pending loan inquiries (only finance + manager)
    if section in ('manager', 'finance'):
        pending_inquiries = WebsiteLoanInquiry.query.filter_by(status='new', is_active=True).count()
    else:
        pending_inquiries = 0

    # Count pending order requests (filtered by section)
    all_new_orders = WebsiteOrderRequest.query.filter_by(status='new', is_active=True).all()
    filtered_new_orders = filter_orders_by_section(all_new_orders)
    pending_orders = len(filtered_new_orders)

    # Recent inquiries (only finance + manager)
    if section in ('manager', 'finance'):
        recent_inquiries = WebsiteLoanInquiry.query.filter_by(is_active=True)\
            .order_by(WebsiteLoanInquiry.submitted_at.desc()).limit(5).all()
    else:
        recent_inquiries = []

    # Recent orders (filtered by section)
    all_recent = WebsiteOrderRequest.query.filter_by(is_active=True)\
        .order_by(WebsiteOrderRequest.submitted_at.desc()).limit(20).all()
    recent_orders = filter_orders_by_section(all_recent)[:5]

    return render_template('website_management/dashboard.html',
        published_count=published_count,
        pending_inquiries=pending_inquiries,
        pending_orders=pending_orders,
        recent_inquiries=recent_inquiries,
        recent_orders=recent_orders,
        user_section=section
    )


# ============ PRODUCT PUBLISHING ============

@website_bp.route('/products')
@staff_required
def products():
    """Manage which products appear on public website.

    Filtered by user section:
    - Manager sees all products
    - Boutique worker sees only boutique
    - Hardware worker sees only hardware
    """
    section = get_user_section()

    # Get published product records filtered by section
    query = PublishedProduct.query.filter_by(is_active=True)
    if section == 'boutique':
        query = query.filter_by(product_type='boutique')
    elif section == 'hardware':
        query = query.filter_by(product_type='hardware')

    all_published = query.all()
    published_ids = {(p.product_type, p.product_id) for p in all_published}

    # Split into live and removed
    live_products = [p for p in all_published if p.is_published]
    removed_products = [p for p in all_published if not p.is_published]

    # Get inventory items filtered by section (finance has no products)
    boutique_items = []
    hardware_items = []
    if section in ('manager', 'boutique'):
        boutique_items = BoutiqueStock.query.filter_by(is_active=True).all()
    if section in ('manager', 'hardware'):
        hardware_items = HardwareStock.query.filter_by(is_active=True).all()

    # Finance workers should not see the products page at all
    if section == 'finance':
        flash('Finance workers manage loan inquiries, not products.', 'info')
        return redirect(url_for('website.loan_inquiries'))

    return render_template('website_management/products.html',
        published=all_published,
        live_products=live_products,
        removed_products=removed_products,
        published_ids=published_ids,
        boutique_items=boutique_items,
        hardware_items=hardware_items,
        user_section=section
    )


@website_bp.route('/products/publish', methods=['POST'])
@staff_required
def publish_product():
    """Publish or update a product for public visibility. Image comes from inventory."""
    product_type = request.form.get('product_type')
    product_id = request.form.get('product_id', type=int)
    is_featured = request.form.get('is_featured') == 'on'
    public_price = request.form.get('public_price', type=float)

    if not product_type or not product_id:
        flash('Invalid product selection', 'error')
        return redirect(url_for('website.products'))

    if not can_publish_type(product_type):
        flash(f'You do not have permission to publish {product_type} products.', 'error')
        return redirect(url_for('website.products'))

    user = User.query.filter_by(username=session['username']).first()

    # Check if already published
    existing = PublishedProduct.query.filter_by(
        product_type=product_type,
        product_id=product_id
    ).first()

    if existing:
        existing.is_published = True
        existing.is_featured = is_featured
        existing.public_price = public_price if public_price else None
        existing.published_at = datetime.utcnow()
        existing.published_by = user.id
    else:
        published = PublishedProduct(
            product_type=product_type,
            product_id=product_id,
            is_published=True,
            is_featured=is_featured,
            public_price=public_price if public_price else None,
            published_at=datetime.utcnow(),
            published_by=user.id
        )
        db.session.add(published)
    
    db.session.commit()
    log_action('publish_product', f'{product_type}:{product_id}')
    flash('Product published successfully! It is now visible on your public website.', 'success')
    return redirect(url_for('website.products'))


@website_bp.route('/products/unpublish/<int:id>', methods=['POST'])
@staff_required
def unpublish_product(id):
    """Remove product from public visibility."""
    published = PublishedProduct.query.get_or_404(id)
    if not can_publish_type(published.product_type):
        flash('You do not have permission to modify this product.', 'error')
        return redirect(url_for('website.products'))
    published.is_published = False
    db.session.commit()
    
    log_action('unpublish_product', f'{published.product_type}:{published.product_id}')
    flash('Product removed from website. You can republish, edit, or delete it below.', 'success')
    return redirect(url_for('website.products'))


@website_bp.route('/products/republish/<int:id>', methods=['POST'])
@staff_required
def republish_product(id):
    """Re-publish a previously unpublished product."""
    published = PublishedProduct.query.get_or_404(id)
    if not can_publish_type(published.product_type):
        flash('You do not have permission to modify this product.', 'error')
        return redirect(url_for('website.products'))
    published.is_published = True
    published.published_at = datetime.utcnow()
    db.session.commit()

    log_action('republish_product', f'{published.product_type}:{published.product_id}')
    flash('Product republished to website!', 'success')
    return redirect(url_for('website.products'))


@website_bp.route('/products/edit/<int:id>', methods=['POST'])
@staff_required
def edit_published_product(id):
    """Edit a published product's price, featured status."""
    published = PublishedProduct.query.get_or_404(id)
    if not can_publish_type(published.product_type):
        flash('You do not have permission to modify this product.', 'error')
        return redirect(url_for('website.products'))
    user = User.query.filter_by(username=session['username']).first()

    is_featured = request.form.get('is_featured') == 'on'
    public_price = request.form.get('public_price', type=float)

    published.is_featured = is_featured
    published.public_price = public_price if public_price else None
    published.updated_at = datetime.utcnow()

    # Republish if currently unpublished
    should_publish = request.form.get('republish') == 'on'
    if should_publish and not published.is_published:
        published.is_published = True
        published.published_at = datetime.utcnow()

    db.session.commit()
    log_action('edit_published_product', f'{published.product_type}:{published.product_id}')
    flash('Product updated successfully!', 'success')
    return redirect(url_for('website.products'))


@website_bp.route('/products/delete/<int:id>', methods=['POST'])
@staff_required
def delete_published_product(id):
    """Permanently delete a published product record (does not affect inventory)."""
    published = PublishedProduct.query.get_or_404(id)
    if not can_publish_type(published.product_type):
        flash('You do not have permission to delete this product.', 'error')
        return redirect(url_for('website.products'))
    product_info = f'{published.product_type}:{published.product_id}'
    db.session.delete(published)
    db.session.commit()

    log_action('delete_published_product', product_info)
    flash('Product record deleted. You can re-publish it from the inventory below.', 'success')
    return redirect(url_for('website.products'))


# ============ IMAGE MANAGEMENT ============

@website_bp.route('/images')
@staff_required
def images():
    """Manage website images."""
    all_images = WebsiteImage.query.filter_by(is_active=True)\
        .order_by(WebsiteImage.display_order).all()
    
    return render_template('website_management/images.html', images=all_images)


@website_bp.route('/images/upload', methods=['POST'])
@staff_required
def upload_image():
    """Upload a new website image."""
    if 'image' not in request.files:
        flash('No image file provided', 'error')
        return redirect(url_for('website.images'))
    
    file = request.files['image']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('website.images'))
    
    if not allowed_image(file.filename):
        flash('Invalid file type. Allowed: png, jpg, jpeg, gif, webp', 'error')
        return redirect(url_for('website.images'))
    
    # Create upload directory if needed
    upload_dir = os.path.join(current_app.static_folder, 'uploads', 'website')
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save file
    filename = secure_filename(file.filename)
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    filename = f"{timestamp}_{filename}"
    file_path = os.path.join(upload_dir, filename)
    file.save(file_path)
    
    # Create database record
    user = User.query.filter_by(username=session['username']).first()
    image = WebsiteImage(
        image_type=request.form.get('image_type', 'product'),
        file_path=f'/static/uploads/website/{filename}',
        alt_text=request.form.get('alt_text', ''),
        is_active=True,
        display_order=request.form.get('display_order', 0, type=int),
        uploaded_by=user.id
    )
    db.session.add(image)
    db.session.commit()
    
    log_action('upload_image', filename)
    flash('Image uploaded successfully', 'success')
    return redirect(url_for('website.images'))


@website_bp.route('/images/toggle/<int:id>', methods=['POST'])
@staff_required
def toggle_image(id):
    """Toggle image active status."""
    image = WebsiteImage.query.get_or_404(id)
    image.is_active = not image.is_active
    db.session.commit()
    
    status = 'activated' if image.is_active else 'deactivated'
    log_action('toggle_image', f'{id}: {status}')
    flash(f'Image {status}', 'success')
    return redirect(url_for('website.images'))


# ============ LOAN INQUIRY INBOX ============

@website_bp.route('/loan-inquiries')
@staff_required
def loan_inquiries():
    """View and manage loan inquiries from website.

    Only accessible to finance workers and managers.
    Boutique/hardware workers are redirected to order requests.
    """
    section = get_user_section()
    if section in ('boutique', 'hardware'):
        flash('Loan inquiries are handled by finance staff.', 'info')
        return redirect(url_for('website.order_requests'))

    status_filter = request.args.get('status', 'all')
    
    query = WebsiteLoanInquiry.query.filter_by(is_active=True)
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    inquiries = query.order_by(WebsiteLoanInquiry.submitted_at.desc()).all()
    
    # Count by status
    status_counts = {
        'new': WebsiteLoanInquiry.query.filter_by(status='new', is_active=True).count(),
        'reviewed': WebsiteLoanInquiry.query.filter_by(status='reviewed', is_active=True).count(),
        'approved': WebsiteLoanInquiry.query.filter_by(status='approved', is_active=True).count(),
        'rejected': WebsiteLoanInquiry.query.filter_by(status='rejected', is_active=True).count(),
    }
    
    return render_template('website_management/loan_inquiries.html',
        inquiries=inquiries,
        status_filter=status_filter,
        status_counts=status_counts
    )


@website_bp.route('/loan-inquiries/<int:id>')
@staff_required
def view_loan_inquiry(id):
    """View single loan inquiry details."""
    inquiry = WebsiteLoanInquiry.query.get_or_404(id)
    return render_template('website_management/loan_inquiry_detail.html', inquiry=inquiry)


@website_bp.route('/loan-inquiries/<int:id>/status', methods=['POST'])
@staff_required
def update_inquiry_status(id):
    """Update loan inquiry status."""
    inquiry = WebsiteLoanInquiry.query.get_or_404(id)
    new_status = request.form.get('status')
    notes = request.form.get('notes', '')
    
    if new_status not in ['new', 'reviewed', 'approved', 'rejected']:
        flash('Invalid status', 'error')
        return redirect(url_for('website.view_loan_inquiry', id=id))
    
    user = User.query.filter_by(username=session['username']).first()
    
    inquiry.status = new_status
    inquiry.notes = notes
    inquiry.reviewed_by = user.id
    inquiry.reviewed_at = datetime.utcnow()
    db.session.commit()
    
    log_action('update_inquiry_status', f'{id}: {new_status}')
    flash(f'Inquiry marked as {new_status}', 'success')
    return redirect(url_for('website.loan_inquiries'))


# ============ ORDER REQUEST INBOX ============

@website_bp.route('/order-requests')
@staff_required
def order_requests():
    """View and manage order requests from website.

    Filtered by section: boutique workers see orders with boutique items,
    hardware workers see orders with hardware items, finance sees none.
    """
    section = get_user_section()

    # Finance workers don't handle product orders
    if section == 'finance':
        flash('Finance workers manage loan inquiries, not product orders.', 'info')
        return redirect(url_for('website.loan_inquiries'))

    status_filter = request.args.get('status', 'all')

    query = WebsiteOrderRequest.query.filter_by(is_active=True)
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)

    all_orders = query.order_by(WebsiteOrderRequest.submitted_at.desc()).all()
    orders = filter_orders_by_section(all_orders)

    # Count by status (also filtered by section)
    all_active = WebsiteOrderRequest.query.filter_by(is_active=True).all()
    section_orders = filter_orders_by_section(all_active)
    status_counts = {'new': 0, 'contacted': 0, 'fulfilled': 0, 'cancelled': 0}
    for o in section_orders:
        if o.status in status_counts:
            status_counts[o.status] += 1

    return render_template('website_management/order_requests.html',
        orders=orders,
        status_filter=status_filter,
        status_counts=status_counts
    )


@website_bp.route('/order-requests/<int:id>')
@staff_required
def view_order_request(id):
    """View single order request details."""
    order = WebsiteOrderRequest.query.get_or_404(id)
    return render_template('website_management/order_request_detail.html', order=order)


@website_bp.route('/order-requests/<int:id>/status', methods=['POST'])
@staff_required
def update_order_status(id):
    """Update order request status."""
    order = WebsiteOrderRequest.query.get_or_404(id)
    new_status = request.form.get('status')
    notes = request.form.get('notes', '')
    
    if new_status not in ['new', 'contacted', 'fulfilled', 'cancelled']:
        flash('Invalid status', 'error')
        return redirect(url_for('website.view_order_request', id=id))
    
    user = User.query.filter_by(username=session['username']).first()
    
    order.status = new_status
    order.notes = notes
    order.reviewed_by = user.id
    
    if new_status == 'fulfilled':
        order.fulfilled_at = datetime.utcnow()
    
    db.session.commit()
    
    log_action('update_order_status', f'{id}: {new_status}')
    flash(f'Order marked as {new_status}', 'success')
    return redirect(url_for('website.order_requests'))


# ============ REAL-TIME NOTIFICATION API ============

@website_bp.route('/api/new-orders')
@staff_required
def check_new_orders():
    """Check for new orders since a given timestamp. Used by polling notifications.

    Filtered by section: boutique workers see boutique orders only, etc.
    Finance workers get empty (they poll /api/new-inquiries instead).
    """
    section = get_user_section()
    if section == 'finance':
        return jsonify({'orders': [], 'count': 0})

    since = request.args.get('since')
    query = WebsiteOrderRequest.query.filter_by(status='new', is_active=True)
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            query = query.filter(WebsiteOrderRequest.submitted_at > since_dt)
        except (ValueError, TypeError):
            pass
    all_orders = query.order_by(WebsiteOrderRequest.submitted_at.desc()).all()
    orders = filter_orders_by_section(all_orders)
    return jsonify({
        'orders': [{
            'id': o.id,
            'customer_name': o.customer_name,
            'customer_phone': o.customer_phone,
            'items': o.items,
            'total_amount': o.total_amount,
            'item_count': o.item_count,
            'submitted_at': o.submitted_at.isoformat() if o.submitted_at else None
        } for o in orders],
        'count': len(orders)
    })


@website_bp.route('/api/new-inquiries')
@staff_required
def check_new_inquiries():
    """Check for new loan inquiries since a given timestamp.

    Only finance workers and managers get loan inquiry notifications.
    """
    section = get_user_section()
    if section in ('boutique', 'hardware'):
        return jsonify({'inquiries': [], 'count': 0})

    since = request.args.get('since')
    query = WebsiteLoanInquiry.query.filter_by(status='new', is_active=True)
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            query = query.filter(WebsiteLoanInquiry.submitted_at > since_dt)
        except (ValueError, TypeError):
            pass
    inquiries = query.order_by(WebsiteLoanInquiry.submitted_at.desc()).all()
    return jsonify({
        'inquiries': [i.to_dict() for i in inquiries],
        'count': len(inquiries)
    })
