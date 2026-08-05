#!/usr/bin/env bash
# Konzept-Test: DeepSeek liest Matching-Anfrage aus E-Mail (kein Ollama).
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap && git fetch origin cursor/abpe-shaduler-scaffold-7f07
#   bash <(git show origin/cursor/abpe-shaduler-scaffold-7f07:scripts/PROBE-matching-anfrage-extrakt.sh)
#
# Optional:
#   FIXTURE=.../fixture-hays-fwd.txt
#   SUBJECT='WG: …'
#   OUTER_FROM='Bär, Karsten <…>'
#   SAVE_JSON=/tmp/anfrage-extrakt.json
set -u

BACKEND="${BACKEND:-/opt/abpe/backend}"
PYBIN="${PYBIN:-/opt/abpe/venv311/bin/python}"
SETTINGS_JSON="${SETTINGS_JSON:-/opt/abpe/backend/settings.json}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-origin/cursor/abpe-shaduler-scaffold-7f07}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
# Wenn via process-substitution gestartet: Fixtures aus git laden
FIXTURE_DIR="${FIXTURE_DIR:-}"
if [[ -z "$FIXTURE_DIR" ]]; then
  if [[ -n "${SCRIPT_DIR:-}" && -d "$SCRIPT_DIR/matching-anfrage-extrakt" ]]; then
    FIXTURE_DIR="$SCRIPT_DIR/matching-anfrage-extrakt"
  elif [[ -d "$REPO/scripts/matching-anfrage-extrakt" ]]; then
    FIXTURE_DIR="$REPO/scripts/matching-anfrage-extrakt"
  else
    FIXTURE_DIR="$(mktemp -d)"
    trap 'rm -rf "$FIXTURE_DIR"' EXIT
    mkdir -p "$FIXTURE_DIR"
    git -C "$REPO" show "$BRANCH:scripts/matching-anfrage-extrakt/PROMPT_SYSTEM.txt" \
      > "$FIXTURE_DIR/PROMPT_SYSTEM.txt"
    git -C "$REPO" show "$BRANCH:scripts/matching-anfrage-extrakt/fixture-hays-fwd.txt" \
      > "$FIXTURE_DIR/fixture-hays-fwd.txt"
    git -C "$REPO" show "$BRANCH:scripts/matching-anfrage-extrakt/fixture-hays-fwd.expected.json" \
      > "$FIXTURE_DIR/fixture-hays-fwd.expected.json"
  fi
fi

FIXTURE="${FIXTURE:-$FIXTURE_DIR/fixture-hays-fwd.txt}"
EXPECTED="${EXPECTED:-$FIXTURE_DIR/fixture-hays-fwd.expected.json}"
PROMPT_SYS="${PROMPT_SYS:-$FIXTURE_DIR/PROMPT_SYSTEM.txt}"
SUBJECT="${SUBJECT:-WG: Hays AG - IT Network & Security Engineer – Fortinet (m/w/d)}"
OUTER_FROM="${OUTER_FROM:-Bär, Karsten <baer.karsten@baer-consulting.bayern>}"

echo "======== PROBE Matching Anfrage-Extrakt (DeepSeek) $(date -Iseconds) ========"
echo "FIXTURE=$FIXTURE"
echo "SETTINGS=$SETTINGS_JSON"
echo

export FIXTURE EXPECTED PROMPT_SYS SUBJECT OUTER_FROM SETTINGS_JSON SAVE_JSON="${SAVE_JSON:-}"
"$PYBIN" - <<'PY'
import json, os, re, sys, urllib.request

settings_path = os.environ['SETTINGS_JSON']
fixture = open(os.environ['FIXTURE'], encoding='utf-8').read()
prompt_sys = open(os.environ['PROMPT_SYS'], encoding='utf-8').read()
expected_pack = json.load(open(os.environ['EXPECTED'], encoding='utf-8'))
expected = expected_pack['expected']
subject = os.environ.get('SUBJECT') or ''
outer_from = os.environ.get('OUTER_FROM') or ''

cfg = json.load(open(settings_path, encoding='utf-8'))
ds = (cfg.get('ai_models') or {}).get('deepseek') or cfg.get('deepseek') or {}
api_key = ds.get('api_key') or os.environ.get('DEEPSEEK_API_KEY') or ''
model = ds.get('model') or 'deepseek-chat'
timeout = int(ds.get('timeout') or 60)
temperature = float(ds.get('temperature') if ds.get('temperature') is not None else 0.1)
max_tokens = int(ds.get('max_tokens') or 2000)
base = (ds.get('base_url') or 'https://api.deepseek.com').rstrip('/')
url = base + '/v1/chat/completions'

if not api_key:
    print('FAIL: kein DeepSeek api_key in settings.json / DEEPSEEK_API_KEY')
    sys.exit(2)

user = f"""Extrahiere Matching-Anfrage als JSON.

Betreff: {subject}
Äußerer Absender (Envelope/From): {outer_from}

--- MAIL BODY ---
{fixture}
--- ENDE ---
"""

payload = {
    'model': model,
    'temperature': temperature,
    'max_tokens': max_tokens,
    'response_format': {'type': 'json_object'},
    'messages': [
        {'role': 'system', 'content': prompt_sys},
        {'role': 'user', 'content': user},
    ],
}

print(f'→ DeepSeek model={model} timeout={timeout}s …')
req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode('utf-8'),
    headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
    },
    method='POST',
)
try:
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode('utf-8')
        http = resp.status
except Exception as exc:
    print('FAIL: HTTP', exc)
    sys.exit(2)

data = json.loads(raw)
content = (((data.get('choices') or [{}])[0].get('message') or {}).get('content')) or ''
# falls Modell Markdown-Fence liefert
m = re.search(r'\{[\s\S]*\}', content)
if not m:
    print('FAIL: keine JSON im Response')
    print(content[:800])
    sys.exit(1)
try:
    result = json.loads(m.group(0))
except Exception as exc:
    print('FAIL: JSON parse', exc)
    print(content[:800])
    sys.exit(1)

save = os.environ.get('SAVE_JSON') or ''
if save:
    open(save, 'w', encoding='utf-8').write(json.dumps(result, ensure_ascii=False, indent=2))
    print(f'OK  gespeichert → {save}')

print()
print('=== DeepSeek Ergebnis ===')
print(json.dumps(result, ensure_ascii=False, indent=2))
print()

PASS = FAIL = WARN = 0

def ok(msg):
    global PASS
    print('  OK ', msg); PASS += 1

def fail(msg):
    global FAIL
    print('  FAIL', msg); FAIL += 1

def warn(msg):
    global WARN
    print('  WARN', msg); WARN += 1

def get(d, *path, default=None):
    cur = d
    for p in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(p, default)
    return cur

print('=== Abgleich Soll (Konzept) ===')

# Kunde
ename = (get(expected, 'kunde', 'name') or '').lower()
gname = (get(result, 'kunde', 'name') or '').lower()
if ename and ename in gname:
    ok(f'kunde.name enthält {expected["kunde"]["name"]!r} → {result.get("kunde")}')
elif 'hays' in gname:
    ok(f'kunde.name≈Hays → {result.get("kunde")}')
else:
    fail(f'kunde.name erwartet Hays AG, got {result.get("kunde")}')

# nicht baer als Kunde
if 'baer' in gname or 'bär' in gname:
    fail('kunde darf nicht baer consulting sein (Weiterleiter)')
else:
    ok('kunde ist nicht der Weiterleiter')

# Ansprechpartner
ap_mail = (get(result, 'ansprechpartner', 'email') or '').lower()
if 'tristan.treder@hays.de' in ap_mail:
    ok(f'ansprechpartner.email={ap_mail}')
else:
    fail(f'ansprechpartner.email erwartet tristan.treder@hays.de, got {result.get("ansprechpartner")}')

ap_name = (get(result, 'ansprechpartner', 'name') or '').lower()
if 'treder' in ap_name:
    ok(f'ansprechpartner.name={get(result,"ansprechpartner","name")}')
else:
    warn(f'ansprechpartner.name ohne Treder: {get(result,"ansprechpartner","name")}')

# Weiterleitung
wl = result.get('weiterleitung') or {}
if wl.get('ja') is True:
    ok(f'weiterleitung.ja=true von={wl.get("von")}')
else:
    fail(f'weiterleitung.ja erwartet true, got {wl}')

# Titel
titel = result.get('titel') or ''
if 'fortinet' in titel.lower() and ('network' in titel.lower() or 'security' in titel.lower()):
    ok(f'titel={titel!r}')
else:
    fail(f'titel unerwartet: {titel!r}')

# Beschreibung
besch = result.get('beschreibung') or ''
for needle in expected.get('beschreibung_contains') or []:
    if needle.lower() in besch.lower():
        ok(f'beschreibung enthält {needle!r}')
    else:
        fail(f'beschreibung fehlt {needle!r}')
# Dauer in Fließtext: "3 MM" oder "3 Monate" — strukturiertes Feld zählt separat
dauer_needles = expected.get('beschreibung_dauer_any') or []
if dauer_needles:
    if any(n.lower() in besch.lower() for n in dauer_needles):
        ok('beschreibung erwähnt Dauer (3 MM/Monate)')
    else:
        # kein FAIL: dauer_monate-Feld ist maßgeblich
        warn(f'beschreibung ohne Dauer-Wortlaut (ok wenn dauer_monate gesetzt)')
for bad in expected.get('beschreibung_excludes') or []:
    if bad.lower() in besch.lower():
        fail(f'beschreibung enthält unerwünscht {bad!r}')
    else:
        ok(f'beschreibung ohne {bad!r}')

# Start / Dauer / Ort / Satz
st = result.get('start') or {}
if st.get('asap') is True:
    ok('start.asap=true')
else:
    fail(f'start.asap erwartet true, got {st}')
if st.get('datum') in (None, '', False):
    ok('start.datum=null (kein erfundenes Datum)')
else:
    warn(f'start.datum gesetzt: {st.get("datum")}')

dm = result.get('dauer_monate')
try:
    dm_n = int(dm) if dm is not None else None
except Exception:
    dm_n = None
if dm_n == 3:
    ok('dauer_monate=3')
else:
    fail(f'dauer_monate erwartet 3, got {dm}')

standort = (result.get('standort') or '')
if 'remote' in standort.lower() or result.get('remote') is True:
    ok(f'standort/remote ok ({standort!r}, remote={result.get("remote")})')
else:
    fail(f'standort/remote erwartet Remote, got {standort!r} / {result.get("remote")}')

if result.get('stundensatz_max') in (None, '', 0):
    ok('stundensatz_max=null (Mail fragt Bewerber-Satz)')
else:
    fail(f'stundensatz_max sollte null sein, got {result.get("stundensatz_max")}')

# Skills
skills = result.get('skills') or []
skills_l = ' '.join(str(s).lower() for s in skills)
hit = False
for s in expected.get('skills_must_include_any') or []:
    if s.lower() in skills_l:
        hit = True
        break
if hit and len(skills) >= 3:
    ok(f'skills ({len(skills)}): {skills[:8]}…')
else:
    fail(f'skills unzureichend: {skills}')

# Hinweise
hints = ' '.join(str(h) for h in (result.get('hinweise') or [])).lower()
hint_ok = False
for h in expected.get('hinweise_any') or []:
    if h.lower() in hints or h.lower() in besch.lower():
        hint_ok = True
        break
if hint_ok:
    ok(f'hinweise/beschreibung Kontext Endkunde/Weiterleitung')
else:
    warn(f'hinweise dünn: {result.get("hinweise")}')

print()
print(f'======== SUMMARY PASS={PASS} FAIL={FAIL} WARN={WARN} ========')
if FAIL:
    print('Konzept-Test: Abweichungen — Prompt/Schema nachschärfen')
    sys.exit(1)
print('Konzept-Test: DeepSeek Extrakt passt zur Soll-Logik (Hays-Fwd)')
sys.exit(0)
PY
