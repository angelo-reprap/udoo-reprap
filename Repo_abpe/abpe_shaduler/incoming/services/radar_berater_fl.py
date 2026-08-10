"""
Freelancermap — Radar Berater (Phase 1).

Öffentliche Suche (kein Login nötig für Liste):
  GET /freelancer/search/ajax?…&excludeUnavailable=1

Profil-URL: https://www.freelancermap.de/profil/{slug}
CRM: freelancermap_profil_c / freelancermap_last_updated_c

cv_extractor bleibt unverändert (Logik hier nachgebaut, nicht importiert).
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


def _request(
    url: str,
    *,
    headers: Optional[dict] = None,
    timeout: int = 30,
) -> tuple[int, bytes]:
    h = {
        'User-Agent': UA,
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'de-DE,de;q=0.9',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': FM_LIST,
    }
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
            return int(resp.status), resp.read(1_500_000)
    except urllib.error.HTTPError as e:
        body = e.read(80_000) if e.fp else b''
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
    for k in ('hourlyRate', 'hourRate', 'rate', 'price', 'amount', 'stundensatz'):
        v = pay.get(k)
        if v is None or v == '':
            continue
        try:
            return float(str(v).replace(',', '.'))
        except (TypeError, ValueError):
            continue
    return None


def normalize_freelancer(raw: dict) -> dict[str, Any]:
    """FM Freelancer-JSON → Radar-Dict."""
    if not isinstance(raw, dict):
        return {}
    fm_id = str(raw.get('id') or '').strip()
    slug = str(raw.get('slug') or '').strip()
    user = raw.get('user') if isinstance(raw.get('user'), dict) else {}
    first = str(user.get('firstName') or '').strip()
    last = str(user.get('lastName') or '').strip()
    if first.lower() == 'anonymous':
        first = ''
    if last.lower() == 'anonymous':
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

    satz = _rate_from_payment(raw.get('paymentInformation'))

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
) -> dict[str, Any]:
    """
    FM Freelancer-Suche (öffentlich).
    page: 1-basiert (pagenr).
    """
    page = max(1, int(page or 1))
    countries = countries or [1, 2, 3]  # DE, AT, CH
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
        ('query', ''),
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
        }
    try:
        data = json.loads(raw.decode('utf-8', errors='replace'))
    except Exception as exc:
        return {'ok': False, 'error': f'JSON: {exc}', 'results': []}

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
    return {
        'ok': True,
        'results': out,
        'page': page,
        'raw_count': len(freelancers),
        'total': total,
        'average_price': data.get('averagePrice') if isinstance(data, dict) else None,
        'http': code,
        'needs_auth': False,
    }


def has_fl_session() -> bool:
    """Liste ist öffentlich — immer True (Session optional später für Sätze/Namen)."""
    return True
