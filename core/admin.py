from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Alert, Attendance, AuditLog, ExamHall, ExamPeriod, ExamSession,
    ExamStudentAssignment, Hall, HallTicket, Student, User,
)


@admin.register(User)
class CoreUserAdmin(UserAdmin):
    list_display = ('username', 'first_name', 'last_name', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Role', {'fields': ('role',)}),
    )


@admin.register(Hall)
class HallAdmin(admin.ModelAdmin):
    list_display = ('name', 'capacity', 'status')
    list_filter = ('status',)
    search_fields = ('name',)


@admin.register(ExamPeriod)
class ExamPeriodAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'student_count', 'session_count')
    list_filter = ('status',)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('roll_number', 'name', 'course', 'exam_period', 'is_active')
    list_filter = ('exam_period', 'course', 'is_active')
    search_fields = ('roll_number', 'name')


@admin.register(HallTicket)
class HallTicketAdmin(admin.ModelAdmin):
    list_display = ('student', 'qr_token')
    search_fields = ('student__roll_number', 'qr_token')


@admin.register(ExamSession)
class ExamSessionAdmin(admin.ModelAdmin):
    list_display = ('subject', 'exam_date', 'start_time', 'end_time', 'status', 'exam_period')
    list_filter = ('status', 'exam_period')
    ordering = ('exam_date', 'start_time')


@admin.register(ExamHall)
class ExamHallAdmin(admin.ModelAdmin):
    list_display = ('exam_session', 'hall', 'capacity_allocated', 'invigilator')
    list_filter = ('exam_session', 'hall')


@admin.register(ExamStudentAssignment)
class ExamStudentAssignmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'exam_session', 'hall', 'row', 'seat')
    list_filter = ('exam_session', 'hall')
    search_fields = ('student__roll_number',)


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'exam_session', 'hall', 'invigilator', 'scanned_at')
    list_filter = ('exam_session', 'hall')


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('alert_type', 'hall', 'exam_session', 'status', 'invigilator', 'timestamp')
    list_filter = ('status', 'alert_type', 'exam_session')
    ordering = ('-timestamp',)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'actor', 'action', 'entity_type', 'entity_repr')
    list_filter = ('entity_type', 'action')
    ordering = ('-timestamp',)
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
