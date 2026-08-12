#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# Live → Repo: Matching/CRM/Shaduler/KI-Wiz von UCS5 ins Git ziehen
#
# 1) Sichert Live-Filesystem (timestamped tar unter /opt/abpe/backups/)
# 2) rsync Live → Repo_abpe/… (ohne Secrets/__pycache__/Backups)
# 3) Optional: commit + push
#
# Auf ucs5 (IMMER erst PULL, bevor Cloud/SYNC Live überschreibt):
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/matching-ki-anfrage-wizard-7f07
#   git checkout cursor/matching-ki-anfrage-wizard-7f07
#   git pull origin cursor/matching-ki-anfrage-wizard-7f07
#   bash <(git show origin/cursor/matching-ki-anfrage-wizard-7f07:scripts/PULL-matching-from-live.sh)
#   # oder mit Commit:
#   bash <(git show origin/cursor/matching-ki-anfrage-wizard-7f07:scripts/PULL-matching-from-live.sh) --push
#
# Danach Cloud-Agent auf DIESEM Stand weiterarbeiten.
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/matching-ki-anfrage-wizard-7f07}"
LIVE_CRM="${LIVE_CRM:-/opt/abpe/backend/apps/abpe_crm}"
LIVE_SH="${LIVE_SH:-/opt/abpe/backend/apps/abpe_shaduler}"
LIVE_KI="${LIVE_KI:-/opt/abpe/backend/apps/abpe_ki_wiz}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"
LIVE_MATCH="${LIVE_MATCH:-/opt/abpe/backend/apps/abpe_matching_workflow}"
STATICFILES="${STATICFILES:-/opt/abpe/backend/staticfiles}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/abpe/backups}"
DO_PUSH=0
for arg in "$@"; do
  case "$arg" in
    --push|--commit) DO_PUSH=1 ;;
    -h|--help)
      sed -n '2,25p' "$0" 2>/dev/null || true
      exit 0
      ;;
  esac
done

TS=$(date +%Y%m%d-%H%M%S)
echo "======== PULL Matching Live → Repo $TS ========"
echo "Repo: $REPO  Branch: $BRANCH  push=$DO_PUSH"

if [[ ! -d "$REPO/.git" ]]; then
  echo "FAIL: $REPO ist kein Git-Repo"
  exit 1
fi
for d in "$LIVE_CRM" "$LIVE_SH" "$LIVE_KI" "$LIVE_UI"; do
  if [[ ! -d "$d" ]]; then
    echo "FAIL: Live-Pfad fehlt: $d"
    exit 1
  fi
done

cd "$REPO"
git fetch origin "$BRANCH" 2>/dev/null || git fetch origin || true
if git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
  git checkout "$BRANCH"
elif git rev-parse --verify "origin/$BRANCH" >/dev/null 2>&1; then
  git checkout -B "$BRANCH" "origin/$BRANCH"
else
  echo "WARN: Branch $BRANCH fehlt — bleibe auf $(git branch --show-current)"
fi
git pull origin "$BRANCH" 2>/dev/null || true

# ── 0) Filesystem-Backup (vor jedem Pull) ───────────────────────────────────
echo
echo "=== 0) Live-Backup → $BACKUP_ROOT ==="
mkdir -p "$BACKUP_ROOT"
BAK_DIR="$BACKUP_ROOT/matching-live-$TS"
mkdir -p "$BAK_DIR"
# Manifest
{
  echo "ts=$TS"
  echo "host=$(hostname -f 2>/dev/null || hostname)"
  echo "branch=$BRANCH"
  date -Iseconds
  supervisorctl status abpe-django 2>/dev/null || true
} > "$BAK_DIR/MANIFEST.txt"

tar_one() {
  local name="$1" src="$2"
  if [[ ! -d "$src" ]]; then
    echo "  skip $name (fehlt)"
    return 0
  fi
  local out="$BAK_DIR/${name}.tar.gz"
  tar -czf "$out" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.session*' \
    -C "$(dirname "$src")" "$(basename "$src")"
  echo "  OK $out ($(du -h "$out" | awk '{print $1}'))"
}

tar_one abpe_crm "$LIVE_CRM"
tar_one abpe_shaduler "$LIVE_SH"
tar_one abpe_ki_wiz "$LIVE_KI"
# UI nur Matching/Shaduler-Module (nicht ganzes Portal)
if [[ -d "$LIVE_UI/static/abpe_ui/js/mod" ]]; then
  mkdir -p "$BAK_DIR/ui_mod"
  cp -a "$LIVE_UI/static/abpe_ui/js/mod/mod-matching.js" "$BAK_DIR/ui_mod/" 2>/dev/null || true
  cp -a "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler.js" "$BAK_DIR/ui_mod/" 2>/dev/null || true
  cp -a "$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css" "$BAK_DIR/ui_mod/" 2>/dev/null || true
  echo "  OK ui_mod/*.js/css"
fi
if [[ -d "$LIVE_MATCH" ]]; then
  tar_one abpe_matching_workflow "$LIVE_MATCH"
fi
# urls.py Snapshot (kritisch — oft neuer als Repo-Export)
if [[ -f "$LIVE_CRM/urls.py" ]]; then
  cp -a "$LIVE_CRM/urls.py" "$BAK_DIR/abpe_crm.urls.py"
fi
if [[ -f "$LIVE_CRM/views.py" ]]; then
  cp -a "$LIVE_CRM/views.py" "$BAK_DIR/abpe_crm.views.py"
fi
if [[ -f "$LIVE_CRM/models.py" ]]; then
  cp -a "$LIVE_CRM/models.py" "$BAK_DIR/abpe_crm.models.py"
fi
ln -sfn "$BAK_DIR" "$BACKUP_ROOT/matching-live-latest"
echo "OK Backup: $BAK_DIR (Symlink matching-live-latest)"

RSYNC_EXCLUDES=(
  --exclude '__pycache__/'
  --exclude '*.pyc'
  --exclude '*.pyo'
  --exclude '*.bak'
  --exclude '*.bak-*'
  --exclude '*.bak-before-matching-sync*'
  --exclude '.session*'
  --exclude '*password*'
  --exclude '*secret*'
  --exclude 'email_settings.json'
  --exclude '.git/'
)

# ── 1) CRM (voll — urls/views/models/templates/i18n/…) ─────────────────────
echo
echo "=== 1) abpe_crm Live → Repo ==="
DEST_CRM="$REPO/Repo_abpe/abpe_crm/incoming"
mkdir -p "$DEST_CRM"
# Repo-Backup vor Überschreiben
if [[ -d "$DEST_CRM" ]] && [[ -n "$(ls -A "$DEST_CRM" 2>/dev/null || true)" ]]; then
  mkdir -p "$REPO/_repo_backups"
  tar -czf "$REPO/_repo_backups/abpe_crm-incoming-before-pull-$TS.tar.gz" \
    -C "$REPO/Repo_abpe/abpe_crm" incoming 2>/dev/null || true
  echo "  Repo-Backup: _repo_backups/abpe_crm-incoming-before-pull-$TS.tar.gz"
fi
rsync -a "${RSYNC_EXCLUDES[@]}" "$LIVE_CRM/" "$DEST_CRM/"
# Terms-Migration behalten/ergänzen falls Live sie noch nicht hatte
mkdir -p "$DEST_CRM/migrations"
touch "$DEST_CRM/migrations/__init__.py"
if [[ ! -f "$DEST_CRM/migrations/0001_berater_verfuegbarkeit_konditionen.py" ]]; then
  if git -C "$REPO" cat-file -e "HEAD:Repo_abpe/abpe_crm/incoming/migrations/0001_berater_verfuegbarkeit_konditionen.py" 2>/dev/null; then
    git -C "$REPO" show "HEAD:Repo_abpe/abpe_crm/incoming/migrations/0001_berater_verfuegbarkeit_konditionen.py" \
      > "$DEST_CRM/migrations/0001_berater_verfuegbarkeit_konditionen.py"
    echo "  + Terms-Migration aus HEAD wiederhergestellt"
  fi
fi
echo "OK → $DEST_CRM ($(find "$DEST_CRM" -type f | wc -l) Dateien)"

# ── 2) Shaduler ────────────────────────────────────────────────────────────
echo
echo "=== 2) abpe_shaduler Live → Repo ==="
DEST_SH="$REPO/Repo_abpe/abpe_shaduler/incoming"
mkdir -p "$DEST_SH"
if [[ -d "$DEST_SH" ]] && [[ -n "$(ls -A "$DEST_SH" 2>/dev/null || true)" ]]; then
  mkdir -p "$REPO/_repo_backups"
  tar -czf "$REPO/_repo_backups/abpe_shaduler-incoming-before-pull-$TS.tar.gz" \
    -C "$REPO/Repo_abpe/abpe_shaduler" incoming 2>/dev/null || true
fi
# Migrationen auf Live nicht blind löschen: ohne --delete auf migrations/
rsync -a "${RSYNC_EXCLUDES[@]}" --exclude 'migrations/' "$LIVE_SH/" "$DEST_SH/"
mkdir -p "$DEST_SH/migrations"
if [[ -f "$LIVE_SH/migrations/__init__.py" ]]; then
  cp -n "$LIVE_SH/migrations/__init__.py" "$DEST_SH/migrations/__init__.py" 2>/dev/null || true
fi
# Live-Migrationen nachziehen (neu + geändert)
for mig in "$LIVE_SH"/migrations/0*.py; do
  [[ -f "$mig" ]] || continue
  cp -a "$mig" "$DEST_SH/migrations/$(basename "$mig")"
done
echo "OK → $DEST_SH"

# ── 3) KI-Wiz ──────────────────────────────────────────────────────────────
echo
echo "=== 3) abpe_ki_wiz Live → Repo ==="
DEST_KI="$REPO/Repo_abpe/abpe_ki_wiz/incoming"
mkdir -p "$DEST_KI"
rsync -a "${RSYNC_EXCLUDES[@]}" "$LIVE_KI/" "$DEST_KI/"
echo "OK → $DEST_KI"

# ── 4) Matching UI ─────────────────────────────────────────────────────────
echo
echo "=== 4) UI mod-matching / mod-shaduler ==="
DEST_UI="$REPO/Repo_abpe/abpe_ui/incoming"
mkdir -p "$DEST_UI/static_abpe_ui/js/mod" "$DEST_UI/static_abpe_ui/css/mod"

copy_ui() {
  local src="$1" dest="$2"
  if [[ -f "$src" ]]; then
    cp -a "$src" "$dest"
    echo "  + $(basename "$dest")  ($(wc -l < "$src") Z, $(stat -c %y "$src" 2>/dev/null | cut -d. -f1))"
  else
    echo "  FEHLT $src"
  fi
}

# Bevorzugt App-Static; Fallback staticfiles
for name in mod-matching.js mod-shaduler.js; do
  if [[ -f "$LIVE_UI/static/abpe_ui/js/mod/$name" ]]; then
    copy_ui "$LIVE_UI/static/abpe_ui/js/mod/$name" "$DEST_UI/$name"
    copy_ui "$LIVE_UI/static/abpe_ui/js/mod/$name" "$DEST_UI/static_abpe_ui/js/mod/$name"
  elif [[ -f "$STATICFILES/abpe_ui/js/mod/$name" ]]; then
    copy_ui "$STATICFILES/abpe_ui/js/mod/$name" "$DEST_UI/$name"
    copy_ui "$STATICFILES/abpe_ui/js/mod/$name" "$DEST_UI/static_abpe_ui/js/mod/$name"
  else
    echo "  FEHLT $name"
  fi
done
if [[ -f "$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css" ]]; then
  copy_ui "$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css" "$DEST_UI/mod-shaduler.css"
  copy_ui "$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css" "$DEST_UI/static_abpe_ui/css/mod/mod-shaduler.css"
elif [[ -f "$STATICFILES/abpe_ui/css/mod/mod-shaduler.css" ]]; then
  copy_ui "$STATICFILES/abpe_ui/css/mod/mod-shaduler.css" "$DEST_UI/mod-shaduler.css"
  copy_ui "$STATICFILES/abpe_ui/css/mod/mod-shaduler.css" "$DEST_UI/static_abpe_ui/css/mod/mod-shaduler.css"
fi

# ── 5) Matching-Workflow (live-only, falls vorhanden) ──────────────────────
echo
echo "=== 5) abpe_matching_workflow (optional) ==="
if [[ -d "$LIVE_MATCH" ]]; then
  DEST_M="$REPO/Repo_abpe/abpe_matching_workflow/incoming"
  mkdir -p "$DEST_M"
  rsync -a "${RSYNC_EXCLUDES[@]}" "$LIVE_MATCH/" "$DEST_M/"
  echo "OK → $DEST_M"
else
  echo "skip (Live-App nicht vorhanden — ok)"
fi

# ── 6) Sanity / Feature-Report ──────────────────────────────────────────────
echo
echo "=== 6) Feature-Report ==="
check() {
  local label="$1" file="$2" pat="$3"
  if [[ -f "$file" ]] && grep -q -- "$pat" "$file"; then
    echo "  OK  $label"
  else
    echo "  FEHLT $label  ($file ~ $pat)"
  fi
}
check "CRM urls.py" "$DEST_CRM/urls.py" "api_contacts_suggest\|api_berater"
check "CRM views api_contacts_suggest" "$DEST_CRM/views.py" "def api_contacts_suggest"
check "CRM views api_berater_cv" "$DEST_CRM/views.py" "def api_berater_cv"
check "CRM Terms satz_remote" "$DEST_CRM/views.py" "satz_remote_c"
check "CRM Terms defer" "$DEST_CRM/views.py" "_CRM_TERMS_DEFER"
check "CRM models Terms" "$DEST_CRM/models.py" "verfuegbar_tage_pro_woche_c"
check "Shaduler MatchingBeraterTerms" "$DEST_SH/models.py" "class MatchingBeraterTerms"
check "Shaduler api_matching_terms" "$DEST_SH/views.py" "def api_matching_terms"
check "UI saveMatchTerms" "$DEST_UI/mod-matching.js" "saveMatchTerms"
check "UI phone_raw" "$DEST_UI/mod-matching.js" "phone_raw"
check "KI matching_anfrage" "$DEST_KI/prompt_defaults.py" "wiz_matching_anfrage_generate"

# ── Stamp: SYNC darf nur nach frischem Live-Pull laufen ─────────────────────
STAMP="$REPO/Repo_abpe/.live-pull-stamp"
{
  echo "ts=$TS"
  echo "iso=$(date -Iseconds)"
  echo "host=$(hostname -f 2>/dev/null || hostname)"
  echo "branch=$(git -C "$REPO" branch --show-current 2>/dev/null || echo '?')"
  echo "backup=$BAK_DIR"
  echo "crm_views_lines=$(wc -l < "$DEST_CRM/views.py" 2>/dev/null || echo 0)"
  echo "crm_has_contacts_suggest=$(grep -c 'def api_contacts_suggest' "$DEST_CRM/views.py" 2>/dev/null || echo 0)"
  echo "crm_has_berater_cv=$(grep -c 'def api_berater_cv' "$DEST_CRM/views.py" 2>/dev/null || echo 0)"
  echo "ui_has_fillSkills=$(grep -c 'fillSkillsFromText' "$DEST_UI/mod-matching.js" 2>/dev/null || echo 0)"
  echo "ui_has_saveMatchTerms=$(grep -c 'saveMatchTerms' "$DEST_UI/mod-matching.js" 2>/dev/null || echo 0)"
} > "$STAMP"
echo "OK Stamp → $STAMP"

# .gitignore für Backups im Share
GITIGNORE="$REPO/.gitignore"
touch "$GITIGNORE"
grep -qxF '_repo_backups/' "$GITIGNORE" 2>/dev/null || echo '_repo_backups/' >> "$GITIGNORE"
grep -qxF '_live_backups/' "$GITIGNORE" 2>/dev/null || echo '_live_backups/' >> "$GITIGNORE"

echo
echo "=== git status (Auszug) ==="
git -C "$REPO" status -sb | head -40
git -C "$REPO" diff --stat | tail -20 || true

if [[ "$DO_PUSH" -eq 1 ]]; then
  echo
  echo "=== commit + push ==="
  git -C "$REPO" add \
    Repo_abpe/abpe_crm \
    Repo_abpe/abpe_shaduler \
    Repo_abpe/abpe_ki_wiz \
    Repo_abpe/abpe_ui \
    Repo_abpe/abpe_matching_workflow \
    Repo_abpe/.live-pull-stamp \
    .gitignore \
    2>/dev/null || true
  if git -C "$REPO" diff --cached --quiet; then
    # Stamp trotzdem committen falls nur Stamp neu
    git -C "$REPO" add Repo_abpe/.live-pull-stamp 2>/dev/null || true
    if git -C "$REPO" diff --cached --quiet; then
      echo "Nichts zu committen (Working tree = Live?)."
    else
      git -C "$REPO" commit -m "pull(live): Matching/CRM/Shaduler/KI Stand von ucs5 ($TS)"
      git -C "$REPO" push -u origin "$(git -C "$REPO" branch --show-current)"
      echo "OK gepusht"
    fi
  else
    git -C "$REPO" commit -m "pull(live): Matching/CRM/Shaduler/KI Stand von ucs5 ($TS)"
    git -C "$REPO" push -u origin "$(git -C "$REPO" branch --show-current)"
    echo "OK gepusht"
  fi
else
  echo
  echo "======== Fertig: Dateien im Repo, noch NICHT committed ========"
  echo "Prüfen:"
  echo "  cd $REPO && git status -sb && git diff --stat | head"
  echo
  echo "Committen + pushen (wichtig — Cloud-Agent braucht den Push):"
  echo "  git add Repo_abpe/abpe_crm Repo_abpe/abpe_shaduler Repo_abpe/abpe_ki_wiz Repo_abpe/abpe_ui"
  echo "  git add Repo_abpe/abpe_matching_workflow Repo_abpe/.live-pull-stamp 2>/dev/null || true"
  echo "  git commit -m 'pull(live): Matching/CRM/Shaduler/KI Stand von ucs5'"
  echo "  git push -u origin $BRANCH"
  echo
  echo "Oder erneut mit --push:"
  echo "  bash scripts/PULL-matching-from-live.sh --push"
fi

echo
echo "Live-Backup bleibt unter: $BAK_DIR"
echo "Rollback Live z.B.:"
echo "  tar -xzf $BAK_DIR/abpe_crm.tar.gz -C /opt/abpe/backend/apps/"
echo "======== Ende PULL ========"
echo
echo ">>> Nächster Schritt für Cloud-Agent: git pull auf dem Branch,"
echo ">>> DANN erst wieder Features. SYNC ohne Stamp → Abbruch."
