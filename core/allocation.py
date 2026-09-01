"""
Seat allocation for InviSense.

Given a roster of students (no hall/row/seat set yet) and a set of halls
with a fixed capacity each, this assigns every student a hall + row + seat
such that:

  1. No hall receives more students than its capacity.
  2. Adjacent seats (in fill order) alternate between subject/department
     codes wherever possible — the standard "zig-zag" anti-copying seating
     pattern used in real exam halls, so two students sitting next to each
     other are unlikely to be writing the same paper.

This is intentionally a simple, explainable round-robin interleave rather
than a full 2D grid optimiser (which would need real seat-grid geometry per
room) — it gives a materially better result than sequential seating with a
few lines of code, without pretending to model physical room layouts we
don't have.
"""

from collections import defaultdict

from django.db import transaction

from .models import Student


class AllocationError(Exception):
    """Raised when the current roster/halls can't be allocated as requested."""


def _interleave_by_subject(students):
    """Round-robin merge students grouped by subject_code, roll-number order
    within each group, so consecutive students differ in subject as often
    as possible."""
    groups = defaultdict(list)
    for student in students:
        groups[student.subject_code].append(student)

    for group in groups.values():
        group.sort(key=lambda s: s.roll_number)

    ordered_groups = sorted(groups.values(), key=len, reverse=True)
    interleaved = []
    index = 0
    while any(index < len(g) for g in ordered_groups):
        for group in ordered_groups:
            if index < len(group):
                interleaved.append(group[index])
        index += 1
    return interleaved


def _seat_label(position, seats_per_row):
    """0-based position -> ('A', 1), ('A', 2) ... ('B', 1) ..."""
    row_index = position // seats_per_row
    seat_number = position % seats_per_row + 1
    if row_index < 26:
        row_label = chr(65 + row_index)
    else:
        # Beyond Z, fall back to AA, AB, ... for very large halls.
        row_label = chr(65 + row_index // 26 - 1) + chr(65 + row_index % 26)
    return row_label, seat_number


@transaction.atomic
def auto_allocate_session(session):
    """Allocate every unseated student in `session` to a hall/row/seat.

    Returns a summary dict. Raises AllocationError if there isn't enough
    capacity or no halls exist — nothing is written in that case.
    """
    halls = list(session.halls.order_by('hall_number'))
    if not halls:
        raise AllocationError("This session has no halls yet — add halls before allocating seats.")

    unseated = list(
        Student.objects.filter(session=session, hall__isnull=True).order_by('roll_number')
    )
    if not unseated:
        raise AllocationError("There are no unseated students in this session to allocate.")

    total_capacity = sum(h.capacity for h in halls)
    if len(unseated) > total_capacity:
        raise AllocationError(
            f"Not enough seats: {len(unseated)} student(s) waiting but only "
            f"{total_capacity} seat(s) across {len(halls)} hall(s). "
            f"Add more halls or increase capacity, then try again."
        )

    ordered_students = _interleave_by_subject(unseated)

    hall_summaries = []
    cursor = 0
    for hall in halls:
        take = min(hall.capacity, len(ordered_students) - cursor)
        if take <= 0:
            hall_summaries.append({'hall': hall.hall_number, 'seated': 0})
            continue

        chunk = ordered_students[cursor:cursor + take]
        for position, student in enumerate(chunk):
            row_label, seat_number = _seat_label(position, hall.seats_per_row)
            student.hall = hall
            student.row = row_label
            student.seat = str(seat_number)
            student.save()

        hall_summaries.append({'hall': hall.hall_number, 'seated': len(chunk)})
        cursor += take

    return {
        'total_allocated': cursor,
        'halls': hall_summaries,
    }
