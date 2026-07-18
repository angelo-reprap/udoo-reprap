"""
Eigener Scheduler-Loop statt Celery Beat.
Prueft alle --interval Sekunden auf faellige Jobs und uebergibt sie
an den bereits laufenden Celery-Worker. Kein Lock-File, kein Beat.
"""
import logging
import signal
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Laeuft dauerhaft, prueft alle --interval Sekunden auf faellige SchedulerJobs."

    def add_arguments(self, parser):
        parser.add_argument('--interval', type=int, default=5, help="Pruefintervall in Sekunden")

    def handle(self, *args, **options):
        interval = options['interval']
        self._running = True
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)

        self.stdout.write(self.style.SUCCESS(f"Scheduler-Loop gestartet, Intervall {interval}s"))

        while self._running:
            try:
                self._tick()
            except Exception as exc:
                logger.exception("scheduler_loop tick failed: %s", exc)
            time.sleep(interval)

        self.stdout.write("Scheduler-Loop sauber beendet.")

    def _stop(self, signum, frame):
        self._running = False

    def _tick(self):
        from apps.abpe_scheduler.models import SchedulerJob, SchedulerJobRun
        from apps.abpe_scheduler.tasks import execute_job

        now = timezone.now()
        due_jobs = SchedulerJob.objects.filter(
            status='ACTIVE', delivery_mode='PUSH', next_run_at__lte=now,
        ).exclude(next_run_at__isnull=True)

        for job in due_jobs:
            if job.lock_key:
                running = SchedulerJobRun.objects.filter(
                    job__lock_key=job.lock_key, status='RUNNING',
                ).exclude(job=job).exists()
                if running:
                    continue
            execute_job.delay(job.id)
            logger.info("scheduler_loop: dispatched job %s (%s:%s:%s)",
                        job.id, job.owner_app, job.owner_type, job.owner_ref)
