"""
InviSense data model.

Key design decisions from this revision:

- Hall is global (institution-wide), not owned by one ExamPeriod. MCA and
  IMCA stay administratively separate (separate ExamPeriod, roster,
  timetable) but can physically share a room — that only works if Hall
  isn't scoped to a period.
- ExamHall carries a `capacity_allocated` — the HOD's explicit decision
  about how many of that room's seats this particular exam gets. Two
  ExamHall rows pointing at the same Hall with overlapping times must not
  let their allocations add up past the room's real capacity.
- Nothing here is ever hard-deleted once it has operational history
  (assignments, attendance, alerts). Every major entity gets `is_active`
  instead, and destructive deletes are blocked in the view layer when
  dependencies exist — see core/validators.py.
"""

import secrets
from io import BytesIO

import qrcode
from django.contrib.auth.models import AbstractUser
from django.core.files import File
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """Custom user carrying an application role used for access control."""

    ROLE_ADMIN = 'ADMIN'
    ROLE_INVIGILATOR = 'INVIGILATOR'
    ROLE_CONTROL_ROOM = 'CONTROL_ROOM'

    ROLE_CHOICES = (
        (ROLE_ADMIN, 'Admin'),
        (ROLE_INVIGILATOR, 'Invigilator'),
        (ROLE_CONTROL_ROOM, 'Control Room Staff'),
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_INVIGILATOR)

    class Meta:
        ordering = ['username']

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"


class Hall(models.Model):
    """A physical room. Global and shared across every exam period —
    MCA and IMCA exams can both use "CLC 306" without knowing about each
    other, as long as the combined seat allocation never exceeds capacity.
    """
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_STOPPED = 'STOPPED'
    STATUS_CHOICES = (
        (STATUS_ACTIVE, 'Active'),
        (STATUS_STOPPED, 'Stopped'),
    )

    name = models.CharField(max_length=50, unique=True)  # displayed exactly as typed, e.g. "CLC 306"
    capacity = models.PositiveIntegerField(default=30)
    seats_per_row = models.PositiveIntegerField(default=6)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def is_stopped(self):
        return self.status == self.STATUS_STOPPED

    @property
    def has_dependencies(self):
        return self.exam_halls.exists()


class ExamPeriod(models.Model):
    """A whole examination cycle — e.g. 'First Internal Exam - MCA'. MCA
    and IMCA are always separate ExamPeriods: separate roster, separate
    timetable, separate exam sessions. Only the physical halls are shared.
    """
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_STOPPED = 'STOPPED'
    STATUS_ARCHIVED = 'ARCHIVED'
    STATUS_CHOICES = (
        (STATUS_ACTIVE, 'Active'),
        (STATUS_STOPPED, 'Stopped'),
        (STATUS_ARCHIVED, 'Archived'),
    )

    name = models.CharField(max_length=150)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def is_active(self):
        return self.status == self.STATUS_ACTIVE

    @property
    def student_count(self):
        return self.students.filter(is_active=True).count()

    @property
    def session_count(self):
        return self.exam_sessions.exclude(status=ExamSession.STATUS_CANCELLED).count()

    @property
    def has_dependencies(self):
        return self.exam_sessions.exists() or self.students.exists()


class Student(models.Model):
    """The roster — uploaded once per exam period, independent of any
    single exam. A student's hall ticket/QR is permanent; only their
    per-exam hall assignment changes."""

    exam_period = models.ForeignKey(ExamPeriod, on_delete=models.CASCADE, related_name='students')
    roll_number = models.CharField(max_length=50)
    name = models.CharField(max_length=100, blank=True, default='')
    course = models.CharField(max_length=50, blank=True, default='')  # e.g. MCA, iMCA
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['roll_number']
        unique_together = ('exam_period', 'roll_number')
        indexes = [
            models.Index(fields=['exam_period', 'roll_number']),
            models.Index(fields=['roll_number']),  # supports cross-period conflict lookups
        ]

    def __str__(self):
        return f"{self.roll_number} — {self.name or 'Unnamed'}"

    @property
    def has_dependencies(self):
        return self.assignments.exists() or self.attendances.exists()

    @property
    def is_hall_ticket_ready(self):
        """Every non-cancelled, non-stopped exam session in this student's
        period must have a seat assignment before their one hall ticket
        unlocks."""
        required = self.exam_period.exam_sessions.exclude(
            status__in=[ExamSession.STATUS_CANCELLED, ExamSession.STATUS_STOPPED]
        )
        if not required.exists():
            return False
        assigned_session_ids = set(self.assignments.values_list('exam_session_id', flat=True))
        return all(s.id in assigned_session_ids for s in required)


class HallTicket(models.Model):
    """One permanent QR per student for the whole exam period.

    The QR encodes ONLY an opaque random token — never a subject, hall,
    seat, or date — so the same physical ticket is valid for every exam in
    the period. The backend resolves everything else at scan time.
    """
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='hall_ticket')
    qr_token = models.CharField(max_length=64, unique=True, editable=False)
    qr_code = models.ImageField(upload_to='qrcodes/', blank=True)

    def __str__(self):
        return f"Hall ticket for {self.student.roll_number}"

    def save(self, *args, **kwargs):
        if not self.qr_token:
            self.qr_token = secrets.token_urlsafe(24)
        if not self.qr_code:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(self.qr_token)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            self.qr_code.save(f'qr_{self.qr_token[:14]}.png', File(buffer), save=False)
        super().save(*args, **kwargs)


class ExamSession(models.Model):
    """One specific exam: a subject on a specific date, within a specific
    time window. Multiple halls can run the SAME exam session at once (see
    ExamHall) — they are not separate exams."""

    STATUS_DRAFT = 'DRAFT'
    STATUS_SCHEDULED = 'SCHEDULED'
    STATUS_READY = 'READY'
    STATUS_STOPPED = 'STOPPED'
    STATUS_ARCHIVED = 'ARCHIVED'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_READY, 'Ready'),
        (STATUS_STOPPED, 'Stopped'),
        (STATUS_ARCHIVED, 'Archived'),
        (STATUS_CANCELLED, 'Cancelled'),
    )
    # Statuses that still represent a live, usable exam (as opposed to a
    # dead end like cancelled/archived/stopped).
    LIVE_STATUSES = (STATUS_DRAFT, STATUS_SCHEDULED, STATUS_READY)

    SCAN_WINDOW_HOURS_BEFORE = 3

    exam_period = models.ForeignKey(ExamPeriod, on_delete=models.CASCADE, related_name='exam_sessions')
    subject = models.CharField(max_length=100)
    exam_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['exam_date', 'start_time']
        indexes = [models.Index(fields=['exam_date', 'status'])]

    def __str__(self):
        return f"{self.subject} — {self.exam_date} ({self.start_time}\u2013{self.end_time})"

    def _aware(self, t):
        """Combine exam_date + a time-of-day into an aware datetime in the
        app's configured timezone (settings.TIME_ZONE) — never the
        browser's timezone, per the institutional-timezone requirement."""
        naive = timezone.datetime.combine(self.exam_date, t)
        return timezone.make_aware(naive, timezone.get_current_timezone())

    def has_passed(self, at=None):
        """True once the exam's own end time is in the past."""
        at = at or timezone.localtime()
        return self._aware(self.end_time) < at

    def scan_window_start_dt(self):
        return self._aware(self.start_time) - timezone.timedelta(hours=self.SCAN_WINDOW_HOURS_BEFORE)

    def is_currently_active(self, at=None):
        """True only while this exam's 3-hour-early scanning window is
        open AND it hasn't been stopped/cancelled/archived."""
        at = at or timezone.localtime()
        if self.status not in self.LIVE_STATUSES:
            return False
        return self.scan_window_start_dt() <= at <= self._aware(self.end_time)

    @property
    def assigned_count(self):
        return self.assignments.count()

    @property
    def present_count(self):
        return self.attendances.count()

    @property
    def pending_alert_count(self):
        return self.alerts.filter(status=Alert.STATUS_PENDING).count()

    @property
    def unassigned_students(self):
        assigned_ids = self.assignments.values_list('student_id', flat=True)
        return self.exam_period.students.filter(is_active=True).exclude(id__in=assigned_ids)

    @property
    def has_dependencies(self):
        return self.assignments.exists() or self.attendances.exists() or self.alerts.exists()

    @property
    def display_status(self):
        """A read-only, informational label layered on top of the stored
        status — e.g. a READY exam whose end time is already in the past
        reads as 'Completed' without needing a background job to flip it."""
        if self.status in (self.STATUS_CANCELLED, self.STATUS_STOPPED, self.STATUS_ARCHIVED):
            return self.get_status_display()
        if self.has_passed():
            return 'Completed'
        return self.get_status_display()


class ExamHall(models.Model):
    """Which halls are running a given exam session, how many of that
    hall's seats are reserved for this exam (the HOD's call), and who's
    invigilating it."""

    exam_session = models.ForeignKey(ExamSession, on_delete=models.CASCADE, related_name='exam_halls')
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE, related_name='exam_halls')
    capacity_allocated = models.PositiveIntegerField(
        help_text="How many of this hall's seats are reserved for this exam. "
                   "Other exams can use the remaining seats at an overlapping time."
    )
    invigilator = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='invigilating_halls',
        limit_choices_to={'role': User.ROLE_INVIGILATOR},
    )

    class Meta:
        unique_together = ('exam_session', 'hall')
        ordering = ['hall__name']

    def __str__(self):
        return f"{self.hall.name} for {self.exam_session}"

    @property
    def assigned_count(self):
        return self.exam_session.assignments.filter(hall=self.hall).count()

    @property
    def present_count(self):
        return self.exam_session.attendances.filter(hall=self.hall).count()

    @property
    def has_dependencies(self):
        return self.assigned_count > 0


class ExamStudentAssignment(models.Model):
    """Which hall a specific student must sit in for a specific exam
    session. Deliberately NOT stored on Student — the same student can (and
    routinely will) have a different hall for every exam in the period."""

    exam_session = models.ForeignKey(ExamSession, on_delete=models.CASCADE, related_name='assignments')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='assignments')
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE, related_name='assignments')
    row = models.CharField(max_length=10, blank=True, default='')
    seat = models.CharField(max_length=10, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('exam_session', 'student')
        ordering = ['hall__name', 'row', 'seat']
        indexes = [models.Index(fields=['exam_session', 'student'])]

    def __str__(self):
        return f"{self.student.roll_number} \u2192 {self.hall.name} for {self.exam_session}"


class Attendance(models.Model):
    """One row per (exam_session, student) — the unique_together is what
    makes duplicate attendance for the same exam impossible at the
    database level, not just in view logic."""

    STATUS_PRESENT = 'PRESENT'
    STATUS_CHOICES = ((STATUS_PRESENT, 'Present'),)

    exam_session = models.ForeignKey(ExamSession, on_delete=models.CASCADE, related_name='attendances')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE, related_name='attendances')
    invigilator = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='marked_attendances'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PRESENT)
    scanned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('exam_session', 'student')
        ordering = ['-scanned_at']
        indexes = [models.Index(fields=['exam_session', 'student'])]

    def __str__(self):
        return f"{self.student.roll_number} present for {self.exam_session}"


class Alert(models.Model):
    TYPE_SUSPICIOUS = 'SUSPICIOUS_ACTIVITY'
    TYPE_SUPERVISOR = 'NEED_SUPERVISOR'
    TYPE_MEDICAL = 'MEDICAL_EMERGENCY'
    TYPE_OTHER = 'OTHER'

    ALERT_TYPES = (
        (TYPE_SUSPICIOUS, 'Suspicious Activity'),
        (TYPE_SUPERVISOR, 'Need Supervisor'),
        (TYPE_MEDICAL, 'Medical Emergency'),
        (TYPE_OTHER, 'Other'),
    )

    STATUS_PENDING = 'PENDING'
    STATUS_ACK = 'ACKNOWLEDGED'
    STATUS_RESOLVED = 'RESOLVED'

    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACK, 'Acknowledged'),
        (STATUS_RESOLVED, 'Resolved'),
    )

    exam_session = models.ForeignKey(ExamSession, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPES)
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    invigilator = models.ForeignKey(User, on_delete=models.CASCADE)

    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True)
    row = models.CharField(max_length=10, blank=True, default='')
    seat = models.CharField(max_length=10, blank=True, default='')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    timestamp = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['exam_session', 'status']),
        ]

    def __str__(self):
        return f"{self.get_alert_type_display()} in {self.hall.name}"


class AuditLog(models.Model):
    """A lightweight activity trail for administrative actions that
    destroy or deactivate something — stop/delete/confirm operations —
    so a production system doesn't lose "who did what, when" just because
    a record was deactivated rather than deleted."""

    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_entries')
    action = models.CharField(max_length=100)  # e.g. "stopped", "deleted", "confirmed_allocation"
    entity_type = models.CharField(max_length=50)  # e.g. "ExamPeriod", "Hall"
    entity_repr = models.CharField(max_length=200)  # human-readable snapshot at the time
    details = models.TextField(blank=True, default='')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} {self.entity_type} \u2014 {self.entity_repr}"

    @classmethod
    def record(cls, actor, action, entity, details=''):
        cls.objects.create(
            actor=actor, action=action,
            entity_type=type(entity).__name__, entity_repr=str(entity),
            details=details,
        )
