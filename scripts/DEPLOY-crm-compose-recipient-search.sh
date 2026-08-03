#!/usr/bin/env bash
# Chirurgischer Deploy: Compose Empfänger-Suche → Live-Pfade auf ucs5
# Usage (auf ucs5):
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/crm-compose-recipient-search-7f07
#   bash scripts/DEPLOY-crm-compose-recipient-search.sh
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
LIVE="${LIVE:-/opt/abpe/backend/apps/abpe_crm}"
BRANCH="${BRANCH:-origin/cursor/crm-compose-recipient-search-7f07}"
STAMP="$(date +%Y%m%d_%H%M%S)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

VIEWS_LIVE="$LIVE/views.py"
URLS_LIVE="$LIVE/urls.py"
TPL_LIVE="$LIVE/templates/abpe_crm/email_compose.html"

SRC_VIEWS="Repo_abpe/abpe_crm/incoming/views.py"
SRC_URLS="Repo_abpe/abpe_crm/incoming/urls.py"
SRC_TPL="Repo_abpe/abpe_crm/incoming/templates/abpe_crm/email_compose.html"

cd "$REPO"

echo "==> Repo:   $REPO"
echo "==> Live:   $LIVE"
echo "==> Branch: $BRANCH"

for f in "$VIEWS_LIVE" "$URLS_LIVE" "$TPL_LIVE"; do
  [[ -f "$f" ]] || { echo "FEHLT: $f"; exit 1; }
done

# Voraussetzungen in Live-views
grep -q 'def _get_phones' "$VIEWS_LIVE" || { echo "FEHLT in Live views: _get_phones"; exit 1; }
grep -q 'CrmContact' "$VIEWS_LIVE" || { echo "FEHLT in Live views: CrmContact"; exit 1; }
grep -q 'CrmEmailAddrBeanRel' "$VIEWS_LIVE" || { echo "FEHLT in Live views: CrmEmailAddrBeanRel"; exit 1; }

echo "==> Backup → ${LIVE}/.bak_compose_search_${STAMP}/"
BAK="${LIVE}/.bak_compose_search_${STAMP}"
mkdir -p "$BAK/templates/abpe_crm"
cp -a "$VIEWS_LIVE" "$BAK/views.py"
cp -a "$URLS_LIVE"  "$BAK/urls.py"
cp -a "$TPL_LIVE"   "$BAK/templates/abpe_crm/email_compose.html"

# Quellen aus Branch (ohne Checkout des ganzen Repos)
git show "$BRANCH:$SRC_VIEWS" > "$TMP/views_src.py"
git show "$BRANCH:$SRC_URLS"  > "$TMP/urls_src.py"
git show "$BRANCH:$SRC_TPL"   > "$TMP/email_compose.html"

python3 - <<'PY' "$VIEWS_LIVE" "$TMP/views_src.py"
import re, sys
live_path, src_path = sys.argv[1], sys.argv[2]
live = open(live_path, encoding='utf-8').read()
src  = open(src_path, encoding='utf-8').read()

# Funktion aus Branch extrahieren (mit optionalem @login_required davor)
m = re.search(
    r'(?ms)^(?:@login_required\n)?@login_or_token_required\n@require_http_methods\(\[\'GET\'\]\)\n'
    r'def api_contacts_suggest\(request\):.*?(?=\n(?:@login_required\n)?(?:@login_or_token_required\n)?(?:@require_http_methods.*\n)?def |\n\ndef |\Z)',
    src,
)
if not m:
    print('Konnte api_contacts_suggest im Branch-Source nicht finden', file=sys.stderr)
    sys.exit(1)

fn = m.group(0).rstrip() + '\n\n'
block = (
    '# ============================================================\n'
    '# CRM — Empfänger-Suche (Compose / Elasticsearch fuzzy)\n'
    '# ============================================================\n\n'
    + fn
)

# Bestehende Version ersetzen (inkl. Comment-Header falls vorhanden)
old = re.search(
    r'(?ms)^(?:# =+\n# CRM — Empfänger-Suche[^\n]*\n# =+\n\n)?'
    r'(?:@login_required\n)?@login_or_token_required\n@require_http_methods\(\[\'GET\'\]\)\n'
    r'def api_contacts_suggest\(request\):.*?(?=\n(?:# =+\n# CRM — E-MAIL COMPOSE|\n(?:@login_required\n)?(?:@login_or_token_required\n)?(?:@require_http_methods.*\n)?def |\n\ndef ))',
    live,
)
# Fallback: ab Comment/Decorators bis crm_email_compose
if not old:
    old = re.search(
        r'(?ms)^(?:# =+\n# CRM — Empfänger-Suche[^\n]*\n# =+\n\n)?'
        r'(?:@login_required\n)?@login_or_token_required\n@require_http_methods\(\[\'GET\'\]\)\n'
        r'def api_contacts_suggest\(request\):.*?(?=\n(?:@login_required\n)?(?:@login_or_token_required\n)?(?:@require_http_methods.*\n)?def crm_email_compose)',
        live,
    )

if old:
    new = live[:old.start()] + block + live[old.end():]
    open(live_path, 'w', encoding='utf-8').write(new)
    print('views.py: api_contacts_suggest ersetzt')
    sys.exit(0)

# Neu einfügen vor crm_email_compose
anchor = re.search(r'(?m)^def crm_email_compose\(request\):', live)
if not anchor:
    print('Anker def crm_email_compose fehlt in Live views.py', file=sys.stderr)
    sys.exit(1)

start = anchor.start()
prefix = live[:start]
lines_before = prefix.splitlines(True)
i = len(lines_before) - 1
while i >= 0 and (lines_before[i].startswith('@') or lines_before[i].strip() == ''):
    if lines_before[i].startswith('@'):
        i -= 1
        continue
    break
j = i + 1
while j < len(lines_before) and lines_before[j].strip() == '':
    j += 1
insert_at = sum(len(x) for x in lines_before[:j])
new = live[:insert_at] + block + live[insert_at:]
open(live_path, 'w', encoding='utf-8').write(new)
print('views.py: api_contacts_suggest eingefügt')
PY

python3 - <<'PY' "$URLS_LIVE"
import sys
path = sys.argv[1]
text = open(path, encoding='utf-8').read()
needle = "path('api/contacts/suggest/'"
if needle in text:
    print('urls.py: contacts/suggest schon vorhanden — skip')
    sys.exit(0)

line = "    path('api/contacts/suggest/',               views.api_contacts_suggest, name='api_contacts_suggest'),\n"
# nach api/email/send
marker = "path('api/email/send/'"
idx = text.find(marker)
if idx < 0:
    print('urls.py: api/email/send nicht gefunden', file=sys.stderr)
    sys.exit(1)
# Ende der Zeile
eol = text.find('\n', idx)
if eol < 0:
    print('urls.py: Zeilenende nicht gefunden', file=sys.stderr)
    sys.exit(1)
new = text[:eol+1] + line + text[eol+1:]
open(path, 'w', encoding='utf-8').write(new)
print('urls.py: contacts/suggest Route eingefügt')
PY

# Fix Send-Crash: tpl.pk = None / tpl_copy.pk = None entfernen (Live + Branch-Sync)
python3 - <<'PY' "$VIEWS_LIVE"
import re, sys
path = sys.argv[1]
text = open(path, encoding='utf-8').read()
new, n1 = re.subn(r'(?m)^\s*tpl\.pk = None[^\n]*\n', '', text)
new, n2 = re.subn(r'(?m)^\s*tpl_copy\.pk = None[^\n]*\n', '', new)
if n1 or n2:
    open(path, 'w', encoding='utf-8').write(new)
    print(f'views.py: pk=None entfernt (tpl={n1}, tpl_copy={n2}) — Send-Fix')
else:
    print('views.py: kein tpl.pk = None gefunden (ok oder schon gefixt)')
PY

# Template: Backup ist da — Live-Compose durch Branch-Version ersetzen
# (An-Feld + Typeahead; Rest entspricht dem Compose-Stand des Branches)
cp -a "$TMP/email_compose.html" "$TPL_LIVE"
echo "email_compose.html: An-Feld Typeahead aus Branch übernommen"

# Syntax-Check
python3 -m py_compile "$VIEWS_LIVE" "$URLS_LIVE"
echo "==> py_compile OK"

# Verify
echo "==> Verify:"
grep -n "def api_contacts_suggest\|contacts/suggest\|crm-to-search\|tpl\.pk = None\|tpl_copy\.pk = None" \
  "$VIEWS_LIVE" "$URLS_LIVE" "$TPL_LIVE" | head -30

echo
echo "OK. Backup: $BAK"
echo "Danach Backend reload (z.B. systemctl reload/restart abpe-*) und Browser Hard-Reload."
echo "Test: /crm/email/compose/ → An-Feld tippen → Treffer mit Name/Mail/Firma/Tel"
echo "Test: Senden / Test senden darf nicht mehr 'no primary key' werfen."
