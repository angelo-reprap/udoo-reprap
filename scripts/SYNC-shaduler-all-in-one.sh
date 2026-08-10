#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# EINZIGER Shaduler-Voll-Deploy — Aufgaben + Kalender + Posteingang + Radar
#
# Problem bisher: Teil-SYNC (nur Radar / nur Matching / nur Posteingang)
# überschreibt mod-shaduler.js und löscht Buttons wie „Neue Aufgabe“.
#
# Immer DIESEN Branch/Script verwenden:
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/shaduler-all-in-one-7f07
#   bash <(git show origin/cursor/shaduler-all-in-one-7f07:scripts/SYNC-shaduler-all-in-one.sh)
#
# Enthält:
#   • Neue Aufgabe / Neuer Eintrag (Kalender)
#   • Posteingang Soft-Poll + email_index 3 Min + namazu prune-guard
#   • Radar Anfragen async 3 Min + Sort Publikationsdatum
#   • Radar Berater FM Aktuellste + ↻ = Verfügbare
#   • abpe-scheduler-loop ENSURE (autostart/autorestart)
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-origin/cursor/shaduler-all-in-one-7f07}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
PYBIN="${PYBIN:-/opt/abpe/venv311/bin/python}"
LIVE_SH="${LIVE_SH:-/opt/abpe/backend/apps/abpe_shaduler}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"
LIVE_NAMAZU_CMD="${LIVE_NAMAZU_CMD:-/opt/abpe/backend/apps/namazu/management/commands}"
STATICFILES="${STATICFILES:-/opt/abpe/backend/staticfiles}"

echo "======== SYNC shaduler-all-in-one $(date -Iseconds) ========"
echo "Branch: $BRANCH"
echo "WARNUNG: Andere SYNC-*-Skripte (nur Matching/Radar/Posteingang) NICHT danach ausführen!"
echo

cd "$REPO"
git fetch origin cursor/shaduler-all-in-one-7f07 || true

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git archive "$BRANCH" \
  Repo_abpe/abpe_shaduler/incoming \
  Repo_abpe/abpe_ui/incoming \
  Repo_abpe/namazu/incoming/management/commands/index_emails.py \
  Repo_abpe/abpe_scheduler/incoming/management/commands/scheduler_loop.py \
  | tar -x -C "$TMP"

# Guard: kritische Features müssen im Archive sein
need_strings=(
  "Neue Aufgabe"
  "Neuer Eintrag"
  "startRadarPoll"
  "startRadarBPoll"
  "mostRecentProfiles"
  "radar_poll_run"
)
for s in "${need_strings[@]}"; do
  if ! grep -Rq -- "$s" "$TMP/Repo_abpe" 2>/dev/null; then
    echo "FEHLER: Feature-Marker fehlt im Branch: $s"
    echo "  → falscher Branch oder kaputter Merge. Abbruch (Live unberührt)."
    exit 1
  fi
done
echo "OK — Feature-Guards bestanden (Aufgaben/Kalender/Radar/Posteingang)"

# ── abpe_shaduler (ohne Live-Migrationen zu löschen) ───────────────────────
mkdir -p "$LIVE_SH"
rsync -a \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude 'migrations/' \
  "$TMP/Repo_abpe/abpe_shaduler/incoming/" \
  "$LIVE_SH/"
# neue Migrationen gezielt nachziehen
mkdir -p "$LIVE_SH/migrations"
if [[ -d "$TMP/Repo_abpe/abpe_shaduler/incoming/migrations" ]]; then
  rsync -a \
    --ignore-existing \
    --exclude '__pycache__/' \
    "$TMP/Repo_abpe/abpe_shaduler/incoming/migrations/" \
    "$LIVE_SH/migrations/" || true
fi
find "$LIVE_SH" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
echo "OK — abpe_shaduler → $LIVE_SH"

# ── UI (mod-shaduler + kalender + i18n) ─────────────────────────────────────
mkdir -p "$LIVE_UI/templates/abpe_ui/modules/shaduler"
mkdir -p "$LIVE_UI/static/abpe_ui/css/mod" "$LIVE_UI/static/abpe_ui/js/mod"
if [[ -f "$TMP/Repo_abpe/abpe_ui/incoming/modules/shaduler/module.json" ]]; then
  cp -a "$TMP/Repo_abpe/abpe_ui/incoming/modules/shaduler/module.json" \
    "$LIVE_UI/templates/abpe_ui/modules/shaduler/module.json"
fi
cp -a "$TMP/Repo_abpe/abpe_ui/incoming/mod-shaduler.css" \
  "$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css"
cp -a "$TMP/Repo_abpe/abpe_ui/incoming/mod-shaduler.js" \
  "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler.js"
cp -a "$TMP/Repo_abpe/abpe_ui/incoming/mod-shaduler-kalender.js" \
  "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler-kalender.js"

# staticfiles (Browser-Cache-Pfad)
if [[ -d "$STATICFILES" ]]; then
  mkdir -p "$STATICFILES/abpe_ui/css/mod" "$STATICFILES/abpe_ui/js/mod"
  cp -a "$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css" \
    "$STATICFILES/abpe_ui/css/mod/mod-shaduler.css"
  cp -a "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler.js" \
    "$STATICFILES/abpe_ui/js/mod/mod-shaduler.js"
  cp -a "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler-kalender.js" \
    "$STATICFILES/abpe_ui/js/mod/mod-shaduler-kalender.js"
  echo "OK — auch nach $STATICFILES kopiert"
fi

for lang in de en; do
  if [[ -d "$TMP/Repo_abpe/abpe_ui/incoming/i18n/$lang/modules/shaduler" ]]; then
    mkdir -p "$LIVE_UI/static/abpe_ui/i18n/$lang/modules/shaduler"
    cp -a "$TMP/Repo_abpe/abpe_ui/incoming/i18n/$lang/modules/shaduler/." \
      "$LIVE_UI/static/abpe_ui/i18n/$lang/modules/shaduler/"
    if [[ -d "$STATICFILES" ]]; then
      mkdir -p "$STATICFILES/abpe_ui/i18n/$lang/modules/shaduler"
      cp -a "$LIVE_UI/static/abpe_ui/i18n/$lang/modules/shaduler/." \
        "$STATICFILES/abpe_ui/i18n/$lang/modules/shaduler/" 2>/dev/null || true
    fi
  fi
done
echo "OK — UI Shaduler"

# Guard Live: Buttons müssen angekommen sein
if ! grep -q 'Neue Aufgabe' "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler.js"; then
  echo "FEHLER: Live mod-shaduler.js ohne „Neue Aufgabe“ — Abbruch vor Restart"
  exit 1
fi
if ! grep -q 'Neuer Eintrag' "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler-kalender.js"; then
  echo "FEHLER: Live kalender.js ohne „Neuer Eintrag“ — Abbruch vor Restart"
  exit 1
fi
echo "OK — Live-Guards (Neue Aufgabe / Neuer Eintrag)"

# ── namazu index_emails (Passwörter unberührt) ─────────────────────────────
if [[ -f "$TMP/Repo_abpe/namazu/incoming/management/commands/index_emails.py" ]]; then
  mkdir -p "$LIVE_NAMAZU_CMD"
  if [[ -f "$LIVE_NAMAZU_CMD/index_emails.py" ]]; then
    cp -a "$LIVE_NAMAZU_CMD/index_emails.py" \
      "$LIVE_NAMAZU_CMD/index_emails.py.bak.$(date +%Y%m%d_%H%M%S)"
  fi
  cp -a "$TMP/Repo_abpe/namazu/incoming/management/commands/index_emails.py" \
    "$LIVE_NAMAZU_CMD/index_emails.py"
  echo "OK — namazu index_emails (email_settings.json NICHT angefasst)"
fi

# ── scheduler_loop ─────────────────────────────────────────────────────────
LIVE_SCHED_CMD="${LIVE_SCHED_CMD:-/opt/abpe/backend/apps/abpe_scheduler/management/commands}"
if [[ -f "$TMP/Repo_abpe/abpe_scheduler/incoming/management/commands/scheduler_loop.py" ]]; then
  mkdir -p "$LIVE_SCHED_CMD"
  cp -a "$TMP/Repo_abpe/abpe_scheduler/incoming/management/commands/scheduler_loop.py" \
    "$LIVE_SCHED_CMD/scheduler_loop.py"
  echo "OK — scheduler_loop.py"
fi

# ── Jobs + Loop ────────────────────────────────────────────────────────────
echo
echo "=== register_scheduler_jobs ==="
cd "$BACKEND"
"$PYBIN" manage.py migrate abpe_shaduler --noinput 2>/dev/null || true
"$PYBIN" manage.py register_scheduler_jobs || true
"$PYBIN" manage.py radar_dedupe_sources --apply 2>/dev/null || true
"$PYBIN" manage.py radar_fix_published_dates --apply 2>/dev/null || true

echo
echo "=== ENSURE abpe-scheduler-loop ==="
bash <(git -C "$REPO" show "$BRANCH:scripts/ENSURE-abpe-scheduler-loop.sh") || true

echo
supervisorctl restart abpe-django abpe-celery
sleep 2
supervisorctl start abpe-scheduler-loop 2>/dev/null || true
supervisorctl status abpe-django abpe-celery abpe-scheduler-loop

echo
echo "======== FERTIG ========"
echo "Browser: Ctrl+F5"
echo "Prüfen: Aufgaben → „Neue Aufgabe“ | Kalender → „Neuer Eintrag“ | Posteingang | Radar"
echo
echo "NICHT mehr verwenden (überschreiben Features):"
echo "  SYNC-radar-anfragen-frisch.sh  SYNC-matching-ki-anfrage-wizard.sh  allein"
echo "  → immer SYNC-shaduler-all-in-one.sh"
