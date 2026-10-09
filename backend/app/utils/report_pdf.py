"""Manager's monthly report as a PDF (three-month comparison)."""
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.utils.branding import get_company_display_name, get_site_settings
from app.utils.pdf_generator import draw_logo_header

INK = colors.HexColor('#1f2937')
MUTED = colors.HexColor('#6b7280')
LINE = colors.HexColor('#e5e7eb')
HEAD = colors.HexColor('#f3f4f6')
BRAND = colors.HexColor('#7a1f2b')


def _money(value):
    return f"{float(value or 0):,.0f}"


def _table(rows, col_widths, bold_last_row=False, align_from=1):
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    style = [
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 8.5),
        ('FONT', (0, 1), (-1, -1), 'Helvetica', 8.5),
        ('TEXTCOLOR', (0, 0), (-1, -1), INK),
        ('BACKGROUND', (0, 0), (-1, 0), HEAD),
        ('ALIGN', (align_from, 0), (-1, -1), 'RIGHT'),
        ('LINEBELOW', (0, 0), (-1, -1), 0.4, LINE),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]
    if bold_last_row:
        style += [('FONT', (0, -1), (-1, -1), 'Helvetica-Bold', 8.5), ('BACKGROUND', (0, -1), (-1, -1), HEAD)]
    table.setStyle(TableStyle(style))
    return table


def generate_monthly_report_pdf(report):
    buffer = io.BytesIO()
    settings = get_site_settings()
    company = get_company_display_name(settings)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle('h1', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=15, textColor=INK, spaceAfter=2)
    h2 = ParagraphStyle('h2', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=10.5, textColor=BRAND,
                        spaceBefore=12, spaceAfter=5)
    note = ParagraphStyle('note', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=MUTED, leading=11)

    def on_page(canvas, doc):
        canvas.saveState()
        draw_logo_header(canvas, A4[0], A4[1] - 26)
        canvas.setFont('Helvetica', 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(50, 28, f"{company} - Monthly report - {report['title_month']}")
        canvas.drawRightString(A4[0] - 50, 28, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=42 * mm, bottomMargin=20 * mm,
                            title=f"Monthly report {report['title_month']}", author=company)
    width = A4[0] - 100
    months = report['months']
    labels = [m['label'] + (' (to date)' if m['partial'] else '') for m in months]
    story = [
        Paragraph(f"Monthly report: {report['title_month']}", h1),
        Paragraph(f"Compared with the two months before. Generated {report['generated_on'].strftime('%d %B %Y')}. "
                  "All amounts in UGX.", note),
    ]

    # 1. Company summary
    story.append(Paragraph('1. Company summary', h2))
    lines = [
        ('Total sales (all units)', 'sales_value'),
        ('Cash received', 'cash_received'),
        ('Gross profit (retail)', 'gross_profit'),
        ('Interest earned (loans)', 'interest_earned'),
        ('Hire income', 'hire_income'),
        ('Expenses', 'expenses'),
        ('Net profit', 'net_profit'),
    ]
    rows = [['', *labels]]
    for label, key in lines:
        rows.append([label, *[_money(m['summary'][key]) for m in months]])
    story.append(_table(rows, [width * 0.34, width * 0.22, width * 0.22, width * 0.22], bold_last_row=True))
    story.append(Paragraph('Sales count in full on the day of sale, including credit. Cash received is money actually '
                           'collected, including loan repayments. Net profit = gross profit + interest earned + hire '
                           'income - expenses - principal written off.', note))

    # 2. The three businesses
    story.append(Paragraph('2. Comparison of the three businesses', h2))
    rows = [['Business', 'Measure', *labels]]
    for unit, label in (('boutique', 'Boutique'), ('hardware', 'Hardware')):
        rows.append([label, 'Sales', *[_money(m['summary'][unit]['sales_value']) for m in months]])
        rows.append(['', 'Gross profit', *[_money(m['summary'][unit]['gross_profit']) for m in months]])
        rows.append(['', 'Expenses', *[_money(m['summary']['expenses_by_unit'][unit]) for m in months]])
        rows.append(['', 'Profit', *[_money(m['summary']['unit_profit'][unit]) for m in months]])
    rows.append(['Finance', 'Loans collected', *[_money(m['summary']['loans']['total']) for m in months]])
    rows.append(['', 'Interest earned', *[_money(m['summary']['interest_earned']) for m in months]])
    rows.append(['', 'Expenses', *[_money(m['summary']['expenses_by_unit']['finance']) for m in months]])
    rows.append(['', 'Profit', *[_money(m['summary']['unit_profit']['finance']) for m in months]])
    table = _table(rows, [width * 0.16, width * 0.21, width * 0.21, width * 0.21, width * 0.21], align_from=2)
    table.setStyle(TableStyle([('FONT', (0, 1), (0, -1), 'Helvetica-Bold', 8.5)]
                              + [('FONT', (1, r), (-1, r), 'Helvetica-Bold', 8.5) for r in (4, 8, 12)]))
    story.append(table)
    story.append(Paragraph('Each business carries its own expenses. Boutique profit includes hire income.', note))

    # 3. Weekly profit
    story.append(Paragraph('3. Weekly profit, last three months', h2))
    rows = [['Week', 'Sales', 'Gross profit', 'Interest', 'Expenses', 'Net profit']]
    for week in report['weeks']:
        rows.append([week['label'], _money(week['sales_value']), _money(week['gross_profit']),
                     _money(week['interest_earned']), _money(week['expenses']), _money(week['net_profit'])])
    rows.append(['Total', *[_money(sum(week[key] for week in report['weeks']))
                            for key in ('sales_value', 'gross_profit', 'interest_earned', 'expenses', 'net_profit')]])
    story.append(_table(rows, [width * 0.25] + [width * 0.15] * 5, bold_last_row=True))

    # 4. Stock
    inventory = report['inventory']
    story.append(Paragraph('4. Stock today', h2))
    rows = [['', 'Value at cost', 'Items low on stock'],
            ['Boutique', _money(inventory['boutique_value']), str(inventory['boutique_low'])],
            ['Hardware', _money(inventory['hardware_value']), str(inventory['hardware_low'])],
            ['Total', _money(inventory['total_value']), str(inventory['boutique_low'] + inventory['hardware_low'])]]
    story.append(_table(rows, [width * 0.4, width * 0.3, width * 0.3], bold_last_row=True))

    # 5. Products
    story.append(Paragraph(f"5. Best and least selling products, {report['title_month']}", h2))
    rows = [['Best selling', 'Business', 'Units sold', 'Sales']]
    for row in report['best_sellers']:
        rows.append([row['item'][:38], row['unit'], str(row['quantity']), _money(row['revenue'])])
    if len(rows) == 1:
        rows.append(['No sales recorded this month', '', '', ''])
    story.append(_table(rows, [width * 0.46, width * 0.18, width * 0.16, width * 0.2], align_from=2))
    story.append(Spacer(1, 6))
    rows = [['Least selling', 'Business', 'Units sold', 'In stock']]
    for row in report['least_sellers']:
        rows.append([row['item'][:38], row['unit'], str(row['quantity']), str(row['in_stock'])])
    if len(rows) == 1:
        rows.append(['No stock items recorded', '', '', ''])
    story.append(_table(rows, [width * 0.46, width * 0.18, width * 0.16, width * 0.2], align_from=2))
    if report['unsold_count']:
        story.append(Paragraph(f"{report['unsold_count']} item(s) in stock sold nothing this month.", note))

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    buffer.seek(0)
    return buffer
