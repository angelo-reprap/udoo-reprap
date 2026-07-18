"""
System-Status-Snapshot für Email-Studio-Platzhalter.

Stufe 1: Disk, Django, DB, Celery, Scheduler, Aggregat
Stufe 2: Host/OS + Django/App (hostname, load, memory, uptime, version, env, cache)
Stufe 3: Celery-Details + HTML-Ampel (workers, queue depth, system_status_html)

Kurze Timeouts — darf Versand/Preview nicht blockieren.
Werte sind Strings für Template-Ersetzung.
"""
from __future__ import annotations

import html
import logging
import os
import shutil
import socket
import time
from pathlib import Path
from typing import Any

log = logging.getLogger('abpe_email_studio.system_status')

# Cache: Status-Checks nicht bei jedem Preview-Tick neu
_CACHE: dict[str, Any] = {'ts': 0.0, 'vars': {}}
_CACHE_TTL_SEC = 30.0
_CELERY_INSPECT_TIMEOUT = 0.4

_OK = 'OK'
_FAIL = 'FAIL'
_WARN = 'WARN'
_NA = 'n/a'

# Ampel-Farben für HTML-Mail (inline, Outlook-tauglich)
_COLOR = {
    _OK: '#15803d',
    _WARN: '#b45309',
    _FAIL: '#b91c1c',
    _NA: '#6b7280',
}


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


def _fmt_uptime(seconds: float) -> str:
    total = int(seconds)
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f'{days}d {hours}h'
    if hours:
        return f'{hours}h {minutes}m'
    return f'{minutes}m'


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


def _host_name() -> str:
    try:
        return socket.gethostname() or _NA
    except Exception:
        return _NA


def _load_avg() -> tuple[str, str]:
    """→ (load_avg text, flag). Flag relativ zu CPU-Anzahl."""
    try:
        load1, load5, load15 = os.getloadavg()
        text = f'{load1:.2f} {load5:.2f} {load15:.2f}'
        cpus = os.cpu_count() or 1
        ratio = load1 / float(cpus)
        if ratio < 0.85:
            flag = _OK
        elif ratio < 1.5:
            flag = _WARN
        else:
            flag = _FAIL
        return text, flag
    except Exception as exc:
        log.debug('loadavg failed: %s', exc)
        return _NA, _NA


def _memory_used_pct() -> tuple[str, str]:
    """→ (memory_used_pct, flag) via /proc/meminfo."""
    try:
        info: dict[str, int] = {}
        for line in Path('/proc/meminfo').read_text(encoding='utf-8').splitlines():
            if ':' not in line:
                continue
            key, rest = line.split(':', 1)
            parts = rest.strip().split()
            if not parts:
                continue
            try:
                info[key] = int(parts[0])  # kB
            except ValueError:
                continue
        total = info.get('MemTotal') or 0
        available = info.get('MemAvailable')
        if available is None:
            free = info.get('MemFree') or 0
            cached = (info.get('Cached') or 0) + (info.get('Buffers') or 0)
            available = free + cached
        if not total:
            return _NA, _NA
        used_pct = int(round(100.0 * (total - available) / total))
        flag = _OK if used_pct < 85 else (_WARN if used_pct < 95 else _FAIL)
        return f'{used_pct}%', flag
    except Exception as exc:
        log.debug('meminfo failed: %s', exc)
        return _NA, _NA


def _uptime() -> str:
    try:
        raw = Path('/proc/uptime').read_text(encoding='utf-8').split()[0]
        return _fmt_uptime(float(raw))
    except Exception as exc:
        log.debug('uptime failed: %s', exc)
        return _NA


def _django_version() -> str:
    try:
        import django
        return django.get_version()
    except Exception:
        return _NA


def _portal_env() -> str:
    for key in ('ABPE_ENV', 'PORTAL_ENV', 'DJANGO_ENV', 'ENVIRONMENT', 'ENV'):
        val = os.environ.get(key)
        if val:
            return str(val)
    try:
        from django.conf import settings
        if getattr(settings, 'DEBUG', False):
            return 'debug'
        return str(getattr(settings, 'ENVIRONMENT', '') or 'production')
    except Exception:
        return _NA


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


def _check_cache() -> str:
    """Django-Cache set/get mit kurzem Schlüssel — kein Secret."""
    try:
        from django.core.cache import cache
        key = 'abpe_email_studio:system_status:ping'
        token = f'ok-{int(time.time())}'
        cache.set(key, token, timeout=10)
        got = cache.get(key)
        return _OK if got == token else _FAIL
    except Exception as exc:
        log.debug('cache check failed: %s', exc)
        return _FAIL


def _celery_inspect():
    from celery import current_app
    return current_app.control.inspect(timeout=_CELERY_INSPECT_TIMEOUT)


def _check_celery() -> tuple[str, str]:
    """→ (celery_ok, celery_workers)"""
    try:
        inspector = _celery_inspect()
        if inspector is None:
            return _FAIL, '0'
        ping = inspector.ping() or {}
        n = len(ping)
        return (_OK if n else _FAIL), str(n)
    except Exception as exc:
        log.debug('celery check failed: %s', exc)
        return _FAIL, '0'


def _check_scheduler() -> str:
    """
    Celery Beat / Scheduler.
    1) django-celery-beat PeriodicTask (enabled)
    2) Fallback: celery inspect scheduled
    """
    try:
        from django_celery_beat.models import PeriodicTask
        if PeriodicTask.objects.filter(enabled=True).exists():
            return _OK
    except Exception:
        pass

    try:
        inspector = _celery_inspect()
        if inspector is None:
            return _NA
        scheduled = inspector.scheduled() or {}
        if scheduled:
            return _OK
        ping = inspector.ping() or {}
        return _WARN if ping else _FAIL
    except Exception as exc:
        log.debug('scheduler check failed: %s', exc)
        return _NA


def _celery_queue_depth() -> str:
    """Broker-Queue-Länge (Redis) — sonst n/a."""
    try:
        from celery import current_app
        conf = current_app.conf
        broker = str(getattr(conf, 'broker_url', '') or '')
        default_queue = str(getattr(conf, 'task_default_queue', None) or 'celery')
        if not broker.startswith('redis'):
            return _NA
        import redis
        client = redis.from_url(broker, socket_connect_timeout=0.4, socket_timeout=0.4)
        try:
            depth = int(client.llen(default_queue))
            return str(depth)
        finally:
            try:
                client.close()
            except Exception:
                pass
    except Exception as exc:
        log.debug('queue depth failed: %s', exc)
        return _NA


def _aggregate(*flags: str) -> str:
    usable = [f for f in flags if f != _NA]
    if not usable:
        return _NA
    if _FAIL in usable:
        return _FAIL
    if _WARN in usable:
        return _WARN
    if all(f == _OK for f in usable):
        return _OK
    return _WARN


def _status_html_rows(rows: list[tuple[str, str, str]]) -> str:
    """rows: (label, value, flag)"""
    parts = [
        '<table role="presentation" cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;font-family:Arial,sans-serif;'
        'font-size:13px;line-height:1.4;width:100%;max-width:520px;">',
        '<tr>'
        '<th align="left" style="padding:6px 8px;border-bottom:1px solid #d1d5db;">Check</th>'
        '<th align="left" style="padding:6px 8px;border-bottom:1px solid #d1d5db;">Wert</th>'
        '<th align="left" style="padding:6px 8px;border-bottom:1px solid #d1d5db;">Status</th>'
        '</tr>',
    ]
    for label, value, flag in rows:
        color = _COLOR.get(flag, _COLOR[_NA])
        parts.append(
            '<tr>'
            f'<td style="padding:6px 8px;border-bottom:1px solid #e5e7eb;">{html.escape(label)}</td>'
            f'<td style="padding:6px 8px;border-bottom:1px solid #e5e7eb;">{html.escape(value)}</td>'
            f'<td style="padding:6px 8px;border-bottom:1px solid #e5e7eb;'
            f'font-weight:bold;color:{color};">{html.escape(flag)}</td>'
            '</tr>'
        )
    parts.append('</table>')
    return ''.join(parts)


def collect_system_status(*, use_cache: bool = True) -> dict[str, str]:
    """
    Liefert Platzhalter-Werte für Templates.

    Stufe 1: disk_*, django_ok, db_ok, celery_ok, scheduler_ok, system_status[_list]
    Stufe 2: host_name, load_avg, uptime, memory_used_pct, django_version, portal_env, cache_ok
    Stufe 3: celery_workers, celery_queue_depth, system_status_html
    """
    now = time.monotonic()
    if use_cache and _CACHE['vars'] and (now - float(_CACHE['ts'])) < _CACHE_TTL_SEC:
        return dict(_CACHE['vars'])

    disk_free, disk_used_pct, disk_flag = _check_disk('/')
    host_name = _host_name()
    load_avg, load_flag = _load_avg()
    memory_used_pct, mem_flag = _memory_used_pct()
    uptime = _uptime()

    django_ok = _OK  # Prozess läuft, sonst wären wir nicht hier
    django_version = _django_version()
    portal_env = _portal_env()
    db_ok = _check_db()
    cache_ok = _check_cache()

    celery_ok, celery_workers = _check_celery()
    scheduler_ok = _check_scheduler()
    celery_queue_depth = _celery_queue_depth()

    system_status = _aggregate(
        disk_flag, load_flag, mem_flag,
        django_ok, db_ok, cache_ok,
        celery_ok, scheduler_ok,
    )

    lines = [
        f'Host: {host_name}',
        f'Disk frei: {disk_free} (belegt {disk_used_pct}) → {disk_flag}',
        f'Load: {load_avg} → {load_flag}',
        f'Speicher: {memory_used_pct} → {mem_flag}',
        f'Uptime: {uptime}',
        f'Django: {django_ok} (v{django_version}, env={portal_env})',
        f'Datenbank: {db_ok}',
        f'Cache: {cache_ok}',
        f'Celery Worker: {celery_ok} ({celery_workers})',
        f'Celery Queue: {celery_queue_depth}',
        f'Scheduler/Beat: {scheduler_ok}',
        f'Gesamt: {system_status}',
    ]

    html_rows = [
        ('Host', host_name, _OK if host_name != _NA else _NA),
        ('Disk frei', f'{disk_free} ({disk_used_pct})', disk_flag),
        ('Load', load_avg, load_flag),
        ('Speicher', memory_used_pct, mem_flag),
        ('Uptime', uptime, _OK if uptime != _NA else _NA),
        ('Django', f'{django_ok} v{django_version}', django_ok),
        ('Umgebung', portal_env, _OK if portal_env != _NA else _NA),
        ('Datenbank', db_ok, db_ok),
        ('Cache', cache_ok, cache_ok),
        ('Celery Worker', f'{celery_ok} ({celery_workers})', celery_ok),
        ('Celery Queue', celery_queue_depth, _OK if celery_queue_depth not in (_NA, '') else _NA),
        ('Scheduler/Beat', scheduler_ok, scheduler_ok),
        ('Gesamt', system_status, system_status),
    ]

    result = {
        'disk_free': disk_free,
        'disk_used_pct': disk_used_pct,
        'host_name': host_name,
        'load_avg': load_avg,
        'uptime': uptime,
        'memory_used_pct': memory_used_pct,
        'django_ok': django_ok,
        'django_version': django_version,
        'portal_env': portal_env,
        'db_ok': db_ok,
        'cache_ok': cache_ok,
        'celery_ok': celery_ok,
        'celery_workers': celery_workers,
        'celery_queue_depth': celery_queue_depth,
        'scheduler_ok': scheduler_ok,
        'system_status': system_status,
        'system_status_list': '\n'.join(lines),
        'system_status_html': _status_html_rows(html_rows),
    }
    _CACHE['ts'] = now
    _CACHE['vars'] = dict(result)
    return result


def clear_system_status_cache() -> None:
    _CACHE['ts'] = 0.0
    _CACHE['vars'] = {}
