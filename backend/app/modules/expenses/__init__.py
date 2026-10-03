"""Operating expenses ledger (manager only)."""
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func

from app.extensions import db
from app.models.expense import Expense
from app.modules.auth import log_action, manager_required
from app.services.periods import resolve_period
from app.utils.timezone import get_local_now, get_local_today

expenses_bp = Blueprint('expenses', __name__)

MAX_EXPENSE = Decimal('1000000000')


def _amount(value):
    try:
        return Decimal(str(value or '').strip()).quantize(Decimal('1'))
    except (InvalidOperation, ValueError):
        return Decimal('0')


@expenses_bp.route('/')
@manager_required
def index():
    period = resolve_period(request.args, get_local_today())
    base = Expense.query.filter(
        Expense.is_deleted == False,  # noqa: E712
        Expense.expense_date >= period['start'],
        Expense.expense_date <= period['end'],
    )
    expenses = base.order_by(Expense.expense_date.desc(), Expense.id.desc()).all()
    by_category = db.session.query(Expense.category, func.sum(Expense.amount)).filter(
        Expense.is_deleted == False,  # noqa: E712
        Expense.expense_date >= period['start'],
        Expense.expense_date <= period['end'],
    ).group_by(Expense.category).order_by(func.sum(Expense.amount).desc()).all()
    total = sum((expense.amount for expense in expenses), Decimal('0'))
    return render_template(
        'expenses/index.html',
        period=period,
        expenses=expenses,
        total=total,
        by_category=[(Expense.CATEGORIES.get(cat, cat), amount) for cat, amount in by_category],
        categories=Expense.CATEGORIES,
        units=Expense.BUSINESS_UNITS,
        methods=Expense.PAYMENT_METHODS,
        today=get_local_today(),
    )


@expenses_bp.route('/add', methods=['POST'])
@manager_required
def add():
    form = request.form
    amount = _amount(form.get('amount'))
    description = (form.get('description') or '').strip()
    category = form.get('category')
    unit = form.get('business_unit') or 'shared'
    method = form.get('payment_method') or None
    try:
        expense_date = date.fromisoformat(form.get('expense_date') or str(get_local_today()))
    except ValueError:
        expense_date = get_local_today()

    if category not in Expense.CATEGORIES or unit not in Expense.BUSINESS_UNITS:
        flash('Choose a category and business unit.', 'error')
    elif amount <= 0 or amount > MAX_EXPENSE:
        flash('Enter an amount greater than 0.', 'error')
    elif len(description) < 3:
        flash('Describe the expense.', 'error')
    elif expense_date > get_local_today():
        flash('Expenses cannot be dated in the future.', 'error')
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
    return redirect(url_for('expenses.index', **request.args))


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
