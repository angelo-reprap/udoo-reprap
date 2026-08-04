"""
Celery-Tasks — Kap. 4 Architektur.
Beat-Einträge später in Celery-Config (nicht hier hardcoden).
"""
import logging

logger = logging.getLogger(__name__)

try:
    from celery import shared_task
except ImportError:  # pragma: no cover
    def shared_task(*args, **kwargs):
        def deco(fn):
            return fn
        return deco


@shared_task(name='shaduler_radar_poll')
def shaduler_radar_poll():
    """Aktive RadarSources rss/html abarbeiten (V2)."""
    logger.info('shaduler_radar_poll: stub')
    return {'ok': True, 'stub': True}


@shared_task(name='shaduler_inbox_poll')
def shaduler_inbox_poll():
    """IMAP Header+Preview (V1.1)."""
    logger.info('shaduler_inbox_poll: stub')
    return {'ok': True, 'stub': True}


@shared_task(name='shaduler_prozess_tick')
def shaduler_prozess_tick():
    """zeit_ohne_reaktion + fällige Schritte (V1)."""
    logger.info('shaduler_prozess_tick: stub')
    return {'ok': True, 'stub': True}


@shared_task(name='shaduler_delegation_notify')
def shaduler_delegation_notify(aufgabe_id: str, to_user_id: int):
    logger.info('shaduler_delegation_notify: stub %s → %s', aufgabe_id, to_user_id)
    return {'ok': True, 'stub': True}
