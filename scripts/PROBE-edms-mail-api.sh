#!/usr/bin/env bash
# Schnell-Diagnose: EDMS Mail-API + JS auf stdout (kein Commit nötig).
# Auf ucs5:
#   bash <(git -C /mnt/public/udoo-reprap show origin/cursor/abpe-shaduler-scaffold-7f07:scripts/PROBE-edms-mail-api.sh)
set -euo pipefail

LIVE_EDMS="${LIVE_EDMS:-/opt/abpe/backend/apps/abpe_edms}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"

echo "=== 1) URLs ==="
grep -n 'mail' "$LIVE_EDMS/urls.py" || true

echo
echo "=== 2) View-Signaturen (def api_mail* / api_person_mails) ==="
python3 - <<'PY'
import ast
from pathlib import Path
root = Path('/opt/abpe/backend/apps/abpe_edms')
want = {'api_person_mails','api_mail_view','api_mail_attachment','api_mail_attachment_preview'}
files = []
if (root/'views.py').exists():
    files.append(root/'views.py')
if (root/'views').is_dir():
    files.extend(sorted((root/'views').glob('*.py')))
for path in files:
    try:
        src = path.read_text(encoding='utf-8', errors='replace')
        tree = ast.parse(src)
    except Exception as e:
        print(f'WARN {path}: {e}')
        continue
    lines = src.splitlines()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in want:
            end = getattr(node, 'end_lineno', node.lineno + 40)
            print(f'\n--- {path.name}:{node.lineno} {node.name} ---')
            # Signatur + Docstring + erste ~35 Zeilen Körper
            chunk = lines[node.lineno-1:min(end, node.lineno+40)]
            print('\n'.join(chunk[:45]))
PY

echo
echo "=== 3) JS-Dateien mod-dms* ==="
find "$LIVE_UI" -name 'mod-dms*.js' -type f 2>/dev/null | head -20

echo
echo "=== 4) JS mail/view/attachment Treffer ==="
find "$LIVE_UI" -name 'mod-dms*.js' -type f 2>/dev/null | while read -r f; do
  echo "-- $f"
  grep -nE 'mail/view|mail/attachment|person/.*/mails|renderMail|loadMail|showMail|fetchMail|/api/mail' "$f" | head -40 || true
done

echo
echo "=== 5) Query-Params api_mail_view (GET-Parameter im Code) ==="
grep -rn "api_mail_view\|mail/view\|request.GET.get" "$LIVE_EDMS" --include='*.py' | grep -iE 'mail|es_id|email_id|doc_id|message' | head -40 || true

echo
echo "DONE — Ausgabe an Cloud Agent schicken oder PULL-edms-mail-slice ausführen."
