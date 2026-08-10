"""Diagnose Posteingang: Elasticsearch abpe_emails + IMAP (EmailImportConfig)."""
from django.core.management.base import BaseCommand

from apps.abpe_shaduler.services import inbox_service


class Command(BaseCommand):
    help = 'Zeigt ES-Index, EmailImportConfig + IMAP und testet optional den Abruf.'

    def add_arguments(self, parser):
        parser.add_argument('--fetch', action='store_true', help='Mails abrufen (limit)')
        parser.add_argument('--limit', type=int, default=10)
        parser.add_argument('--force-imap', action='store_true', help='ES/DB überspringen, direkt IMAP')

    def handle(self, *args, **options):
        info = inbox_service.probe()
        self.stdout.write(self.style.NOTICE('source order: ' + ' → '.join(info.get('source_order') or [])))

        es = info.get('elasticsearch') or {}
        self.stdout.write(self.style.NOTICE('Elasticsearch:'))
        self.stdout.write(
            f"  hosts={es.get('hosts')} index={es.get('index')} "
            f"reachable={es.get('reachable')} count={es.get('count')}"
        )
        self.stdout.write(
            f"  newest_date={es.get('newest_date')} account={es.get('newest_account')} "
            f"subj={es.get('newest_subject')!r}"
        )
        if es.get('bad_future_dates') is not None:
            self.stdout.write(
                self.style.WARNING(
                    f"  bad_future_dates(>2100)={es.get('bad_future_dates')} "
                    f"— Indexer schreibt kaputte Daten (z.B. 4501); namazu prüfen"
                )
            )
        if es.get('top_accounts'):
            tops = ', '.join(
                f"{a.get('account')}={a.get('count')}" for a in (es.get('top_accounts') or [])[:8]
            )
            self.stdout.write(f'  top_accounts: {tops}')
        if es.get('error'):
            self.stdout.write(self.style.WARNING(f"  error: {es['error']}"))

        cfg = info.get('email_import_config') or {}
        msg = info.get('email_message') or {}
        self.stdout.write(self.style.NOTICE('EmailImportConfig / EmailMessage:'))
        self.stdout.write(
            f"  configs active={cfg.get('active')}/{cfg.get('total')}  "
            f"messages total={msg.get('total')} new={msg.get('new')}"
        )
        if cfg.get('error'):
            self.stdout.write(self.style.WARNING(f"  config error: {cfg['error']}"))

        self.stdout.write(self.style.NOTICE('IMAP accounts (EmailImportConfig):'))
        accs = info.get('accounts') or []
        if not accs:
            self.stdout.write(self.style.WARNING('  (keine aktiven EmailImportConfig)'))
        for a in accs:
            pw = 'yes' if a.get('has_password') else 'NO'
            self.stdout.write(
                f"  - {a.get('label')}  {a.get('user')}@{a.get('host')}:{a.get('port')} "
                f"folder={a.get('folder')} ssl={a.get('ssl')} password={pw} "
                f"[{a.get('source')}]"
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
            if data.get('hint'):
                self.stdout.write(self.style.WARNING(f"  hint: {data['hint']}"))
            if data.get('error'):
                self.stdout.write(self.style.ERROR(data['error']))
            for err in data.get('errors') or []:
                self.stdout.write(self.style.ERROR(f'  {err}'))
            for m in (data.get('results') or [])[: options['limit']]:
                flag = '●' if m.get('unread') else '○'
                self.stdout.write(
                    f"  {flag} [{m.get('box')}] {m.get('subj')!r} — {m.get('from')} ({m.get('age')})"
                )
