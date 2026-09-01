import csv
import json

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .allocation import AllocationError, auto_allocate_session
from .hall_tickets import generate_hall_tickets_pdf
from .models import Alert, ExamSession, Hall, Student, User

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
# Admin
# ---------------------------------------------------------------------------

@login_required
@role_required(User.ROLE_ADMIN)
def admin_dashboard(request):
    sessions = ExamSession.objects.all().prefetch_related('halls', 'students')
    stats = {
        'active_sessions': sessions.filter(is_active=True).count(),
        'total_students': Student.objects.count(),
        'pending_alerts': Alert.objects.filter(status=Alert.STATUS_PENDING).count(),
        'total_invigilators': User.objects.filter(role=User.ROLE_INVIGILATOR).count(),
    }
    return render(request, 'admin/dashboard.html', {'sessions': sessions, 'stats': stats})


@login_required
@role_required(User.ROLE_ADMIN)
def setup_session(request):
    if request.method == 'POST':
        date = request.POST.get('date')
        shift = request.POST.get('shift')
        hall_numbers = request.POST.getlist('hall_number')
        capacities = request.POST.getlist('capacity')
        seats_per_rows = request.POST.getlist('seats_per_row')

        if not date or not shift or not any(hall_numbers):
            messages.error(request, 'Please provide a date, shift and at least one hall.')
            return render(request, 'admin/setup_session.html')

        session = ExamSession.objects.create(date=date, shift=shift)

        created = 0
        for h, cap, spr in zip(hall_numbers, capacities, seats_per_rows):
            h = (h or '').strip()
            if not h:
                continue
            try:
                cap_val = max(int(cap), 1)
            except (TypeError, ValueError):
                cap_val = 30
            try:
                spr_val = max(int(spr), 1)
            except (TypeError, ValueError):
                spr_val = 6

            Hall.objects.get_or_create(
                session=session, hall_number=h,
                defaults={'capacity': cap_val, 'seats_per_row': spr_val},
            )
            created += 1

        messages.success(request, f'Session created with {created} hall(s).')
        return redirect('session_detail', session_id=session.id)

    return render(request, 'admin/setup_session.html')


@login_required
@role_required(User.ROLE_ADMIN)
def session_detail(request, session_id):
    session = get_object_or_404(ExamSession, id=session_id)
    halls = session.halls.select_related('invigilator').all()
    invigilators = User.objects.filter(role=User.ROLE_INVIGILATOR)
    return render(request, 'admin/session_detail.html', {
        'session': session,
        'halls': halls,
        'invigilators': invigilators,
        'unseated_count': session.unseated_count,
        'total_capacity': session.total_capacity,
    })


@login_required
@role_required(User.ROLE_ADMIN)
def auto_allocate_seating(request, session_id):
    session = get_object_or_404(ExamSession, id=session_id)
    if request.method == 'POST':
        try:
            summary = auto_allocate_session(session)
            per_hall = ', '.join(f"Hall {h['hall']}: {h['seated']}" for h in summary['halls'])
            messages.success(
                request,
                f"Seated {summary['total_allocated']} student(s) across {len(summary['halls'])} hall(s) — {per_hall}."
            )
        except AllocationError as exc:
            messages.error(request, str(exc))
    return redirect('session_detail', session_id=session.id)


@login_required
@role_required(User.ROLE_ADMIN)
def download_hall_tickets(request, session_id):
    session = get_object_or_404(ExamSession, id=session_id)
    students = session.students.filter(hall__isnull=False).select_related('hall').order_by(
        'hall__hall_number', 'row', 'seat'
    )
    if not students.exists():
        messages.error(request, 'No seated students yet — allocate or upload a mapping first.')
        return redirect('session_detail', session_id=session.id)

    buffer = generate_hall_tickets_pdf(students, session)
    filename = f'hall_tickets_{session.date}_{session.shift}.pdf'.replace(' ', '_')
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@role_required(User.ROLE_ADMIN)
def assign_invigilator(request, hall_id):
    hall = get_object_or_404(Hall, id=hall_id)
    if request.method == 'POST':
        user_id = request.POST.get('invigilator_id')
        if user_id:
            hall.invigilator = get_object_or_404(User, id=user_id, role=User.ROLE_INVIGILATOR)
        else:
            hall.invigilator = None
        hall.save()
        messages.success(request, f'Hall {hall.hall_number} updated.')
    return redirect('session_detail', session_id=hall.session_id)


@login_required
@role_required(User.ROLE_ADMIN)
def toggle_session(request, session_id):
    session = get_object_or_404(ExamSession, id=session_id)
    if request.method == 'POST':
        session.is_active = not session.is_active
        session.save()
        state = 'reopened' if session.is_active else 'closed'
        messages.success(request, f'Session {state}.')
    return redirect('session_detail', session_id=session.id)


@login_required
@role_required(User.ROLE_ADMIN)
def upload_mapping(request):
    sessions = ExamSession.objects.filter(is_active=True)

    if request.method == 'POST':
        session_id = request.POST.get('session_id')
        csv_file = request.FILES.get('mapping_file')

        if not csv_file or not csv_file.name.lower().endswith('.csv'):
            messages.error(request, 'Please upload a valid CSV file.')
            return redirect('upload_mapping')

        session = get_object_or_404(ExamSession, id=session_id)

        try:
            file_data = csv_file.read().decode('utf-8-sig').splitlines()
        except UnicodeDecodeError:
            messages.error(request, 'Could not read file. Please save the CSV as UTF-8 and try again.')
            return redirect('upload_mapping')

        reader = csv.DictReader(file_data)
        columns = {c.strip() for c in (reader.fieldnames or [])}
        required_cols = {'roll_number', 'subject_code'}
        seat_cols = {'hall_number', 'row', 'seat'}

        if not required_cols.issubset(columns):
            messages.error(request, 'CSV is missing required columns: roll_number, subject_code.')
            return redirect('upload_mapping')

        # Pre-set mode: the CSV already specifies hall/row/seat for every row.
        # Roster mode: only roll_number/name/subject_code — seats come later
        # from "Auto-allocate seating" on the session page.
        preset_mode = seat_cols.issubset(columns)
        halls_by_number = {h.hall_number: h for h in session.halls.all()} if preset_mode else {}

        created, skipped_no_hall, skipped_duplicate, skipped_incomplete = 0, 0, 0, 0
        for row in reader:
            roll_number = (row.get('roll_number') or '').strip()
            subject_code = (row.get('subject_code') or '').strip()

            if not roll_number or not subject_code:
                skipped_incomplete += 1
                continue

            if Student.objects.filter(session=session, roll_number=roll_number, subject_code=subject_code).exists():
                skipped_duplicate += 1
                continue

            hall_obj, row_label, seat_label = None, '', ''
            if preset_mode:
                hall_number = (row.get('hall_number') or '').strip()
                if not hall_number:
                    skipped_incomplete += 1
                    continue
                hall_obj = halls_by_number.get(hall_number)
                if not hall_obj:
                    skipped_no_hall += 1
                    continue
                row_label = (row.get('row') or '').strip()
                seat_label = (row.get('seat') or '').strip()

            Student.objects.create(
                session=session,
                roll_number=roll_number,
                name=(row.get('name') or '').strip(),
                subject_code=subject_code,
                exam_time=(row.get('exam_time') or '').strip(),
                hall=hall_obj,
                row=row_label,
                seat=seat_label,
            )
            created += 1

        if preset_mode:
            summary = f'Imported {created} student(s) with fixed seating and generated QR codes.'
        else:
            summary = f'Imported {created} student(s) to the roster. Go to the session page to auto-allocate seating.'

        extras = []
        if skipped_no_hall:
            extras.append(f'{skipped_no_hall} skipped (unknown hall)')
        if skipped_duplicate:
            extras.append(f'{skipped_duplicate} skipped (already exists)')
        if skipped_incomplete:
            extras.append(f'{skipped_incomplete} skipped (missing fields)')
        if extras:
            summary += ' — ' + ', '.join(extras) + '.'

        messages.success(request, summary)
        return redirect('session_detail', session_id=session.id)

    return render(request, 'admin/upload_mapping.html', {'sessions': sessions})


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
    active_hall = Hall.objects.filter(invigilator=request.user, session__is_active=True).first()
    roster = []
    if active_hall:
        roster = active_hall.students.order_by('row', 'seat')
    return render(request, 'invigilator/dashboard.html', {'active_hall': active_hall, 'roster': roster})


@login_required
@role_required(User.ROLE_INVIGILATOR)
def hall_roster_json(request):
    """Lightweight polling endpoint so the roster panel can refresh live
    without restarting the QR scanner (a full page reload would kill the
    camera stream)."""
    active_hall = Hall.objects.filter(invigilator=request.user, session__is_active=True).first()
    if not active_hall:
        return JsonResponse({'students': []})

    students = active_hall.students.order_by('row', 'seat').values(
        'id', 'roll_number', 'name', 'row', 'seat', 'is_present'
    )
    present_count = sum(1 for s in students if s['is_present'])
    return JsonResponse({
        'students': list(students),
        'present_count': present_count,
        'total_count': len(students),
    })


@login_required
def verify_seat(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'invalid_method'}, status=405)
    if request.user.role != User.ROLE_INVIGILATOR:
        return JsonResponse({'status': 'error', 'message': 'Not authorized.'}, status=403)

    try:
        data = json.loads(request.body)
        qr_data = data.get('qr_data')
        parsed = json.loads(qr_data) if isinstance(qr_data, str) else (qr_data or {})

        roll_number = parsed.get('roll_number')
        subject_code = parsed.get('subject_code')

        active_hall = Hall.objects.filter(invigilator=request.user, session__is_active=True).first()
        if not active_hall:
            return JsonResponse({'status': 'error', 'message': 'No active hall assigned to you.'})

        student = Student.objects.filter(
            session=active_hall.session, roll_number=roll_number, subject_code=subject_code
        ).first()

        if not student:
            return JsonResponse({'status': 'error', 'message': 'Student not found in this session.'})

        if student.hall_id != active_hall.id:
            return JsonResponse({
                'status': 'warning',
                'message': f'Wrong hall — this student belongs in Hall {student.hall.hall_number}.',
                'student_id': student.id,
            })

        if student.is_present:
            return JsonResponse({
                'status': 'warning',
                'message': f'Already checked in: {student.name or student.roll_number} '
                           f'(Row {student.row}, Seat {student.seat}).',
                'student_id': student.id,
            })

        student.is_present = True
        student.checked_in_at = timezone.now()
        student.save(update_fields=['is_present', 'checked_in_at'])

        return JsonResponse({
            'status': 'success',
            'message': f'Verified: {student.name or student.roll_number} — Row {student.row}, Seat {student.seat}.',
            'student_id': student.id,
        })

    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'status': 'error', 'message': 'Malformed QR payload.'})
    except Exception as exc:  # keep the scanner usable even on unexpected errors
        return JsonResponse({'status': 'error', 'message': f'Unexpected error: {exc}'})


@login_required
@role_required(User.ROLE_INVIGILATOR)
def raise_alert(request):
    active_hall = Hall.objects.filter(invigilator=request.user, session__is_active=True).first()
    scanned_students = active_hall.students.filter(is_present=True).order_by('row', 'seat') if active_hall else []

    if request.method == 'POST':
        if not active_hall:
            messages.error(request, 'You have no active hall assignment.')
            return redirect('invigilator_dashboard')

        alert_type = request.POST.get('alert_type')
        student_id = request.POST.get('student_id')
        notes = request.POST.get('notes', '').strip()

        student = None
        row = seat = ''
        if student_id:
            student = Student.objects.filter(id=student_id, session=active_hall.session).first()
            if student:
                row, seat = student.row, student.seat
        else:
            row = request.POST.get('row', '').strip()
            seat = request.POST.get('seat', '').strip()

        if alert_type not in dict(Alert.ALERT_TYPES):
            messages.error(request, 'Please choose a valid alert type.')
            return render(request, 'invigilator/raise_alert.html', {
                'active_hall': active_hall,
                'alert_types': Alert.ALERT_TYPES,
                'student': student,
                'scanned_students': scanned_students,
            })

        Alert.objects.create(
            session=active_hall.session,
            alert_type=alert_type,
            hall=active_hall,
            invigilator=request.user,
            student=student,
            row=row,
            seat=seat,
            notes=notes,
        )
        messages.success(request, 'Alert raised. The control room has been notified.')
        return redirect('invigilator_dashboard')

    student_id = request.GET.get('student_id')
    student = None
    if student_id and active_hall:
        student = Student.objects.filter(id=student_id, session=active_hall.session).first()

    return render(request, 'invigilator/raise_alert.html', {
        'active_hall': active_hall,
        'alert_types': Alert.ALERT_TYPES,
        'student': student,
        'scanned_students': scanned_students,
    })


# ---------------------------------------------------------------------------
# Control room
# ---------------------------------------------------------------------------

@login_required
@role_required(User.ROLE_CONTROL_ROOM, User.ROLE_ADMIN)
def control_room(request):
    alerts = Alert.objects.filter(session__is_active=True).select_related('hall', 'student', 'invigilator')
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
    sessions_list = ExamSession.objects.all().prefetch_related('alert_set')
    paginator = Paginator(sessions_list, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'control_room/reports.html', {'page_obj': page_obj})


@login_required
@role_required(User.ROLE_CONTROL_ROOM, User.ROLE_ADMIN)
def export_session_report(request, session_id):
    session = get_object_or_404(ExamSession, id=session_id)
    response = HttpResponse(content_type='text/csv')
    filename = f'invisense_report_{session.date}_{session.shift}.csv'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(['Timestamp', 'Hall', 'Alert Type', 'Status', 'Row', 'Seat', 'Invigilator', 'Notes'])
    for alert in session.alert_set.select_related('hall', 'invigilator').order_by('timestamp'):
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
