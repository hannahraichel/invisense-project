"""
InviSense data model — rebuilt around the "one student, one permanent QR,
many exams" architecture.

The key idea: a student's identity (Student/HallTicket) is completely
separate from any single exam. What hall a student must sit in is decided
per ExamSession via ExamStudentAssignment, never stored on Student itself
— the same student can be in a different hall every day.
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


class ExamPeriod(models.Model):
    """A whole examination cycle — e.g. 'MCA/iMCA Semester 3 Exams, Aug 2026'.

    The roster and hall catalog are uploaded once per period. Every exam
    inside it (Monday's subject, Tuesday's subject, ...) is a separate
    ExamSession underneath this same period, sharing the same roster.
    """
    name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def student_count(self):
        return self.students.count()

    @property
    def session_count(self):
        return self.exam_sessions.count()

    @property
    def hall_count(self):
        return self.halls.count()


class Hall(models.Model):
    """A physical room. Reusable across every exam session in this period —
    a hall is not tied to one exam."""

    exam_period = models.ForeignKey(ExamPeriod, on_delete=models.CASCADE, related_name='halls')
    hall_number = models.CharField(max_length=20)
    capacity = models.PositiveIntegerField(default=30)
    seats_per_row = models.PositiveIntegerField(default=6)

    class Meta:
        ordering = ['hall_number']
        unique_together = ('exam_period', 'hall_number')

    def __str__(self):
        return f"Hall {self.hall_number} ({self.exam_period})"


class Student(models.Model):
    """The roster — uploaded once per exam period, independent of any
    single exam. A student's hall ticket/QR is permanent; only their
    per-exam hall assignment changes."""

    exam_period = models.ForeignKey(ExamPeriod, on_delete=models.CASCADE, related_name='students')
    roll_number = models.CharField(max_length=50)
    name = models.CharField(max_length=100, blank=True, default='')
    course = models.CharField(max_length=50, blank=True, default='')  # e.g. MCA, iMCA

    class Meta:
        ordering = ['roll_number']
        unique_together = ('exam_period', 'roll_number')
        indexes = [models.Index(fields=['exam_period', 'roll_number'])]

    def __str__(self):
        return f"{self.roll_number} — {self.name or 'Unnamed'}"


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

    STATUS_SCHEDULED = 'SCHEDULED'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_CLOSED = 'CLOSED'
    STATUS_CHOICES = (
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_CLOSED, 'Closed'),
    )

    exam_period = models.ForeignKey(ExamPeriod, on_delete=models.CASCADE, related_name='exam_sessions')
    subject = models.CharField(max_length=100)
    exam_date = models.DateField()
    shift = models.CharField(max_length=50, blank=True, default='')
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SCHEDULED)
    seating_confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['exam_date', 'start_time']
        indexes = [models.Index(fields=['exam_date', 'status'])]

    def __str__(self):
        return f"{self.subject} — {self.exam_date} ({self.start_time}\u2013{self.end_time})"

    def is_currently_active(self, at=None):
        """True only when this exam's own date/time window contains `at`
        (default: now) AND it hasn't been cancelled/closed. This is what
        lets one permanent QR resolve to the right exam automatically."""
        at = at or timezone.localtime()
        if self.status != self.STATUS_SCHEDULED:
            return False
        return self.exam_date == at.date() and self.start_time <= at.time() <= self.end_time

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
        return self.exam_period.students.exclude(id__in=assigned_ids)


class ExamHall(models.Model):
    """Which halls are running a given exam session, and who's invigilating
    each one. This defines an invigilator's "current hall" for that exam —
    the thing every QR scan gets checked against."""

    exam_session = models.ForeignKey(ExamSession, on_delete=models.CASCADE, related_name='exam_halls')
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE, related_name='exam_halls')
    invigilator = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='invigilating_halls',
        limit_choices_to={'role': User.ROLE_INVIGILATOR},
    )

    class Meta:
        unique_together = ('exam_session', 'hall')
        ordering = ['hall__hall_number']

    def __str__(self):
        return f"{self.hall.hall_number} for {self.exam_session}"

    @property
    def assigned_count(self):
        return self.exam_session.assignments.filter(hall=self.hall).count()

    @property
    def present_count(self):
        return self.exam_session.attendances.filter(hall=self.hall).count()


class ExamStudentAssignment(models.Model):
    """Which hall a specific student must sit in for a specific exam
    session. Deliberately NOT stored on Student — the same student can (and
    routinely will) have a different hall for every exam in the period."""

    exam_session = models.ForeignKey(ExamSession, on_delete=models.CASCADE, related_name='assignments')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='assignments')
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE, related_name='assignments')
    row = models.CharField(max_length=10, blank=True, default='')
    seat = models.CharField(max_length=10, blank=True, default='')

    class Meta:
        unique_together = ('exam_session', 'student')
        ordering = ['hall__hall_number', 'row', 'seat']
        indexes = [models.Index(fields=['exam_session', 'student'])]

    def __str__(self):
        return f"{self.student.roll_number} \u2192 Hall {self.hall.hall_number} for {self.exam_session}"


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
        return f"{self.get_alert_type_display()} in Hall {self.hall.hall_number}"
