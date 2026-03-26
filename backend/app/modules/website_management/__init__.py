"""
Website Management Module - Manager-Only Control Plane

This module provides managers with full control over:
- Published products (what appears on public website)
- Website images (banners, product images)
- Loan inquiry inbox (demand signals)
- Order request inbox (cart submissions)

CRITICAL: This module is accessible ONLY to managers.
"""
from datetime import datetime
from functools import wraps
from decimal import Decimal, InvalidOperation
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, current_app
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models.user import User
from app.models.website import (
    WebsiteLoanInquiry,
    WebsiteOrderRequest,
    PublishedProduct,
    WebsiteImage,
    WebsiteSettings,
)
from app.models.finance import LoanClient
from app.models.boutique import BoutiqueStock, BoutiqueCategory
from app.models.hardware import HardwareStock, HardwareCategory
from app.modules.auth import get_session_user, log_action as audit_log_action
from app.utils.branding import get_site_settings
from app.utils.timezone import get_local_now
import os

website_bp = Blueprint('website', __name__, template_folder='../../templates/website_management')

from app.utils.uploads import allowed_image, validate_and_save_image


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
        user = get_session_user()
        requested_section = session.get('section')

        if not user:
            session.clear()
            flash('Please login to access the website controls.', 'error')
            return redirect(url_for('auth.login', next=request.path))

        if not user.is_active:
            session.clear()
            flash('Your account is inactive. Contact your manager.', 'error')
            return redirect(url_for('auth.login'))

        if requested_section and not user.has_access_to(requested_section):
            flash('Your current session no longer has access to this area.', 'error')
            return redirect(url_for('auth.login'))

        return f(*args, **kwargs)
    return decorated_function


def safe_decimal(value, default='0'):
    normalized = str(value or '').strip()
    if not normalized:
        return Decimal(default)
    try:
        return Decimal(normalized)
    except (InvalidOperation, ValueError):
        return Decimal(default)


def get_current_website_user():
    return get_session_user()


def get_user_section():
    """Get current user's section for filtering."""
    user = get_current_website_user()
    return session.get('section') or (user.role if user else '')


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


def can_manage_loan_inquiries():
    return get_user_section() in ('manager', 'finance')


def can_access_order(order):
    if get_user_section() == 'manager':
        return True
    if get_user_section() == 'finance':
        return False
    for item in order.items or []:
        item_type = item.get('type') or item.get('product_type')
        if item_type == get_user_section():
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


def log_website_action(action, entity, entity_id=None, details=None):
    user = get_current_website_user()
    if not user:
        return
    audit_log_action(
        user.username,
        session.get('section') or user.role,
        action,
        entity,
        entity_id,
        details,
    )


def ensure_finance_client_for_inquiry(inquiry):
    if inquiry.finance_client_id and inquiry.finance_client:
        if not inquiry.finance_client.is_active:
            inquiry.finance_client.is_active = True
        return inquiry.finance_client, False

    existing = LoanClient.query.filter_by(phone=(inquiry.phone or '').strip()).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
        if not existing.name:
            existing.name = inquiry.full_name.strip()
        inquiry.finance_client_id = existing.id
        return existing, False

    client = LoanClient(
        name=(inquiry.full_name or '').strip(),
        phone=(inquiry.phone or '').strip(),
        payer_status='neutral',
        address='',
        is_active=True,
    )
    db.session.add(client)
    db.session.flush()
    inquiry.finance_client_id = client.id
    return client, True


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
        user_section=section,
        website_settings=WebsiteSettings.get_settings(),
    )


@website_bp.route('/settings', methods=['GET', 'POST'])
@staff_required
def website_settings():
    """Global website branding and public loan settings."""
    settings = WebsiteSettings.query.first()
    user = get_current_website_user()

    if request.method == 'POST':
        if not settings:
            settings = WebsiteSettings()
            db.session.add(settings)

        loan_interest_rate = safe_decimal(request.form.get('loan_interest_rate', '0'))
        loan_min_amount = safe_decimal(request.form.get('loan_min_amount', '0'))
        loan_max_amount = safe_decimal(request.form.get('loan_max_amount', '0'))
        loan_approval_hours = request.form.get('loan_approval_hours', type=int) or 48

        if loan_interest_rate < 0 or loan_interest_rate > Decimal('100'):
            flash('Public interest rate must be between 0 and 100.', 'error')
            return redirect(url_for('website.website_settings'))
        if loan_min_amount < 0 or loan_max_amount < 0:
            flash('Loan amounts cannot be negative.', 'error')
            return redirect(url_for('website.website_settings'))
        if loan_max_amount and loan_min_amount and loan_max_amount < loan_min_amount:
            flash('Maximum loan amount must be greater than or equal to the minimum amount.', 'error')
            return redirect(url_for('website.website_settings'))
        if loan_approval_hours <= 0 or loan_approval_hours > 720:
            flash('Approval turnaround must be between 1 and 720 hours.', 'error')
            return redirect(url_for('website.website_settings'))

        settings.company_name = request.form.get('company_name', 'Denove').strip() or 'Denove'
        settings.company_suffix = request.form.get('company_suffix', 'APS').strip() or 'APS'
        settings.tagline = request.form.get('tagline', '').strip() or None
        settings.announcement_text = request.form.get('announcement_text', '').strip() or None
        settings.hero_title = request.form.get('hero_title', '').strip() or None
        settings.hero_description = request.form.get('hero_description', '').strip() or None
        settings.contact_phone = request.form.get('contact_phone', '').strip() or None
        settings.whatsapp_number = request.form.get('whatsapp_number', '').strip() or None
        settings.contact_email = request.form.get('contact_email', '').strip() or None
        settings.headquarters = request.form.get('headquarters', '').strip() or None
        settings.service_area = request.form.get('service_area', '').strip() or None
        settings.loan_interest_rate = loan_interest_rate
        settings.loan_interest_rate_label = request.form.get('loan_interest_rate_label', '').strip() or 'interest per month'
        settings.loan_min_amount = loan_min_amount
        settings.loan_max_amount = loan_max_amount
        settings.loan_repayment_note = request.form.get('loan_repayment_note', '').strip() or None
        settings.loan_approval_hours = loan_approval_hours
        settings.footer_description = request.form.get('footer_description', '').strip() or None
        settings.updated_by = user.id if user else None

        logo_file = request.files.get('logo_file')
        if logo_file and logo_file.filename:
            if not allowed_image(logo_file.filename):
                flash('Invalid logo file. Please upload PNG, JPG, JPEG, or GIF.', 'error')
                return redirect(url_for('website.website_settings'))

            upload_dir = os.path.join(current_app.static_folder, 'uploads', 'website')
            os.makedirs(upload_dir, exist_ok=True)
            extension = logo_file.filename.rsplit('.', 1)[1].lower()
            if extension not in {'png', 'jpg', 'jpeg', 'gif'}:
                flash('Please upload a PNG, JPG, JPEG, or GIF logo so it can appear correctly on documents too.', 'error')
                return redirect(url_for('website.website_settings'))
            filename = f'logo_{get_local_now().strftime("%Y%m%d%H%M%S")}.{extension}'
            file_path = os.path.join(upload_dir, filename)
            if not validate_and_save_image(logo_file, file_path):
                flash('The selected logo file is not a valid image.', 'error')
                return redirect(url_for('website.website_settings'))
            settings.logo_path = f'uploads/website/{filename}'

        db.session.commit()
        log_website_action('update', 'website_settings', settings.id, {'company_name': settings.company_name})
        flash('Website settings updated successfully.', 'success')
        return redirect(url_for('website.website_settings'))

    return render_template('website_management/settings.html', settings=get_site_settings())


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
        existing.published_at = get_local_now()
        existing.published_by = user.id
    else:
        published = PublishedProduct(
            product_type=product_type,
            product_id=product_id,
            is_published=True,
            is_featured=is_featured,
            public_price=public_price if public_price else None,
            published_at=get_local_now(),
            published_by=user.id
        )
        db.session.add(published)
    
    db.session.commit()
    log_website_action('publish', 'published_product', existing.id if existing else published.id, {
        'product_type': product_type,
        'product_id': product_id,
    })
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
    
    log_website_action('unpublish', 'published_product', published.id, {
        'product_type': published.product_type,
        'product_id': published.product_id,
    })
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
    published.published_at = get_local_now()
    db.session.commit()

    log_website_action('republish', 'published_product', published.id, {
        'product_type': published.product_type,
        'product_id': published.product_id,
    })
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
    is_featured = request.form.get('is_featured') == 'on'
    public_price = request.form.get('public_price', type=float)

    published.is_featured = is_featured
    published.public_price = public_price if public_price else None
    published.updated_at = get_local_now()

    # Republish if currently unpublished
    should_publish = request.form.get('republish') == 'on'
    if should_publish and not published.is_published:
        published.is_published = True
        published.published_at = get_local_now()

    db.session.commit()
    log_website_action('update', 'published_product', published.id, {
        'product_type': published.product_type,
        'product_id': published.product_id,
        'is_featured': published.is_featured,
        'public_price': float(published.public_price) if published.public_price else None,
    })
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

    log_website_action('delete', 'published_product', id, {'product_info': product_info})
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
    
    # Validate and save file
    filename = secure_filename(file.filename)
    timestamp = get_local_now().strftime('%Y%m%d%H%M%S')
    filename = f"{timestamp}_{filename}"
    file_path = os.path.join(upload_dir, filename)
    if not validate_and_save_image(file, file_path):
        flash('Invalid image file. The file appears corrupted or is not a real image.', 'error')
        return redirect(url_for('website.images'))

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
    
    log_website_action('upload', 'website_image', image.id, {'filename': filename})
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
    log_website_action('toggle', 'website_image', image.id, {'status': status})
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
    if not can_manage_loan_inquiries():
        flash('Loan inquiries are handled by finance staff.', 'error')
        return redirect(url_for('website.order_requests'))
    inquiry = WebsiteLoanInquiry.query.get_or_404(id)
    return render_template('website_management/loan_inquiry_detail.html', inquiry=inquiry)


@website_bp.route('/loan-inquiries/<int:id>/status', methods=['POST'])
@staff_required
def update_inquiry_status(id):
    """Update loan inquiry status."""
    if not can_manage_loan_inquiries():
        flash('Loan inquiries are handled by finance staff.', 'error')
        return redirect(url_for('website.order_requests'))

    inquiry = WebsiteLoanInquiry.query.get_or_404(id)
    new_status = request.form.get('status')
    notes = request.form.get('notes', '')
    add_to_client_list = request.form.get('add_to_client_list') == 'on'
    
    if new_status not in ['new', 'reviewed', 'approved', 'rejected']:
        flash('Invalid status', 'error')
        return redirect(url_for('website.view_loan_inquiry', id=id))
    
    user = User.query.filter_by(username=session['username']).first()
    
    inquiry.status = new_status
    inquiry.notes = notes
    inquiry.reviewed_by = user.id
    inquiry.reviewed_at = get_local_now()
    linked_client = None
    client_created = False
    if new_status == 'approved' and add_to_client_list:
        linked_client, client_created = ensure_finance_client_for_inquiry(inquiry)
    db.session.commit()
    
    log_details = {'status': new_status}
    if linked_client:
        log_details['finance_client_id'] = linked_client.id
        log_details['finance_client_created'] = client_created
    log_website_action('update', 'website_loan_inquiry', inquiry.id, log_details)

    if linked_client and client_created:
        flash(f'Inquiry marked as {new_status} and added to Finance clients.', 'success')
    elif linked_client:
        flash(f'Inquiry marked as {new_status} and linked to an existing Finance client.', 'success')
    else:
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
    if not can_access_order(order):
        flash('You do not have permission to view this order request.', 'error')
        return redirect(url_for('website.order_requests'))
    return render_template('website_management/order_request_detail.html', order=order)


@website_bp.route('/order-requests/<int:id>/status', methods=['POST'])
@staff_required
def update_order_status(id):
    """Update order request status."""
    order = WebsiteOrderRequest.query.get_or_404(id)
    if not can_access_order(order):
        flash('You do not have permission to update this order request.', 'error')
        return redirect(url_for('website.order_requests'))
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
        order.fulfilled_at = get_local_now()
    
    db.session.commit()
    
    log_website_action('update', 'website_order_request', order.id, {'status': new_status})
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
