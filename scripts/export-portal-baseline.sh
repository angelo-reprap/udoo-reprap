#!/usr/bin/env bash
# Exportiert Portal-Basis + Email-Studio-Ergänzungen nach Repo_abpe-Staging.
# Secrets in settings.json werden vor dem Kopieren redigiert.
#
# Auf ucs5:
#   curl -fsSL -o /opt/abpe/scripts/export-portal-baseline.sh \
#     "https://raw.githubusercontent.com/angelo-reprap/udoo-reprap/cursor/portal-export-script-bf44/scripts/export-portal-baseline.sh"
#   chmod +x /opt/abpe/scripts/export-portal-baseline.sh
#   /opt/abpe/scripts/export-portal-baseline.sh

set -euo pipefail

BACKEND_ROOT="${ABPE_BACKEND:-/opt/abpe/backend}"
STAGING_ROOT="${REPO_ABPE_STAGING:-/mnt/public/Repo_abpe}"
EXPORT_SH="${ABPE_EXPORT_SH:-/opt/abpe/scripts/export-to-repo.sh}"

if [[ ! -x "$EXPORT_SH" ]]; then
  echo "Fehler: $EXPORT_SH nicht gefunden/ausführbar." >&2
  echo "Zuerst export-to-repo.sh installieren." >&2
  exit 1
fi

if [[ ! -d "$BACKEND_ROOT" ]]; then
  echo "Fehler: Backend nicht gefunden: $BACKEND_ROOT" >&2
  exit 1
fi

copy_backend_file() {
  local module="$1"
  local rel="$2"
  local dest_name="${3:-$(basename "$rel")}"
  local src="${BACKEND_ROOT}/${rel}"
  local dest_dir="${STAGING_ROOT}/${module}/incoming"

  if [[ ! -e "$src" ]]; then
    echo "WARN: fehlt — $src"
    return 0
  fi

  mkdir -p "$dest_dir"
  cp -a "$src" "${dest_dir}/${dest_name}"
  echo "OK: ${src} -> ${dest_dir}/${dest_name}"
}

copy_glob() {
  local module="$1"
  local pattern="$2"
  shopt -s nullglob
  local files=( $pattern )
  shopt -u nullglob
  if [[ ${#files[@]} -eq 0 ]]; then
    echo "WARN: kein Treffer — $pattern"
    return 0
  fi
  for f in "${files[@]}"; do
    "$EXPORT_SH" "$module" "$f"
  done
}

sanitize_settings_json() {
  local src="${BACKEND_ROOT}/settings.json"
  local dest_dir="${STAGING_ROOT}/abpe_core/incoming"
  local dest="${dest_dir}/settings.json"

  if [[ ! -f "$src" ]]; then
    echo "WARN: settings.json fehlt — $src"
    return 0
  fi

  mkdir -p "$dest_dir"
  python3 - "$src" "$dest" <<'PY'
import json, re, sys
from pathlib import Path

src, dest = Path(sys.argv[1]), Path(sys.argv[2])
data = json.loads(src.read_text(encoding="utf-8"))

SENSITIVE_KEYS = {
    "api_key", "password", "secret", "token", "private_key",
    "EMAIL_HOST_PASSWORD", "SECRET_KEY", "DATABASE_PASSWORD",
}

def redact(obj, path=""):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            key_lower = k.lower()
            if any(s in key_lower for s in SENSITIVE_KEYS):
                out[k] = "***REDACTED***"
            else:
                out[k] = redact(v, f"{path}.{k}")
        return out
    if isinstance(obj, list):
        return [redact(x, path) for x in obj]
    if isinstance(obj, str) and re.fullmatch(r"ghp_[A-Za-z0-9]+", obj):
        return "***REDACTED***"
    return obj

clean = redact(data)
dest.write_text(json.dumps(clean, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"OK: {src} -> {dest} (Secrets redigiert)")
PY
}

write_apps_manifest() {
  local dest_dir="${STAGING_ROOT}/abpe_core/incoming"
  local dest="${dest_dir}/APPS_MANIFEST.txt"
  mkdir -p "$dest_dir"
  {
    echo "# ABpE Django Apps — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "# Backend: ${BACKEND_ROOT}"
    echo ""
    if [[ -d "${BACKEND_ROOT}/apps" ]]; then
      find "${BACKEND_ROOT}/apps" -mindepth 1 -maxdepth 1 -type d | sort | while read -r app; do
        echo "$(basename "$app")"
      done
    fi
  } > "$dest"
  echo "OK: ${dest}"
}

echo "=== ABpE Portal Baseline Export ==="
echo "Backend: ${BACKEND_ROOT}"
echo "Staging: ${STAGING_ROOT}"
echo ""

write_apps_manifest

# ── abpe_core: Konfiguration + Root-Routing ──────────────────────────────────
sanitize_settings_json

for candidate in \
  "urls.py" \
  "config/urls.py" \
  "abpe/urls.py" \
  "abpe_portal/urls.py" \
  "settings/email.py" \
  "settings/base.py" \
  "settings/__init__.py" \
  "manage.py"
do
  copy_backend_file "abpe_core" "$candidate" "$(echo "$candidate" | tr '/' '_')"
done

copy_backend_file "abpe_core" "apps/abpe_ui/bin/lang_map.json" "lang_map.json"

# ── abpe_ui: Portal-Shell ───────────────────────────────────────────────────
UI_TEMPLATES=(
  "apps/abpe_ui/templates/abpe_ui/base.html"
  "apps/abpe_ui/templates/abpe_ui/sidebar.html"
  "apps/abpe_ui/templates/abpe_ui/navbar.html"
  "apps/abpe_ui/templates/abpe_ui/login.html"
  "apps/abpe_ui/templates/abpe_ui/home.html"
)

for f in "${UI_TEMPLATES[@]}"; do
  copy_backend_file "abpe_ui" "$f" "$(basename "$f")"
done

copy_glob "abpe_ui" "${BACKEND_ROOT}/apps/abpe_ui/static/abpe_ui/js/core-*.js"
copy_glob "abpe_ui" "${BACKEND_ROOT}/apps/abpe_ui/static/abpe_ui/css/*.css"
copy_glob "abpe_ui" "${BACKEND_ROOT}/apps/abpe_ui/static/abpe_ui/css/mod/mod-*.css"

# i18n-Basis (nur Struktur + Kern, keine Secrets)
copy_backend_file "abpe_ui" "apps/abpe_ui/static/abpe_ui/i18n/de/manifest.json" "i18n_de_manifest.json" || true
copy_backend_file "abpe_ui" "apps/abpe_ui/static/abpe_ui/i18n/en/manifest.json" "i18n_en_manifest.json" || true
copy_backend_file "abpe_ui" "apps/abpe_ui/static/abpe_ui/i18n/de/portal.json" "i18n_de_portal.json" || true
copy_backend_file "abpe_ui" "apps/abpe_ui/static/abpe_ui/i18n/en/portal.json" "i18n_en_portal.json" || true

# ── email_studio: fehlende Ergänzungen ───────────────────────────────────────
"$EXPORT_SH" email_studio --from-backend \
  abpe_email_studio/tasks.py \
  abpe_email_studio/signals.py \
  abpe_email_studio/admin.py \
  abpe_email_studio/services/compatibility.py \
  abpe_email_studio/apps.py \
  abpe_email_studio/__init__.py

"$EXPORT_SH" email_studio \
  "${BACKEND_ROOT}/apps/abpe_ui/static/abpe_ui/i18n/de/modules/email_studio/email_studio.json" \
  "${BACKEND_ROOT}/apps/abpe_ui/static/abpe_ui/i18n/de/modules/email_studio/manifest.json" \
  "${BACKEND_ROOT}/apps/abpe_ui/static/abpe_ui/i18n/en/modules/email_studio/email_studio.json" \
  "${BACKEND_ROOT}/apps/abpe_ui/static/abpe_ui/i18n/en/modules/email_studio/manifest.json" \
  "${BACKEND_ROOT}/apps/abpe_ui/static/abpe_ui/css/mod/mod-es-components.css" \
  "${BACKEND_ROOT}/apps/abpe_email_studio/static/email_studio/i18n/help_de.json" \
  "${BACKEND_ROOT}/apps/abpe_email_studio/static/email_studio/i18n/help_en.json" 2>/dev/null || true

# ── abpe_crm: Kern ───────────────────────────────────────────────────────────
"$EXPORT_SH" abpe_crm --from-backend \
  abpe_crm/urls.py \
  abpe_crm/views.py \
  abpe_crm/models.py \
  abpe_crm/reporting_api.py 2>/dev/null || true

copy_glob "abpe_crm" "${BACKEND_ROOT}/apps/abpe_crm/static/abpe_crm/js/mod-crm*.js"

# ── abpe_meetme: Kern ────────────────────────────────────────────────────────
"$EXPORT_SH" abpe_meetme --from-backend \
  abpe_meetme/urls.py \
  abpe_meetme/views.py \
  abpe_meetme/email_helpers.py 2>/dev/null || true

# ── Zusammenfassung ──────────────────────────────────────────────────────────
echo ""
echo "=== Export fertig ==="
for mod in abpe_core abpe_ui email_studio abpe_crm abpe_meetme; do
  dir="${STAGING_ROOT}/${mod}/incoming"
  if [[ -d "$dir" ]]; then
    count=$(find "$dir" -type f | wc -l | tr -d ' ')
    echo "  ${mod}: ${count} Dateien — ${dir}"
  fi
done

echo ""
echo "Nächster Schritt:"
echo "  1) Dateien ins udoo-reprap-Repo kopieren (Repo_abpe/<modul>/incoming/)"
echo "  2) git add / commit / push"
echo "  3) Cloud Agent: 'Bitte Repo_abpe analysieren'"
