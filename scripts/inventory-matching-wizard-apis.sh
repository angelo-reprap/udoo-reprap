#!/usr/bin/env bash
# Inventar: Matching-/Anschreiben-/Wiedervorlage-Schnittstellen (Live ucs5)
#
# Auf ucs5:
#   cd /mnt/public/udoo-reprap
#   git pull --rebase origin cursor/cv-extractor-7f07   # oder aktueller Branch
#   bash scripts/inventory-matching-wizard-apis.sh
#
# Optional:
#   OUT=artifacts/matching-wizard-api-$(date +%Y%m%d-%H%M%S) bash scripts/inventory-matching-wizard-apis.sh
#   BACKEND=/opt/abpe/backend bash scripts/inventory-matching-wizard-apis.sh
#
# Ergebnis: OUT/report.md + OUT/*.tsv  → bitte committen/pushen oder Inhalt pasten.
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
OUT="${OUT:-$REPO/artifacts/matching-wizard-api-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$OUT"

echo "=== Matching Wizard API Inventory ==="
echo "BACKEND=$BACKEND"
echo "OUT=$OUT"
echo

# ── 1) Django URL dump (Live) ───────────────────────────────────────────────
echo ">>> 1) Django URL-Resolver"
cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate

python3 manage.py shell <<'PY' > "$OUT/django-urls.tsv" 2>"$OUT/django-urls.err" || true
from django.urls import get_resolver
import re

want = re.compile(
    r'(matching|ki-wizard|ki_wizard|shaduler|crm|email|anschreiben|wizard|aufgabe)',
    re.I,
)

def walk(patterns, prefix=''):
    rows = []
    for p in patterns:
        try:
            route = prefix + str(p.pattern)
        except Exception:
            route = prefix + getattr(p, 'pattern', '?')
        if hasattr(p, 'url_patterns'):
            rows.extend(walk(p.url_patterns, route))
            continue
        name = getattr(p, 'name', '') or ''
        cb = p.callback
        cb_name = getattr(cb, '__name__', None) or getattr(getattr(cb, 'view_class', None), '__name__', '') or str(cb)
        mod = getattr(cb, '__module__', '') or getattr(getattr(cb, 'view_class', None), '__module__', '')
        line = f"{route}\t{name}\t{mod}.{cb_name}"
        if want.search(line):
            rows.append(line)
    return rows

rows = walk(get_resolver().url_patterns)
print('path\tname\tcallback')
for r in sorted(set(rows)):
    print(r)
print(f'# total_matched={len(set(rows))}', flush=True)
PY

if [[ -s "$OUT/django-urls.tsv" ]]; then
  echo "  → $OUT/django-urls.tsv ($(grep -cve '^#' "$OUT/django-urls.tsv" || true) Zeilen)"
else
  echo "  WARN: URL-Dump fehlgeschlagen — siehe django-urls.err"
  head -40 "$OUT/django-urls.err" 2>/dev/null || true
fi

# ── 2) Code-Grep Live Apps ──────────────────────────────────────────────────
echo ">>> 2) Code-Grep (Live apps)"
APPS="$BACKEND/apps"
{
  echo "path	line	snippet"
  for pat in \
    'anschreiben' 'cover.?letter' 'personaliz' 'glätt' 'polish' \
    'match_reason' 'shortlist' 'send_all' 'Alle anschreiben' \
    'wiedervorlage' 'aufgaben/create' 'deepseek' 'run_llm_rerank' \
    'matching-anfrage' 'email/send' 'STAGE_MAIL' 'sendAllAboveThreshold'
  do
    rg -n -i --no-heading -g '*.py' -g '*.js' -g '*.html' -g '*.md' \
      "$pat" "$APPS" 2>/dev/null \
      | head -80 \
      | while IFS= read -r line; do
          # path:line:text → tsv
          f="${line%%:*}"
          rest="${line#*:}"
          ln="${rest%%:*}"
          sn="${rest#*:}"
          sn="$(echo "$sn" | tr '\t' ' ' | cut -c1-160)"
          printf '%s\t%s\t[%s] %s\n' "$f" "$ln" "$pat" "$sn"
        done
  done
} > "$OUT/code-hits.tsv"
echo "  → $OUT/code-hits.tsv ($(wc -l < "$OUT/code-hits.tsv" | tr -d ' ') Zeilen)"

# ── 3) Wizard-Bedarf vs. Fund ───────────────────────────────────────────────
echo ">>> 3) Wizard-Bedarf Checkliste"
OUT_DIR="$OUT" python3 - <<'PY'
from pathlib import Path
import os, re

out = Path(os.environ["OUT_DIR"])
urls = (out / "django-urls.tsv").read_text(encoding="utf-8", errors="replace") if (out / "django-urls.tsv").exists() else ""
hits = (out / "code-hits.tsv").read_text(encoding="utf-8", errors="replace") if (out / "code-hits.tsv").exists() else ""
blob = urls + "\n" + hits

def found(*needles):
    return any(re.search(n, blob, re.I) for n in needles)

needs = [
    ("W1", "Match starten (Anfrage → Kandidaten)",
     ["requests/.*/match", r"/match/"], True,
     "POST /matching/api/requests/<uuid>/match/"),
    ("W2", "Shortlist + Schwellwert lesen",
     ["shortlist", "threshold"], True,
     "GET /matching/api/requests/<uuid>/shortlist/?threshold="),
    ("W3", "Anfrage-Skills setzen / speichern",
     ["requests/.*/update", "required_skills"], True,
     "PATCH /matching/api/requests/<uuid>/update/"),
    ("W4", "DeepSeek: Anfrage aus Mail extrahieren",
     ["matching-anfrage/extract"], True,
     "POST /ki-wizard/api/matching-anfrage/extract/"),
    ("W5", "DeepSeek: CV↔Anfrage Begründung (warum/Interesse/Antwort)",
     [r"cv.?anfrage", "match_reason", "antwortchance", "rationale", "deep-reason"], False,
     "NEU z.B. POST /matching/api/match/<uuid>/deep-reason/"),
    ("W6", "DeepSeek: persönliches Anschreiben draften",
     ["anschreiben", "cover_letter", "personaliz", "consultant_email", "letter/draft"], False,
     "NEU z.B. POST /matching/api/match/<uuid>/letter/draft/"),
    ("W7", "Anschreiben manuell speichern (Edit)",
     ["letter/save", "anschreiben.*save", "draft.*save"], False,
     "NEU oder CRM draft speichern"),
    ("W8", "DeepSeek: Anschreiben glätten (Stil behalten)",
     ["polish", "glätt", "rewrite", "smooth", "letter/polish"], False,
     "NEU z.B. POST /matching/api/letter/polish/"),
    ("W9", "Kandidat aussortieren / Status",
     ["match/.*/status", "match/.*/move"], True,
     "POST /matching/api/match/<uuid>/status|move/"),
    ("W10", "Mail senden",
     ["crm/api/email/send", "email/send"], True,
     "POST /crm/api/email/send/"),
    ("W11", "Alle anschreiben (Batch)",
     ["send_all", "sendAllAboveThreshold", "alle anschreiben"], False,
     "UI-Stub — Backend fehlt"),
    ("W12", "Wiedervorlage / Aufgabe anlegen (mit Fälligkeit)",
     ["inbox/.*/aufgabe", "aufgaben/create", "wiedervorlage"], True,
     "POST /shaduler/api/inbox/<id>/aufgabe/ (reich) oder /aufgaben/create/"),
    ("W13", "Popup-im-Popup UI-Muster vorhanden",
     ["10060", "Aufgabe erzeugen", "STAGE_MAIL", "matching-ki-wizard"], True,
     "mod-matching.js / mod-shaduler.js"),
]

lines = [
    "# Matching Wizard — API Gap Report",
    "",
    f"Generated from live scan under `{out}`",
    "",
    "| ID | Bedarf | Status | Hinweis |",
    "|----|--------|--------|---------|",
]
summary = {"OK": 0, "PARTIAL": 0, "MISSING": 0}
for wid, title, needles, expect_ok, hint in needs:
    ok = found(*needles)
    if wid in ("W5", "W6", "W7", "W8", "W11"):
        st = "PARTIAL" if ok else "MISSING"
    else:
        st = "OK" if ok else "MISSING"
    summary[st] = summary.get(st, 0) + 1
    lines.append(f"| {wid} | {title} | **{st}** | `{hint}` |")

lines += [
    "",
    "## Summary",
    f"- OK: {summary.get('OK', 0)}",
    f"- PARTIAL: {summary.get('PARTIAL', 0)}",
    f"- MISSING: {summary.get('MISSING', 0)}",
    "",
    "## Wizard Steps (Soll)",
    "1. Anfrage laden / Skills prüfen (sonst Matching Mist)",
    "2. Match starten → Shortlist nach Schwellwert (Top N)",
    "3. Sequenz: für jeden Kandidaten oberhalb Schwellwert",
    "   a. DeepSeek Begründung (CV↔Anfrage)",
    "   b. Draft Anschreiben",
    "   c. Manuell editieren (Anrede, 4-Tage-Woche, …) oder aussortieren",
    "   d. Optional glätten",
    "   e. Senden",
    "   f. Wiedervorlage anlegen (Default, editierbar wie Aufgabe erzeugen)",
    "4. Nächster Kandidat",
    "",
    "## Popup-im-Popup",
    "Ja möglich — bestehendes Muster: KI-Wizard / Kontakt→Mail Composer (gestapelte Modals).",
    "",
    "## Nächste Bau-Schritte (wenn Gaps bestätigt)",
    "1. `POST .../match/<id>/deep-reason/` — DeepSeek JSON: why, interest, reply_likelihood, risks",
    "2. `POST .../match/<id>/letter/draft/` — Draft aus Anfrage+CV+Ton",
    "3. `POST .../letter/polish/` — {draft, edits, keep_style:true}",
    "4. Shortlist-Wizard-State: exclude[], current_index, letter_drafts{}",
    "5. Nach Send: Shaduler Wiedervorlage (inbox-aufgabe Payload-Felder)",
    "",
]

text = "\n".join(lines) + "\n"
(out / "wizard-gaps.md").write_text(text, encoding="utf-8")
print(text)
PY

# ── 4) Kurzer Report ────────────────────────────────────────────────────────
{
  echo "# Matching Wizard API Inventory"
  echo
  echo "- Backend: \`$BACKEND\`"
  echo "- Out: \`$OUT\`"
  echo "- Host: \`$(hostname)\`  Date: \`$(date -Iseconds)\`"
  echo
  echo "## Files"
  echo "- \`django-urls.tsv\` — gefilterte URL-Routen"
  echo "- \`code-hits.tsv\` — Code-Treffer"
  echo "- \`wizard-gaps.md\` — Bedarf vs. Fund"
  echo
  echo "## Gaps (Auszug)"
  sed -n '1,40p' "$OUT/wizard-gaps.md"
  echo
  echo "## URL sample (matching|letter|aufgabe|email)"
  rg -i 'matching|letter|aufgabe|email/send|anschreiben|ki-wizard' "$OUT/django-urls.tsv" 2>/dev/null | head -60 || true
} > "$OUT/report.md"

echo
echo "======== FERTIG ========"
echo "Report: $OUT/report.md"
echo "Gaps:   $OUT/wizard-gaps.md"
echo
echo "Bitte pasten oder syncen:"
echo "  cat $OUT/wizard-gaps.md"
echo "  bash scripts/sync-letter-artifacts.sh matching-wizard  # ggf. anpassen"
echo "  # oder:"
echo "  cd $REPO && git add $OUT && git commit -m 'chore: matching wizard API inventory' && git push"
