"""
Eigener Scheduler-Loop statt Celery Beat.
Prueft alle --interval Sekunden auf faellige Jobs und uebergibt sie
an den bereits laufenden Celery-Worker. Kein Lock-File, kein Beat.

Stabilitaet (Supervisor-Programm abpe-scheduler-loop):
- Lauft dauerhaft; beendet sich nur bei SIGTERM/SIGINT (Supervisor-Stop).
- close_old_connections() vor jedem Tick (stale MySQL nach DB-Restart).
- Pro Job try/except — ein kaputter Job blockiert nicht die Tick-Runde.
- Celery-Dispatch-Fehler loggen und weiter (Broker kurz weg → naechster Tick).
- Heartbeat in stdout → sichtbar in supervisor-Log.
- Interruptierbarer Sleep → schneller Stop ohne lange Wartezeit.
- stdout flush nach jedem Log (unbuffered fuer Supervisor-Logs).

Was dieses Skript NICHT abfangen kann: SIGKILL/OOM. Dagegen:
  supervisor autostart=true + autorestart=true (siehe deploy/supervisor/).
"""
import logging
import signal
import sys
import time
import traceback

from django.core.management.base import BaseCommand
from django.db import close_old_connections, connections
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Laeuft dauerhaft, prueft alle --interval Sekunden auf faellige SchedulerJobs."

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval', type=int, default=5,
            help="Pruefintervall in Sekunden",
        )
        parser.add_argument(
            '--heartbeat-every', type=int, default=60,
            help="Alle N Ticks ein Lebenszeichen loggen (0 = aus)",
        )
        parser.add_argument(
            '--max-jobs-per-tick', type=int, default=200,
            help="Hartes Limit faelliger Jobs pro Tick",
        )

    def handle(self, *args, **options):
        interval = max(1, int(options['interval']))
        heartbeat_every = int(options['heartbeat_every'])
        max_jobs = max(1, int(options['max_jobs_per_tick']))
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
                dispatched_since_heartbeat += self._tick(max_jobs=max_jobs)
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

            self._sleep_interruptible(interval)

        self._log("Scheduler-Loop sauber beendet.")
        # Exit 0 nur bei Supervisor-Stop — sonst wuerde autorestart=unexpected
        # den Prozess nicht neu starten. Mit autorestart=true ist beides ok.
        sys.exit(0)

    def _stop(self, signum, frame):
        self._log(f"Stop-Signal {signum} empfangen — beende nach aktuellem Tick/Sleep")
        self._running = False

    def _sleep_interruptible(self, seconds):
        """Kurze Sleep-Chunks, damit SIGTERM nicht bis zu --interval wartet."""
        end = time.monotonic() + seconds
        while self._running:
            remaining = end - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.5, remaining))

    def _log(self, message):
        self.stdout.write(self.style.SUCCESS(message))
        try:
            self.stdout.flush()
        except Exception:
            pass
        logger.info(message)

    def _log_exception(self, message):
        self.stdout.write(self.style.ERROR(message))
        self.stdout.write(traceback.format_exc())
        try:
            self.stdout.flush()
        except Exception:
            pass
        logger.exception(message)

    def _tick(self, *, max_jobs=200):
        from apps.abpe_scheduler.models import SchedulerJob, SchedulerJobRun
        from apps.abpe_scheduler.tasks import execute_job

        now = timezone.now()
        due_jobs = SchedulerJob.objects.filter(
            status='ACTIVE', delivery_mode='PUSH', next_run_at__lte=now,
        ).exclude(next_run_at__isnull=True).order_by('next_run_at')[:max_jobs]

        dispatched = 0
        for job in due_jobs:
            if not self._running:
                break
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
                self._log_exception(
                    f"scheduler_loop: Job {job.id} konnte nicht dispatcht werden"
                )

        return dispatched
