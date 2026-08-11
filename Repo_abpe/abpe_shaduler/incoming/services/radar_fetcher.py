"""
Radar-Fetcher — Freelancermap + Gulp.

- Freelancermap: eingebettete application/json-Blöcke der Projektliste
- Gulp: POST /gulp2/rest/internal/projects/search (CSRF-Cookie + x-trust)

Persistenz in RadarItem / RadarSource.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import date, datetime, timedelta
from html import unescape
from http.cookiejar import CookieJar
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

log = logging.getLogger('abpe_shaduler.radar_fetcher')

FM_LIST_URL = 'https://www.freelancermap.de/projekte'
FM_UA = (
    'Mozilla/5.0 (compatible; ABpE-Radar/1.0; +https://abcona.de) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)
SOURCE_NAME = 'freelancermap'
SOURCE_URL = FM_LIST_URL

GULP_SOURCE_NAME = 'gulp'
GULP_LIST_URL = 'https://www.gulp.de/gulp2/g/projekte?order=DATE_DESC&query=&page=1'
GULP_CSRF_URL = 'https://www.gulp.de/gulp2/rest/internal/system/csrf'
GULP_SEARCH_URL = 'https://www.gulp.de/gulp2/rest/internal/projects/search'
GULP_CSRF_COOKIE = 'LzA8Jg9Oe2'
GULP_CSRF_HEADER = 'x-trust'
GULP_TYPE_PATH = {
    'TALENT_FINDER': 'talentfinder',
    'AGENCY': 'agentur',
    'DIREKT': 'direkt',
    'EXTERNAL': 'extern',
}
# Detail-REST: type.toLowerCase() der Angular-App — Talentfinder läuft über „direkt“
GULP_DETAIL_API_PATH = {
    'TALENT_FINDER': 'direkt',
    'DIREKT': 'direkt',
    'AGENCY': 'agency',
    'EXTERNAL': 'external',
    'LEGACY': 'legacy',
}

# Hays Jobsuche (Liferay HTML + JobPosting JSON-LD)
HAYS_SOURCE_NAME = 'hays'
HAYS_LIST_URL = (
    'https://www.hays.de/jobsuche/stellenangebote-jobs/'
    's/IT/1/j/Contracting/3/p/1?e=false&pt=false&ij=false&sortOrder=createdAt'
)


def _cfg(key: str, default: str) -> str:
    """DB-Einstellung mit Hardcode-Fallback (Shaduler → Einstellungen)."""
    try:
        from .settings_service import get_setting
        return get_setting(key, default) or default
    except Exception:
        return default


def fm_list_url() -> str:
    return _cfg('radar.fm.list_url', FM_LIST_URL)


def fm_base_url() -> str:
    return _cfg('radar.fm.base_url', 'https://www.freelancermap.de')


def gulp_list_url() -> str:
    return _cfg('radar.gulp.list_url', GULP_LIST_URL)


def gulp_csrf_url() -> str:
    return _cfg('radar.gulp.csrf_url', GULP_CSRF_URL)


def gulp_search_url() -> str:
    return _cfg('radar.gulp.search_url', GULP_SEARCH_URL)


def gulp_base_url() -> str:
    return _cfg('radar.gulp.base_url', 'https://www.gulp.de')


def hays_list_url() -> str:
    return _cfg('radar.hays.list_url', HAYS_LIST_URL)
HAYS_SPECIALISM = 'IT'       # /s/IT/1
HAYS_SPECIALISM_ID = '1'
HAYS_JOBTYPE = 'Contracting'  # /j/Contracting/3
HAYS_JOBTYPE_ID = '3'

ANFRAGEN_SOURCES = (SOURCE_NAME, GULP_SOURCE_NAME, HAYS_SOURCE_NAME)

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
            return urljoin(fm_base_url(), proj)
    pid = raw.get('id') or raw.get('pid')
    if pid:
        return f"{fm_base_url()}/projekte?id={pid}"
    slug = raw.get('slug') or ''
    if slug:
        return f"{fm_base_url()}/projekt/{slug}"
    return fm_list_url()


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

    age = _format_age(created)

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


def fetch_html(url: str | None = None, *, timeout: int = 25) -> str:
    if not url:
        url = fm_list_url()
    req = Request(url, headers={
        'User-Agent': FM_UA,
        'Accept': 'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8',
        'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
    })
    with urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or 'utf-8'
        return resp.read().decode(charset, errors='replace')


def _format_age(created: Optional[datetime], *, today: Optional[date] = None) -> str:
    """
    Heute: „vor X Min“ / „vor X Std“.
    Nicht heute (gestern/älter): Datum „04.08.2026“.
    """
    if not created:
        return ''
    today = today or date.today()
    try:
        created_d = created.date()
    except Exception:
        return ''
    if created_d != today:
        return created.strftime('%d.%m.%Y')
    try:
        now = datetime.now(created.tzinfo) if created.tzinfo else datetime.now()
        mins = int((now - created).total_seconds() // 60)
        if mins < 0:
            mins = 0
        if mins < 60:
            return f'vor {mins} Min'
        hours = mins // 60
        if hours < 24:
            return f'vor {hours} Std'
        return created.strftime('%d.%m.%Y')
    except Exception:
        return created.strftime('%d.%m.%Y')


def _skills_from_raw(raw: dict) -> list[str]:
    skills: list[str] = []
    for key in ('mustHaveSkills', 'niceToHaveSkills', 'skills'):
        arr = raw.get(key) or []
        if not isinstance(arr, list):
            continue
        for s in arr:
            if isinstance(s, str) and s.strip():
                skills.append(s.strip())
            elif isinstance(s, dict):
                name = s.get('name') or s.get('label') or ''
                if name:
                    skills.append(str(name).strip())
    # dedupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for s in skills:
        k = s.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
    return out


def _build_gulp_beschreibung(raw: dict) -> str:
    """Volle Detail-Beschreibung inkl. Must/Nice-Have Skills."""
    parts: list[str] = []
    desc = str(raw.get('description') or '').strip()
    if desc:
        parts.append(desc)
    must = raw.get('mustHaveSkills') or []
    if isinstance(must, list) and must:
        parts.append('Must-Have Skills')
        for s in must:
            if isinstance(s, str) and s.strip():
                parts.append(f'- {s.strip()}')
    nice = raw.get('niceToHaveSkills') or []
    if isinstance(nice, list) and nice:
        parts.append('Nice-to-Have Skills')
        for s in nice:
            if isinstance(s, str) and s.strip():
                parts.append(f'- {s.strip()}')
    return '\n'.join(parts).strip()


def _gulp_detail_api_type(typ: str) -> str:
    t = str(typ or '').strip().upper()
    return GULP_DETAIL_API_PATH.get(t, t.lower() if t else 'direkt')


def fetch_gulp_project_detail(
    project_id: str,
    typ: str = 'TALENT_FINDER',
    *,
    opener=None,
    token: str = '',
) -> Optional[dict]:
    """GET /gulp2/rest/internal/projects/{apiType}/{id}?language=DE"""
    pid = str(project_id or '').strip()
    if not pid:
        return None
    api_type = _gulp_detail_api_type(typ)
    url = f"{gulp_base_url()}/gulp2/rest/internal/projects/{api_type}/{pid}?language=DE"
    own_opener = opener is None
    jar = None
    if own_opener:
        opener, jar = _gulp_opener()
        try:
            token = _gulp_csrf_token(opener, jar)
        except Exception as exc:
            log.warning('gulp detail csrf failed: %s', exc)
            return None
    if not token:
        return None
    req = Request(url, headers={
        'User-Agent': FM_UA,
        'Accept': 'application/json',
        'Origin': gulp_base_url(),
        'Referer': _gulp_project_url({'id': pid, 'type': typ, 'url': ''}),
        GULP_CSRF_HEADER: token,
    })
    try:
        with opener.open(req, timeout=25) as resp:
            data = json.loads(resp.read().decode('utf-8', errors='replace'))
        return data if isinstance(data, dict) and data.get('id') else None
    except Exception as exc:
        log.warning('gulp detail failed %s/%s: %s', api_type, pid, exc)
        return None


def enrich_gulp_item(item: dict, *, opener=None, token: str = '') -> dict:
    """List-Hit mit Detail-API anreichern (volle Beschreibung + Skills)."""
    if not item:
        return item
    eck = item.get('eckdaten') or {}
    if eck.get('detail_enriched'):
        return item
    pid = item.get('external_id') or eck.get('project_id') or ''
    typ = eck.get('gulp_type') or eck.get('contract_type') or 'TALENT_FINDER'
    detail = fetch_gulp_project_detail(pid, typ, opener=opener, token=token)
    if not detail:
        return item
    desc = _build_gulp_beschreibung(detail)
    if desc:
        item['beschreibung'] = desc
    skills = _skills_from_raw(detail)
    if skills:
        item['skills'] = skills
    company = str(detail.get('companyName') or '').strip()
    if company:
        item['company'] = company
        eck['company'] = company
    city = str(detail.get('location') or '').strip()
    if city:
        item['city'] = city
        eck['city'] = city
    start = str(detail.get('startDate') or detail.get('externalStartDateText') or '').strip()
    if start:
        eck['beginning'] = start
    duration = detail.get('duration') or detail.get('externalWorkloadText') or ''
    if duration not in (None, ''):
        eck['duration'] = duration
        eck['duration_text'] = str(duration).strip()
    remote = detail.get('remoteWorkPossible')
    if remote is True or detail.get('isRemoteWorkPossible') is True:
        eck['remote_percent'] = 100
    elif detail.get('percentWorkload') is not None:
        try:
            eck['workload_percent'] = int(detail.get('percentWorkload'))
        except Exception:
            pass
    created = _parse_dt(detail.get('originalPublicationDate'))
    if created:
        eck['created'] = created.isoformat()
        item['raw_created'] = created.isoformat()
        item['age'] = _format_age(created)
    title = str(detail.get('title') or '').strip()
    if title:
        item['headline'] = title
    url = str(detail.get('url') or eck.get('url') or item.get('external_url') or '').strip()
    if url:
        item['external_url'] = url
        eck['url'] = url
    eck['detail_enriched'] = True
    eck['must_have_skills'] = [
        s for s in (detail.get('mustHaveSkills') or []) if isinstance(s, str)
    ]
    eck['nice_have_skills'] = [
        s for s in (detail.get('niceToHaveSkills') or []) if isinstance(s, str)
    ]
    item['eckdaten'] = eck
    # meta neu
    meta_parts = []
    if eck.get('beginning'):
        meta_parts.append(f"Start {eck['beginning']}")
    if eck.get('duration_text'):
        meta_parts.append(str(eck['duration_text']))
    if eck.get('city'):
        meta_parts.append(eck['city'])
    if eck.get('remote_percent') is not None:
        meta_parts.append('100% Remote' if eck['remote_percent'] >= 100 else f"{eck['remote_percent']}% Remote")
    if eck.get('company'):
        meta_parts.append(eck['company'])
    item['meta'] = ' · '.join(meta_parts)
    return item


def _in_recent_window(created: Optional[datetime], day: date, recent_days: int) -> tuple[bool, bool]:
    """
    Returns (include, is_older_than_window).
    is_older_than_window → DATE_DESC kann abbrechen.
    """
    if not created:
        return False, False
    recent_days = max(1, int(recent_days or 1))
    oldest = day - timedelta(days=recent_days - 1)
    d = created.date()
    if d < oldest:
        return False, True
    if d > day:
        return False, False
    return True, False


def fetch_freelancermap_projects(
    *,
    pages: int = 1,
    today_only: bool = True,
    day: Optional[date] = None,
    recent_days: int = 2,
) -> list[dict]:
    """
    Lädt 1..N Listenseiten und gibt normalisierte Projekte zurück.
    today_only: nur Einträge im Fenster [day-(recent_days-1) .. day] (Default: heute+gestern).
    """
    day = day or date.today()
    recent_days = max(1, int(recent_days or 1))
    out: list[dict] = []
    seen: set[str] = set()
    for page in range(1, max(1, int(pages)) + 1):
        base = fm_list_url(); url = base if page == 1 else f'{base}?pagenr={page}#list'
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
                include, _older = _in_recent_window(created, day, recent_days)
                if not include:
                    continue
            seen.add(pid)
            out.append(item)
    out.sort(key=lambda x: x.get('raw_created') or '', reverse=True)
    return out


def ensure_freelancermap_source():
    """RadarSource freelancermap (Anfragen) anlegen/holen."""
    return ensure_source(SOURCE_NAME, fm_list_url())


def ensure_source(name: str, url: str = '', *, ziel=None):
    """RadarSource anlegen/holen — robust gegen Duplikate (name+ziel).

    Live-Fehler: get_or_create(name=…) traf Anfragen+Berater (gleicher Name)
    → MultipleObjectsReturned. Lookup immer name+ziel; bei Duplikaten
    kanonische Quelle behalten, Rest deaktivieren.
    """
    from django.db.models import Count

    from apps.abpe_shaduler.models import RadarSource

    ziel = ziel or RadarSource.Ziel.ANFRAGEN
    defaults = {
        'typ': RadarSource.Typ.HTML_PUBLIC,
        'url': url or '',
        'intervall_min': 5,
        'aktiv': True,
    }

    qs = RadarSource.objects.filter(name=name, ziel=ziel)
    src = (
        qs.annotate(_item_n=Count('items', distinct=True))
        .order_by('-aktiv', '-_item_n', 'created_at')
        .first()
    )
    if src is None:
        src = RadarSource.objects.create(name=name, ziel=ziel, **defaults)
    else:
        # Weitere Duplikate (gleicher name+ziel) stilllegen — Poll nicht blockieren
        dup_ids = list(qs.exclude(pk=src.pk).values_list('pk', flat=True))
        if dup_ids:
            RadarSource.objects.filter(pk__in=dup_ids).update(
                aktiv=False,
                letzter_status='duplikat-deaktiviert',
            )
        updates = []
        if url and src.url != url:
            src.url = url
            updates.append('url')
        if not src.aktiv:
            src.aktiv = True
            updates.append('aktiv')
        if updates:
            src.save(update_fields=updates)
    return src


def ensure_gulp_source():
    return ensure_source(GULP_SOURCE_NAME, gulp_list_url())


def _gulp_opener():
    jar = CookieJar()
    return build_opener(HTTPCookieProcessor(jar)), jar


def _gulp_csrf_token(opener, jar) -> str:
    req = Request(gulp_csrf_url(), headers={
        'User-Agent': FM_UA,
        'Accept': 'application/json, text/plain, */*',
        'Referer': gulp_list_url(),
    })
    opener.open(req, timeout=20).read()
    for c in jar:
        if c.name == GULP_CSRF_COOKIE and c.value:
            return c.value
    raise RuntimeError('Gulp CSRF-Cookie fehlt')


def _gulp_project_url(raw: dict) -> str:
    url = str(raw.get('url') or '').strip()
    if url.startswith('http'):
        return url
    pid = str(raw.get('id') or '').strip()
    typ = str(raw.get('type') or '').strip().upper()
    path = GULP_TYPE_PATH.get(typ, typ.lower() if typ else 'projekte')
    if pid and path != 'external':
        return f"{gulp_base_url()}/gulp2/g/projekte/{path}/{pid}"
    return url or gulp_list_url()


def normalize_gulp_project(raw: dict, *, source: str = GULP_SOURCE_NAME) -> dict:
    """Gulp search-hit → UI-/DB-Dict (gleiches Schema wie Freelancermap)."""
    pid = str(raw.get('id') or raw.get('idInIndex') or '').strip()
    title = str(raw.get('title') or '').strip()
    desc = str(raw.get('description') or '').strip()
    company = str(raw.get('companyName') or '').strip()
    city = str(raw.get('location') or '').strip()
    created = _parse_dt(raw.get('originalPublicationDate'))
    remote = 100 if raw.get('isRemoteWorkPossible') else None
    if city and re.search(r'\bremote\b', city, re.I):
        remote = 100
    start = str(raw.get('startDate') or '').strip()
    duration = raw.get('duration')
    duration_text = str(duration).strip() if duration not in (None, '') else ''
    skills = []
    for s in (raw.get('skills') or []):
        if isinstance(s, str) and s.strip():
            skills.append(s.strip())
        elif isinstance(s, dict):
            name = s.get('name') or s.get('label') or ''
            if name:
                skills.append(str(name).strip())
    url = _gulp_project_url(raw)
    typ = str(raw.get('type') or '').strip()
    dedup = hashlib.sha256(f'{source}:{pid or url}:{title}'.encode('utf-8')).hexdigest()

    meta_parts = []
    if start:
        meta_parts.append(f'Start {start}')
    if duration_text:
        meta_parts.append(duration_text)
    if city:
        meta_parts.append(city)
    if remote is not None:
        meta_parts.append('100% Remote' if remote >= 100 else f'{remote}% Remote')
    if company:
        meta_parts.append(company)
    if typ:
        meta_parts.append(typ)

    eckdaten = {
        'project_id': pid,
        'slug': '',
        'company': company,
        'contact': '',
        'contact_first': '',
        'contact_last': '',
        'city': city,
        'country': '',
        'remote_percent': remote,
        'beginning': start,
        'duration': duration,
        'duration_text': duration_text,
        'industry': '',
        'contract_type': typ,
        'created': created.isoformat() if created else str(raw.get('originalPublicationDate') or ''),
        'source': source,
        'url': url,
        'gulp_type': typ,
    }

    age = _format_age(created)

    return {
        'id': f'gulp-{pid}' if pid else dedup[:16],
        'external_id': pid,
        'dedup_hash': dedup,
        'headline': title or f'Gulp {pid}',
        'beschreibung': desc,
        'beschreibung_html': '',
        'skills': skills,
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
        'contact': '',
        'city': city,
        'raw_created': created.isoformat() if created else None,
    }


def fetch_gulp_projects(
    *,
    pages: int = 3,
    page_size: int = 20,
    today_only: bool = True,
    day: Optional[date] = None,
    recent_days: int = 2,
    enrich_details: bool = True,
) -> list[dict]:
    """
    Lädt Gulp-Projekte via REST search (DATE_DESC).
    today_only: Fenster [day-(recent_days-1) .. day] (Default: heute+gestern).
    enrich_details: Detail-API für volle Beschreibung + Skills nachladen.

    Hinweis: Gulp-API sortiert bei limit>=50 unzuverlässig (neueste fehlen) —
    daher page_size default 20.
    """
    day = day or date.today()
    recent_days = max(1, int(recent_days or 1))
    opener, jar = _gulp_opener()
    try:
        token = _gulp_csrf_token(opener, jar)
    except Exception as exc:
        log.warning('gulp csrf failed: %s', exc)
        return []

    out: list[dict] = []
    seen: set[str] = set()
    stop_old = False
    limit = max(10, min(30, int(page_size)))  # >30: API liefert oft ohne neueste
    for page in range(1, max(1, int(pages)) + 1):
        if stop_old:
            break
        body = json.dumps({
            'query': '',
            'page': page,
            'limit': limit,
            'order': 'DATE_DESC',
            'language': 'DE',
        }).encode('utf-8')
        req = Request(gulp_search_url(), data=body, method='POST', headers={
            'User-Agent': FM_UA,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Origin': gulp_base_url(),
            'Referer': gulp_list_url(),
            GULP_CSRF_HEADER: token,
        })
        try:
            with opener.open(req, timeout=30) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
            data = json.loads(raw)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            log.warning('gulp search failed page=%s: %s', page, exc)
            break
        projects = data.get('projects') if isinstance(data, dict) else None
        if not isinstance(projects, list) or not projects:
            log.info('gulp page=%s: keine Projekte', page)
            break
        page_had_match = False
        for raw_p in projects:
            if not isinstance(raw_p, dict):
                continue
            item = normalize_gulp_project(raw_p)
            pid = item.get('external_id') or item['id']
            if pid in seen:
                continue
            created = _parse_dt(item.get('raw_created') or (item.get('eckdaten') or {}).get('created'))
            if today_only:
                include, older = _in_recent_window(created, day, recent_days)
                if older:
                    stop_old = True
                    continue
                if not include:
                    continue
                page_had_match = True
            seen.add(pid)
            out.append(item)
        if today_only and stop_old and not page_had_match:
            break

    if enrich_details and out:
        for i, item in enumerate(out):
            try:
                out[i] = enrich_gulp_item(item, opener=opener, token=token)
            except Exception as exc:
                log.warning('gulp enrich failed %s: %s', item.get('external_id'), exc)

    out.sort(key=lambda x: x.get('raw_created') or '', reverse=True)
    return out


def ensure_hays_source():
    return ensure_source(HAYS_SOURCE_NAME, hays_list_url())


def _hays_list_url(page: int = 1, *, query: str = '') -> str:
    page = max(1, int(page or 1))
    q = (query or '').strip()
    base = (
        f'https://www.hays.de/jobsuche/stellenangebote-jobs/'
        f's/{HAYS_SPECIALISM}/{HAYS_SPECIALISM_ID}/'
        f'j/{HAYS_JOBTYPE}/{HAYS_JOBTYPE_ID}/p/{page}'
    )
    params = 'e=false&pt=false&ij=false&sortOrder=createdAt'
    if q:
        from urllib.parse import quote
        params = f'q={quote(q)}&' + params
    return f'{base}?{params}'


def _hays_ref_from_url(url: str) -> str:
    """…-888822/1 → 888822/1"""
    m = re.search(r'-(\d+)/(\d+)/?$', (url or '').rstrip('/'))
    if m:
        return f'{m.group(1)}/{m.group(2)}'
    m = re.search(r'-(\d+)(?:/|$)', url or '')
    return m.group(1) if m else ''


def parse_hays_list_html(html: str) -> list[dict]:
    """SSR-Karten aus Hays-Suchseite."""
    parts = re.split(r'(?=<div class="search__result border-radius-10")', html or '')
    cards = [p for p in parts if p.startswith('<div class="search__result border-radius-10"')]
    out: list[dict] = []
    for c in cards:
        jid_m = re.search(r'data-job-id="\s*([^"]+)"', c)
        jid = (jid_m.group(1).strip() if jid_m else '')
        title_m = re.search(r'<h4 class="search__result__header__title">(.*?)</h4>', c, re.S)
        title = ''
        if title_m:
            title = _WS_RE.sub(' ', unescape(_TAG_RE.sub(' ', title_m.group(1)))).strip()
        link_m = re.search(
            r'href="(https://www\.hays\.de/jobsuche/stellenangebote-jobs-detail[^"]+)"', c,
        )
        url = link_m.group(1) if link_m else ''
        teaser_m = re.search(r'class="search__result__teaser"[^>]*>(.*?)</div>', c, re.S)
        teaser = ''
        if teaser_m:
            teaser = _WS_RE.sub(' ', unescape(_TAG_RE.sub(' ', teaser_m.group(1)))).strip()
        city = ''
        typ = ''
        loc_m = re.search(
            r'search__result__job__attribute__location[^>]*>.*?>\s*([^<]+)', c, re.S,
        )
        if loc_m:
            city = _WS_RE.sub(' ', unescape(loc_m.group(1))).strip()
        typ_m = re.search(
            r'search__result__job__attribute__type[^>]*>.*?>\s*([^<]+)', c, re.S,
        )
        if typ_m:
            typ = _WS_RE.sub(' ', unescape(typ_m.group(1))).strip()
        prosp_m = re.search(r'search__result__prospectnumber[^>]*>\s*([^<]+)', c)
        prosp = ''
        if prosp_m:
            prosp = _WS_RE.sub(' ', unescape(prosp_m.group(1))).strip()
            prosp = re.sub(r'(?i)^referenznummer:\s*', '', prosp).strip()
        ref = prosp or _hays_ref_from_url(url)
        if not title and not url:
            continue
        out.append({
            'id': jid or ref,
            'title': title,
            'url': url,
            'teaser': teaser,
            'city': city,
            'contract_type': typ,
            'reference': ref,
        })
    return out


def fetch_hays_job_detail(url: str) -> Optional[dict]:
    """Detailseite → JobPosting JSON-LD (+ Sektionen)."""
    if not url:
        return None
    try:
        req = Request(url, headers={
            'User-Agent': FM_UA,
            'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
        })
        html = urlopen(req, timeout=25).read().decode('utf-8', 'replace')
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        log.warning('hays detail fetch failed: %s', exc)
        return None
    m = re.search(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.S | re.I,
    )
    ld: dict = {}
    if m:
        try:
            ld = json.loads(m.group(1))
        except json.JSONDecodeError:
            ld = {}
    sections: dict[str, str] = {}
    for t, b in re.findall(
        r'h-job-detail__listing-title[^>]*>(.*?)</[^>]+>\s*'
        r'<div[^>]*h-job-detail__listing-body[^>]*>(.*?)</div>',
        html, re.S,
    ):
        key = _WS_RE.sub(' ', unescape(_TAG_RE.sub(' ', t))).strip().lower()
        body = _WS_RE.sub(' ', unescape(_TAG_RE.sub(' ', b))).strip()
        if key and body:
            sections[key] = body
    return {'ld': ld, 'sections': sections, 'url': url}


def normalize_hays_project(
    raw: dict,
    *,
    detail: Optional[dict] = None,
    source: str = HAYS_SOURCE_NAME,
) -> dict:
    """Hays-Karte (+ optional Detail) → Radar-Dict."""
    ld = (detail or {}).get('ld') or {}
    sections = (detail or {}).get('sections') or {}
    pid = str(raw.get('reference') or raw.get('id') or '').strip()
    if not pid and isinstance(ld.get('identifier'), dict):
        pid = str(ld['identifier'].get('value') or '').strip()
    title = str(ld.get('title') or raw.get('title') or '').strip()
    url = str(ld.get('url') or raw.get('url') or '').strip()
    if url.startswith('http://'):
        url = 'https://' + url[len('http://'):]
    city = str(raw.get('city') or '').strip()
    loc = ld.get('jobLocation') or {}
    addr = loc.get('address') if isinstance(loc, dict) else {}
    if isinstance(addr, dict) and addr.get('addressLocality'):
        city = str(addr.get('addressLocality') or city).strip()
    created = _parse_dt(ld.get('datePosted'))
    desc = str(ld.get('description') or '').strip()
    if not desc:
        parts = []
        for k in ('aufgaben', 'profil', 'benefits'):
            if sections.get(k):
                parts.append(sections[k])
        desc = '\n\n'.join(parts) if parts else str(raw.get('teaser') or '')
    # Skills: nur bekannte Tech-/Methoden-Tokens aus Profil
    skills: list[str] = []
    profile = sections.get('profil') or str(ld.get('experienceRequirements') or '')
    skill_re = re.compile(
        r'\b(?:'
        r'SAP(?:\s*[A-Z0-9/]+)?|SAFe|ABAP|Fiori|S/?4HANA|HANA|'
        r'Java(?:Script)?|TypeScript|Python|Go|Rust|C\+\+|C#|\.NET|PHP|'
        r'React|Angular|Vue\.?js|Node\.?js|Spring(?:\s*Boot)?|'
        r'AWS|Azure|GCP|Kubernetes|K8s|Docker|Terraform|Ansible|'
        r'Scrum|Kanban|DevOps|CI/?CD|Kafka|Spark|Databricks|Snowflake|'
        r'Power\s*BI|Tableau|Salesforce|ServiceNow|Jira|Confluence|'
        r'Linux|Windows|Active\s*Directory|M365|Microsoft\s*365|'
        r'IBP|PP/?DS|BW/?4|BTP|CPI|PI/?PO'
        r')\b',
        re.I,
    )
    for m in skill_re.finditer(profile):
        t = re.sub(r'\s+', ' ', m.group(0)).strip()
        # canonical casing for common ones
        key = t.lower()
        if key and key not in {s.lower() for s in skills} and len(skills) < 16:
            skills.append(t)
    industry = str(ld.get('industry') or '').strip()
    contract = str(raw.get('contract_type') or '').strip()
    emp = ld.get('employmentType') or []
    if isinstance(emp, list) and emp:
        contract = contract or ', '.join(str(x) for x in emp)
    company = 'Hays'
    if isinstance(ld.get('hiringOrganization'), dict):
        company = str(ld['hiringOrganization'].get('name') or company)
    dedup = hashlib.sha256(f'{source}:{pid or url}:{title}'.encode('utf-8')).hexdigest()

    meta_parts = []
    if city:
        meta_parts.append(city)
    if contract:
        meta_parts.append(contract)
    if industry:
        meta_parts.append(industry)
    if pid:
        meta_parts.append(f'Ref {pid}')

    eckdaten = {
        'project_id': pid,
        'slug': '',
        'company': company,
        'contact': '',
        'contact_first': '',
        'contact_last': '',
        'city': city,
        'country': (addr.get('addressCountry') if isinstance(addr, dict) else '') or 'DE',
        'remote_percent': 100 if re.search(r'\bremote\b', f'{title} {city} {desc}', re.I) else None,
        'beginning': '',
        'duration': '',
        'duration_text': '',
        'industry': industry,
        'contract_type': contract,
        'created': created.isoformat() if created else str(ld.get('datePosted') or ''),
        'source': source,
        'url': url,
        'hays_job_id': str(raw.get('id') or ''),
        'detail_enriched': bool(ld),
    }
    age = _format_age(created)
    return {
        'id': f'hays-{pid}' if pid else dedup[:16],
        'external_id': pid,
        'dedup_hash': dedup,
        'headline': title or f'Hays {pid}',
        'beschreibung': desc,
        'beschreibung_html': '',
        'skills': skills,
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
        'contact': '',
        'city': city,
        'raw_created': created.isoformat() if created else None,
    }


def fetch_hays_projects(
    *,
    pages: int = 2,
    today_only: bool = True,
    recent_days: int = 2,
    query: str = '',
    enrich_details: bool = True,
) -> list[dict]:
    """
    Hays IT/Contracting, Sortierung Neueste (createdAt).
    Detail (JSON-LD) liefert datePosted — bei Datumsfenster Early-Stop.
    """
    pages = max(1, min(8, int(pages or 2)))
    recent_days = max(1, min(30, int(recent_days or 2)))
    cutoff_date = date.today() - timedelta(days=recent_days - 1)
    out: list[dict] = []
    seen: set[str] = set()

    for page in range(1, pages + 1):
        url = _hays_list_url(page, query=query)
        try:
            req = Request(url, headers={
                'User-Agent': FM_UA,
                'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'de-DE,de;q=0.9',
            })
            html = urlopen(req, timeout=30).read().decode('utf-8', 'replace')
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            log.warning('hays list page %s failed: %s', page, exc)
            break
        cards = parse_hays_list_html(html)
        if not cards:
            break
        page_had_match = False
        stop_old = False
        for card in cards:
            key = card.get('id') or card.get('url') or card.get('title')
            if not key or key in seen:
                continue
            seen.add(key)
            detail = None
            if enrich_details and card.get('url'):
                detail = fetch_hays_job_detail(card['url'])
            item = normalize_hays_project(card, detail=detail)
            created = _parse_dt((item.get('eckdaten') or {}).get('created')) or _parse_dt(
                item.get('raw_created')
            )
            if today_only and created:
                if created.date() < cutoff_date:
                    stop_old = True
                    continue
                page_had_match = True
            elif today_only and not created:
                # ohne Datum nur aufnehmen wenn Fenster großzügig / erste Seiten
                page_had_match = True
            out.append(item)
        if today_only and stop_old and not page_had_match:
            break
        if today_only and stop_old:
            break

    out.sort(key=lambda x: x.get('raw_created') or '', reverse=True)
    return out


def persist_items(
    items: list[dict],
    *,
    archive_older: bool = True,
    source_name: str = SOURCE_NAME,
    source_url: str | None = None,
) -> dict:
    """
    Upsert RadarItem. archive_older: ältere „neu“-Items derselben Quelle → verworfen
    (Tages-Archiv-Idee: nur heutige bleiben aktiv sichtbar).

    eingegangen_am = Projekt-Publikationsdatum (nicht Importzeit!) — sonst sortiert
    „neueste zuerst“ nach Batch-Insert verkehrt (letzte Zeile = späteste auto_now_add).
    """
    from django.utils import timezone
    from apps.abpe_shaduler.models import RadarItem

    src = ensure_source(source_name, source_url or '')
    created = 0
    updated = 0
    hashes = []
    touched = []
    for it in items:
        dedup = it['dedup_hash']
        hashes.append(dedup)
        pub_dt = _parse_dt(
            it.get('raw_created')
            or it.get('eingegangen_am')
            or (it.get('eckdaten') or {}).get('created')
        )
        if pub_dt is not None and timezone.is_naive(pub_dt):
            try:
                pub_dt = timezone.make_aware(pub_dt, timezone.get_current_timezone())
            except Exception:
                pub_dt = timezone.make_aware(pub_dt, timezone.utc)
        fields = {
            'external_url': it.get('external_url') or '',
            'headline': (it.get('headline') or '')[:250],
            'beschreibung': it.get('beschreibung') or '',
            'skills': it.get('skills') or [],
            'eckdaten': it.get('eckdaten') or {},
        }
        obj = RadarItem.objects.filter(quelle=src, dedup_hash=dedup).first()
        if obj:
            for k, v in fields.items():
                setattr(obj, k, v)
            if obj.status == RadarItem.Status.VERWORFEN:
                # wieder sichtbar wenn erneut am heutigen Tag gefunden
                obj.status = RadarItem.Status.NEU
            # Publikationsdatum nachziehen (älterer Import-Zeitstempel korrigieren)
            if pub_dt and (not obj.eingegangen_am or abs(
                (obj.eingegangen_am - pub_dt).total_seconds()
            ) > 60):
                obj.eingegangen_am = pub_dt
            obj.save()
            updated += 1
        else:
            obj = RadarItem.objects.create(
                quelle=src,
                dedup_hash=dedup,
                status=RadarItem.Status.NEU,
                **fields,
            )
            # auto_now_add setzt Importzeit — Publikationsdatum per UPDATE setzen
            if pub_dt:
                RadarItem.objects.filter(pk=obj.pk).update(eingegangen_am=pub_dt)
                obj.eingegangen_am = pub_dt
            created += 1
        touched.append(obj)

    archived = 0
    archived_ids: list = []
    if archive_older:
        # Alles andere „neu“ von dieser Quelle, das heute nicht mehr kam → archivieren
        qs = RadarItem.objects.filter(quelle=src, status=RadarItem.Status.NEU)
        if hashes:
            qs = qs.exclude(dedup_hash__in=hashes)
        # nur Items, die älter als heute Mitternacht sind
        start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        qs = qs.filter(eingegangen_am__lt=start)
        archived_ids = list(qs.values_list('pk', flat=True)[:2000])
        archived = qs.update(status=RadarItem.Status.VERWORFEN)

    src.letzter_lauf = timezone.now()
    src.letzter_status = f'ok +{created}/~{updated}/arch {archived}'
    src.save(update_fields=['letzter_lauf', 'letzter_status'])

    indexed = 0
    try:
        from . import radar_index
        info = radar_index.index_items(touched, refresh=True)
        indexed = int(info.get('indexed') or 0)
        for pk in archived_ids:
            try:
                radar_index.delete_item(str(pk))
            except Exception:
                pass
    except Exception as exc:
        log.warning('radar index after persist failed: %s', exc)

    grouped = {}
    try:
        from . import radar_grouper
        grouped = radar_grouper.regroup_touched(touched)
    except Exception as exc:
        log.warning('radar group after persist failed: %s', exc)
        grouped = {'ok': False, 'error': str(exc)}

    return {
        'ok': True,
        'source': source_name,
        'created': created,
        'updated': updated,
        'archived': archived,
        'fetched': len(items),
        'indexed': indexed,
        'grouped': grouped,
    }


def serialize_db_item(obj) -> dict:
    eck = obj.eckdaten or {}
    source = eck.get('source') or (obj.quelle.name if obj.quelle_id else SOURCE_NAME)
    created = _parse_dt(eck.get('created')) or (
        obj.eingegangen_am.replace(tzinfo=None) if getattr(obj, 'eingegangen_am', None) else None
    )
    grp_n = 1
    if getattr(obj, 'gruppe_id', None) and getattr(obj, 'gruppe', None):
        try:
            grp_n = max(1, int(obj.gruppe.anbieter_anzahl or 1))
        except Exception:
            grp_n = 1
    raw_created = None
    if created:
        try:
            raw_created = created.isoformat()
        except Exception:
            raw_created = str(created)
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
        'age': _format_age(created),
        'sources': [source],
        'score': obj.quick_score,
        'grp': grp_n,
        'gruppe_id': str(obj.gruppe_id) if getattr(obj, 'gruppe_id', None) else None,
        'top': obj.top_berater or [],
        'status': obj.status,
        'external_url': obj.external_url,
        'raw_created': raw_created,
        'eingegangen_am': obj.eingegangen_am.isoformat() if obj.eingegangen_am else None,
        'company': eck.get('company') or '',
        'contact': eck.get('contact') or '',
        'city': eck.get('city') or '',
    }


def _sort_key_published(r: dict) -> datetime:
    """Sortierschlüssel: Publikationsdatum (nicht Importzeit)."""
    dt = _parse_dt(
        r.get('raw_created')
        or (r.get('eckdaten') or {}).get('created')
        or r.get('eingegangen_am')
    )
    if dt is None:
        return datetime.min
    if dt.tzinfo is not None:
        try:
            return dt.replace(tzinfo=None)
        except Exception:
            return datetime.min
    return dt


def _apply_date_sort(results: list[dict], sort: str) -> list[dict]:
    asc = (sort or '').lower() in ('date_asc', 'asc', 'oldest')
    return sorted(results, key=_sort_key_published, reverse=not asc)


def list_anfragen(
    *,
    use_live_fetch: bool = True,
    today_only: bool = True,
    persist: bool = True,
    pages: int = 1,
    status: str = 'neu',
    recent_days: int = 2,
    q: str = '',
    source: str = '',
    sort: str = 'date_desc',
    limit: int = 300,
) -> dict:
    """
    Primärer Einstieg für API.
    1) Optional live von Freelancermap + Gulp + Hays holen + persistieren (+ ES-Index)
    2) Suche bevorzugt über ES (q / Zeitraum / Quelle / Sort)
    3) Fallback: DB
    """
    # days=0 → alle; sonst 1..365 (UI: 1/2/7/30)
    try:
        recent_days = int(recent_days)
    except (TypeError, ValueError):
        recent_days = 2
    if recent_days < 0:
        recent_days = 0
    recent_days = min(365, recent_days)
    fetch_days = recent_days if recent_days > 0 else 2
    fetch_days = max(1, min(30, fetch_days))
    q = (q or '').strip()
    source = (source or '').strip().lower()
    sort = (sort or 'date_desc').strip().lower()
    limit = max(1, min(500, int(limit or 300)))

    fetched: list[dict] = []
    persist_info: dict = {}
    if use_live_fetch:
        fm_items: list[dict] = []
        gulp_items: list[dict] = []
        hays_items: list[dict] = []
        try:
            fm_items = fetch_freelancermap_projects(
                pages=pages, today_only=today_only, recent_days=fetch_days,
            )
            if persist:
                try:
                    persist_info['freelancermap'] = persist_items(
                        fm_items, archive_older=today_only and recent_days > 0 and recent_days <= 2,
                        source_name=SOURCE_NAME, source_url=fm_list_url(),
                    )
                except Exception as exc:
                    log.warning('persist FM failed: %s', exc)
                    persist_info['freelancermap'] = {'ok': False, 'error': str(exc)}
        except Exception as exc:
            log.warning('FM live fetch failed: %s', exc)
            persist_info['freelancermap'] = {'ok': False, 'error': str(exc)}

        try:
            gulp_pages = max(3, min(6, int(pages) + 2))
            gulp_items = fetch_gulp_projects(
                pages=gulp_pages, page_size=20,
                today_only=today_only, recent_days=fetch_days,
            )
            if persist:
                try:
                    persist_info['gulp'] = persist_items(
                        gulp_items, archive_older=today_only and recent_days > 0 and recent_days <= 2,
                        source_name=GULP_SOURCE_NAME, source_url=gulp_list_url(),
                    )
                except Exception as exc:
                    log.warning('persist gulp failed: %s', exc)
                    persist_info['gulp'] = {'ok': False, 'error': str(exc)}
        except Exception as exc:
            log.warning('gulp live fetch failed: %s', exc)
            persist_info['gulp'] = {'ok': False, 'error': str(exc)}

        try:
            hays_pages = max(2, min(5, int(pages) + 1))
            hays_items = fetch_hays_projects(
                pages=hays_pages,
                today_only=today_only,
                recent_days=fetch_days,
                # Liste schnell — volle Beschreibung beim Öffnen (get_item)
                enrich_details=False,
            )
            if persist:
                try:
                    persist_info['hays'] = persist_items(
                        hays_items, archive_older=today_only and recent_days > 0 and recent_days <= 2,
                        source_name=HAYS_SOURCE_NAME, source_url=hays_list_url(),
                    )
                except Exception as exc:
                    log.warning('persist hays failed: %s', exc)
                    persist_info['hays'] = {'ok': False, 'error': str(exc)}
        except Exception as exc:
            log.warning('hays live fetch failed: %s', exc)
            persist_info['hays'] = {'ok': False, 'error': str(exc)}

        fetched = fm_items + gulp_items + hays_items
        persist_info['ok'] = True
        persist_info['fetched'] = len(fetched)
        persist_info['recent_days'] = recent_days

    results: list[dict] = []
    list_source = 'db'
    by_src: dict = {}
    es_total = None

    # ── ES-Suche ────────────────────────────────────────────────────────────
    try:
        from . import radar_index
        es_pack = radar_index.search(
            q=q,
            days=recent_days if recent_days > 0 else None,
            source=source,
            status=status,
            sort=sort,
            limit=limit,
        )
    except Exception as exc:
        log.warning('radar ES search error: %s', exc)
        es_pack = None

    if es_pack and es_pack.get('ids') is not None:
        list_source = 'elasticsearch'
        by_src = es_pack.get('by_source') or {}
        es_total = es_pack.get('total')
        ids = es_pack.get('ids') or []
        if ids:
            try:
                from apps.abpe_shaduler.models import RadarItem
                import uuid as _uuid
                uuids = []
                for i in ids:
                    try:
                        uuids.append(_uuid.UUID(str(i)))
                    except Exception:
                        continue
                objs = {
                    str(o.pk): o
                    for o in RadarItem.objects.filter(pk__in=uuids).select_related('quelle', 'gruppe')
                }
                results = [serialize_db_item(objs[str(u)]) for u in uuids if str(u) in objs]
            except Exception as exc:
                log.warning('hydrate ES radar ids failed: %s', exc)
                results = []
        else:
            results = []
        # Leerer Index, 0 Treffer oder Hydrate-Fail → DB (sonst wirkt Radar „tot“)
        if not results:
            list_source = 'db'
            by_src = {}
            es_total = None

    # ── DB-Fallback ─────────────────────────────────────────────────────────
    if list_source != 'elasticsearch':
        try:
            from apps.abpe_shaduler.models import RadarItem, RadarSource
            from datetime import timedelta
            from django.utils import timezone as dj_tz
            src_qs = RadarSource.objects.filter(name__in=ANFRAGEN_SOURCES)
            if source:
                src_qs = src_qs.filter(name=source)
            src_ids = list(src_qs.values_list('pk', flat=True))
            qs = RadarItem.objects.all()
            if src_ids:
                qs = qs.filter(quelle_id__in=src_ids)
            elif source:
                qs = qs.none()
            if status:
                qs = qs.filter(status=status)
            if recent_days > 0:
                since = dj_tz.now() - timedelta(days=recent_days)
                qs = qs.filter(eingegangen_am__gte=since)
            if q:
                from django.db.models import Q
                qs = qs.filter(
                    Q(headline__icontains=q)
                    | Q(beschreibung__icontains=q)
                    | Q(eckdaten__company__icontains=q)
                    | Q(eckdaten__city__icontains=q)
                )
            order = 'eingegangen_am' if sort in ('date_asc', 'asc', 'oldest') else '-eingegangen_am'
            qs = qs.select_related('quelle', 'gruppe').order_by(order)[:limit]
            results = [serialize_db_item(o) for o in qs]
            list_source = 'db'
        except Exception as exc:
            log.warning('DB list failed, fallback live: %s', exc)
            results = fetched
            list_source = 'live'

    if not results and fetched and not q and not source and list_source != 'elasticsearch':
        results = fetched
        list_source = 'live'

    # Client-side refine nur für DB/Live (ES liefert schon gefiltert/sortiert)
    if list_source != 'elasticsearch':
        if source:
            results = [
                r for r in results
                if ((r.get('sources') or [''])[0] or '').lower() == source
            ]
        results = _apply_date_sort(results, sort)

    # Cross-Source-Dedup: fehlende Gruppen nachziehen, dann kollabieren
    raw_count = len(results)
    try:
        from . import radar_grouper
        need = [r for r in results if not r.get('gruppe_id')]
        if need and list_source in ('elasticsearch', 'db'):
            try:
                from apps.abpe_shaduler.models import RadarItem
                import uuid as _uuid
                pks = []
                for r in need[:200]:
                    try:
                        pks.append(_uuid.UUID(str(r['id'])))
                    except Exception:
                        pass
                if pks:
                    touched = list(
                        RadarItem.objects.filter(pk__in=pks).select_related('quelle', 'gruppe')
                    )
                    radar_grouper.regroup_touched(touched)
                    # gruppe_id in Results aktualisieren
                    refreshed = {
                        str(o.pk): str(o.gruppe_id) if o.gruppe_id else None
                        for o in RadarItem.objects.filter(pk__in=pks).only('id', 'gruppe_id')
                    }
                    for r in results:
                        if not r.get('gruppe_id') and r.get('id') in refreshed:
                            r['gruppe_id'] = refreshed[r['id']]
            except Exception as exc:
                log.warning('radar lazy regroup failed: %s', exc)
        results = radar_grouper.collapse_serialized(results, source_filter=source)
        # Collapse kann Reihenfolge zerstören (Singles ans Ende) — neu sortieren
        results = _apply_date_sort(results, sort)
    except Exception as exc:
        log.warning('radar collapse failed: %s', exc)

    if not by_src:
        for it in results:
            for s in (it.get('sources') or ['?']):
                s = s or '?'
                by_src[s] = by_src.get(s, 0) + 1

    return {
        'ok': True,
        'demo': False,
        'source': '+'.join(ANFRAGEN_SOURCES),
        'list_source': list_source,
        'recent_days': recent_days,
        'q': q,
        'filter_source': source,
        'sort': sort,
        'by_source': by_src,
        'results': results,
        'count': len(results),
        'total': len(results),
        'raw_count': raw_count,
        'es_total': es_total,
        'fetched': len(fetched),
        'persist': persist_info,
        'dedup': True,
    }


def get_item(item_id: str) -> Optional[dict]:
    """Detail per UUID oder fm-/gulp-/hays-<projectId>."""
    # Live/DB UUID
    try:
        from apps.abpe_shaduler.models import RadarItem
        import uuid as _uuid
        obj = None
        try:
            uid = _uuid.UUID(str(item_id))
            obj = RadarItem.objects.filter(pk=uid).select_related('quelle').first()
        except Exception:
            obj = None
        if not obj:
            pid = str(item_id)
            for prefix in ('fm-', 'gulp-', 'hays-'):
                if pid.startswith(prefix):
                    pid = pid[len(prefix):]
                    break
            obj = RadarItem.objects.filter(eckdaten__project_id=pid).select_related('quelle').first()
        if obj:
            item = serialize_db_item(obj)
            src = ((item.get('sources') or [''])[0] or '').lower()
            eck = item.get('eckdaten') or {}
            needs_gulp = (
                src == 'gulp'
                and (
                    not eck.get('detail_enriched')
                    or len(item.get('beschreibung') or '') < 400
                    or (item.get('beschreibung') or '').rstrip().endswith('...')
                )
            )
            needs_hays = (
                src == 'hays'
                and (
                    not eck.get('detail_enriched')
                    or len(item.get('beschreibung') or '') < 200
                )
            )
            if needs_gulp:
                item = enrich_gulp_item(item)
                try:
                    obj.beschreibung = item.get('beschreibung') or obj.beschreibung
                    obj.skills = item.get('skills') or obj.skills
                    obj.headline = (item.get('headline') or obj.headline or '')[:250]
                    obj.external_url = item.get('external_url') or obj.external_url
                    obj.eckdaten = item.get('eckdaten') or obj.eckdaten
                    obj.save(update_fields=[
                        'beschreibung', 'skills', 'headline', 'external_url', 'eckdaten', 'updated_at',
                    ])
                except Exception as exc:
                    log.debug('persist enriched gulp detail: %s', exc)
            elif needs_hays and (item.get('external_url') or eck.get('url')):
                try:
                    detail = fetch_hays_job_detail(item.get('external_url') or eck.get('url'))
                    if detail and detail.get('ld'):
                        raw = {
                            'id': eck.get('hays_job_id') or '',
                            'reference': eck.get('project_id') or '',
                            'title': item.get('headline') or '',
                            'url': item.get('external_url') or eck.get('url') or '',
                            'teaser': '',
                            'city': item.get('city') or eck.get('city') or '',
                            'contract_type': eck.get('contract_type') or '',
                        }
                        item = normalize_hays_project(raw, detail=detail)
                        obj.beschreibung = item.get('beschreibung') or obj.beschreibung
                        obj.skills = item.get('skills') or obj.skills
                        obj.headline = (item.get('headline') or obj.headline or '')[:250]
                        obj.external_url = item.get('external_url') or obj.external_url
                        obj.eckdaten = item.get('eckdaten') or obj.eckdaten
                        obj.save(update_fields=[
                            'beschreibung', 'skills', 'headline', 'external_url', 'eckdaten', 'updated_at',
                        ])
                except Exception as exc:
                    log.debug('persist enriched hays detail: %s', exc)
            return item
    except Exception as exc:
        log.debug('get_item db: %s', exc)

    # Live-Nachladen: Listenseite + Filter
    try:
        items = fetch_freelancermap_projects(pages=2, today_only=False)
        items += fetch_gulp_projects(pages=2, today_only=False, enrich_details=True)
        items += fetch_hays_projects(pages=1, today_only=False, enrich_details=True)
        pid = str(item_id)
        for prefix in ('fm-', 'gulp-', 'hays-'):
            if pid.startswith(prefix):
                pid = pid[len(prefix):]
                break
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
        pid = str(item_id)
        for prefix in ('fm-', 'gulp-', 'hays-'):
            if pid.startswith(prefix):
                pid = pid[len(prefix):]
                break
        obj = RadarItem.objects.filter(eckdaten__project_id=pid).first()
    if not obj:
        return {'ok': False, 'error': 'nicht gefunden'}
    if status not in dict(RadarItem.Status.choices):
        return {'ok': False, 'error': f'ungültiger Status: {status}'}
    obj.status = status
    obj.save(update_fields=['status', 'updated_at'])
    return {'ok': True, 'item': serialize_db_item(obj)}


def poll_once(*, pages: int = 1, today_only: bool = True, recent_days: int = 2) -> dict:
    """Für Scheduler / management command — FM + Gulp + Hays."""
    recent_days = max(1, min(14, int(recent_days or 2)))
    fm_items = fetch_freelancermap_projects(
        pages=pages, today_only=today_only, recent_days=recent_days,
    )
    fm_info = persist_items(
        fm_items, archive_older=today_only,
        source_name=SOURCE_NAME, source_url=fm_list_url(),
    )
    gulp_pages = max(3, min(6, int(pages) + 2))
    gulp_items = fetch_gulp_projects(
        pages=gulp_pages, page_size=20,
        today_only=today_only, recent_days=recent_days,
    )
    gulp_info = persist_items(
        gulp_items, archive_older=today_only,
        source_name=GULP_SOURCE_NAME, source_url=gulp_list_url(),
    )
    hays_pages = max(2, min(5, int(pages) + 1))
    hays_items = fetch_hays_projects(
        pages=hays_pages,
        today_only=today_only,
        recent_days=recent_days,
        enrich_details=True,
    )
    hays_info = persist_items(
        hays_items, archive_older=today_only,
        source_name=HAYS_SOURCE_NAME, source_url=hays_list_url(),
    )
    return {
        'ok': True,
        'source': '+'.join(ANFRAGEN_SOURCES),
        'recent_days': recent_days,
        'freelancermap': fm_info,
        'gulp': gulp_info,
        'hays': hays_info,
        'fetched': len(fm_items) + len(gulp_items) + len(hays_items),
        'items_sample': [
            {'id': i.get('external_id'), 'headline': i.get('headline'), 'sources': i.get('sources')}
            for i in (fm_items[:2] + gulp_items[:2] + hays_items[:2])
        ],
    }