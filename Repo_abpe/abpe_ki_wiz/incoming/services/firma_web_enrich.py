"""
Firma aus öffentlicher Website anreichern (on-demand).

Ablauf: Firmenname → Suche Homepage → Impressum/Kontakt laden →
Regex + DeepSeek JSON → Vorschlag für CRM (UI bestätigt).
"""
from __future__ import annotations

import html as html_lib
import json
import logging
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from apps.abpe_ki_wiz.services.deepseek_client import call_wizard_prompt
from apps.abpe_ki_wiz.services.prompt_loader import get_prompt_by_key

log = logging.getLogger('abpe_ki_wiz.firma_web')

PROMPT_KEY = 'wiz_firma_web_enrich'

UA = (
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 ABpE-FirmaWeb/1.0'
)
TIMEOUT = 18
CTX = ssl.create_default_context()

SKIP_HOSTS = {
    'duckduckgo.com', 'google.com', 'google.de', 'bing.com', 'yahoo.com',
    'wikipedia.org', 'linkedin.com', 'facebook.com', 'xing.com',
    'northdata.de', 'northdata.com', 'firmenwissen.de', 'creditreform.de',
    'kununu.com', 'glassdoor.com', 'yelp.com', 'maps.google.com',
    'instagram.com', 'twitter.com', 'x.com', 'youtube.com',
    'handelsregister.de', 'unternehmensregister.de', 'gelbe-seiten.de',
}

EMAIL_RE = re.compile(r'\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b', re.I)
PHONE_RE = re.compile(
    r'(?:\+49[\s\-./()]*\d{1,5}(?:[\s\-./()]*\d{2,}){1,5}'
    r'|\b0\d{2,5}[\s\-./]*\d{3,12}\b)'
)
ADDR_RE = re.compile(
    r'([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\- ]{2,50}(?:straße|strasse|str\.|weg|platz|allee|ring|'
    r'gasse|brücke|bruecke|damm|ufer|chaussee|hof|markt|promenade)'
    r'\s*\d{1,4}[a-zA-Z]?)\s*[,\n ]*\s*(\d{5})\s+([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\- ]{2,40})',
    re.I,
)


def _fetch(url: str, max_bytes: int = 700_000) -> tuple[int, str, str]:
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': UA,
            'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
        },
        method='GET',
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=CTX) as resp:
            raw = resp.read(max_bytes)
            final = resp.geturl()
            ctype = (resp.headers.get('Content-Type') or '').lower()
            charset = 'utf-8'
            m = re.search(r'charset=([\w-]+)', ctype)
            if m:
                charset = m.group(1)
            try:
                text = raw.decode(charset, errors='replace')
            except LookupError:
                text = raw.decode('utf-8', errors='replace')
            return int(resp.status), final, text
    except urllib.error.HTTPError as e:
        body = e.read(40_000).decode('utf-8', errors='replace') if e.fp else ''
        return int(e.code), url, body
    except Exception as exc:
        return 0, url, f'ERROR: {exc}'


def _strip_html(html: str) -> str:
    s = re.sub(r'(?is)<(script|style|noscript|svg|iframe)[^>]*>.*?</\1>', ' ', html)
    s = re.sub(r'(?is)<!--.*?-->', ' ', s)
    s = re.sub(r'(?is)<br\s*/?>', '\n', s)
    s = re.sub(r'(?is)</(p|div|li|tr|h[1-6])>', '\n', s)
    s = re.sub(r'(?is)<[^>]+>', ' ', s)
    s = html_lib.unescape(s)
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()


def _regex_extract(text: str) -> dict[str, list[str]]:
    emails: list[str] = []
    for e in EMAIL_RE.findall(text or ''):
        el = e.lower()
        if any(x in el for x in ('example.com', 'sentry', 'wixpress', 'domain.com', 'email.com', 'wght@')):
            continue
        if el not in emails:
            emails.append(el)
    phones: list[str] = []
    for p in PHONE_RE.findall(text or ''):
        cleaned = re.sub(r'\s+', ' ', p.strip())
        digits = re.sub(r'\D', '', cleaned)
        if cleaned not in phones and len(digits) >= 8 and not digits.startswith('000'):
            phones.append(cleaned)
    addrs: list[str] = []
    for m in ADDR_RE.finditer(text or ''):
        line = f'{m.group(1).strip()}, {m.group(2)} {m.group(3).strip()}'
        if line not in addrs:
            addrs.append(line)
    return {'emails': emails[:8], 'phones': phones[:8], 'addresses': addrs[:5]}


def _ddg_search(query: str, n: int = 8) -> list[dict[str, str]]:
    url = 'https://html.duckduckgo.com/html/?' + urllib.parse.urlencode({'q': query})
    code, _final, body = _fetch(url)
    if code >= 400 and code != 0:
        return []
    out: list[dict[str, str]] = []
    for m in re.finditer(
        r'(?is)<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        body,
    ):
        href = html_lib.unescape(m.group(1))
        title = _strip_html(m.group(2))
        if 'uddg=' in href:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            href = urllib.parse.unquote(qs.get('uddg', [href])[0])
        if href.startswith('//'):
            href = 'https:' + href
        if not href.startswith('http'):
            continue
        host = urllib.parse.urlparse(href).netloc.lower().removeprefix('www.')
        if any(host == s or host.endswith('.' + s) for s in SKIP_HOSTS):
            continue
        out.append({'title': title[:120], 'url': href, 'host': host})
        if len(out) >= n:
            break
    return out


def _pick_homepage(company: str, hits: list[dict[str, str]]) -> Optional[str]:
    if not hits:
        return None
    name_toks = [
        t.lower() for t in re.findall(r'[A-Za-z0-9ÄÖÜäöüß]{3,}', company)
        if t.lower() not in {
            'gmbh', 'ltd', 'inc', 'corp', 'co', 'kg', 'ug', 'ag', 'se',
            'deutschland', 'germany', 'and', 'the',
        }
    ]
    scored: list[tuple[int, str]] = []
    for h in hits:
        url = h['url']
        host = h['host']
        score = 0
        path = urllib.parse.urlparse(url).path.lower()
        host_flat = host.replace('-', '').replace('.', '')
        for t in name_toks:
            if t in host_flat:
                score += 5
            elif t in host:
                score += 3
        if path in ('', '/', '/de', '/de/', '/de-de', '/de-de/', '/en', '/en/'):
            score += 2
        if any(x in path for x in ('impressum', 'imprint', 'kontakt', 'contact', 'uber', 'about')):
            score -= 1
        score -= max(0, host.count('.') - 1)
        scored.append((score, url))
    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored else None


def _discover_info_urls(home_url: str, html: str) -> list[str]:
    found = {home_url}
    for m in re.finditer(r'(?is)<a[^>]+href=["\']([^"\']+)["\']', html):
        href = html_lib.unescape(m.group(1)).strip()
        if not href or href.startswith(('#', 'mailto:', 'tel:', 'javascript:')):
            continue
        full = urllib.parse.urljoin(home_url, href).split('#')[0]
        low = full.lower()
        if any(k in low for k in (
            'impressum', 'imprint', 'legal-notice', 'legal_notice',
            'kontakt', 'contact', 'uber-uns', 'ueber-uns', 'about',
            'unternehmen', 'company',
        )):
            found.add(full)
    parsed = urllib.parse.urlparse(home_url)
    roots = [f'{parsed.scheme}://{parsed.netloc}']
    parts = [p for p in parsed.path.split('/') if p]
    if parts and parts[0] in ('de', 'en', 'de-de', 'en-us'):
        roots.append(f'{parsed.scheme}://{parsed.netloc}/{parts[0]}')
    for root in roots:
        for path in (
            '/impressum/', '/imprint/', '/kontakt/', '/contact/',
            '/uber-uns/', '/ueber-uns/', '/about/', '/de/impressum/', '/de/kontakt/',
        ):
            found.add(urllib.parse.urljoin(root + '/', path.lstrip('/')))
    others = sorted(
        (u for u in found if u.rstrip('/') != home_url.rstrip('/')),
        key=lambda u: (
            0 if 'impressum' in u.lower() or 'imprint' in u.lower() else
            1 if any(x in u.lower() for x in ('kontakt', 'contact')) else
            2 if any(x in u.lower() for x in ('uber', 'about', 'unternehmen')) else 3,
            len(u),
        ),
    )
    # dedupe by normalized URL
    seen: set[str] = set()
    ordered = [home_url]
    for u in others:
        key = u.rstrip('/').lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(u)
        if len(ordered) >= 6:
            break
    return ordered


def _parse_ai_json(text: str) -> dict[str, Any]:
    s = (text or '').strip()
    if s.startswith('```'):
        s = re.sub(r'^```(?:json)?\s*', '', s)
        s = re.sub(r'\s*```$', '', s)
    return json.loads(s)


def _merge_regex_into_ki(ki: dict[str, Any], merged: dict[str, list[str]]) -> dict[str, Any]:
    if not isinstance(ki, dict):
        return ki
    if not ki.get('emails') and merged.get('emails'):
        ki['emails'] = list(merged['emails'])
    if not ki.get('phones') and merged.get('phones'):
        ki['phones'] = list(merged['phones'])
    if (not ki.get('street') or not ki.get('city')) and merged.get('addresses'):
        m = re.match(r'^(.+?),\s*(\d{5})\s+(.+)$', merged['addresses'][0])
        if m:
            if not ki.get('street'):
                ki['street'] = m.group(1)
            if not ki.get('zip'):
                ki['zip'] = m.group(2)
            if not ki.get('city'):
                ki['city'] = m.group(3)
    return ki


def enrich_firma_from_web(
    company_name: str,
    *,
    homepage_url: str = '',
) -> dict[str, Any]:
    """
    On-demand Firmen-Anreicherung.
    Returns { success, company, enrich, pages, regex, seconds, error? }
    """
    t0 = time.time()
    name = (company_name or '').strip()
    if len(name) < 2:
        return {'success': False, 'error': 'Firmenname fehlt'}

    home = (homepage_url or '').strip()
    search_hits: list[dict[str, str]] = []
    if not home:
        search_hits = _ddg_search(f'{name} offizielle website', n=10)
        home = _pick_homepage(name, search_hits) or ''
        if not home:
            search_hits = _ddg_search(name, n=10)
            home = _pick_homepage(name, search_hits) or ''
    if not home:
        return {
            'success': False,
            'error': 'Keine Homepage gefunden — bitte URL manuell angeben',
            'search_hits': search_hits[:5],
            'seconds': round(time.time() - t0, 1),
        }

    code, final_home, home_html = _fetch(home)
    if code not in (200, 203) or not home_html or home_html.startswith('ERROR:'):
        return {
            'success': False,
            'error': f'Homepage nicht ladbar (HTTP {code})',
            'homepage': home,
            'search_hits': search_hits[:5],
            'seconds': round(time.time() - t0, 1),
        }

    info_urls = _discover_info_urls(final_home, home_html)
    pages: list[dict[str, Any]] = []
    seen: set[str] = set()
    for u in info_urls:
        key = u.rstrip('/').lower()
        if key in seen:
            continue
        seen.add(key)
        c, fu, html = _fetch(u)
        if c not in (200, 203) or not html or html.startswith('ERROR:'):
            continue
        text = _strip_html(html)
        if len(text) < 40 and len(html) < 500:
            continue
        rx = _regex_extract(text + '\n' + html)
        pages.append({
            'url': fu,
            'chars': len(text),
            'text': (text if len(text) >= 80 else html)[:16000],
            'regex': rx,
        })
        if len(pages) >= 4:
            break

    if not any(p['url'].rstrip('/') == final_home.rstrip('/') for p in pages):
        home_text = _strip_html(home_html)
        pages.insert(0, {
            'url': final_home,
            'chars': len(home_text),
            'text': (home_text if len(home_text) >= 80 else home_html)[:16000],
            'regex': _regex_extract(home_text + '\n' + home_html),
        })

    merged = {'emails': [], 'phones': [], 'addresses': []}
    for p in pages:
        for k in merged:
            for v in (p.get('regex') or {}).get(k) or []:
                if v not in merged[k]:
                    merged[k].append(v)

    prompt = get_prompt_by_key(PROMPT_KEY)
    if not prompt:
        enrich = {
            'website': final_home,
            'legal_name': name,
            'street': None,
            'zip': None,
            'city': None,
            'country': 'Deutschland' if merged.get('addresses') else None,
            'emails': merged.get('emails') or [],
            'phones': merged.get('phones') or [],
            'contacts': [],
            'summary_de': None,
            'sources': [p['url'] for p in pages],
            'source': 'regex_only',
        }
        if merged.get('addresses'):
            m = re.match(r'^(.+?),\s*(\d{5})\s+(.+)$', merged['addresses'][0])
            if m:
                enrich['street'], enrich['zip'], enrich['city'] = m.group(1), m.group(2), m.group(3)
        return {
            'success': True,
            'company': name,
            'homepage': final_home,
            'search_hits': search_hits[:5],
            'pages': [{'url': p['url'], 'chars': p['chars']} for p in pages],
            'regex': merged,
            'enrich': enrich,
            'warning': f'Prompt „{PROMPT_KEY}“ fehlt in DB — nur Regex',
            'seconds': round(time.time() - t0, 1),
        }

    chunks = []
    for p in pages:
        chunks.append(f"### URL: {p['url']}\n{(p.get('text') or '')[:10000]}")
    blob = '\n\n'.join(chunks)[:32000]
    briefing = (
        f'Firma: {name}\n'
        f'Homepage: {final_home}\n'
        f'Regex-Hinweis: {json.dumps(merged, ensure_ascii=False)}\n\n'
        f'SEITENTEXT:\n{blob}'
    )
    ds = call_wizard_prompt(prompt, briefing=briefing)
    enrich: dict[str, Any]
    if not ds.success or not ds.text:
        enrich = {
            'website': final_home,
            'legal_name': name,
            'street': None,
            'zip': None,
            'city': None,
            'country': None,
            'emails': merged.get('emails') or [],
            'phones': merged.get('phones') or [],
            'contacts': [],
            'summary_de': None,
            'sources': [p['url'] for p in pages],
            'source': 'regex_fallback',
            'deepseek_error': ds.error or 'kein Text',
        }
        if merged.get('addresses'):
            m = re.match(r'^(.+?),\s*(\d{5})\s+(.+)$', merged['addresses'][0])
            if m:
                enrich['street'], enrich['zip'], enrich['city'] = m.group(1), m.group(2), m.group(3)
    else:
        try:
            enrich = _parse_ai_json(ds.text)
        except Exception as exc:
            log.warning('firma enrich JSON parse failed: %s', exc)
            enrich = {
                'website': final_home,
                'legal_name': name,
                'emails': merged.get('emails') or [],
                'phones': merged.get('phones') or [],
                'contacts': [],
                'summary_de': None,
                'sources': [p['url'] for p in pages],
                'source': 'parse_error',
                'raw': (ds.text or '')[:1500],
            }
        enrich = _merge_regex_into_ki(enrich, merged)
        if not enrich.get('website'):
            enrich['website'] = final_home
        enrich['source'] = enrich.get('source') or 'deepseek'

    ok = bool(
        enrich.get('emails')
        or enrich.get('phones')
        or enrich.get('street')
        or enrich.get('summary_de')
        or enrich.get('website')
    )
    return {
        'success': ok,
        'company': name,
        'homepage': final_home,
        'search_hits': search_hits[:5],
        'pages': [{'url': p['url'], 'chars': p['chars']} for p in pages],
        'regex': merged,
        'enrich': enrich,
        'seconds': round(time.time() - t0, 1),
        'error': None if ok else 'Keine Kontaktdaten gefunden',
    }
