"""
Registriert die wiederkehrenden Shaduler-Jobs in abpe_scheduler.

Intervalle:
  radar_poll      alle 3 Min  (FM+Gulp+Hays → DB/ES, async via Celery)
  inbox_poll      alle 2 Min
  prozess_tick    alle 15 Min
  email_index     alle 3 Min  (IMAP→ES, inkrementell)
  radar_berater_index alle 30 Min
  radar_berater_gulp_available alle 30 Min (Talentfinder „verfügbar“ → list_rank)
  radar_berater_fl_available   alle 30 Min (FM aktuellste → list_rank)

Ablauf radar_poll / email_index:
  1) abpe-scheduler-loop triggert Webhook
  2) Webhook queued Celery sofort (Scheduler-Timeout 15s!)
  3) Celery holt neue Projekte/Mails → DB/ES
  4) UI Soft-Poll liest ES/DB

Voraussetzung: SCHEDULER_SERVICE_TOKEN + erreichbare scheduler/api
  und: abpe-scheduler-loop dauerhaft RUNNING (autostart+autorestart).
  Fix: bash scripts/ENSURE-abpe-scheduler-loop.sh
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
        'rrule': 'FREQ=MINUTELY;INTERVAL=3',
        'payload': {
            'job': 'radar_poll',
            'pages': 2,
            'today': 1,
            'days': 2,
        },
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
        'rrule': 'FREQ=MINUTELY;INTERVAL=3',
        'payload': {
            'job': 'email_index',
            'since_days': 1,
            'folders': 'INBOX',
            'incremental': True,
        },
    },
    {
        'job_key': 'radar_berater_index',
        'owner_type': 'system',
        'owner_ref': 'shaduler',
        'webhook': 'radar-berater-index',
        'rrule': 'FREQ=MINUTELY;INTERVAL=30',
        'payload': {'job': 'radar_berater_index', 'reindex': True},
    },
    {
        'job_key': 'radar_berater_gulp_available',
        'owner_type': 'system',
        'owner_ref': 'shaduler',
        'webhook': 'radar-berater-gulp-available',
        'rrule': 'FREQ=MINUTELY;INTERVAL=30',
        'payload': {
            'job': 'radar_berater_gulp_available',
            'limit': 40,
            'pages': 2,
            'enrich': True,
        },
    },
    {
        'job_key': 'radar_berater_fl_available',
        'owner_type': 'system',
        'owner_ref': 'shaduler',
        'webhook': 'radar-berater-fl-available',
        'rrule': 'FREQ=MINUTELY;INTERVAL=30',
        'payload': {
            'job': 'radar_berater_fl_available',
            'limit': 36,
            'pages': 2,
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
