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
  A) ✅ Existenz-Check + Verfügbarkeit/Satz — Logik wie CV-Extractor
     GULPImporter (_resolve_gulp_id / _fetch_profile), aber lokal in
     radar_berater_gulp (cv_extractor bleibt unverändert):
     POST …/expert-profiles/search (Body mId) → GET …/{mongoId}
     (0 Treffer = gulp_status=gone). Batch-API + UI-Button.
     Session: settings.json ODER data/url/gu/.session_cookies.json.
  B) Später: PDF/DOCX / volle CV-Pipeline (weiterhin nur CV-Extractor).
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


def _cv_extractor_cookie_paths(cfg: Optional[dict] = None) -> list[str]:
    """Kandidaten: CV-Extractor Session-Datei (Chrome-Extension → gu-session)."""
    cfg = cfg if cfg is not None else _load_tf_cfg()
    out: list[str] = []
    custom = (cfg.get('session_file') or cfg.get('cookies_file') or '').strip()
    if custom:
        out.append(custom)
    # Live-Standard + relative zum Backend-CWD
    out.extend([
        '/opt/abpe/backend/data/url/gu/.session_cookies.json',
        'data/url/gu/.session_cookies.json',
        '/opt/abpe/backend/apps/cv_extractor/data/url/gu/.session_cookies.json',
    ])
    # Dedup, Reihenfolge behalten
    seen = set()
    uniq = []
    for p in out:
        if p and p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def _cookies_from_cv_session_file(path: str) -> str:
    """
    Liest data/url/gu/.session_cookies.json (Format CV-Extractor / Extension):
      { "cookies": [ {"name":"JSESSION_ID_DIREKT","value":"..."}, ... ] }
    Alle Cookies übernehmen (nicht nur JSESSION) — sonst 403.
    """
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return ''
    if not isinstance(data, dict):
        return ''
    raw = data.get('cookies') or data.get('gulp_cookies') or []
    parts: list[str] = []
    has_session_key = False
    if isinstance(raw, dict):
        for k, v in raw.items():
            if not k or v is None or str(v) == '':
                continue
            parts.append(f'{k}={v}')
            if 'JSESSION' in k.upper() or 'remember-me' in k.lower():
                has_session_key = True
    elif isinstance(raw, list):
        for c in raw:
            if not isinstance(c, dict):
                continue
            n = (c.get('name') or '').strip()
            v = c.get('value')
            if not n or v is None or str(v) == '':
                continue
            parts.append(f'{n}={v}')
            if 'JSESSION' in n.upper() or 'remember-me' in n.lower():
                has_session_key = True
    if not parts or not has_session_key:
        return ''
    return '; '.join(parts)


def _cookie_header() -> str:
    """settings.json zuerst, sonst CV-Extractor .session_cookies.json."""
    info = gulp_session_info()
    return info.get('cookie_header') or ''


def gulp_session_info() -> dict[str, Any]:
    """Diagnose: woher die Session kommt."""
    cfg = _load_tf_cfg()
    if cfg.get('cookie_header'):
        h = str(cfg['cookie_header']).strip()
        if h:
            return {
                'ok': True,
                'source': 'settings.cookie_header',
                'path': None,
                'cookie_header': h,
            }
    cookies = cfg.get('cookies') or {}
    if isinstance(cookies, dict) and cookies:
        h = '; '.join(f'{k}={v}' for k, v in cookies.items() if v)
        if h:
            return {
                'ok': True,
                'source': 'settings.cookies',
                'path': None,
                'cookie_header': h,
            }
    for path in _cv_extractor_cookie_paths(cfg):
        h = _cookies_from_cv_session_file(path)
        if h:
            return {
                'ok': True,
                'source': 'cv_extractor.session_file',
                'path': path,
                'cookie_header': h,
            }
    return {
        'ok': False,
        'source': None,
        'path': None,
        'cookie_header': '',
        'hint': (
            'Keine Gulp-Session. Entweder settings.json → shaduler.gulp_talentfinder '
            'oder CV-Extractor Session erneuern '
            '(→ data/url/gu/.session_cookies.json via Chrome-Extension).'
        ),
        'tried_files': _cv_extractor_cookie_paths(cfg),
    }


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
        # XSRF aus Session-Cookies (CV-Extractor speichert XSRF-TOKEN mit)
        m = re.search(r'(?:^|;\s*)XSRF-TOKEN=([^;]+)', cookie)
        if m:
            tok = urllib.parse.unquote(m.group(1).strip())
            h.setdefault('X-XSRF-TOKEN', tok)
            h.setdefault('x-xsrf-token', tok)
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


def _mongo_id_from_hit(hit: Any) -> str:
    """Talentfinder-Hit → profile.id (24-hex Mongo)."""
    if not isinstance(hit, dict):
        return ''
    profile = hit.get('profile') if isinstance(hit.get('profile'), dict) else {}
    for cand in (
        profile.get('id'),
        hit.get('profileId'),
        hit.get('id'),
        (hit.get('expertProfileId') or {}).get('profileId')
        if isinstance(hit.get('expertProfileId'), dict) else None,
    ):
        mid = str(cand or '').strip()
        if re.fullmatch(r'[a-f0-9]{24}', mid, re.I):
            return mid
    n = normalize_expert_profile(hit)
    mid = str(n.get('mongo_id') or '').strip()
    return mid if re.fullmatch(r'[a-f0-9]{24}', mid, re.I) else ''


def _search_by_gulp_mid(gid: str) -> dict[str, Any]:
    """
    gulpId → Mongo — Logik wie GULPImporter._resolve_gulp_id
    (cv_extractor unverändert; hier nur nachgebaut).

    POST …/expert-profiles/search?pageIndex=0&pageSize=5
    Body: mId + sortOrder UPDATED_DATE (wie Importer).
    """
    steps: list[dict] = []
    qs = urllib.parse.urlencode({'pageIndex': 0, 'pageSize': 5})
    url = f'{TF_PROFILE_API}/search?{qs}'
    # Exakt wie url_gu_importer.GULPImporter._resolve_gulp_id
    body = {
        'mId': str(gid),
        'sortOrder': 'UPDATED_DATE',
        'availabilityPercent': 20,
        'remote': False,
        'searchOnlyInRecentProjects': False,
        'searchTerm': None,
    }
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Referer': f'{TF_EXPERTEN}?gulpId={urllib.parse.quote(gid)}',
        'Origin': 'https://www.gulp.de',
    }
    code, _u, raw = _request(
        url,
        method='POST',
        data=json.dumps(body).encode('utf-8'),
        headers=headers,
    )
    steps.append({
        'url': url,
        'method': 'POST',
        'code': code,
        'like': 'GULPImporter._resolve_gulp_id',
    })
    if code != 200 or not raw:
        return {
            'ok': False,
            'empty': False,
            'mongo_id': '',
            'hit': None,
            'steps': steps,
            'http': code,
            'error': f'search HTTP {code}' if code else 'search failed',
        }
    try:
        data = json.loads(raw.decode('utf-8', errors='replace'))
    except Exception as exc:
        steps[-1]['json_err'] = str(exc)[:120]
        return {
            'ok': False,
            'empty': False,
            'mongo_id': '',
            'hit': None,
            'steps': steps,
            'http': code,
            'error': 'JSON',
        }
    hits = _extract_hit_list(data)
    if not hits:
        return {
            'ok': True,
            'empty': True,
            'mongo_id': '',
            'hit': None,
            'steps': steps,
            'http': code,
        }
    # Wie Importer: objects[0].profile.id
    chosen = hits[0] if isinstance(hits[0], dict) else None
    mid = _mongo_id_from_hit(chosen) if chosen else ''
    if not mid:
        for hit in hits:
            mid = _mongo_id_from_hit(hit)
            if mid:
                chosen = hit
                break
    if not mid:
        return {
            'ok': False,
            'empty': False,
            'mongo_id': '',
            'hit': chosen,
            'steps': steps,
            'http': code,
            'error': 'search hit ohne profile.id',
        }
    return {
        'ok': True,
        'empty': False,
        'mongo_id': mid,
        'hit': chosen,
        'steps': steps,
        'http': code,
    }


def _resolve_mongo_id(gid: str) -> tuple[Optional[str], list[dict], bool]:
    """
    Numerische gulpId → Mongo-Profil-ID.
    Returns (mongo_id|None, steps, empty_confirmed).
    empty_confirmed=True → Talentfinder-Suche 200 mit 0 Treffern (gone).
    """
    searched = _search_by_gulp_mid(gid)
    steps = list(searched.get('steps') or [])
    if searched.get('empty'):
        return None, steps, True
    mid = str(searched.get('mongo_id') or '').strip()
    if mid:
        return mid, steps, False
    return None, steps, False


def fetch_expert_by_gulp_id(gulp_id: str, *, mongo_id: str = '') -> dict[str, Any]:
    """
    Lädt Experten-Profil (Session wie CV-Extractor).

    Logik analog GULPImporter — ohne Import/Änderung an cv_extractor:
      1) GET expert-profiles/{mongoId}
      2) POST search mId (=gulpId) → mongoId → GET
      3) HTML / gulp2 nur Fallback
    needs_auth nur wenn probe_session() fehlschlägt.
    """
    gid = str(gulp_id or '').strip()
    mid = str(mongo_id or '').strip()
    steps: list[dict] = []
    if not gid:
        return {'ok': False, 'error': 'gulp_id fehlt'}
    if not has_gulp_session():
        return {
            'ok': False,
            'error': (
                'Gulp-Session fehlt — CV-Extractor Session erneuern '
                '(data/url/gu/.session_cookies.json) oder settings.json'
            ),
            'gulp_id': gid,
            'profil_url': profil_url_for_gulp_id(gid),
            'needs_auth': True,
        }

    if not mid and re.fullmatch(r'[a-f0-9]{24}', gid, re.I):
        mid = gid

    def _load_by_mongo(mongo: str) -> Optional[dict]:
        code, _u, raw = _request(
            f'{TF_PROFILE_API}/{mongo}',
            headers={'Referer': TF_EXPERTEN, 'Origin': 'https://www.gulp.de'},
        )
        steps.append({'url': f'{TF_PROFILE_API}/{mongo}', 'code': code})
        if code == 404:
            return {
                'ok': False,
                'error': 'Profil nicht mehr in Gulp',
                'gulp_id': gid,
                'mongo_id': mongo,
                'profil_url': profil_url_for_gulp_id(gid),
                'not_found': True,
            }
        if code != 200:
            return None
        try:
            data = json.loads(raw.decode('utf-8', errors='replace'))
        except Exception as exc:
            return {'ok': False, 'error': f'JSON: {exc}', 'gulp_id': gid}
        parsed = normalize_expert_profile(data)
        parsed['ok'] = True
        parsed['not_found'] = False
        parsed['mongo_id'] = mongo
        return parsed

    if mid:
        got = _load_by_mongo(mid)
        if got is not None:
            return got

    # Numerische ID → Mongo über Talentfinder (offiziell: search mId)
    if not mid:
        resolved, res_steps, empty = _resolve_mongo_id(gid)
        steps.extend(res_steps)
        if empty:
            return {
                'ok': False,
                'error': 'Profil nicht mehr in Gulp (0 Treffer)',
                'gulp_id': gid,
                'profil_url': profil_url_for_gulp_id(gid),
                'not_found': True,
                'steps': steps,
            }
        if resolved:
            mid = resolved
            got = _load_by_mongo(mid)
            if got is not None:
                if got.get('ok') and not got.get('gulp_id'):
                    got['gulp_id'] = gid
                return got

    # HTML Talentfinder (SPA-Shell — selten mit Daten; Fallback)
    code, _final_url, raw = _request(
        profil_url_for_gulp_id(gid),
        headers={
            'Accept': 'text/html,application/xhtml+xml,application/json',
            'Referer': 'https://www.gulp.de/',
            'Origin': 'https://www.gulp.de',
        },
    )
    steps.append({'url': profil_url_for_gulp_id(gid), 'code': code})
    if code == 200 and raw:
        html = raw.decode('utf-8', errors='replace')
        parsed = _parse_experten_html(html, prefer_gulp_id=gid)
        if parsed:
            mongo2 = parsed.get('mongo_id') or ''
            if mongo2:
                got = _load_by_mongo(mongo2)
                if got is not None:
                    if got.get('ok') and not got.get('gulp_id'):
                        got['gulp_id'] = gid
                    return got
            parsed['ok'] = True
            parsed['not_found'] = False
            parsed['profil_url'] = parsed.get('profil_url') or profil_url_for_gulp_id(gid)
            return parsed
        if any(x in html.lower() for x in (
            'keine treffer', 'keine ergebnisse', '0 ergebnisse', 'keine experten',
        )):
            return {
                'ok': False,
                'error': 'Profil nicht mehr in Gulp (0 Treffer)',
                'gulp_id': gid,
                'profil_url': profil_url_for_gulp_id(gid),
                'not_found': True,
                'steps': steps,
            }

    # gulp2 Fallback (häufig 403 mit Talentfinder-Cookies — kein Auth-Kill)
    csrf = _gulp2_csrf_token()
    saw_ok_empty = False
    for body in (
        {'gulpId': gid, 'page': 0, 'size': 5},
        {'query': gid, 'page': 0, 'size': 5},
        {'filters': {'gulpId': gid}, 'page': 0, 'size': 5},
    ):
        headers = {
            'Content-Type': 'application/json',
            'Origin': 'https://www.gulp.de',
            'Referer': TF_EXPERTEN,
        }
        if csrf:
            headers['x-trust'] = csrf
            headers['X-XSRF-TOKEN'] = csrf
        code, _u, raw = _request(
            GULP2_PROFILES_SEARCH,
            method='POST',
            data=json.dumps(body).encode('utf-8'),
            headers=headers,
        )
        steps.append({'url': GULP2_PROFILES_SEARCH, 'code': code, 'body_keys': list(body)})
        if code != 200:
            continue
        try:
            data = json.loads(raw.decode('utf-8', errors='replace'))
        except Exception:
            continue
        hits = _extract_hit_list(data)
        if not hits:
            saw_ok_empty = True
            continue
        parsed = _normalize_search_hit(data, prefer_gulp_id=gid)
        if parsed:
            parsed['ok'] = True
            parsed['not_found'] = False
            parsed['profil_url'] = parsed.get('profil_url') or profil_url_for_gulp_id(gid)
            return parsed

    if saw_ok_empty:
        return {
            'ok': False,
            'error': 'Profil nicht mehr in Gulp (0 Treffer)',
            'gulp_id': gid,
            'profil_url': profil_url_for_gulp_id(gid),
            'not_found': True,
            'steps': steps,
        }

    # Auth nur wenn Probe wirklich tot
    probe = probe_session()
    if not probe.get('login_test'):
        return {
            'ok': False,
            'error': probe.get('hint') or 'Gulp-Session ungültig',
            'gulp_id': gid,
            'profil_url': profil_url_for_gulp_id(gid),
            'needs_auth': True,
            'probe': {k: probe.get(k) for k in ('login_test', 'http', 'source', 'path')},
            'steps': steps,
        }

    return {
        'ok': False,
        'error': (
            f'Profil gulpId={gid} nicht über Talentfinder auflösbar '
            f'(Session ok). steps={[s.get("code") for s in steps]}'
        ),
        'gulp_id': gid,
        'profil_url': profil_url_for_gulp_id(gid),
        'needs_auth': False,
        'steps': steps,
        'probe': {k: probe.get(k) for k in ('login_test', 'http')},
    }


def _gulp2_csrf_token() -> str:
    """Wie Radar-Anfragen: CSRF-Cookie für gulp2 REST."""
    code, _u, _raw = _request(
        GULP2_CSRF,
        headers={'Referer': 'https://www.gulp.de/gulp2/g/projekte'},
    )
    # Token steckt oft im Set-Cookie der Response — wir bekommen ihn nicht über urllib leicht.
    # Fallback: Cookie-Header aus Session nach CSRF-Call neu lesen hilft nicht.
    # Projekte nutzen CookieJar; hier: Header x-trust aus bekannten Cookie-Namen.
    hdr = _cookie_header()
    for name in ('LzA8Jg9Oe2', 'XSRF-TOKEN', 'csrf', 'CSRF-TOKEN'):
        m = re.search(rf'(?:^|;\s*){re.escape(name)}=([^;]+)', hdr)
        if m:
            return m.group(1)
    # Nach CSRF-GET: manchen Deployments reicht Cookie-Jar nicht — Token aus Body
    if code == 200 and _raw:
        try:
            data = json.loads(_raw.decode('utf-8', errors='replace'))
            if isinstance(data, dict):
                for k in ('token', 'csrf', 'csrfToken', 'value'):
                    if data.get(k):
                        return str(data[k])
            if isinstance(data, str) and data.strip():
                return data.strip()
        except Exception:
            t = _raw.decode('utf-8', errors='replace').strip().strip('"')
            if t and len(t) < 200:
                return t
    return ''


def probe_session() -> dict[str, Any]:
    """
    Wie CV-Extractor Login-Test: Talentfinder secure expert-profiles.
    Zeigt, ob die Session-Datei noch gültig ist (vs. abgelaufen → 403).
    """
    info = gulp_session_info()
    if not info.get('ok'):
        return {**info, 'login_test': False, 'http': None}
    # Feste Probe-URL (wie CV-Extractor); 404 bei fremdem Profil ok, 403 = Auth tot
    probe_url = f'{TF_PROFILE_API}/540e2fc4e4b04404f785de0c'
    code, _u, raw = _request(
        probe_url,
        headers={
            'Referer': TF_EXPERTEN,
            'Origin': 'https://www.gulp.de',
        },
    )
    # 200 = eingeloggt; 404 = Auth ok, Profil fremd/weg; 401/403 = Session tot
    login_ok = code in (200, 404)
    return {
        **{k: v for k, v in info.items() if k != 'cookie_header'},
        'login_test': login_ok,
        'http': code,
        'probe_url': probe_url,
        'body_snip': (raw[:200].decode('utf-8', errors='replace') if raw else ''),
        'hint': (
            None if login_ok
            else 'Session abgelaufen — im Portal CV-Extractor Gulp-Session erneuern (Chrome-Extension).'
        ),
    }


def _parse_experten_html(html: str, prefer_gulp_id: str = '') -> Optional[dict]:
    """Talentfinder HTML/SPA: JSON-Inseln + Meta für Verfügbarkeit."""
    if not html:
        return None
    # Embedded JSON blobs
    for m in re.finditer(
        r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
        html, re.I | re.S,
    ):
        try:
            data = json.loads(m.group(1))
        except Exception:
            continue
        parsed = _normalize_search_hit(data, prefer_gulp_id=prefer_gulp_id)
        if parsed:
            return parsed
        if isinstance(data, dict):
            n = normalize_expert_profile(data)
            if n.get('gulp_id') or n.get('name'):
                return n
    # __NEXT_DATA__ / window.__INITIAL_STATE__
    for pat in (
        r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});\s*</script>',
        r'<script id="__NEXT_DATA__"[^>]*>(\{.*?\})</script>',
    ):
        m = re.search(pat, html, re.I | re.S)
        if not m:
            continue
        try:
            data = json.loads(m.group(1))
        except Exception:
            continue
        parsed = _normalize_search_hit(data, prefer_gulp_id=prefer_gulp_id)
        if parsed:
            return parsed
    # Leere Trefferliste?
    low = html.lower()
    if any(x in low for x in (
        'keine treffer', 'keine ergebnisse', '0 ergebnisse',
        'no results', 'keine experten',
    )):
        return None
    # Heuristik: gulpId + verfügbarkeit im Text
    if prefer_gulp_id and prefer_gulp_id not in html:
        return None
    avail = None
    m = re.search(
        r'(?:verfügbar(?:\s*ab)?|available(?:\s*from)?)\s*[:\s]*'
        r'(\d{1,2}[./]\d{1,2}[./]\d{2,4}|\d{4}-\d{2}-\d{2})',
        html, re.I,
    )
    if m:
        avail = _parse_date(m.group(1))
    rate = None
    m = re.search(r'(\d{2,3}(?:[.,]\d{1,2})?)\s*€\s*/\s*(?:Tag|tag|Std|std|h\b)', html)
    if m:
        rate = _parse_rate(m.group(1))
    mongo = ''
    m = re.search(r'/expert-profiles/([a-f0-9]{24})', html, re.I)
    if m:
        mongo = m.group(1)
    if not avail and not rate and not mongo:
        return None
    return {
        'gulp_id': prefer_gulp_id,
        'mongo_id': mongo,
        'name': placeholder_name(prefer_gulp_id),
        'verfuegbar_ab': avail,
        'satz': rate,
        'ort': '',
        'skills': [],
        'beschreibung': '',
        'profil_url': profil_url_for_gulp_id(prefer_gulp_id),
        'source': 'html',
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
    # Talentfinder search: { objects: [ {expert, profile}, … ] }
    for key in ('objects', 'content', 'results', 'items', 'profiles', 'data', 'hits'):
        v = data.get(key)
        if isinstance(v, list):
            return v
        if isinstance(v, dict) and isinstance(v.get('content'), list):
            return v['content']
        if isinstance(v, dict) and isinstance(v.get('objects'), list):
            return v['objects']
    return []


def _normalize_search_hit(data: Any, prefer_gulp_id: str = '') -> Optional[dict]:
    items = _extract_hit_list(data)
    if not items and isinstance(data, dict) and (
        data.get('gulpId') or data.get('id') or data.get('expert') or data.get('profile')
    ):
        items = [data]
    for hit in items:
        n = normalize_expert_profile(hit)
        if prefer_gulp_id and not n.get('gulp_id'):
            n['gulp_id'] = prefer_gulp_id
        if prefer_gulp_id and str(n.get('gulp_id') or '') != str(prefer_gulp_id):
            # trotzdem nehmen wenn nur ein Treffer
            if len(items) > 1:
                continue
        return n
    return None


def normalize_expert_profile(raw: dict) -> dict[str, Any]:
    """Gulp Expert JSON → flaches Radar-Dict (auch Talentfinder {expert,profile})."""
    if not isinstance(raw, dict):
        return {}

    expert = raw.get('expert') if isinstance(raw.get('expert'), dict) else {}
    profile = raw.get('profile') if isinstance(raw.get('profile'), dict) else {}
    personal = (
        expert.get('personalData')
        if isinstance(expert.get('personalData'), dict)
        else (raw.get('personalData') if isinstance(raw.get('personalData'), dict) else {})
    )
    addr = (
        expert.get('address')
        if isinstance(expert.get('address'), dict)
        else (raw.get('address') if isinstance(raw.get('address'), dict) else {})
    )
    pay = (
        profile.get('expectedPayment')
        if isinstance(profile.get('expectedPayment'), dict)
        else (
            raw.get('expectedPayment')
            if isinstance(raw.get('expectedPayment'), dict)
            else {}
        )
    )

    gulp_id = str(
        raw.get('gulpId')
        or raw.get('gulp_id')
        or raw.get('numericId')
        or expert.get('gulpId')
        or expert.get('mId')  # wie GULPImporter
        or profile.get('gulpId')
        or ''
    ).strip()
    # expert.id ist oft die numerische Gulp-ID
    if not gulp_id:
        eid = str(expert.get('id') or '').strip()
        if eid.isdigit():
            gulp_id = eid

    mongo = str(
        profile.get('id')
        or raw.get('profileId')
        or ''
    ).strip()
    if not re.fullmatch(r'[a-f0-9]{24}', mongo, re.I):
        cand = str(raw.get('id') or '').strip()
        mongo = cand if re.fullmatch(r'[a-f0-9]{24}', cand, re.I) else ''
    if not gulp_id and mongo:
        gulp_id = mongo

    name_obj = raw.get('name') if isinstance(raw.get('name'), dict) else {}
    first = (
        personal.get('firstName')
        or raw.get('firstName')
        or raw.get('firstname')
        or name_obj.get('first')
        or ''
    )
    last = (
        personal.get('lastName')
        or raw.get('lastName')
        or raw.get('lastname')
        or name_obj.get('last')
        or ''
    )
    # Expert-Model hat .name als Property — API liefert ggf. schon string
    expert_name = expert.get('name') if isinstance(expert.get('name'), str) else ''
    display = (
        raw.get('displayName')
        or raw.get('fullName')
        or expert_name
        or ' '.join(x for x in [str(first or '').strip(), str(last or '').strip()] if x)
        or ''
    )
    if not display and gulp_id:
        display = placeholder_name(gulp_id)

    skills = (
        profile.get('topSkills')
        or profile.get('additionalSkills')
        or raw.get('skills')
        or raw.get('skillNames')
        or raw.get('topSkills')
        or []
    )
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

    ort = (
        raw.get('city')
        or raw.get('location')
        or raw.get('wohnort')
        or addr.get('city')
        or ''
    )
    avail = (
        profile.get('availableFrom')
        or profile.get('availableFromDate')
        or profile.get('availabilityDate')
        or raw.get('availableFrom')
        or raw.get('availabilityDate')
        or raw.get('verfuegbarAb')
        or raw.get('available_from')
        or expert.get('availableFrom')
    )
    verfuegbar = _parse_date(avail)
    satz = _parse_rate(
        (pay.get('rate') if pay else None)
        or raw.get('dayRate')
        or raw.get('hourlyRate')
        or raw.get('rate')
        or raw.get('satz')
        or profile.get('dayRate')
        or profile.get('hourlyRate')
    )
    desc = (
        profile.get('coreCompetence')
        or profile.get('competencesText')
        or raw.get('profileText')
        or raw.get('description')
        or raw.get('summary')
        or raw.get('about')
        or ''
    )
    cv_text = (
        profile.get('projectsText')
        or raw.get('cvText')
        or raw.get('curriculum')
        or ''
    )
    url = ''
    if mongo:
        url = f'{TF_EXPERTEN}/{mongo}'
    elif gulp_id:
        url = profil_url_for_gulp_id(gulp_id)

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
