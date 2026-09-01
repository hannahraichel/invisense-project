import json
from io import BytesIO

import qrcode
from django.contrib.auth.models import AbstractUser
from django.core.files import File
from django.db import models


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


class ExamSession(models.Model):
    date = models.DateField()
    shift = models.CharField(max_length=50)  # e.g. "Morning", "Afternoon"
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']
        indexes = [models.Index(fields=['is_active'])]

    def __str__(self):
        return f"{self.date} - {self.shift}"

    @property
    def student_count(self):
        return self.students.count()

    @property
    def present_count(self):
        return self.students.filter(is_present=True).count()

    @property
    def alert_count(self):
        return self.alert_set.count()

    @property
    def pending_alert_count(self):
        return self.alert_set.filter(status=Alert.STATUS_PENDING).count()

    @property
    def unseated_count(self):
        return self.students.filter(hall__isnull=True).count()

    @property
    def total_capacity(self):
        return sum(h.capacity for h in self.halls.all())


class Hall(models.Model):
    session = models.ForeignKey(ExamSession, on_delete=models.CASCADE, related_name="halls")
    hall_number = models.CharField(max_length=20)
    row_range = models.CharField(max_length=50, blank=True)  # optional descriptive label, e.g. "Ground floor"
    capacity = models.PositiveIntegerField(default=30, help_text="Total seats available in this hall.")
    seats_per_row = models.PositiveIntegerField(
        default=6, help_text="Used only to label rows/seats when auto-allocating (e.g. 6 -> A1..A6, B1..B6)."
    )
    invigilator = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_halls",
        limit_choices_to={'role': User.ROLE_INVIGILATOR},
    )

    class Meta:
        ordering = ['hall_number']
        unique_together = ('session', 'hall_number')

    def __str__(self):
        return f"Hall {self.hall_number} ({self.session})"

    @property
    def student_count(self):
        return self.students.count()

    @property
    def present_count(self):
        return self.students.filter(is_present=True).count()

    @property
    def seats_remaining(self):
        return max(self.capacity - self.student_count, 0)


class Student(models.Model):
    session = models.ForeignKey(ExamSession, on_delete=models.CASCADE, related_name="students")
    roll_number = models.CharField(max_length=50)
    name = models.CharField(max_length=100, blank=True, null=True)
    subject_code = models.CharField(max_length=50)
    exam_time = models.CharField(
        max_length=50, blank=True, default='',
        help_text="Free-text exam time for this subject, e.g. '9:30 AM - 11:30 AM'. "
                   "Different subjects in the same session/shift can run at different times."
    )

    # Null/blank until seating is allocated (either by CSV with a hall_number
    # column, or by the auto-allocator). A student can exist in the roster
    # before a seat is assigned.
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE, related_name="students", null=True, blank=True)
    row = models.CharField(max_length=10, blank=True, default='')
    seat = models.CharField(max_length=10, blank=True, default='')

    qr_code = models.ImageField(upload_to='qrcodes/', blank=True)
    is_present = models.BooleanField(default=False)
    checked_in_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['roll_number']
        unique_together = ('session', 'roll_number', 'subject_code')
        indexes = [
            models.Index(fields=['session', 'roll_number']),
            models.Index(fields=['is_present']),
            models.Index(fields=['hall']),
        ]

    def __str__(self):
        return f"{self.roll_number} - {self.subject_code}"

    @property
    def is_seated(self):
        return self.hall_id is not None

    def save(self, *args, **kwargs):
        # Only a seated student (hall assigned) gets a QR code — the code
        # encodes the hall, so it can't be generated before allocation.
        if self.hall_id and not self.qr_code:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            data = {
                'roll_number': self.roll_number,
                'subject_code': self.subject_code,
                'hall_number': self.hall.hall_number,
                'seat': self.seat,
            }
            qr.add_data(json.dumps(data))
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            file_name = f'qr_{self.roll_number}_{self.subject_code}.png'
            self.qr_code.save(file_name, File(buffer), save=False)
        super().save(*args, **kwargs)


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

    session = models.ForeignKey(ExamSession, on_delete=models.CASCADE)
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPES)
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    invigilator = models.ForeignKey(User, on_delete=models.CASCADE)

    # Optional fields for student-specific alerts
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True)
    row = models.CharField(max_length=10, blank=True, null=True)
    seat = models.CharField(max_length=10, blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    timestamp = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['session', 'status']),
        ]

    def __str__(self):
        return f"{self.get_alert_type_display()} in Hall {self.hall.hall_number}"
