# Generated for the InviSense project

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
            name='ExamSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('shift', models.CharField(max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-date', '-id'],
            },
        ),
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
            name='Hall',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hall_number', models.CharField(max_length=20)),
                ('row_range', models.CharField(max_length=50)),
                ('invigilator', models.ForeignKey(blank=True, limit_choices_to={'role': 'INVIGILATOR'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_halls', to=settings.AUTH_USER_MODEL)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='halls', to='core.examsession')),
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
                ('name', models.CharField(blank=True, max_length=100, null=True)),
                ('subject_code', models.CharField(max_length=50)),
                ('row', models.CharField(max_length=10)),
                ('seat', models.CharField(max_length=10)),
                ('qr_code', models.ImageField(blank=True, upload_to='qrcodes/')),
                ('is_present', models.BooleanField(default=False)),
                ('checked_in_at', models.DateTimeField(blank=True, null=True)),
                ('hall', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='students', to='core.hall')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='students', to='core.examsession')),
            ],
            options={
                'ordering': ['roll_number'],
            },
        ),
        migrations.CreateModel(
            name='Alert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('alert_type', models.CharField(choices=[('SUSPICIOUS_ACTIVITY', 'Suspicious Activity'), ('NEED_SUPERVISOR', 'Need Supervisor'), ('MEDICAL_EMERGENCY', 'Medical Emergency'), ('OTHER', 'Other')], max_length=50)),
                ('row', models.CharField(blank=True, max_length=10, null=True)),
                ('seat', models.CharField(blank=True, max_length=10, null=True)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('ACKNOWLEDGED', 'Acknowledged'), ('RESOLVED', 'Resolved')], default='PENDING', max_length=20)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('invigilator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.examsession')),
                ('hall', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.hall')),
                ('student', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.student')),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='examsession',
            index=models.Index(fields=['is_active'], name='core_examse_is_acti_1a2b3c_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='hall',
            unique_together={('session', 'hall_number')},
        ),
        migrations.AlterUniqueTogether(
            name='student',
            unique_together={('session', 'roll_number', 'subject_code')},
        ),
        migrations.AddIndex(
            model_name='student',
            index=models.Index(fields=['session', 'roll_number'], name='core_studen_session_4d5e6f_idx'),
        ),
        migrations.AddIndex(
            model_name='student',
            index=models.Index(fields=['is_present'], name='core_studen_is_pres_7g8h9i_idx'),
        ),
        migrations.AddIndex(
            model_name='alert',
            index=models.Index(fields=['status'], name='core_alert_status_0j1k2l_idx'),
        ),
        migrations.AddIndex(
            model_name='alert',
            index=models.Index(fields=['session', 'status'], name='core_alert_session_3m4n5o_idx'),
        ),
    ]
