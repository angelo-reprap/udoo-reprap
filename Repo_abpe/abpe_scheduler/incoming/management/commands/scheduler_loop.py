"""
Eigener Scheduler-Loop statt Celery Beat.
Prueft alle --interval Sekunden auf faellige Jobs und uebergibt sie
an den bereits laufenden Celery-Worker. Kein Lock-File, kein Beat.

Robustheits-Massnahmen (2026-07-09):
- close_old_connections() vor jedem Tick, damit stale DB-Verbindungen
  (z.B. nach MySQL-Neustart) nicht zu wiederholten, unklaren Fehlern fuehren.
- Jeder Job wird einzeln try/except behandelt -- ein kaputter Job blockiert
  nicht die restlichen faelligen Jobs derselben Tick-Runde.
- Alle Logs gehen zusaetzlich ueber self.stdout, damit sie garantiert in
  der supervisor-Logdatei landen, unabhaengig von der Django-LOGGING-Konfiguration.
- Heartbeat-Log alle N Ticks, damit im Log sichtbar ist, dass der Loop
  noch lebt (und wie viele Jobs er zuletzt verarbeitet hat).
- Hartes Limit pro Tick (200 Jobs), damit ein unerwarteter Stau nicht
  eine einzelne Tick-Runde unbegrenzt aufblaehen kann.

Was dieses Skript NICHT abfangen kann: einen harten SIGKILL durch den
OOM-Killer des Betriebssystems. Dagegen hilft nur, den Speicherdruck auf
der Maschine selbst zu senken (separates Thema).
"""
import logging
import signal
import time
import traceback

from django.core.management.base import BaseCommand
from django.db import close_old_connections, connections
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Laeuft dauerhaft, prueft alle --interval Sekunden auf faellige SchedulerJobs."

    def add_arguments(self, parser):
        parser.add_argument('--interval', type=int, default=5, help="Pruefintervall in Sekunden")
        parser.add_argument('--heartbeat-every', type=int, default=60,
                             help="Alle N Ticks ein Lebenszeichen loggen (0 = aus)")

    def handle(self, *args, **options):
        interval = options['interval']
        heartbeat_every = options['heartbeat_every']
        self._running = True
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)

        self._log(f"Scheduler-Loop gestartet, Intervall {interval}s")

        tick_count = 0
        dispatched_since_heartbeat = 0

        while self._running:
            tick_count += 1
            try:
                close_old_connections()
                dispatched_since_heartbeat += self._tick()
            except Exception:
                self._log_exception(f"scheduler_loop: Tick #{tick_count} fehlgeschlagen")
                try:
                    connections.close_all()
                except Exception:
                    pass

            if heartbeat_every and tick_count % heartbeat_every == 0:
                self._log(
                    f"Lebenszeichen: {tick_count} Ticks gelaufen, "
                    f"{dispatched_since_heartbeat} Jobs seit letztem Heartbeat versendet"
                )
                dispatched_since_heartbeat = 0

            time.sleep(interval)

        self._log("Scheduler-Loop sauber beendet.")

    def _stop(self, signum, frame):
        self._running = False

    def _log(self, message):
        self.stdout.write(self.style.SUCCESS(message))
        logger.info(message)

    def _log_exception(self, message):
        self.stdout.write(self.style.ERROR(message))
        self.stdout.write(traceback.format_exc())
        logger.exception(message)

    def _tick(self):
        from apps.abpe_scheduler.models import SchedulerJob, SchedulerJobRun
        from apps.abpe_scheduler.tasks import execute_job

        now = timezone.now()
        due_jobs = SchedulerJob.objects.filter(
            status='ACTIVE', delivery_mode='PUSH', next_run_at__lte=now,
        ).exclude(next_run_at__isnull=True).order_by('next_run_at')[:200]

        dispatched = 0
        for job in due_jobs:
            try:
                if job.lock_key:
                    running = SchedulerJobRun.objects.filter(
                        job__lock_key=job.lock_key, status='RUNNING',
                    ).exclude(job=job).exists()
                    if running:
                        continue
                execute_job.delay(job.id)
                dispatched += 1
                logger.info(
                    "scheduler_loop: dispatched job %s (%s:%s:%s)",
                    job.id, job.owner_app, job.owner_type, job.owner_ref,
                )
            except Exception:
                self._log_exception(f"scheduler_loop: Job {job.id} konnte nicht dispatcht werden")

        return dispatched
