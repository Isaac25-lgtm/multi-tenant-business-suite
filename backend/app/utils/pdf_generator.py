from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from datetime import datetime, date
import io
import os

LOGO_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'static', 'images', 'devs.png')
)


def format_currency(amount):
    """Format currency as UGX with thousands separator"""
    return f"UGX {amount:,.0f}"


def _format_receipt_date(value, fallback):
    if isinstance(value, date):
        return value.strftime('%B %d, %Y')
    if isinstance(value, str) and value.strip():
        try:
            parsed = date.fromisoformat(value.strip())
            return parsed.strftime('%B %d, %Y')
        except ValueError:
            return value.strip()
    if isinstance(fallback, date):
        return fallback.strftime('%B %d, %Y')
    return 'N/A'


def _draw_logo_image(c, x, y, size):
    if not os.path.exists(LOGO_PATH):
        return False
    try:
        logo = ImageReader(LOGO_PATH)
        iw, ih = logo.getSize()
        if not iw or not ih:
            return False
        scale = size / max(iw, ih)
        draw_w = iw * scale
        draw_h = ih * scale
        c.drawImage(logo, x, y + (size - draw_h) / 2, width=draw_w, height=draw_h, mask='auto')
        return True
    except Exception:
        return False


def draw_logo_header(c, width, y):
    """Draw the Devs logo header on PDF"""
    logo_size = 72
    start_x = (width - logo_size) / 2
    logo_y = y - logo_size

    _draw_logo_image(c, start_x, logo_y, logo_size)
    return y - logo_size - 16


def generate_receipt_pdf(sale, business_name, served_by=None, items_override=None, totals_override=None, meta_override=None):
    """Generate PDF receipt for a sale"""
    buffer = io.BytesIO()

    # Create PDF
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    meta_override = meta_override or {}

    # Header with logo
    y = height - 20
    y = draw_logo_header(c, width, y)

    y -= 10
    c.setFont("Helvetica", 12)
    c.drawCentredString(width/2, y, f"[{business_name}]")
    
    y -= 30
    c.line(50, y, width-50, y)
    
    # Business details
    y -= 20
    c.setFont("Helvetica", 10)
    phone_text = f"Phone: {meta_override.get('phone')}" if meta_override.get('phone') else "Phone: -"
    address_text = f"Address: {meta_override.get('address')}" if meta_override.get('address') else "Address: -"
    c.drawCentredString(width/2, y, phone_text)
    y -= 15
    c.drawCentredString(width/2, y, address_text)
    
    y -= 20
    c.line(50, y, width-50, y)
    
    # Receipt title
    y -= 24
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(HexColor('#c24b28'))
    c.drawCentredString(width/2, y, "RECEIPT")
    c.setFillColor(HexColor('#0f172a'))

    # Receipt details
    y -= 24
    c.setFont("Helvetica", 10)
    customer_name = meta_override.get('customer_name') or (sale.customer.name if sale.customer else None)
    customer_phone = sale.customer.phone if sale.customer else None
    receipt_date = _format_receipt_date(meta_override.get('sale_date'), sale.sale_date)

    detail_rows = [
        ("Reference", sale.reference_number),
        ("Date", receipt_date),
        ("Time", sale.created_at.strftime('%I:%M %p') if getattr(sale, 'created_at', None) else 'N/A'),
        ("Served by", served_by or 'N/A')
    ]
    if customer_name:
        detail_rows.append(("Customer", customer_name))

    left_x = 50
    right_x = width / 2 + 10
    row_height = 16
    for idx, (label, value) in enumerate(detail_rows):
        col_x = left_x if idx % 2 == 0 else right_x
        row_y = y - (idx // 2) * row_height
        c.setFillColor(HexColor('#64748b'))
        c.setFont("Helvetica", 9)
        c.drawString(col_x, row_y, f"{label}:")
        c.setFillColor(HexColor('#0f172a'))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(col_x + 60, row_y, str(value))

    rows_count = (len(detail_rows) + 1) // 2
    y = y - rows_count * row_height - 10
    c.setStrokeColor(HexColor('#e2e8f0'))
    c.line(50, y, width-50, y)

    # Items header
    y -= 20
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(HexColor('#0f172a'))
    c.drawString(50, y, "ITEMS")

    def draw_items_header(header_y):
        table_left = 50
        table_right = width - 50
        c.setFillColor(HexColor('#c24b28'))
        c.rect(table_left, header_y - 18, table_right - table_left, 20, fill=1, stroke=0)
        c.setFillColor(HexColor('#ffffff'))
        c.setFont("Helvetica-Bold", 9)
        c.drawString(table_left + 8, header_y - 14, "ITEM")
        c.drawRightString(table_left + 330, header_y - 14, "QTY")
        c.drawRightString(table_left + 420, header_y - 14, "PRICE")
        c.drawRightString(table_right - 10, header_y - 14, "AMOUNT")
        c.setFillColor(HexColor('#0f172a'))
        return header_y - 24

    y = draw_items_header(y - 6)

    # Items
    items = items_override
    if items is None:
        items = sale.items.all() if hasattr(sale.items, 'all') else sale.items

    row_height = 18
    table_left = 50
    table_right = width - 50
    for row_index, item in enumerate(items):
        if y < 120:
            c.showPage()
            y = height - 40
            y = draw_items_header(y)

        if isinstance(item, dict):
            item_name = item.get('item_name', '')
            quantity = item.get('quantity', 0)
            unit_price = item.get('unit_price', 0)
            subtotal = item.get('subtotal', 0)
        else:
            item_name = item.item_name
            quantity = item.quantity
            unit_price = item.unit_price
            subtotal = item.subtotal

        if row_index % 2 == 0:
            c.setFillColor(HexColor('#f8fafc'))
            c.rect(table_left, y - 14, table_right - table_left, row_height, fill=1, stroke=0)
        c.setFillColor(HexColor('#0f172a'))
        c.setFont("Helvetica", 9)
        c.drawString(table_left + 8, y - 12, str(item_name)[:38])
        c.drawRightString(table_left + 330, y - 12, str(quantity))
        c.drawRightString(table_left + 420, y - 12, format_currency(float(unit_price)))
        c.drawRightString(table_right - 10, y - 12, format_currency(float(subtotal)))
        y -= row_height

    y -= 6
    c.setStrokeColor(HexColor('#e2e8f0'))
    c.line(50, y, width-50, y)

    # Totals box
    if totals_override:
        total_amount = totals_override.get('total_amount', float(sale.total_amount))
        amount_paid = totals_override.get('amount_paid', float(sale.amount_paid))
        balance = totals_override.get('balance', float(sale.balance))
        payment_type = totals_override.get('payment_type', sale.payment_type)
    else:
        total_amount = float(sale.total_amount)
        amount_paid = float(sale.amount_paid)
        balance = float(sale.balance)
        payment_type = sale.payment_type

    totals = [
        ("Total", format_currency(float(total_amount))),
        ("Paid", format_currency(float(amount_paid))),
        ("Balance", format_currency(float(balance)))
    ]
    box_width = 210
    box_height = 18 * len(totals) + 14
    box_x = width - 50 - box_width
    box_y = y - box_height - 6
    c.setFillColor(HexColor('#fff7f5'))
    c.roundRect(box_x, box_y, box_width, box_height, 8, fill=1, stroke=0)
    c.setFillColor(HexColor('#0f172a'))
    c.setFont("Helvetica-Bold", 9)
    for idx, (label, value) in enumerate(totals):
        line_y = box_y + box_height - 18 - idx * 18
        c.drawString(box_x + 10, line_y, label.upper())
        c.drawRightString(box_x + box_width - 10, line_y, value)

    y = box_y - 20

    # Payment details
    c.setFillColor(HexColor('#0f172a'))
    c.setFont("Helvetica", 9)
    payment_label = "FULL PAYMENT" if payment_type == 'full' else "PART PAYMENT"
    c.drawString(50, y, f"Payment Method: {payment_label}")
    if payment_type != 'full':
        y -= 14
        c.setFillColor(HexColor('#c24b28'))
        c.setFont("Helvetica-Bold", 9)
        c.drawString(50, y, f"Balance Due: {format_currency(float(balance))}")
        c.setFillColor(HexColor('#0f172a'))
    y -= 18
    c.setStrokeColor(HexColor('#e2e8f0'))
    c.line(50, y, width-50, y)
    
    # Footer
    y -= 30
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(width/2, y, "Thank you for shopping with us!")
    
    y -= 20
    c.setFont("Helvetica", 8)
    c.drawCentredString(width/2, y, "[Footer text - to be configured]")
    
    # Finalize PDF
    c.save()
    
    buffer.seek(0)
    return buffer


def generate_group_agreement_pdf(group_loan):
    """Generate PDF agreement for a group loan"""
    buffer = io.BytesIO()

    # Create PDF
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Header with logo
    y = height - 20
    y = draw_logo_header(c, width, y)

    y -= 10
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width/2, y, "GROUP LOAN AGREEMENT")

    y -= 30
    c.line(50, y, width-50, y)

    # Group Information Section
    y -= 30
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "GROUP INFORMATION")

    y -= 25
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Group Name: {group_loan.group_name}")
    y -= 18
    c.drawString(50, y, f"Number of Members: {group_loan.member_count}")
    y -= 18
    c.drawString(50, y, f"Agreement Reference: GL-{group_loan.id:04d}")
    y -= 18
    if group_loan.issue_date:
        c.drawString(50, y, f"Issue Date: {group_loan.issue_date.strftime('%B %d, %Y')}")

    y -= 30
    c.line(50, y, width-50, y)

    # Loan Details Section
    y -= 25
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "LOAN DETAILS")

    y -= 25
    c.setFont("Helvetica", 10)

    # Create a table-like structure for loan details
    details = [
        ("Principal Amount:", format_currency(float(group_loan.principal) if group_loan.principal else 0)),
        ("Interest Rate:", f"{float(group_loan.interest_rate) if group_loan.interest_rate else 0}%"),
        ("Interest Amount:", format_currency(float(group_loan.interest_amount) if group_loan.interest_amount else 0)),
        ("Total Loan Amount:", format_currency(float(group_loan.total_amount))),
        ("Payment Period Type:", (group_loan.period_type or 'monthly').replace('-', ' ').title()),
        ("Number of Periods:", str(group_loan.total_periods)),
        ("Amount Per Period:", format_currency(float(group_loan.amount_per_period))),
    ]

    if group_loan.due_date:
        details.append(("Expected Completion Date:", group_loan.due_date.strftime('%B %d, %Y')))

    for label, value in details:
        c.drawString(50, y, label)
        c.drawString(250, y, value)
        y -= 18

    y -= 20
    c.line(50, y, width-50, y)

    # Payment Schedule Section
    y -= 25
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "PAYMENT SCHEDULE")

    y -= 25
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Period")
    c.drawString(150, y, "Due Date")
    c.drawString(300, y, "Amount")
    c.drawString(420, y, "Status")

    y -= 5
    c.line(50, y, width-50, y)

    y -= 18
    c.setFont("Helvetica", 10)

    # Calculate payment schedule
    period_days = {
        'weekly': 7,
        'bi-weekly': 14,
        'monthly': 30,
        'bi-monthly': 60
    }
    days_per_period = period_days.get(group_loan.period_type or 'monthly', 30)

    from datetime import date, timedelta
    start_date = group_loan.issue_date or date.today()

    for i in range(1, min(group_loan.total_periods + 1, 13)):  # Show max 12 periods
        if y < 100:  # Check if we need a new page
            c.showPage()
            y = height - 40
            c.setFont("Helvetica", 10)

        period_date = start_date + timedelta(days=days_per_period * i)
        status = "Paid" if i <= group_loan.periods_paid else "Pending"

        c.drawString(50, y, f"Period {i}")
        c.drawString(150, y, period_date.strftime('%b %d, %Y'))
        c.drawString(300, y, format_currency(float(group_loan.amount_per_period)))
        c.drawString(420, y, status)
        y -= 18

    if group_loan.total_periods > 12:
        c.drawString(50, y, f"... and {group_loan.total_periods - 12} more periods")
        y -= 18

    y -= 20
    c.line(50, y, width-50, y)

    # Summary Section
    y -= 25
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "PAYMENT SUMMARY")

    y -= 25
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Periods Paid: {group_loan.periods_paid} of {group_loan.total_periods}")
    y -= 18
    c.drawString(50, y, f"Amount Paid: {format_currency(float(group_loan.amount_paid))}")
    y -= 18
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, f"Outstanding Balance: {format_currency(float(group_loan.balance))}")

    y -= 40
    c.line(50, y, width-50, y)

    # Terms and Conditions
    y -= 25
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "TERMS AND CONDITIONS")

    y -= 20
    c.setFont("Helvetica", 9)
    terms = [
        "1. The group agrees to make payments on the scheduled dates.",
        "2. Late payments may result in additional charges.",
        "3. All members are jointly responsible for the loan repayment.",
        "4. Early repayment is allowed without penalty.",
        "5. This agreement is binding upon signing by all parties."
    ]

    for term in terms:
        if y < 80:
            c.showPage()
            y = height - 40
        c.drawString(50, y, term)
        y -= 15

    # Signature Section
    y -= 40
    c.line(50, y, width-50, y)

    y -= 30
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "GROUP REPRESENTATIVE:")
    c.drawString(320, y, "FINANCE OFFICER:")

    y -= 40
    c.line(50, y, 200, y)
    c.line(320, y, 500, y)

    y -= 15
    c.setFont("Helvetica", 9)
    c.drawString(50, y, "Signature & Date")
    c.drawString(320, y, "Signature & Date")

    y -= 30
    c.line(50, y, 200, y)
    c.line(320, y, 500, y)

    y -= 15
    c.drawString(50, y, "Name")
    c.drawString(320, y, "Name")

    # Footer
    y = 30
    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(width/2, y, f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")

    # Finalize PDF
    c.save()

    buffer.seek(0)
    return buffer


def generate_hire_receipt_pdf(hire, business_name, served_by=None):
    """Generate PDF receipt for a hire/rental transaction"""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Header with logo
    y = height - 20
    y = draw_logo_header(c, width, y)

    y -= 10
    c.setFont("Helvetica", 12)
    c.drawCentredString(width / 2, y, f"[{business_name}]")

    y -= 30
    c.line(50, y, width - 50, y)

    # Title
    y -= 24
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(HexColor('#7c3aed'))
    c.drawCentredString(width / 2, y, "HIRE AGREEMENT / RECEIPT")
    c.setFillColor(HexColor('#0f172a'))

    # Reference & dates
    y -= 28
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Reference: {hire.reference_number}")
    c.drawRightString(width - 50, y, f"Date: {hire.hire_date.strftime('%B %d, %Y')}")

    # Customer info
    y -= 20
    customer_name = hire.customer.name if hire.customer else (hire.customer_name or 'N/A')
    customer_phone = hire.customer.phone if hire.customer else (hire.customer_phone or 'N/A')
    c.drawString(50, y, f"Customer: {customer_name}")
    c.drawRightString(width - 50, y, f"Phone: {customer_phone}")

    if hire.purpose:
        y -= 16
        c.drawString(50, y, f"Purpose: {hire.purpose}")

    y -= 20
    c.line(50, y, width - 50, y)

    # Item details table header
    y -= 24
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(HexColor('#f8fafc'))
    c.rect(50, y - 4, width - 100, 20, fill=True, stroke=False)
    c.setFillColor(HexColor('#0f172a'))
    c.drawString(55, y, "Item")
    c.drawString(250, y, "Qty")
    c.drawString(310, y, "Rate/Day")
    c.drawString(400, y, "Days")
    c.drawRightString(width - 55, y, "Amount")

    # Item row
    y -= 20
    c.setFont("Helvetica", 10)
    item_name = hire.stock_item.item_name if hire.stock_item else 'N/A'
    hire_days = max(1, ((hire.actual_return_date or hire.expected_return_date) - hire.hire_date).days)
    line_total = float(hire.daily_rate) * hire.quantity * hire_days

    c.drawString(55, y, item_name[:30])
    c.drawString(250, y, str(hire.quantity))
    c.drawString(310, y, format_currency(float(hire.daily_rate)))
    c.drawString(400, y, str(hire_days))
    c.drawRightString(width - 55, y, format_currency(line_total))

    y -= 16
    c.line(50, y, width - 50, y)

    # Dates section
    y -= 22
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Hire Date: {hire.hire_date.strftime('%B %d, %Y')}")
    y -= 16
    c.drawString(50, y, f"Expected Return: {hire.expected_return_date.strftime('%B %d, %Y')}")
    if hire.actual_return_date:
        y -= 16
        c.drawString(50, y, f"Actual Return: {hire.actual_return_date.strftime('%B %d, %Y')}")
    if hire.return_condition:
        y -= 16
        c.drawString(50, y, f"Return Condition: {hire.return_condition}")

    y -= 20
    c.line(50, y, width - 50, y)

    # Financial summary
    y -= 22
    c.setFont("Helvetica", 10)
    c.drawString(50, y, "Total Amount:")
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(width - 50, y, format_currency(float(hire.total_amount)))

    y -= 18
    c.setFont("Helvetica", 10)
    c.drawString(50, y, "Deposit Paid:")
    c.setFillColor(HexColor('#16a34a'))
    c.drawRightString(width - 50, y, format_currency(float(hire.deposit_amount)))
    c.setFillColor(HexColor('#0f172a'))

    y -= 18
    c.drawString(50, y, "Total Paid:")
    c.setFillColor(HexColor('#16a34a'))
    c.drawRightString(width - 50, y, format_currency(float(hire.amount_paid)))
    c.setFillColor(HexColor('#0f172a'))

    if hire.balance > 0:
        y -= 18
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, "Balance Due:")
        c.setFillColor(HexColor('#ea580c'))
        c.drawRightString(width - 50, y, format_currency(float(hire.balance)))
        c.setFillColor(HexColor('#0f172a'))

    y -= 18
    c.line(50, y, width - 50, y)

    # Status
    y -= 22
    c.setFont("Helvetica-Bold", 10)
    status_label = hire.status.upper()
    c.drawString(50, y, f"Status: {status_label}")

    # Terms
    y -= 30
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Terms & Conditions:")
    y -= 16
    c.setFont("Helvetica", 8)
    terms = [
        "1. Items must be returned in the same condition as received.",
        "2. Late returns may incur additional charges at the daily rate.",
        "3. The hirer is responsible for any damage, loss, or theft of hired items.",
        "4. Deposit is refundable upon satisfactory return of items.",
        "5. Full payment is due upon return of items."
    ]
    for term in terms:
        c.drawString(55, y, term)
        y -= 14

    # Served by
    if served_by:
        y -= 20
        c.setFont("Helvetica", 9)
        c.drawString(50, y, f"Served by: {served_by}")

    # Footer
    y -= 30
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(width / 2, y, "Thank you for choosing our hire service!")

    y -= 16
    c.setFont("Helvetica", 8)
    c.setFillColor(HexColor('#94a3b8'))
    c.drawCentredString(width / 2, y, f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")

    c.save()
    buffer.seek(0)
    return buffer
