"""Operating expenses ledger.

Every unit handles its own expenses: staff record expenses for their own unit
(boutique, hardware or finance); managers see and record for every unit and
are the only ones who can delete.
"""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func

from app.extensions import db
from app.models.expense import Expense
from app.modules.auth import get_session_user, log_action, manager_required
from app.services.periods import resolve_period
from app.utils.timezone import get_local_now, get_local_today

expenses_bp = Blueprint('expenses', __name__)

MAX_EXPENSE = Decimal('1000000000')
STAFF_UNITS = ('boutique', 'hardware', 'finance')


def _amount(value):
    try:
        return Decimal(str(value or '').strip()).quantize(Decimal('1'))
    except (InvalidOperation, ValueError):
        return Decimal('0')


def staff_required(f):
    """Any active signed-in staff member."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_session_user()
        if not user or not user.is_active:
            session.clear()
            flash('Please login to record expenses', 'error')
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)
    return decorated


def _is_manager():
    return session.get('section') == 'manager'


def _allowed_units():
    """Units the signed-in person may record and view expenses for."""
    if _is_manager():
        return list(Expense.SELECTABLE_UNITS)
    section = session.get('section')
    return [section] if section in STAFF_UNITS else []


@expenses_bp.route('/')
@staff_required
def index():
    units = _allowed_units()
    if not units:
        flash('Expenses are recorded from the boutique, hardware or finance section.', 'error')
        return redirect(url_for('auth.login'))

    period = resolve_period(request.args, get_local_today())
    filters = [
        Expense.is_deleted == False,  # noqa: E712
        Expense.expense_date >= period['start'],
        Expense.expense_date <= period['end'],
    ]
    if not _is_manager():
        filters.append(Expense.business_unit.in_(units))
    expenses = Expense.query.filter(*filters).order_by(Expense.expense_date.desc(), Expense.id.desc()).all()
    by_category = db.session.query(Expense.category, func.sum(Expense.amount)).filter(*filters).group_by(
        Expense.category).order_by(func.sum(Expense.amount).desc()).all()
    by_unit = db.session.query(Expense.business_unit, func.sum(Expense.amount)).filter(*filters).group_by(
        Expense.business_unit).order_by(func.sum(Expense.amount).desc()).all()
    total = sum((expense.amount for expense in expenses), Decimal('0'))
    return render_template(
        'expenses/index.html',
        period=period,
        expenses=expenses,
        total=total,
        by_category=[(Expense.CATEGORIES.get(cat, cat), amount) for cat, amount in by_category],
        by_unit=[(Expense.BUSINESS_UNITS.get(unit, unit), amount) for unit, amount in by_unit],
        categories=Expense.CATEGORIES,
        units={unit: Expense.BUSINESS_UNITS[unit] for unit in units},
        methods=Expense.PAYMENT_METHODS,
        is_manager=_is_manager(),
        today=get_local_today(),
    )


@expenses_bp.route('/add', methods=['POST'])
@staff_required
def add():
    form = request.form
    units = _allowed_units()
    amount = _amount(form.get('amount'))
    description = (form.get('description') or '').strip()
    category = form.get('category')
    unit = form.get('business_unit') or (units[0] if units else '')
    method = form.get('payment_method') or None
    today = get_local_today()
    try:
        expense_date = date.fromisoformat(form.get('expense_date') or str(today))
    except ValueError:
        expense_date = today

    if category not in Expense.CATEGORIES or unit not in units:
        flash('Choose a category and your business unit.', 'error')
    elif amount <= 0 or amount > MAX_EXPENSE:
        flash('Enter an amount greater than 0.', 'error')
    elif len(description) < 3:
        flash('Describe the expense.', 'error')
    elif expense_date > today:
        flash('Expenses cannot be dated in the future.', 'error')
    elif not _is_manager() and expense_date < today - timedelta(days=1):
        flash('You can only enter expenses for today or yesterday. Ask a manager for older entries.', 'error')
    else:
        expense = Expense(
            expense_date=expense_date, category=category, business_unit=unit, amount=amount,
            description=description[:255], payment_method=method if method in Expense.PAYMENT_METHODS else None,
            reference=(form.get('reference') or '').strip()[:100] or None,
            created_by=session.get('username'),
        )
        db.session.add(expense)
        db.session.commit()
        log_action(session['username'], 'expenses', 'create', 'expense', expense.id,
                   {'date': expense_date, 'category': category, 'unit': unit, 'amount': amount,
                    'description': description})
        flash(f'Expense of UGX {amount:,.0f} recorded.', 'success')
    return redirect(url_for('expenses.index'))


@expenses_bp.route('/<int:id>/delete', methods=['POST'])
@manager_required
def delete(id):
    expense = Expense.query.get_or_404(id)
    reason = (request.form.get('reason') or '').strip()
    if expense.is_deleted:
        flash('This expense was already deleted.', 'warning')
    elif len(reason) < 5:
        flash('Give a reason for deleting the expense (at least 5 characters).', 'error')
    else:
        expense.is_deleted = True
        expense.deleted_by = session.get('username')
        expense.deleted_at = get_local_now()
        expense.deletion_reason = reason[:255]
        db.session.commit()
        log_action(session['username'], 'expenses', 'delete', 'expense', expense.id,
                   {'amount': expense.amount, 'description': expense.description, 'reason': reason})
        flash('Expense deleted.', 'success')
    return redirect(url_for('expenses.index'))
