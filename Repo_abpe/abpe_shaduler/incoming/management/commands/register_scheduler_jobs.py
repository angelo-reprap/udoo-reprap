"""
Registriert die wiederkehrenden Shaduler-Jobs in abpe_scheduler.

Intervalle (Architektur Kap. 4 / Kap. 0):
  radar_poll      alle 5 Min
  inbox_poll      alle 2 Min
  prozess_tick    alle 15 Min
  email_index     alle 3 Min  (IMAP→ES, inkrementell: nur neue Message-IDs)

Ablauf email_index:
  1) abpe-scheduler-loop triggert Webhook alle 3 Min
  2) Celery: IMAP SINCE ~1 Tag, indexiert nur Message-IDs die noch nicht in ES sind
  3) UI liest ES (↻ / Soft-Poll) — zeigt aktuelle Treffer

Voraussetzung: SCHEDULER_SERVICE_TOKEN + erreichbare scheduler/api
  und: supervisorctl start abpe-scheduler-loop  (muss RUNNING sein!)
"""
from datetime import datetime, timezone

from django.core.management.base import BaseCommand

from apps.abpe_shaduler import scheduler_client as sc


# RECURRING + RRULE minutely intervals
JOBS = [
    {
        'job_key': 'radar_poll',
        'owner_type': 'system',
        'owner_ref': 'shaduler',
        'webhook': 'radar-poll',
        'rrule': 'FREQ=MINUTELY;INTERVAL=5',
        'payload': {'job': 'radar_poll'},
    },
    {
        'job_key': 'inbox_poll',
        'owner_type': 'system',
        'owner_ref': 'shaduler',
        'webhook': 'inbox-poll',
        'rrule': 'FREQ=MINUTELY;INTERVAL=2',
        'payload': {'job': 'inbox_poll'},
    },
    {
        'job_key': 'prozess_tick',
        'owner_type': 'system',
        'owner_ref': 'shaduler',
        'webhook': 'prozess-tick',
        'rrule': 'FREQ=MINUTELY;INTERVAL=15',
        'payload': {'job': 'prozess_tick'},
    },
    {
        'job_key': 'email_index',
        'owner_type': 'system',
        'owner_ref': 'namazu',
        'webhook': 'email-index',
        # Alle 3 Min — inkrementell (nur neue Message-IDs im SINCE-Fenster).
        'rrule': 'FREQ=MINUTELY;INTERVAL=3',
        'payload': {
            'job': 'email_index',
            # IMAP SINCE ist tagesgenau; 1 Tag reicht für den 3‑Min-Takt.
            # Schon indexierte Message-IDs werden übersprungen (incremental).
            'since_days': 1,
            'folders': 'INBOX',
            'incremental': True,
        },
    },
]


class Command(BaseCommand):
    help = 'Shaduler-Periodik als SchedulerJob (RECURRING/RRULE) bei abpe_scheduler anlegen.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Nur anzeigen, nichts schreiben',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        now = datetime.now(timezone.utc)
        for spec in JOBS:
            cb = sc.build_callback_url(spec['webhook'])
            self.stdout.write(f"→ {spec['job_key']}: RECURRING {spec['rrule']} → {cb}")
            if dry:
                continue
            try:
                res = sc.upsert_job(
                    owner_type=spec['owner_type'],
                    owner_ref=spec['owner_ref'],
                    job_key=spec['job_key'],
                    schedule_type='RECURRING',
                    callback_url=cb,
                    payload=spec['payload'],
                    rrule_string=spec['rrule'],
                    dtstart=now,
                    delivery_mode='PUSH',
                )
                # Kurzfassung — volle runs-Historie macht die Shell unlesbar
                jid = res.get('id') if isinstance(res, dict) else None
                status = res.get('status') if isinstance(res, dict) else None
                nxt = res.get('next_run_at') if isinstance(res, dict) else None
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  OK id={jid} status={status} next={nxt}"
                    )
                )
            except sc.SchedulerClientError as exc:
                self.stdout.write(self.style.ERROR(f"  FAIL {exc}"))
        if dry:
            self.stdout.write(self.style.WARNING('dry-run — nichts registriert'))
