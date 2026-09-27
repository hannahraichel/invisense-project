import csv
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.cache import add_never_cache_headers
from django.utils.dateparse import parse_date, parse_time

from .allocation import AllocationError, auto_assign_exam_session
from .hall_tickets import generate_hall_tickets_pdf
from .models import (
    Alert, Attendance, AuditLog, ExamHall, ExamPeriod, ExamSession,
    ExamStudentAssignment, Hall, HallTicket, Student, User,
)
from .validators import (
    ValidationError, check_hall_capacity, check_invigilator_conflict,
    check_not_expired, guard_delete,
)

# ---------------------------------------------------------------------------
# Access-control helpers
# ---------------------------------------------------------------------------

def role_required(*roles):
    """Decorator that redirects home if the logged-in user lacks one of `roles`."""
    def decorator(view_func):
        def wrapped(request, *args, **kwargs):
            if request.user.role not in roles:
                messages.error(request, "You don't have access to that page.")
                return redirect('home')
            return view_func(request, *args, **kwargs)
        wrapped.__name__ = view_func.__name__
        return wrapped
    return decorator


def get_current_invigilator_context(user):
    """The ExamHall (exam session + hall) this invigilator is currently
    running, determined purely from the clock — not from anything the
    client sends. Scanning opens 3 hours before the exam's start time."""
    now = timezone.localtime()
    candidates = ExamHall.objects.filter(
        invigilator=user,
        exam_session__exam_date__in=[
            now.date() - timezone.timedelta(days=1),
            now.date(),
            now.date() + timezone.timedelta(days=1),
        ],
        exam_session__status__in=ExamSession.LIVE_STATUSES,
    ).select_related('exam_session', 'hall')
    for eh in candidates:
        if eh.exam_session.is_currently_active(now):
            return eh
    return None


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def home_redirect(request):
    if not request.user.is_authenticated:
        return redirect('login')
    if request.user.role == User.ROLE_ADMIN:
        return redirect('admin_dashboard')
    elif request.user.role == User.ROLE_INVIGILATOR:
        return redirect('invigilator_dashboard')
    elif request.user.role == User.ROLE_CONTROL_ROOM:
        return redirect('control_room')
    return redirect('login')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        u = request.POST.get('username', '').strip()
        p = request.POST.get('password', '')
        user = authenticate(request, username=u, password=p)
        if user is not None:
            if not user.is_active:
                messages.error(request, 'This account is deactivated. Please contact an administrator.')
                return render(request, 'login.html')
            login(request, user)
            request.session.cycle_key()
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url and next_url.startswith('/') and not next_url.startswith('//'):
                return redirect(next_url)
            return redirect('home')
        messages.error(request, 'Invalid username or password.')
    return render(request, 'login.html')


def logout_view(request):
    """
    Complete logout: invalidates session, removes session cookies,
    and returns a response with never-cache headers so browser history/Back
    cannot expose authenticated pages.
    """
    logout(request)
    if hasattr(request, 'session'):
        request.session.flush()
    response = redirect('login')
    add_never_cache_headers(response)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, private, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response.delete_cookie(settings.SESSION_COOKIE_NAME)
    return response


# ---------------------------------------------------------------------------
# Admin — exam periods
# ---------------------------------------------------------------------------

@login_required
@role_required(User.ROLE_ADMIN)
def admin_dashboard(request):
    periods = ExamPeriod.objects.all()
    stats = {
        'active_periods': periods.filter(status=ExamPeriod.STATUS_ACTIVE).count(),
        'total_students': Student.objects.filter(is_active=True).count(),
        'pending_alerts': Alert.objects.filter(status=Alert.STATUS_PENDING).count(),
        'total_invigilators': User.objects.filter(role=User.ROLE_INVIGILATOR).count(),
    }
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Please give the exam period a name.')
        else:
            period = ExamPeriod.objects.create(name=name)
            AuditLog.record(request.user, 'created', period)
            messages.success(request, f'"{name}" created.')
            return redirect('period_detail', period_id=period.id)

    return render(request, 'admin/dashboard.html', {'periods': periods, 'stats': stats})


@login_required
@role_required(User.ROLE_ADMIN)
def period_detail(request, period_id):
    period = get_object_or_404(ExamPeriod, id=period_id)
    exam_sessions = period.exam_sessions.all()
    students = period.students.all()
    active_students = students.filter(is_active=True)
    ready_count = sum(1 for s in active_students if s.is_hall_ticket_ready)

    return render(request, 'admin/period_detail.html', {
        'period': period,
        'exam_sessions': exam_sessions,
        'students': students,
        'student_count': active_students.count(),
        'ready_count': ready_count,
    })


@login_required
@role_required(User.ROLE_ADMIN)
def edit_period(request, period_id):
    period = get_object_or_404(ExamPeriod, id=period_id)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Name cannot be empty.')
        else:
            period.name = name
            period.save(update_fields=['name'])
            AuditLog.record(request.user, 'edited', period)
            messages.success(request, 'Exam period updated.')
    return redirect('period_detail', period_id=period.id)


@login_required
@role_required(User.ROLE_ADMIN)
def stop_period(request, period_id):
    period = get_object_or_404(ExamPeriod, id=period_id)
    if request.method == 'POST':
        period.status = ExamPeriod.STATUS_ACTIVE if period.status == ExamPeriod.STATUS_STOPPED else ExamPeriod.STATUS_STOPPED
        period.save(update_fields=['status'])
        AuditLog.record(request.user, 'stopped' if not period.is_active else 'reactivated', period)
        messages.success(request, f'Exam period {"stopped" if not period.is_active else "reactivated"}.')
    return redirect('period_detail', period_id=period.id)


@login_required
@role_required(User.ROLE_ADMIN)
def delete_period(request, period_id):
    period = get_object_or_404(ExamPeriod, id=period_id)
    if request.method == 'POST':
        try:
            guard_delete(period, 'exam period')
        except ValidationError as exc:
            messages.error(request, str(exc))
            return redirect('period_detail', period_id=period.id)
        name = period.name
        AuditLog.record(request.user, 'deleted', period)
        period.delete()
        messages.success(request, f'"{name}" deleted.')
        return redirect('admin_dashboard')
    return redirect('period_detail', period_id=period.id)


@login_required
@role_required(User.ROLE_ADMIN)
def upload_roster(request, period_id):
    period = get_object_or_404(ExamPeriod, id=period_id)

    if request.method == 'POST':
        csv_file = request.FILES.get('roster_file')
        if not csv_file or not csv_file.name.lower().endswith('.csv'):
            messages.error(request, 'Please upload a valid CSV file.')
            return redirect('upload_roster', period_id=period.id)

        try:
            file_data = csv_file.read().decode('utf-8-sig').splitlines()
        except UnicodeDecodeError:
            messages.error(request, 'Could not read file. Please save the CSV as UTF-8 and try again.')
            return redirect('upload_roster', period_id=period.id)

        reader = csv.DictReader(file_data)
        columns = {c.strip() for c in (reader.fieldnames or [])}
        if 'roll_number' not in columns:
            messages.error(request, 'CSV is missing the required column: roll_number.')
            return redirect('upload_roster', period_id=period.id)

        created, skipped_duplicate, skipped_incomplete = 0, 0, 0
        for row in reader:
            roll_number = (row.get('roll_number') or '').strip()
            if not roll_number:
                skipped_incomplete += 1
                continue
            if Student.objects.filter(exam_period=period, roll_number=roll_number).exists():
                skipped_duplicate += 1
                continue

            student = Student.objects.create(
                exam_period=period,
                roll_number=roll_number,
                name=(row.get('name') or '').strip(),
                course=(row.get('course') or '').strip(),
            )
            HallTicket.objects.create(student=student)
            created += 1

        summary = f'Imported {created} student(s) and issued their permanent hall-ticket QR.'
        extras = []
        if skipped_duplicate:
            extras.append(f'{skipped_duplicate} skipped (already on this roster)')
        if skipped_incomplete:
            extras.append(f'{skipped_incomplete} skipped (missing roll number)')
        if extras:
            summary += ' — ' + ', '.join(extras) + '.'
        messages.success(request, summary)
        return redirect('period_detail', period_id=period.id)

    return render(request, 'admin/upload_roster.html', {'period': period})


@login_required
@role_required(User.ROLE_ADMIN)
def upload_timetable(request, period_id):
    period = get_object_or_404(ExamPeriod, id=period_id)

    if request.method == 'POST':
        csv_file = request.FILES.get('timetable_file')
        if not csv_file or not csv_file.name.lower().endswith('.csv'):
            messages.error(request, 'Please upload a valid CSV file.')
            return redirect('upload_timetable', period_id=period.id)

        try:
            file_data = csv_file.read().decode('utf-8-sig').splitlines()
        except UnicodeDecodeError:
            messages.error(request, 'Could not read file. Please save the CSV as UTF-8 and try again.')
            return redirect('upload_timetable', period_id=period.id)

        reader = csv.DictReader(file_data)
        columns = {c.strip() for c in (reader.fieldnames or [])}
        required = {'subject', 'exam_date', 'start_time', 'end_time'}
        if not required.issubset(columns):
            messages.error(request, 'CSV needs at least: subject, exam_date, start_time, end_time.')
            return redirect('upload_timetable', period_id=period.id)

        results = []  # [(row_number, subject, 'created'/'rejected', reason)]
        for row_number, row in enumerate(reader, start=2):  # header is row 1
            subject = (row.get('subject') or '').strip()
            exam_date = parse_date((row.get('exam_date') or '').strip())
            start_time = parse_time((row.get('start_time') or '').strip())
            end_time = parse_time((row.get('end_time') or '').strip())

            if not subject or not exam_date or not start_time or not end_time:
                results.append((row_number, subject or '(blank)', 'rejected',
                                 'Missing or unparseable subject/date/time (need YYYY-MM-DD and HH:MM).'))
                continue

            if ExamSession.objects.filter(
                exam_period=period, subject=subject, exam_date=exam_date, start_time=start_time
            ).exists():
                results.append((row_number, subject, 'rejected', 'Already exists.'))
                continue

            try:
                check_not_expired(exam_date, end_time)
            except ValidationError as exc:
                results.append((row_number, subject, 'rejected', exc.message))
                continue

            ExamSession.objects.create(
                exam_period=period, subject=subject, exam_date=exam_date,
                start_time=start_time, end_time=end_time,
            )
            results.append((row_number, subject, 'created', ''))

        created_count = sum(1 for r in results if r[2] == 'created')
        rejected = [r for r in results if r[2] == 'rejected']
        request.session['timetable_upload_report'] = results
        messages.success(
            request,
            f'{created_count} exam session(s) created' + (f', {len(rejected)} rejected — see report below.' if rejected else '.')
        )
        return redirect('upload_timetable', period_id=period.id)

    report = request.session.pop('timetable_upload_report', None)
    return render(request, 'admin/upload_timetable.html', {'period': period, 'report': report})


@login_required
@role_required(User.ROLE_ADMIN)
def download_hall_tickets(request, period_id):
    period = get_object_or_404(ExamPeriod, id=period_id)
    ready_students = [s for s in period.students.filter(is_active=True) if s.is_hall_ticket_ready]
    if not ready_students:
        messages.error(
            request,
            'No student has a complete seating allocation yet — every exam session in this '
            'period needs a confirmed hall assignment before their hall ticket unlocks.'
        )
        return redirect('period_detail', period_id=period.id)

    buffer = generate_hall_tickets_pdf(ready_students, period)
    filename = f'hall_tickets_{period.name}.pdf'.replace(' ', '_')
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ---------------------------------------------------------------------------
# Admin — student roster management
# ---------------------------------------------------------------------------

@login_required
@role_required(User.ROLE_ADMIN)
def add_student(request, period_id):
    period = get_object_or_404(ExamPeriod, id=period_id)
    if request.method == 'POST':
        roll_number = request.POST.get('roll_number', '').strip()
        name = request.POST.get('name', '').strip()
        course = request.POST.get('course', '').strip()
        if not roll_number:
            messages.error(request, 'Roll number is required.')
        elif Student.objects.filter(exam_period=period, roll_number=roll_number).exists():
            messages.error(request, f'{roll_number} is already on this roster.')
        else:
            student = Student.objects.create(exam_period=period, roll_number=roll_number, name=name, course=course)
            HallTicket.objects.create(student=student)
            AuditLog.record(request.user, 'added', student)
            messages.success(request, f'{roll_number} added.')
    return redirect('period_detail', period_id=period.id)


@login_required
@role_required(User.ROLE_ADMIN)
def edit_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    if request.method == 'POST':
        student.name = request.POST.get('name', '').strip()
        student.course = request.POST.get('course', '').strip()
        student.save(update_fields=['name', 'course'])
        AuditLog.record(request.user, 'edited', student)
        messages.success(request, f'{student.roll_number} updated.')
    return redirect('period_detail', period_id=student.exam_period_id)


@login_required
@role_required(User.ROLE_ADMIN)
def toggle_student_active(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    if request.method == 'POST':
        student.is_active = not student.is_active
        student.save(update_fields=['is_active'])
        AuditLog.record(request.user, 'deactivated' if not student.is_active else 'reactivated', student)
        messages.success(request, f'{student.roll_number} {"deactivated" if not student.is_active else "reactivated"}.')
    return redirect('period_detail', period_id=student.exam_period_id)


@login_required
@role_required(User.ROLE_ADMIN)
def delete_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    period_id = student.exam_period_id
    if request.method == 'POST':
        try:
            guard_delete(student, 'student')
        except ValidationError as exc:
            messages.error(request, str(exc))
        else:
            roll_number = student.roll_number
            AuditLog.record(request.user, 'deleted', student)
            student.delete()
            messages.success(request, f'{roll_number} removed from the roster.')
    return redirect('period_detail', period_id=period_id)


# ---------------------------------------------------------------------------
# Admin — Section/Hall manager (global, shared across periods)
# ---------------------------------------------------------------------------

@login_required
@role_required(User.ROLE_ADMIN)
def hall_manager(request):
    halls = Hall.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        capacity = request.POST.get('capacity', '30').strip()
        seats_per_row = request.POST.get('seats_per_row', '6').strip()
        try:
            cap_val = max(int(capacity), 1)
        except (TypeError, ValueError):
            cap_val = 30
        try:
            spr_val = max(int(seats_per_row), 1)
        except (TypeError, ValueError):
            spr_val = 6

        if not name:
            messages.error(request, 'Please give the section a name.')
        elif Hall.objects.filter(name=name).exists():
            messages.error(request, f'"{name}" already exists.')
        else:
            hall = Hall.objects.create(name=name, capacity=cap_val, seats_per_row=spr_val)
            AuditLog.record(request.user, 'created', hall)
            messages.success(request, f'"{name}" added.')
        return redirect('hall_manager')

    return render(request, 'admin/hall_manager.html', {'halls': halls})


@login_required
@role_required(User.ROLE_ADMIN)
def edit_hall(request, hall_id):
    hall = get_object_or_404(Hall, id=hall_id)
    if request.method == 'POST':
        try:
            new_capacity = max(int(request.POST.get('capacity', hall.capacity)), 1)
        except (TypeError, ValueError):
            new_capacity = hall.capacity

        # Shrinking capacity below what's already allocated at some overlapping
        # time would silently create an invalid state — block it.
        max_allocated = 0
        for eh in hall.exam_halls.select_related('exam_session'):
            overlapping_total = sum(
                other.capacity_allocated for other in hall.exam_halls.select_related('exam_session')
                if other.exam_session.exam_date == eh.exam_session.exam_date
                and other.exam_session.start_time < eh.exam_session.end_time
                and eh.exam_session.start_time < other.exam_session.end_time
            )
            max_allocated = max(max_allocated, overlapping_total)

        if new_capacity < max_allocated:
            messages.error(
                request,
                f'Cannot reduce capacity below {max_allocated} — that many seats are already '
                f'allocated for an overlapping exam.'
            )
        else:
            hall.name = request.POST.get('name', hall.name).strip() or hall.name
            hall.capacity = new_capacity
            hall.save(update_fields=['name', 'capacity'])
            AuditLog.record(request.user, 'edited', hall)
            messages.success(request, f'{hall.name} updated.')
    return redirect('hall_manager')


@login_required
@role_required(User.ROLE_ADMIN)
def stop_hall(request, hall_id):
    hall = get_object_or_404(Hall, id=hall_id)
    if request.method == 'POST':
        hall.status = Hall.STATUS_ACTIVE if hall.status == Hall.STATUS_STOPPED else Hall.STATUS_STOPPED
        hall.save(update_fields=['status'])
        AuditLog.record(request.user, 'stopped' if hall.is_stopped else 'reactivated', hall)
        messages.success(request, f'{hall.name} {"stopped" if hall.is_stopped else "reactivated"}.')
    return redirect('hall_manager')


@login_required
@role_required(User.ROLE_ADMIN)
def delete_hall(request, hall_id):
    hall = get_object_or_404(Hall, id=hall_id)
    if request.method == 'POST':
        try:
            guard_delete(hall, 'section')
        except ValidationError as exc:
            messages.error(request, str(exc))
        else:
            name = hall.name
            AuditLog.record(request.user, 'deleted', hall)
            hall.delete()
            messages.success(request, f'{name} deleted.')
    return redirect('hall_manager')


# ---------------------------------------------------------------------------
# Admin — a single exam session: halls, invigilators, auto-assign
# ---------------------------------------------------------------------------

@login_required
@role_required(User.ROLE_ADMIN)
def exam_session_detail(request, session_id):
    exam_session = get_object_or_404(ExamSession, id=session_id)
    exam_halls = list(exam_session.exam_halls.select_related('hall', 'invigilator').all())
    selected_hall_ids = {eh.hall_id for eh in exam_halls}
    available_halls = Hall.objects.filter(status=Hall.STATUS_ACTIVE).exclude(id__in=selected_hall_ids)
    invigilators = User.objects.filter(role=User.ROLE_INVIGILATOR)

    assignments = exam_session.assignments.select_related('student', 'hall').order_by('hall__name', 'row', 'seat')
    assignments_by_hall = {}
    for a in assignments:
        assignments_by_hall.setdefault(a.hall_id, []).append(a)
    for exam_hall in exam_halls:
        exam_hall.review_assignments = assignments_by_hall.get(exam_hall.hall_id, [])

    return render(request, 'admin/exam_session_detail.html', {
        'exam_session': exam_session,
        'exam_halls': exam_halls,
        'available_halls': available_halls,
        'invigilators': invigilators,
        'unassigned_count': exam_session.unassigned_students.count(),
    })


@login_required
@role_required(User.ROLE_ADMIN)
def edit_exam_session(request, session_id):
    exam_session = get_object_or_404(ExamSession, id=session_id)
    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        exam_date = parse_date(request.POST.get('exam_date', '').strip())
        start_time = parse_time(request.POST.get('start_time', '').strip())
        end_time = parse_time(request.POST.get('end_time', '').strip())

        if not subject or not exam_date or not start_time or not end_time:
            messages.error(request, 'Please provide a valid subject, date, start time, and end time.')
            return redirect('exam_session_detail', session_id=exam_session.id)

        try:
            with transaction.atomic():
                check_not_expired(exam_date, end_time)
                # Re-check every existing hall allocation still fits at the new time.
                for eh in exam_session.exam_halls.select_related('hall'):
                    temp = ExamSession(
                        id=exam_session.id, exam_period=exam_session.exam_period,
                        exam_date=exam_date, start_time=start_time, end_time=end_time,
                    )
                    check_hall_capacity(eh.hall, temp, eh.capacity_allocated, exclude_exam_hall_id=eh.id)
                exam_session.subject = subject
                exam_session.exam_date = exam_date
                exam_session.start_time = start_time
                exam_session.end_time = end_time
                exam_session.save(update_fields=['subject', 'exam_date', 'start_time', 'end_time'])
        except ValidationError as exc:
            messages.error(request, str(exc))
        else:
            AuditLog.record(request.user, 'edited', exam_session)
            messages.success(request, 'Exam session updated.')
    return redirect('exam_session_detail', session_id=exam_session.id)


@login_required
@role_required(User.ROLE_ADMIN)
def add_exam_hall(request, session_id):
    exam_session = get_object_or_404(ExamSession, id=session_id)
    if request.method == 'POST':
        hall_id = request.POST.get('hall_id')
        hall = get_object_or_404(Hall, id=hall_id)
        try:
            requested = max(int(request.POST.get('capacity_allocated', '0')), 1)
        except (TypeError, ValueError):
            requested = 1

        try:
            with transaction.atomic():
                check_hall_capacity(hall, exam_session, requested)
                ExamHall.objects.create(exam_session=exam_session, hall=hall, capacity_allocated=requested)
        except ValidationError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f'{hall.name} added with {requested} seat(s) reserved.')
    return redirect('exam_session_detail', session_id=exam_session.id)


@login_required
@role_required(User.ROLE_ADMIN)
def edit_exam_hall_capacity(request, exam_hall_id):
    exam_hall = get_object_or_404(ExamHall, id=exam_hall_id)
    if request.method == 'POST':
        try:
            requested = max(int(request.POST.get('capacity_allocated', '0')), 1)
        except (TypeError, ValueError):
            requested = exam_hall.capacity_allocated

        if requested < exam_hall.assigned_count:
            messages.error(
                request,
                f'Cannot reduce below {exam_hall.assigned_count} — that many students are '
                f'already seated in {exam_hall.hall.name} for this exam.'
            )
            return redirect('exam_session_detail', session_id=exam_hall.exam_session_id)

        try:
            with transaction.atomic():
                check_hall_capacity(
                    exam_hall.hall, exam_hall.exam_session, requested, exclude_exam_hall_id=exam_hall.id
                )
                exam_hall.capacity_allocated = requested
                exam_hall.save(update_fields=['capacity_allocated'])
        except ValidationError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f'{exam_hall.hall.name} updated to {requested} seat(s).')
    return redirect('exam_session_detail', session_id=exam_hall.exam_session_id)


@login_required
@role_required(User.ROLE_ADMIN)
def remove_exam_hall(request, exam_hall_id):
    exam_hall = get_object_or_404(ExamHall, id=exam_hall_id)
    session_id = exam_hall.exam_session_id
    if request.method == 'POST':
        try:
            guard_delete(exam_hall, 'section assignment')
        except ValidationError as exc:
            messages.error(request, str(exc))
        else:
            hall_name = exam_hall.hall.name
            exam_hall.delete()
            messages.success(request, f'{hall_name} removed from this exam.')
    return redirect('exam_session_detail', session_id=session_id)


@login_required
@role_required(User.ROLE_ADMIN)
def assign_exam_hall_invigilator(request, exam_hall_id):
    exam_hall = get_object_or_404(ExamHall, id=exam_hall_id)
    if request.method == 'POST':
        user_id = request.POST.get('invigilator_id')
        new_invigilator = get_object_or_404(User, id=user_id, role=User.ROLE_INVIGILATOR) if user_id else None
        try:
            if new_invigilator:
                check_invigilator_conflict(new_invigilator, exam_hall.exam_session, exclude_exam_hall_id=exam_hall.id)
        except ValidationError as exc:
            messages.error(request, str(exc))
        else:
            exam_hall.invigilator = new_invigilator
            exam_hall.save(update_fields=['invigilator'])
            messages.success(request, f'{exam_hall.hall.name} updated.')
    return redirect('exam_session_detail', session_id=exam_hall.exam_session_id)


@login_required
@role_required(User.ROLE_ADMIN)
def auto_assign_students(request, session_id):
    exam_session = get_object_or_404(ExamSession, id=session_id)
    if request.method == 'POST':
        try:
            summary = auto_assign_exam_session(exam_session)
            per_hall = ', '.join(f"{h['hall']}: {h['assigned']}" for h in summary['halls'])
            msg = f"Assigned {summary['total_assigned']} student(s) — {per_hall}."
            if summary['skipped_conflicts']:
                msg += f" Skipped (schedule conflict): {', '.join(summary['skipped_conflicts'])}."
            messages.success(request, msg)
        except AllocationError as exc:
            messages.error(request, str(exc))
    return redirect('exam_session_detail', session_id=exam_session.id)


@login_required
@role_required(User.ROLE_ADMIN)
def confirm_allocation(request, session_id):
    exam_session = get_object_or_404(ExamSession, id=session_id)
    if request.method == 'POST':
        if exam_session.unassigned_students.exists():
            messages.error(request, 'Every active roster student must be assigned before confirming.')
        else:
            exam_session.status = ExamSession.STATUS_READY
            exam_session.save(update_fields=['status'])
            AuditLog.record(request.user, 'confirmed_allocation', exam_session)
            messages.success(request, 'Allocation confirmed — this exam is ready.')
    return redirect('exam_session_detail', session_id=exam_session.id)


@login_required
@role_required(User.ROLE_ADMIN)
def stop_exam_session(request, session_id):
    exam_session = get_object_or_404(ExamSession, id=session_id)
    if request.method == 'POST':
        if exam_session.status == ExamSession.STATUS_STOPPED:
            exam_session.status = ExamSession.STATUS_SCHEDULED if exam_session.exam_halls.exists() else ExamSession.STATUS_DRAFT
        else:
            exam_session.status = ExamSession.STATUS_STOPPED
        exam_session.save(update_fields=['status'])
        AuditLog.record(request.user, exam_session.get_status_display(), exam_session)
        messages.success(request, f'Exam session set to {exam_session.get_status_display()}.')
    return redirect('exam_session_detail', session_id=exam_session.id)


@login_required
@role_required(User.ROLE_ADMIN)
def delete_exam_session(request, session_id):
    exam_session = get_object_or_404(ExamSession, id=session_id)
    period_id = exam_session.exam_period_id
    if request.method == 'POST':
        try:
            guard_delete(exam_session, 'exam session')
        except ValidationError as exc:
            messages.error(request, str(exc))
            return redirect('exam_session_detail', session_id=exam_session.id)
        subject = exam_session.subject
        AuditLog.record(request.user, 'deleted', exam_session)
        exam_session.delete()
        messages.success(request, f'{subject} deleted.')
    return redirect('period_detail', period_id=period_id)


# ---------------------------------------------------------------------------
# Admin — staff accounts
# ---------------------------------------------------------------------------

@login_required
@role_required(User.ROLE_ADMIN)
def manage_users(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        role = request.POST.get('role')
        first_name = request.POST.get('first_name', '').strip()

        if not username or not password or role not in dict(User.ROLE_CHOICES):
            messages.error(request, 'Please fill all fields correctly.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" is already taken.')
        else:
            user = User.objects.create_user(username=username, password=password, first_name=first_name)
            user.role = role
            user.save()
            messages.success(request, f'{user.get_role_display()} account "{username}" created.')
        return redirect('manage_users')

    staff_users = User.objects.exclude(role=User.ROLE_ADMIN)
    return render(request, 'admin/manage_users.html', {
        'staff_users': staff_users,
        'role_choices': [c for c in User.ROLE_CHOICES if c[0] != User.ROLE_ADMIN],
    })


@login_required
@role_required(User.ROLE_ADMIN)
def toggle_user_active(request, user_id):
    target = get_object_or_404(User, id=user_id)
    if request.method == 'POST' and target != request.user:
        target.is_active = not target.is_active
        target.save()
    return redirect('manage_users')


# ---------------------------------------------------------------------------
# Invigilator
# ---------------------------------------------------------------------------

@login_required
@role_required(User.ROLE_INVIGILATOR)
def invigilator_dashboard(request):
    current = get_current_invigilator_context(request.user)

    roster = []
    if current:
        assignments = ExamStudentAssignment.objects.filter(
            exam_session=current.exam_session, hall=current.hall
        ).select_related('student').order_by('row', 'seat')
        present_ids = set(
            Attendance.objects.filter(exam_session=current.exam_session, hall=current.hall)
            .values_list('student_id', flat=True)
        )
        roster = [{
            'id': a.student.id, 'roll_number': a.student.roll_number, 'name': a.student.name,
            'row': a.row, 'seat': a.seat, 'is_present': a.student.id in present_ids,
        } for a in assignments]

    upcoming = []
    if not current:
        now = timezone.localtime()
        upcoming = ExamHall.objects.filter(
            invigilator=request.user,
            exam_session__status__in=ExamSession.LIVE_STATUSES,
            exam_session__exam_date__gte=now.date(),
        ).select_related('exam_session', 'hall').order_by('exam_session__exam_date', 'exam_session__start_time')[:5]

    my_alerts = Alert.objects.filter(invigilator=request.user).select_related(
        'student', 'hall', 'exam_session'
    ).order_by('-timestamp')[:20]

    return render(request, 'invigilator/dashboard.html', {
        'current': current, 'roster': roster, 'upcoming': upcoming, 'my_alerts': my_alerts,
    })


@login_required
@role_required(User.ROLE_INVIGILATOR)
def hall_roster_json(request):
    current = get_current_invigilator_context(request.user)
    if not current:
        return JsonResponse({'students': [], 'present_count': 0, 'total_count': 0})

    assignments = ExamStudentAssignment.objects.filter(
        exam_session=current.exam_session, hall=current.hall
    ).select_related('student').order_by('row', 'seat')
    present_ids = set(
        Attendance.objects.filter(exam_session=current.exam_session, hall=current.hall)
        .values_list('student_id', flat=True)
    )
    students = [{
        'id': a.student.id, 'roll_number': a.student.roll_number, 'name': a.student.name,
        'row': a.row, 'seat': a.seat, 'is_present': a.student.id in present_ids,
    } for a in assignments]

    return JsonResponse({
        'students': students,
        'present_count': len(present_ids),
        'total_count': len(students),
    })


@login_required
def verify_qr(request):
    """QR -> student -> current active exam -> student's assignment for
    that exam -> compare with the invigilator's current hall -> mark or
    reject. Nothing about the exam/hall/seat is trusted from the client —
    only the opaque qr_token is read from the scan; everything else is
    looked up."""
    if request.method != 'POST':
        return JsonResponse({'status': 'invalid_method'}, status=405)
    if request.user.role != User.ROLE_INVIGILATOR:
        return JsonResponse({'status': 'error', 'message': 'Not authorized.'}, status=403)

    try:
        data = json.loads(request.body)
        qr_token = (data.get('qr_data') or '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'status': 'error', 'message': 'Malformed scan payload.'})

    if not qr_token:
        return JsonResponse({'status': 'error', 'message': 'Empty QR code.'})

    current = get_current_invigilator_context(request.user)
    if not current:
        now = timezone.localtime()
        upcoming = ExamHall.objects.filter(
            invigilator=request.user,
            exam_session__status__in=ExamSession.LIVE_STATUSES,
            exam_session__exam_date__gte=now.date(),
        ).select_related('exam_session').order_by('exam_session__exam_date', 'exam_session__start_time').first()

        if upcoming and now < upcoming.exam_session.scan_window_start_dt():
            opens_at = upcoming.exam_session.scan_window_start_dt().strftime("%I:%M %p")
            return JsonResponse({
                'status': 'error',
                'message': f'Scanning is locked. Scanning opens 3 hours before exam start time (at {opens_at}).',
            })
        return JsonResponse({'status': 'error', 'message': 'No active exam session for you right now. Scanning opens 3 hours before start time.'})

    hall_ticket = HallTicket.objects.filter(qr_token=qr_token).select_related('student').first()
    if not hall_ticket:
        return JsonResponse({'status': 'error', 'message': 'Invalid hall ticket / QR code.'})

    student = hall_ticket.student
    if not student.is_active:
        return JsonResponse({'status': 'error', 'message': 'This student record is deactivated.'})

    assignment = ExamStudentAssignment.objects.filter(
        exam_session=current.exam_session, student=student
    ).select_related('hall').first()
    if not assignment:
        return JsonResponse({
            'status': 'error',
            'message': f'{student.name or student.roll_number} is not assigned to this exam session.',
        })

    if assignment.hall_id != current.hall_id:
        return JsonResponse({
            'status': 'warning',
            'message': f'Wrong section — {student.roll_number} belongs in {assignment.hall.name}.',
            'student_id': student.id,
        })

    _, created = Attendance.objects.get_or_create(
        exam_session=current.exam_session, student=student,
        defaults={'hall': current.hall, 'invigilator': request.user},
    )
    if not created:
        return JsonResponse({
            'status': 'warning',
            'message': f'Attendance already marked for {student.name or student.roll_number} '
                       f'(Row {assignment.row}, Seat {assignment.seat}).',
            'student_id': student.id,
        })

    return JsonResponse({
        'status': 'success',
        'message': f'Verified: {student.name or student.roll_number} — Row {assignment.row}, Seat {assignment.seat}.',
        'student_id': student.id,
    })


@login_required
@role_required(User.ROLE_INVIGILATOR)
def raise_alert(request):
    current = get_current_invigilator_context(request.user)
    scanned_students = []
    if current:
        present_ids = Attendance.objects.filter(
            exam_session=current.exam_session, hall=current.hall
        ).values_list('student_id', flat=True)
        scanned_students = ExamStudentAssignment.objects.filter(
            exam_session=current.exam_session, hall=current.hall, student_id__in=present_ids
        ).select_related('student').order_by('row', 'seat')

    if request.method == 'POST':
        if not current:
            messages.error(request, 'You have no active exam session right now.')
            return redirect('invigilator_dashboard')

        alert_type = request.POST.get('alert_type')
        student_id = request.POST.get('student_id')
        notes = request.POST.get('notes', '').strip()

        student = None
        row = seat = ''
        if student_id:
            student = Student.objects.filter(id=student_id, exam_period=current.exam_session.exam_period).first()
            assignment = ExamStudentAssignment.objects.filter(
                exam_session=current.exam_session, student=student
            ).first() if student else None
            if assignment:
                row, seat = assignment.row, assignment.seat
        else:
            row = request.POST.get('row', '').strip()
            seat = request.POST.get('seat', '').strip()

        if alert_type not in dict(Alert.ALERT_TYPES):
            messages.error(request, 'Please choose a valid alert type.')
            return render(request, 'invigilator/raise_alert.html', {
                'current': current, 'alert_types': Alert.ALERT_TYPES,
                'student': student, 'scanned_students': scanned_students,
            })

        Alert.objects.create(
            exam_session=current.exam_session, alert_type=alert_type, hall=current.hall,
            invigilator=request.user, student=student, row=row, seat=seat, notes=notes,
        )
        messages.success(request, 'Alert raised. The control room has been notified.')
        return redirect('invigilator_dashboard')

    student_id = request.GET.get('student_id')
    student = None
    if student_id and current:
        student = Student.objects.filter(id=student_id, exam_period=current.exam_session.exam_period).first()

    my_alerts = Alert.objects.filter(invigilator=request.user).select_related(
        'student', 'hall', 'exam_session'
    ).order_by('-timestamp')[:20]

    return render(request, 'invigilator/raise_alert.html', {
        'current': current, 'alert_types': Alert.ALERT_TYPES,
        'student': student, 'scanned_students': scanned_students,
        'my_alerts': my_alerts,
    })


# ---------------------------------------------------------------------------
# Control room
# ---------------------------------------------------------------------------

@login_required
@role_required(User.ROLE_CONTROL_ROOM, User.ROLE_ADMIN)
def control_room(request):
    alerts = Alert.objects.filter(exam_session__exam_period__status=ExamPeriod.STATUS_ACTIVE).select_related(
        'hall', 'student', 'invigilator', 'exam_session'
    ).order_by('-timestamp')
    counts = alerts.aggregate(
        pending=Count('id', filter=Q(status=Alert.STATUS_PENDING)),
        acknowledged=Count('id', filter=Q(status=Alert.STATUS_ACK)),
        resolved=Count('id', filter=Q(status=Alert.STATUS_RESOLVED)),
    )
    return render(request, 'control_room/dashboard.html', {'alerts': alerts, 'counts': counts})


@login_required
@role_required(User.ROLE_CONTROL_ROOM, User.ROLE_ADMIN)
def update_alert(request, alert_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'invalid_method'}, status=405)
    alert = get_object_or_404(Alert, id=alert_id)
    status = request.POST.get('status')
    if status in dict(Alert.STATUS_CHOICES):
        alert.status = status
        if status == Alert.STATUS_RESOLVED:
            alert.resolved_at = timezone.now()
        alert.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'message': 'Invalid status.'}, status=400)


@login_required
@role_required(User.ROLE_CONTROL_ROOM, User.ROLE_ADMIN)
def reports(request):
    alerts_prefetch = Prefetch(
        'alerts',
        queryset=Alert.objects.select_related('hall', 'student', 'invigilator').order_by('-timestamp')
    )
    sessions_list = (
        ExamSession.objects
        .select_related('exam_period')
        .annotate(alerts_count=Count('alerts'))
        .prefetch_related(alerts_prefetch)
        .order_by('-exam_date', '-start_time')
    )
    paginator = Paginator(sessions_list, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'control_room/reports.html', {'page_obj': page_obj})


@login_required
@role_required(User.ROLE_CONTROL_ROOM, User.ROLE_ADMIN)
def export_session_report(request, session_id):
    exam_session = get_object_or_404(ExamSession, id=session_id)
    response = HttpResponse(content_type='text/csv')
    filename = f'invisense_report_{exam_session.exam_date}_{exam_session.subject}.csv'.replace(' ', '_')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(['Flag Time', 'Hall', 'Seat', 'Student Name', 'Roll Number', 'Type', 'Status', 'Invigilator Name', 'Notes'])
    for alert in exam_session.alerts.select_related('hall', 'invigilator', 'student').order_by('timestamp'):
        seat_parts = []
        if alert.row:
            seat_parts.append(f"Row {alert.row}")
        if alert.seat:
            seat_parts.append(f"Seat {alert.seat}")
        seat_str = ", ".join(seat_parts) if seat_parts else '-'
        student_name = alert.student.name if (alert.student and alert.student.name) else (alert.student.roll_number if alert.student else '-')
        roll_no = alert.student.roll_number if alert.student else '-'
        invigilator_name = alert.invigilator.get_full_name() or alert.invigilator.username
        writer.writerow([
            alert.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            alert.hall.name,
            seat_str,
            student_name,
            roll_no,
            alert.get_alert_type_display(),
            alert.get_status_display(),
            invigilator_name,
            alert.notes or '',
        ])
    return response


# ---------------------------------------------------------------------------
# Admin — Setup session & Upload mapping (convenience & backward compatibility)
# ---------------------------------------------------------------------------

@login_required
@role_required(User.ROLE_ADMIN)
def setup_session(request):
    if request.method == 'POST':
        exam_date_str = request.POST.get('date', '').strip()
        shift = request.POST.get('shift', 'Morning').strip()
        hall_number = request.POST.get('hall_number', '').strip()
        try:
            capacity = max(int(request.POST.get('capacity', '30')), 1)
        except (ValueError, TypeError):
            capacity = 30
        try:
            seats_per_row = max(int(request.POST.get('seats_per_row', '6')), 1)
        except (ValueError, TypeError):
            seats_per_row = 6

        exam_date = parse_date(exam_date_str) or timezone.now().date()
        shift_times = {
            'Morning': (timezone.datetime.strptime('09:30', '%H:%M').time(), timezone.datetime.strptime('12:30', '%H:%M').time()),
            'Afternoon': (timezone.datetime.strptime('13:30', '%H:%M').time(), timezone.datetime.strptime('16:30', '%H:%M').time()),
            'Evening': (timezone.datetime.strptime('17:30', '%H:%M').time(), timezone.datetime.strptime('20:30', '%H:%M').time()),
        }
        start_time, end_time = shift_times.get(shift, shift_times['Morning'])

        period = ExamPeriod.objects.filter(status=ExamPeriod.STATUS_ACTIVE).first()
        if not period:
            period = ExamPeriod.objects.create(name=f"Exam Period ({exam_date.strftime('%B %Y')})")

        session = ExamSession.objects.create(
            exam_period=period,
            subject=f"{shift} Exam Session",
            exam_date=exam_date,
            start_time=start_time,
            end_time=end_time,
            status=ExamSession.STATUS_SCHEDULED,
        )

        if hall_number:
            hall, _ = Hall.objects.get_or_create(
                name=hall_number,
                defaults={'capacity': capacity, 'seats_per_row': seats_per_row}
            )
            ExamHall.objects.create(
                exam_session=session,
                hall=hall,
                capacity_allocated=min(capacity, hall.capacity),
            )

        messages.success(request, f'Session created for {exam_date} ({shift}).')
        return redirect('exam_session_detail', session_id=session.id)

    return render(request, 'admin/setup_session.html')


@login_required
@role_required(User.ROLE_ADMIN)
def upload_mapping(request):
    sessions = ExamSession.objects.filter(status__in=ExamSession.LIVE_STATUSES).select_related('exam_period')
    if not sessions.exists():
        period = ExamPeriod.objects.filter(status=ExamPeriod.STATUS_ACTIVE).first()
        if not period:
            period = ExamPeriod.objects.create(name='General Exam Period')
        default_session = ExamSession.objects.create(
            exam_period=period, subject='General Exam',
            exam_date=timezone.now().date() + timezone.timedelta(days=1),
            start_time=timezone.datetime.strptime('09:30', '%H:%M').time(),
            end_time=timezone.datetime.strptime('12:30', '%H:%M').time(),
        )
        sessions = ExamSession.objects.filter(id=default_session.id)

    if request.method == 'POST':
        session_id = request.POST.get('session_id')
        exam_session = get_object_or_404(ExamSession, id=session_id)
        csv_file = request.FILES.get('mapping_file')

        if not csv_file or not csv_file.name.lower().endswith('.csv'):
            messages.error(request, 'Please upload a valid CSV file.')
            return redirect('upload_mapping')

        try:
            file_data = csv_file.read().decode('utf-8-sig').splitlines()
        except UnicodeDecodeError:
            messages.error(request, 'Could not read file. Please save as UTF-8.')
            return redirect('upload_mapping')

        reader = csv.DictReader(file_data)
        created = 0
        for row in reader:
            roll_number = (row.get('roll_number') or '').strip()
            if not roll_number:
                continue
            student, _ = Student.objects.get_or_create(
                exam_period=exam_session.exam_period,
                roll_number=roll_number,
                defaults={
                    'name': (row.get('name') or '').strip(),
                    'course': (row.get('course') or row.get('subject_code') or '').strip(),
                }
            )
            HallTicket.objects.get_or_create(student=student)
            created += 1

        messages.success(request, f'Imported {created} student(s) successfully.')
        return redirect('period_detail', period_id=exam_session.exam_period_id)

    return render(request, 'admin/upload_mapping.html', {'sessions': sessions})

