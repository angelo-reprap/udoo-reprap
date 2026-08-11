#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# Live → Repo: aktuellen UCS5-Stand von Shaduler in den Git-Share ziehen
#
# Warum: Ohne diesen Schritt überschreiben Cloud-Fixes den Live-Stand blind
# und löschen Features („Neue Aufgabe“ weg nach Radar-SYNC).
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/shaduler-all-in-one-7f07
#   git checkout cursor/shaduler-all-in-one-7f07
#   git pull origin cursor/shaduler-all-in-one-7f07
#   bash <(git show origin/cursor/shaduler-all-in-one-7f07:scripts/PULL-shaduler-from-live.sh)
#   git status
#   git add -A && git commit -m "pull(live): Shaduler Stand von ucs5" && git push
#
# Danach Cloud-Agent arbeitet auf DIESEM Stand weiter.
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/shaduler-all-in-one-7f07}"
LIVE_SH="${LIVE_SH:-/opt/abpe/backend/apps/abpe_shaduler}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"
LIVE_NAMAZU_CMD="${LIVE_NAMAZU_CMD:-/opt/abpe/backend/apps/namazu/management/commands}"
LIVE_SCHED_CMD="${LIVE_SCHED_CMD:-/opt/abpe/backend/apps/abpe_scheduler/management/commands}"
STATICFILES="${STATICFILES:-/opt/abpe/backend/staticfiles}"

echo "======== PULL Shaduler Live → Repo $(date -Iseconds) ========"
echo "Repo: $REPO  Branch: $BRANCH"

if [[ ! -d "$REPO/.git" ]]; then
  echo "FAIL: $REPO ist kein Git-Repo"
  exit 1
fi
if [[ ! -d "$LIVE_SH" ]]; then
  echo "FAIL: $LIVE_SH fehlt"
  exit 1
fi

cd "$REPO"
git fetch origin "$BRANCH" 2>/dev/null || git fetch origin || true
# Branch sicherstellen
if git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
  git checkout "$BRANCH"
elif git rev-parse --verify "origin/$BRANCH" >/dev/null 2>&1; then
  git checkout -B "$BRANCH" "origin/$BRANCH"
else
  echo "WARN: Branch $BRANCH fehlt — bleibe auf $(git branch --show-current)"
fi

DEST_SH="$REPO/Repo_abpe/abpe_shaduler/incoming"
DEST_UI="$REPO/Repo_abpe/abpe_ui/incoming"
mkdir -p "$DEST_SH" "$DEST_UI"

# ── 1) abpe_shaduler App ───────────────────────────────────────────────────
echo
echo "=== 1) abpe_shaduler ==="
rsync -a \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '*.bak*' \
  --exclude '.session*' \
  --exclude '*password*' \
  --exclude '*secret*' \
  --exclude 'email_settings.json' \
  "$LIVE_SH/" "$DEST_SH/"
echo "OK → $DEST_SH"

# ── 2) UI: App-Static + ggf. staticfiles falls neuer ───────────────────────
echo
echo "=== 2) UI mod-shaduler* ==="
mkdir -p "$DEST_UI/static_abpe_ui/js/mod" "$DEST_UI/static_abpe_ui/css/mod"

copy_ui() {
  local src="$1" name="$2"
  if [[ -f "$src" ]]; then
    cp -a "$src" "$DEST_UI/$name"
    echo "  + $name  ($(wc -l < "$src") Zeilen, mtime=$(stat -c %y "$src" 2>/dev/null | cut -d. -f1))"
    return 0
  fi
  return 1
}

# Bevorzuge App-Static; wenn staticfiles neuer → die nehmen
pick_newer() {
  local a="$1" b="$2"
  if [[ -f "$a" && -f "$b" ]]; then
    if [[ "$b" -nt "$a" ]]; then echo "$b"; else echo "$a"; fi
  elif [[ -f "$a" ]]; then echo "$a"
  elif [[ -f "$b" ]]; then echo "$b"
  else echo ""; fi
}

JS=$(pick_newer \
  "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler.js" \
  "$STATICFILES/abpe_ui/js/mod/mod-shaduler.js")
CSS=$(pick_newer \
  "$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css" \
  "$STATICFILES/abpe_ui/css/mod/mod-shaduler.css")
KAL=$(pick_newer \
  "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler-kalender.js" \
  "$STATICFILES/abpe_ui/js/mod/mod-shaduler-kalender.js")

[[ -n "$JS" ]] && cp -a "$JS" "$DEST_UI/mod-shaduler.js" \
  && cp -a "$JS" "$DEST_UI/static_abpe_ui/js/mod/mod-shaduler.js" \
  && echo "  + mod-shaduler.js ← $JS"
[[ -n "$CSS" ]] && cp -a "$CSS" "$DEST_UI/mod-shaduler.css" \
  && cp -a "$CSS" "$DEST_UI/static_abpe_ui/css/mod/mod-shaduler.css" \
  && echo "  + mod-shaduler.css ← $CSS"
[[ -n "$KAL" ]] && cp -a "$KAL" "$DEST_UI/mod-shaduler-kalender.js" \
  && cp -a "$KAL" "$DEST_UI/static_abpe_ui/js/mod/mod-shaduler-kalender.js" \
  && echo "  + mod-shaduler-kalender.js ← $KAL"

# module.json + i18n
if [[ -f "$LIVE_UI/templates/abpe_ui/modules/shaduler/module.json" ]]; then
  mkdir -p "$DEST_UI/modules/shaduler"
  cp -a "$LIVE_UI/templates/abpe_ui/modules/shaduler/module.json" \
    "$DEST_UI/modules/shaduler/module.json"
  echo "  + modules/shaduler/module.json"
fi
# Alle Portal-Sprachen (nicht nur de/en)
if [[ -d "$LIVE_UI/static/abpe_ui/i18n" ]]; then
  for lang_dir in "$LIVE_UI/static/abpe_ui/i18n"/*; do
    [[ -d "$lang_dir" ]] || continue
    lang=$(basename "$lang_dir")
    src="$lang_dir/modules/shaduler"
    if [[ -d "$src" ]]; then
      mkdir -p "$DEST_UI/i18n/$lang/modules/shaduler"
      mkdir -p "$DEST_UI/static_abpe_ui/i18n/$lang/modules/shaduler"
      cp -a "$src/." "$DEST_UI/i18n/$lang/modules/shaduler/"
      cp -a "$src/." "$DEST_UI/static_abpe_ui/i18n/$lang/modules/shaduler/"
      echo "  + i18n/$lang/modules/shaduler"
    fi
  done
fi

# ── 3) namazu index_emails (keine Passwörter) ──────────────────────────────
echo
echo "=== 3) namazu index_emails ==="
DEST_N="$REPO/Repo_abpe/namazu/incoming/management/commands"
mkdir -p "$DEST_N"
if [[ -f "$LIVE_NAMAZU_CMD/index_emails.py" ]]; then
  cp -a "$LIVE_NAMAZU_CMD/index_emails.py" "$DEST_N/index_emails.py"
  echo "OK → index_emails.py"
else
  echo "WARN: $LIVE_NAMAZU_CMD/index_emails.py fehlt"
fi
# email_settings nur redacted
if [[ -f "$LIVE_NAMAZU_CMD/email_settings.json" ]]; then
  python3 - "$LIVE_NAMAZU_CMD/email_settings.json" "$DEST_N/email_settings.json" <<'PY'
import json, sys
src, dst = sys.argv[1], sys.argv[2]
data = json.load(open(src, encoding='utf-8'))
accs = data.get('accounts') or {}
if isinstance(accs, dict):
    for k, v in list(accs.items()):
        if isinstance(v, dict) and 'password' in v:
            v = dict(v)
            v['password'] = '***REDACTED***'
            accs[k] = v
json.dump(data, open(dst, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('OK → email_settings.json (passwords redacted)')
PY
fi

# ── 4) scheduler_loop ──────────────────────────────────────────────────────
echo
echo "=== 4) scheduler_loop ==="
DEST_S="$REPO/Repo_abpe/abpe_scheduler/incoming/management/commands"
mkdir -p "$DEST_S"
if [[ -f "$LIVE_SCHED_CMD/scheduler_loop.py" ]]; then
  cp -a "$LIVE_SCHED_CMD/scheduler_loop.py" "$DEST_S/scheduler_loop.py"
  touch "$DEST_S/__init__.py" "$DEST_S/../__init__.py" 2>/dev/null || true
  echo "OK → scheduler_loop.py"
else
  echo "WARN: scheduler_loop.py fehlt auf Live"
fi

# ── 5) Feature-Report (was Live wirklich hat) ──────────────────────────────
echo
echo "=== 5) Feature-Report (Live / Repo-Kopie) ==="
check() {
  local label="$1" file="$2" pat="$3"
  if [[ -f "$file" ]] && grep -q -- "$pat" "$file"; then
    echo "  OK  $label"
  else
    echo "  FEHLT $label  ($file ~ $pat)"
  fi
}
check "Neue Aufgabe" "$DEST_UI/mod-shaduler.js" "Neue Aufgabe"
check "Neuer Eintrag" "$DEST_UI/mod-shaduler-kalender.js" "Neuer Eintrag"
check "Radar Soft-Poll" "$DEST_UI/mod-shaduler.js" "startRadarPoll"
check "Berater Soft-Poll" "$DEST_UI/mod-shaduler.js" "startRadarBPoll"
check "FM Aktuellste" "$DEST_SH/services/radar_berater_fl.py" "mostRecentProfiles"
check "radar_poll async" "$DEST_SH/tasks.py" "radar_poll_run"
check "email_index job" "$DEST_SH/management/commands/register_scheduler_jobs.py" "email_index"

echo
echo "=== Supervisor ==="
supervisorctl status abpe-django abpe-celery abpe-scheduler-loop 2>/dev/null || true

echo
echo "======== Fertig: Dateien im Repo, noch NICHT committed ========"
echo "Prüfen:"
echo "  cd $REPO && git status -sb && git diff --stat | head"
echo
echo "Dann committen + pushen:"
echo "  git add Repo_abpe/abpe_shaduler Repo_abpe/abpe_ui Repo_abpe/namazu Repo_abpe/abpe_scheduler"
echo "  git commit -m 'pull(live): Shaduler Stand von ucs5'"
echo "  git push -u origin $BRANCH"
echo
echo "Danach dem Agenten sagen: Live-Stand ist gepusht — weiter darauf arbeiten."
