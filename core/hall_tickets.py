"""
Printable hall-ticket (admit card) generation.

Produces a single PDF containing one ticket per seated student: name, roll
number, subject, hall/row/seat, and their QR code, laid out two-up on each
A4 page so a batch prints cleanly on ordinary paper.
"""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

TICKET_HEIGHT = 130 * mm
MARGIN = 12 * mm


def _draw_ticket(pdf, x, y, width, height, student, session):
    pdf.setStrokeColor(colors.HexColor('#cfcabb'))
    pdf.setLineWidth(0.75)
    pdf.rect(x, y, width, height)

    pad = 8 * mm
    text_x = x + pad
    top = y + height - pad

    pdf.setFillColor(colors.HexColor('#a8452b'))
    pdf.setFont('Helvetica-Bold', 8)
    pdf.drawString(text_x, top, 'INVISENSE — EXAMINATION HALL TICKET')

    pdf.setFillColor(colors.HexColor('#1c1b17'))
    pdf.setFont('Helvetica-Bold', 15)
    pdf.drawString(text_x, top - 9 * mm, student.name or student.roll_number)

    pdf.setFont('Helvetica', 9.5)
    pdf.setFillColor(colors.HexColor('#55534c'))
    pdf.drawString(text_x, top - 15 * mm, f"Roll No.  {student.roll_number}")
    pdf.drawString(text_x, top - 20 * mm, f"Subject   {student.subject_code}")
    time_label = student.exam_time.strip() if student.exam_time else session.shift
    pdf.drawString(text_x, top - 25 * mm, f"Date       {session.date}  ·  {time_label}")

    pdf.setLineWidth(0.5)
    pdf.setStrokeColor(colors.HexColor('#e6e2d5'))
    pdf.line(text_x, top - 30 * mm, x + width - pad, top - 30 * mm)

    pdf.setFont('Helvetica-Bold', 22)
    pdf.setFillColor(colors.HexColor('#1c1b17'))
    pdf.drawString(text_x, top - 42 * mm, f"Hall {student.hall.hall_number}")

    pdf.setFont('Helvetica', 11)
    pdf.setFillColor(colors.HexColor('#55534c'))
    pdf.drawString(text_x, top - 49 * mm, f"Row {student.row}   ·   Seat {student.seat}")

    pdf.setFont('Helvetica-Oblique', 7.5)
    pdf.setFillColor(colors.HexColor('#9a9686'))
    pdf.drawString(text_x, y + pad, "Bring this ticket and a valid ID. Report 30 minutes before the shift.")

    # QR code, right-aligned within the ticket
    qr_size = 32 * mm
    qr_x = x + width - pad - qr_size
    qr_y = y + height - pad - qr_size
    if student.qr_code:
        try:
            student.qr_code.open('rb')
            img = ImageReader(student.qr_code)
            pdf.drawImage(img, qr_x, qr_y, width=qr_size, height=qr_size)
        finally:
            student.qr_code.close()
        pdf.setStrokeColor(colors.HexColor('#e6e2d5'))
        pdf.rect(qr_x, qr_y, qr_size, qr_size)


def generate_hall_tickets_pdf(students, session):
    """students: iterable of seated Student instances (hall/row/seat set).
    Returns a BytesIO containing the finished PDF."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4
    ticket_width = page_width - 2 * MARGIN

    students = list(students)
    for i, student in enumerate(students):
        slot = i % 2
        if slot == 0 and i != 0:
            pdf.showPage()

        if slot == 0:
            y = page_height - MARGIN - TICKET_HEIGHT
        else:
            y = MARGIN

        _draw_ticket(pdf, MARGIN, y, ticket_width, TICKET_HEIGHT, student, session)

    pdf.save()
    buffer.seek(0)
    return buffer
