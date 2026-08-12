# Generated manually for Radar Berater Phase-1 fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('abpe_shaduler', '0002_inboxmailread'),
    ]

    operations = [
        migrations.AddField(
            model_name='radarconsultantitem',
            name='gulp_id',
            field=models.CharField(blank=True, db_index=True, max_length=32),
        ),
        migrations.AddField(
            model_name='radarconsultantitem',
            name='crm_contact_id',
            field=models.CharField(blank=True, db_index=True, max_length=36),
        ),
        migrations.AddField(
            model_name='radarconsultantitem',
            name='beschreibung',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='radarconsultantitem',
            name='eckdaten',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='radarconsultantitem',
            name='eingegangen_am',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='radarconsultantitem',
            name='cv_versions',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
