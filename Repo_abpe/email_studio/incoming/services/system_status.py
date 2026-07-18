"""
System-Status-Snapshot für Email-Studio-Platzhalter.

Kurze Timeouts — darf Versand/Preview nicht blockieren.
Werte sind Strings für Template-Ersetzung.
"""
from __future__ import annotations

import logging
import shutil
import time
from typing import Any

log = logging.getLogger('abpe_email_studio.system_status')

# Cache: Status-Checks nicht bei jedem Preview-Tick neu
_CACHE: dict[str, Any] = {'ts': 0.0, 'vars': {}}
_CACHE_TTL_SEC = 30.0

_OK = 'OK'
_FAIL = 'FAIL'
_WARN = 'WARN'
_NA = 'n/a'


def _fmt_bytes(n: int) -> str:
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = float(n)
    for u in units:
        if size < 1024 or u == units[-1]:
            if u == 'B':
                return f'{int(size)} {u}'
            return f'{size:.1f} {u}'
        size /= 1024
    return f'{n} B'


def _check_disk(path: str = '/') -> tuple[str, str, str]:
    """→ (disk_free, disk_used_pct, ok_flag)"""
    try:
        usage = shutil.disk_usage(path)
        free = _fmt_bytes(usage.free)
        used_pct = int(round(100.0 * usage.used / usage.total)) if usage.total else 0
        flag = _OK if used_pct < 90 else (_WARN if used_pct < 95 else _FAIL)
        return free, f'{used_pct}%', flag
    except Exception as exc:
        log.debug('disk check failed: %s', exc)
        return _NA, _NA, _FAIL


def _check_db() -> str:
    try:
        from django.db import connection
        with connection.cursor() as cur:
            cur.execute('SELECT 1')
            cur.fetchone()
        return _OK
    except Exception as exc:
        log.debug('db check failed: %s', exc)
        return _FAIL


def _check_celery() -> str:
    try:
        from celery import current_app
        inspector = current_app.control.inspect(timeout=0.4)
        if inspector is None:
            return _FAIL
        ping = inspector.ping() or {}
        return _OK if ping else _FAIL
    except Exception as exc:
        log.debug('celery check failed: %s', exc)
        return _FAIL


def _check_scheduler() -> str:
    """
    Celery Beat / Scheduler.
    1) django-celery-beat PeriodicTask (enabled)
    2) Fallback: celery inspect scheduled (nicht leer = Beat aktiv)
    """
    try:
        from django_celery_beat.models import PeriodicTask
        if PeriodicTask.objects.filter(enabled=True).exists():
            return _OK
    except Exception:
        pass

    try:
        from celery import current_app
        inspector = current_app.control.inspect(timeout=0.4)
        if inspector is None:
            return _NA
        scheduled = inspector.scheduled() or {}
        if scheduled:
            return _OK
        # Worker da, aber keine scheduled entries → Beat evtl. nicht aktiv
        ping = inspector.ping() or {}
        return _WARN if ping else _FAIL
    except Exception as exc:
        log.debug('scheduler check failed: %s', exc)
        return _NA


def _aggregate(*flags: str) -> str:
    if _FAIL in flags:
        return _FAIL
    if _WARN in flags:
        return _WARN
    if all(f in (_OK, _NA) for f in flags) and any(f == _OK for f in flags):
        return _OK
    if all(f == _NA for f in flags):
        return _NA
    return _WARN


def collect_system_status(*, use_cache: bool = True) -> dict[str, str]:
    """
    Liefert Platzhalter-Werte für Templates.

    Keys:
      disk_free, disk_used_pct, django_ok, db_ok, celery_ok,
      scheduler_ok, system_status, system_status_list
    """
    now = time.monotonic()
    if use_cache and _CACHE['vars'] and (now - float(_CACHE['ts'])) < _CACHE_TTL_SEC:
        return dict(_CACHE['vars'])

    disk_free, disk_used_pct, disk_flag = _check_disk('/')
    django_ok = _OK  # Prozess läuft, sonst wären wir nicht hier
    db_ok = _check_db()
    celery_ok = _check_celery()
    scheduler_ok = _check_scheduler()
    system_status = _aggregate(disk_flag, django_ok, db_ok, celery_ok, scheduler_ok)

    lines = [
        f'Disk frei: {disk_free} (belegt {disk_used_pct}) → {disk_flag}',
        f'Django: {django_ok}',
        f'Datenbank: {db_ok}',
        f'Celery Worker: {celery_ok}',
        f'Scheduler/Beat: {scheduler_ok}',
        f'Gesamt: {system_status}',
    ]
    result = {
        'disk_free': disk_free,
        'disk_used_pct': disk_used_pct,
        'django_ok': django_ok,
        'db_ok': db_ok,
        'celery_ok': celery_ok,
        'scheduler_ok': scheduler_ok,
        'system_status': system_status,
        'system_status_list': '\n'.join(lines),
    }
    _CACHE['ts'] = now
    _CACHE['vars'] = dict(result)
    return result


def clear_system_status_cache() -> None:
    _CACHE['ts'] = 0.0
    _CACHE['vars'] = {}
