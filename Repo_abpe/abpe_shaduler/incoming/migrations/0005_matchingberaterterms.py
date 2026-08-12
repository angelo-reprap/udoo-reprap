from django.db import migrations, models
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('abpe_shaduler', '0004_radarconsultantitem_deleted_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='MatchingBeraterTerms',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('match_id', models.UUIDField(db_index=True, help_text='abpe_matching_workflow.ProjectConsultant.id', unique=True)),
                ('project_id', models.CharField(blank=True, db_index=True, default='', help_text='ProjectRequest.id oder project_number', max_length=64)),
                ('crm_contact_id', models.CharField(blank=True, db_index=True, default='', max_length=36)),
                ('avail_from', models.DateField(blank=True, help_text='Verfügbar ab (für diese Anfrage)', null=True)),
                ('avail_days_per_week', models.PositiveSmallIntegerField(blank=True, help_text='Tage/Woche (1–7)', null=True)),
                ('avail_note', models.CharField(blank=True, default='', help_text='z.B. nur Mo–Mi', max_length=255)),
                ('rate_remote', models.DecimalField(blank=True, decimal_places=2, help_text='Stundensatz Remote € (diese Anfrage)', max_digits=8, null=True)),
                ('rate_onsite', models.DecimalField(blank=True, decimal_places=2, help_text='Stundensatz vor Ort € (diese Anfrage)', max_digits=8, null=True)),
                ('rate_note', models.CharField(blank=True, default='', max_length=255)),
                ('updated_by', models.CharField(blank=True, default='', max_length=80)),
            ],
            options={
                'verbose_name': 'Matching-Berater-Konditionen',
                'verbose_name_plural': 'Matching-Berater-Konditionen',
            },
        ),
        migrations.AddIndex(
            model_name='matchingberaterterms',
            index=models.Index(fields=['crm_contact_id', 'updated_at'], name='abpe_shadul_crm_con_7f07a1_idx'),
        ),
        migrations.AddIndex(
            model_name='matchingberaterterms',
            index=models.Index(fields=['project_id'], name='abpe_shadul_project_7f07a2_idx'),
        ),
    ]
