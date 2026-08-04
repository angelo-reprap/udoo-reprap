"""
Registriert die wiederkehrenden Shaduler-Jobs in abpe_scheduler.

Intervalle (Architektur Kap. 4 / Kap. 0):
  radar_poll      alle 5 Min
  inbox_poll      alle 2 Min
  prozess_tick    alle 15 Min
  delegation_notify — on-demand (hier optional als seltener Tick)

schedule_type: ONCE | RECURRING  (RRULE-String → Feld rrule_string)
Voraussetzung: SCHEDULER_SERVICE_TOKEN + erreichbare scheduler/api.
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
                self.stdout.write(self.style.SUCCESS(f"  OK {res}"))
            except sc.SchedulerClientError as exc:
                self.stdout.write(self.style.ERROR(f"  FAIL {exc}"))
        if dry:
            self.stdout.write(self.style.WARNING('dry-run — nichts registriert'))
