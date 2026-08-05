#!/usr/bin/env bash
# Repo → Live: abpe_ki_wiz + Matching-UI (KI-Anfragen-Wizard)
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap && git fetch origin
#   bash scripts/SYNC-matching-ki-anfrage-wizard.sh
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BRANCH="${BRANCH:-origin/cursor/matching-ki-anfrage-wizard-7f07}"
LIVE_KI="${LIVE_KI:-/opt/abpe/backend/apps/abpe_ki_wiz}"
LIVE_UI="${LIVE_UI:-/opt/abpe/backend/apps/abpe_ui}"
STATICFILES="${STATICFILES:-/opt/abpe/backend/staticfiles}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
PYBIN="${PYBIN:-/opt/abpe/venv311/bin/python}"

cd "$REPO"
git fetch origin cursor/matching-ki-anfrage-wizard-7f07 || true

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git archive "$BRANCH" \
  Repo_abpe/abpe_ki_wiz/incoming \
  Repo_abpe/abpe_ui/incoming/mod-matching.js \
  Repo_abpe/abpe_ui/incoming/mod-shaduler.js \
  Repo_abpe/abpe_ui/incoming/mod-shaduler.css \
  Repo_abpe/abpe_shaduler/incoming \
  | tar -x -C "$TMP"

# Guard: Prompt-Default muss im Archive sein
if ! grep -q "wiz_matching_anfrage_generate" \
  "$TMP/Repo_abpe/abpe_ki_wiz/incoming/prompt_defaults.py"; then
  echo "FEHLER: Branch $BRANCH enthält wiz_matching_anfrage_generate nicht."
  echo "  git -C $REPO fetch origin && git -C $REPO rev-parse $BRANCH"
  exit 1
fi

# ── abpe_ki_wiz (kein --delete: Live kann zusätzliche Dateien haben) ─────────
mkdir -p "$LIVE_KI"
rsync -a \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  "$TMP/Repo_abpe/abpe_ki_wiz/incoming/" \
  "$LIVE_KI/"
echo "OK — abpe_ki_wiz → $LIVE_KI"

# pycache invalidieren, damit Django Defaults neu lädt
find "$LIVE_KI" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find "$LIVE_KI" -name '*.pyc' -delete 2>/dev/null || true

if ! grep -q "wiz_matching_anfrage_generate" "$LIVE_KI/prompt_defaults.py"; then
  echo "FEHLER: $LIVE_KI/prompt_defaults.py ohne wiz_matching_anfrage_generate nach rsync"
  exit 1
fi
echo "OK — prompt_defaults enthält wiz_matching_anfrage_generate"


# ── Shaduler (Radar Freelancermap + Inbox-Ack) ───────────────────────────────
LIVE_SH="${LIVE_SH:-/opt/abpe/backend/apps/abpe_shaduler}"
if [[ -d "$TMP/Repo_abpe/abpe_shaduler/incoming" ]]; then
  mkdir -p "$LIVE_SH"
  rsync -a \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude 'migrations/0*.py' \
    "$TMP/Repo_abpe/abpe_shaduler/incoming/" \
    "$LIVE_SH/"
  echo "OK — abpe_shaduler → $LIVE_SH (Radar + Ack-Send)"
fi

# ── Matching UI ──────────────────────────────────────────────────────────────
mkdir -p "$LIVE_UI/static/abpe_ui/js/mod"
cp -a "$TMP/Repo_abpe/abpe_ui/incoming/mod-matching.js" \
  "$LIVE_UI/static/abpe_ui/js/mod/mod-matching.js"
echo "OK — mod-matching.js → $LIVE_UI/static/abpe_ui/js/mod/"

if [[ -f "$TMP/Repo_abpe/abpe_ui/incoming/mod-shaduler.js" ]]; then
  cp -a "$TMP/Repo_abpe/abpe_ui/incoming/mod-shaduler.js" \
    "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler.js"
  echo "OK — mod-shaduler.js (Matching + Antworten) → $LIVE_UI/static/abpe_ui/js/mod/"
fi

if [[ -f "$TMP/Repo_abpe/abpe_ui/incoming/mod-shaduler.css" ]]; then
  mkdir -p "$LIVE_UI/static/abpe_ui/css/mod"
  cp -a "$TMP/Repo_abpe/abpe_ui/incoming/mod-shaduler.css" \
    "$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css"
  echo "OK — mod-shaduler.css → $LIVE_UI/static/abpe_ui/css/mod/"
fi

if [[ -d "$STATICFILES" ]]; then
  mkdir -p "$STATICFILES/abpe_ui/js/mod"
  cp -a "$LIVE_UI/static/abpe_ui/js/mod/mod-matching.js" \
    "$STATICFILES/abpe_ui/js/mod/mod-matching.js"
  if [[ -f "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler.js" ]]; then
    cp -a "$LIVE_UI/static/abpe_ui/js/mod/mod-shaduler.js" \
      "$STATICFILES/abpe_ui/js/mod/mod-shaduler.js"
  fi
  if [[ -f "$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css" ]]; then
    mkdir -p "$STATICFILES/abpe_ui/css/mod"
    cp -a "$LIVE_UI/static/abpe_ui/css/mod/mod-shaduler.css" \
      "$STATICFILES/abpe_ui/css/mod/mod-shaduler.css"
  fi
  echo "OK — auch nach $STATICFILES/abpe_ui/… kopiert"
fi

# ── Prompt in DB ─────────────────────────────────────────────────────────────
echo
echo "→ sync_wizard_prompts --wizard-id matching_anfrage"
cd "$BACKEND"
"$PYBIN" manage.py sync_wizard_prompts --wizard-id matching_anfrage --force
"$PYBIN" manage.py shell -c "
from apps.abpe_ki_wiz.models import WizardPrompt
from apps.abpe_ki_wiz.prompt_defaults import WIZARD_PROMPT_DEFAULTS
keys=[r['key'] for r in WIZARD_PROMPT_DEFAULTS if r.get('wizard_id')=='matching_anfrage']
print('defaults:', keys)
p=WizardPrompt.objects.filter(key='wiz_matching_anfrage_generate').first()
print('db:', p.key if p else 'FEHLT', 'aktiv='+str(getattr(p,'aktiv',None)), 'sys_len='+str(len(getattr(p,'system','') or '')))
if not p:
    raise SystemExit(2)
"

echo
echo "Restart: supervisorctl restart abpe-django"
echo "UI Matching: Button „KI-Anfragen-Wizard“ links neben „+ Neue Anfrage“"
echo "UI: Matching; Posteingang Antworten An/CC/BCC; Radar Anfragen = Freelancermap"
echo "API: POST /ki-wizard/api/matching-anfrage/extract/"
echo "Browser: Ctrl+F5 (mod-matching.js + mod-shaduler.js/css)"

echo "Optional Email-Studio-Vorlage: manage.py shell < scripts/ensure-inbox-anfrage-bestaetigung-template.py"
