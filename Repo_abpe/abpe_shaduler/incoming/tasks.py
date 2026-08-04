"""
Job-Handler für abpe_scheduler-Webhooks.

Architektur Kap. 0: KEIN Celery Beat — periodische Läufe als SchedulerJob
(RRULE) über scheduler_client, Callback auf /shaduler/api/webhook/<job>/.

Die Funktionsnamen bleiben an Kap. 4 angelehnt (radar_poll, inbox_poll, …).
"""
import logging

logger = logging.getLogger(__name__)


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


def shaduler_email_index(payload=None):
    """Namazu IMAP→ES Indexer (abpe_emails). Default: INBOX, letzte N Tage."""
    payload = payload or {}
    since = int(payload.get('since_days') or 3)
    account = payload.get('account')
    logger.info('shaduler_email_index: since_days=%s account=%s', since, account)
    try:
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        kwargs = {'since_days': since, 'stdout': out}
        if account:
            kwargs['account'] = account
        call_command('index_emails', **kwargs)
        text = out.getvalue()
        return {
            'ok': True,
            'job': 'email_index',
            'since_days': since,
            'log_tail': text[-800:],
        }
    except Exception as exc:
        logger.exception('email_index failed')
        return {'ok': False, 'error': str(exc)}


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
