from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.models.boutique import (
    BoutiqueCategory, BoutiqueStock, BoutiqueSale,
    BoutiqueSaleItem, BoutiqueCreditPayment
)
from app.models.customer import Customer
from app.modules.auth import login_required, log_action
from app.extensions import db
from app.utils.timezone import get_local_today
from app.utils.utils import generate_reference_number
from datetime import date
from decimal import Decimal

boutique_bp = Blueprint('boutique', __name__)


@boutique_bp.route('/')
@login_required('boutique')
def index():
    """Boutique overview page"""
    today = get_local_today()

    # Quick stats
    stock_count = BoutiqueStock.query.filter_by(is_active=True).count()
    low_stock = BoutiqueStock.query.filter(
        BoutiqueStock.is_active == True,
        BoutiqueStock.quantity <= BoutiqueStock.low_stock_threshold
    ).count()
    pending_credits = BoutiqueSale.query.filter(
        BoutiqueSale.is_deleted == False,
        BoutiqueSale.payment_type == 'part',
        BoutiqueSale.is_credit_cleared == False
    ).count()
    today_sales = BoutiqueSale.query.filter(
        BoutiqueSale.sale_date == today,
        BoutiqueSale.is_deleted == False
    ).count()

    return render_template('boutique/index.html',
        stock_count=stock_count,
        low_stock=low_stock,
        pending_credits=pending_credits,
        today_sales=today_sales
    )


# ============ CATEGORIES ============

@boutique_bp.route('/categories')
@login_required('boutique')
def categories():
    """List all categories"""
    cats = BoutiqueCategory.query.order_by(BoutiqueCategory.name).all()
    return render_template('boutique/categories.html', categories=cats)


@boutique_bp.route('/categories/add', methods=['POST'])
@login_required('boutique')
def add_category():
    """Add a new category"""
    name = request.form.get('name', '').strip()
    if not name:
        flash('Category name is required', 'error')
        return redirect(url_for('boutique.categories'))

    if BoutiqueCategory.query.filter_by(name=name).first():
        flash('Category already exists', 'error')
        return redirect(url_for('boutique.categories'))

    category = BoutiqueCategory(name=name)
    db.session.add(category)
    db.session.commit()

    log_action(session['username'], 'boutique', 'create', 'category', category.id, {'name': name})
    flash(f'Category "{name}" added successfully', 'success')
    return redirect(url_for('boutique.categories'))


# ============ STOCK ============

@boutique_bp.route('/stock')
@login_required('boutique')
def stock():
    """List all stock items"""
    show_inactive = request.args.get('show_inactive', 'false').lower() == 'true'
    query = BoutiqueStock.query
    if not show_inactive:
        query = query.filter_by(is_active=True)
    items = query.order_by(BoutiqueStock.item_name).all()
    categories = BoutiqueCategory.query.order_by(BoutiqueCategory.name).all()
    return render_template('boutique/stock.html',
        stock=items,
        categories=categories,
        show_inactive=show_inactive
    )


@boutique_bp.route('/stock/add', methods=['POST'])
@login_required('boutique')
def add_stock():
    """Add a new stock item"""
    try:
        item_name = request.form.get('item_name', '').strip()
        category_id = request.form.get('category_id', type=int)
        quantity = request.form.get('quantity', type=int)
        unit = request.form.get('unit', 'pieces')
        cost_price = Decimal(request.form.get('cost_price', '0'))
        min_selling_price = Decimal(request.form.get('min_selling_price', '0'))
        max_selling_price = Decimal(request.form.get('max_selling_price', '0'))
        low_stock_threshold = request.form.get('low_stock_threshold', type=int)

        if not item_name or quantity is None or quantity < 0:
            flash('Item name and valid quantity are required', 'error')
            return redirect(url_for('boutique.stock'))

        # Auto-calculate threshold if not provided
        if low_stock_threshold is None:
            low_stock_threshold = max(1, int(quantity * 0.25))

        stock_item = BoutiqueStock(
            item_name=item_name,
            category_id=category_id,
            quantity=quantity,
            initial_quantity=quantity,
            unit=unit,
            cost_price=cost_price,
            min_selling_price=min_selling_price,
            max_selling_price=max_selling_price,
            low_stock_threshold=low_stock_threshold
        )
        db.session.add(stock_item)
        db.session.commit()

        log_action(session['username'], 'boutique', 'create', 'stock', stock_item.id,
                   {'item_name': item_name, 'quantity': quantity})
        flash(f'Stock item "{item_name}" added successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding stock: {str(e)}', 'error')

    return redirect(url_for('boutique.stock'))


@boutique_bp.route('/stock/<int:id>/edit', methods=['POST'])
@login_required('boutique')
def edit_stock(id):
    """Edit a stock item"""
    item = BoutiqueStock.query.get_or_404(id)

    try:
        old_name = item.item_name
        item.item_name = request.form.get('item_name', item.item_name).strip()
        item.category_id = request.form.get('category_id', type=int) or item.category_id
        item.unit = request.form.get('unit', item.unit)
        item.cost_price = Decimal(request.form.get('cost_price', item.cost_price))
        item.min_selling_price = Decimal(request.form.get('min_selling_price', item.min_selling_price))
        item.max_selling_price = Decimal(request.form.get('max_selling_price', item.max_selling_price))
        item.low_stock_threshold = request.form.get('low_stock_threshold', type=int) or item.low_stock_threshold
        item.is_active = request.form.get('is_active', 'true').lower() == 'true'

        db.session.commit()

        log_action(session['username'], 'boutique', 'update', 'stock', item.id,
                   {'item_name': item.item_name, 'old_name': old_name})
        flash(f'Stock item "{item.item_name}" updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating stock: {str(e)}', 'error')

    return redirect(url_for('boutique.stock'))


@boutique_bp.route('/stock/<int:id>/adjust', methods=['POST'])
@login_required('boutique')
def adjust_stock(id):
    """Adjust stock quantity"""
    item = BoutiqueStock.query.get_or_404(id)

    try:
        adjustment = request.form.get('adjustment', type=int, default=0)
        old_quantity = item.quantity
        item.quantity += adjustment
        if item.quantity < 0:
            item.quantity = 0
        db.session.commit()

        log_action(session['username'], 'boutique', 'adjust', 'stock', item.id,
                   {'item_name': item.item_name, 'old_quantity': old_quantity,
                    'adjustment': adjustment, 'new_quantity': item.quantity})
        flash(f'Stock adjusted for "{item.item_name}"', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adjusting stock: {str(e)}', 'error')

    return redirect(url_for('boutique.stock'))


@boutique_bp.route('/stock/<int:id>/delete', methods=['POST'])
@login_required('boutique')
def delete_stock(id):
    """Soft delete a stock item"""
    item = BoutiqueStock.query.get_or_404(id)
    item.is_active = False
    db.session.commit()

    log_action(session['username'], 'boutique', 'delete', 'stock', item.id,
               {'item_name': item.item_name})
    flash(f'Stock item "{item.item_name}" deactivated', 'success')
    return redirect(url_for('boutique.stock'))


# ============ SALES ============

@boutique_bp.route('/sales')
@login_required('boutique')
def sales():
    """List all sales"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = BoutiqueSale.query.filter_by(is_deleted=False)

    if start_date:
        query = query.filter(BoutiqueSale.sale_date >= date.fromisoformat(start_date))
    if end_date:
        query = query.filter(BoutiqueSale.sale_date <= date.fromisoformat(end_date))

    sales_list = query.order_by(BoutiqueSale.sale_date.desc(), BoutiqueSale.id.desc()).limit(100).all()
    return render_template('boutique/sales.html', sales=sales_list, start_date=start_date, end_date=end_date)


@boutique_bp.route('/sales/new')
@login_required('boutique')
def new_sale():
    """New sale form"""
    stock_items = BoutiqueStock.query.filter_by(is_active=True).filter(BoutiqueStock.quantity > 0).all()
    customers = Customer.query.filter_by(business_type='boutique').order_by(Customer.name).all()
    return render_template('boutique/sale_form.html', stock=stock_items, customers=customers, today=get_local_today())


@boutique_bp.route('/sales/create', methods=['POST'])
@login_required('boutique')
def create_sale():
    """Create a new sale"""
    try:
        sale_date = date.fromisoformat(request.form.get('sale_date', str(get_local_today())))
        payment_type = request.form.get('payment_type', 'full')
        customer_id = request.form.get('customer_id', type=int)
        amount_paid = Decimal(request.form.get('amount_paid', '0'))

        # Get items from form
        item_ids = request.form.getlist('item_id[]')
        quantities = request.form.getlist('quantity[]')
        prices = request.form.getlist('price[]')

        if not item_ids or not quantities or not prices:
            flash('At least one item is required', 'error')
            return redirect(url_for('boutique.new_sale'))

        # Calculate total
        total_amount = Decimal('0')
        items_data = []
        for i, item_id in enumerate(item_ids):
            qty = int(quantities[i])
            price = Decimal(prices[i])
            subtotal = qty * price
            total_amount += subtotal

            stock_item = BoutiqueStock.query.get(int(item_id))
            if stock_item:
                items_data.append({
                    'stock_id': stock_item.id,
                    'item_name': stock_item.item_name,
                    'quantity': qty,
                    'unit_price': price,
                    'subtotal': subtotal
                })

        if payment_type == 'full':
            amount_paid = total_amount

        balance = total_amount - amount_paid

        # Create customer if needed for credit sale
        if payment_type == 'part' and not customer_id:
            customer_name = request.form.get('customer_name', '').strip()
            customer_phone = request.form.get('customer_phone', '').strip()
            if customer_name and customer_phone:
                customer = Customer(name=customer_name, phone=customer_phone, business_type='boutique')
                db.session.add(customer)
                db.session.flush()
                customer_id = customer.id

        # Create sale
        sale = BoutiqueSale(
            reference_number=generate_reference_number('DNV-B-', BoutiqueSale),
            sale_date=sale_date,
            customer_id=customer_id,
            payment_type=payment_type,
            total_amount=total_amount,
            amount_paid=amount_paid,
            balance=balance,
            is_credit_cleared=(balance <= 0)
        )
        db.session.add(sale)
        db.session.flush()

        # Create sale items and update stock
        for item_data in items_data:
            sale_item = BoutiqueSaleItem(
                sale_id=sale.id,
                stock_id=item_data['stock_id'],
                item_name=item_data['item_name'],
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
                subtotal=item_data['subtotal']
            )
            db.session.add(sale_item)

            # Update stock quantity
            stock = BoutiqueStock.query.get(item_data['stock_id'])
            if stock:
                stock.quantity -= item_data['quantity']

        db.session.commit()

        log_action(session['username'], 'boutique', 'create', 'sale', sale.id,
                   {'reference': sale.reference_number, 'total': float(total_amount),
                    'payment_type': payment_type, 'items_count': len(items_data)})
        flash(f'Sale {sale.reference_number} created successfully', 'success')
        return redirect(url_for('boutique.sales'))

    except Exception as e:
        db.session.rollback()
        flash(f'Error creating sale: {str(e)}', 'error')
        return redirect(url_for('boutique.new_sale'))


@boutique_bp.route('/sales/<int:id>')
@login_required('boutique')
def view_sale(id):
    """View sale details"""
    sale = BoutiqueSale.query.get_or_404(id)
    items = sale.items.all()
    payments = BoutiqueCreditPayment.query.filter_by(sale_id=id).order_by(BoutiqueCreditPayment.payment_date.desc()).all()
    return render_template('boutique/sale_detail.html', sale=sale, items=items, payments=payments)


@boutique_bp.route('/sales/<int:id>/delete', methods=['POST'])
@login_required('boutique')
def delete_sale(id):
    """Soft delete a sale and restore stock"""
    sale = BoutiqueSale.query.get_or_404(id)

    try:
        # Restore stock quantities
        for item in sale.items:
            if item.stock_id:
                stock = BoutiqueStock.query.get(item.stock_id)
                if stock:
                    stock.quantity += item.quantity

        sale.is_deleted = True
        sale.deleted_at = db.func.now()
        db.session.commit()

        log_action(session['username'], 'boutique', 'delete', 'sale', sale.id,
                   {'reference': sale.reference_number, 'total': float(sale.total_amount)})
        flash(f'Sale {sale.reference_number} deleted', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting sale: {str(e)}', 'error')

    return redirect(url_for('boutique.sales'))


# ============ CREDITS ============

@boutique_bp.route('/credits')
@login_required('boutique')
def credits():
    """List pending credits"""
    pending = BoutiqueSale.query.filter(
        BoutiqueSale.is_deleted == False,
        BoutiqueSale.payment_type == 'part',
        BoutiqueSale.is_credit_cleared == False,
        BoutiqueSale.balance > 0
    ).order_by(BoutiqueSale.sale_date.desc()).all()

    return render_template('boutique/credits.html', credits=pending)


@boutique_bp.route('/credits/<int:id>/pay', methods=['POST'])
@login_required('boutique')
def pay_credit(id):
    """Record a credit payment"""
    sale = BoutiqueSale.query.get_or_404(id)

    try:
        amount = Decimal(request.form.get('amount', '0'))
        payment_date = date.fromisoformat(request.form.get('payment_date', str(get_local_today())))

        if amount <= 0:
            flash('Payment amount must be greater than 0', 'error')
            return redirect(url_for('boutique.credits'))

        # Update sale
        sale.amount_paid += amount
        sale.balance = sale.total_amount - sale.amount_paid
        if sale.balance <= 0:
            sale.balance = Decimal('0')
            sale.is_credit_cleared = True

        # Create payment record
        payment = BoutiqueCreditPayment(
            sale_id=sale.id,
            payment_date=payment_date,
            amount=amount,
            remaining_balance=sale.balance
        )
        db.session.add(payment)
        db.session.commit()

        log_action(session['username'], 'boutique', 'create', 'credit_payment', payment.id,
                   {'sale_reference': sale.reference_number, 'amount': float(amount),
                    'remaining_balance': float(sale.balance)})
        flash(f'Payment of UGX {amount:,.0f} recorded for {sale.reference_number}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error recording payment: {str(e)}', 'error')

    return redirect(url_for('boutique.credits'))
