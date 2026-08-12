# Generated for abpe_ki_wiz Phase 0

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='WizardPrompt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(db_index=True, help_text='Eindeutig, z. B. wiz_email_analyze', max_length=64, unique=True, verbose_name='Prompt-Key')),
                ('wizard_id', models.CharField(db_index=True, default='general', help_text='z. B. email_template, matching_berater, doc_letter', max_length=64, verbose_name='Wizard-ID')),
                ('phase', models.CharField(choices=[('analyze', 'Briefing analysieren'), ('clarify', 'Klärfragen'), ('suggest_meta', 'Metadaten vorschlagen'), ('generate', 'Inhalt generieren'), ('refine', 'Nachbearbeitung'), ('general', 'Allgemein / Shared')], default='general', max_length=32, verbose_name='Phase')),
                ('name', models.CharField(max_length=128, verbose_name='Anzeigename')),
                ('description', models.TextField(blank=True, verbose_name='Beschreibung')),
                ('app_scope', models.CharField(default='general', help_text='general, telefon, matching, crm, doc, …', max_length=32, verbose_name='App-Bereich')),
                ('system', models.TextField(help_text='System-Prompt für DeepSeek', verbose_name='System-Prompt')),
                ('user_template', models.TextField(help_text='User-Template mit [[CONTEXT]], [[INSTRUCTION]], …', verbose_name='User-Template')),
                ('instruction_default', models.TextField(blank=True, help_text='Fallback wenn API keine Instruction übergibt', verbose_name='Standard-Instruction')),
                ('checklist_template', models.TextField(blank=True, help_text='Optional: Regeln für prompt_builder (eine Zeile pro Punkt)', verbose_name='Checklist-Vorlage')),
                ('aktiv', models.BooleanField(default=True, verbose_name='Aktiv')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='wizard_prompts_updated', to=settings.AUTH_USER_MODEL, verbose_name='Zuletzt geändert von')),
            ],
            options={
                'verbose_name': 'KI-Wizard-Prompt',
                'verbose_name_plural': 'KI-Wizard-Prompts',
                'db_table': 'abpe_ki_wiz_prompt',
                'ordering': ['wizard_id', 'phase', 'name'],
            },
        ),
        migrations.CreateModel(
            name='WizardSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('wizard_id', models.CharField(db_index=True, max_length=64, verbose_name='Wizard-ID')),
                ('status', models.CharField(choices=[('open', 'Offen'), ('completed', 'Abgeschlossen'), ('cancelled', 'Abgebrochen'), ('failed', 'Fehlgeschlagen')], default='open', max_length=20, verbose_name='Status')),
                ('phase', models.CharField(choices=[('analyze', 'Briefing analysieren'), ('clarify', 'Klärfragen'), ('suggest_meta', 'Metadaten vorschlagen'), ('generate', 'Inhalt generieren'), ('refine', 'Nachbearbeitung'), ('general', 'Allgemein / Shared')], default='analyze', max_length=32, verbose_name='Aktuelle Phase')),
                ('briefing', models.TextField(blank=True, verbose_name='Briefing (Freitext)')),
                ('answers', models.JSONField(blank=True, default=dict, help_text='question_id → Antwort', verbose_name='Klär-Antworten')),
                ('meta_suggestions', models.JSONField(blank=True, default=dict, verbose_name='Metadaten-Vorschläge')),
                ('result', models.JSONField(blank=True, default=dict, verbose_name='Generiertes Ergebnis')),
                ('error_message', models.TextField(blank=True, verbose_name='Fehler')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='Abgeschlossen am')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='wizard_sessions', to=settings.AUTH_USER_MODEL, verbose_name='Benutzer')),
            ],
            options={
                'verbose_name': 'KI-Wizard-Session',
                'verbose_name_plural': 'KI-Wizard-Sessions',
                'db_table': 'abpe_ki_wiz_session',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='wizardprompt',
            index=models.Index(fields=['wizard_id', 'phase'], name='abpe_ki_wiz_wizard__a1b2c3_idx'),
        ),
        migrations.AddIndex(
            model_name='wizardsession',
            index=models.Index(fields=['wizard_id', 'status'], name='abpe_ki_wiz_wizard__d4e5f6_idx'),
        ),
        migrations.AddIndex(
            model_name='wizardsession',
            index=models.Index(fields=['user', '-created_at'], name='abpe_ki_wiz_user_id_g7h8i9_idx'),
        ),
    ]
