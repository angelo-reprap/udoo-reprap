#!/usr/bin/env bash
# Live → Repo: EDMS-Mail-Schnittstellen (Referenz für Posteingang-Viewer).
#
# Nur Lesen/Import — SYNC-abpe-shaduler überschreibt EDMS NICHT.
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap && git fetch origin cursor/abpe-shaduler-scaffold-7f07
#   bash <(git show origin/cursor/abpe-shaduler-scaffold-7f07:scripts/PULL-edms-mail-slice-from-live.sh)
set -euo pipefail

LIVE_EDMS="${LIVE_EDMS:-/opt/abpe/backend/apps/abpe_edms}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"
REPO="${REPO:-/mnt/public/udoo-reprap}"
DEST="$REPO/Repo_abpe/abpe_edms/incoming"
BRANCH="${BRANCH:-cursor/abpe-shaduler-scaffold-7f07}"

if [[ ! -d "$LIVE_EDMS" ]]; then
  echo "FAIL: $LIVE_EDMS fehlt."
  exit 1
fi
if [[ ! -d "$REPO/.git" ]]; then
  echo "FAIL: $REPO ist kein Git-Repo."
  exit 1
fi

mkdir -p "$DEST/views_snip" "$DEST/js" "$DEST/urls"

# URLs komplett (klein)
cp -a "$LIVE_EDMS/urls.py" "$DEST/urls/urls.py"

# Views: Mail-relevante Funktionen + Imports extrahieren
python3 - <<'PY' "$LIVE_EDMS" "$DEST/views_snip"
import ast, sys
from pathlib import Path

root = Path(sys.argv[1])
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)

want = {
    'api_person_mails', 'api_mail_view', 'api_mail_attachment',
    'api_mail_attachment_preview',
}

# views.py oder views/*.py
candidates = []
vp = root / 'views.py'
if vp.exists():
    candidates.append(vp)
vd = root / 'views'
if vd.is_dir():
    candidates.extend(sorted(vd.glob('*.py')))

found = {}
for path in candidates:
    try:
        tree = ast.parse(path.read_text(encoding='utf-8', errors='replace'))
    except SyntaxError as e:
        print(f'WARN parse {path}: {e}')
        continue
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in want:
            found[node.name] = (path, node.lineno, getattr(node, 'end_lineno', None))

report = []
for name in sorted(want):
    if name not in found:
        report.append(f'MISS {name}')
        continue
    path, start, end = found[name]
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    if end is None:
        # Fallback: bis nächste top-level def
        end = start
        for i in range(start, len(lines)):
            if i > start - 1 and lines[i].startswith('def ') and i + 1 != start:
                end = i
                break
        else:
            end = len(lines)
    chunk = '\n'.join(lines[start - 1:end])
    (out / f'{name}.py').write_text(chunk + '\n', encoding='utf-8')
    report.append(f'OK {name} ← {path.relative_to(root)}:{start}-{end} ({end - start + 1} Zeilen)')

(out / '_INDEX.txt').write_text('\n'.join(report) + '\n', encoding='utf-8')
print('\n'.join(report))
PY

# JS: alle mod-dms* + Treffer-Dateien
mkdir -p "$DEST/js"
shopt -s nullglob
for f in "$LIVE_UI"/static/abpe_ui/js/mod/mod-dms*.js; do
  cp -a "$f" "$DEST/js/$(basename "$f")"
done
# Fallback: Templates/andere Pfade
if [[ ! -e "$DEST/js/mod-dms.js" ]]; then
  find "$LIVE_UI" -name 'mod-dms*.js' -type f 2>/dev/null | while read -r f; do
    cp -a "$f" "$DEST/js/$(basename "$f")"
  done
fi

# Kurzer Interface-Report
REPORT="$DEST/INTERFACE.md"
{
  echo "# EDMS Mail-Schnittstellen (Live-Snapshot)"
  echo
  echo "Quelle: $LIVE_EDMS + $LIVE_UI"
  echo "Datum: $(date -Iseconds)"
  echo
  echo "## URLs"
  grep -n 'mail\|Mail' "$DEST/urls/urls.py" || true
  echo
  echo "## View-Snippets"
  cat "$DEST/views_snip/_INDEX.txt" 2>/dev/null || true
  echo
  echo "## JS-Treffer (mail/view/attachment/fetch)"
  if ls "$DEST/js"/mod-dms*.js >/dev/null 2>&1; then
    grep -nH -E 'mail/view|mail/attachment|api_mail|person/.*/mails|renderMail|loadMail|showMail|fetchMail|Mails' "$DEST/js"/mod-dms*.js | head -80 || true
  else
    echo "MISS: keine mod-dms*.js gefunden"
  fi
} > "$REPORT"

echo
echo "OK → $DEST"
echo "Report: $REPORT"
echo "Dateien: $(find "$DEST" -type f | wc -l)"
echo
echo "Nächste Schritte:"
echo "  cd $REPO"
echo "  git fetch origin && git checkout $BRANCH && git pull origin $BRANCH"
echo "  git add Repo_abpe/abpe_edms/incoming"
echo "  git commit -m 'Import: EDMS Mail-Slice von Live (Referenz Posteingang-Viewer)'"
echo "  git push -u origin $BRANCH"
echo
echo "Cloud Agent analysiert danach INTERFACE.md + View-Snippets + JS."
