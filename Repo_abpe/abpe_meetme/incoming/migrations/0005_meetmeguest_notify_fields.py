from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('abpe_meetme', '0004_meetmeguest_invited_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='meetmeguest',
            name='last_notified_start_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Zuletzt informiert über Termin (Stand)'),
        ),
        migrations.AddField(
            model_name='meetmeguest',
            name='notified_cancelled',
            field=models.BooleanField(default=False, verbose_name='Über Absage informiert'),
        ),
    ]
