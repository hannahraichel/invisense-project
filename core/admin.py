from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Alert, ExamSession, Hall, Student, User


@admin.register(User)
class CoreUserAdmin(UserAdmin):
    list_display = ('username', 'first_name', 'last_name', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Role', {'fields': ('role',)}),
    )


@admin.register(ExamSession)
class ExamSessionAdmin(admin.ModelAdmin):
    list_display = ('date', 'shift', 'is_active', 'student_count', 'alert_count')
    list_filter = ('is_active', 'shift')
    ordering = ('-date',)


@admin.register(Hall)
class HallAdmin(admin.ModelAdmin):
    list_display = ('hall_number', 'session', 'capacity', 'invigilator', 'student_count')
    list_filter = ('session',)
    search_fields = ('hall_number',)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('roll_number', 'name', 'subject_code', 'hall', 'session', 'is_present')
    list_filter = ('session', 'hall', 'is_present')
    search_fields = ('roll_number', 'name')


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('alert_type', 'hall', 'session', 'status', 'invigilator', 'timestamp')
    list_filter = ('status', 'alert_type', 'session')
    ordering = ('-timestamp',)
