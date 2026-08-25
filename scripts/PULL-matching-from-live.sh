#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# Live → Repo: Matching/CRM/Shaduler/KI-Wiz von UCS5 ins Git ziehen
#
# Schnell (Default):
#   - Nur kritische Dateien sichern (~KB, kein 1.4G CRM-Tar)
#   - rsync ohne node_modules / softphone-electron / Symlinks
#   - optional --push
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/matching-shortlist-weights-1532
#   bash <(git show origin/cursor/matching-shortlist-weights-1532:scripts/LIVE-FIRST-pull.sh)
#
# Flags:
#   --push           commit + push nach Pull
#   --no-backup      gar kein Backup
#   --full-backup    schwere App-Tars (langsam, nur Notfall)
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-cursor/matching-shortlist-weights-1532}"
LIVE_CRM="${LIVE_CRM:-/opt/abpe/backend/apps/abpe_crm}"
LIVE_SH="${LIVE_SH:-/opt/abpe/backend/apps/abpe_shaduler}"
LIVE_KI="${LIVE_KI:-/opt/abpe/backend/apps/abpe_ki_wiz}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"
LIVE_MATCH="${LIVE_MATCH:-/opt/abpe/backend/apps/abpe_matching_workflow}"
STATICFILES="${STATICFILES:-/opt/abpe/backend/staticfiles}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/abpe/backups}"
DO_PUSH=0
DO_BACKUP=1
FULL_BACKUP=0
for arg in "$@"; do
  case "$arg" in
    --push|--commit) DO_PUSH=1 ;;
    --no-backup) DO_BACKUP=0 ;;
    --full-backup) FULL_BACKUP=1 ;;
    -h|--help)
      sed -n '2,22p' "$0" 2>/dev/null || true
      exit 0
      ;;
  esac
done

TS=$(date +%Y%m%d-%H%M%S)
echo "======== PULL Matching Live → Repo $TS ========"
echo "Repo: $REPO  Branch: $BRANCH  push=$DO_PUSH  backup=$DO_BACKUP full=$FULL_BACKUP"

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

BAK_DIR=""
# ── 0) Leichtes Backup (Default) — KEINE 1.4G CRM-Tars ─────────────────────
if [[ "$DO_BACKUP" -eq 1 ]]; then
  echo
  echo "=== 0) Leichtes Live-Backup → $BACKUP_ROOT (nur kritische Dateien) ==="
  mkdir -p "$BACKUP_ROOT"
  BAK_DIR="$BACKUP_ROOT/matching-live-$TS"
  mkdir -p "$BAK_DIR/crm" "$BAK_DIR/shaduler" "$BAK_DIR/ki_wiz" "$BAK_DIR/ui_mod"
  {
    echo "ts=$TS"
    echo "host=$(hostname -f 2>/dev/null || hostname)"
    echo "branch=$BRANCH"
    echo "mode=$([ "$FULL_BACKUP" -eq 1 ] && echo full || echo light)"
    date -Iseconds
    supervisorctl status abpe-django 2>/dev/null || true
  } > "$BAK_DIR/MANIFEST.txt"

  # Kritische Einzeldateien (schnell, klein)
  for f in urls.py views.py models.py apps.py admin.py; do
    [[ -f "$LIVE_CRM/$f" ]] && cp -a "$LIVE_CRM/$f" "$BAK_DIR/crm/$f" || true
    [[ -f "$LIVE_SH/$f" ]] && cp -a "$LIVE_SH/$f" "$BAK_DIR/shaduler/$f" || true
    [[ -f "$LIVE_KI/$f" ]] && cp -a "$LIVE_KI/$f" "$BAK_DIR/ki_wiz/$f" || true
  done
  [[ -f "$LIVE_KI/prompt_defaults.py" ]] && cp -a "$LIVE_KI/prompt_defaults.py" "$BAK_DIR/ki_wiz/" || true
  for name in mod-matching.js mod-shaduler.js; do
    [[ -f "$LIVE_UI/static/abpe_ui/js/mod/$name" ]] \
      && cp -a "$LIVE_UI/static/abpe_ui/js/mod/$name" "$BAK_DIR/ui_mod/" || true
  done
  [[ -f "$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css" ]] \
    && cp -a "$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css" "$BAK_DIR/ui_mod/" || true

  if [[ "$FULL_BACKUP" -eq 1 ]]; then
    echo "  (full-backup: schwere Tars — langsam)"
    tar_one() {
      local name="$1" src="$2"
      [[ -d "$src" ]] || return 0
      local out="$BAK_DIR/${name}.tar.gz"
      tar -czf "$out" \
        --exclude='__pycache__' --exclude='*.pyc' --exclude='.session*' \
        --exclude='node_modules' --exclude='softphone-electron' \
        -C "$(dirname "$src")" "$(basename "$src")" 2>/dev/null \
        || tar -czf "$out" \
          --exclude='__pycache__' --exclude='*.pyc' \
          --exclude='node_modules' --exclude='softphone-electron' \
          -C "$(dirname "$src")" "$(basename "$src")"
      echo "  OK $out ($(du -h "$out" | awk '{print $1}'))"
    }
    tar_one abpe_crm "$LIVE_CRM"
    tar_one abpe_shaduler "$LIVE_SH"
    tar_one abpe_ki_wiz "$LIVE_KI"
    [[ -d "$LIVE_MATCH" ]] && tar_one abpe_matching_workflow "$LIVE_MATCH"
  fi

  ln -sfn "$BAK_DIR" "$BACKUP_ROOT/matching-live-latest" 2>/dev/null || true
  echo "OK Backup: $BAK_DIR ($(du -sh "$BAK_DIR" 2>/dev/null | awk '{print $1}'))"
  echo "  (Rollback z.B.: cp -a $BAK_DIR/crm/views.py $LIVE_CRM/views.py)"
else
  echo
  echo "=== 0) Backup übersprungen (--no-backup) ==="
fi

# /mnt/public ist oft CIFS/NFS → keine Symlinks. node_modules nie mitziehen.
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
  --exclude 'node_modules/'
  --exclude 'softphone-electron/'
  --exclude 'static/softphone-electron/'
  --exclude '.bin/'
  --exclude '*.map'
)

# rsync: keine Symlinks auf Share; Exit 23 (partial) nicht fatal wenn Kern da
rsync_safe() {
  local src="$1" dest="$2"
  shift 2 || true
  set +e
  rsync -a --no-links "${RSYNC_EXCLUDES[@]}" "$@" "$src" "$dest"
  local rc=$?
  set -e
  # 0=ok, 23=partial (Symlinks/Attrs) — ok wenn Zieldateien da
  if [[ "$rc" -eq 0 || "$rc" -eq 23 ]]; then
    return 0
  fi
  echo "FEHLER: rsync exit $rc ($src → $dest)"
  return "$rc"
}

# ── 1) CRM (ohne softphone/node_modules) ───────────────────────────────────
echo
echo "=== 1) abpe_crm Live → Repo ==="
DEST_CRM="$REPO/Repo_abpe/abpe_crm/incoming"
mkdir -p "$DEST_CRM"
if [[ -d "$DEST_CRM" ]] && [[ -n "$(ls -A "$DEST_CRM" 2>/dev/null || true)" ]]; then
  mkdir -p "$REPO/_repo_backups"
  # leicht: nur views/urls/models, kein Full-Tar von softphone
  tar -czf "$REPO/_repo_backups/abpe_crm-core-before-pull-$TS.tar.gz" \
    -C "$DEST_CRM" urls.py views.py models.py 2>/dev/null || true
fi
rsync_safe "$LIVE_CRM/" "$DEST_CRM/"
mkdir -p "$DEST_CRM/migrations"
touch "$DEST_CRM/migrations/__init__.py"
# Kern prüfen
for must in urls.py views.py models.py; do
  if [[ ! -f "$DEST_CRM/$must" ]]; then
    echo "FEHLER: $DEST_CRM/$must fehlt nach rsync"
    exit 1
  fi
done
echo "OK → $DEST_CRM (views=$(wc -l < "$DEST_CRM/views.py") Z)"

# ── 2) Shaduler ────────────────────────────────────────────────────────────
echo
echo "=== 2) abpe_shaduler Live → Repo ==="
DEST_SH="$REPO/Repo_abpe/abpe_shaduler/incoming"
mkdir -p "$DEST_SH"
rsync_safe "$LIVE_SH/" "$DEST_SH/" --exclude 'migrations/'
mkdir -p "$DEST_SH/migrations"
[[ -f "$LIVE_SH/migrations/__init__.py" ]] \
  && cp -n "$LIVE_SH/migrations/__init__.py" "$DEST_SH/migrations/__init__.py" 2>/dev/null || true
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
rsync_safe "$LIVE_KI/" "$DEST_KI/"
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
    echo "  + $(basename "$dest")  ($(wc -l < "$src") Z)"
  else
    echo "  FEHLT $src"
  fi
}

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

# ── 5) Matching-Workflow (optional) ────────────────────────────────────────
echo
echo "=== 5) abpe_matching_workflow (optional) ==="
if [[ -d "$LIVE_MATCH" ]]; then
  DEST_M="$REPO/Repo_abpe/abpe_matching_workflow/incoming"
  mkdir -p "$DEST_M"
  rsync_safe "$LIVE_MATCH/" "$DEST_M/"
  echo "OK → $DEST_M"
else
  echo "skip (Live-App nicht vorhanden — ok)"
fi

# ── 6) Feature-Report ──────────────────────────────────────────────────────
echo
echo "=== 6) Feature-Report ==="
check() {
  local label="$1" file="$2" pat="$3"
  if [[ -f "$file" ]] && grep -qE -- "$pat" "$file"; then
    echo "  OK  $label"
  else
    echo "  FEHLT $label  ($file ~ $pat)"
  fi
}
check "CRM urls.py" "$DEST_CRM/urls.py" "api_contacts_suggest|api_berater"
check "CRM views api_contacts_suggest" "$DEST_CRM/views.py" "def api_contacts_suggest"
check "CRM views api_berater_cv" "$DEST_CRM/views.py" "def api_berater_cv"
check "CRM Terms satz_remote" "$DEST_CRM/views.py" "satz_remote_c"
check "Shaduler MatchingBeraterTerms" "$DEST_SH/models.py" "class MatchingBeraterTerms"
check "UI saveMatchTerms" "$DEST_UI/mod-matching.js" "saveMatchTerms"
check "UI phone_raw" "$DEST_UI/mod-matching.js" "phone_raw"
check "UI outreachSelectTemplate" "$DEST_UI/mod-matching.js" "outreachSelectTemplate"
check "UI outreachSelectSignature" "$DEST_UI/mod-matching.js" "outreachSelectSignature"
if [[ -n "${DEST_M:-}" && -d "${DEST_M:-}" ]]; then
  check "Matching outreach_wizard redact" "$DEST_M/services/outreach_wizard.py" "_redact_customer_names"
  check "Matching email-templates API" "$DEST_M/views.py" "api_outreach_email_templates"
fi
check "KI matching_anfrage" "$DEST_KI/prompt_defaults.py" "wiz_matching_anfrage_generate"

STAMP="$REPO/Repo_abpe/.live-pull-stamp"
{
  echo "ts=$TS"
  echo "iso=$(date -Iseconds)"
  echo "host=$(hostname -f 2>/dev/null || hostname)"
  echo "branch=$(git -C "$REPO" branch --show-current 2>/dev/null || echo '?')"
  echo "backup=${BAK_DIR:-none}"
  echo "crm_views_lines=$(wc -l < "$DEST_CRM/views.py" 2>/dev/null || echo 0)"
  echo "crm_has_contacts_suggest=$(grep -c 'def api_contacts_suggest' "$DEST_CRM/views.py" 2>/dev/null || echo 0)"
  echo "crm_has_berater_cv=$(grep -c 'def api_berater_cv' "$DEST_CRM/views.py" 2>/dev/null || echo 0)"
  echo "ui_has_fillSkills=$(grep -c 'fillSkillsFromText' "$DEST_UI/mod-matching.js" 2>/dev/null || echo 0)"
  echo "ui_has_saveMatchTerms=$(grep -c 'saveMatchTerms' "$DEST_UI/mod-matching.js" 2>/dev/null || echo 0)"
} > "$STAMP"
echo "OK Stamp → $STAMP"

GITIGNORE="$REPO/.gitignore"
touch "$GITIGNORE"
grep -qxF '_repo_backups/' "$GITIGNORE" 2>/dev/null || echo '_repo_backups/' >> "$GITIGNORE"
grep -qxF '_live_backups/' "$GITIGNORE" 2>/dev/null || echo '_live_backups/' >> "$GITIGNORE"
# Softphone/node_modules nie committen
grep -qxF 'Repo_abpe/abpe_crm/incoming/static/softphone-electron/' "$GITIGNORE" 2>/dev/null \
  || echo 'Repo_abpe/abpe_crm/incoming/static/softphone-electron/' >> "$GITIGNORE"
grep -qxF '**/node_modules/' "$GITIGNORE" 2>/dev/null || echo '**/node_modules/' >> "$GITIGNORE"

echo
echo "=== git status (Auszug) ==="
git -C "$REPO" status -sb | head -40
git -C "$REPO" diff --stat | tail -25 || true

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
  # softphone nie stagen
  git -C "$REPO" reset -q -- \
    'Repo_abpe/abpe_crm/incoming/static/softphone-electron' 2>/dev/null || true
  if git -C "$REPO" diff --cached --quiet; then
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
  echo "Fertig ohne Commit. Mit --push committen, oder:"
  echo "  git add Repo_abpe/… Repo_abpe/.live-pull-stamp && git commit && git push"
fi

echo
echo "======== Ende PULL ========"
echo ">>> Cloud-Agent: git pull origin $BRANCH — dann weiter."
