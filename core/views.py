import csv
import json

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time

from .allocation import AllocationError, auto_assign_exam_session
from .hall_tickets import generate_hall_tickets_pdf
from .models import (
    Alert, Attendance, ExamHall, ExamPeriod, ExamSession,
    ExamStudentAssignment, Hall, HallTicket, Student, User,
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
    client sends. Returns None if nothing is active right now."""
    now = timezone.localtime()
    return ExamHall.objects.filter(
        invigilator=user,
        exam_session__status=ExamSession.STATUS_SCHEDULED,
        exam_session__exam_date=now.date(),
        exam_session__start_time__lte=now.time(),
        exam_session__end_time__gte=now.time(),
    ).select_related('exam_session', 'hall').first()


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
            login(request, user)
            return redirect('home')
        messages.error(request, 'Invalid username or password.')
    return render(request, 'login.html')


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


# ---------------------------------------------------------------------------
# Admin — exam periods
# ---------------------------------------------------------------------------

@login_required
@role_required(User.ROLE_ADMIN)
def admin_dashboard(request):
    periods = ExamPeriod.objects.all()
    stats = {
        'active_periods': periods.filter(is_active=True).count(),
        'total_students': Student.objects.count(),
        'pending_alerts': Alert.objects.filter(status=Alert.STATUS_PENDING).count(),
        'total_invigilators': User.objects.filter(role=User.ROLE_INVIGILATOR).count(),
    }
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Please give the exam period a name.')
        else:
            period = ExamPeriod.objects.create(name=name)
            messages.success(request, f'"{name}" created.')
            return redirect('period_detail', period_id=period.id)

    return render(request, 'admin/dashboard.html', {'periods': periods, 'stats': stats})


@login_required
@role_required(User.ROLE_ADMIN)
def period_detail(request, period_id):
    period = get_object_or_404(ExamPeriod, id=period_id)
    exam_sessions = period.exam_sessions.all()
    halls = period.halls.all()

    if request.method == 'POST':
        # Inline "add a hall" form on this page.
        hall_number = request.POST.get('hall_number', '').strip()
        capacity = request.POST.get('capacity', '30').strip()
        seats_per_row = request.POST.get('seats_per_row', '6').strip()
        if hall_number:
            try:
                cap_val = max(int(capacity), 1)
            except (TypeError, ValueError):
                cap_val = 30
            try:
                spr_val = max(int(seats_per_row), 1)
            except (TypeError, ValueError):
                spr_val = 6
            _, created = Hall.objects.get_or_create(
                exam_period=period, hall_number=hall_number,
                defaults={'capacity': cap_val, 'seats_per_row': spr_val},
            )
            if created:
                messages.success(request, f'Hall {hall_number} added.')
            else:
                messages.error(request, f'Hall {hall_number} already exists in this period.')
        return redirect('period_detail', period_id=period.id)

    return render(request, 'admin/period_detail.html', {
        'period': period,
        'exam_sessions': exam_sessions,
        'halls': halls,
    })


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
            HallTicket.objects.create(student=student)  # generates the one permanent QR
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

        created, skipped_invalid, skipped_duplicate = 0, 0, 0
        for row in reader:
            subject = (row.get('subject') or '').strip()
            exam_date = parse_date((row.get('exam_date') or '').strip())
            start_time = parse_time((row.get('start_time') or '').strip())
            end_time = parse_time((row.get('end_time') or '').strip())
            shift = (row.get('shift') or '').strip()

            if not subject or not exam_date or not start_time or not end_time:
                skipped_invalid += 1
                continue

            if ExamSession.objects.filter(
                exam_period=period, subject=subject, exam_date=exam_date, start_time=start_time
            ).exists():
                skipped_duplicate += 1
                continue

            ExamSession.objects.create(
                exam_period=period, subject=subject, exam_date=exam_date,
                shift=shift, start_time=start_time, end_time=end_time,
            )
            created += 1

        summary = f'Created {created} exam session(s).'
        extras = []
        if skipped_invalid:
            extras.append(f'{skipped_invalid} skipped (bad/missing date or time — use YYYY-MM-DD and HH:MM)')
        if skipped_duplicate:
            extras.append(f'{skipped_duplicate} skipped (already exists)')
        if extras:
            summary += ' — ' + ', '.join(extras) + '.'
        messages.success(request, summary)
        return redirect('period_detail', period_id=period.id)

    return render(request, 'admin/upload_timetable.html', {'period': period})


@login_required
@role_required(User.ROLE_ADMIN)
def download_hall_tickets(request, period_id):
    period = get_object_or_404(ExamPeriod, id=period_id)
    students = period.students.filter(assignments__isnull=False).distinct().select_related('hall_ticket')
    if not students.exists():
        messages.error(request, 'No students have an exam assignment yet — assign seating first.')
        return redirect('period_detail', period_id=period.id)

    buffer = generate_hall_tickets_pdf(students, period)
    filename = f'hall_tickets_{period.name}.pdf'.replace(' ', '_')
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ---------------------------------------------------------------------------
# Admin — a single exam session: halls, invigilators, auto-assign, confirm
# ---------------------------------------------------------------------------

@login_required
@role_required(User.ROLE_ADMIN)
def exam_session_detail(request, session_id):
    exam_session = get_object_or_404(ExamSession, id=session_id)
    exam_halls = list(exam_session.exam_halls.select_related('hall', 'invigilator').all())
    selected_hall_ids = {eh.hall_id for eh in exam_halls}
    available_halls = exam_session.exam_period.halls.exclude(id__in=selected_hall_ids)
    invigilators = User.objects.filter(role=User.ROLE_INVIGILATOR)

    assignments = exam_session.assignments.select_related('student', 'hall').order_by('hall__hall_number', 'row', 'seat')
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
def add_exam_hall(request, session_id):
    exam_session = get_object_or_404(ExamSession, id=session_id)
    if request.method == 'POST':
        hall_id = request.POST.get('hall_id')
        hall = get_object_or_404(Hall, id=hall_id, exam_period=exam_session.exam_period)
        ExamHall.objects.get_or_create(exam_session=exam_session, hall=hall)
        messages.success(request, f'Hall {hall.hall_number} added to this exam.')
    return redirect('exam_session_detail', session_id=exam_session.id)


@login_required
@role_required(User.ROLE_ADMIN)
def remove_exam_hall(request, exam_hall_id):
    exam_hall = get_object_or_404(ExamHall, id=exam_hall_id)
    session_id = exam_hall.exam_session_id
    if request.method == 'POST':
        if exam_hall.assigned_count > 0:
            messages.error(
                request,
                f'Hall {exam_hall.hall.hall_number} already has students assigned for this exam — '
                f'remove those assignments first.'
            )
        else:
            hall_number = exam_hall.hall.hall_number
            exam_hall.delete()
            messages.success(request, f'Hall {hall_number} removed from this exam.')
    return redirect('exam_session_detail', session_id=session_id)


@login_required
@role_required(User.ROLE_ADMIN)
def assign_exam_hall_invigilator(request, exam_hall_id):
    exam_hall = get_object_or_404(ExamHall, id=exam_hall_id)
    if request.method == 'POST':
        user_id = request.POST.get('invigilator_id')
        exam_hall.invigilator = get_object_or_404(User, id=user_id, role=User.ROLE_INVIGILATOR) if user_id else None
        exam_hall.save()
        messages.success(request, f'Hall {exam_hall.hall.hall_number} updated.')
    return redirect('exam_session_detail', session_id=exam_hall.exam_session_id)


@login_required
@role_required(User.ROLE_ADMIN)
def auto_assign_students(request, session_id):
    exam_session = get_object_or_404(ExamSession, id=session_id)
    if request.method == 'POST':
        try:
            summary = auto_assign_exam_session(exam_session)
            per_hall = ', '.join(f"Hall {h['hall']}: {h['assigned']}" for h in summary['halls'])
            messages.success(
                request,
                f"Assigned {summary['total_assigned']} student(s) — {per_hall}."
            )
        except AllocationError as exc:
            messages.error(request, str(exc))
    return redirect('exam_session_detail', session_id=exam_session.id)


@login_required
@role_required(User.ROLE_ADMIN)
def confirm_allocation(request, session_id):
    exam_session = get_object_or_404(ExamSession, id=session_id)
    if request.method == 'POST':
        exam_session.seating_confirmed = True
        exam_session.save(update_fields=['seating_confirmed'])
        messages.success(request, 'Allocation confirmed.')
    return redirect('exam_session_detail', session_id=exam_session.id)


@login_required
@role_required(User.ROLE_ADMIN)
def cancel_exam_session(request, session_id):
    exam_session = get_object_or_404(ExamSession, id=session_id)
    if request.method == 'POST':
        exam_session.status = (
            ExamSession.STATUS_CANCELLED if exam_session.status != ExamSession.STATUS_CANCELLED
            else ExamSession.STATUS_SCHEDULED
        )
        exam_session.save(update_fields=['status'])
        state = 'cancelled' if exam_session.status == ExamSession.STATUS_CANCELLED else 'reinstated'
        messages.success(request, f'Exam {state}.')
    return redirect('exam_session_detail', session_id=exam_session.id)


# ---------------------------------------------------------------------------
# Admin — staff accounts (unchanged from before)
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
            exam_session__status=ExamSession.STATUS_SCHEDULED,
            exam_session__exam_date__gte=now.date(),
        ).select_related('exam_session', 'hall').order_by('exam_session__exam_date', 'exam_session__start_time')[:5]

    return render(request, 'invigilator/dashboard.html', {
        'current': current, 'roster': roster, 'upcoming': upcoming,
    })


@login_required
@role_required(User.ROLE_INVIGILATOR)
def hall_roster_json(request):
    """Lightweight polling endpoint so the roster panel can refresh live
    without restarting the QR scanner (a full page reload would kill the
    camera stream)."""
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
    """The core validation described in the spec:
    QR -> student -> current active exam -> student's assignment for that
    exam -> compare with the invigilator's current hall -> mark or reject.
    Nothing about the exam/hall/seat is trusted from the client — only the
    opaque qr_token is read from the scan; everything else is looked up."""
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
        return JsonResponse({'status': 'error', 'message': 'No active exam session for you right now.'})

    hall_ticket = HallTicket.objects.filter(qr_token=qr_token).select_related('student').first()
    if not hall_ticket:
        return JsonResponse({'status': 'error', 'message': 'Invalid hall ticket / QR code.'})

    student = hall_ticket.student

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
            'message': f'Wrong hall — {student.roll_number} belongs in Hall {assignment.hall.hall_number}.',
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

    return render(request, 'invigilator/raise_alert.html', {
        'current': current, 'alert_types': Alert.ALERT_TYPES,
        'student': student, 'scanned_students': scanned_students,
    })


# ---------------------------------------------------------------------------
# Control room
# ---------------------------------------------------------------------------

@login_required
@role_required(User.ROLE_CONTROL_ROOM, User.ROLE_ADMIN)
def control_room(request):
    alerts = Alert.objects.filter(exam_session__exam_period__is_active=True).select_related(
        'hall', 'student', 'invigilator', 'exam_session'
    )
    counts = {
        'pending': alerts.filter(status=Alert.STATUS_PENDING).count(),
        'acknowledged': alerts.filter(status=Alert.STATUS_ACK).count(),
        'resolved': alerts.filter(status=Alert.STATUS_RESOLVED).count(),
    }
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
    sessions_list = ExamSession.objects.select_related('exam_period').all()
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
    writer.writerow(['Timestamp', 'Hall', 'Alert Type', 'Status', 'Row', 'Seat', 'Invigilator', 'Notes'])
    for alert in exam_session.alerts.select_related('hall', 'invigilator').order_by('timestamp'):
        writer.writerow([
            alert.timestamp.strftime('%Y-%m-%d %H:%M'),
            alert.hall.hall_number,
            alert.get_alert_type_display(),
            alert.get_status_display(),
            alert.row or '-',
            alert.seat or '-',
            alert.invigilator.username,
            alert.notes or '',
        ])
    return response
