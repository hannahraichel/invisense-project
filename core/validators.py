"""
Validation rules that must hold no matter which screen (or which
concurrent admin) is writing data. Anything that touches capacity uses
select_for_update() so two admins racing to fill the same hall can never
push it over capacity — the second write always re-checks against the
first one's committed state, not a stale read.
"""

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone


class ValidationError(Exception):
    """A rule in this module was violated. `field` is optional, for
    attaching the error to a specific form field in the view."""

    def __init__(self, message, field=None, row=None):
        super().__init__(message)
        self.message = message
        self.field = field
        self.row = row  # 1-based row number, for CSV batch validation


# ---------------------------------------------------------------------------
# Expired-date validation (timetable upload / edit)
# ---------------------------------------------------------------------------

def check_not_expired(exam_date, end_time, now=None):
    """Raise if the exam's end time is already in the past. Uses the app's
    configured timezone consistently (see settings.TIME_ZONE), never the
    browser's."""
    now = now or timezone.localtime()
    exam_end = timezone.make_aware(
        timezone.datetime.combine(exam_date, end_time), timezone.get_current_timezone()
    )
    if exam_end < now:
        raise ValidationError(
            f"Cannot create/update this exam session — {exam_date} at "
            f"{end_time.strftime('%H:%M')} has already passed."
        )


# ---------------------------------------------------------------------------
# Time-overlap helper
# ---------------------------------------------------------------------------

def _times_overlap(date_a, start_a, end_a, date_b, start_b, end_b):
    if date_a != date_b:
        return False
    return start_a < end_b and start_b < end_a


# ---------------------------------------------------------------------------
# Hall capacity validation (global, cross-period, concurrency-safe)
# ---------------------------------------------------------------------------

def check_hall_capacity(hall, exam_session, requested_seats, exclude_exam_hall_id=None):
    """Sum every OTHER ExamHall allocation on this hall whose exam session
    overlaps this one in time (any period), lock the hall row so a
    concurrent request can't read stale totals, and make sure adding
    `requested_seats` doesn't exceed the room's real capacity.

    Must be called inside a transaction.atomic() block.
    """
    from .models import ExamHall  # local import avoids a circular import at module load

    # Lock the hall row itself — every writer contending for this hall's
    # capacity serializes here, so two concurrent admins can't both read
    # "12 used" and both add more than the last seat allows.
    hall.__class__.objects.select_for_update().get(pk=hall.pk)

    overlapping = ExamHall.objects.filter(hall=hall).select_related('exam_session')
    if exclude_exam_hall_id:
        overlapping = overlapping.exclude(id=exclude_exam_hall_id)

    already_allocated = 0
    for eh in overlapping:
        if _times_overlap(
            exam_session.exam_date, exam_session.start_time, exam_session.end_time,
            eh.exam_session.exam_date, eh.exam_session.start_time, eh.exam_session.end_time,
        ):
            already_allocated += eh.capacity_allocated

    total = already_allocated + requested_seats
    if total > hall.capacity:
        raise ValidationError(
            f"Section capacity exceeded. {hall.name} has capacity for only "
            f"{hall.capacity} students ({already_allocated} already allocated "
            f"for this time slot, {requested_seats} requested)."
        )


# ---------------------------------------------------------------------------
# Invigilator conflict validation (global, cross-period)
# ---------------------------------------------------------------------------

def check_invigilator_conflict(user, exam_session, exclude_exam_hall_id=None):
    """An invigilator can't be assigned to two overlapping exam halls —
    across any exam period, not just the one currently open."""
    from .models import ExamHall

    if user is None:
        return

    existing = ExamHall.objects.filter(invigilator=user).select_related('exam_session', 'hall')
    if exclude_exam_hall_id:
        existing = existing.exclude(id=exclude_exam_hall_id)

    for eh in existing:
        if eh.exam_session_id == exam_session.id:
            continue
        if _times_overlap(
            exam_session.exam_date, exam_session.start_time, exam_session.end_time,
            eh.exam_session.exam_date, eh.exam_session.start_time, eh.exam_session.end_time,
        ):
            raise ValidationError(
                f"{user.username} is already invigilating {eh.hall.name} for "
                f"{eh.exam_session.subject} at an overlapping time."
            )


# ---------------------------------------------------------------------------
# Student conflict validation (global, cross-period, by roll number)
# ---------------------------------------------------------------------------

def check_student_conflict(roll_number, exam_session, exclude_assignment_id=None):
    """The same student (matched by roll number, since a person could in
    principle appear on more than one period's roster) can't be seated for
    two overlapping exams."""
    from .models import ExamStudentAssignment

    existing = ExamStudentAssignment.objects.filter(
        student__roll_number=roll_number
    ).select_related('exam_session', 'student')
    if exclude_assignment_id:
        existing = existing.exclude(id=exclude_assignment_id)

    for a in existing:
        if a.exam_session_id == exam_session.id:
            continue
        if _times_overlap(
            exam_session.exam_date, exam_session.start_time, exam_session.end_time,
            a.exam_session.exam_date, a.exam_session.start_time, a.exam_session.end_time,
        ):
            raise ValidationError(
                f"{roll_number} already has an overlapping exam ({a.exam_session.subject} "
                f"on {a.exam_session.exam_date})."
            )


# ---------------------------------------------------------------------------
# Dependency-aware delete guard
# ---------------------------------------------------------------------------

def guard_delete(entity, label=None):
    """Raise if `entity` has operational/historical dependencies that make
    a hard delete unsafe. Callers should catch this and suggest Stop
    instead."""
    if getattr(entity, 'has_dependencies', False):
        name = label or type(entity).__name__
        raise ValidationError(
            f"Can't delete this {name} — it already has exam history attached. "
            f"Use Stop/Deactivate instead to preserve records."
        )
