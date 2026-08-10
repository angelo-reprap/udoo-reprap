"""Dünner HTTP-Client für die abpe_scheduler-API.

Muster wie abpe_meetme/scheduler_client.py — kein Import der Scheduler-Models.
Shaduler-Periodik (Radar/Inbox/Prozess) läuft über SchedulerJob + Webhook,
nicht über Celery Beat (Architektur Kap. 0, Befund 04.08.2026).
"""
import requests
from django.conf import settings


class SchedulerClientError(Exception):
    pass


def _base_url():
    return getattr(
        settings, 'SCHEDULER_API_BASE_URL', 'http://localhost:8000/scheduler/api',
    )


def _callback_base_url():
    return getattr(
        settings, 'SHADULER_CALLBACK_BASE_URL', 'http://localhost:8000/shaduler/api',
    )


def _headers():
    token = getattr(settings, 'SCHEDULER_SERVICE_TOKEN', '')
    if not token:
        raise SchedulerClientError(
            'SCHEDULER_SERVICE_TOKEN ist nicht in den Settings konfiguriert '
            '(gleicher Token wie MeetMe / abpe_scheduler).'
        )
    return {
        'Authorization': f'Token {token}',
        'Content-Type': 'application/json',
    }


def build_callback_url(path):
    """path z.B. 'radar-poll' → …/shaduler/api/webhook/radar-poll/?token=…

    abpe_scheduler POSTet ohne Authorization-Header (timeout=15).
    Token deshalb als Query-Param — api_webhook_job akzeptiert GET token=.
    """
    from urllib.parse import urlencode

    path = path.strip('/')
    url = f"{_callback_base_url().rstrip('/')}/webhook/{path}/"
    token = getattr(settings, 'SCHEDULER_SERVICE_TOKEN', '') or ''
    if token:
        url = f"{url}?{urlencode({'token': token})}"
    return url


def upsert_job(
    owner_type,
    owner_ref,
    job_key,
    schedule_type,
    callback_url,
    payload,
    run_at=None,
    rrule_string='',
    dtstart=None,
    until=None,
    delivery_mode='PUSH',
    max_retries=3,
    retry_backoff_seconds=300,
):
    body = {
        'owner_app': 'abpe_shaduler',
        'owner_type': owner_type,
        'owner_ref': owner_ref,
        'job_key': job_key,
        'schedule_type': schedule_type,
        'delivery_mode': delivery_mode,
        'callback_url': callback_url,
        'payload': payload or {},
        'max_retries': max_retries,
        'retry_backoff_seconds': retry_backoff_seconds,
    }
    if run_at is not None:
        body['run_at'] = run_at.isoformat()
    if rrule_string:
        body['rrule_string'] = rrule_string
    if dtstart is not None:
        body['dtstart'] = dtstart.isoformat()
    if until is not None:
        body['until'] = until.isoformat()

    try:
        resp = requests.post(
            f"{_base_url().rstrip('/')}/jobs/create/",
            json=body,
            headers=_headers(),
            timeout=10,
        )
    except requests.RequestException as exc:
        raise SchedulerClientError(str(exc)) from exc

    if not resp.ok:
        raise SchedulerClientError(f'HTTP {resp.status_code}: {resp.text[:500]}')
    return resp.json()


def cancel_job(job_id):
    try:
        resp = requests.delete(
            f"{_base_url().rstrip('/')}/jobs/{job_id}/cancel/",
            headers=_headers(),
            timeout=10,
        )
    except requests.RequestException as exc:
        raise SchedulerClientError(str(exc)) from exc

    if resp.status_code not in (204, 404):
        raise SchedulerClientError(f'HTTP {resp.status_code}: {resp.text[:500]}')
