#!/usr/bin/env python3
"""
Probe: Firmenname → Homepage → Impressum/About → Kontaktfelder (Regex + optional DeepSeek).

Usage:
  python3 scripts/PROBE-firma-web-enrich.py
  DEEPSEEK_API_KEY=sk-... python3 scripts/PROBE-firma-web-enrich.py
  # oder mit /opt/abpe/backend/settings.json (ucs5)
"""
from __future__ import annotations

import html as html_lib
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = (
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 ABpE-Probe/1.0'
)
TIMEOUT = 20
CTX = ssl.create_default_context()

COMPANIES = [
    'ACT DIGITAL Deutschland GmbH',
    'Moodwear',
    'C4 Energy GmbH & Co. KG',
]

SKIP_HOSTS = {
    'duckduckgo.com', 'google.com', 'google.de', 'bing.com', 'yahoo.com',
    'wikipedia.org', 'linkedin.com', 'facebook.com', 'xing.com',
    'northdata.de', 'northdata.com', 'firmenwissen.de', 'creditreform.de',
    'kununu.com', 'glassdoor.com', 'yelp.com', 'maps.google.com',
    'instagram.com', 'twitter.com', 'x.com', 'youtube.com',
    'handelsregister.de', 'unternehmensregister.de', 'gelbe-seiten.de',
}


def fetch(url: str, max_bytes: int = 800_000) -> tuple[int, str, str]:
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
            return resp.status, final, text
    except urllib.error.HTTPError as e:
        body = e.read(50_000).decode('utf-8', errors='replace') if e.fp else ''
        return e.code, url, body
    except Exception as e:
        return 0, url, f'ERROR: {e}'


def strip_html(html: str) -> str:
    s = re.sub(r'(?is)<(script|style|noscript|svg|iframe)[^>]*>.*?</\1>', ' ', html)
    s = re.sub(r'(?is)<!--.*?-->', ' ', s)
    s = re.sub(r'(?is)<br\s*/?>', '\n', s)
    s = re.sub(r'(?is)</p>', '\n', s)
    s = re.sub(r'(?is)</div>', '\n', s)
    s = re.sub(r'(?is)</li>', '\n', s)
    s = re.sub(r'(?is)<[^>]+>', ' ', s)
    s = html_lib.unescape(s)
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()


def ddg_search(query: str, n: int = 8) -> list[dict]:
    url = 'https://html.duckduckgo.com/html/?' + urllib.parse.urlencode({'q': query})
    code, final, body = fetch(url)
    if code not in (200, 0) and code >= 400:
        return [{'error': f'DDG HTTP {code}', 'url': final}]
    out = []
    for m in re.finditer(
        r'(?is)<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        body,
    ):
        href = html_lib.unescape(m.group(1))
        title = strip_html(m.group(2))
        # DDG redirect: /l/?uddg=<url>
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


def pick_homepage(company: str, hits: list[dict]) -> str | None:
    if not hits or hits[0].get('error'):
        return None
    # Prefer shorter corporate domains, German path if present
    scored = []
    name_toks = [t.lower() for t in re.findall(r'[A-Za-z0-9ÄÖÜäöüß]{3,}', company) if t.lower() not in {
        'gmbh', 'ltd', 'inc', 'co', 'kg', 'ug', 'ag', 'se', 'deutschland', 'germany', 'and', 'the',
    }]
    for h in hits:
        url = h['url']
        host = h['host']
        score = 0
        path = urllib.parse.urlparse(url).path.lower()
        for t in name_toks:
            if t in host.replace('-', '').replace('.', ''):
                score += 5
            if t in host:
                score += 3
        if path in ('', '/', '/de', '/de/', '/de-de', '/de-de/', '/en', '/en/'):
            score += 2
        if any(x in path for x in ('impressum', 'imprint', 'kontakt', 'contact', 'uber', 'about')):
            score -= 1  # prefer homepage root later crawl
        # shorter host = often better
        score -= max(0, host.count('.') - 1)
        scored.append((score, url))
    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored else None


def discover_info_urls(home_url: str, html: str) -> list[str]:
    base = urllib.parse.urljoin(home_url, '/')
    found = {home_url}
    # Absolute + relative links
    for m in re.finditer(r'(?is)<a[^>]+href=["\']([^"\']+)["\']', html):
        href = html_lib.unescape(m.group(1)).strip()
        if not href or href.startswith(('#', 'mailto:', 'tel:', 'javascript:')):
            continue
        full = urllib.parse.urljoin(home_url, href)
        low = full.lower()
        if any(k in low for k in (
            'impressum', 'imprint', 'legal-notice', 'legal_notice',
            'kontakt', 'contact', 'uber-uns', 'ueber-uns', 'about',
            'unternehmen', 'company', 'datenschutz',  # datenschutz often has company addr too
        )):
            # skip pure privacy if we have impressum — keep both for now, limit later
            found.add(full.split('#')[0])
    # Heuristic paths relative to site root / locale
    parsed = urllib.parse.urlparse(home_url)
    roots = [f'{parsed.scheme}://{parsed.netloc}']
    # if /de/ in path, also try under that
    parts = [p for p in parsed.path.split('/') if p]
    if parts and parts[0] in ('de', 'en', 'de-de', 'en-us'):
        roots.append(f'{parsed.scheme}://{parsed.netloc}/{parts[0]}')
    for root in roots:
        for path in (
            '/impressum', '/impressum/', '/imprint', '/imprint/',
            '/kontakt', '/kontakt/', '/contact', '/contact/',
            '/uber-uns', '/ueber-uns', '/uber', '/about', '/about-us',
            '/de/impressum/', '/de/uber/', '/de/ueber-uns/', '/de/kontakt/',
        ):
            found.add(urllib.parse.urljoin(root + '/', path.lstrip('/')))
    # Prefer impressum first, but Homepage immer behalten
    ordered = sorted(
        (u for u in found if u.rstrip('/') != home_url.rstrip('/') and u != home_url),
        key=lambda u: (
            0 if 'impressum' in u.lower() or 'imprint' in u.lower() else
            1 if any(x in u.lower() for x in ('kontakt', 'contact')) else
            2 if any(x in u.lower() for x in ('uber', 'about', 'unternehmen')) else 3,
            len(u),
        ),
    )
    return [home_url] + ordered[:7]


EMAIL_RE = re.compile(r'\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b', re.I)
PHONE_RE = re.compile(
    r'(?:\+49[\s\-./()]*\d{1,5}(?:[\s\-./()]*\d{2,}){1,5}'
    r'|\b0\d{2,5}[\s\-./]*\d{3,12}\b)'
)
# DE street + PLZ city (inkl. Brücke, Damm, Ufer, Chaussee …)
ADDR_RE = re.compile(
    r'([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\- ]{2,50}(?:straße|strasse|str\.|weg|platz|allee|ring|'
    r'gasse|brücke|bruecke|damm|ufer|chaussee|hof|markt|promenade)'
    r'\s*\d{1,4}[a-zA-Z]?)\s*[,\n ]*\s*(\d{5})\s+([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\- ]{2,40})',
    re.I,
)


def regex_extract(text: str) -> dict:
    emails = []
    for e in EMAIL_RE.findall(text):
        el = e.lower()
        if any(x in el for x in ('example.com', 'sentry', 'wixpress', 'domain.com', 'email.com')):
            continue
        if el not in emails:
            emails.append(el)
    phones = []
    for p in PHONE_RE.findall(text):
        cleaned = re.sub(r'\s+', ' ', p.strip())
        digits = re.sub(r'\D', '', cleaned)
        if cleaned not in phones and len(digits) >= 8 and not digits.startswith('000'):
            phones.append(cleaned)
    addrs = []
    for m in ADDR_RE.finditer(text):
        line = f'{m.group(1).strip()}, {m.group(2)} {m.group(3).strip()}'
        if line not in addrs:
            addrs.append(line)
    return {
        'emails': emails[:8],
        'phones': phones[:8],
        'addresses': addrs[:5],
    }


def load_deepseek_key() -> tuple[str, str]:
    key = os.environ.get('DEEPSEEK_API_KEY') or ''
    model = os.environ.get('DEEPSEEK_MODEL') or 'deepseek-chat'
    cfg_path = Path(os.environ.get('ABPE_SETTINGS') or '/opt/abpe/backend/settings.json')
    if cfg_path.is_file():
        try:
            cfg = json.loads(cfg_path.read_text())
            ds = (cfg.get('ai_models') or {}).get('deepseek') or cfg.get('deepseek') or {}
            key = key or ds.get('api_key') or ''
            model = ds.get('model') or model
        except Exception:
            pass
    return key, model


def deepseek_extract(company: str, pages: list[dict], api_key: str, model: str) -> dict | None:
    chunks = []
    for p in pages:
        if p.get('text'):
            chunks.append(f"### URL: {p['url']}\n{p['text'][:12000]}")
    blob = '\n\n'.join(chunks)[:35000]
    if not blob.strip():
        return None
    system = (
        'Du extrahierst Firmenstammdaten aus öffentlichen Webseiten (Impressum/About/Kontakt). '
        'Antworte NUR mit JSON. Keine Halluzinationen — nur was im Text steht. '
        'Unbekannt = null oder [].'
    )
    user = (
        f'Firma: {company}\n\n'
        'Extrahiere:\n'
        '{\n'
        '  "website": "kanonische Homepage URL oder null",\n'
        '  "legal_name": "offizieller Name oder null",\n'
        '  "street": null,\n'
        '  "zip": null,\n'
        '  "city": null,\n'
        '  "country": null,\n'
        '  "emails": [],\n'
        '  "phones": [],\n'
        '  "contacts": [{"name": "", "role": "", "email": null, "phone": null}],\n'
        '  "summary_de": "2-4 Sätze Firmennotiz auf Deutsch oder null",\n'
        '  "sources": ["URLs die genutzt wurden"]\n'
        '}\n\n'
        f'SEITENTEXT:\n{blob}'
    )
    body = json.dumps({
        'model': model,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user},
        ],
        'temperature': 0.1,
        'max_tokens': 1200,
        'response_format': {'type': 'json_object'},
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://api.deepseek.com/v1/chat/completions',
        data=body,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'User-Agent': UA,
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=90, context=CTX) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        content = data['choices'][0]['message']['content']
        return json.loads(content)
    except Exception as e:
        return {'error': str(e)}


def enrich_company(company: str, api_key: str, model: str) -> dict:
    t0 = time.time()
    result: dict = {'company': company, 'ok': False}
    hits = ddg_search(f'{company} offizielle website', n=10)
    result['search_hits'] = hits[:5]
    home = pick_homepage(company, [h for h in hits if 'url' in h])
    # fallback query
    if not home:
        hits2 = ddg_search(company, n=10)
        result['search_hits_2'] = hits2[:5]
        home = pick_homepage(company, [h for h in hits2 if 'url' in h])
    result['homepage_guess'] = home
    if not home:
        result['error'] = 'keine Homepage gefunden'
        result['seconds'] = round(time.time() - t0, 1)
        return result

    code, final_home, home_html = fetch(home)
    result['homepage_final'] = final_home
    result['homepage_status'] = code
    if code not in (200, 203) or not home_html or home_html.startswith('ERROR:'):
        result['error'] = f'Homepage nicht ladbar ({code})'
        result['seconds'] = round(time.time() - t0, 1)
        return result

    info_urls = discover_info_urls(final_home, home_html)
    result['candidate_urls'] = info_urls
    pages = []
    seen = set()
    for u in info_urls:
        if u in seen:
            continue
        seen.add(u)
        c, fu, html = fetch(u)
        if c not in (200, 203) or not html or html.startswith('ERROR:'):
            continue
        # Kontaktdaten oft in JS/JSON — Regex auf Roh-HTML + Klartext
        text = strip_html(html)
        if len(text) < 40 and len(html) < 500:
            continue
        rx = regex_extract(text + '\n' + html)
        pages.append({
            'url': fu,
            'status': c,
            'chars': len(text),
            'text': text if len(text) >= 80 else strip_html(re.sub(r'(?is)<script[^>]*>', '<script>', html))[:20000],
            'regex': rx,
        })
        if len(pages) >= 4:
            break

    # always include homepage text snippet
    home_text = strip_html(home_html)
    home_rx = regex_extract(home_text + '\n' + home_html)
    if not any(p['url'] == final_home for p in pages):
        pages.insert(0, {
            'url': final_home,
            'status': code,
            'chars': len(home_text),
            'text': (home_text if len(home_text) >= 80 else home_html)[:20000],
            'regex': home_rx,
        })
    elif pages:
        # merge homepage regex into first page if same URL
        pass

    # Prefer pages that actually have contact signals
    pages.sort(key=lambda p: -(
        len(p['regex'].get('emails') or []) * 3
        + len(p['regex'].get('phones') or []) * 2
        + len(p['regex'].get('addresses') or []) * 3
    ))

    # merge regex
    merged = {'emails': [], 'phones': [], 'addresses': []}
    for p in pages:
        for k in merged:
            for v in p['regex'].get(k) or []:
                if v not in merged[k]:
                    merged[k].append(v)

    result['pages_used'] = [{'url': p['url'], 'chars': p['chars'], 'regex': p['regex']} for p in pages]
    result['regex_merged'] = merged

    if api_key:
        ki = deepseek_extract(company, pages, api_key, model)
        result['deepseek'] = ki
        result['deepseek_used'] = True
    else:
        result['deepseek_used'] = False
        result['deepseek'] = None

    result['ok'] = bool(merged['emails'] or merged['phones'] or merged['addresses'] or result.get('deepseek'))
    result['seconds'] = round(time.time() - t0, 1)
    return result


def main() -> int:
    api_key, model = load_deepseek_key()
    print(f'DeepSeek: {"JA (" + model + ")" if api_key else "NEIN (nur Regex)"}')
    print('=' * 72)
    all_out = []
    for name in COMPANIES:
        print(f'\n### {name}')
        r = enrich_company(name, api_key, model)
        all_out.append(r)
        print(f'  Homepage: {r.get("homepage_final") or r.get("homepage_guess")}  [{r.get("homepage_status")}]')
        print(f'  Seiten:   {len(r.get("pages_used") or [])}  ({r.get("seconds")}s)')
        m = r.get('regex_merged') or {}
        print(f'  Regex E-Mail:  {m.get("emails")}')
        print(f'  Regex Tel:     {m.get("phones")}')
        print(f'  Regex Adresse: {m.get("addresses")}')
        if r.get('deepseek_used'):
            ds = r.get('deepseek')
            print(f'  DeepSeek: {json.dumps(ds, ensure_ascii=False, indent=2)[:1200]}')
        if r.get('error'):
            print(f'  ERROR: {r["error"]}')
        # show top search hits briefly
        for h in (r.get('search_hits') or [])[:3]:
            if 'url' in h:
                print(f'  hit: {h.get("title", "")[:50]} → {h["url"]}')

    out_path = Path('/tmp/cursor/artifacts/firma-web-enrich-probe.json')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(all_out, ensure_ascii=False, indent=2))
    print('\n' + '=' * 72)
    print(f'JSON: {out_path}')
    ok_n = sum(1 for r in all_out if r.get('ok'))
    print(f'OK: {ok_n}/{len(all_out)}')
    return 0 if ok_n == len(all_out) else 1


if __name__ == '__main__':
    sys.exit(main())
