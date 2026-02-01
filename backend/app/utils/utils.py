"""Utility functions for the application."""
from datetime import date


def format_currency(amount):
    """Format amount as currency string."""
    return f"UGX {amount:,.0f}"


def generate_reference_number(prefix, model_class):
    """Generate a unique reference number for a model.

    Args:
        prefix: The prefix for the reference number (e.g., 'DNV-B-')
        model_class: The SQLAlchemy model class to query

    Returns:
        A unique reference number string
    """
    last_record = model_class.query.filter(
        model_class.reference_number.like(f'{prefix}%')
    ).order_by(model_class.id.desc()).first()

    if last_record and last_record.reference_number:
        try:
            last_number = int(last_record.reference_number.split('-')[-1])
            new_number = last_number + 1
        except (ValueError, IndexError):
            new_number = 1
    else:
        new_number = 1

    return f"{prefix}{new_number:05d}"


def get_date_range(start_date_str=None, end_date_str=None):
    """Parse date range from request parameters.

    Args:
        start_date_str: Start date string (YYYY-MM-DD) or None
        end_date_str: End date string (YYYY-MM-DD) or None

    Returns:
        Tuple of (start_date, end_date) as date objects or None
    """
    start_date = None
    end_date = None

    if start_date_str:
        try:
            start_date = date.fromisoformat(start_date_str)
        except ValueError:
            pass

    if end_date_str:
        try:
            end_date = date.fromisoformat(end_date_str)
        except ValueError:
            pass

    return start_date, end_date
