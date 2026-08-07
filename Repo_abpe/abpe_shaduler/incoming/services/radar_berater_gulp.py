"""
Gulp Talentfinder — Berater/Experten (Phase 1).

Live-Liste braucht Gulp-Login (Session-Cookies). Ohne Cookies:
  - Paste Gulp-ID / Profil-URL
  - Seed aus CRM (contacts.gulp_id_c)

settings.json → shaduler.gulp_talentfinder:
  {
    "cookies": { "JSESSION_ID_DIREKT": "...", "remember-me-dir": "..." },
    "cookie_header": "JSESSION_ID_DIREKT=...; remember-me-dir=..."
  }

GEPLANT — „Gulp aktualisieren“:
  A) ✅ Existenz-Check + Verfügbarkeit/Satz via profiles/search
     (0 Treffer = gulp_status=gone). Batch-API + UI-Button.
  B) Später: PDF/DOCX via GULPImporter, volle CV-Pipeline.
     Radar = News/Deltas, kein CRM-Spiegel.
"""
from __future__ import annotations

import json
import logging
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from typing import Any, Optional

from django.conf import settings

log = logging.getLogger('abpe_shaduler.radar_berater_gulp')

UA = (
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 ABpE-RadarBerater/1.0'
)
CTX = ssl.create_default_context()

TF_BASE = 'https://www.gulp.de/talentfinder/app'
TF_EXPERTEN = f'{TF_BASE}/experten'
TF_PROFILE_API = f'{TF_BASE}/api/secure/expert-profiles'
GULP2_PROFILES_SEARCH = 'https://www.gulp.de/gulp2/rest/internal/profiles/search'
GULP2_CSRF = 'https://www.gulp.de/gulp2/rest/internal/system/csrf'


def _load_tf_cfg() -> dict:
    try:
        path = getattr(settings, 'ABPE_SETTINGS_PATH', None) or '/opt/abpe/backend/settings.json'
        with open(path, encoding='utf-8') as f:
            cfg = json.load(f)
        return (cfg.get('shaduler') or {}).get('gulp_talentfinder') or {}
    except Exception:
        return {}


def _cookie_header() -> str:
    cfg = _load_tf_cfg()
    if cfg.get('cookie_header'):
        return str(cfg['cookie_header']).strip()
    cookies = cfg.get('cookies') or {}
    if isinstance(cookies, dict) and cookies:
        return '; '.join(f'{k}={v}' for k, v in cookies.items() if v)
    return ''


def has_gulp_session() -> bool:
    return bool(_cookie_header())


def parse_gulp_id(text: str) -> str:
    """Extrahiert numerische Gulp-ID aus URL oder Freitext."""
    s = (text or '').strip()
    if not s:
        return ''
    m = re.search(r'[?&]gulpId=(\d+)', s, re.I)
    if m:
        return m.group(1)
    m = re.search(r'/experten/(\d+)\b', s)
    if m:
        return m.group(1)
    m = re.search(r'/expert-profiles/([a-f0-9]{24})\b', s, re.I)
    if m:
        return m.group(1)  # mongo id — speichern als gulp_id string
    m = re.fullmatch(r'(\d{3,12})', s)
    if m:
        return m.group(1)
    m = re.search(r'\bGulp[-\s]?ID\s*[:=]?\s*(\d+)\b', s, re.I)
    if m:
        return m.group(1)
    return ''


def profil_url_for_gulp_id(gulp_id: str) -> str:
    gid = str(gulp_id or '').strip()
    if not gid:
        return ''
    if re.fullmatch(r'[a-f0-9]{24}', gid, re.I):
        return f'{TF_PROFILE_API}/{gid}'
    return f'{TF_EXPERTEN}?gulpId={urllib.parse.quote(gid)}'


def placeholder_name(gulp_id: str) -> str:
    return f'Gulp {gulp_id}' if gulp_id else 'Gulp ?'


def _request(
    url: str,
    *,
    method: str = 'GET',
    data: Optional[bytes] = None,
    headers: Optional[dict] = None,
    timeout: int = 25,
) -> tuple[int, str, bytes]:
    h = {
        'User-Agent': UA,
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'de-DE,de;q=0.9',
        'direkt-language': 'de',
        'x-requested-with': 'XMLHttpRequest',
    }
    cookie = _cookie_header()
    if cookie:
        h['Cookie'] = cookie
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
            return int(resp.status), resp.geturl(), resp.read(900_000)
    except urllib.error.HTTPError as e:
        body = e.read(50_000) if e.fp else b''
        return int(e.code), url, body
    except Exception as exc:
        return 0, url, str(exc).encode('utf-8', errors='replace')


def fetch_expert_by_gulp_id(gulp_id: str) -> dict[str, Any]:
    """
    Lädt ein Experten-Profil (braucht Session).

    Returns u.a.:
      ok, gulp_id, name, skills, ort, verfuegbar_ab, satz, …
      not_found=True  → API 200, 0 Treffer (Profil weg)
      needs_auth=True → keine Cookies / 401/403
    """
    gid = str(gulp_id or '').strip()
    if not gid:
        return {'ok': False, 'error': 'gulp_id fehlt'}
    if not has_gulp_session():
        return {
            'ok': False,
            'error': 'Gulp-Session fehlt (settings.json → shaduler.gulp_talentfinder.cookies)',
            'gulp_id': gid,
            'profil_url': profil_url_for_gulp_id(gid),
            'needs_auth': True,
        }

    saw_ok_empty = False
    last_http = None
    payloads = [
        {'gulpId': gid, 'page': 0, 'size': 5},
        {'query': gid, 'page': 0, 'size': 5},
        {'filters': {'gulpId': gid}, 'page': 0, 'size': 5},
    ]
    for body in payloads:
        code, _u, raw = _request(
            GULP2_PROFILES_SEARCH,
            method='POST',
            data=json.dumps(body).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'Origin': 'https://www.gulp.de',
                'Referer': TF_EXPERTEN,
            },
        )
        last_http = code
        if code in (401, 403):
            return {
                'ok': False,
                'error': f'Nicht autorisiert (HTTP {code}) — Gulp-Cookies prüfen',
                'gulp_id': gid,
                'profil_url': profil_url_for_gulp_id(gid),
                'needs_auth': True,
            }
        if code != 200:
            continue
        try:
            data = json.loads(raw.decode('utf-8', errors='replace'))
        except Exception:
            continue
        hits = _extract_hit_list(data)
        if not hits and isinstance(data, dict) and (data.get('gulpId') or data.get('id')):
            hits = [data]
        if not hits:
            saw_ok_empty = True
            continue
        parsed = _normalize_search_hit(data, prefer_gulp_id=gid)
        if parsed:
            parsed['ok'] = True
            parsed['not_found'] = False
            parsed['profil_url'] = parsed.get('profil_url') or profil_url_for_gulp_id(gid)
            return parsed

    # Mongo-ID Direktzugriff
    if re.fullmatch(r'[a-f0-9]{24}', gid, re.I):
        code, _u, raw = _request(f'{TF_PROFILE_API}/{gid}')
        if code in (401, 403):
            return {
                'ok': False,
                'error': f'Nicht autorisiert (HTTP {code})',
                'gulp_id': gid,
                'needs_auth': True,
            }
        if code == 404:
            return {
                'ok': False,
                'error': 'Profil nicht mehr in Gulp',
                'gulp_id': gid,
                'profil_url': profil_url_for_gulp_id(gid),
                'not_found': True,
            }
        if code == 200:
            try:
                data = json.loads(raw.decode('utf-8', errors='replace'))
            except Exception as exc:
                return {'ok': False, 'error': f'JSON: {exc}', 'gulp_id': gid}
            parsed = normalize_expert_profile(data)
            parsed['ok'] = True
            parsed['not_found'] = False
            return parsed
        return {'ok': False, 'error': f'Profil HTTP {code}', 'gulp_id': gid}

    if saw_ok_empty:
        return {
            'ok': False,
            'error': 'Profil nicht mehr in Gulp (0 Treffer)',
            'gulp_id': gid,
            'profil_url': profil_url_for_gulp_id(gid),
            'not_found': True,
        }

    return {
        'ok': False,
        'error': f'Profil nicht ladbar (HTTP {last_http}) — Login/API prüfen',
        'gulp_id': gid,
        'profil_url': profil_url_for_gulp_id(gid),
        'needs_auth': last_http in (401, 403, None) and not has_gulp_session(),
    }


def fetch_experts_list(
    *,
    page: int = 0,
    size: int = 20,
    available_only: bool = True,
) -> dict[str, Any]:
    """
    Listensuche Talentfinder (Session nötig).
    available_only=True → Filter soweit die API mitmacht.
    """
    if not has_gulp_session():
        return {
            'ok': False,
            'error': 'Gulp-Session fehlt',
            'needs_auth': True,
            'results': [],
        }

    bodies = []
    if available_only:
        bodies += [
            {'page': page, 'size': size, 'onlyAvailable': True},
            {'page': page, 'size': size, 'availability': 'AVAILABLE'},
            {'page': page, 'size': size, 'filters': {'available': True}},
        ]
    bodies.append({'page': page, 'size': size, 'query': ''})

    last_err = ''
    for body in bodies:
        code, _u, raw = _request(
            GULP2_PROFILES_SEARCH,
            method='POST',
            data=json.dumps(body).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'Origin': 'https://www.gulp.de',
                'Referer': TF_EXPERTEN,
            },
        )
        if code in (401, 403):
            return {
                'ok': False,
                'error': f'Nicht autorisiert (HTTP {code}) — Gulp-Cookies prüfen',
                'needs_auth': True,
                'results': [],
            }
        if code != 200:
            last_err = f'HTTP {code}: {raw[:200]!r}'
            continue
        try:
            data = json.loads(raw.decode('utf-8', errors='replace'))
        except Exception as exc:
            last_err = str(exc)
            continue
        items = _extract_hit_list(data)
        out = []
        for hit in items:
            n = normalize_expert_profile(hit)
            if n.get('gulp_id') or n.get('name'):
                out.append(n)
        return {
            'ok': True,
            'results': out,
            'page': page,
            'size': size,
            'available_only': available_only,
            'raw_count': len(items),
        }

    return {'ok': False, 'error': last_err or 'Suche fehlgeschlagen', 'results': []}


def _extract_hit_list(data: Any) -> list:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in ('content', 'results', 'items', 'profiles', 'data', 'hits'):
        v = data.get(key)
        if isinstance(v, list):
            return v
        if isinstance(v, dict) and isinstance(v.get('content'), list):
            return v['content']
    return []


def _normalize_search_hit(data: Any, prefer_gulp_id: str = '') -> Optional[dict]:
    items = _extract_hit_list(data)
    if not items and isinstance(data, dict) and (data.get('gulpId') or data.get('id')):
        items = [data]
    for hit in items:
        n = normalize_expert_profile(hit)
        if prefer_gulp_id and str(n.get('gulp_id') or '') != str(prefer_gulp_id):
            # trotzdem nehmen wenn nur ein Treffer
            if len(items) > 1:
                continue
        return n
    return None


def normalize_expert_profile(raw: dict) -> dict[str, Any]:
    """Gulp Expert JSON → flaches Radar-Dict."""
    if not isinstance(raw, dict):
        return {}
    gulp_id = str(
        raw.get('gulpId')
        or raw.get('gulp_id')
        or raw.get('numericId')
        or ''
    ).strip()
    mongo = str(raw.get('id') or raw.get('profileId') or '').strip()
    if not gulp_id and mongo:
        gulp_id = mongo

    name_obj = raw.get('name') if isinstance(raw.get('name'), dict) else {}
    first = (
        raw.get('firstName')
        or raw.get('firstname')
        or name_obj.get('first')
        or ''
    )
    last = (
        raw.get('lastName')
        or raw.get('lastname')
        or name_obj.get('last')
        or ''
    )
    display = (
        raw.get('displayName')
        or raw.get('fullName')
        or ' '.join(x for x in [str(first or '').strip(), str(last or '').strip()] if x)
        or ''
    )
    if not display and gulp_id:
        display = placeholder_name(gulp_id)

    skills = raw.get('skills') or raw.get('skillNames') or raw.get('topSkills') or []
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(',') if s.strip()]
    if isinstance(skills, list):
        skills = [
            (s.get('name') if isinstance(s, dict) else str(s)).strip()
            for s in skills
            if (s.get('name') if isinstance(s, dict) else str(s)).strip()
        ]
    else:
        skills = []

    addr = raw.get('address') if isinstance(raw.get('address'), dict) else {}
    ort = (
        raw.get('city')
        or raw.get('location')
        or raw.get('wohnort')
        or addr.get('city')
        or ''
    )
    avail = (
        raw.get('availableFrom')
        or raw.get('availabilityDate')
        or raw.get('verfuegbarAb')
        or raw.get('available_from')
    )
    verfuegbar = _parse_date(avail)
    satz = _parse_rate(
        raw.get('dayRate')
        or raw.get('hourlyRate')
        or raw.get('rate')
        or raw.get('satz')
    )
    desc = (
        raw.get('profileText')
        or raw.get('description')
        or raw.get('summary')
        or raw.get('about')
        or ''
    )
    cv_text = raw.get('cvText') or raw.get('curriculum') or ''
    url = profil_url_for_gulp_id(gulp_id) if gulp_id else ''

    return {
        'gulp_id': gulp_id,
        'mongo_id': mongo,
        'name': display,
        'first_name': str(first or '').strip(),
        'last_name': str(last or '').strip(),
        'skills': skills[:40],
        'ort': str(ort or '').strip(),
        'verfuegbar_ab': verfuegbar.isoformat() if isinstance(verfuegbar, date) else None,
        'satz': satz,
        'beschreibung': str(desc or '')[:8000],
        'cv_text': str(cv_text or '')[:50000] if cv_text else '',
        'profil_url': url,
        'raw': {k: raw[k] for k in list(raw)[:40]},  # truncated keys only
        'source': 'gulp',
    }


def _parse_date(val) -> Optional[date]:
    if val is None or val == '':
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    s = str(val).strip()
    for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%fZ'):
        try:
            return datetime.strptime(s[:26].replace('Z', ''), fmt.replace('.%fZ', '')).date()
        except ValueError:
            continue
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def _parse_rate(val) -> Optional[float]:
    if val is None or val == '':
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        s = re.sub(r'[^\d.,]', '', str(val))
        s = s.replace('.', '').replace(',', '.') if s.count(',') == 1 else s
        try:
            return float(s)
        except ValueError:
            return None
