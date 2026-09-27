"""
Per-exam-session seat allocation.

Fills each hall selected for this exam up to its `capacity_allocated`
quota (never the hall's full physical capacity — that's shared with
whatever else is using the room), in contiguous roll-number blocks.
Students who'd conflict with another exam at an overlapping time are
skipped and reported rather than silently seated somewhere wrong.
"""

from django.db import transaction

from .models import ExamStudentAssignment
from .validators import ValidationError, check_student_conflict


class AllocationError(Exception):
    """Raised when this exam session can't be auto-assigned at all right
    now (no halls, or nobody left to seat)."""


def _seat_label(position, seats_per_row):
    row_index = position // seats_per_row
    seat_number = position % seats_per_row + 1
    row_label = chr(65 + row_index) if row_index < 26 else chr(65 + row_index // 26 - 1) + chr(65 + row_index % 26)
    return row_label, seat_number


@transaction.atomic
def auto_assign_exam_session(exam_session):
    """Assign every unassigned roster student (for this session) to one of
    the halls selected for this exam, filling each to its allocated quota
    in contiguous roll-number blocks.

    Returns a summary dict. Raises AllocationError (writing nothing) if
    there are no halls selected or no students waiting.
    """
    exam_halls = list(exam_session.exam_halls.select_related('hall').order_by('hall__name'))
    if not exam_halls:
        raise AllocationError("No halls have been selected for this exam yet — add halls before assigning.")

    students = list(exam_session.unassigned_students.order_by('roll_number'))
    if not students:
        raise AllocationError("Every active roster student already has a hall assignment for this exam.")

    total_quota = sum(eh.capacity_allocated for eh in exam_halls)

    summaries = []
    skipped_conflicts = []
    cursor = 0
    for exam_hall in exam_halls:
        remaining_quota = exam_hall.capacity_allocated
        seated_here = 0

        while remaining_quota > 0 and cursor < len(students):
            student = students[cursor]
            cursor += 1
            try:
                check_student_conflict(student.roll_number, exam_session)
            except ValidationError:
                skipped_conflicts.append(student.roll_number)
                continue

            row_label, seat_number = _seat_label(seated_here, exam_hall.hall.seats_per_row)
            ExamStudentAssignment.objects.create(
                exam_session=exam_session,
                student=student,
                hall=exam_hall.hall,
                row=row_label,
                seat=str(seat_number),
            )
            seated_here += 1
            remaining_quota -= 1

        summaries.append({'hall': exam_hall.hall.name, 'assigned': seated_here})

    total_assigned = sum(s['assigned'] for s in summaries)
    if total_assigned == 0 and not skipped_conflicts:
        raise AllocationError(
            f"Nothing was assigned — the selected halls only have {total_quota} seat(s) "
            f"reserved for this exam in total, and something else is blocking allocation."
        )

    return {
        'total_assigned': total_assigned,
        'halls': summaries,
        'skipped_conflicts': skipped_conflicts,
        'leftover_unassigned': len(students) - cursor,
    }
