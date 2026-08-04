"""Diagnose Posteingang / IMAP (Host 172.20.3.150)."""
from django.core.management.base import BaseCommand

from apps.abpe_shaduler.services import inbox_service


class Command(BaseCommand):
    help = 'Zeigt ingest_email-Modelle + IMAP-Accounts und testet optional den Abruf.'

    def add_arguments(self, parser):
        parser.add_argument('--fetch', action='store_true', help='Mails abrufen (limit)')
        parser.add_argument('--limit', type=int, default=10)
        parser.add_argument('--force-imap', action='store_true', help='DB überspringen, direkt IMAP')

    def handle(self, *args, **options):
        info = inbox_service.probe()
        self.stdout.write(self.style.NOTICE('ingest-related models:'))
        for m in info.get('ingest_related_models') or []:
            self.stdout.write(f'  - {m}')
        self.stdout.write(self.style.NOTICE('IMAP accounts:'))
        accs = info.get('accounts') or []
        if not accs:
            self.stdout.write(self.style.WARNING(
                '  (keine) — setze z.B. in settings.json:\n'
                '  "shaduler": {"imap_accounts": [{"host":"172.20.3.150","port":993,'
                '"user":"...","password":"...","folder":"INBOX","ssl":true,"label":"Dispo"}]}'
            ))
        for a in accs:
            pw = 'yes' if a.get('has_password') else 'NO'
            self.stdout.write(
                f"  - {a.get('label')}  {a.get('user')}@{a.get('host')}:{a.get('port')} "
                f"folder={a.get('folder')} ssl={a.get('ssl')} password={pw}"
            )
        if options['fetch']:
            data = inbox_service.list_mails(
                limit=options['limit'],
                force_imap=options['force_imap'],
            )
            self.stdout.write(self.style.SUCCESS(
                f"source={data.get('source')} ok={data.get('ok')} "
                f"n={len(data.get('results') or [])} unread={data.get('unread')}"
            ))
            if data.get('error'):
                self.stdout.write(self.style.ERROR(data['error']))
            for err in data.get('errors') or []:
                self.stdout.write(self.style.ERROR(f'  {err}'))
            for m in (data.get('results') or [])[: options['limit']]:
                flag = '●' if m.get('unread') else '○'
                self.stdout.write(
                    f"  {flag} [{m.get('box')}] {m.get('subj')!r} — {m.get('from')} ({m.get('age')})"
                )
