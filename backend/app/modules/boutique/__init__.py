from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response
from app.models.boutique import (
    BoutiqueCategory, BoutiqueStock, BoutiqueSale,
    BoutiqueSaleItem, BoutiqueCreditPayment
)
from app.models.customer import Customer
from app.models.user import User
from app.modules.auth import login_required, log_action
from app.extensions import db
from app.utils.timezone import get_local_today
from app.utils.utils import generate_reference_number
from app.utils.image_fetch import fetch_product_image_async, fetch_product_image
from app.utils.pdf_generator import generate_receipt_pdf
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

boutique_bp = Blueprint('boutique', __name__)

# Branch names
BRANCHES = {
    'K': 'Kapchorwa Branch',
    'M': 'Mbale Branch'
}

AUTO_IMAGE_FETCH_SESSION_KEY = 'boutique_auto_image_fetch_date'


def get_current_branch():
    """Get the current branch from session"""
    return session.get('boutique_branch')


def get_user_branch():
    """Get branch assigned to the current user"""
    user_id = session.get('user_id')
    if user_id:
        user = User.query.get(user_id)
        if user:
            return user.boutique_branch
    return None


def safe_decimal(value, default='0'):
    """Safely convert a value to Decimal, handling empty strings and invalid values"""
    if value is None or value == '':
        return Decimal(default)
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return Decimal(default)


def auto_fetch_missing_images():
    """Auto-fetch images for items missing an image URL."""
    items = BoutiqueStock.query.filter(
        BoutiqueStock.is_active == True,
        db.or_(BoutiqueStock.image_url == None, BoutiqueStock.image_url == '')
    ).all()

    for item in items:
        category_name = item.category.name if item.category else None
        fetch_product_image_async(item.id, item.item_name, category_name)

    return len(items)


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

    # Managers can enter data for any date
    if user_section == 'manager':
        return True

    # Employees can only enter data for today or yesterday
    return yesterday <= entry_date <= today


@boutique_bp.route('/')
@login_required('boutique')
def index():
    """Boutique branch selection or overview page"""
    user_section = session.get('section', '')
    current_branch = get_current_branch()
    user_branch = get_user_branch()

    # If user is assigned to a specific branch, set it automatically
    if user_branch and user_section != 'manager':
        session['boutique_branch'] = user_branch
        current_branch = user_branch

    # If no branch selected and not manager, show branch selection
    if not current_branch and user_section != 'manager':
        return render_template('boutique/select_branch.html', branches=BRANCHES)

    # For managers without branch selected, show branch selection with option to view all
    if not current_branch and user_section == 'manager':
        return render_template('boutique/select_branch.html', branches=BRANCHES, is_manager=True)

    today = get_local_today()

    # Auto-fetch missing images once per day per session
    today_str = str(today)
    if session.get(AUTO_IMAGE_FETCH_SESSION_KEY) != today_str:
        try:
            auto_fetch_missing_images()
        except Exception:
            pass
        session[AUTO_IMAGE_FETCH_SESSION_KEY] = today_str

    try:
        # Build queries with branch filter
        stock_query = BoutiqueStock.query.filter_by(is_active=True)
        sales_query = BoutiqueSale.query.filter_by(is_deleted=False)
        credits_query = BoutiqueSale.query.filter(
            BoutiqueSale.is_deleted == False,
            BoutiqueSale.payment_type == 'part',
            BoutiqueSale.is_credit_cleared == False
        )

        # Filter by branch unless viewing all
        if current_branch != 'ALL':
            stock_query = stock_query.filter(
                db.or_(BoutiqueStock.branch == current_branch, BoutiqueStock.branch == None)
            )
            sales_query = sales_query.filter(BoutiqueSale.branch == current_branch)
            credits_query = credits_query.filter(BoutiqueSale.branch == current_branch)

        # Quick stats
        stock_count = stock_query.count()
        low_stock = stock_query.filter(
            BoutiqueStock.quantity <= BoutiqueStock.low_stock_threshold
        ).count()
        pending_credits = credits_query.count()
        today_sales = sales_query.filter(BoutiqueSale.sale_date == today).count()
    except Exception:
        db.session.rollback()
        stock_count = low_stock = pending_credits = today_sales = 0

    branch_name = 'All Branches' if current_branch == 'ALL' else BRANCHES.get(current_branch, current_branch)

    return render_template('boutique/index.html',
        stock_count=stock_count,
        low_stock=low_stock,
        pending_credits=pending_credits,
        today_sales=today_sales,
        current_branch=current_branch,
        branch_name=branch_name,
        branches=BRANCHES,
        is_manager=(user_section == 'manager')
    )


@boutique_bp.route('/select-branch/<branch>')
@login_required('boutique')
def select_branch(branch):
    """Select a branch to work with"""
    user_section = session.get('section', '')
    user_branch = get_user_branch()

    # If user is assigned to a specific branch and not manager, they can't change
    if user_branch and user_section != 'manager' and branch != user_branch:
        flash(f'You are assigned to {BRANCHES.get(user_branch, user_branch)} only', 'error')
        return redirect(url_for('boutique.index'))

    # Allow managers to view all or specific branch
    if branch in BRANCHES or (branch == 'ALL' and user_section == 'manager'):
        session['boutique_branch'] = branch
        branch_name = 'All Branches' if branch == 'ALL' else BRANCHES.get(branch, branch)
        flash(f'Switched to {branch_name}', 'success')
    else:
        flash('Invalid branch', 'error')

    return redirect(url_for('boutique.index'))


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
    # Auto-fetch missing images once per day per session
    today_str = str(get_local_today())
    if session.get(AUTO_IMAGE_FETCH_SESSION_KEY) != today_str:
        auto_fetch_missing_images()
        session[AUTO_IMAGE_FETCH_SESSION_KEY] = today_str

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
        quantity = request.form.get('quantity', type=int)
        unit = request.form.get('unit', 'pieces')
        cost_price = safe_decimal(request.form.get('cost_price', '0'))
        min_selling_price = safe_decimal(request.form.get('min_selling_price', '0'))
        max_selling_price = safe_decimal(request.form.get('max_selling_price', '0'))
        low_stock_threshold = request.form.get('low_stock_threshold', type=int)

        if not item_name or quantity is None or quantity < 0:
            flash('Item name and valid quantity are required', 'error')
            return redirect(url_for('boutique.stock'))

        # Handle category - either existing or new
        category_id = request.form.get('category_id')
        if category_id == 'new':
            # Create new category
            new_category_name = request.form.get('new_category', '').strip()
            if new_category_name:
                existing_cat = BoutiqueCategory.query.filter_by(name=new_category_name).first()
                if existing_cat:
                    category_id = existing_cat.id
                else:
                    new_category = BoutiqueCategory(name=new_category_name)
                    db.session.add(new_category)
                    db.session.flush()
                    category_id = new_category.id
                    log_action(session['username'], 'boutique', 'create', 'category', new_category.id,
                               {'name': new_category_name, 'created_with_stock': item_name})
            else:
                category_id = None
        else:
            category_id = int(category_id) if category_id else None

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

        # Auto-fetch product image in the background
        category_name = None
        if category_id:
            cat = BoutiqueCategory.query.get(category_id)
            if cat:
                category_name = cat.name
        fetch_product_image_async(stock_item.id, item_name, category_name)

        log_action(session['username'], 'boutique', 'create', 'stock', stock_item.id,
                   {'item_name': item_name, 'quantity': quantity, 'cost_price': float(cost_price)})
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

        # Handle category - either existing or new
        category_id = request.form.get('category_id')
        if category_id == 'new':
            new_category_name = request.form.get('new_category', '').strip()
            if new_category_name:
                existing_cat = BoutiqueCategory.query.filter_by(name=new_category_name).first()
                if existing_cat:
                    item.category_id = existing_cat.id
                else:
                    new_category = BoutiqueCategory(name=new_category_name)
                    db.session.add(new_category)
                    db.session.flush()
                    item.category_id = new_category.id
                    log_action(session['username'], 'boutique', 'create', 'category', new_category.id,
                               {'name': new_category_name, 'created_with_stock_edit': item.item_name})
        elif category_id:
            item.category_id = int(category_id)

        item.unit = request.form.get('unit', item.unit)
        item.cost_price = safe_decimal(request.form.get('cost_price'), str(item.cost_price))
        item.min_selling_price = safe_decimal(request.form.get('min_selling_price'), str(item.min_selling_price))
        item.max_selling_price = safe_decimal(request.form.get('max_selling_price'), str(item.max_selling_price))
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


@boutique_bp.route('/stock/<int:id>/reactivate', methods=['POST'])
@login_required('boutique')
def reactivate_stock(id):
    """Reactivate a deactivated stock item"""
    item = BoutiqueStock.query.get_or_404(id)
    item.is_active = True
    db.session.commit()

    log_action(session['username'], 'boutique', 'reactivate', 'stock', item.id,
               {'item_name': item.item_name})
    flash(f'Stock item "{item.item_name}" reactivated', 'success')
    return redirect(url_for('boutique.stock'))


@boutique_bp.route('/stock/<int:id>/refresh-image', methods=['POST'])
@login_required('boutique')
def refresh_image(id):
    """Re-fetch the product image for a stock item"""
    item = BoutiqueStock.query.get_or_404(id)
    category_name = item.category.name if item.category else None
    image_url = fetch_product_image(item.item_name, category_name)
    if image_url:
        item.image_url = image_url
        db.session.commit()
        flash(f'Image updated for "{item.item_name}"', 'success')
    else:
        flash(f'No image found for "{item.item_name}"', 'warning')
    return redirect(url_for('boutique.stock'))


@boutique_bp.route('/stock/fetch-all-images', methods=['POST'])
@login_required('boutique')
def fetch_all_images():
    """Fetch images for all stock items that don't have one yet"""
    items = BoutiqueStock.query.filter(
        BoutiqueStock.is_active == True,
        db.or_(BoutiqueStock.image_url == None, BoutiqueStock.image_url == '')
    ).all()

    count = 0
    for item in items:
        category_name = item.category.name if item.category else None
        fetch_product_image_async(item.id, item.item_name, category_name)
        count += 1

    flash(f'Fetching images for {count} items in the background...', 'success')
    return redirect(url_for('boutique.stock'))


@boutique_bp.route('/stock/<int:id>/permanent-delete', methods=['POST'])
@login_required('boutique')
def permanent_delete_stock(id):
    """Permanently delete a stock item - manager only"""
    user_section = session.get('section', '')
    if user_section != 'manager':
        flash('Only managers can permanently delete stock items', 'error')
        return redirect(url_for('boutique.stock'))

    item = BoutiqueStock.query.get_or_404(id)
    item_name = item.item_name

    db.session.delete(item)
    db.session.commit()

    log_action(session['username'], 'boutique', 'permanent_delete', 'stock', id,
               {'item_name': item_name})
    flash(f'Stock item "{item_name}" permanently deleted', 'success')
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
        amount_paid = safe_decimal(request.form.get('amount_paid', '0'))

        # Check date permission for non-managers
        user_section = session.get('section', '')
        if not check_date_permission(sale_date, user_section):
            flash('You can only enter sales for today or yesterday. Contact a manager for older entries.', 'error')
            return redirect(url_for('boutique.new_sale'))

        # Get items from form
        item_ids = request.form.getlist('item_id[]')
        quantities = request.form.getlist('quantity[]')
        prices = request.form.getlist('price[]')

        if not item_ids or not quantities or not prices:
            flash('At least one item is required', 'error')
            return redirect(url_for('boutique.new_sale'))

        # Calculate total - filter out empty items
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

            stock_item = BoutiqueStock.query.get(int(item_id))
            if stock_item:
                items_data.append({
                    'stock_id': stock_item.id,
                    'item_name': stock_item.item_name,
                    'quantity': qty,
                    'unit_price': price,
                    'subtotal': subtotal
                })

        if not items_data:
            flash('At least one valid item with quantity and price is required', 'error')
            return redirect(url_for('boutique.new_sale'))

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


@boutique_bp.route('/sales/<int:id>/receipt/preview')
@login_required('boutique')
def receipt_preview(id):
    """Preview receipt with editable items before download"""
    sale = BoutiqueSale.query.get_or_404(id)
    items = sale.items.all()
    branch_label = BRANCHES.get(sale.branch) if sale.branch else None
    business_name = f"BOUTIQUE - {branch_label}" if branch_label else "BOUTIQUE"
    return render_template('boutique/receipt_preview.html',
        sale=sale,
        items=items,
        business_name=business_name,
        is_full_payment=(sale.payment_type == 'full')
    )


@boutique_bp.route('/sales/<int:id>/receipt', methods=['GET', 'POST'])
@login_required('boutique')
def download_receipt(id):
    """Download sale receipt as PDF"""
    sale = BoutiqueSale.query.get_or_404(id)
    branch_label = BRANCHES.get(sale.branch) if sale.branch else None
    business_name = f"BOUTIQUE - {branch_label}" if branch_label else "BOUTIQUE"
    items_override = None
    totals_override = None
    meta_override = None
    served_by_override = session.get('username')
    business_name_override = business_name

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
            return redirect(url_for('boutique.receipt_preview', id=id))

        total_amount = sum(item['subtotal'] for item in items_override)
        amount_paid = safe_decimal(request.form.get('amount_paid', str(sale.amount_paid)), str(sale.amount_paid))
        amount_paid_value = float(amount_paid)
        if amount_paid_value > total_amount:
            flash('Amount paid cannot exceed the total amount.', 'error')
            return redirect(url_for('boutique.receipt_preview', id=id))

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
        amount = safe_decimal(request.form.get('amount', '0'))
        payment_date = date.fromisoformat(request.form.get('payment_date', str(get_local_today())))

        # Check date permission for non-managers
        user_section = session.get('section', '')
        if not check_date_permission(payment_date, user_section):
            flash('You can only enter payments for today or yesterday. Contact a manager for older entries.', 'error')
            return redirect(url_for('boutique.credits'))

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
