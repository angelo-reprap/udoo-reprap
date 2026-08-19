#!/usr/bin/env bash
# FM-Session 302-Diagnose (nur lesen).
#   cd /mnt/public/udoo-reprap
#   bash <(git show origin/cursor/posteingang-radar-fix-1532:scripts/PROBE-fm-session-302.sh)
#   FM_URL='https://www.freelancermap.de/profil/mats-thieme' bash …
set -euo pipefail
BACKEND="${BACKEND:-/opt/abpe/backend}"
PYBIN="${PYBIN:-/opt/abpe/venv311/bin/python}"
FM_URL="${FM_URL:-https://www.freelancermap.de/profil/mats-thieme}"
cd "$BACKEND"
"$PYBIN" - <<PY
import os, json, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe_backend.settings')
django.setup()
from pathlib import Path
from apps.abpe_shaduler.services import radar_berater_fl as fl

url = os.environ.get('FM_URL', 'https://www.freelancermap.de/profil/mats-thieme')
info = fl.fl_session_info(include_secrets=False)
print('=== Session-Datei ===')
print(json.dumps(info, ensure_ascii=False, indent=2))
path = info.get('path')
if path and Path(path).is_file():
    st = Path(path).stat()
    import datetime as dt
    print('mtime=', dt.datetime.fromtimestamp(st.st_mtime).isoformat(), 'size=', st.st_size)
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    cookies = raw.get('cookies') or []
    if isinstance(cookies, list):
        for c in cookies:
            if not isinstance(c, dict):
                continue
            n = c.get('name')
            exp = c.get('expirationDate') or c.get('expires') or c.get('expiry')
            print(f'  cookie {n!r} exp={exp} domain={c.get("domain")}')

print()
print('=== Request (no follow) ===')
# raw urllib to see Location
import ssl, urllib.request
UA = 'Mozilla/5.0 ABpE-FM-Probe/1.0'
CTX = ssl.create_default_context()
cookie = fl.fl_session_info(include_secrets=True).get('cookie_header') or ''
headers = {'User-Agent': UA, 'Accept': 'text/html', 'Cookie': cookie}
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
opener = urllib.request.build_opener(NoRedirect)
req = urllib.request.Request(url, headers=headers, method='GET')
try:
    with opener.open(req, timeout=30, context=CTX) as resp:
        print('HTTP', resp.status, 'final=', resp.geturl())
        print('body_len', len(resp.read(500)))
except Exception as e:
    code = getattr(e, 'code', None)
    hdrs = getattr(e, 'headers', None)
    print('HTTP', code, type(e).__name__)
    if hdrs is not None:
        print('Location:', hdrs.get('Location'))
        print('Set-Cookie:', hdrs.get('Set-Cookie'))
    body = getattr(e, 'read', lambda: b'')()
    print('body:', (body or b'')[:300])

print()
print('=== fl._request (wie Radar) ===')
code, raw = fl._request(url, accept='text/html', timeout=30)
print('code=', code, 'body_len=', len(raw or b''))
if raw:
    print('body_head:', raw[:200])
print()
print('Wenn Location auf /login oder /anmelden → Cookies abgelaufen.')
print('Fix: Chrome-Extension Session neu exportieren →', path or 'data/url/fl/.session_cookies.json')
PY
