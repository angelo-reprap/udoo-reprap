"""
Job-Handler für abpe_scheduler-Webhooks.

Architektur Kap. 0: KEIN Celery Beat — periodische Läufe als SchedulerJob
(RRULE) über scheduler_client, Callback auf /shaduler/api/webhook/<job>/.

Wichtig: abpe_scheduler POST mit timeout=15s. Lange Jobs (email_index)
dürfen im Webhook NICHT synchron laufen → Celery-Queue, sofort 200.
Celery down → Thread-Fallback (nicht sync im Request).
Indexer-Fehler → Celery-Retry 60s / 120s / 180s.
"""
import logging
import threading

logger = logging.getLogger(__name__)

EMAIL_INDEX_LOCK = 'shaduler:email_index:lock'
EMAIL_INDEX_LOCK_TTL = 600  # Sekunden — verhindert parallele IMAP-Läufe
EMAIL_INDEX_RETRY_BASE = 60  # 60 → 120 → 180


def shaduler_radar_poll(payload=None):
    """Aktive RadarSources rss/html abarbeiten (V2)."""
    logger.info('shaduler_radar_poll: stub payload=%s', payload)
    return {'ok': True, 'stub': True, 'job': 'radar_poll'}


def shaduler_inbox_poll(payload=None):
    """IMAP Header+Preview (V1.1) — warmt den Abruf / zählt Unread."""
    logger.info('shaduler_inbox_poll: payload=%s', payload)
    try:
        from .services import inbox_service
        data = inbox_service.list_mails(limit=30)
        return {
            'ok': bool(data.get('ok')),
            'job': 'inbox_poll',
            'source': data.get('source'),
            'count': len(data.get('results') or []),
            'unread': data.get('unread', 0),
            'error': data.get('error'),
        }
    except Exception as exc:
        logger.exception('inbox_poll failed')
        return {'ok': False, 'error': str(exc)}


def shaduler_prozess_tick(payload=None):
    """zeit_ohne_reaktion + fällige Schritte (V1)."""
    logger.info('shaduler_prozess_tick: payload=%s', payload)
    try:
        from .services import prozess_engine
        return prozess_engine.tick_zeit_ohne_reaktion()
    except Exception as exc:
        logger.exception('prozess_tick failed')
        return {'ok': False, 'error': str(exc)}


def _email_index_kwargs(payload=None):
    payload = payload or {}
    since = int(payload.get('since_days') or 7)
    account = payload.get('account')
    folders = str(payload.get('folders') or 'INBOX')
    incremental = payload.get('incremental', True)
    if isinstance(incremental, str):
        incremental = incremental.strip().lower() not in ('0', 'false', 'no', 'off')
    return {
        'since_days': since,
        'account': account,
        'folders': folders,
        'incremental': bool(incremental),
    }


def _email_index_thread(**kw):
    """Daemon-Thread wenn Celery/Broker nicht erreichbar — Webhook bleibt <15s."""
    def _run():
        try:
            _email_index_sync(**kw)
        except Exception:
            logger.exception('email_index thread fallback failed')
    t = threading.Thread(target=_run, name='shaduler-email-index', daemon=True)
    t.start()
    return t.name


def shaduler_email_index(payload=None):
    """Webhook: sofort 200, Index-Lauf asynchron via Celery (sonst Thread)."""
    kw = _email_index_kwargs(payload)
    logger.info(
        'shaduler_email_index: queue since_days=%s account=%s folders=%s incremental=%s',
        kw['since_days'], kw['account'], kw['folders'], kw['incremental'],
    )
    try:
        async_result = email_index_run.delay(**kw)
        return {
            'ok': True,
            'job': 'email_index',
            'queued': True,
            'via': 'celery',
            'task_id': getattr(async_result, 'id', None),
            **{k: v for k, v in kw.items() if k != 'account' or v},
        }
    except Exception as exc:
        # Celery/Broker down → Thread, nicht sync im HTTP-Request (15s-Timeout)
        logger.warning('email_index Celery unavailable, thread fallback: %s', exc)
        name = _email_index_thread(**kw)
        return {
            'ok': True,
            'job': 'email_index',
            'queued': True,
            'via': 'thread',
            'thread': name,
            'celery_error': str(exc)[:200],
            **{k: v for k, v in kw.items() if k != 'account' or v},
        }


def _email_index_sync(*, since_days=7, account=None, folders='INBOX', incremental=True):
    from django.core.cache import cache
    from django.core.management import call_command
    from io import StringIO

    if not cache.add(EMAIL_INDEX_LOCK, '1', EMAIL_INDEX_LOCK_TTL):
        return {'ok': True, 'job': 'email_index', 'skipped': 'lock'}
    try:
        out = StringIO()
        kwargs = {
            'since_days': since_days,
            'folders': folders,
            'incremental': bool(incremental),
            'stdout': out,
        }
        if account:
            kwargs['account'] = account
        call_command('index_emails', **kwargs)
        text = out.getvalue()
        return {
            'ok': True,
            'job': 'email_index',
            'since_days': since_days,
            'folders': folders,
            'incremental': bool(incremental),
            'log_tail': text[-800:],
        }
    except Exception as exc:
        logger.exception('email_index failed')
        return {'ok': False, 'error': str(exc)}
    finally:
        cache.delete(EMAIL_INDEX_LOCK)


try:
    from celery import shared_task
    from celery.exceptions import SoftTimeLimitExceeded

    @shared_task(
        bind=True,
        name='abpe_shaduler.email_index_run',
        ignore_result=True,
        max_retries=3,
        soft_time_limit=540,
        time_limit=600,
    )
    def email_index_run(self, since_days=7, account=None, folders='INBOX', incremental=True):
        """Celery: IMAP→ES. Bei Fehler Retry nach 60 / 120 / 180 Sekunden."""
        logger.info(
            'email_index_run start try=%s since_days=%s account=%s folders=%s incremental=%s',
            getattr(self.request, 'retries', 0), since_days, account, folders, incremental,
        )
        try:
            result = _email_index_sync(
                since_days=since_days,
                account=account,
                folders=folders,
                incremental=incremental,
            )
        except SoftTimeLimitExceeded as exc:
            result = {'ok': False, 'error': f'soft_time_limit: {exc}'}
        except Exception as exc:
            result = {'ok': False, 'error': str(exc)}

        if result.get('ok') or result.get('skipped') == 'lock':
            logger.info(
                'email_index_run done: %s',
                {k: result.get(k) for k in ('ok', 'skipped', 'error')},
            )
            return result

        retries = int(getattr(self.request, 'retries', 0) or 0)
        countdown = EMAIL_INDEX_RETRY_BASE * (retries + 1)  # 60, 120, 180
        logger.warning(
            'email_index_run fail try=%s next_in=%ss err=%s',
            retries, countdown, (result.get('error') or '')[:160],
        )
        raise self.retry(
            countdown=countdown,
            exc=RuntimeError(result.get('error') or 'email_index failed'),
        )

except Exception:  # pragma: no cover — Celery optional beim Import
    def email_index_run(**kwargs):  # type: ignore
        return _email_index_sync(**kwargs)


def shaduler_delegation_notify(payload=None):
    """Benachrichtigungs-Mail bei Delegation (on-demand / Job)."""
    logger.info('shaduler_delegation_notify: stub payload=%s', payload)
    return {'ok': True, 'stub': True, 'job': 'delegation_notify'}


# Alias-Map für Webhook-Routing
JOB_HANDLERS = {
    'radar-poll': shaduler_radar_poll,
    'radar_poll': shaduler_radar_poll,
    'inbox-poll': shaduler_inbox_poll,
    'inbox_poll': shaduler_inbox_poll,
    'prozess-tick': shaduler_prozess_tick,
    'prozess_tick': shaduler_prozess_tick,
    'email-index': shaduler_email_index,
    'email_index': shaduler_email_index,
    'delegation-notify': shaduler_delegation_notify,
    'delegation_notify': shaduler_delegation_notify,
}
