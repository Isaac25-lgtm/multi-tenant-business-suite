from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response
from app.models.hardware import (
    HardwareCategory, HardwareStock, HardwareSale,
    HardwareSaleItem, HardwareCreditPayment
)
from app.models.customer import Customer
from app.modules.auth import login_required, log_action
from app.extensions import db
from app.utils.timezone import get_local_today
from app.utils.utils import generate_reference_number
from app.utils.image_fetch import fetch_product_image_async, fetch_product_image
from app.utils.pdf_generator import generate_receipt_pdf
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

hardware_bp = Blueprint('hardware', __name__)

AUTO_IMAGE_FETCH_SESSION_KEY = 'hardware_auto_image_fetch_date'


def safe_decimal(value, default='0'):
    """Safely convert a value to Decimal, handling empty strings and invalid values"""
    if value is None or value == '':
        return Decimal(default)
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return Decimal(default)


def parse_receipt_items(form):
    """Parse receipt item rows from a form submission."""
    names = form.getlist('item_name[]')
    quantities = form.getlist('quantity[]')
    prices = form.getlist('price[]')
    items = []

    for i, name in enumerate(names):
        name = (name or '').strip()
        if not name:
            continue

        qty_raw = quantities[i] if i < len(quantities) else '0'
        price_raw = prices[i] if i < len(prices) else '0'
        qty = safe_decimal(qty_raw, '0')
        price = safe_decimal(price_raw, '0')

        if qty <= 0 or price <= 0:
            continue

        subtotal = qty * price
        qty_value = int(qty) if qty == qty.to_integral() else float(qty)

        items.append({
            'item_name': name,
            'quantity': qty_value,
            'unit_price': float(price),
            'subtotal': float(subtotal)
        })

    return items


def check_date_permission(entry_date, user_section):
    """Check if user has permission to enter data for the given date"""
    today = get_local_today()
    yesterday = today - timedelta(days=1)
    if user_section == 'manager':
        return True
    return yesterday <= entry_date <= today


def auto_fetch_missing_images():
    """Auto-fetch images for hardware items missing an image URL."""
    items = HardwareStock.query.filter(
        HardwareStock.is_active == True,
        db.or_(HardwareStock.image_url == None, HardwareStock.image_url == '')
    ).all()

    for item in items:
        category_name = item.category.name if item.category else None
        fetch_product_image_async(item.id, item.item_name, category_name, model_class='HardwareStock')

    return len(items)


@hardware_bp.route('/')
@login_required('hardware')
def index():
    """Hardware overview page"""
    today = get_local_today()
    try:
        stock_count = HardwareStock.query.filter_by(is_active=True).count()
        low_stock = HardwareStock.query.filter(
            HardwareStock.is_active == True,
            HardwareStock.quantity <= HardwareStock.low_stock_threshold
        ).count()
        pending_credits = HardwareSale.query.filter(
            HardwareSale.is_deleted == False,
            HardwareSale.payment_type == 'part',
            HardwareSale.is_credit_cleared == False
        ).count()
        today_sales = HardwareSale.query.filter(
            HardwareSale.sale_date == today,
            HardwareSale.is_deleted == False
        ).count()
    except Exception:
        db.session.rollback()
        stock_count = low_stock = pending_credits = today_sales = 0

    return render_template('hardware/index.html',
        stock_count=stock_count, low_stock=low_stock,
        pending_credits=pending_credits, today_sales=today_sales
    )


@hardware_bp.route('/categories')
@login_required('hardware')
def categories():
    cats = HardwareCategory.query.order_by(HardwareCategory.name).all()
    return render_template('hardware/categories.html', categories=cats)


@hardware_bp.route('/categories/add', methods=['POST'])
@login_required('hardware')
def add_category():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Category name is required', 'error')
        return redirect(url_for('hardware.categories'))
    if HardwareCategory.query.filter_by(name=name).first():
        flash('Category already exists', 'error')
        return redirect(url_for('hardware.categories'))
    category = HardwareCategory(name=name)
    db.session.add(category)
    db.session.commit()

    log_action(session['username'], 'hardware', 'create', 'category', category.id, {'name': name})
    flash(f'Category "{name}" added', 'success')
    return redirect(url_for('hardware.categories'))


@hardware_bp.route('/stock')
@login_required('hardware')
def stock():
    # Auto-fetch missing images once per day per session
    today_str = str(get_local_today())
    if session.get(AUTO_IMAGE_FETCH_SESSION_KEY) != today_str:
        auto_fetch_missing_images()
        session[AUTO_IMAGE_FETCH_SESSION_KEY] = today_str

    show_inactive = request.args.get('show_inactive', 'false').lower() == 'true'
    query = HardwareStock.query
    if not show_inactive:
        query = query.filter_by(is_active=True)
    items = query.order_by(HardwareStock.item_name).all()
    categories = HardwareCategory.query.order_by(HardwareCategory.name).all()
    return render_template('hardware/stock.html', stock=items, categories=categories, show_inactive=show_inactive)


@hardware_bp.route('/stock/add', methods=['POST'])
@login_required('hardware')
def add_stock():
    try:
        item_name = request.form.get('item_name', '').strip()
        quantity = request.form.get('quantity', type=int)
        if not item_name or quantity is None:
            flash('Item name and quantity required', 'error')
            return redirect(url_for('hardware.stock'))

        # Handle category - either existing or new
        category_id = request.form.get('category_id')
        if category_id == 'new':
            # Create new category
            new_category_name = request.form.get('new_category', '').strip()
            if new_category_name:
                existing_cat = HardwareCategory.query.filter_by(name=new_category_name).first()
                if existing_cat:
                    category_id = existing_cat.id
                else:
                    new_category = HardwareCategory(name=new_category_name)
                    db.session.add(new_category)
                    db.session.flush()
                    category_id = new_category.id
                    log_action(session['username'], 'hardware', 'create', 'category', new_category.id,
                               {'name': new_category_name, 'created_with_stock': item_name})
            else:
                category_id = None
        else:
            category_id = int(category_id) if category_id else None

        low_stock_threshold = request.form.get('low_stock_threshold', type=int)
        if low_stock_threshold is None:
            low_stock_threshold = max(1, int(quantity * 0.25))

        stock_item = HardwareStock(
            item_name=item_name,
            category_id=category_id,
            quantity=quantity,
            initial_quantity=quantity,
            unit=request.form.get('unit', 'pieces'),
            cost_price=safe_decimal(request.form.get('cost_price', '0')),
            min_selling_price=safe_decimal(request.form.get('min_selling_price', '0')),
            max_selling_price=safe_decimal(request.form.get('max_selling_price', '0')),
            low_stock_threshold=low_stock_threshold
        )
        db.session.add(stock_item)
        db.session.commit()

        # Auto-fetch product image in the background
        category_name = None
        if category_id:
            cat = HardwareCategory.query.get(category_id)
            if cat:
                category_name = cat.name
        fetch_product_image_async(stock_item.id, item_name, category_name, model_class='HardwareStock')

        log_action(session['username'], 'hardware', 'create', 'stock', stock_item.id,
                   {'item_name': item_name, 'quantity': quantity, 'cost_price': float(stock_item.cost_price)})
        flash(f'Stock item "{item_name}" added', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('hardware.stock'))


@hardware_bp.route('/stock/<int:id>/edit', methods=['POST'])
@login_required('hardware')
def edit_stock(id):
    item = HardwareStock.query.get_or_404(id)
    try:
        old_name = item.item_name
        old_quantity = item.quantity
        item.item_name = request.form.get('item_name', item.item_name).strip()

        # Handle category - either existing or new
        category_id = request.form.get('category_id')
        if category_id == 'new':
            new_category_name = request.form.get('new_category', '').strip()
            if new_category_name:
                existing_cat = HardwareCategory.query.filter_by(name=new_category_name).first()
                if existing_cat:
                    item.category_id = existing_cat.id
                else:
                    new_category = HardwareCategory(name=new_category_name)
                    db.session.add(new_category)
                    db.session.flush()
                    item.category_id = new_category.id
                    log_action(session['username'], 'hardware', 'create', 'category', new_category.id,
                               {'name': new_category_name, 'created_with_stock_edit': item.item_name})
        elif category_id:
            item.category_id = int(category_id)

        item.unit = request.form.get('unit', item.unit)
        item.cost_price = safe_decimal(request.form.get('cost_price'), str(item.cost_price))
        item.min_selling_price = safe_decimal(request.form.get('min_selling_price'), str(item.min_selling_price))
        item.max_selling_price = safe_decimal(request.form.get('max_selling_price'), str(item.max_selling_price))
        item.low_stock_threshold = request.form.get('low_stock_threshold', type=int) or item.low_stock_threshold

        # Handle stock adjustment (add/subtract)
        adjustment = request.form.get('stock_adjustment', type=int, default=0)
        if adjustment != 0:
            item.quantity += adjustment
            if item.quantity < 0:
                item.quantity = 0

        db.session.commit()

        # Log stock adjustment separately for audit trail
        if adjustment != 0:
            log_action(session['username'], 'hardware', 'adjust', 'stock', item.id,
                       {'item_name': item.item_name, 'old_quantity': old_quantity,
                        'adjustment': adjustment, 'new_quantity': item.quantity,
                        'reason': 'Stock adjusted via edit'})

        details = {'item_name': item.item_name, 'old_name': old_name}
        if adjustment != 0:
            details['stock_adjustment'] = adjustment
            details['old_quantity'] = old_quantity
            details['new_quantity'] = item.quantity
        log_action(session['username'], 'hardware', 'update', 'stock', item.id, details)
        flash(f'Stock item updated', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('hardware.stock'))


@hardware_bp.route('/stock/<int:id>/adjust', methods=['POST'])
@login_required('hardware')
def adjust_stock(id):
    """Adjust stock quantity"""
    item = HardwareStock.query.get_or_404(id)
    try:
        adjustment = request.form.get('adjustment', type=int, default=0)
        old_quantity = item.quantity
        item.quantity += adjustment
        if item.quantity < 0:
            item.quantity = 0
        db.session.commit()

        log_action(session['username'], 'hardware', 'adjust', 'stock', item.id,
                   {'item_name': item.item_name, 'old_quantity': old_quantity,
                    'adjustment': adjustment, 'new_quantity': item.quantity})
        flash(f'Stock adjusted for "{item.item_name}"', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('hardware.stock'))


@hardware_bp.route('/stock/<int:id>/delete', methods=['POST'])
@login_required('hardware')
def delete_stock(id):
    item = HardwareStock.query.get_or_404(id)
    item.is_active = False
    db.session.commit()

    log_action(session['username'], 'hardware', 'delete', 'stock', item.id,
               {'item_name': item.item_name})
    flash(f'Stock item deactivated', 'success')
    return redirect(url_for('hardware.stock'))


@hardware_bp.route('/stock/<int:id>/reactivate', methods=['POST'])
@login_required('hardware')
def reactivate_stock(id):
    """Reactivate a deactivated stock item"""
    item = HardwareStock.query.get_or_404(id)
    item.is_active = True
    db.session.commit()

    log_action(session['username'], 'hardware', 'reactivate', 'stock', item.id,
               {'item_name': item.item_name})
    flash(f'Stock item "{item.item_name}" reactivated', 'success')
    return redirect(url_for('hardware.stock'))


@hardware_bp.route('/stock/<int:id>/permanent-delete', methods=['POST'])
@login_required('hardware')
def permanent_delete_stock(id):
    """Permanently delete a stock item - manager only"""
    user_section = session.get('section', '')
    if user_section != 'manager':
        flash('Only managers can permanently delete stock items', 'error')
        return redirect(url_for('hardware.stock'))

    item = HardwareStock.query.get_or_404(id)
    item_name = item.item_name

    db.session.delete(item)
    db.session.commit()

    log_action(session['username'], 'hardware', 'permanent_delete', 'stock', id,
               {'item_name': item_name})
    flash(f'Stock item "{item_name}" permanently deleted', 'success')
    return redirect(url_for('hardware.stock'))


@hardware_bp.route('/stock/<int:id>/refresh-image', methods=['POST'])
@login_required('hardware')
def refresh_image(id):
    """Re-fetch the product image for a stock item"""
    item = HardwareStock.query.get_or_404(id)
    category_name = item.category.name if item.category else None
    image_url = fetch_product_image(item.item_name, category_name, search_context='hardware building material')
    if image_url:
        item.image_url = image_url
        db.session.commit()
        flash(f'Image refreshed for "{item.item_name}"', 'success')
    else:
        flash(f'No image found for "{item.item_name}"', 'warning')
    return redirect(url_for('hardware.stock'))


@hardware_bp.route('/stock/fetch-all-images', methods=['POST'])
@login_required('hardware')
def fetch_all_images():
    """Clear all existing images and re-fetch for all active stock items"""
    items = HardwareStock.query.filter(HardwareStock.is_active == True).all()

    # Clear all existing images first so they all get re-fetched
    for item in items:
        item.image_url = None
    db.session.commit()

    count = 0
    for item in items:
        category_name = item.category.name if item.category else None
        fetch_product_image_async(item.id, item.item_name, category_name, model_class='HardwareStock')
        count += 1

    flash(f'Re-fetching images for {count} items in the background. Refresh the page in a few seconds.', 'success')
    return redirect(url_for('hardware.stock'))


@hardware_bp.route('/sales')
@login_required('hardware')
def sales():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    query = HardwareSale.query.filter_by(is_deleted=False)
    if start_date:
        query = query.filter(HardwareSale.sale_date >= date.fromisoformat(start_date))
    if end_date:
        query = query.filter(HardwareSale.sale_date <= date.fromisoformat(end_date))
    sales_list = query.order_by(HardwareSale.sale_date.desc(), HardwareSale.id.desc()).limit(100).all()
    return render_template('hardware/sales.html', sales=sales_list, start_date=start_date, end_date=end_date)


@hardware_bp.route('/sales/new')
@login_required('hardware')
def new_sale():
    stock_items = HardwareStock.query.filter_by(is_active=True).filter(HardwareStock.quantity > 0).all()
    customers = Customer.query.filter_by(business_type='hardware').order_by(Customer.name).all()
    return render_template('hardware/sale_form.html', stock=stock_items, customers=customers, today=get_local_today())


@hardware_bp.route('/sales/create', methods=['POST'])
@login_required('hardware')
def create_sale():
    try:
        sale_date = date.fromisoformat(request.form.get('sale_date', str(get_local_today())))
        payment_type = request.form.get('payment_type', 'full')
        customer_id = request.form.get('customer_id', type=int)
        amount_paid = safe_decimal(request.form.get('amount_paid', '0'))

        # Check date permission for non-managers
        user_section = session.get('section', '')
        if not check_date_permission(sale_date, user_section):
            flash('You can only enter sales for today or yesterday. Contact a manager for older entries.', 'error')
            return redirect(url_for('hardware.new_sale'))

        item_ids = request.form.getlist('item_id[]')
        quantities = request.form.getlist('quantity[]')
        prices = request.form.getlist('price[]')

        if not item_ids:
            flash('At least one item required', 'error')
            return redirect(url_for('hardware.new_sale'))

        total_amount = Decimal('0')
        items_data = []
        for i, item_id in enumerate(item_ids):
            # Skip empty items
            if not item_id or not quantities[i] or not prices[i]:
                continue

            try:
                qty = int(quantities[i])
                price = safe_decimal(prices[i])
            except (ValueError, TypeError):
                continue

            if qty <= 0 or price <= 0:
                continue

            subtotal = qty * price
            total_amount += subtotal
            stock_item = HardwareStock.query.get(int(item_id))
            if stock_item:
                items_data.append({
                    'stock_id': stock_item.id, 'item_name': stock_item.item_name,
                    'quantity': qty, 'unit_price': price, 'subtotal': subtotal
                })

        if not items_data:
            flash('At least one valid item with quantity and price is required', 'error')
            return redirect(url_for('hardware.new_sale'))

        if payment_type == 'full':
            amount_paid = total_amount
        balance = total_amount - amount_paid

        if payment_type == 'part' and not customer_id:
            customer_name = request.form.get('customer_name', '').strip()
            customer_phone = request.form.get('customer_phone', '').strip()
            if customer_name and customer_phone:
                customer = Customer(name=customer_name, phone=customer_phone, business_type='hardware')
                db.session.add(customer)
                db.session.flush()
                customer_id = customer.id

        sale = HardwareSale(
            reference_number=generate_reference_number('DNV-H-', HardwareSale),
            sale_date=sale_date, customer_id=customer_id, payment_type=payment_type,
            total_amount=total_amount, amount_paid=amount_paid, balance=balance,
            is_credit_cleared=(balance <= 0)
        )
        db.session.add(sale)
        db.session.flush()

        for item_data in items_data:
            sale_item = HardwareSaleItem(
                sale_id=sale.id, stock_id=item_data['stock_id'],
                item_name=item_data['item_name'], quantity=item_data['quantity'],
                unit_price=item_data['unit_price'], subtotal=item_data['subtotal']
            )
            db.session.add(sale_item)
            stock = HardwareStock.query.get(item_data['stock_id'])
            if stock:
                stock.quantity -= item_data['quantity']

        db.session.commit()

        log_action(session['username'], 'hardware', 'create', 'sale', sale.id,
                   {'reference': sale.reference_number, 'total': float(total_amount),
                    'payment_type': payment_type, 'items_count': len(items_data)})
        flash(f'Sale {sale.reference_number} created', 'success')
        return redirect(url_for('hardware.sales'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('hardware.new_sale'))


@hardware_bp.route('/sales/<int:id>')
@login_required('hardware')
def view_sale(id):
    sale = HardwareSale.query.get_or_404(id)
    items = sale.items.all()
    payments = HardwareCreditPayment.query.filter_by(sale_id=id).order_by(HardwareCreditPayment.payment_date.desc()).all()
    return render_template('hardware/sale_detail.html', sale=sale, items=items, payments=payments)


@hardware_bp.route('/sales/<int:id>/receipt/preview')
@login_required('hardware')
def receipt_preview(id):
    """Preview receipt with editable items before download"""
    sale = HardwareSale.query.get_or_404(id)
    items = sale.items.all()
    return render_template('hardware/receipt_preview.html',
        sale=sale,
        items=items,
        business_name="HARDWARE",
        is_full_payment=(sale.payment_type == 'full')
    )


@hardware_bp.route('/sales/<int:id>/receipt', methods=['GET', 'POST'])
@login_required('hardware')
def download_receipt(id):
    """Download sale receipt as PDF"""
    sale = HardwareSale.query.get_or_404(id)
    items_override = None
    totals_override = None
    meta_override = None
    served_by_override = session.get('username')
    business_name_override = "HARDWARE"

    if request.method == 'POST':
        business_name_input = request.form.get('receipt_business_name', '').strip()
        if business_name_input:
            business_name_override = business_name_input
        served_by_input = request.form.get('receipt_served_by', '').strip()
        if served_by_input:
            served_by_override = served_by_input

        meta_override = {
            'sale_date': request.form.get('receipt_date', '').strip() or None,
            'customer_name': request.form.get('receipt_customer', '').strip() or None,
            'phone': request.form.get('receipt_phone', '').strip() or None,
            'address': request.form.get('receipt_address', '').strip() or None
        }

        items_override = parse_receipt_items(request.form)
        if not items_override:
            flash('Please add at least one valid item before downloading the receipt.', 'error')
            return redirect(url_for('hardware.receipt_preview', id=id))

        total_amount = sum(item['subtotal'] for item in items_override)
        amount_paid = safe_decimal(request.form.get('amount_paid', str(sale.amount_paid)), str(sale.amount_paid))
        amount_paid_value = float(amount_paid)
        if amount_paid_value > total_amount:
            flash('Amount paid cannot exceed the total amount.', 'error')
            return redirect(url_for('hardware.receipt_preview', id=id))

        balance_value = max(total_amount - amount_paid_value, 0)
        payment_type = 'full' if balance_value <= 0 else 'part'
        totals_override = {
            'total_amount': total_amount,
            'amount_paid': amount_paid_value,
            'balance': balance_value,
            'payment_type': payment_type
        }

    buffer = generate_receipt_pdf(
        sale,
        business_name_override,
        served_by=served_by_override,
        items_override=items_override,
        totals_override=totals_override,
        meta_override=meta_override
    )
    filename = f"receipt_{sale.reference_number}.pdf"
    return Response(
        buffer.getvalue(),
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


@hardware_bp.route('/sales/<int:id>/delete', methods=['POST'])
@login_required('hardware')
def delete_sale(id):
    sale = HardwareSale.query.get_or_404(id)
    try:
        for item in sale.items:
            if item.stock_id:
                stock = HardwareStock.query.get(item.stock_id)
                if stock:
                    stock.quantity += item.quantity
        sale.is_deleted = True
        sale.deleted_at = db.func.now()
        db.session.commit()

        log_action(session['username'], 'hardware', 'delete', 'sale', sale.id,
                   {'reference': sale.reference_number, 'total': float(sale.total_amount)})
        flash(f'Sale deleted', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('hardware.sales'))


@hardware_bp.route('/credits')
@login_required('hardware')
def credits():
    pending = HardwareSale.query.filter(
        HardwareSale.is_deleted == False, HardwareSale.payment_type == 'part',
        HardwareSale.is_credit_cleared == False, HardwareSale.balance > 0
    ).order_by(HardwareSale.sale_date.desc()).all()
    return render_template('hardware/credits.html', credits=pending)


@hardware_bp.route('/credits/<int:id>/pay', methods=['POST'])
@login_required('hardware')
def pay_credit(id):
    sale = HardwareSale.query.get_or_404(id)
    try:
        amount = safe_decimal(request.form.get('amount', '0'))
        payment_date = date.fromisoformat(request.form.get('payment_date', str(get_local_today())))

        # Check date permission for non-managers
        user_section = session.get('section', '')
        if not check_date_permission(payment_date, user_section):
            flash('You can only enter payments for today or yesterday. Contact a manager for older entries.', 'error')
            return redirect(url_for('hardware.credits'))

        if amount <= 0:
            flash('Amount must be greater than 0', 'error')
            return redirect(url_for('hardware.credits'))

        sale.amount_paid += amount
        sale.balance = sale.total_amount - sale.amount_paid
        if sale.balance <= 0:
            sale.balance = Decimal('0')
            sale.is_credit_cleared = True

        payment = HardwareCreditPayment(
            sale_id=sale.id, payment_date=payment_date,
            amount=amount, remaining_balance=sale.balance
        )
        db.session.add(payment)
        db.session.commit()

        log_action(session['username'], 'hardware', 'create', 'credit_payment', payment.id,
                   {'sale_reference': sale.reference_number, 'amount': float(amount),
                    'remaining_balance': float(sale.balance)})
        flash(f'Payment recorded', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('hardware.credits'))
