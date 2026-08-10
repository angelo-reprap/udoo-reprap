"""
Job-Handler für abpe_scheduler-Webhooks.

Architektur Kap. 0: KEIN Celery Beat — periodische Läufe als SchedulerJob
(RRULE) über scheduler_client, Callback auf /shaduler/api/webhook/<job>/.

Wichtig: abpe_scheduler POST mit timeout=15s. Lange Jobs (email_index,
radar_poll) dürfen im Webhook NICHT synchron laufen → Celery-Queue, sofort 200.
Celery down → Thread-Fallback (nicht sync im Request).
Indexer-Fehler → Celery-Retry 60s / 120s / 180s.
"""
import logging
import threading

logger = logging.getLogger(__name__)

EMAIL_INDEX_LOCK = 'shaduler:email_index:lock'
EMAIL_INDEX_LOCK_TTL = 600  # Sekunden — verhindert parallele IMAP-Läufe
EMAIL_INDEX_RETRY_BASE = 60  # 60 → 120 → 180

RADAR_POLL_LOCK = 'shaduler:radar_poll:lock'
RADAR_POLL_LOCK_TTL = 600  # FM+Gulp+Hays — kein Parallel-Lauf
RADAR_POLL_RETRY_BASE = 60
RADAR_POLL_LAST_OK = 'shaduler:radar_poll:last_ok'


def _radar_poll_kwargs(payload=None):
    payload = payload or {}
    try:
        pages = int(payload.get('pages') or 2)
    except (TypeError, ValueError):
        pages = 2
    today_only = str(payload.get('today', '1')).lower() not in ('0', 'false', 'no')
    try:
        days = max(1, min(14, int(payload.get('days') or 2)))
    except (TypeError, ValueError):
        days = 2
    return {
        'pages': max(1, min(5, pages)),
        'today_only': today_only,
        'recent_days': days,
    }


def _radar_poll_sync(*, pages=2, today_only=True, recent_days=2):
    """Sync: FM+Gulp+Hays → DB/ES. Nur aus Celery/Thread aufrufen (nicht Webhook)."""
    from django.core.cache import cache
    from django.utils import timezone

    if not cache.add(RADAR_POLL_LOCK, '1', RADAR_POLL_LOCK_TTL):
        return {'ok': True, 'job': 'radar_poll', 'skipped': 'lock'}
    try:
        from .services import radar_fetcher
        result = radar_fetcher.poll_once(
            pages=pages,
            today_only=today_only,
            recent_days=recent_days,
        )
        now_iso = timezone.now().isoformat()
        cache.set(RADAR_POLL_LAST_OK, now_iso, 86400)
        if isinstance(result, dict):
            result = {**result, 'job': 'radar_poll', 'last_ok': now_iso}
        return result
    except Exception as exc:
        logger.exception('radar_poll failed')
        return {'ok': False, 'error': str(exc), 'job': 'radar_poll'}
    finally:
        cache.delete(RADAR_POLL_LOCK)


def _radar_poll_thread(**kw):
    def _run():
        try:
            _radar_poll_sync(**kw)
        except Exception:
            logger.exception('radar_poll thread fallback failed')
    t = threading.Thread(target=_run, name='shaduler-radar-poll', daemon=True)
    t.start()
    return t.name


def shaduler_radar_poll(payload=None):
    """Webhook: sofort 200 — FM/Gulp/Hays-Poll asynchron (Scheduler-Timeout 15s)."""
    kw = _radar_poll_kwargs(payload)
    logger.info(
        'shaduler_radar_poll: queue pages=%s today_only=%s days=%s',
        kw['pages'], kw['today_only'], kw['recent_days'],
    )
    try:
        async_result = radar_poll_run.delay(**kw)
        return {
            'ok': True,
            'job': 'radar_poll',
            'queued': True,
            'via': 'celery',
            'task_id': getattr(async_result, 'id', None),
            **kw,
        }
    except Exception as exc:
        logger.warning('radar_poll Celery unavailable, thread fallback: %s', exc)
        name = _radar_poll_thread(**kw)
        return {
            'ok': True,
            'job': 'radar_poll',
            'queued': True,
            'via': 'thread',
            'thread': name,
            'celery_error': str(exc)[:200],
            **kw,
        }


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
    since = int(payload.get('since_days') or 2)
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


def _email_index_sync(*, since_days=2, account=None, folders='INBOX', incremental=True):
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
    def email_index_run(self, since_days=2, account=None, folders='INBOX', incremental=True):
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

    @shared_task(
        bind=True,
        name='abpe_shaduler.radar_poll_run',
        ignore_result=True,
        max_retries=3,
        soft_time_limit=540,
        time_limit=600,
    )
    def radar_poll_run(self, pages=2, today_only=True, recent_days=2):
        """Celery: FM+Gulp+Hays → DB/ES. Bei Fehler Retry 60/120/180s."""
        logger.info(
            'radar_poll_run start try=%s pages=%s today_only=%s days=%s',
            getattr(self.request, 'retries', 0), pages, today_only, recent_days,
        )
        try:
            result = _radar_poll_sync(
                pages=pages,
                today_only=today_only,
                recent_days=recent_days,
            )
        except SoftTimeLimitExceeded as exc:
            result = {'ok': False, 'error': f'soft_time_limit: {exc}', 'job': 'radar_poll'}
        except Exception as exc:
            result = {'ok': False, 'error': str(exc), 'job': 'radar_poll'}

        if result.get('ok') or result.get('skipped') == 'lock':
            logger.info(
                'radar_poll_run done: %s',
                {k: result.get(k) for k in ('ok', 'skipped', 'fetched', 'error')},
            )
            return result

        retries = int(getattr(self.request, 'retries', 0) or 0)
        countdown = RADAR_POLL_RETRY_BASE * (retries + 1)
        logger.warning(
            'radar_poll_run fail try=%s next_in=%ss err=%s',
            retries, countdown, (result.get('error') or '')[:160],
        )
        raise self.retry(
            countdown=countdown,
            exc=RuntimeError(result.get('error') or 'radar_poll failed'),
        )

except Exception:  # pragma: no cover — Celery optional beim Import
    def email_index_run(**kwargs):  # type: ignore
        return _email_index_sync(**kwargs)

    def radar_poll_run(**kwargs):  # type: ignore
        return _radar_poll_sync(**kwargs)


def shaduler_radar_berater_index(payload=None):
    """CRM gulp_id → Radar + Soft-Delete + ES (alle 30 Min)."""
    logger.info('shaduler_radar_berater_index: payload=%s', payload)
    payload = payload or {}
    try:
        from .services import radar_berater_service as rbs
        return rbs.sync_crm_index(
            limit=0,
            reindex=str(payload.get('reindex', '1')).lower() not in ('0', 'false', 'no'),
        )
    except Exception as exc:
        logger.exception('radar_berater_index failed')
        return {'ok': False, 'error': str(exc), 'job': 'radar_berater_index'}


def shaduler_delegation_notify(payload=None):
    """Benachrichtigungs-Mail bei Delegation (on-demand / Job)."""
    logger.info('shaduler_delegation_notify: stub payload=%s', payload)
    return {'ok': True, 'stub': True, 'job': 'delegation_notify'}


# Alias-Map für Webhook-Routing
JOB_HANDLERS = {
    'radar-poll': shaduler_radar_poll,
    'radar_poll': shaduler_radar_poll,
    'radar-berater-index': shaduler_radar_berater_index,
    'radar_berater_index': shaduler_radar_berater_index,
    'inbox-poll': shaduler_inbox_poll,
    'inbox_poll': shaduler_inbox_poll,
    'prozess-tick': shaduler_prozess_tick,
    'prozess_tick': shaduler_prozess_tick,
    'email-index': shaduler_email_index,
    'email_index': shaduler_email_index,
    'delegation-notify': shaduler_delegation_notify,
    'delegation_notify': shaduler_delegation_notify,
}
