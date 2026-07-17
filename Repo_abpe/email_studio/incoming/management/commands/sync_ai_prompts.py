"""
Management-Command: KI-Prompts aus Defaults in DB synchronisieren.

  python manage.py sync_ai_prompts
  python manage.py sync_ai_prompts --force
  python manage.py sync_ai_prompts --key meetme_email
"""
from django.core.management.base import BaseCommand

from apps.abpe_email_studio.models import AiPrompt
from apps.abpe_email_studio.ai_prompt_defaults import AI_PROMPT_DEFAULTS


class Command(BaseCommand):
    help = 'Legt KI-Prompts (AiPrompt) aus Default-Liste an oder aktualisiert sie mit --force'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Bestehende überschreiben')
        parser.add_argument('--key', type=str, default='', help='Nur einen Key')

    def handle(self, *args, **options):
        force = options['force']
        only_key = (options['key'] or '').strip()
        created = updated = skipped = 0

        for row in AI_PROMPT_DEFAULTS:
            key = row['key']
            if only_key and key != only_key:
                continue
            defaults = {
                'name': row['name'],
                'description': row.get('description', ''),
                'app_scope': row.get('app_scope', 'general'),
                'system': row['system'],
                'user_template': row['user_template'],
                'instruction_default': row.get('instruction_default', ''),
                'aktiv': True,
            }
            obj, was_created = AiPrompt.objects.get_or_create(key=key, defaults=defaults)
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'  + {key}'))
            elif force:
                for k, v in defaults.items():
                    setattr(obj, k, v)
                obj.save()
                updated += 1
                self.stdout.write(self.style.WARNING(f'  ~ {key} (force)'))
            else:
                skipped += 1
                self.stdout.write(f'  = {key} (exists)')

        self.stdout.write(self.style.SUCCESS(
            f'Fertig: {created} neu, {updated} aktualisiert, {skipped} übersprungen'
        ))
