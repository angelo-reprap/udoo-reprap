#!/usr/bin/env bash
# Vollständiger Export: ABpE Portal + Email Studio → Repo_abpe/incoming/
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap && git pull
#   bash scripts/export-portal-full.sh
#   # dann: git add Repo_abpe/abpe_ui Repo_abpe/email_studio Repo_abpe/abpe_core
#   #       git commit -m "Export: Portal + Email Studio von ucs5"
#   #       git push
#
# WICHTIG: Kein --delete — nur ergänzen/überschreiben (wie MeetMe-Export).

set -euo pipefail

BACKEND="${ABPE_BACKEND:-/opt/abpe/backend}"
STAGING="${REPO_ABPE_STAGING:-/mnt/public/udoo-reprap/Repo_abpe}"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "=== ABpE Portal + Email Studio Export ==="
echo "Backend: $BACKEND"
echo "Staging: $STAGING"
echo "Zeit:    $TS"
echo ""

if [[ ! -d "$BACKEND/apps/abpe_email_studio" ]]; then
  echo "FEHLER: $BACKEND/apps/abpe_email_studio nicht gefunden" >&2
  exit 1
fi

mkdir -p "$STAGING"

# ── Hilfsfunktion: App-Verzeichnis → incoming/ (flach + Unterordner) ─────────
export_app() {
  local app="$1"       # z.B. abpe_email_studio
  local module="$2"      # z.B. email_studio
  local src="${BACKEND}/apps/${app}"
  local dest="${STAGING}/${module}/incoming"

  if [[ ! -d "$src" ]]; then
    echo "WARN: $src fehlt — übersprungen"
    return 0
  fi

  mkdir -p "$dest"
  echo "--- Export $app → $module/incoming ---"

  # Python Backend
  rsync -av \
    --exclude '__pycache__/' --exclude '*.pyc' --exclude 'migrations/__pycache__/' \
    --include '*/' --include '*.py' --exclude '*' \
    "$src/" "$dest/"

  # Templates (Dateiname = basename)
  if [[ -d "$src/templates" ]]; then
    find "$src/templates" -type f \( -name '*.html' -o -name '*.txt' \) | while read -r f; do
      cp -a "$f" "$dest/$(basename "$f")"
    done
  fi

  # Static JS/CSS (email_studio + abpe_ui)
  if [[ -d "$src/static" ]]; then
    find "$src/static" -type f \( -name '*.js' -o -name '*.css' -o -name '*.json' \) \
      ! -path '*/node_modules/*' | while read -r f; do
      cp -a "$f" "$dest/$(basename "$f")"
    done
    # i18n-Verzeichnisse erhalten
    if [[ -d "$src/static" ]]; then
      find "$src/static" -type d -name 'i18n' | while read -r idir; do
        rel="${idir#"$src/static/"}"
        mkdir -p "$dest/static_${rel}"
        rsync -av "$idir/" "$dest/static_${rel}/"
      done
    fi
  fi

  local count
  count=$(find "$dest" -type f | wc -l | tr -d ' ')
  echo "OK: $module/incoming — $count Dateien"
}

# ── abpe_email_studio ────────────────────────────────────────────────────────
export_app abpe_email_studio email_studio

# ── abpe_ui (Portal-Shell) ───────────────────────────────────────────────────
export_app abpe_ui abpe_ui

# ── abpe_core (urls, settings redigiert) ─────────────────────────────────────
CORE_DEST="${STAGING}/abpe_core/incoming"
mkdir -p "$CORE_DEST"

for f in urls.py manage.py; do
  [[ -f "$BACKEND/$f" ]] && cp -a "$BACKEND/$f" "$CORE_DEST/" && echo "OK: $f"
done

if [[ -f "$BACKEND/settings.json" ]]; then
  python3 - "$BACKEND/settings.json" "$CORE_DEST/settings.json" <<'PY'
import json, re, sys
from pathlib import Path
src, dest = Path(sys.argv[1]), Path(sys.argv[2])
data = json.loads(src.read_text(encoding="utf-8"))
SENS = {"password", "secret", "token", "api_key", "private_key"}
def redact(obj):
    if isinstance(obj, dict):
        return {k: ("***REDACTED***" if any(s in k.lower() for s in SENS) else redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    return obj
dest.write_text(json.dumps(redact(data), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("OK: settings.json (redigiert)")
PY
fi

# lang_map
[[ -f "$BACKEND/apps/abpe_ui/bin/lang_map.json" ]] && \
  cp -a "$BACKEND/apps/abpe_ui/bin/lang_map.json" "$CORE_DEST/lang_map.json"

# Manifest
{
  echo "# ABpE Apps — $TS"
  find "$BACKEND/apps" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort
} > "$CORE_DEST/APPS_MANIFEST.txt"
echo "OK: APPS_MANIFEST.txt"

echo ""
echo "=== Fertig ==="
for mod in email_studio abpe_ui abpe_core; do
  d="${STAGING}/${mod}/incoming"
  [[ -d "$d" ]] && echo "  $mod: $(find "$d" -type f | wc -l | tr -d ' ') Dateien"
done
echo ""
echo "Nächster Schritt (udoo-reprap):"
echo "  git add Repo_abpe/email_studio Repo_abpe/abpe_ui Repo_abpe/abpe_core"
echo "  git commit -m \"Export: Portal + Email Studio von ucs5 ($TS)\""
echo "  git push"
