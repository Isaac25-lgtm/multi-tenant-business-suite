from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from dateutil.relativedelta import relativedelta
import io
import os
from xml.sax.saxutils import escape

from app.utils.branding import get_company_display_name, get_site_settings
from app.utils.timezone import get_local_now


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


def _resolve_logo_path(settings):
    logo_path = getattr(settings, 'logo_path', None)
    if not logo_path:
        return None
    resolved = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'static', logo_path)
    )
    return resolved if os.path.exists(resolved) else None


def _draw_logo_image(c, x, y, width, height, image_path):
    if not image_path or image_path.lower().endswith(('.svg', '.webp')):
        return False
    try:
        logo = ImageReader(image_path)
        iw, ih = logo.getSize()
        if not iw or not ih:
            return False
        scale = min(width / iw, height / ih)
        draw_w = iw * scale
        draw_h = ih * scale
        c.drawImage(logo, x, y + (height - draw_h) / 2, width=draw_w, height=draw_h, mask='auto')
        return True
    except Exception:
        return False


def _draw_vector_brand_mark(c, x, y, size):
    c.setFillColor(HexColor('#b85c38'))
    c.roundRect(x, y, size, size, 12, fill=1, stroke=0)
    c.setFillColor(HexColor('#fff7f5'))
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(x + (size / 2), y + 12, "D")
    c.setFillColor(HexColor('#e8d5a0'))
    c.circle(x + size - 10, y + size - 10, 4, fill=1, stroke=0)


def draw_logo_header(c, width, y):
    """Draw a branded PDF header that works with the default Denove logo."""
    settings = get_site_settings()
    company_name = get_company_display_name(settings)
    tagline = getattr(settings, 'tagline', None) or 'Fashion, Hardware & Finance'

    logo_height = 54
    logo_width = 140
    logo_x = 50
    logo_y = y - logo_height
    image_path = _resolve_logo_path(settings)

    if _draw_logo_image(c, logo_x, logo_y, logo_width, logo_height, image_path):
        text_x = logo_x + logo_width + 10
    else:
        _draw_vector_brand_mark(c, logo_x, logo_y + 2, 48)
        text_x = logo_x + 62

    c.setFillColor(HexColor('#0f172a'))
    c.setFont("Helvetica-Bold", 18)
    c.drawString(text_x, y - 16, company_name)
    c.setFillColor(HexColor('#64748b'))
    c.setFont("Helvetica", 9)
    c.drawString(text_x, y - 30, tagline[:90])
    c.setStrokeColor(HexColor('#e2e8f0'))
    c.line(50, y - logo_height - 10, width - 50, y - logo_height - 10)
    return y - logo_height - 22


def generate_receipt_pdf(sale, business_name, served_by=None, items_override=None, totals_override=None, meta_override=None):
    """Generate PDF receipt for a sale"""
    buffer = io.BytesIO()
    settings = get_site_settings()
    company_name = get_company_display_name(settings)

    # Create PDF
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    meta_override = meta_override or {}

    # Header with logo
    y = height - 26
    y = draw_logo_header(c, width, y)

    y -= 2
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(HexColor('#64748b'))
    c.drawCentredString(width/2, y, business_name)
    c.setFillColor(HexColor('#0f172a'))
    
    y -= 20
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
    c.drawCentredString(width/2, y, f"{company_name} | {settings.contact_phone or 'Please contact our team for support.'}")
    
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
    y = height - 26
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


def _draw_clearance_page_header(c, width, height, cert_ref, clearance_date_str, is_continuation=False):
    """Draw the compact identity header used on page 1 and repeated on continuation pages."""
    green = HexColor('#16a34a')
    slate = HexColor('#0f172a')
    gray = HexColor('#64748b')
    border = HexColor('#e2e8f0')

    if is_continuation:
        y = height - 30
        c.setFillColor(green)
        c.rect(50, y, width - 100, 2, fill=1, stroke=0)
        y -= 14
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(slate)
        c.drawString(50, y, "LOAN CLEARANCE CERTIFICATE  (continued)")
        c.setFont("Helvetica", 9)
        c.setFillColor(gray)
        c.drawRightString(width - 50, y, f"{cert_ref}  |  {clearance_date_str}")
        y -= 8
        c.setStrokeColor(border)
        c.line(50, y, width - 50, y)
        return y - 8
    return None


def _draw_payment_table_header_individual(c, width, y, green):
    """Draw the payment table column headers for individual loans."""
    c.setFillColor(green)
    c.rect(50, y - 16, width - 100, 18, fill=1, stroke=0)
    c.setFillColor(HexColor('#ffffff'))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(58, y - 12, "DATE")
    c.drawRightString(220, y - 12, "PRINCIPAL")
    c.drawRightString(330, y - 12, "INTEREST")
    c.drawRightString(440, y - 12, "AMOUNT")
    c.drawRightString(width - 58, y - 12, "BALANCE AFTER")
    return y - 22


def _draw_payment_table_header_group(c, width, y, green):
    """Draw the payment table column headers for group loans."""
    c.setFillColor(green)
    c.rect(50, y - 16, width - 100, 18, fill=1, stroke=0)
    c.setFillColor(HexColor('#ffffff'))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(58, y - 12, "DATE")
    c.drawRightString(300, y - 12, "PERIODS COVERED")
    c.drawRightString(440, y - 12, "AMOUNT")
    c.drawRightString(width - 58, y - 12, "BALANCE AFTER")
    return y - 22


def _draw_clearance_footer(c, width, company_name, contact_phone, headquarters, cert_ref, clearance_date_str, y):
    """Draw signature block, stamp, and footer on the final page."""
    green = HexColor('#16a34a')
    slate = HexColor('#0f172a')
    gray = HexColor('#64748b')
    border = HexColor('#e2e8f0')
    col_right = width / 2 + 10

    c.setStrokeColor(border)
    c.line(50, y, width - 50, y)
    y -= 14

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(slate)
    c.drawString(50, y, "FINANCE OFFICER:")
    c.drawString(col_right, y, "AUTHORIZED SIGNATORY:")

    y -= 38
    c.setStrokeColor(HexColor('#94a3b8'))
    c.line(50, y, 220, y)
    c.line(col_right, y, col_right + 170, y)
    y -= 14
    c.setFont("Helvetica", 9)
    c.setFillColor(gray)
    c.drawString(50, y, "Signature & Date")
    c.drawString(col_right, y, "Signature & Date")

    y -= 28
    c.setStrokeColor(HexColor('#94a3b8'))
    c.line(50, y, 220, y)
    c.line(col_right, y, col_right + 170, y)
    y -= 14
    c.setFont("Helvetica", 9)
    c.setFillColor(gray)
    c.drawString(50, y, "Full Name & Designation")
    c.drawString(col_right, y, "Full Name & Designation")

    stamp_box_x = width / 2 - 36
    stamp_box_y = y - 52
    c.setStrokeColor(HexColor('#cbd5e1'))
    c.setDash(4, 3)
    c.roundRect(stamp_box_x, stamp_box_y, 72, 48, 4, fill=0, stroke=1)
    c.setDash()
    c.setFont("Helvetica", 7)
    c.setFillColor(HexColor('#94a3b8'))
    c.drawCentredString(width / 2, stamp_box_y + 18, "OFFICIAL STAMP")
    y = stamp_box_y - 16

    footer_y = max(y - 10, 24)
    c.setStrokeColor(green)
    c.setLineWidth(1)
    c.line(50, footer_y + 14, width - 50, footer_y + 14)
    c.setFont("Helvetica", 8)
    c.setFillColor(gray)
    footer_parts = [company_name]
    if contact_phone:
        footer_parts.append(f"Tel: {contact_phone}")
    if headquarters:
        footer_parts.append(headquarters)
    c.drawCentredString(width / 2, footer_y + 4, "  |  ".join(footer_parts))
    c.setFont("Helvetica-Oblique", 7)
    c.drawCentredString(width / 2, footer_y - 6,
                        f"Certificate {cert_ref}  |  Clearance date: {clearance_date_str}")


def _paragraph_text(value):
    """Escape dynamic values before inserting them into ReportLab paragraph markup."""
    return escape(str(value or ''))


def _clearance_date(record, payments):
    """Use the latest recorded payment date, regardless of input ordering."""
    payment_dates = [
        payment.payment_date
        for payment in payments
        if getattr(payment, 'payment_date', None)
    ]
    if payment_dates:
        return max(payment_dates)
    return record.due_date or get_local_now().date()


def _money(value):
    return Decimal(str(value or 0)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)


def _loan_plan_label(loan):
    if getattr(loan, 'interest_mode', None) == 'monthly_accrual':
        return 'Monthly accrual'
    if getattr(loan, 'interest_mode', None) == 'reducing_balance_equal':
        return 'Reducing balance - equal monthly payments'
    return 'Flat rate'


def _start_loan_pdf(title, reference):
    buffer = io.BytesIO()
    settings = get_site_settings()
    company_name = get_company_display_name(settings)
    contact_phone = getattr(settings, 'contact_phone', '') or ''
    headquarters = getattr(settings, 'headquarters', '') or ''

    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 26
    y = draw_logo_header(c, width, y)
    y -= 6
    c.setFillColor(HexColor('#0f172a'))
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(width / 2, y, title)
    y -= 16
    c.setFillColor(HexColor('#64748b'))
    c.setFont("Helvetica", 9)
    c.drawCentredString(width / 2, y, f"Reference: {reference} | Generated: {get_local_now().strftime('%B %d, %Y')}")
    y -= 16
    c.setStrokeColor(HexColor('#e2e8f0'))
    c.line(50, y, width - 50, y)
    y -= 18
    return buffer, c, width, height, y, company_name, contact_phone, headquarters


def _draw_loan_summary(c, width, y, loan):
    slate = HexColor('#0f172a')
    gray = HexColor('#64748b')
    border = HexColor('#e2e8f0')

    left_w = (width - 112) / 2
    right_x = 62 + left_w + 20
    top = y
    c.setFillColor(HexColor('#f8fafc'))
    c.roundRect(50, top - 120, left_w, 128, 6, fill=1, stroke=0)
    c.setStrokeColor(border)
    c.roundRect(50, top - 120, left_w, 128, 6, fill=0, stroke=1)
    c.setFillColor(HexColor('#fff7ed'))
    c.roundRect(right_x - 12, top - 120, left_w, 128, 6, fill=1, stroke=0)
    c.setStrokeColor(border)
    c.roundRect(right_x - 12, top - 120, left_w, 128, 6, fill=0, stroke=1)

    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(slate)
    c.drawString(62, top - 14, "BORROWER")
    c.drawString(right_x, top - 14, "FINANCIAL SUMMARY")
    c.setFont("Helvetica", 9)
    c.setFillColor(gray)
    client = getattr(loan, 'client', None)
    borrower_rows = [
        ("Name", getattr(client, 'name', 'N/A') if client else 'N/A'),
        ("Phone", getattr(client, 'phone', 'N/A') if client else 'N/A'),
        ("NIN", getattr(client, 'nin', None) or 'N/A' if client else 'N/A'),
        ("Plan", _loan_plan_label(loan)),
        ("Due Date", loan.due_date.strftime('%b %d, %Y') if getattr(loan, 'due_date', None) else 'N/A'),
    ]
    by = top - 30
    for label, value in borrower_rows:
        c.drawString(62, by, f"{label}:")
        c.setFillColor(slate)
        c.drawString(110, by, str(value)[:34])
        c.setFillColor(gray)
        by -= 15

    summary_rows = [
        ("Principal", format_currency(float(_money(getattr(loan, 'principal', 0))))),
        ("Scheduled Interest", format_currency(float(_money(getattr(loan, 'interest_amount', 0))))),
        ("Total Due", format_currency(float(_money(getattr(loan, 'total_amount', 0))))),
        ("Amount Paid", format_currency(float(_money(getattr(loan, 'amount_paid', 0))))),
        ("Balance", format_currency(float(_money(getattr(loan, 'balance', 0))))),
    ]
    sy = top - 30
    for label, value in summary_rows:
        c.setFillColor(gray)
        c.drawString(right_x, sy, f"{label}:")
        c.setFillColor(slate)
        c.drawRightString(width - 62, sy, value)
        sy -= 15

    return top - 138


def _draw_payments_table(c, width, height, y, payments):
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(HexColor('#0f172a'))
    c.drawString(50, y, "PAYMENT HISTORY")
    y -= 16
    c.setFont("Helvetica-Bold", 8)
    c.drawString(58, y, "Date")
    c.drawRightString(205, y, "Principal")
    c.drawRightString(310, y, "Interest")
    c.drawRightString(415, y, "Paid")
    c.drawRightString(width - 58, y, "Balance")
    y -= 10
    c.setFont("Helvetica", 8)
    if not payments:
        c.setFillColor(HexColor('#64748b'))
        c.drawString(58, y, "No payments recorded yet.")
        return y - 18

    for idx, pmt in enumerate(payments):
        if y < 90:
            c.showPage()
            y = height - 60
        c.setFillColor(HexColor('#f8fafc') if idx % 2 == 0 else HexColor('#ffffff'))
        c.rect(50, y - 11, width - 100, 15, fill=1, stroke=0)
        c.setFillColor(HexColor('#0f172a'))
        pdate = pmt.payment_date.strftime('%b %d, %Y') if getattr(pmt, 'payment_date', None) else '-'
        c.drawString(58, y - 8, pdate)
        c.drawRightString(205, y - 8, format_currency(float(_money(getattr(pmt, 'principal_amount', 0)))))
        c.drawRightString(310, y - 8, format_currency(float(_money(getattr(pmt, 'interest_amount', 0)))))
        c.drawRightString(415, y - 8, format_currency(float(_money(getattr(pmt, 'amount', 0)))))
        c.drawRightString(width - 58, y - 8, format_currency(float(_money(getattr(pmt, 'balance_after', 0)))))
        y -= 15
    return y - 10


def _draw_schedule_table(c, width, height, y, schedule, title="REPAYMENT SCHEDULE"):
    if not schedule:
        return y
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(HexColor('#0f172a'))
    c.drawString(50, y, title)
    y -= 16
    c.setFont("Helvetica-Bold", 8)
    c.drawString(58, y, "Month")
    c.drawString(112, y, "Due")
    c.drawRightString(230, y, "Payment")
    c.drawRightString(330, y, "Interest")
    c.drawRightString(435, y, "Principal")
    c.drawRightString(width - 58, y, "Balance")
    y -= 10
    c.setFont("Helvetica", 8)
    for idx, row in enumerate(schedule):
        if y < 90:
            c.showPage()
            y = height - 60
        c.setFillColor(HexColor('#f8fafc') if idx % 2 == 0 else HexColor('#ffffff'))
        c.rect(50, y - 11, width - 100, 15, fill=1, stroke=0)
        c.setFillColor(HexColor('#0f172a'))
        due_value = row.get('due_date')
        due_text = due_value.strftime('%b %d, %Y') if hasattr(due_value, 'strftime') else '-'
        c.drawString(58, y - 8, str(row.get('period', idx + 1)))
        c.drawString(112, y - 8, due_text)
        c.drawRightString(230, y - 8, format_currency(float(_money(row.get('payment', 0)))))
        c.drawRightString(330, y - 8, format_currency(float(_money(row.get('interest', 0)))))
        c.drawRightString(435, y - 8, format_currency(float(_money(row.get('principal', 0)))))
        c.drawRightString(width - 58, y - 8, format_currency(float(_money(row.get('balance_after', 0)))))
        y -= 15
    return y - 10


def _finish_loan_pdf(buffer, c, width, company_name, contact_phone, headquarters):
    c.setFillColor(HexColor('#64748b'))
    c.setFont("Helvetica", 8)
    footer = company_name
    if contact_phone:
        footer += f" | {contact_phone}"
    if headquarters:
        footer += f" | {headquarters}"
    c.drawCentredString(width / 2, 32, footer[:120])
    c.save()
    buffer.seek(0)
    return buffer


def generate_loan_statement_pdf(loan, payments, schedule=None):
    """Generate a printable/shareable individual loan statement."""
    ref = f"LOAN-{loan.id:05d}"
    buffer, c, width, height, y, company_name, contact_phone, headquarters = _start_loan_pdf(
        "INDIVIDUAL LOAN STATEMENT", ref
    )
    y = _draw_loan_summary(c, width, y, loan)
    if schedule:
        y = _draw_schedule_table(c, width, height, y, schedule)
    y = _draw_payments_table(c, width, height, y, payments)
    return _finish_loan_pdf(buffer, c, width, company_name, contact_phone, headquarters)


def generate_payment_plan_pdf(loan, payments, plan_months=3, schedule=None):
    """Generate a proposed repayment plan for an overdue or delayed borrower."""
    ref = f"PLAN-{loan.id:05d}"
    buffer, c, width, height, y, company_name, contact_phone, headquarters = _start_loan_pdf(
        "PROPOSED PAYMENT PLAN", ref
    )
    y = _draw_loan_summary(c, width, y, loan)

    balance = _money(getattr(loan, 'balance', 0))
    months = max(1, int(plan_months or 1))
    monthly_amount = _money(balance / Decimal(months)) if balance > 0 else Decimal('0')
    start_date = get_local_now().date()

    styles = getSampleStyleSheet()
    body_style = styles['Normal']
    body_style.fontName = 'Helvetica'
    body_style.fontSize = 9
    body_style.leading = 14
    body_style.textColor = HexColor('#0f172a')
    client_name = getattr(getattr(loan, 'client', None), 'name', 'the borrower')
    text = (
        f"This proposal gives {client_name} a structured way to clear the outstanding "
        f"balance of <b>{format_currency(float(balance))}</b> over <b>{months}</b> months. "
        "Payments may be adjusted by management if the borrower pays early or makes an additional deposit."
    )
    para = Paragraph(text, body_style)
    para_h = para.wrap(width - 100, 90)[1]
    para.drawOn(c, 50, y - para_h)
    y -= para_h + 18

    plan_rows = []
    remaining = balance
    for idx in range(1, months + 1):
        amount = monthly_amount if idx < months else remaining
        remaining -= amount
        due_date = start_date + relativedelta(months=idx)
        plan_rows.append({
            'period': idx,
            'payment': amount,
            'interest': Decimal('0'),
            'principal': amount,
            'balance_after': max(remaining, Decimal('0')),
            'due_date': due_date,
        })
    y = _draw_schedule_table(c, width, height, y, plan_rows, title="PROPOSED CLEARANCE PLAN")
    y = _draw_payments_table(c, width, height, y, payments)
    return _finish_loan_pdf(buffer, c, width, company_name, contact_phone, headquarters)


def generate_overdue_reminder_pdf(loan, payments, schedule=None):
    """Generate an overdue reminder letter with a financial summary."""
    ref = f"REM-{loan.id:05d}"
    buffer, c, width, height, y, company_name, contact_phone, headquarters = _start_loan_pdf(
        "OVERDUE LOAN REMINDER", ref
    )
    y = _draw_loan_summary(c, width, y, loan)

    styles = getSampleStyleSheet()
    body_style = styles['Normal']
    body_style.fontName = 'Helvetica'
    body_style.fontSize = 10
    body_style.leading = 15
    body_style.textColor = HexColor('#0f172a')
    client_name = getattr(getattr(loan, 'client', None), 'name', 'Borrower')
    due_date = loan.due_date.strftime('%B %d, %Y') if getattr(loan, 'due_date', None) else 'the due date'
    balance = format_currency(float(_money(getattr(loan, 'balance', 0))))
    text = (
        f"Dear <b>{_paragraph_text(client_name)}</b>,<br/><br/>"
        f"Our records show that your loan due on <b>{due_date}</b> has an outstanding "
        f"balance of <b>{balance}</b>. Please contact our finance office or make a payment "
        "as soon as possible so that we can agree on a clear repayment path."
    )
    para = Paragraph(text, body_style)
    para_h = para.wrap(width - 100, 140)[1]
    para.drawOn(c, 50, y - para_h)
    y -= para_h + 20

    if schedule:
        y = _draw_schedule_table(c, width, height, y, schedule)
    y = _draw_payments_table(c, width, height, y, payments)
    return _finish_loan_pdf(buffer, c, width, company_name, contact_phone, headquarters)


def generate_clearance_pdf(loan, payments):
    """Generate a formal Loan Clearance Certificate for a fully paid individual loan."""
    buffer = io.BytesIO()
    settings = get_site_settings()
    company_name = get_company_display_name(settings)
    contact_phone = getattr(settings, 'contact_phone', '') or ''
    headquarters = getattr(settings, 'headquarters', '') or ''

    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    green = HexColor('#16a34a')
    green_light = HexColor('#f0fdf4')
    slate = HexColor('#0f172a')
    gray = HexColor('#64748b')
    border = HexColor('#e2e8f0')

    # Deterministic certificate identity: derived from loan ID and final payment date
    cert_ref = f'LCC-{loan.id:05d}'
    clearance_date = _clearance_date(loan, payments)
    clearance_date_str = clearance_date.strftime('%B %d, %Y') if hasattr(clearance_date, 'strftime') else str(clearance_date)

    # ── Page 1 header ────────────────────────────────────────────
    y = height - 26
    y = draw_logo_header(c, width, y)

    y -= 4
    c.setFillColor(green)
    c.rect(50, y - 2, width - 100, 3, fill=1, stroke=0)
    y -= 16

    c.setFillColor(slate)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, y, "LOAN CLEARANCE CERTIFICATE")
    y -= 20

    c.setFont("Helvetica", 9)
    c.setFillColor(gray)
    c.drawCentredString(width / 2, y,
                        f"Certificate No: {cert_ref}   |   Clearance Date: {clearance_date_str}")
    y -= 14
    c.setStrokeColor(border)
    c.line(50, y, width - 50, y)
    y -= 20

    # ── Salutation ───────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(slate)
    c.drawString(50, y, "TO WHOM IT MAY CONCERN")
    y -= 18

    client_name = _paragraph_text(loan.client.name if loan.client else 'The Borrower')
    company_name_paragraph = _paragraph_text(company_name)

    styles = getSampleStyleSheet()
    body_style = styles['Normal']
    body_style.fontName = 'Helvetica'
    body_style.fontSize = 10
    body_style.leading = 16
    body_style.textColor = HexColor('#0f172a')

    cert_text = (
        f"This is to certify that <b>{client_name}</b> held loan account <b>{cert_ref}</b> "
        f"with <b>{company_name_paragraph}</b>. As recorded in the loan ledger, the outstanding balance "
        f"on this account was confirmed as zero (0) on <b>{clearance_date_str}</b>, "
        f"reflecting full repayment of the principal and all accrued interest."
    )
    para = Paragraph(cert_text, body_style)
    para_width = width - 100
    para_height = para.wrap(para_width, 200)[1]
    para.drawOn(c, 50, y - para_height)
    y -= para_height + 20

    c.setStrokeColor(border)
    c.line(50, y, width - 50, y)
    y -= 16

    # ── Two-column info boxes ────────────────────────────────────
    col_right = width / 2 + 10
    col_w = (width - 100) / 2 - 8
    box_top = y

    c.setFillColor(HexColor('#f8fafc'))
    c.roundRect(50, box_top - 100, col_w, 108, 6, fill=1, stroke=0)
    c.setStrokeColor(border)
    c.roundRect(50, box_top - 100, col_w, 108, 6, fill=0, stroke=1)

    bx, by = 60, box_top - 14
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(green)
    c.drawString(bx, by, "BORROWER INFORMATION")
    by -= 14
    c.setFont("Helvetica", 9)
    c.setFillColor(slate)
    c.drawString(bx, by, f"Name:    {(loan.client.name if loan.client else 'N/A')[:32]}")
    by -= 13
    c.drawString(bx, by, f"Phone:   {(loan.client.phone if loan.client else 'N/A')[:32]}")
    by -= 13
    nin_display = str(loan.client.nin if loan.client and loan.client.nin else 'N/A')
    c.drawString(bx, by, f"NIN:     {nin_display[:32]}")
    by -= 13
    addr = (loan.client.address if loan.client and loan.client.address else 'N/A')
    c.drawString(bx, by, f"Address: {addr[:32]}")

    c.setFillColor(HexColor('#f8fafc'))
    c.roundRect(col_right, box_top - 100, col_w, 108, 6, fill=1, stroke=0)
    c.setStrokeColor(border)
    c.roundRect(col_right, box_top - 100, col_w, 108, 6, fill=0, stroke=1)

    rx, ry = col_right + 10, box_top - 14
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(green)
    c.drawString(rx, ry, "LOAN ACCOUNT SUMMARY")
    ry -= 14
    c.setFont("Helvetica", 9)
    c.setFillColor(slate)
    c.drawString(rx, ry, f"Reference:  {cert_ref}")
    ry -= 13
    issue_str = loan.issue_date.strftime('%b %d, %Y') if loan.issue_date else 'N/A'
    c.drawString(rx, ry, f"Issued:     {issue_str}")
    ry -= 13
    c.drawString(rx, ry, f"Cleared:    {clearance_date_str}")
    ry -= 13
    c.drawString(rx, ry, f"Principal:  {format_currency(float(loan.principal or 0))}")
    ry -= 13
    c.drawString(rx, ry, f"Total Paid: {format_currency(float(loan.amount_paid or 0))}")

    y = box_top - 110
    c.setStrokeColor(border)
    c.line(50, y, width - 50, y)
    y -= 16

    # ── Payment Record ───────────────────────────────────────────
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(slate)
    c.drawString(50, y, "PAYMENT RECORD")
    y -= 14
    y = _draw_payment_table_header_individual(c, width, y, green)

    c.setFont("Helvetica", 9)
    for idx, pmt in enumerate(payments):
        if y < 160:
            c.showPage()
            y = _draw_clearance_page_header(c, width, height, cert_ref, clearance_date_str, is_continuation=True)
            y = _draw_payment_table_header_individual(c, width, y, green)
        bg = HexColor('#f0fdf4') if idx % 2 == 0 else HexColor('#ffffff')
        c.setFillColor(bg)
        c.rect(50, y - 13, width - 100, 16, fill=1, stroke=0)
        c.setFillColor(slate)
        pdate = pmt.payment_date.strftime('%b %d, %Y') if pmt.payment_date else '-'
        c.drawString(58, y - 10, pdate)
        c.drawRightString(220, y - 10, format_currency(float(pmt.principal_amount or 0)))
        c.drawRightString(330, y - 10, format_currency(float(pmt.interest_amount or 0)))
        c.drawRightString(440, y - 10, format_currency(float(pmt.amount or 0)))
        c.drawRightString(width - 58, y - 10, format_currency(float(pmt.balance_after or 0)))
        y -= 16

    # Keep the settlement statement and signatures together instead of drawing
    # them into the bottom margin after a nearly full payment table.
    if y < 310:
        c.showPage()
        y = _draw_clearance_page_header(
            c, width, height, cert_ref, clearance_date_str, is_continuation=True
        )

    y -= 8
    c.setStrokeColor(border)
    c.line(50, y, width - 50, y)
    y -= 18

    # ── FULLY SETTLED badge ──────────────────────────────────────
    stamp_w, stamp_h = 200, 36
    stamp_x = (width - stamp_w) / 2
    stamp_y = y - stamp_h
    c.setFillColor(green_light)
    c.roundRect(stamp_x, stamp_y, stamp_w, stamp_h, 10, fill=1, stroke=0)
    c.setStrokeColor(green)
    c.setLineWidth(1.5)
    c.roundRect(stamp_x, stamp_y, stamp_w, stamp_h, 10, fill=0, stroke=1)
    c.setLineWidth(1)
    c.setFillColor(green)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, stamp_y + 11, "FULLY SETTLED")
    y = stamp_y - 18

    # ── Closing declaration ──────────────────────────────────────
    c.setStrokeColor(border)
    c.line(50, y, width - 50, y)
    y -= 14

    decl_style = styles['Normal']
    decl_style.fontName = 'Helvetica-Oblique'
    decl_style.fontSize = 9
    decl_style.leading = 14
    decl_style.textColor = HexColor('#475569')
    decl_text = (
        f"This document confirms that, as of {clearance_date_str}, the recorded balance for "
        f"loan account {cert_ref} is zero. It is issued as a record of the loan ledger status "
        f"on that date and does not constitute a legal waiver of any kind."
    )
    decl_para = Paragraph(decl_text, decl_style)
    decl_h = decl_para.wrap(width - 100, 80)[1]
    decl_para.drawOn(c, 50, y - decl_h)
    y -= decl_h + 16

    if y < 200:
        c.showPage()
        y = _draw_clearance_page_header(
            c, width, height, cert_ref, clearance_date_str, is_continuation=True
        )

    _draw_clearance_footer(c, width, company_name, contact_phone, headquarters,
                           cert_ref, clearance_date_str, y)
    c.save()
    buffer.seek(0)
    return buffer


def generate_group_clearance_pdf(group, payments):
    """Generate a formal Loan Clearance Certificate for a fully paid group loan."""
    buffer = io.BytesIO()
    settings = get_site_settings()
    company_name = get_company_display_name(settings)
    contact_phone = getattr(settings, 'contact_phone', '') or ''
    headquarters = getattr(settings, 'headquarters', '') or ''

    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    green = HexColor('#16a34a')
    green_light = HexColor('#f0fdf4')
    slate = HexColor('#0f172a')
    gray = HexColor('#64748b')
    border = HexColor('#e2e8f0')

    cert_ref = f'GLCC-{group.id:05d}'
    clearance_date = _clearance_date(group, payments)
    clearance_date_str = clearance_date.strftime('%B %d, %Y') if hasattr(clearance_date, 'strftime') else str(clearance_date)

    # When a group loan balance reaches zero the periods_paid counter may be lower
    # than total_periods (e.g. early lump-sum settlement). Show "Fully settled"
    # instead of the raw fraction to avoid a contradictory certificate.
    if float(group.balance or 0) <= 0:
        periods_display = "Fully settled"
    else:
        periods_display = f"{group.periods_paid} of {group.total_periods}"

    # ── Page 1 header ────────────────────────────────────────────
    y = height - 26
    y = draw_logo_header(c, width, y)

    y -= 4
    c.setFillColor(green)
    c.rect(50, y - 2, width - 100, 3, fill=1, stroke=0)
    y -= 16

    c.setFillColor(slate)
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(width / 2, y, "GROUP LOAN CLEARANCE CERTIFICATE")
    y -= 20

    c.setFont("Helvetica", 9)
    c.setFillColor(gray)
    c.drawCentredString(width / 2, y,
                        f"Certificate No: {cert_ref}   |   Clearance Date: {clearance_date_str}")
    y -= 14
    c.setStrokeColor(border)
    c.line(50, y, width - 50, y)
    y -= 20

    # ── Salutation ───────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(slate)
    c.drawString(50, y, "TO WHOM IT MAY CONCERN")
    y -= 18

    styles = getSampleStyleSheet()
    body_style = styles['Normal']
    body_style.fontName = 'Helvetica'
    body_style.fontSize = 10
    body_style.leading = 16
    body_style.textColor = HexColor('#0f172a')

    group_name_paragraph = _paragraph_text(group.group_name)
    company_name_paragraph = _paragraph_text(company_name)
    cert_text = (
        f"This is to certify that <b>{group_name_paragraph}</b> (comprising <b>{group.member_count} "
        f"member(s)</b>) held group loan account <b>{cert_ref}</b> with <b>{company_name_paragraph}</b>. "
        f"As recorded in the loan ledger, the outstanding balance on this account was confirmed "
        f"as zero (0) on <b>{clearance_date_str}</b>, reflecting full repayment of the principal "
        f"and all accrued interest."
    )
    para = Paragraph(cert_text, body_style)
    para_h = para.wrap(width - 100, 200)[1]
    para.drawOn(c, 50, y - para_h)
    y -= para_h + 20

    c.setStrokeColor(border)
    c.line(50, y, width - 50, y)
    y -= 16

    # ── Two-column info boxes ────────────────────────────────────
    col_right = width / 2 + 10
    col_w = (width - 100) / 2 - 8
    box_top = y

    c.setFillColor(HexColor('#f8fafc'))
    c.roundRect(50, box_top - 100, col_w, 108, 6, fill=1, stroke=0)
    c.setStrokeColor(border)
    c.roundRect(50, box_top - 100, col_w, 108, 6, fill=0, stroke=1)

    bx, by = 60, box_top - 14
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(green)
    c.drawString(bx, by, "GROUP INFORMATION")
    by -= 14
    c.setFont("Helvetica", 9)
    c.setFillColor(slate)
    c.drawString(bx, by, f"Group Name: {group.group_name[:30]}")
    by -= 13
    c.drawString(bx, by, f"Members:    {group.member_count}")
    by -= 13
    issue_str = group.issue_date.strftime('%b %d, %Y') if group.issue_date else 'N/A'
    c.drawString(bx, by, f"Issued:     {issue_str}")
    by -= 13
    c.drawString(bx, by, f"Cleared:    {clearance_date_str}")

    c.setFillColor(HexColor('#f8fafc'))
    c.roundRect(col_right, box_top - 100, col_w, 108, 6, fill=1, stroke=0)
    c.setStrokeColor(border)
    c.roundRect(col_right, box_top - 100, col_w, 108, 6, fill=0, stroke=1)

    rx, ry = col_right + 10, box_top - 14
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(green)
    c.drawString(rx, ry, "LOAN ACCOUNT SUMMARY")
    ry -= 14
    c.setFont("Helvetica", 9)
    c.setFillColor(slate)
    c.drawString(rx, ry, f"Reference:  {cert_ref}")
    ry -= 13
    c.drawString(rx, ry, f"Principal:  {format_currency(float(group.principal or 0))}")
    ry -= 13
    c.drawString(rx, ry, f"Total Paid: {format_currency(float(group.amount_paid or 0))}")
    ry -= 13
    c.drawString(rx, ry, f"Periods:    {periods_display}")

    y = box_top - 110
    c.setStrokeColor(border)
    c.line(50, y, width - 50, y)
    y -= 16

    # ── Payment Record ───────────────────────────────────────────
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(slate)
    c.drawString(50, y, "PAYMENT RECORD")
    y -= 14
    y = _draw_payment_table_header_group(c, width, y, green)

    c.setFont("Helvetica", 9)
    for idx, pmt in enumerate(payments):
        if y < 160:
            c.showPage()
            y = _draw_clearance_page_header(c, width, height, cert_ref, clearance_date_str, is_continuation=True)
            y = _draw_payment_table_header_group(c, width, y, green)
        bg = HexColor('#f0fdf4') if idx % 2 == 0 else HexColor('#ffffff')
        c.setFillColor(bg)
        c.rect(50, y - 13, width - 100, 16, fill=1, stroke=0)
        c.setFillColor(slate)
        pdate = pmt.payment_date.strftime('%b %d, %Y') if pmt.payment_date else '-'
        c.drawString(58, y - 10, pdate)
        c.drawRightString(300, y - 10, str(getattr(pmt, 'periods_covered', '-')))
        c.drawRightString(440, y - 10, format_currency(float(pmt.amount or 0)))
        c.drawRightString(width - 58, y - 10, format_currency(float(pmt.balance_after or 0)))
        y -= 16

    if y < 310:
        c.showPage()
        y = _draw_clearance_page_header(
            c, width, height, cert_ref, clearance_date_str, is_continuation=True
        )

    y -= 8
    c.setStrokeColor(border)
    c.line(50, y, width - 50, y)
    y -= 18

    # ── FULLY SETTLED badge ──────────────────────────────────────
    stamp_w, stamp_h = 220, 36
    stamp_x = (width - stamp_w) / 2
    stamp_y = y - stamp_h
    c.setFillColor(green_light)
    c.roundRect(stamp_x, stamp_y, stamp_w, stamp_h, 10, fill=1, stroke=0)
    c.setStrokeColor(green)
    c.setLineWidth(1.5)
    c.roundRect(stamp_x, stamp_y, stamp_w, stamp_h, 10, fill=0, stroke=1)
    c.setLineWidth(1)
    c.setFillColor(green)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, stamp_y + 11, "FULLY SETTLED")
    y = stamp_y - 18

    # ── Closing declaration ──────────────────────────────────────
    c.setStrokeColor(border)
    c.line(50, y, width - 50, y)
    y -= 14

    decl_style = styles['Normal']
    decl_style.fontName = 'Helvetica-Oblique'
    decl_style.fontSize = 9
    decl_style.leading = 14
    decl_style.textColor = HexColor('#475569')
    decl_text = (
        f"This document confirms that, as of {clearance_date_str}, the recorded balance for "
        f"group loan account {cert_ref} is zero. It is issued as a record of the loan ledger "
        f"status on that date and does not constitute a legal waiver of any kind."
    )
    decl_para = Paragraph(decl_text, decl_style)
    decl_h = decl_para.wrap(width - 100, 80)[1]
    decl_para.drawOn(c, 50, y - decl_h)
    y -= decl_h + 16

    if y < 200:
        c.showPage()
        y = _draw_clearance_page_header(
            c, width, height, cert_ref, clearance_date_str, is_continuation=True
        )

    _draw_clearance_footer(c, width, company_name, contact_phone, headquarters,
                           cert_ref, clearance_date_str, y)
    c.save()
    buffer.seek(0)
    return buffer


def generate_hire_receipt_pdf(hire, business_name, served_by=None):
    """Generate PDF receipt for a hire/rental transaction"""
    buffer = io.BytesIO()
    company_name = get_company_display_name()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Header with logo
    y = height - 26
    y = draw_logo_header(c, width, y)

    y -= 2
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(HexColor('#64748b'))
    c.drawCentredString(width / 2, y, business_name)
    c.setFillColor(HexColor('#0f172a'))

    y -= 20
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
    c.drawCentredString(width / 2, y, f"Thank you for choosing {company_name}.")

    y -= 16
    c.setFont("Helvetica", 8)
    c.setFillColor(HexColor('#94a3b8'))
    c.drawCentredString(width / 2, y, f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")

    c.save()
    buffer.seek(0)
    return buffer
