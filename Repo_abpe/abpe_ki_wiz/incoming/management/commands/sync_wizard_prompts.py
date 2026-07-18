"""
Management-Command: Wizard-Prompts aus Defaults in DB synchronisieren.

  python manage.py sync_wizard_prompts
  python manage.py sync_wizard_prompts --force
  python manage.py sync_wizard_prompts --key wiz_email_analyze
  python manage.py sync_wizard_prompts --wizard-id email_template
"""
from django.core.management.base import BaseCommand

from apps.abpe_ki_wiz.models import WizardPrompt
from apps.abpe_ki_wiz.prompt_defaults import WIZARD_PROMPT_DEFAULTS


class Command(BaseCommand):
    help = 'Legt KI-Wizard-Prompts aus Default-Liste an oder aktualisiert sie mit --force'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Bestehende Prompts überschreiben',
        )
        parser.add_argument(
            '--key',
            type=str,
            default='',
            help='Nur einen Prompt-Key',
        )
        parser.add_argument(
            '--wizard-id',
            type=str,
            default='',
            help='Nur Prompts eines Wizards',
        )

    def handle(self, *args, **options):
        force = options['force']
        only_key = (options['key'] or '').strip()
        only_wizard = (options['wizard_id'] or '').strip()
        created = updated = skipped = 0

        for row in WIZARD_PROMPT_DEFAULTS:
            key = row['key']
            if only_key and key != only_key:
                continue
            if only_wizard and row.get('wizard_id') != only_wizard:
                continue

            defaults = {
                'wizard_id': row.get('wizard_id', 'general'),
                'phase': row.get('phase', 'general'),
                'name': row['name'],
                'description': row.get('description', ''),
                'app_scope': row.get('app_scope', 'general'),
                'system': row['system'],
                'user_template': row['user_template'],
                'instruction_default': row.get('instruction_default', ''),
                'checklist_template': row.get('checklist_template', ''),
                'aktiv': True,
            }

            obj, was_created = WizardPrompt.objects.get_or_create(
                key=key,
                defaults=defaults,
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'  + {key}'))
            elif force:
                for field, value in defaults.items():
                    setattr(obj, field, value)
                obj.save()
                updated += 1
                self.stdout.write(self.style.WARNING(f'  ~ {key} (force)'))
            else:
                skipped += 1
                self.stdout.write(f'  = {key} (exists)')

        self.stdout.write(self.style.SUCCESS(
            f'Fertig: {created} neu, {updated} aktualisiert, {skipped} übersprungen'
        ))
