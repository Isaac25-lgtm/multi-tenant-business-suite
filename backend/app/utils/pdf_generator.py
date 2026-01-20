from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from datetime import datetime
import io


def format_currency(amount):
    """Format currency as UGX with thousands separator"""
    return f"UGX {amount:,.0f}"


def generate_receipt_pdf(sale, business_name):
    """Generate PDF receipt for a sale"""
    buffer = io.BytesIO()
    
    # Create PDF
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Set font
    c.setFont("Helvetica-Bold", 16)
    
    # Header
    y = height - 40
    c.drawCentredString(width/2, y, "DENOVE APS")
    
    y -= 20
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
