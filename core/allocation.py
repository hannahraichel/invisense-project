"""
Per-exam-session seat allocation.

Unlike a one-off seating chart, this runs once per ExamSession: given the
halls selected for that specific exam (ExamHall rows) and the roster
students who don't yet have an ExamStudentAssignment for this session, it
splits them into contiguous, evenly-sized blocks in roll-number order —
e.g. 61 students across 2 halls -> 31 in the first hall, 30 in the second.
This is deterministic and transparent (register-number order), matching
how HODs actually assign halls on a real timetable.
"""

from django.db import transaction

from .models import ExamStudentAssignment


class AllocationError(Exception):
    """Raised when this exam session can't be auto-assigned right now."""


def _seat_label(position, seats_per_row):
    row_index = position // seats_per_row
    seat_number = position % seats_per_row + 1
    row_label = chr(65 + row_index) if row_index < 26 else chr(65 + row_index // 26 - 1) + chr(65 + row_index % 26)
    return row_label, seat_number


@transaction.atomic
def auto_assign_exam_session(exam_session):
    """Assign every unassigned roster student (for this session) to one of
    the halls selected for this exam, in contiguous roll-number blocks.

    Returns a summary dict. Raises AllocationError (writing nothing) if
    there are no halls selected or no students waiting.
    """
    exam_halls = list(exam_session.exam_halls.select_related('hall').order_by('hall__hall_number'))
    if not exam_halls:
        raise AllocationError("No halls have been selected for this exam yet — add halls before assigning.")

    students = list(exam_session.unassigned_students.order_by('roll_number'))
    if not students:
        raise AllocationError("Every roster student already has a hall assignment for this exam.")

    n_halls = len(exam_halls)
    total = len(students)
    base, remainder = divmod(total, n_halls)

    summaries = []
    cursor = 0
    for i, exam_hall in enumerate(exam_halls):
        take = base + (1 if i < remainder else 0)
        chunk = students[cursor:cursor + take]

        for position, student in enumerate(chunk):
            row_label, seat_number = _seat_label(position, exam_hall.hall.seats_per_row)
            ExamStudentAssignment.objects.create(
                exam_session=exam_session,
                student=student,
                hall=exam_hall.hall,
                row=row_label,
                seat=str(seat_number),
            )

        summaries.append({'hall': exam_hall.hall.hall_number, 'assigned': len(chunk)})
        cursor += take

    return {'total_assigned': cursor, 'halls': summaries}
