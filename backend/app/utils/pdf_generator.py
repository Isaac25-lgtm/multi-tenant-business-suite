from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.lib.colors import HexColor
from datetime import datetime
import io


def format_currency(amount):
    """Format currency as UGX with thousands separator"""
    return f"UGX {amount:,.0f}"


def draw_logo_header(c, width, y):
    """Draw the Denove APS logo header on PDF"""
    # Draw logo box (indigo background)
    logo_color = HexColor('#4f46e5')
    gold_color = HexColor('#fbbf24')

    # Logo box
    box_x = width/2 - 100
    box_y = y - 30
    c.setFillColor(logo_color)
    c.roundRect(box_x, box_y, 45, 40, 8, fill=1, stroke=0)

    # Letter D in the box
    c.setFillColor(HexColor('#ffffff'))
    c.setFont("Helvetica-Bold", 24)
    c.drawString(box_x + 12, box_y + 10, "D")

    # Gold coin circle
    c.setFillColor(gold_color)
    c.circle(box_x + 30, box_y + 20, 8, fill=1, stroke=0)
    c.setFillColor(logo_color)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(box_x + 30, box_y + 17, "$")

    # Company name
    c.setFillColor(HexColor('#1f2937'))
    c.setFont("Helvetica-Bold", 22)
    c.drawString(box_x + 55, box_y + 18, "DENOVE")

    c.setFillColor(HexColor('#6b7280'))
    c.setFont("Helvetica", 14)
    c.drawString(box_x + 55, box_y + 2, "APS")

    # Underline
    c.setStrokeColor(logo_color)
    c.setLineWidth(2)
    c.line(box_x + 55, box_y - 2, box_x + 115, box_y - 2)

    # Reset colors
    c.setStrokeColor(HexColor('#000000'))
    c.setFillColor(HexColor('#000000'))
    c.setLineWidth(1)

    return y - 50


def generate_receipt_pdf(sale, business_name):
    """Generate PDF receipt for a sale"""
    buffer = io.BytesIO()

    # Create PDF
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Header with logo
    y = height - 20
    y = draw_logo_header(c, width, y)

    y -= 10
    c.setFont("Helvetica", 12)
    c.drawCentredString(width/2, y, f"[{business_name}]")
    
    y -= 30
    c.line(50, y, width-50, y)
    
    # Business details (placeholders)
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawCentredString(width/2, y, "Phone: [To be configured]")
    y -= 15
    c.drawCentredString(width/2, y, "Address: [To be configured]")
    
    y -= 20
    c.line(50, y, width-50, y)
    
    # Receipt title
    y -= 30
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width/2, y, "RECEIPT")
    
    # Receipt details
    y -= 30
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Reference: {sale.reference_number}")
    y -= 15
    c.drawString(50, y, f"Date: {sale.sale_date.strftime('%B %d, %Y')}")
    y -= 15
    c.drawString(50, y, f"Time: {sale.created_at.strftime('%I:%M %p')}")
    y -= 15
    c.drawString(50, y, f"Served by: {sale.creator.name if sale.creator else 'N/A'}")
    
    y -= 30
    c.line(50, y, width-50, y)
    
    # Items header
    y -= 20
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "ITEMS")
    
    y -= 20
    c.line(50, y, width-50, y)
    
    y -= 20
    c.drawString(50, y, "Description")
    c.drawString(250, y, "Qty")
    c.drawString(320, y, "Price")
    c.drawString(420, y, "Amount")
    
    y -= 5
    c.line(50, y, width-50, y)
    
    # Items
    y -= 20
    c.setFont("Helvetica", 10)
    
    for item in sale.items:
        if y < 100:  # Check if we need a new page
            c.showPage()
            y = height - 40
            c.setFont("Helvetica", 10)
        
        c.drawString(50, y, item.item_name[:30])  # Truncate long names
        c.drawString(250, y, str(item.quantity))
        c.drawString(320, y, format_currency(float(item.unit_price)))
        c.drawString(420, y, format_currency(float(item.subtotal)))
        y -= 20
    
    y -= 10
    c.line(50, y, width-50, y)
    
    # Total
    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(350, y, "TOTAL:")
    c.drawString(420, y, format_currency(float(sale.total_amount)))
    
    y -= 5
    c.line(50, y, width-50, y)
    
    # Payment details
    y -= 25
    c.setFont("Helvetica", 10)
    
    if sale.payment_type == 'full':
        c.drawString(50, y, "Payment Method: FULL PAYMENT")
        y -= 15
        c.drawString(50, y, f"Amount Paid: {format_currency(float(sale.amount_paid))}")
    else:
        c.drawString(50, y, "Payment Method: PART PAYMENT")
        y -= 15
        c.drawString(50, y, f"Amount Paid: {format_currency(float(sale.amount_paid))}")
        y -= 15
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, f"Balance Due: {format_currency(float(sale.balance))}")
        
        if sale.customer:
            y -= 25
            c.setFont("Helvetica", 10)
            c.drawString(50, y, f"Customer: {sale.customer.name}")
            y -= 15
            c.drawString(50, y, f"Phone: {sale.customer.phone}")
    
    y -= 30
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
