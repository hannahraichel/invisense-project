
"""
Printable hall ticket — one per student, one page, one permanent QR, and a
table of every exam in the period with that student's assigned section
for each one. Only generated for students whose seating is complete for
every exam session in their period (see Student.is_hall_ticket_ready) —
callers are expected to have already filtered on that.
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

    pdf.drawString(
        x,
        block_top - 18,
        f"Roll No.   {student.roll_number}"
    )

    # Keep the fallback value outside the f-string expression.
    program = student.course or "—"
    pdf.drawString(
        x,
        block_top - 34,
        f"Program    {program}"
    )

    # QR code
    qr_size = 34 * mm
    qr_x = page_width - MARGIN - qr_size
    qr_y = block_top - qr_size + 14

    try:
        student.hall_ticket.qr_code.open('rb')
        img = ImageReader(student.hall_ticket.qr_code)
        pdf.drawImage(
            img,
            qr_x,
            qr_y,
            width=qr_size,
            height=qr_size
        )
    finally:
        student.hall_ticket.qr_code.close()

    pdf.setStrokeColor(colors.HexColor('#e6e2d5'))
    pdf.rect(qr_x, qr_y, qr_size, qr_size)

    pdf.setFont('Helvetica-Oblique', 7.5)
    pdf.setFillColor(colors.HexColor('#9a9686'))
    pdf.drawCentredString(
        qr_x + qr_size / 2,
        qr_y - 12,
        'Same QR — every exam'
    )

    pdf.setStrokeColor(colors.HexColor('#e6e2d5'))
    pdf.line(
        x,
        block_top - 50,
        page_width - MARGIN,
        block_top - 50
    )

    # Schedule table
    table_top = block_top - 72

    pdf.setFont('Helvetica-Bold', 8.5)
    pdf.setFillColor(colors.HexColor('#6b6858'))

    col_date = x
    col_subject = x + 75
    col_time = x + 220
    col_hall = x + 340

    pdf.drawString(col_date, table_top, 'DATE')
    pdf.drawString(col_subject, table_top, 'SUBJECT')
    pdf.drawString(col_time, table_top, 'TIME')
    pdf.drawString(col_hall, table_top, 'SECTION')

    pdf.setLineWidth(0.5)
    pdf.line(
        x,
        table_top - 6,
        page_width - MARGIN,
        table_top - 6
    )

    row_y = table_top - 24

    pdf.setFont('Helvetica', 10)

    for assignment in assignments:
        session = assignment.exam_session

        pdf.setFillColor(colors.HexColor('#1c1b17'))

        pdf.drawString(
            col_date,
            row_y,
            session.exam_date.strftime('%d %b %Y')
        )

        pdf.drawString(
            col_subject,
            row_y,
            session.subject
        )

        pdf.setFillColor(colors.HexColor('#55534c'))

        start_time = session.start_time.strftime('%I:%M %p')
        end_time = session.end_time.strftime('%I:%M %p')
        time_range = f"{start_time}–{end_time}"

        pdf.drawString(
            col_time,
            row_y,
            time_range
        )

        pdf.setFillColor(colors.HexColor('#1c1b17'))

        section_text = (
            f"{assignment.hall.name}  "
            f"(Row {assignment.row}, Seat {assignment.seat})"
        )

        pdf.drawString(
            col_hall,
            row_y,
            section_text
        )

        row_y -= 20

        pdf.setStrokeColor(colors.HexColor('#f0eee7'))
        pdf.line(
            x,
            row_y + 8,
            page_width - MARGIN,
            row_y + 8
        )

        if row_y < MARGIN + 40:
            pdf.showPage()
            row_y = page_height - MARGIN - 20

    # Footer
    pdf.setFont('Helvetica-Oblique', 8)
    pdf.setFillColor(colors.HexColor('#9a9686'))

    pdf.drawString(
        x,
        MARGIN,
        "Bring this ticket and a valid ID to every exam. "
        "Report 30 minutes before each session."
    )


def generate_hall_tickets_pdf(students, exam_period):
    """
    students: iterable of Student instances that are already confirmed
    ticket-ready (see Student.is_hall_ticket_ready).

    One ticket per student, each on its own page(s).
    """
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    students = list(students)

    for student in students:
        assignments = (
            student.assignments
            .select_related('exam_session', 'hall')
            .exclude(
                exam_session__status__in=['CANCELLED', 'STOPPED']
            )
            .order_by(
                'exam_session__exam_date',
                'exam_session__start_time'
            )
        )

        _draw_ticket(
            pdf,
            student,
            exam_period,
            assignments
        )

        pdf.showPage()

    pdf.save()

    buffer.seek(0)

    return buffer

