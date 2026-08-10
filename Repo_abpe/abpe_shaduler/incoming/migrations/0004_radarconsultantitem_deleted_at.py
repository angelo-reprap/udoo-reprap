# Soft-delete + geloescht status for Radar Berater CRM sync

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('abpe_shaduler', '0003_radarconsultantitem_gulp_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='radarconsultantitem',
            name='deleted_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AlterField(
            model_name='radarconsultantitem',
            name='status',
            field=models.CharField(
                choices=[
                    ('neu', 'Neu'),
                    ('bestaetigt', 'Bestätigt'),
                    ('beobachten', 'Beobachten'),
                    ('verworfen', 'Verworfen'),
                    ('geloescht', 'Gelöscht (CRM)'),
                ],
                db_index=True,
                default='neu',
                max_length=20,
            ),
        ),
    ]
