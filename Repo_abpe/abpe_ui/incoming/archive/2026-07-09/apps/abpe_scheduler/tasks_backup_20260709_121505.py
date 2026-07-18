"""Celery Tasks fuer abpe_scheduler.
Laeuft im bestehenden, stabilen Celery-Worker (kein Beat noetig) —
ausgeloest wird das ueber management/commands/scheduler_loop.py."""
import logging

import requests
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name='scheduler_execute_job', bind=True)
def execute_job(self, job_id):
    from .models import SchedulerJob, SchedulerJobRun
    from .recurrence import compute_next_run

    try:
        job = SchedulerJob.objects.get(id=job_id)
    except SchedulerJob.DoesNotExist:
        return

    now = timezone.now()

    # Idempotenz: falls fuer diesen Zeitpunkt schon ein Run existiert, nicht doppelt ausfuehren
    run, created = SchedulerJobRun.objects.get_or_create(
        job=job, scheduled_for=job.next_run_at or now,
        defaults={'status': 'RUNNING', 'started_at': now, 'attempt': 1},
    )
    if not created:
        return

    try:
        resp = requests.post(job.callback_url, json=job.payload, timeout=15)
        run.response_status = resp.status_code
        run.response_body = resp.text[:2000]
        run.status = 'SUCCESS' if resp.ok else 'FAILED'
        if not resp.ok:
            run.error_message = f"HTTP {resp.status_code}"
    except requests.RequestException as exc:
        run.status = 'FAILED'
        run.error_message = str(exc)[:2000]
        logger.warning("scheduler execute_job failed job=%s: %s", job_id, exc)

    run.finished_at = timezone.now()
    run.save()

    if run.status == 'FAILED' and run.attempt < job.max_retries:
        run.attempt += 1
        run.status = 'PENDING'
        run.save(update_fields=['attempt', 'status'])
        execute_job.apply_async(args=[job_id], countdown=job.retry_backoff_seconds)
        return

    if job.schedule_type == 'ONCE':
        job.status = 'COMPLETED'
        job.next_run_at = None
    else:
        job.next_run_at = compute_next_run(job, after=timezone.now())
        if job.next_run_at is None:
            job.status = 'COMPLETED'
    job.save(update_fields=['status', 'next_run_at', 'updated_at'])
