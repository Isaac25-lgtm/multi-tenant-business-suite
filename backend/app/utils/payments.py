"""How a payment was made: method and reference, shared by every payment form."""

PAYMENT_METHODS = {
    'cash': 'Cash',
    'mobile_money': 'Mobile money',
    'bank': 'Bank',
}
DEFAULT_PAYMENT_METHOD = 'cash'


def read_payment_details(form):
    """Return (method, reference) from a submitted form, validated."""
    method = (form.get('payment_method') or DEFAULT_PAYMENT_METHOD).strip()
    if method not in PAYMENT_METHODS:
        method = DEFAULT_PAYMENT_METHOD
    reference = (form.get('payment_reference') or '').strip()[:100] or None
    return method, reference


def payment_method_label(method):
    return PAYMENT_METHODS.get(method or '', '')
