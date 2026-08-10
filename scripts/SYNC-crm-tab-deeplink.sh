#!/usr/bin/env bash
# Patcht Live CRM-JS: ?detail=<id>&tab=notizen öffnet den Notizen-Reiter.
# Usage (ucs5):
#   cd /mnt/public/udoo-reprap && git fetch origin
#   bash scripts/SYNC-crm-tab-deeplink.sh
set -euo pipefail

LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"
STATICFILES="${STATICFILES:-/opt/abpe/backend/staticfiles}"
STAMP="$(date +%Y%m%d_%H%M%S)"

SNIP=$'/* CRM_TAB_DEEPLINK */\n'
SNIP+=$'                  var crmDeeplinkTab = params.get(\'tab\');\n'
SNIP+=$'                  if (crmDeeplinkTab) {\n'
SNIP+=$'                    var tabHost = (window.location.pathname.indexOf(\'/kunden\') >= 0 && typeof CRM_Kunden !== \'undefined\') ? CRM_Kunden : (typeof CRM_Berater !== \'undefined\' ? CRM_Berater : null);\n'
SNIP+=$'                    if (tabHost && typeof tabHost.switchTab === \'function\') {\n'
SNIP+=$'                      var tabEl = document.querySelector(\'.crm-detail-tab[onclick*=\"\\\'\' + crmDeeplinkTab + \'\\\'\"]\');\n'
SNIP+=$'                      tabHost.switchTab(crmDeeplinkTab, tabEl || null);\n'
SNIP+=$'                    }\n'
SNIP+=$'                  }\n'

patch_file() {
  local f="$1"
  [[ -f "$f" ]] || { echo "SKIP (fehlt): $f"; return 0; }
  if grep -q 'CRM_TAB_DEEPLINK' "$f"; then
    echo "OK bereits: $f"
    return 0
  fi
  cp -a "$f" "${f}.bak_tab_${STAMP}"
  CRM_SNIP="$SNIP" python3 - "$f" <<'PY'
import os, re, sys
path = sys.argv[1]
src = open(path, encoding='utf-8').read()
snip = os.environ['CRM_SNIP']
# Insert after CRM_*.renderDetail(d); inside auto-open handler
pat = re.compile(r'((?:CRM_(?:Berater|Kunden)\.)?renderDetail\(d\);)(\s*)')
m = pat.search(src)
if not m:
    print('WARN: kein renderDetail(d) in', path, file=sys.stderr)
    sys.exit(1)
# Replace all auto-open occurrences (berater + kunden files usually 1 each)
new, n = pat.subn(r'\1\n' + snip + r'\2', src, count=3)
open(path, 'w', encoding='utf-8').write(new)
print('PATCHED', path, 'n=', n)
PY
}

echo "==> CRM tab= deeplink patch"
for name in mod-crm-berater.js mod-crm-kunden.js; do
  patch_file "$LIVE_UI/static/abpe_ui/js/mod/$name"
  if [[ -d "$STATICFILES/abpe_ui/js/mod" && -f "$LIVE_UI/static/abpe_ui/js/mod/$name" ]]; then
    cp -a "$LIVE_UI/static/abpe_ui/js/mod/$name" "$STATICFILES/abpe_ui/js/mod/$name"
    echo "→ staticfiles: $name"
  fi
done
echo "Fertig. Hard-Reload im Browser."
