from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.models.hardware import (
    HardwareCategory, HardwareStock, HardwareSale,
    HardwareSaleItem, HardwareCreditPayment
)
from app.models.customer import Customer
from app.modules.auth import login_required, log_action
from app.extensions import db
from app.utils.timezone import get_local_today
from app.utils.utils import generate_reference_number
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

hardware_bp = Blueprint('hardware', __name__)


def safe_decimal(value, default='0'):
    """Safely convert a value to Decimal, handling empty strings and invalid values"""
    if value is None or value == '':
        return Decimal(default)
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return Decimal(default)


def check_date_permission(entry_date, user_section):
    """Check if user has permission to enter data for the given date"""
    today = get_local_today()
    yesterday = today - timedelta(days=1)
    if user_section == 'manager':
        return True
    return yesterday <= entry_date <= today


@hardware_bp.route('/')
@login_required('hardware')
def index():
    """Hardware overview page"""
    today = get_local_today()
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

        low_stock_threshold = request.form.get('low_stock_threshold', type=int)
        if low_stock_threshold is None:
            low_stock_threshold = max(1, int(quantity * 0.25))

        stock_item = HardwareStock(
            item_name=item_name,
            category_id=request.form.get('category_id', type=int),
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

        log_action(session['username'], 'hardware', 'create', 'stock', stock_item.id,
                   {'item_name': item_name, 'quantity': quantity})
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
        item.item_name = request.form.get('item_name', item.item_name).strip()
        item.category_id = request.form.get('category_id', type=int) or item.category_id
        item.unit = request.form.get('unit', item.unit)
        item.cost_price = safe_decimal(request.form.get('cost_price'), str(item.cost_price))
        item.min_selling_price = safe_decimal(request.form.get('min_selling_price'), str(item.min_selling_price))
        item.max_selling_price = safe_decimal(request.form.get('max_selling_price'), str(item.max_selling_price))
        item.low_stock_threshold = request.form.get('low_stock_threshold', type=int) or item.low_stock_threshold
        db.session.commit()

        log_action(session['username'], 'hardware', 'update', 'stock', item.id,
                   {'item_name': item.item_name, 'old_name': old_name})
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
