# Generated for the InviSense project — rebuilt schema (see README:
# "Database changes" for why this replaces the previous migrations).

import django.contrib.auth.models
import django.contrib.auth.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('username', models.CharField(error_messages={'unique': 'A user with that username already exists.'}, help_text='Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.', max_length=150, unique=True, validators=[django.contrib.auth.validators.UnicodeUsernameValidator()], verbose_name='username')),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='first name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='last name')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='email address')),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('role', models.CharField(choices=[('ADMIN', 'Admin'), ('INVIGILATOR', 'Invigilator'), ('CONTROL_ROOM', 'Control Room Staff')], default='INVIGILATOR', max_length=20)),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'verbose_name': 'user',
                'verbose_name_plural': 'users',
                'ordering': ['username'],
                'abstract': False,
            },
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name='ExamPeriod',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Hall',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hall_number', models.CharField(max_length=20)),
                ('capacity', models.PositiveIntegerField(default=30)),
                ('seats_per_row', models.PositiveIntegerField(default=6)),
                ('exam_period', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='halls', to='core.examperiod')),
            ],
            options={
                'ordering': ['hall_number'],
            },
        ),
        migrations.CreateModel(
            name='Student',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('roll_number', models.CharField(max_length=50)),
                ('name', models.CharField(blank=True, default='', max_length=100)),
                ('course', models.CharField(blank=True, default='', max_length=50)),
                ('exam_period', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='students', to='core.examperiod')),
            ],
            options={
                'ordering': ['roll_number'],
            },
        ),
        migrations.CreateModel(
            name='HallTicket',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('qr_token', models.CharField(editable=False, max_length=64, unique=True)),
                ('qr_code', models.ImageField(blank=True, upload_to='qrcodes/')),
                ('student', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='hall_ticket', to='core.student')),
            ],
        ),
        migrations.CreateModel(
            name='ExamSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subject', models.CharField(max_length=100)),
                ('exam_date', models.DateField()),
                ('shift', models.CharField(blank=True, default='', max_length=50)),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('status', models.CharField(choices=[('SCHEDULED', 'Scheduled'), ('CANCELLED', 'Cancelled'), ('CLOSED', 'Closed')], default='SCHEDULED', max_length=20)),
                ('seating_confirmed', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('exam_period', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exam_sessions', to='core.examperiod')),
            ],
            options={
                'ordering': ['exam_date', 'start_time'],
            },
        ),
        migrations.CreateModel(
            name='ExamHall',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('exam_session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exam_halls', to='core.examsession')),
                ('hall', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exam_halls', to='core.hall')),
                ('invigilator', models.ForeignKey(blank=True, limit_choices_to={'role': 'INVIGILATOR'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='invigilating_halls', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['hall__hall_number'],
            },
        ),
        migrations.CreateModel(
            name='ExamStudentAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('row', models.CharField(blank=True, default='', max_length=10)),
                ('seat', models.CharField(blank=True, default='', max_length=10)),
                ('exam_session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='core.examsession')),
                ('hall', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='core.hall')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='core.student')),
            ],
            options={
                'ordering': ['hall__hall_number', 'row', 'seat'],
            },
        ),
        migrations.CreateModel(
            name='Attendance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('PRESENT', 'Present')], default='PRESENT', max_length=20)),
                ('scanned_at', models.DateTimeField(auto_now_add=True)),
                ('exam_session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendances', to='core.examsession')),
                ('hall', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendances', to='core.hall')),
                ('invigilator', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='marked_attendances', to=settings.AUTH_USER_MODEL)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendances', to='core.student')),
            ],
            options={
                'ordering': ['-scanned_at'],
            },
        ),
        migrations.CreateModel(
            name='Alert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('alert_type', models.CharField(choices=[('SUSPICIOUS_ACTIVITY', 'Suspicious Activity'), ('NEED_SUPERVISOR', 'Need Supervisor'), ('MEDICAL_EMERGENCY', 'Medical Emergency'), ('OTHER', 'Other')], max_length=50)),
                ('row', models.CharField(blank=True, default='', max_length=10)),
                ('seat', models.CharField(blank=True, default='', max_length=10)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('ACKNOWLEDGED', 'Acknowledged'), ('RESOLVED', 'Resolved')], default='PENDING', max_length=20)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('notes', models.TextField(blank=True, default='')),
                ('exam_session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='alerts', to='core.examsession')),
                ('hall', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.hall')),
                ('invigilator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('student', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.student')),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='student',
            index=models.Index(fields=['exam_period', 'roll_number'], name='core_studen_exam_pe_1a1a1a_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='student',
            unique_together={('exam_period', 'roll_number')},
        ),
        migrations.AlterUniqueTogether(
            name='hall',
            unique_together={('exam_period', 'hall_number')},
        ),
        migrations.AddIndex(
            model_name='examsession',
            index=models.Index(fields=['exam_date', 'status'], name='core_examse_exam_da_2b2b2b_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='examhall',
            unique_together={('exam_session', 'hall')},
        ),
        migrations.AddIndex(
            model_name='examstudentassignment',
            index=models.Index(fields=['exam_session', 'student'], name='core_examst_exam_se_3c3c3c_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='examstudentassignment',
            unique_together={('exam_session', 'student')},
        ),
        migrations.AddIndex(
            model_name='attendance',
            index=models.Index(fields=['exam_session', 'student'], name='core_attend_exam_se_4d4d4d_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='attendance',
            unique_together={('exam_session', 'student')},
        ),
        migrations.AddIndex(
            model_name='alert',
            index=models.Index(fields=['status'], name='core_alert_status_5e5e5e_idx'),
        ),
        migrations.AddIndex(
            model_name='alert',
            index=models.Index(fields=['exam_session', 'status'], name='core_alert_exam_se_6f6f6f_idx'),
        ),
    ]
