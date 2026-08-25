"""
Freelancermap — Radar Berater (Phase 1 + Stufe B).

Suche:
  GET /freelancer/search/ajax?…&excludeUnavailable=1
  Ohne Session: Liste ok, Stundensätze oft null.
  Mit Business-Session: paymentInformation.hourlyRate gesetzt.

Profil (Paste / Enrich):
  GET /profil/{slug} → <script data-component-name="ProfileShow">…</script>
  Optional ld+json Person bei Soft-Anonym (firstName/lastName == anonymous).

Session (wie Gulp, Pfad fl statt gu):
  settings.json → shaduler.freelancermap
    cookie_header | cookies | session_file
  ODER data/url/fl/.session_cookies.json
    { "cookies": [ {"name":"…","value":"…"}, … ] }

Profil-URL: https://www.freelancermap.de/profil/{slug}
CRM: freelancermap_profil_c / freelancermap_last_updated_c

cv_extractor bleibt unverändert (Logik hier nachgebaut, nicht importiert).
"""
from __future__ import annotations

import json
import logging
import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from typing import Any, Optional

from django.conf import settings

log = logging.getLogger('abpe_shaduler.radar_berater_fl')

UA = (
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 ABpE-RadarBerater-FL/1.0'
)
CTX = ssl.create_default_context()

FM_BASE = 'https://www.freelancermap.de'
FM_LIST = f'{FM_BASE}/freelancer'
FM_SEARCH_AJAX = f'{FM_BASE}/freelancer/search/ajax'

# availability.* aus FM-Übersetzungen
# 3=Verfügbar, 2=Teilweise, 20/40/60/80=% , 1=nicht verfügbar (mit until)
AVAIL_OK = {2, 3, 20, 40, 60, 80}

_RE_PROFIL_SLUG = re.compile(
    r'(?:https?://)?(?:www\.)?freelancermap\.de/profil/([A-Za-z0-9][A-Za-z0-9\-_/]*)',
    re.I,
)
_RE_SLUG_ID = re.compile(r'-(\d{4,8})$')
_RE_PROFILE_SHOW = re.compile(
    r'<script[^>]*\bdata-component-name=["\']ProfileShow["\'][^>]*>(.*?)</script>',
    re.I | re.DOTALL,
)
_RE_LD_JSON = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.DOTALL,
)


def profil_url_for(*, slug: str = '', fm_id: str = '') -> str:
    slug = (slug or '').strip().strip('/')
    if slug:
        return f'{FM_BASE}/profil/{slug}'
    fid = str(fm_id or '').strip()
    if fid:
        return f'{FM_BASE}/freelancer?id={urllib.parse.quote(fid)}'
    return FM_LIST


def kontakt_url_for(*, slug: str = '', fm_id: str = '') -> str:
    """Kontakt über Profilseite (Anschreiben in FM nach Login)."""
    return profil_url_for(slug=slug, fm_id=fm_id)


def _load_fl_cfg() -> dict:
    try:
        path = getattr(settings, 'ABPE_SETTINGS_PATH', None) or '/opt/abpe/backend/settings.json'
        with open(path, encoding='utf-8') as f:
            cfg = json.load(f)
        return (cfg.get('shaduler') or {}).get('freelancermap') or {}
    except Exception:
        return {}


def _fl_cookie_paths(cfg: Optional[dict] = None) -> list[str]:
    """Kandidaten: CV-Extractor / Extension Session-Datei (fl)."""
    cfg = cfg if cfg is not None else _load_fl_cfg()
    out: list[str] = []
    custom = (cfg.get('session_file') or cfg.get('cookies_file') or '').strip()
    if custom:
        out.append(custom)
    out.extend([
        '/opt/abpe/backend/data/url/fl/.session_cookies.json',
        'data/url/fl/.session_cookies.json',
        '/opt/abpe/backend/apps/cv_extractor/data/url/fl/.session_cookies.json',
    ])
    seen: set[str] = set()
    uniq: list[str] = []
    for p in out:
        if p and p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def _cookies_from_session_file(path: str) -> str:
    """
    Liest data/url/fl/.session_cookies.json:
      { "cookies": [ {"name":"…","value":"…"}, … ] }
    Alle Cookies übernehmen (Business-Login → Stundensätze).
    """
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return ''
    if not isinstance(data, dict):
        return ''
    raw = data.get('cookies') or data.get('fl_cookies') or data.get('fm_cookies') or []
    parts: list[str] = []
    if isinstance(raw, dict):
        for k, v in raw.items():
            if not k or v is None or str(v) == '':
                continue
            parts.append(f'{k}={v}')
    elif isinstance(raw, list):
        for c in raw:
            if not isinstance(c, dict):
                continue
            n = (c.get('name') or '').strip()
            v = c.get('value')
            if not n or v is None or str(v) == '':
                continue
            parts.append(f'{n}={v}')
    # FM: kein JSESSION-Pflicht — jede nicht-leere Cookie-Menge zählt
    return '; '.join(parts) if parts else ''


def _cookie_names(header: str) -> list[str]:
    names: list[str] = []
    for part in (header or '').split(';'):
        part = part.strip()
        if not part or '=' not in part:
            continue
        names.append(part.split('=', 1)[0].strip())
    return names


def _session_payload(
    *,
    ok: bool,
    source: Optional[str],
    path: Optional[str],
    cookie_header: str = '',
    include_secrets: bool = False,
    hint: Optional[str] = None,
    tried_files: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Diagnose ohne Cookie-Werte (Secrets nur intern / explizit)."""
    out: dict[str, Any] = {
        'ok': ok,
        'source': source,
        'path': path,
        'cookie_names': _cookie_names(cookie_header) if cookie_header else [],
        'cookies_n': len(_cookie_names(cookie_header)) if cookie_header else 0,
    }
    if hint:
        out['hint'] = hint
    if tried_files is not None:
        out['tried_files'] = tried_files
    if include_secrets:
        out['cookie_header'] = cookie_header or ''
    return out


def fl_session_info(*, include_secrets: bool = False) -> dict[str, Any]:
    """Diagnose: woher die FM-Session kommt (ohne Cookie-Werte)."""
    cfg = _load_fl_cfg()
    if cfg.get('cookie_header'):
        h = str(cfg['cookie_header']).strip()
        if h:
            return _session_payload(
                ok=True,
                source='settings.cookie_header',
                path=None,
                cookie_header=h,
                include_secrets=include_secrets,
            )
    cookies = cfg.get('cookies') or {}
    if isinstance(cookies, dict) and cookies:
        h = '; '.join(f'{k}={v}' for k, v in cookies.items() if v)
        if h:
            return _session_payload(
                ok=True,
                source='settings.cookies',
                path=None,
                cookie_header=h,
                include_secrets=include_secrets,
            )
    for path in _fl_cookie_paths(cfg):
        if not os.path.isfile(path):
            continue
        h = _cookies_from_session_file(path)
        if h:
            return _session_payload(
                ok=True,
                source='session_file',
                path=path,
                cookie_header=h,
                include_secrets=include_secrets,
            )
    return _session_payload(
        ok=False,
        source=None,
        path=None,
        cookie_header='',
        include_secrets=include_secrets,
        hint=(
            'Keine Freelancermap-Session. settings.json → shaduler.freelancermap '
            '(cookie_header/cookies/session_file) oder '
            'data/url/fl/.session_cookies.json (Chrome-Extension / CV-Login).'
        ),
        tried_files=_fl_cookie_paths(cfg),
    )


def _cookie_header() -> str:
    return fl_session_info(include_secrets=True).get('cookie_header') or ''


def has_fl_session() -> bool:
    return bool(_cookie_header())


def _request(
    url: str,
    *,
    headers: Optional[dict] = None,
    timeout: int = 30,
    use_cookies: bool = True,
    accept: str = 'application/json, text/plain, */*',
) -> tuple[int, bytes]:
    h = {
        'User-Agent': UA,
        'Accept': accept,
        'Accept-Language': 'de-DE,de;q=0.9',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': FM_LIST,
    }
    if use_cookies:
        cookie = _cookie_header()
        if cookie:
            h['Cookie'] = cookie
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
            return int(resp.status), resp.read(2_500_000)
    except urllib.error.HTTPError as e:
        body = e.read(120_000) if e.fp else b''
        return int(e.code), body
    except Exception as exc:
        return 0, str(exc).encode('utf-8', errors='replace')


def _parse_date(val) -> Optional[date]:
    if val is None or val == '':
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    s = str(val).strip()
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def _html_to_text(html: str) -> str:
    if not html:
        return ''
    t = re.sub(r'<[^>]+>', ' ', str(html))
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def _rate_from_payment(pay: Any) -> Optional[float]:
    if not isinstance(pay, dict):
        return None
    for k in (
        'hourlyRate', 'hourRate', 'rate', 'price', 'amount',
        'stundensatz', 'hour_rate', 'hourly_rate',
    ):
        v = pay.get(k)
        if v is None or v == '':
            continue
        try:
            n = float(str(v).replace(',', '.').replace('€', '').strip())
        except (TypeError, ValueError):
            continue
        if n > 0:
            return n
    return None


def _rate_from_raw(raw: dict) -> Optional[float]:
    """paymentInformation oder Top-Level-Felder."""
    if not isinstance(raw, dict):
        return None
    for key in ('paymentInformation', 'payment', 'payment_information'):
        r = _rate_from_payment(raw.get(key))
        if r is not None:
            return r
    for k in ('hourlyRate', 'hourRate', 'stundensatz', 'hourly_rate'):
        v = raw.get(k)
        if v is None or v == '':
            continue
        try:
            n = float(str(v).replace(',', '.').replace('€', '').strip())
        except (TypeError, ValueError):
            continue
        if n > 0:
            return n
    return None


def _is_masked_name(val: str) -> bool:
    """Soft-Anonym: anonymous / **** / nur Maskierungszeichen."""
    t = (val or '').strip()
    if not t:
        return True
    low = t.lower()
    if low in ('anonymous', 'anonym', 'n/a', '-', 'null', 'none'):
        return True
    if re.fullmatch(r'[\*\u2022·.•\u00d7xX]+', t):
        return True
    return False


def normalize_freelancer(raw: dict) -> dict[str, Any]:
    """FM Freelancer-JSON → Radar-Dict."""
    if not isinstance(raw, dict):
        return {}
    fm_id = str(raw.get('id') or '').strip()
    slug = str(raw.get('slug') or '').strip()
    user = raw.get('user') if isinstance(raw.get('user'), dict) else {}
    first = str(user.get('firstName') or '').strip()
    last = str(user.get('lastName') or '').strip()
    if _is_masked_name(first):
        first = ''
    if _is_masked_name(last):
        last = ''
    title = str(raw.get('title') or '').strip()
    display = ' '.join(x for x in [first, last] if x).strip() or title or (
        f'FM {fm_id}' if fm_id else 'Freelancermap'
    )

    skills = raw.get('skills') or []
    if isinstance(skills, list):
        out_skills = []
        for s in skills:
            if isinstance(s, dict):
                nm = (
                    s.get('de') or s.get('name') or s.get('label')
                    or s.get('en') or ''
                ).strip()
            else:
                nm = str(s).strip()
            # reine Kategorie-IDs verwerfen
            if nm.isdigit():
                continue
            if nm and nm not in out_skills:
                out_skills.append(nm)
        skills = out_skills
    else:
        skills = []

    # Subcategories as skills fallback (nur Dicts mit Namen)
    for cat in (raw.get('sortedSubCategories') or []):
        if isinstance(cat, dict):
            nm = (
                cat.get('de') or cat.get('name') or cat.get('label')
                or cat.get('en') or ''
            ).strip()
        else:
            nm = str(cat).strip()
        if nm.isdigit():
            continue
        if nm and nm not in skills:
            skills.append(nm)

    city = str(user.get('city') or '').strip()
    country = ''
    cobj = user.get('country') if isinstance(user.get('country'), dict) else {}
    if cobj:
        country = str(cobj.get('name') or cobj.get('iso2') or '').strip()
    ort = ', '.join(x for x in [city, country] if x)

    avail_code = raw.get('availability')
    try:
        avail_code_i = int(avail_code) if avail_code is not None else None
    except (TypeError, ValueError):
        avail_code_i = None
    avail_pct = raw.get('availability_normalized')
    until = _parse_date(raw.get('unavailableUntil'))
    verfuegbar = None
    if until:
        verfuegbar = until
    elif avail_code_i in AVAIL_OK or (isinstance(avail_pct, (int, float)) and avail_pct > 0):
        verfuegbar = date.today()

    satz = _rate_from_raw(raw)

    desc_parts: list[str] = []
    if title:
        desc_parts.append(title)
    grad = str(raw.get('graduation') or '').strip()
    if grad:
        desc_parts.append(grad)
    other = _html_to_text(raw.get('other') or '')
    if other:
        desc_parts.append(other)

    refs = raw.get('references') or []
    proj_lines = []
    if isinstance(refs, list):
        for ref in refs[:15]:
            if not isinstance(ref, dict):
                continue
            start = _parse_date(ref.get('startDate'))
            end = _parse_date(ref.get('endDate'))
            period = ' – '.join(
                x for x in [
                    start.isoformat() if start else '',
                    'heute' if ref.get('atNow') else (end.isoformat() if end else ''),
                ] if x
            )
            pos = (ref.get('position') or '').strip()
            comp = (ref.get('company') or '').strip()
            line = ' · '.join(x for x in [period, pos, comp] if x)
            body = _html_to_text(ref.get('description') or '')[:400]
            if body:
                line = (line + '\n' + body).strip() if line else body
            if line:
                proj_lines.append(line)
    if proj_lines:
        desc_parts.append('Projekte:\n' + '\n\n'.join(proj_lines))

    links = raw.get('links') if isinstance(raw.get('links'), dict) else {}
    profil = str(links.get('title') or '').strip() or profil_url_for(slug=slug, fm_id=fm_id)

    return {
        'fm_id': fm_id,
        'fm_slug': slug,
        'fm_user_id': str(user.get('id') or '').strip(),
        'gulp_id': '',  # FL-only
        'name': display,
        'first_name': first,
        'last_name': last,
        'title': title,
        'skills': skills[:80],
        'ort': ort,
        'verfuegbar_ab': verfuegbar.isoformat() if verfuegbar else None,
        'satz': satz,
        'beschreibung': '\n\n'.join(desc_parts)[:8000],
        'cv_text': '',
        'profil_url': profil,
        'kontakt_url': kontakt_url_for(slug=slug, fm_id=fm_id),
        'availability_code': avail_code_i,
        'availability_percent': avail_pct,
        'anonym': bool(raw.get('anonym')),
        'source': 'freelancermap',
        'source_name': 'freelancermap',
    }


def fetch_freelancers_list(
    *,
    page: int = 1,
    available_only: bool = True,
    countries: Optional[list[int]] = None,
    query: str = '',
) -> dict[str, Any]:
    """
    FM Freelancer-Suche (öffentlich).
    page: 1-basiert (pagenr).
    query: Freitext/Keywords (wie Suchfeld auf /freelancer).
    """
    page = max(1, int(page or 1))
    countries = countries or [1, 2, 3]  # DE, AT, CH
    q = (query or '').strip()
    params: list[tuple[str, str]] = [
        ('pagenr', str(page)),
        ('sort', '1'),
        ('locale', 'de'),
        ('currentPlatform', '1'),
        ('placeOfWorkMode', 'travel'),
        ('attachments', '0'),
        ('permanentJobs', '0'),
        ('employeeLeasingJobs', '0'),
        ('maxDailyRate', '0'),
        ('maxHourlyRate', '0'),
        ('profileUpdate', '0'),
        ('mostRecentProfiles', '0'),
        ('excludeDachRegion', '0'),
        ('excludeUnavailable', '1' if available_only else '0'),
        ('excludeMemolist', '0'),
        ('query', q),
    ]
    for i, cid in enumerate(countries):
        params.append((f'countries[{i}]', str(cid)))

    url = FM_SEARCH_AJAX + '?' + urllib.parse.urlencode(params)
    code, raw = _request(url)
    if code != 200 or not raw:
        return {
            'ok': False,
            'error': f'FM Suche HTTP {code}',
            'results': [],
            'http': code,
            'query': q,
        }
    try:
        data = json.loads(raw.decode('utf-8', errors='replace'))
    except Exception as exc:
        return {'ok': False, 'error': f'JSON: {exc}', 'results': [], 'query': q}

    freelancers = data.get('freelancers') if isinstance(data, dict) else None
    if not isinstance(freelancers, list):
        freelancers = []
    out = []
    for hit in freelancers:
        if not isinstance(hit, dict):
            continue
        n = normalize_freelancer(hit)
        if n.get('fm_id'):
            out.append(n)
    total = None
    try:
        total = int(data.get('count')) if isinstance(data, dict) and data.get('count') is not None else None
    except (TypeError, ValueError):
        total = None
    sess = fl_session_info()
    rates_n = sum(1 for r in out if r.get('satz') is not None)
    return {
        'ok': True,
        'results': out,
        'page': page,
        'query': q,
        'raw_count': len(freelancers),
        'total': total,
        'average_price': data.get('averagePrice') if isinstance(data, dict) else None,
        'http': code,
        'needs_auth': False,
        'fl_session': bool(sess.get('ok')),
        'fl_session_info': {
            'ok': sess.get('ok'),
            'source': sess.get('source'),
            'path': sess.get('path'),
            'cookie_names': sess.get('cookie_names') or [],
            'cookies_n': sess.get('cookies_n') or 0,
        },
        'rates_with_value': rates_n,
        'hint': (
            'Session gesetzt, aber keine Stundensätze in der Suche — '
            'Cookies ggf. abgelaufen oder kein Business-Account. '
            'Session neu exportieren (Extension → data/url/fl/.session_cookies.json).'
            if (sess.get('ok') and rates_n == 0 and out)
            else None
        ),
    }


def parse_fm_ref(text: str) -> dict[str, str]:
    """
    Extrahiert fm_slug / fm_id aus URL oder Freitext.
    Beispiele:
      https://www.freelancermap.de/profil/product-owner-205265
      product-owner-205265
      205265
    """
    s = (text or '').strip()
    if not s:
        return {}
    slug = ''
    fm_id = ''
    m = _RE_PROFIL_SLUG.search(s)
    if m:
        slug = m.group(1).strip().strip('/')
    elif re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9\-_]{2,120}', s) and not s.isdigit():
        # Bare slug (enthält typischerweise Bindestrich + ID)
        if '-' in s or not s.isdigit():
            slug = s.strip().strip('/')
    if slug:
        mid = _RE_SLUG_ID.search(slug)
        if mid:
            fm_id = mid.group(1)
    if not fm_id:
        m2 = re.fullmatch(r'(\d{4,8})', s)
        if m2:
            fm_id = m2.group(1)
        else:
            m3 = re.search(r'[?&]id=(\d{4,8})\b', s, re.I)
            if m3:
                fm_id = m3.group(1)
            else:
                m4 = re.search(r'\bFM[-\s]?ID\s*[:=]?\s*(\d{4,8})\b', s, re.I)
                if m4:
                    fm_id = m4.group(1)
    if not slug and not fm_id:
        return {}
    return {'fm_slug': slug, 'fm_id': fm_id}


def _profile_from_html(html: str) -> Optional[dict]:
    """ProfileShow-JSON aus Profil-HTML extrahieren."""
    if not html:
        return None
    m = _RE_PROFILE_SHOW.search(html)
    if not m:
        return None
    raw = (m.group(1) or '').strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    profile = data.get('profile') if isinstance(data.get('profile'), dict) else data
    if not isinstance(profile, dict):
        return None
    if not (profile.get('id') or profile.get('slug')):
        return None
    return profile


def _person_from_ldjson(html: str) -> dict[str, str]:
    """Optional echte Namen aus ld+json Person (bei Soft-Anonym)."""
    out: dict[str, str] = {}
    if not html:
        return out
    for m in _RE_LD_JSON.finditer(html):
        raw = (m.group(1) or '').strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        candidates = data if isinstance(data, list) else [data]
        for obj in candidates:
            if not isinstance(obj, dict):
                continue
            typ = obj.get('@type') or obj.get('type') or ''
            typ_s = typ if isinstance(typ, str) else (
                typ[0] if isinstance(typ, list) and typ else ''
            )
            if str(typ_s).lower() not in ('person',):
                continue
            given = str(obj.get('givenName') or '').strip()
            family = str(obj.get('familyName') or '').strip()
            name = str(obj.get('name') or '').strip()
            if given:
                out['first_name'] = given
            if family:
                out['last_name'] = family
            if name and (not given or not family):
                parts = name.split(None, 1)
                if parts and not given:
                    out['first_name'] = parts[0]
                if len(parts) > 1 and not family:
                    out['last_name'] = parts[1]
            if out:
                return out
    return out


def _merge_soft_anonym_names(profile: dict, html: str) -> dict:
    """Wenn user-Namen maskiert (anonymous/****) → ld+json Person mergen."""
    user = profile.get('user') if isinstance(profile.get('user'), dict) else {}
    first = str(user.get('firstName') or '').strip()
    last = str(user.get('lastName') or '').strip()
    if not _is_masked_name(first) and not _is_masked_name(last):
        return profile
    person = _person_from_ldjson(html)
    if not person:
        return profile
    # ld+json kann ebenfalls maskiert sein
    pf = person.get('first_name') or ''
    pl = person.get('last_name') or ''
    if _is_masked_name(pf) and _is_masked_name(pl):
        return profile
    user = dict(user)
    if _is_masked_name(first) and pf and not _is_masked_name(pf):
        user['firstName'] = pf
    if _is_masked_name(last) and pl and not _is_masked_name(pl):
        user['lastName'] = pl
    out = dict(profile)
    out['user'] = user
    return out


def _search_ajax(
    *,
    query: str = '',
    page: int = 1,
    available_only: bool = False,
    countries: Optional[list[int]] = None,
) -> dict[str, Any]:
    """Rohe Freelancer-Suche (Ajax) — für Enrich nach ID/Slug."""
    page = max(1, int(page or 1))
    countries = countries or [1, 2, 3]
    params: list[tuple[str, str]] = [
        ('pagenr', str(page)),
        ('sort', '1'),
        ('locale', 'de'),
        ('currentPlatform', '1'),
        ('placeOfWorkMode', 'travel'),
        ('attachments', '0'),
        ('permanentJobs', '0'),
        ('employeeLeasingJobs', '0'),
        ('maxDailyRate', '0'),
        ('maxHourlyRate', '0'),
        ('profileUpdate', '0'),
        ('mostRecentProfiles', '0'),
        ('excludeDachRegion', '0'),
        ('excludeUnavailable', '1' if available_only else '0'),
        ('excludeMemolist', '0'),
        ('query', query or ''),
    ]
    for i, cid in enumerate(countries):
        params.append((f'countries[{i}]', str(cid)))
    url = FM_SEARCH_AJAX + '?' + urllib.parse.urlencode(params)
    code, raw = _request(url)
    if code != 200 or not raw:
        return {'ok': False, 'http': code, 'freelancers': [], 'url': url}
    try:
        data = json.loads(raw.decode('utf-8', errors='replace'))
    except Exception as exc:
        return {'ok': False, 'http': code, 'error': str(exc), 'freelancers': [], 'url': url}
    freelancers = data.get('freelancers') if isinstance(data, dict) else []
    if not isinstance(freelancers, list):
        freelancers = []
    return {
        'ok': True,
        'http': code,
        'freelancers': freelancers,
        'url': url,
        'average_price': data.get('averagePrice') if isinstance(data, dict) else None,
    }


def _find_search_hit(*, fm_id: str = '', slug: str = '') -> Optional[dict]:
    """
    Business-Suche: Stundensätze stecken oft nur in Search-Ajax, nicht in ProfileShow.
    """
    fm_id = str(fm_id or '').strip()
    slug = (slug or '').strip().strip('/')
    queries: list[str] = []
    if fm_id:
        queries.append(fm_id)
    if slug:
        queries.append(slug)
        # Slug ohne trailing ID: product-owner-205265 → product owner
        base = _RE_SLUG_ID.sub('', slug).replace('-', ' ').strip()
        if base and base not in queries:
            queries.append(base)
    seen_q: set[str] = set()
    for q in queries:
        if not q or q in seen_q:
            continue
        seen_q.add(q)
        res = _search_ajax(query=q, page=1, available_only=False)
        if not res.get('ok'):
            continue
        for hit in res.get('freelancers') or []:
            if not isinstance(hit, dict):
                continue
            hid = str(hit.get('id') or '').strip()
            hslug = str(hit.get('slug') or '').strip()
            if (fm_id and hid == fm_id) or (slug and hslug == slug):
                return hit
    return None


def _enrich_item_from_search(item: dict[str, Any]) -> dict[str, Any]:
    """Satz/Namen aus Search-Ajax nachziehen (mit Session → Business-Raten)."""
    if not isinstance(item, dict):
        return item
    need_rate = item.get('satz') is None
    need_name = _is_masked_name(item.get('first_name') or '') and _is_masked_name(
        item.get('last_name') or ''
    )
    # Name nur Platzhalter/Titel ok — wenn first/last leer und name == title, trotzdem Search versuchen für Satz
    if not need_rate and not need_name:
        return item
    hit = _find_search_hit(fm_id=item.get('fm_id') or '', slug=item.get('fm_slug') or '')
    if not hit:
        return item
    enriched = normalize_freelancer(hit)
    out = dict(item)
    if need_rate and enriched.get('satz') is not None:
        out['satz'] = enriched['satz']
    if need_name:
        if enriched.get('first_name'):
            out['first_name'] = enriched['first_name']
        if enriched.get('last_name'):
            out['last_name'] = enriched['last_name']
        if enriched.get('name') and (
            _is_masked_name(out.get('name') or '')
            or (out.get('name') or '').startswith('FM ')
            or out.get('name') == out.get('title')
        ):
            # echte Namen bevorzugen, sonst Search-Display behalten wenn besser
            if enriched.get('first_name') or enriched.get('last_name'):
                out['name'] = enriched['name']
            elif enriched.get('name') and not _is_masked_name(enriched['name']):
                out['name'] = enriched['name']
    if enriched.get('skills') and not out.get('skills'):
        out['skills'] = enriched['skills']
    out['_enriched_from_search'] = True
    return out


def fetch_profile(
    *,
    slug: str = '',
    fm_id: str = '',
) -> dict[str, Any]:
    """
    Profilseite laden + ProfileShow parsen → normalize_freelancer.
    Stundensätze: oft nur in Search-Ajax mit Business-Session → Enrich.
    """
    slug = (slug or '').strip().strip('/')
    fm_id = str(fm_id or '').strip()
    if not slug and not fm_id:
        return {'ok': False, 'error': 'slug oder fm_id erforderlich'}

    urls: list[str] = []
    if slug:
        urls.append(profil_url_for(slug=slug, fm_id=fm_id))
    if fm_id:
        urls.append(f'{FM_BASE}/freelancer?id={urllib.parse.quote(fm_id)}')
        if not slug:
            urls.append(f'{FM_BASE}/profil/{urllib.parse.quote(fm_id)}')

    last_err = ''
    last_http = 0
    for url in urls:
        code, raw = _request(
            url,
            accept='text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            timeout=45,
        )
        last_http = code
        if code != 200 or not raw:
            last_err = f'HTTP {code} für {url}'
            continue
        html = raw.decode('utf-8', errors='replace')
        profile = _profile_from_html(html)
        if not profile:
            last_err = f'Kein ProfileShow in {url}'
            continue
        profile = _merge_soft_anonym_names(profile, html)
        item = normalize_freelancer(profile)
        if not item.get('fm_id') and fm_id:
            item['fm_id'] = fm_id
        if not item.get('fm_slug') and slug:
            item['fm_slug'] = slug
        item = _enrich_item_from_search(item)
        return {
            'ok': True,
            'item': item,
            'http': code,
            'url': url,
            'fl_session': has_fl_session(),
            'needs_auth': False,
            'enriched_from_search': bool(item.get('_enriched_from_search')),
        }

    # Fallback: gezielte Query-Suche nach ID/Slug
    hit = _find_search_hit(fm_id=fm_id, slug=slug)
    if hit:
        item = normalize_freelancer(hit)
        return {
            'ok': True,
            'item': item,
            'http': 200,
            'url': 'search/ajax',
            'fl_session': has_fl_session(),
            'from_search': True,
        }

    return {
        'ok': False,
        'error': last_err or 'Profil nicht gefunden',
        'http': last_http,
        'fl_session': has_fl_session(),
        'needs_auth': (last_http in (401, 403)) and not has_fl_session(),
    }


def fetch_profile_by_text(text: str) -> dict[str, Any]:
    """Paste-Helfer: URL/Slug/ID → fetch_profile."""
    ref = parse_fm_ref(text)
    if not ref:
        return {'ok': False, 'error': 'Keine Freelancermap-URL/ID erkannt'}
    return fetch_profile(slug=ref.get('fm_slug') or '', fm_id=ref.get('fm_id') or '')
