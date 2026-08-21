"""
Registriert die wiederkehrenden Shaduler-Jobs in abpe_scheduler.

Intervalle (Architektur Kap. 4 / Kap. 0):
  radar_poll      alle 5 Min
  inbox_poll      alle 2 Min
  prozess_tick    alle 15 Min
  email_index     alle 1 Min  (IMAP→ES, inkrementell)
  radar_berater_index alle 30 Min
  namazu_profiles_index        Mo–Fr 08–19 Europe/Berlin alle 10 Min
  namazu_profiles_index_22     täglich 22:00 Europe/Berlin
  namazu_profiles_index_03     täglich 03:00 Europe/Berlin
  (alle drei → HTML→ES abpe_namazu_profiles, inkrementell)
  delegation_notify — on-demand (hier optional als seltener Tick)

schedule_type: ONCE | RECURRING  (RRULE-String → Feld rrule_string)
Voraussetzung: SCHEDULER_SERVICE_TOKEN + erreichbare scheduler/api.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand

from apps.abpe_shaduler import scheduler_client as sc

TZ_BERLIN = ZoneInfo('Europe/Berlin')

_NAMAZU_PAYLOAD = {
    'job': 'namazu_profiles_index',
    'incremental': True,
    'since_hours': 168,
}

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
        # Jede Minute — Indexer läuft inkrementell (nur neue Message-IDs).
        'rrule': 'FREQ=MINUTELY;INTERVAL=1',
        'payload': {
            'job': 'email_index',
            'since_days': 2,
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
        # HTML /var/www/namazu/index → ES abpe_namazu_profiles (async Webhook)
        # Mo–Fr 08:00–19:50 Europe/Berlin, alle 10 Minuten
        'job_key': 'namazu_profiles_index',
        'owner_type': 'system',
        'owner_ref': 'namazu',
        'webhook': 'namazu-profiles-index',
        'rrule': (
            'FREQ=MINUTELY;INTERVAL=10;BYDAY=MO,TU,WE,TH,FR;'
            'BYHOUR=8,9,10,11,12,13,14,15,16,17,18,19'
        ),
        'tz': 'Europe/Berlin',
        'payload': {
            **_NAMAZU_PAYLOAD,
            'schedule_window': 'daytime_mo_fr_08_19',
        },
    },
    {
        'job_key': 'namazu_profiles_index_22',
        'owner_type': 'system',
        'owner_ref': 'namazu',
        'webhook': 'namazu-profiles-index',
        'rrule': 'FREQ=DAILY;BYHOUR=22;BYMINUTE=0;BYSECOND=0',
        'tz': 'Europe/Berlin',
        'payload': {
            **_NAMAZU_PAYLOAD,
            'schedule_window': 'daily_22',
        },
    },
    {
        'job_key': 'namazu_profiles_index_03',
        'owner_type': 'system',
        'owner_ref': 'namazu',
        'webhook': 'namazu-profiles-index',
        'rrule': 'FREQ=DAILY;BYHOUR=3;BYMINUTE=0;BYSECOND=0',
        'tz': 'Europe/Berlin',
        'payload': {
            **_NAMAZU_PAYLOAD,
            'schedule_window': 'daily_03',
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
        now_utc = datetime.now(timezone.utc)
        for spec in JOBS:
            cb = sc.build_callback_url(spec['webhook'])
            # Namazu-Fenster an Wanduhr Europe/Berlin koppeln (BYHOUR/BYDAY).
            if spec.get('tz') == 'Europe/Berlin':
                dtstart = datetime.now(TZ_BERLIN)
            else:
                dtstart = now_utc
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
                    dtstart=dtstart,
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
