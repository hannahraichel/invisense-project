import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='hall',
            name='row_range',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='hall',
            name='capacity',
            field=models.PositiveIntegerField(default=30, help_text='Total seats available in this hall.'),
        ),
        migrations.AddField(
            model_name='hall',
            name='seats_per_row',
            field=models.PositiveIntegerField(
                default=6,
                help_text='Used only to label rows/seats when auto-allocating (e.g. 6 -> A1..A6, B1..B6).',
            ),
        ),
        migrations.AlterField(
            model_name='student',
            name='hall',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='students', to='core.hall',
            ),
        ),
        migrations.AlterField(
            model_name='student',
            name='row',
            field=models.CharField(blank=True, default='', max_length=10),
        ),
        migrations.AlterField(
            model_name='student',
            name='seat',
            field=models.CharField(blank=True, default='', max_length=10),
        ),
        migrations.AddIndex(
            model_name='student',
            index=models.Index(fields=['hall'], name='core_studen_hall_id_8a1b2c_idx'),
        ),
    ]
