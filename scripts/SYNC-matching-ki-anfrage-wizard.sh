#!/usr/bin/env bash
# Repo → Live: abpe_ki_wiz + Matching-UI + Shaduler (Radar Anfragen/Berater)
#
# VORHER auf ucs5 immer Live→Repo ziehen (sonst gehen Live-Fixes verloren):
#   bash <(git show origin/cursor/matching-ki-anfrage-wizard-7f07:scripts/PULL-matching-from-live.sh) --push
#
# Auf ucs5 (erst fetch, dann Script — sonst läuft eine alte Script-Version):
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/matching-ki-anfrage-wizard-7f07
#   bash <(git show origin/cursor/matching-ki-anfrage-wizard-7f07:scripts/SYNC-matching-ki-anfrage-wizard.sh)
#   supervisorctl restart abpe-django
#   # Browser: Ctrl+F5
#
# Regeln:
# - CRM views/models: kein Blind-Overwrite; timestamped *.bak-before-matching-sync-*
# - DB-Spalten/Terms-Tabelle werden per ensure-matching-terms-db.py erzwungen
# - manage.py check muss grün sein, sonst Abbruch vor Restart-Hinweis
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
  Repo_abpe/abpe_crm/incoming/models.py \
  Repo_abpe/abpe_crm/incoming/views.py \
  Repo_abpe/abpe_crm/incoming/migrations \
  scripts/ensure-matching-terms-db.py \
  | tar -x -C "$TMP"

# Guard: Prompt-Default muss im Archive sein
if ! grep -q "wiz_matching_anfrage_generate" \
  "$TMP/Repo_abpe/abpe_ki_wiz/incoming/prompt_defaults.py"; then
  echo "FEHLER: Branch $BRANCH enthält wiz_matching_anfrage_generate nicht."
  echo "  git -C $REPO fetch origin && git -C $REPO rev-parse $BRANCH"
  exit 1
fi
if ! grep -q "wiz_firma_web_enrich" \
  "$TMP/Repo_abpe/abpe_ki_wiz/incoming/prompt_defaults.py"; then
  echo "FEHLER: Branch $BRANCH enthält wiz_firma_web_enrich nicht."
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


# ── Shaduler (Radar Freelancermap + Inbox-Ack + Berater) ─────────────────────
LIVE_SH="${LIVE_SH:-/opt/abpe/backend/apps/abpe_shaduler}"
if [[ -d "$TMP/Repo_abpe/abpe_shaduler/incoming" ]]; then
  mkdir -p "$LIVE_SH"
  ts=$(date +%Y%m%d-%H%M%S)
  if [[ -f "$LIVE_SH/views.py" ]]; then
    cp -a "$LIVE_SH/views.py" "$LIVE_SH/views.py.bak-before-matching-sync-$ts"
    cp -a "$LIVE_SH/views.py" "$LIVE_SH/views.py.bak-before-matching-sync"
  fi
  if [[ -f "$LIVE_SH/models.py" ]]; then
    cp -a "$LIVE_SH/models.py" "$LIVE_SH/models.py.bak-before-matching-sync-$ts"
    cp -a "$LIVE_SH/models.py" "$LIVE_SH/models.py.bak-before-matching-sync"
  fi
  # Code ohne Migrationen (Live-History nicht überschreiben) …
  rsync -a \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude 'migrations/' \
    "$TMP/Repo_abpe/abpe_shaduler/incoming/" \
    "$LIVE_SH/"
  # … neue Migrationen gezielt nachziehen (fehlende Dateien + geänderte)
  mkdir -p "$LIVE_SH/migrations"
  if [[ -f "$LIVE_SH/migrations/__init__.py" ]] || \
     [[ -f "$TMP/Repo_abpe/abpe_shaduler/incoming/migrations/__init__.py" ]]; then
    cp -n "$TMP/Repo_abpe/abpe_shaduler/incoming/migrations/__init__.py" \
      "$LIVE_SH/migrations/__init__.py" 2>/dev/null || true
  fi
  for mig in "$TMP"/Repo_abpe/abpe_shaduler/incoming/migrations/0*.py; do
    [[ -f "$mig" ]] || continue
    base=$(basename "$mig")
    if [[ ! -f "$LIVE_SH/migrations/$base" ]]; then
      cp -a "$mig" "$LIVE_SH/migrations/$base"
      echo "OK — Migration neu: $base"
    elif [[ "$base" == *matchingberaterterms* ]]; then
      cp -a "$mig" "$LIVE_SH/migrations/$base"
      echo "OK — Migration aktualisiert: $base"
    fi
  done
  # Alte kollidierende Leaf entfernen (0005_matching… parallel zu 0005_shadulersetting)
  if [[ -f "$LIVE_SH/migrations/0005_matchingberaterterms.py" ]]; then
    mv -f "$LIVE_SH/migrations/0005_matchingberaterterms.py" \
      "$LIVE_SH/migrations/0005_matchingberaterterms.py.bak-conflict-$ts" 2>/dev/null \
      || rm -f "$LIVE_SH/migrations/0005_matchingberaterterms.py"
    echo "OK — kollidierende 0005_matchingberaterterms.py entfernt"
  fi
  find "$LIVE_SH" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
  echo "OK — abpe_shaduler → $LIVE_SH (Radar Anfragen + Berater)"
fi

# ── CRM (Stammdaten Verfügbarkeit/Konditionen) ───────────────────────────────
# WICHTIG: Live-CRM (urls.py + views.py) ist oft NEUER als der Matching-Export.
# Nie views.py blind überschreiben — sonst fehlen Handler wie api_contacts_suggest.
LIVE_CRM="${LIVE_CRM:-/opt/abpe/backend/apps/abpe_crm}"
if [[ -d "$TMP/Repo_abpe/abpe_crm/incoming" && -d "$LIVE_CRM" ]]; then
  REPO_CRM_VIEWS="$TMP/Repo_abpe/abpe_crm/incoming/views.py"
  LIVE_CRM_VIEWS="$LIVE_CRM/views.py"
  LIVE_CRM_URLS="$LIVE_CRM/urls.py"

  _crm_view_has() {
    # def name ... oder name = ... (Re-Export / Wrapper)
    local file="$1" name="$2"
    grep -qE "(^def ${name}\\b|^${name}\\s*=)" "$file"
  }

  _crm_urls_need() {
    local name="$1"
    [[ -f "$LIVE_CRM_URLS" ]] || return 1
    grep -qE "views\\.${name}\\b" "$LIVE_CRM_URLS"
  }

  if [[ -f "$REPO_CRM_VIEWS" && -f "$LIVE_CRM_VIEWS" ]]; then
    if ! _crm_view_has "$REPO_CRM_VIEWS" api_berater_cv; then
      echo "FEHLER: Repo CRM views.py ohne api_berater_cv"
      exit 1
    fi
    if ! grep -q "satz_remote_c" "$REPO_CRM_VIEWS"; then
      echo "FEHLER: CRM views.py ohne satz_remote_c (Terms)"
      exit 1
    fi
    if ! _crm_view_has "$REPO_CRM_VIEWS" api_contacts_suggest; then
      echo "FEHLER: Repo CRM views.py ohne api_contacts_suggest"
      exit 1
    fi

    # Wenn Live-urls Handler verlangt, die Repo-views nicht hat → kein Full-Replace
    SKIP_VIEWS_COPY=0
    if [[ -f "$LIVE_CRM_URLS" ]]; then
      while read -r attr; do
        [[ -n "$attr" ]] || continue
        if ! _crm_view_has "$REPO_CRM_VIEWS" "$attr"; then
          echo "WARN: Live urls braucht views.$attr — fehlt im Repo-Export → kein views.py-Replace"
          SKIP_VIEWS_COPY=1
          break
        fi
      done < <(grep -oE 'views\.[A-Za-z_][A-Za-z0-9_]*' "$LIVE_CRM_URLS" \
        | sed 's/^views\.//' | sort -u)
    fi

    # Recovery / Harden: fehlende Handler ODER noch ohne Terms-Defer-Schutz
    NEED_RECOVERY=0
    for must in api_berater_cv api_contacts_suggest; do
      if _crm_urls_need "$must" && ! _crm_view_has "$LIVE_CRM_VIEWS" "$must"; then
        echo "WARN: Live views.py fehlt $must (urls verlangt es) → Recovery nötig"
        NEED_RECOVERY=1
      fi
    done
    if ! grep -q "satz_remote_c" "$LIVE_CRM_VIEWS"; then
      echo "WARN: Live views.py ohne satz_remote_c → Terms-Patch nötig"
      NEED_RECOVERY=1
    fi
    if ! grep -q "_CRM_TERMS_DEFER" "$LIVE_CRM_VIEWS"; then
      echo "WARN: Live views.py ohne _CRM_TERMS_DEFER → Harden nötig"
      NEED_RECOVERY=1
    fi

    ts=$(date +%Y%m%d-%H%M%S)
    cp -a "$LIVE_CRM_VIEWS" "$LIVE_CRM/views.py.bak-before-matching-sync-$ts"
    cp -a "$LIVE_CRM_VIEWS" "$LIVE_CRM/views.py.bak-before-matching-sync"

    if [[ "$SKIP_VIEWS_COPY" -eq 0 && "$NEED_RECOVERY" -eq 1 ]]; then
      cp -a "$REPO_CRM_VIEWS" "$LIVE_CRM_VIEWS"
      echo "OK — abpe_crm/views.py ersetzt (Backup: views.py.bak-before-matching-sync-$ts)"
    elif [[ "$SKIP_VIEWS_COPY" -eq 0 && "$NEED_RECOVERY" -eq 0 ]]; then
      echo "OK — abpe_crm/views.py unverändert (Live ok, Backup: views.py.bak-before-matching-sync-$ts)"
    else
      echo "→ CRM views: chirurgisch (kein Full-Replace); Backup: views.py.bak-before-matching-sync-$ts"
      if _crm_urls_need api_contacts_suggest && ! _crm_view_has "$LIVE_CRM_VIEWS" api_contacts_suggest; then
        if _crm_view_has "$REPO_CRM_VIEWS" api_contacts_suggest; then
          # Funktion aus Repo extrahieren und vor crm_email_compose / Dateiende einfügen
          "$PYBIN" - "$REPO_CRM_VIEWS" "$LIVE_CRM_VIEWS" <<'PY'
import re, sys
repo, live = sys.argv[1], sys.argv[2]
rs, ls = open(repo, encoding="utf-8").read(), open(live, encoding="utf-8").read()
m = re.search(
    r"\n@login_required\n@login_or_token_required\n@require_http_methods\(\['GET'\]\)\n"
    r"def api_contacts_suggest\(request\):.*?(?=\n@login_required\ndef crm_email_compose|\n\ndef crm_email_compose|\Z)",
    rs, re.S,
)
if not m:
    # fallback: ab def api_contacts_suggest bis nächste Top-Level def nach Compose-Block
    m = re.search(
        r"\ndef api_contacts_suggest\(request\):.*?(?=\n@login_required\ndef crm_email_compose|\n\ndef crm_email_compose|\Z)",
        rs, re.S,
    )
if not m:
    raise SystemExit("api_contacts_suggest nicht im Repo-Export gefunden")
snippet = m.group(0)
if "def api_contacts_suggest" in ls:
    print("skip: already present")
else:
    anchor = "\ndef crm_email_compose(request):"
    if anchor in ls:
        ls = ls.replace(anchor, snippet + anchor, 1)
    else:
        ls = ls.rstrip() + "\n" + snippet + "\n"
    open(live, "w", encoding="utf-8").write(ls)
    print("injected api_contacts_suggest")
PY
          echo "OK — api_contacts_suggest in Live views injiziert"
        fi
      fi
      if ! grep -q "satz_remote_c" "$LIVE_CRM_VIEWS"; then
        echo "WARN: satz_remote_c fehlt in Live views — bitte Terms manuell prüfen / Full-Replace wenn urls-kompatibel"
      fi
      if _crm_urls_need api_berater_cv && ! _crm_view_has "$LIVE_CRM_VIEWS" api_berater_cv; then
        echo "FEHLER: Live fehlt api_berater_cv und Full-Replace war nicht sicher — manuell mergen"
        exit 1
      fi
    fi
  fi

  # models.py: NIE Full-Replace — nur fehlende Terms-Felder chirurgisch einfügen
  if [[ -f "$LIVE_CRM/models.py" ]]; then
    ts=$(date +%Y%m%d-%H%M%S)
    cp -a "$LIVE_CRM/models.py" "$LIVE_CRM/models.py.bak-before-matching-sync-$ts"
    cp -a "$LIVE_CRM/models.py" "$LIVE_CRM/models.py.bak-before-matching-sync"
    if ! grep -q "verfuegbar_tage_pro_woche_c" "$LIVE_CRM/models.py"; then
      "$PYBIN" - "$LIVE_CRM/models.py" <<'PY'
import re, sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
if "verfuegbar_tage_pro_woche_c" in text:
    print("skip models: already has terms fields")
    raise SystemExit(0)
block = '''
    # Eingeschränkte Verfügbarkeit (Stammdaten / Default) — Matching Terms
    verfuegbar_tage_pro_woche_c = models.PositiveSmallIntegerField(
                                    null=True, blank=True,
                                    help_text='Max. Einsatztage pro Woche (1–7)')
    verfuegbar_hinweis_c        = models.CharField(
                                    max_length=255, blank=True, null=True,
                                    help_text='z.B. nur Mo–Mi, keine Reise')
'''
# konditionen_c bleibt; Sätze danach
rates = '''
    # Mehrere Konditionen (Stammdaten / Default) — Matching Terms
    satz_remote_c               = models.DecimalField(
                                    max_digits=8, decimal_places=2, null=True, blank=True,
                                    help_text='Stundensatz Remote €')
    satz_vor_ort_c              = models.DecimalField(
                                    max_digits=8, decimal_places=2, null=True, blank=True,
                                    help_text='Stundensatz vor Ort €')
'''
# Nach verfuegbar_ab_c einfügen
pat = r"(verfuegbar_ab_c\s*=\s*models\.DateField\([^\n]*\n)"
m = re.search(pat, text)
if not m:
    raise SystemExit("verfuegbar_ab_c nicht in Live models.py — Abbruch")
text = text[:m.end()] + block + text[m.end():]
# Nach konditionen_c einfügen (falls vorhanden), sonst nach hinweis-Block
if "satz_remote_c" not in text:
    m2 = re.search(r"(konditionen_c\s*=\s*models\.CharField\([^\n]*\n)", text)
    if m2:
        text = text[:m2.end()] + rates + text[m2.end():]
    else:
        # hinter verfuegbar_hinweis_c
        m3 = re.search(r"(verfuegbar_hinweis_c\s*=\s*models\.CharField\([\s\S]*?\)\n)", text)
        if not m3:
            raise SystemExit("kein Insert-Punkt für satz_remote_c")
        text = text[:m3.end()] + rates + text[m3.end():]
open(path, "w", encoding="utf-8").write(text)
print("patched models.py Terms fields")
PY
      echo "OK — abpe_crm/models.py chirurgisch (Terms-Felder)"
    else
      echo "OK — abpe_crm/models.py unverändert (Terms-Felder bereits vorhanden)"
    fi
  fi
  mkdir -p "$LIVE_CRM/migrations"
  if [[ -f "$LIVE_CRM/migrations/__init__.py" ]] || \
     [[ -f "$TMP/Repo_abpe/abpe_crm/incoming/migrations/__init__.py" ]]; then
    cp -n "$TMP/Repo_abpe/abpe_crm/incoming/migrations/__init__.py" \
      "$LIVE_CRM/migrations/__init__.py" 2>/dev/null || true
  fi
  for mig in "$TMP"/Repo_abpe/abpe_crm/incoming/migrations/0*.py; do
    [[ -f "$mig" ]] || continue
    base=$(basename "$mig")
    if [[ ! -f "$LIVE_CRM/migrations/$base" ]]; then
      cp -a "$mig" "$LIVE_CRM/migrations/$base"
      echo "OK — CRM Migration neu: $base"
    elif [[ "$base" == *berater_verfuegbarkeit* ]]; then
      cp -a "$mig" "$LIVE_CRM/migrations/$base"
      echo "OK — CRM Migration aktualisiert: $base"
    fi
  done
  # Alte kollidierende 0001_berater… (parallel zu 0017_…) entfernen
  if [[ -f "$LIVE_CRM/migrations/0001_berater_verfuegbarkeit_konditionen.py" ]]; then
    mv -f "$LIVE_CRM/migrations/0001_berater_verfuegbarkeit_konditionen.py" \
      "$LIVE_CRM/migrations/0001_berater_verfuegbarkeit_konditionen.py.bak-conflict" 2>/dev/null \
      || rm -f "$LIVE_CRM/migrations/0001_berater_verfuegbarkeit_konditionen.py"
    echo "OK — kollidierende CRM 0001_berater_verfuegbarkeit_konditionen.py entfernt"
  fi
  find "$LIVE_CRM" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
fi

# ── Matching UI ──────────────────────────────────────────────────────────────
if ! grep -q "phone_raw" "$TMP/Repo_abpe/abpe_ui/incoming/mod-matching.js" \
  || ! grep -q "_fetchBeraterDetail" "$TMP/Repo_abpe/abpe_ui/incoming/mod-matching.js" \
  || ! grep -q "matching-avail-box" "$TMP/Repo_abpe/abpe_ui/incoming/mod-matching.js" \
  || ! grep -q "saveMatchTerms" "$TMP/Repo_abpe/abpe_ui/incoming/mod-matching.js"; then
  echo "FEHLER: mod-matching.js ohne CRM Tel/E-Mail/Verfügbarkeit/Terms-Fix"
  exit 1
fi
mkdir -p "$LIVE_UI/static/abpe_ui/js/mod"
cp -a "$TMP/Repo_abpe/abpe_ui/incoming/mod-matching.js" \
  "$LIVE_UI/static/abpe_ui/js/mod/mod-matching.js"
echo "OK — mod-matching.js → $LIVE_UI/static/abpe_ui/js/mod/"
# Guard: Live-Datei enthält den Fix
if ! grep -q "_fetchBeraterDetail" "$LIVE_UI/static/abpe_ui/js/mod/mod-matching.js"; then
  echo "FEHLER: Live mod-matching.js ohne _fetchBeraterDetail nach Copy"
  exit 1
fi

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
echo "→ sync_wizard_prompts (matching_anfrage + firma_web)"
cd "$BACKEND"
"$PYBIN" manage.py sync_wizard_prompts --wizard-id matching_anfrage --force
"$PYBIN" manage.py sync_wizard_prompts --wizard-id firma_web --force
"$PYBIN" manage.py shell -c "
from apps.abpe_ki_wiz.models import WizardPrompt
from apps.abpe_ki_wiz.prompt_defaults import WIZARD_PROMPT_DEFAULTS
keys=[r['key'] for r in WIZARD_PROMPT_DEFAULTS if r.get('wizard_id') in ('matching_anfrage','firma_web')]
print('defaults:', keys)
for k in ('wiz_matching_anfrage_generate','wiz_firma_web_enrich'):
    p=WizardPrompt.objects.filter(key=k).first()
    print('db:', k, '→', ('aktiv='+str(getattr(p,'aktiv',None)) if p else 'FEHLT'))
    if not p:
        raise SystemExit(2)
"

# ── DB sicherstellen (Spalten + Terms-Tabelle) — MUSS vor Restart ────────────
echo
echo "→ ensure-matching-terms-db (ADD COLUMN IF NOT EXISTS + migrate)"
cd "$BACKEND"
ENSURE_PY="${TMP}/scripts/ensure-matching-terms-db.py"
if [[ ! -f "$ENSURE_PY" ]]; then
  # Fallback: aus Repo-Working-Tree / git show
  if [[ -f "$REPO/scripts/ensure-matching-terms-db.py" ]]; then
    ENSURE_PY="$REPO/scripts/ensure-matching-terms-db.py"
  else
    mkdir -p "$TMP/scripts"
    git -C "$REPO" show "$BRANCH:scripts/ensure-matching-terms-db.py" \
      > "$TMP/scripts/ensure-matching-terms-db.py"
    ENSURE_PY="$TMP/scripts/ensure-matching-terms-db.py"
  fi
fi
BACKEND="$BACKEND" "$PYBIN" "$ENSURE_PY"
ENSURE_RC=$?
if [[ "$ENSURE_RC" -ne 0 ]]; then
  echo "FEHLER: DB-Ensure fehlgeschlagen (exit $ENSURE_RC)."
  echo "  Ohne Spalten/Tabelle liefern /crm/api/berater/ und /matching/terms/ 500."
  echo "  Rollback-Beispiel: cp -a $LIVE_CRM/models.py.bak-before-matching-sync $LIVE_CRM/models.py"
  exit "$ENSURE_RC"
fi

# ── Django-Check ─────────────────────────────────────────────────────────────
echo
echo "→ manage.py check"
"$PYBIN" manage.py check || {
  echo "FEHLER: manage.py check fehlgeschlagen — Django nicht restarten bis behoben"
  exit 1
}

echo "Hinweis: CRM-Vollindex manuell / alle 30 Min via Scheduler:"
echo "  $PYBIN manage.py radar_berater_seed --reindex"
echo "  $PYBIN manage.py register_scheduler_jobs   # inkl. radar_berater_index 30 Min"
echo "  UI: ↻ = Index aktualisieren (CRM→ES); Liste=ES, Detail=DB"
echo "  Gulp-Login: settings.json → shaduler.gulp_talentfinder.cookies"
echo "  FM-Login:   settings.json → shaduler.freelancermap  ODER data/url/fl/.session_cookies.json"
echo "              (ohne Session: Liste ok, Stundensätze oft leer)"
echo
echo "Restart: supervisorctl restart abpe-django"
echo "API Match-Terms: GET/POST /shaduler/api/matching/terms/<match_uuid>/"
echo "CRM-Felder: verfuegbar_tage_pro_woche_c, verfuegbar_hinweis_c, satz_remote_c, satz_vor_ort_c"
echo "Backups: $LIVE_CRM/*.bak-before-matching-sync[-TIMESTAMP]"
echo "Optional (Radar Anfragen ES): $PYBIN manage.py radar_reindex --status neu"
echo "Optional (Radar Dedup):       $PYBIN manage.py radar_regroup --days 14"
echo "UI Matching: Button „KI-Anfragen-Wizard“ links neben „+ Neue Anfrage“"
echo "UI Firma: Neuer Kontakt → „Aus Web anreichern“ (Homepage/Impressum)"
echo "UI: Matching; Posteingang Antworten; Radar Anfragen = FM+Gulp+Hays"
echo "UI: Radar Berater = Gulp + Freelancermap (verfügbar/Match; CRM gulp_id_c / freelancermap_profil_c)"
echo "CLI (immer aus $BACKEND):"
echo "  cd $BACKEND"
echo "  $PYBIN manage.py radar_berater_gulp_available --limit 40"
echo "  $PYBIN manage.py radar_berater_fl_available --limit 36 --pages 1"
echo "  # Paste-Test FM: manage.py shell → fl.fetch_profile_by_text('https://www.freelancermap.de/profil/…')"
echo "API: POST /ki-wizard/api/matching-anfrage/extract/"
echo "API: POST /ki-wizard/api/firma-web/enrich/"
echo "Browser: Ctrl+F5 (mod-matching.js + mod-shaduler.js/css)"
echo "Optional Email-Studio-Vorlage: manage.py shell < scripts/ensure-inbox-anfrage-bestaetigung-template.py"
