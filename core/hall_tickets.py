"""
Printable hall ticket — one per student, one page, one permanent QR, and a
table of every exam in the period with that student's assigned hall for
each one. This is what the student carries for the whole exam period, not
per exam.
"""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

MARGIN = 18 * mm


def _draw_ticket(pdf, student, exam_period, assignments):
    page_width, page_height = A4
    x = MARGIN
    top = page_height - MARGIN

    pdf.setFillColor(colors.HexColor('#a8452b'))
    pdf.setFont('Helvetica-Bold', 10)
    pdf.drawString(x, top, 'INVISENSE — EXAMINATION HALL TICKET')
    pdf.setFont('Helvetica', 9)
    pdf.setFillColor(colors.HexColor('#6b6858'))
    pdf.drawRightString(page_width - MARGIN, top, exam_period.name)

    pdf.setStrokeColor(colors.HexColor('#cfcabb'))
    pdf.setLineWidth(0.75)
    pdf.line(x, top - 8, page_width - MARGIN, top - 8)

    # Student block (left) + QR (right)
    block_top = top - 30
    pdf.setFillColor(colors.HexColor('#1c1b17'))
    pdf.setFont('Helvetica-Bold', 20)
    pdf.drawString(x, block_top, student.name or student.roll_number)

    pdf.setFont('Helvetica', 11)
    pdf.setFillColor(colors.HexColor('#55534c'))
    pdf.drawString(x, block_top - 18, f"Roll No.   {student.roll_number}")
    pdf.drawString(x, block_top - 34, f"Course     {student.course or '—'}")

    qr_size = 34 * mm
    qr_x = page_width - MARGIN - qr_size
    qr_y = block_top - qr_size + 14
    try:
        student.hall_ticket.qr_code.open('rb')
        img = ImageReader(student.hall_ticket.qr_code)
        pdf.drawImage(img, qr_x, qr_y, width=qr_size, height=qr_size)
    finally:
        student.hall_ticket.qr_code.close()
    pdf.setStrokeColor(colors.HexColor('#e6e2d5'))
    pdf.rect(qr_x, qr_y, qr_size, qr_size)
    pdf.setFont('Helvetica-Oblique', 7.5)
    pdf.setFillColor(colors.HexColor('#9a9686'))
    pdf.drawCentredString(qr_x + qr_size / 2, qr_y - 12, 'Same QR — every exam')

    pdf.setStrokeColor(colors.HexColor('#e6e2d5'))
    pdf.line(x, block_top - 50, page_width - MARGIN, block_top - 50)

    # Schedule table
    table_top = block_top - 72
    pdf.setFont('Helvetica-Bold', 8.5)
    pdf.setFillColor(colors.HexColor('#6b6858'))
    col_date, col_subject, col_time, col_hall = x, x + 75, x + 220, x + 340
    pdf.drawString(col_date, table_top, 'DATE')
    pdf.drawString(col_subject, table_top, 'SUBJECT')
    pdf.drawString(col_time, table_top, 'TIME')
    pdf.drawString(col_hall, table_top, 'HALL')

    pdf.setLineWidth(0.5)
    pdf.line(x, table_top - 6, page_width - MARGIN, table_top - 6)

    row_y = table_top - 24
    pdf.setFont('Helvetica', 10)
    for assignment in assignments:
        session = assignment.exam_session
        pdf.setFillColor(colors.HexColor('#1c1b17'))
        pdf.drawString(col_date, row_y, session.exam_date.strftime('%d %b %Y'))
        pdf.drawString(col_subject, row_y, session.subject)
        pdf.setFillColor(colors.HexColor('#55534c'))
        pdf.drawString(col_time, row_y, f"{session.start_time.strftime('%I:%M %p')}\u2013{session.end_time.strftime('%I:%M %p')}")
        pdf.setFillColor(colors.HexColor('#1c1b17'))
        pdf.drawString(col_hall, row_y, f"Hall {assignment.hall.hall_number}  (Row {assignment.row}, Seat {assignment.seat})")

        row_y -= 20
        pdf.setStrokeColor(colors.HexColor('#f0eee7'))
        pdf.line(x, row_y + 8, page_width - MARGIN, row_y + 8)

        if row_y < MARGIN + 40:
            pdf.showPage()
            row_y = page_height - MARGIN - 20

    pdf.setFont('Helvetica-Oblique', 8)
    pdf.setFillColor(colors.HexColor('#9a9686'))
    pdf.drawString(x, MARGIN, "Bring this ticket and a valid ID to every exam. Report 30 minutes before each session.")


def generate_hall_tickets_pdf(students, exam_period):
    """students: iterable of Student instances (each needs hall_ticket set
    and .assignments prefetched/queryable). One ticket per student, each on
    its own page(s)."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    students = list(students)
    for i, student in enumerate(students):
        assignments = student.assignments.select_related('exam_session', 'hall').order_by(
            'exam_session__exam_date', 'exam_session__start_time'
        )
        _draw_ticket(pdf, student, exam_period, assignments)
        pdf.showPage()

    pdf.save()
    buffer.seek(0)
    return buffer
