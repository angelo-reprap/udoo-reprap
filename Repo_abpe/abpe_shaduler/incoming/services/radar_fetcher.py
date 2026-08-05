"""
Radar-Fetcher — Freelancermap HTML/JSON auslesen.

Liest die eingebetteten application/json-Blöcke der Projektliste
(https://www.freelancermap.de/projekte) und normalisiert sie zu Radar-Items.
Optional: Persistenz in RadarItem / RadarSource.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import date, datetime, timedelta
from html import unescape
from typing import Any, Optional
from urllib.parse import urljoin
from urllib.request import Request, urlopen

log = logging.getLogger('abpe_shaduler.radar_fetcher')

FM_LIST_URL = 'https://www.freelancermap.de/projekte'
FM_UA = (
    'Mozilla/5.0 (compatible; ABpE-Radar/1.0; +https://abcona.de) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)
SOURCE_NAME = 'freelancermap'
SOURCE_URL = FM_LIST_URL

_TAG_RE = re.compile(r'<[^>]+>')
_WS_RE = re.compile(r'\s+')
_JSON_SCRIPT_RE = re.compile(
    r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)


def ping() -> bool:
    return True


def _strip_html(html: str) -> str:
    if not html:
        return ''
    text = _TAG_RE.sub(' ', html)
    text = unescape(text)
    return _WS_RE.sub(' ', text).strip()


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        # freelancermap „updated/expires“ oft Unix-Sekunden
        try:
            ts = float(value)
            if ts > 10_000_000_000:  # ms
                ts /= 1000.0
            return datetime.fromtimestamp(ts)
        except Exception:
            return None
    s = str(value).strip()
    if not s:
        return None
    try:
        # 2026-08-05T15:06:37+02:00
        return datetime.fromisoformat(s)
    except Exception:
        pass
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(s[:19], fmt)
        except Exception:
            continue
    return None


def _project_url(raw: dict) -> str:
    links = raw.get('links') or {}
    if isinstance(links, dict):
        proj = links.get('project') or ''
        if proj:
            return urljoin('https://www.freelancermap.de', proj)
    pid = raw.get('id') or raw.get('pid')
    if pid:
        return f'https://www.freelancermap.de/projekte?id={pid}'
    slug = raw.get('slug') or ''
    if slug:
        return f'https://www.freelancermap.de/projekt/{slug}'
    return FM_LIST_URL


def _remote_pct(raw: dict) -> Optional[int]:
    pct = raw.get('projectContractType') or {}
    if isinstance(pct, dict) and pct.get('remoteInPercent') is not None:
        try:
            return int(pct.get('remoteInPercent'))
        except Exception:
            return None
    links = raw.get('links') or {}
    if isinstance(links, dict):
        loc = links.get('location') or {}
        if isinstance(loc, dict) and loc.get('remote'):
            return 100
    return None


def _skills(raw: dict) -> list[str]:
    skills = raw.get('skills') or []
    out: list[str] = []
    if isinstance(skills, list):
        for s in skills:
            if isinstance(s, str) and s.strip():
                out.append(s.strip())
            elif isinstance(s, dict):
                name = s.get('name') or s.get('nameDe') or s.get('label') or ''
                if name:
                    out.append(str(name).strip())
    return out


def normalize_project(raw: dict, *, source: str = SOURCE_NAME) -> dict:
    """Roh-JSON → UI-/DB-freundliches Dict."""
    pid = str(raw.get('id') or raw.get('pid') or '').strip()
    title = str(raw.get('title') or '').strip()
    desc_html = str(raw.get('description') or '')
    desc_plain = _strip_html(desc_html)
    company = str(raw.get('company') or (raw.get('poster') or {}).get('company') or '').strip()
    first = str(raw.get('firstName') or (raw.get('poster') or {}).get('firstName') or '').strip()
    last = str(raw.get('lastName') or (raw.get('poster') or {}).get('lastName') or '').strip()
    contact = f'{first} {last}'.strip()
    city = str(raw.get('city') or '').strip()
    if not city:
        locs = raw.get('locations') or []
        if isinstance(locs, list) and locs:
            city = str((locs[0] or {}).get('name') or '').strip()
    created = _parse_dt(raw.get('created'))
    remote = _remote_pct(raw)
    duration = raw.get('duration')
    duration_text = raw.get('durationText') or (
        f'{duration} Monate' if duration not in (None, '') else ''
    )
    beginning = str(raw.get('beginningText') or '').strip()
    industry = ''
    ind = raw.get('industry')
    if isinstance(ind, dict):
        industry = str(ind.get('nameDe') or ind.get('name') or '').strip()
    elif isinstance(ind, str):
        industry = ind.strip()

    url = _project_url(raw)
    dedup = hashlib.sha256(f'{source}:{pid or url}:{title}'.encode('utf-8')).hexdigest()

    meta_parts = []
    if beginning:
        meta_parts.append(f'Start {beginning}')
    if duration_text:
        meta_parts.append(str(duration_text))
    if city:
        meta_parts.append(city)
    if remote is not None:
        meta_parts.append(f'{remote}% Remote' if remote < 100 else '100% Remote')
    if company:
        meta_parts.append(company)

    eckdaten = {
        'project_id': pid,
        'slug': raw.get('slug') or '',
        'company': company,
        'contact': contact,
        'contact_first': first,
        'contact_last': last,
        'city': city,
        'country': (
            (raw.get('country') or {}).get('nameDe')
            if isinstance(raw.get('country'), dict) else ''
        ),
        'remote_percent': remote,
        'beginning': beginning,
        'duration': duration,
        'duration_text': duration_text,
        'industry': industry,
        'contract_type': raw.get('contractType') or '',
        'created': created.isoformat() if created else str(raw.get('created') or ''),
        'source': source,
        'url': url,
    }

    age = ''
    if created:
        try:
            delta = datetime.now(created.tzinfo) - created if created.tzinfo else datetime.now() - created
            mins = int(delta.total_seconds() // 60)
            if mins < 60:
                age = f'vor {max(mins, 0)} Min'
            elif mins < 60 * 24:
                age = f'vor {mins // 60} Std'
            else:
                age = f'vor {mins // (60 * 24)} T'
        except Exception:
            age = ''

    return {
        'id': f'fm-{pid}' if pid else dedup[:16],
        'external_id': pid,
        'dedup_hash': dedup,
        'headline': title or f'Projekt {pid}',
        'beschreibung': desc_plain,
        'beschreibung_html': desc_html,
        'skills': _skills(raw),
        'eckdaten': eckdaten,
        'meta': ' · '.join(meta_parts),
        'age': age,
        'sources': [source],
        'score': None,
        'grp': 1,
        'top': [],
        'status': 'neu',
        'external_url': url,
        'eingegangen_am': created.isoformat() if created else None,
        'company': company,
        'contact': contact,
        'city': city,
        'raw_created': created.isoformat() if created else None,
    }


def extract_projects_from_html(html: str) -> list[dict]:
    """Extrahiert Projekt-Dicts aus freelancermap HTML."""
    projects: list[dict] = []
    seen: set[str] = set()
    for blob in _JSON_SCRIPT_RE.findall(html or ''):
        if 'initialState' not in blob and 'initialResults' not in blob and '"title"' not in blob:
            continue
        try:
            data = json.loads(blob)
        except Exception:
            continue
        candidates: list = []
        if isinstance(data, dict):
            init = data.get('initialResults')
            if isinstance(init, list):
                candidates.extend(init)
            state = data.get('initialState') or {}
            if isinstance(state, dict):
                result = state.get('result') or {}
                if isinstance(result, dict):
                    for key in ('projects', 'topProjects'):
                        arr = result.get(key)
                        if isinstance(arr, list):
                            candidates.extend(arr)
            # Fallback: nested search for list of project-like dicts
            if not candidates:
                def walk(o):
                    if isinstance(o, list) and o and isinstance(o[0], dict) and 'title' in o[0] and 'id' in o[0]:
                        candidates.extend(o)
                        return
                    if isinstance(o, dict):
                        for v in o.values():
                            walk(v)
                walk(data)
        for raw in candidates:
            if not isinstance(raw, dict):
                continue
            pid = str(raw.get('id') or '').strip()
            if not pid or pid in seen:
                continue
            if not raw.get('title'):
                continue
            seen.add(pid)
            projects.append(raw)
    return projects


def fetch_html(url: str = FM_LIST_URL, *, timeout: int = 25) -> str:
    req = Request(url, headers={
        'User-Agent': FM_UA,
        'Accept': 'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8',
        'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
    })
    with urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or 'utf-8'
        return resp.read().decode(charset, errors='replace')


def fetch_freelancermap_projects(
    *,
    pages: int = 1,
    today_only: bool = True,
    day: Optional[date] = None,
) -> list[dict]:
    """
    Lädt 1..N Listenseiten und gibt normalisierte Projekte zurück.
    today_only: nur Einträge mit created == day (Default: heute).
    """
    day = day or date.today()
    out: list[dict] = []
    seen: set[str] = set()
    for page in range(1, max(1, int(pages)) + 1):
        url = FM_LIST_URL if page == 1 else f'{FM_LIST_URL}?pagenr={page}#list'
        try:
            html = fetch_html(url)
        except Exception as exc:
            log.warning('freelancermap fetch failed page=%s: %s', page, exc)
            break
        raws = extract_projects_from_html(html)
        if not raws:
            log.info('freelancermap page=%s: keine Projekte im JSON', page)
            break
        for raw in raws:
            item = normalize_project(raw)
            pid = item.get('external_id') or item['id']
            if pid in seen:
                continue
            if today_only:
                created = _parse_dt(item.get('raw_created') or (item.get('eckdaten') or {}).get('created'))
                if not created:
                    continue
                if created.date() != day:
                    continue
            seen.add(pid)
            out.append(item)
    out.sort(key=lambda x: x.get('raw_created') or '', reverse=True)
    return out


def ensure_freelancermap_source():
    """RadarSource freelancermap anlegen/holen."""
    from apps.abpe_shaduler.models import RadarSource
    src, _ = RadarSource.objects.get_or_create(
        name=SOURCE_NAME,
        defaults={
            'typ': RadarSource.Typ.HTML_PUBLIC,
            'url': SOURCE_URL,
            'ziel': RadarSource.Ziel.ANFRAGEN,
            'intervall_min': 5,
            'aktiv': True,
        },
    )
    return src


def persist_items(items: list[dict], *, archive_older: bool = True) -> dict:
    """
    Upsert RadarItem. archive_older: ältere „neu“-Items derselben Quelle → verworfen
    (Tages-Archiv-Idee: nur heutige bleiben aktiv sichtbar).
    """
    from django.utils import timezone
    from apps.abpe_shaduler.models import RadarItem

    src = ensure_freelancermap_source()
    created = 0
    updated = 0
    hashes = []
    for it in items:
        dedup = it['dedup_hash']
        hashes.append(dedup)
        obj = RadarItem.objects.filter(quelle=src, dedup_hash=dedup).first()
        fields = {
            'external_url': it.get('external_url') or '',
            'headline': (it.get('headline') or '')[:250],
            'beschreibung': it.get('beschreibung') or '',
            'skills': it.get('skills') or [],
            'eckdaten': it.get('eckdaten') or {},
        }
        if obj:
            for k, v in fields.items():
                setattr(obj, k, v)
            if obj.status == RadarItem.Status.VERWORFEN:
                # wieder sichtbar wenn erneut am heutigen Tag gefunden
                obj.status = RadarItem.Status.NEU
            obj.save()
            updated += 1
        else:
            RadarItem.objects.create(
                quelle=src,
                dedup_hash=dedup,
                status=RadarItem.Status.NEU,
                **fields,
            )
            created += 1

    archived = 0
    if archive_older:
        # Alles andere „neu“ von dieser Quelle, das heute nicht mehr kam → archivieren
        qs = RadarItem.objects.filter(quelle=src, status=RadarItem.Status.NEU)
        if hashes:
            qs = qs.exclude(dedup_hash__in=hashes)
        # nur Items, die älter als heute Mitternacht sind
        start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        qs = qs.filter(eingegangen_am__lt=start)
        archived = qs.update(status=RadarItem.Status.VERWORFEN)

    src.letzter_lauf = timezone.now()
    src.letzter_status = f'ok +{created}/~{updated}/arch {archived}'
    src.save(update_fields=['letzter_lauf', 'letzter_status'])

    return {
        'ok': True,
        'source': SOURCE_NAME,
        'created': created,
        'updated': updated,
        'archived': archived,
        'fetched': len(items),
    }


def serialize_db_item(obj) -> dict:
    eck = obj.eckdaten or {}
    return {
        'id': str(obj.pk),
        'external_id': eck.get('project_id') or '',
        'dedup_hash': obj.dedup_hash,
        'headline': obj.headline,
        'beschreibung': obj.beschreibung,
        'skills': obj.skills or [],
        'eckdaten': eck,
        'meta': ' · '.join([
            x for x in [
                eck.get('beginning') and f"Start {eck.get('beginning')}",
                eck.get('duration_text'),
                eck.get('city'),
                (f"{eck.get('remote_percent')}% Remote"
                 if eck.get('remote_percent') is not None else None),
                eck.get('company'),
            ] if x
        ]),
        'age': '',
        'sources': [SOURCE_NAME],
        'score': obj.quick_score,
        'grp': 1,
        'top': obj.top_berater or [],
        'status': obj.status,
        'external_url': obj.external_url,
        'eingegangen_am': obj.eingegangen_am.isoformat() if obj.eingegangen_am else None,
        'company': eck.get('company') or '',
        'contact': eck.get('contact') or '',
        'city': eck.get('city') or '',
    }


def list_anfragen(
    *,
    use_live_fetch: bool = True,
    today_only: bool = True,
    persist: bool = True,
    pages: int = 1,
    status: str = 'neu',
) -> dict:
    """
    Primärer Einstieg für API.
    1) Optional live von freelancermap holen + persistieren
    2) Aus DB lesen (Status neu), Fallback: Live-Liste ohne DB
    """
    fetched: list[dict] = []
    persist_info: dict = {}
    if use_live_fetch:
        try:
            fetched = fetch_freelancermap_projects(pages=pages, today_only=today_only)
            if persist:
                try:
                    persist_info = persist_items(fetched, archive_older=today_only)
                except Exception as exc:
                    log.warning('persist RadarItem failed: %s', exc)
                    persist_info = {'ok': False, 'error': str(exc)}
        except Exception as exc:
            log.warning('live fetch failed: %s', exc)
            persist_info = {'ok': False, 'error': str(exc)}

    results: list[dict] = []
    try:
        from apps.abpe_shaduler.models import RadarItem, RadarSource
        src = RadarSource.objects.filter(name=SOURCE_NAME).first()
        qs = RadarItem.objects.all()
        if src:
            qs = qs.filter(quelle=src)
        if status:
            qs = qs.filter(status=status)
        qs = qs.order_by('-eingegangen_am')[:200]
        results = [serialize_db_item(o) for o in qs]
    except Exception as exc:
        log.warning('DB list failed, fallback live: %s', exc)
        results = fetched

    if not results and fetched:
        results = fetched

    return {
        'ok': True,
        'demo': False,
        'source': SOURCE_NAME,
        'results': results,
        'count': len(results),
        'fetched': len(fetched),
        'persist': persist_info,
    }


def get_item(item_id: str) -> Optional[dict]:
    """Detail per UUID oder fm-<projectId>."""
    # Live/DB UUID
    try:
        from apps.abpe_shaduler.models import RadarItem
        import uuid as _uuid
        try:
            uid = _uuid.UUID(str(item_id))
            obj = RadarItem.objects.filter(pk=uid).first()
            if obj:
                return serialize_db_item(obj)
        except Exception:
            pass
        # eckdaten.project_id
        pid = str(item_id)
        if pid.startswith('fm-'):
            pid = pid[3:]
        obj = RadarItem.objects.filter(eckdaten__project_id=pid).first()
        if obj:
            return serialize_db_item(obj)
    except Exception as exc:
        log.debug('get_item db: %s', exc)

    # Live-Nachladen: Listenseite + Filter
    try:
        items = fetch_freelancermap_projects(pages=2, today_only=False)
        pid = str(item_id)
        if pid.startswith('fm-'):
            pid = pid[3:]
        for it in items:
            if str(it.get('external_id')) == pid or str(it.get('id')) == str(item_id):
                return it
    except Exception as exc:
        log.warning('get_item live failed: %s', exc)
    return None


def set_status(item_id: str, status: str) -> dict:
    from apps.abpe_shaduler.models import RadarItem
    import uuid as _uuid
    obj = None
    try:
        obj = RadarItem.objects.filter(pk=_uuid.UUID(str(item_id))).first()
    except Exception:
        obj = None
    if not obj:
        pid = str(item_id)[3:] if str(item_id).startswith('fm-') else str(item_id)
        obj = RadarItem.objects.filter(eckdaten__project_id=pid).first()
    if not obj:
        return {'ok': False, 'error': 'nicht gefunden'}
    if status not in dict(RadarItem.Status.choices):
        return {'ok': False, 'error': f'ungültiger Status: {status}'}
    obj.status = status
    obj.save(update_fields=['status', 'updated_at'])
    return {'ok': True, 'item': serialize_db_item(obj)}


def poll_once(*, pages: int = 1, today_only: bool = True) -> dict:
    """Für Scheduler / management command."""
    items = fetch_freelancermap_projects(pages=pages, today_only=today_only)
    info = persist_items(items, archive_older=today_only)
    info['items_sample'] = [
        {'id': i.get('external_id'), 'headline': i.get('headline')} for i in items[:5]
    ]
    return info
