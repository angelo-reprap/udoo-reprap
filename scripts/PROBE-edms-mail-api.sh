#!/usr/bin/env bash
# Schnell-Diagnose: EDMS Mail-API + JS auf stdout (kein Commit nötig).
# Auf ucs5:
#   bash <(git -C /mnt/public/udoo-reprap show origin/cursor/abpe-shaduler-scaffold-7f07:scripts/PROBE-edms-mail-api.sh)
set -euo pipefail

LIVE_EDMS="${LIVE_EDMS:-/opt/abpe/backend/apps/abpe_edms}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"
LIVE_ROOT="${LIVE_ROOT:-/opt/abpe/backend}"

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
            chunk = lines[node.lineno-1:min(end, node.lineno+40)]
            print('\n'.join(chunk[:45]))
PY

echo
echo "=== 3) JS/HTML: DMS + mail/view (breitere Suche) ==="
find "$LIVE_UI" \( -iname '*dms*' -o -iname '*edms*' \) 2>/dev/null | head -40 || true
echo "--- grep mail/view ---"
grep -rn "mail/view\|api/mail\|api_mail" "$LIVE_UI" --include='*.js' --include='*.html' --include='*.vue' 2>/dev/null | head -50 || true

echo
echo "=== 4) EDMS URL-Mount ==="
grep -rn "abpe_edms\|edms" "$LIVE_ROOT/abpe_backend/urls.py" "$LIVE_ROOT/apps"/*/urls.py 2>/dev/null | head -30 || true

echo
echo "=== 5) _imap_fetch_message — PEEK? ==="
grep -n "_imap_fetch_message\|BODY.PEEK\|BODY\[\|Seen" "$LIVE_EDMS/views.py" 2>/dev/null | head -40 || true

echo
echo "DONE — Ausgabe an Cloud Agent schicken oder PULL-edms-mail-slice ausführen."
