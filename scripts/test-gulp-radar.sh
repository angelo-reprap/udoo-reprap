#!/usr/bin/env bash
# Gulp-Radar-Test auf ucs5 (ohne Django, nur HTTP).
#
#   bash scripts/test-gulp-radar.sh
#   bash scripts/test-gulp-radar.sh --days 3
set -euo pipefail

DAYS="${1:-2}"
if [[ "${1:-}" == "--days" ]]; then
  DAYS="${2:-2}"
fi

python3 - <<PY
import json, ssl
from collections import Counter
from datetime import date, timedelta
from http.cookiejar import CookieJar
from urllib.request import HTTPCookieProcessor, Request, build_opener

UA = "Mozilla/5.0 (compatible; ABpE-Radar-Test/1.0)"
CSRF_URL = "https://www.gulp.de/gulp2/rest/internal/system/csrf"
SEARCH_URL = "https://www.gulp.de/gulp2/rest/internal/projects/search"
LIST_URL = "https://www.gulp.de/gulp2/g/projekte?order=DATE_DESC&query=&page=1"
COOKIE = "LzA8Jg9Oe2"
HEADER = "x-trust"
DAYS = max(1, min(14, int("${DAYS}")))
day = date.today()
oldest = day - timedelta(days=DAYS - 1)

jar = CookieJar()
opener = build_opener(HTTPCookieProcessor(jar))
opener.open(Request(CSRF_URL, headers={"User-Agent": UA, "Referer": LIST_URL}), timeout=20).read()
token = next((c.value for c in jar if c.name == COOKIE), None)
if not token:
    raise SystemExit("CSRF-Cookie fehlt — Egress/Firewall?")
print(f"OK CSRF {COOKIE}={token[:8]}…")
print(f"Fenster {oldest} … {day} (days={DAYS})")

out = []
stop = False
for page in range(1, 5):
    if stop:
        break
    body = json.dumps({
        "query": "", "page": page, "limit": 20,
        "order": "DATE_DESC", "language": "DE",
    }).encode()
    req = Request(SEARCH_URL, data=body, method="POST", headers={
        "User-Agent": UA, "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://www.gulp.de", "Referer": LIST_URL,
        HEADER: token,
    })
    data = json.loads(opener.open(req, timeout=30).read().decode())
    projects = data.get("projects") or []
    print(f"page {page}: {len(projects)} roh (totalCount={data.get('totalCount')})")
    if not projects:
        break
    for p in projects:
        pub = (p.get("originalPublicationDate") or "")[:10]
        try:
            d = date.fromisoformat(pub)
        except Exception:
            continue
        if d < oldest:
            stop = True
            continue
        if d > day:
            continue
        out.append(p)

by = Counter((p.get("originalPublicationDate") or "")[:10] for p in out)
print(f"OK Treffer im Fenster: {len(out)}")
print("nach Tag:", dict(sorted(by.items(), reverse=True)))
for p in out[:5]:
    print(f" · {(p.get('originalPublicationDate') or '')[:16]}  {(p.get('title') or '')[:70]}")
    print(f"   {p.get('url') or ''}")
if not out:
    print("Keine Treffer — ggf. DAYS erhöhen oder Gulp hat noch nichts Neues.")
PY
