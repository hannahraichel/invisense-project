import json
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import (
    Alert, Attendance, ExamHall, ExamSession,
    ExamStudentAssignment, HallTicket, Student, User,
)
from .views import get_current_invigilator_context

TOKEN_SALT = 'invisense-invigilator-api-token'
TOKEN_MAX_AGE_SECONDS = 7 * 24 * 60 * 60  # 7 days


def get_invigilator_from_request(request):
    """
    Resolves the authenticated invigilator from either:
    1. HTTP Authorization header: 'Bearer <token>' or 'Token <token>'
    2. Django session authentication (cookies)
    """
    auth_header = request.headers.get('Authorization') or request.META.get('HTTP_AUTHORIZATION', '')
    if auth_header:
        parts = auth_header.strip().split()
        if len(parts) == 2 and parts[0].lower() in ('bearer', 'token'):
            raw_token = parts[1]
            signer = TimestampSigner(salt=TOKEN_SALT)
            try:
                user_id_str = signer.unsign(raw_token, max_age=TOKEN_MAX_AGE_SECONDS)
                user_id = int(user_id_str)
                user = User.objects.filter(id=user_id, role=User.ROLE_INVIGILATOR, is_active=True).first()
                if user:
                    return user
            except (BadSignature, SignatureExpired, ValueError):
                return None

    if getattr(request, 'user', None) and request.user.is_authenticated:
        if request.user.role == User.ROLE_INVIGILATOR and request.user.is_active:
            return request.user

    return None


def invigilator_api_required(view_func):
    """Decorator ensuring request is made by an authenticated invigilator."""
    def wrapped(request, *args, **kwargs):
        user = get_invigilator_from_request(request)
        if not user:
            return JsonResponse({
                'status': 'error',
                'message': 'Authentication required. Please log in as an Invigilator.'
            }, status=401)
        request.api_user = user
        return view_func(request, *args, **kwargs)
    wrapped.__name__ = view_func.__name__
    return wrapped


@csrf_exempt
def api_invigilator_login(request):
    """
    API endpoint for native Android app login.
    POST JSON: {"username": "...", "password": "..."}
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed.'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        data = request.POST

    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username or not password:
        return JsonResponse({
            'status': 'error',
            'message': 'Please provide both username and password.'
        }, status=400)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid username or password.'
        }, status=401)

    if not user.is_active:
        return JsonResponse({
            'status': 'error',
            'message': 'This account has been deactivated. Please contact the administrator.'
        }, status=403)

    if user.role != User.ROLE_INVIGILATOR:
        return JsonResponse({
            'status': 'error',
            'message': 'Access denied. Only Invigilators can log in through the Invigilator app.'
        }, status=403)

    # Generate secure token
    signer = TimestampSigner(salt=TOKEN_SALT)
    token = signer.sign(str(user.id))

    # Also log in session if cookie-capable
    login(request, user)

    return JsonResponse({
        'status': 'success',
        'message': 'Login successful.',
        'token': token,
        'user': {
            'id': user.id,
            'username': user.username,
            'name': user.get_full_name() or user.username,
            'full_name': user.get_full_name() or user.username,
            'role': user.role,
        }
    })


@csrf_exempt
@invigilator_api_required
def api_invigilator_logout(request):
    """Invalidates session on logout."""
    if hasattr(request, 'session'):
        request.session.flush()
    logout(request)
    return JsonResponse({
        'status': 'success',
        'message': 'Logged out successfully.'
    })


@invigilator_api_required
def api_invigilator_dashboard(request):
    """
    Dashboard API returning current active exam session (if within 3-hour window)
    and upcoming exams for this invigilator.
    """
    user = request.api_user
    current = get_current_invigilator_context(user)
    now = timezone.localtime()

    current_data = None
    if current:
        session = current.exam_session
        hall = current.hall
        assigned_count = current.assigned_count
        present_count = current.present_count
        scan_start_dt = session.scan_window_start_dt()

        current_data = {
            'exam_session_id': session.id,
            'exam_hall_id': current.id,
            'subject': session.subject,
            'period_name': session.exam_period.name,
            'exam_date': session.exam_date.isoformat(),
            'start_time': session.start_time.strftime('%I:%M %p'),
            'end_time': session.end_time.strftime('%I:%M %p'),
            'start_time_display': session.start_time.strftime('%I:%M %p'),
            'end_time_display': session.end_time.strftime('%I:%M %p'),
            'hall_id': hall.id,
            'hall_name': hall.name,
            'capacity_allocated': current.capacity_allocated,
            'total_students': assigned_count,
            'total_assigned': assigned_count,
            'present_count': present_count,
            'absent_count': max(0, assigned_count - present_count),
            'is_scanning_open': session.is_currently_active(now),
            'scan_open': session.is_currently_active(now),
            'scan_window_start': scan_start_dt.isoformat(),
            'scan_window_start_display': scan_start_dt.strftime('%I:%M %p'),
            'scan_opens_at': scan_start_dt.strftime('%I:%M %p'),
            'scan_window_note': f"Scanning opens 3 hours before start time (at {scan_start_dt.strftime('%I:%M %p')})",
            'display_status': session.display_status,
        }

    # Check if there is an active exam right now
    active_eh = current

    # Find the most recently ended exam for this invigilator (ended today or previously)
    past_candidates = ExamHall.objects.filter(
        invigilator=user,
        exam_session__status__in=ExamSession.LIVE_STATUSES,
        exam_session__exam_date__lte=now.date(),
    ).select_related('exam_session', 'hall').order_by('-exam_session__exam_date', '-exam_session__end_time')

    most_recent_ended = None
    for peh in past_candidates:
        if peh.exam_session.has_passed(now):
            most_recent_ended = peh
            break

    # Upcoming exams (strictly in the future)
    upcoming_candidates = ExamHall.objects.filter(
        invigilator=user,
        exam_session__status__in=ExamSession.LIVE_STATUSES,
        exam_session__exam_date__gte=now.date(),
    ).select_related('exam_session', 'hall').order_by('exam_session__exam_date', 'exam_session__start_time')

    upcoming_list = []
    future_candidates = []
    for eh in upcoming_candidates:
        s = eh.exam_session
        if active_eh and eh.id == active_eh.id:
            continue
        if s.has_passed(now):
            continue
        future_candidates.append(eh)
        scan_dt = s.scan_window_start_dt()
        is_open = s.is_currently_active(now)
        upcoming_list.append({
            'exam_session_id': s.id,
            'exam_hall_id': eh.id,
            'subject': s.subject,
            'period_name': s.exam_period.name,
            'exam_date': s.exam_date.isoformat(),
            'start_time': s.start_time.strftime('%I:%M %p'),
            'end_time': s.end_time.strftime('%I:%M %p'),
            'start_time_display': s.start_time.strftime('%I:%M %p'),
            'end_time_display': s.end_time.strftime('%I:%M %p'),
            'hall_id': eh.hall.id,
            'hall_name': eh.hall.name,
            'capacity_allocated': eh.capacity_allocated,
            'total_students': eh.assigned_count,
            'total_assigned': eh.assigned_count,
            'present_count': eh.present_count,
            'is_scanning_open': is_open,
            'scan_open': is_open,
            'scan_window_start': scan_dt.isoformat(),
            'scan_window_start_display': scan_dt.strftime('%I:%M %p'),
            'scan_opens_at': scan_dt.strftime('%I:%M %p'),
            'scan_window_note': f"Scanning opens at {scan_dt.strftime('%I:%M %p')} (3 hours before exam)",
            'display_status': s.display_status,
        })

    # Prepare response for Android app
    # Priority for display target:
    # 1. Currently active exam
    # 2. Upcoming exam (future)
    # 3. Most recently ended exam
    target_exam = active_eh or (future_candidates[0] if future_candidates else most_recent_ended)
    has_active_exam = False
    scan_open = False
    is_ended = False
    exam_payload = None
    msg = "No exam assigned right now."

    if target_exam:
        s = target_exam.exam_session
        h = target_exam.hall
        scan_dt = s.scan_window_start_dt()
        is_open = s.is_currently_active(now)
        is_ended = s.has_passed(now)

        has_active_exam = is_open
        scan_open = is_open

        exam_payload = {
            'subject': s.subject,
            'exam_date': s.exam_date.isoformat(),
            'start_time': s.start_time.strftime('%I:%M %p'),
            'end_time': s.end_time.strftime('%I:%M %p'),
            'hall_name': h.name,
            'scan_opens_at': scan_dt.strftime('%I:%M %p'),
            'present_count': target_exam.present_count,
            'total_assigned': target_exam.assigned_count,
            'is_ended': is_ended,
            'is_scanning_open': is_open,
        }

        if is_open:
            msg = "Scanning is OPEN"
        elif is_ended:
            msg = "Exam has ended. Scanning and alert raising are closed."
        else:
            msg = f"Scanning opens at {scan_dt.strftime('%I:%M %p')} (3 hours before start)"

    # Teacher's flagged alerts history
    my_alerts = Alert.objects.filter(invigilator=user).select_related(
        'student', 'hall', 'exam_session'
    ).order_by('-timestamp')[:20]

    recent_alerts = []
    for a in my_alerts:
        student_name = a.student.name if (a.student and a.student.name) else (a.student.roll_number if a.student else None)
        seat_parts = []
        if a.row: seat_parts.append(f"Row {a.row}")
        if a.seat: seat_parts.append(f"Seat {a.seat}")
        seat_str = ", ".join(seat_parts) if seat_parts else "-"

        recent_alerts.append({
            'id': a.id,
            'alert_type': a.alert_type,
            'alert_type_display': a.get_alert_type_display(),
            'student_name': student_name,
            'roll_number': a.student.roll_number if a.student else None,
            'seat': seat_str,
            'hall_name': a.hall.name,
            'status': a.status,
            'status_display': a.get_status_display(),
            'timestamp_display': a.timestamp.strftime('%H:%M · %b %d'),
            'notes': a.notes or '',
        })

    return JsonResponse({
        'status': 'success',
        'has_active_exam': has_active_exam,
        'scan_open': scan_open,
        'message': msg,
        'exam': exam_payload,
        'server_time': now.isoformat(),
        'invigilator': {
            'id': user.id,
            'username': user.username,
            'name': user.get_full_name() or user.username,
            'full_name': user.get_full_name() or user.username,
        },
        'current_exam': current_data,
        'upcoming_exams': upcoming_list,
        'recent_alerts': recent_alerts,
    })


@invigilator_api_required
def api_invigilator_roster(request):
    """
    Returns student roster for the current active exam hall.
    """
    user = request.api_user
    now = timezone.localtime()
    target_eh = get_current_invigilator_context(user)

    if not target_eh:
        # Check if caller specified a specific exam_hall_id or exam_session_id
        session_id = request.GET.get('exam_session_id')
        if session_id:
            target_eh = ExamHall.objects.filter(
                invigilator=user, exam_session_id=session_id
            ).select_related('exam_session', 'hall').first()

    if not target_eh:
        # Fallback to the most recent exam (whether past or future) so teacher can always review their roster
        target_eh = ExamHall.objects.filter(
            invigilator=user,
            exam_session__status__in=ExamSession.LIVE_STATUSES,
        ).select_related('exam_session', 'hall').order_by('-exam_session__exam_date', '-exam_session__start_time').first()

    if not target_eh:
        return JsonResponse({
            'status': 'no_active_exam',
            'message': 'No exam roster assigned to your account.',
            'students': [],
            'present_count': 0,
            'total_count': 0,
        })

    assignments = ExamStudentAssignment.objects.filter(
        exam_session=target_eh.exam_session, hall=target_eh.hall
    ).select_related('student').order_by('row', 'seat', 'student__roll_number')

    attendance_map = dict(
        Attendance.objects.filter(exam_session=target_eh.exam_session, hall=target_eh.hall)
        .values_list('student_id', 'scanned_at')
    )

    students = []
    for a in assignments:
        scanned_at = attendance_map.get(a.student_id)
        students.append({
            'id': a.student.id,
            'roll_number': a.student.roll_number,
            'name': a.student.name or a.student.roll_number,
            'course': a.student.course or '',
            'row': a.row or '',
            'seat': a.seat or '',
            'is_present': a.student_id in attendance_map,
            'scanned_at': scanned_at.strftime('%I:%M:%S %p') if scanned_at else None,
        })

    return JsonResponse({
        'status': 'success',
        'exam_info': {
            'subject': target_eh.exam_session.subject,
            'hall_name': target_eh.hall.name,
            'exam_date': target_eh.exam_session.exam_date.isoformat(),
            'start_time': target_eh.exam_session.start_time.strftime('%I:%M %p'),
            'end_time': target_eh.exam_session.end_time.strftime('%I:%M %p'),
            'is_ended': target_eh.exam_session.has_passed(now),
        },
        'students': students,
        'present_count': len(attendance_map),
        'total_count': len(students),
    })


@csrf_exempt
@invigilator_api_required
def api_invigilator_verify_qr(request):
    """
    QR verification endpoint for mobile scanner:
    Enforces that scanning is open (3 hours before exam start until end time).
    Accepts JSON: {"qr_data": "<qr_token>"}
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed.'}, status=405)

    user = request.api_user
    current = get_current_invigilator_context(user)
    now = timezone.localtime()

    if not current:
        # Check upcoming exam to provide helpful timing feedback
        upcoming = ExamHall.objects.filter(
            invigilator=user,
            exam_session__status__in=ExamSession.LIVE_STATUSES,
            exam_session__exam_date__gte=now.date(),
        ).select_related('exam_session').order_by('exam_session__exam_date', 'exam_session__start_time').first()

        if upcoming and now < upcoming.exam_session.scan_window_start_dt():
            opens_at = upcoming.exam_session.scan_window_start_dt().strftime("%I:%M %p")
            return JsonResponse({
                'status': 'error',
                'message': f'Scanning is locked. Scanning opens 3 hours before exam start time (at {opens_at}).',
            }, status=400)

        return JsonResponse({
            'status': 'error',
            'message': 'No active exam session found for your account right now.',
        }, status=400)

    try:
        data = json.loads(request.body.decode('utf-8'))
        qr_token = (data.get('qr_data') or '').strip()
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
        qr_token = (request.POST.get('qr_data') or '').strip()

    if not qr_token:
        return JsonResponse({'status': 'error', 'message': 'Empty QR code payload.'}, status=400)

    hall_ticket = HallTicket.objects.filter(qr_token=qr_token).select_related('student').first()
    if not hall_ticket:
        return JsonResponse({'status': 'error', 'message': 'Invalid hall ticket QR code.'}, status=404)

    student = hall_ticket.student
    if not student.is_active:
        return JsonResponse({
            'status': 'error',
            'message': f'Student {student.roll_number} is deactivated on this roster.',
            'student_id': student.id,
        }, status=400)

    assignment = ExamStudentAssignment.objects.filter(
        exam_session=current.exam_session, student=student
    ).select_related('hall').first()

    if not assignment:
        return JsonResponse({
            'status': 'error',
            'message': f'Student {student.name or student.roll_number} is not assigned to this exam session.',
            'student_id': student.id,
        }, status=400)

    if assignment.hall_id != current.hall_id:
        return JsonResponse({
            'status': 'warning',
            'message': f'Wrong section: {student.roll_number} is assigned to {assignment.hall.name}, not {current.hall.name}.',
            'student_id': student.id,
            'student': {
                'id': student.id,
                'roll_number': student.roll_number,
                'name': student.name,
                'assigned_hall': assignment.hall.name,
                'row': assignment.row,
                'seat': assignment.seat,
            }
        })

    attendance, created = Attendance.objects.get_or_create(
        exam_session=current.exam_session,
        student=student,
        defaults={'hall': current.hall, 'invigilator': user},
    )

    if not created:
        return JsonResponse({
            'status': 'warning',
            'message': f'Already marked: {student.name or student.roll_number} was previously verified (Row {assignment.row}, Seat {assignment.seat}).',
            'student_id': student.id,
            'student': {
                'id': student.id,
                'roll_number': student.roll_number,
                'name': student.name,
                'row': assignment.row,
                'seat': assignment.seat,
                'scanned_at': attendance.scanned_at.strftime('%I:%M:%S %p'),
            }
        })

    return JsonResponse({
        'status': 'success',
        'message': f'Verified: {student.name or student.roll_number} — Row {assignment.row}, Seat {assignment.seat}.',
        'student_id': student.id,
        'student': {
            'id': student.id,
            'roll_number': student.roll_number,
            'name': student.name,
            'row': assignment.row,
            'seat': assignment.seat,
            'scanned_at': attendance.scanned_at.strftime('%I:%M:%S %p'),
        }
    })


@csrf_exempt
@invigilator_api_required
def api_invigilator_raise_alert(request):
    """
    API endpoint to raise an incident or assistance alert from mobile.
    POST JSON: {"alert_type": "...", "student_id": ..., "row": "...", "seat": "...", "notes": "..."}
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed.'}, status=405)

    user = request.api_user
    current = get_current_invigilator_context(user)
    if not current:
        now = timezone.localtime()
        # Check if they had an exam today that ended
        past = ExamHall.objects.filter(
            invigilator=user,
            exam_session__status__in=ExamSession.LIVE_STATUSES,
            exam_session__exam_date__lte=now.date(),
        ).select_related('exam_session').order_by('-exam_session__exam_date', '-exam_session__end_time').first()

        if past and past.exam_session.has_passed(now):
            msg = 'You cannot raise an alert after the exam has ended.'
        else:
            msg = 'You cannot raise an alert: you have no active exam session right now.'

        return JsonResponse({
            'status': 'error',
            'message': msg
        }, status=400)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        data = request.POST

    alert_type = data.get('alert_type')
    student_id = data.get('student_id')
    row = (data.get('row') or '').strip()
    seat = (data.get('seat') or '').strip()
    notes = (data.get('notes') or '').strip()

    if alert_type not in dict(Alert.ALERT_TYPES):
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid alert type selected.'
        }, status=400)

    student = None
    if student_id:
        student = Student.objects.filter(id=student_id, exam_period=current.exam_session.exam_period).first()
        if student and (not row or not seat):
            assignment = ExamStudentAssignment.objects.filter(
                exam_session=current.exam_session, student=student
            ).first()
            if assignment:
                row = row or assignment.row
                seat = seat or assignment.seat

    alert = Alert.objects.create(
        exam_session=current.exam_session,
        alert_type=alert_type,
        hall=current.hall,
        invigilator=user,
        student=student,
        row=row,
        seat=seat,
        notes=notes,
    )

    return JsonResponse({
        'status': 'success',
        'message': 'Alert submitted successfully. Control room notified.',
        'alert_id': alert.id,
    })


@invigilator_api_required
def api_invigilator_alert_types(request):
    """Returns available alert types for the mobile app spinner."""
    return JsonResponse({
        'status': 'success',
        'alert_types': [{'code': code, 'label': label} for code, label in Alert.ALERT_TYPES]
    })
