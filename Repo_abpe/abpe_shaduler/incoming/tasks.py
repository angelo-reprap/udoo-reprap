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
    """IMAP Header+Preview (V1.1)."""
    logger.info('shaduler_inbox_poll: stub payload=%s', payload)
    return {'ok': True, 'stub': True, 'job': 'inbox_poll'}


def shaduler_prozess_tick(payload=None):
    """zeit_ohne_reaktion + fällige Schritte (V1)."""
    logger.info('shaduler_prozess_tick: stub payload=%s', payload)
    return {'ok': True, 'stub': True, 'job': 'prozess_tick'}


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
    'delegation-notify': shaduler_delegation_notify,
    'delegation_notify': shaduler_delegation_notify,
}
