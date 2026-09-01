from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_hall_capacity_and_roster_mode'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='exam_time',
            field=models.CharField(
                blank=True, default='', max_length=50,
                help_text=(
                    "Free-text exam time for this subject, e.g. '9:30 AM - 11:30 AM'. "
                    "Different subjects in the same session/shift can run at different times."
                ),
            ),
        ),
    ]
