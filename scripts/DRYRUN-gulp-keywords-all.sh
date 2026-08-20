#!/usr/bin/env bash
# Dry-Run: Keyword-Detection v1.1 über ALLE CRM gulp_profil_c (kein TXT-Dump ins Repo).
# Schreibt Summary + Fail-Liste unter OUT. Kein PDF, kein DB-Write.
#
# Auf ucs5:
#   cd /opt/abpe/backend && source /opt/abpe/venv311/bin/activate
#   MIN_LEN=200 OUT=/tmp/gulp-keyword-dryrun-$(date +%Y%m%d-%H%M%S) \
#     bash /mnt/public/udoo-reprap/scripts/DRYRUN-gulp-keywords-all.sh
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
OUT="${OUT:-/tmp/gulp-keyword-dryrun-$(date +%Y%m%d-%H%M%S)}"
MIN_LEN="${MIN_LEN:-200}"
LIMIT="${LIMIT:-0}"  # 0 = all

mkdir -p "$OUT"
cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"
export OUT MIN_LEN LIMIT

python3 manage.py shell <<'PY'
import os, re, json
from pathlib import Path
from collections import Counter, defaultdict
from django.apps import apps

OUT = Path(os.environ["OUT"])
MIN_LEN = int(os.environ.get("MIN_LEN", "200"))
LIMIT = int(os.environ.get("LIMIT", "0"))
OUT.mkdir(parents=True, exist_ok=True)

CrmContactCstm = apps.get_model("abpe_crm", "CrmContactCstm")
CrmContact = apps.get_model("abpe_crm", "CrmContact")

def norm_text(t: str) -> str:
    for ch in ("\u00a0", "\u2009", "\u202f"):
        t = t.replace(ch, " ")
    for ch in ("\u200b", "\u00ad"):
        t = t.replace(ch, "")
    return t.replace("&amp;", "&")

CORE_SECTIONS = [
    r"Fachlicher\s+Schwerpunkt", r"Schwerpunkt", r"Position", r"Ausbildung",
    r"Beruflicher\s+Werdegang", r"(?:Durchgef[uü]hrte\s+)?Projekte",
    r"Projekt[uü]bersicht", r"Branchen?", r"Fremdsprachen", r"Einsatzort",
    r"Regionen(?:\s*&\s*L[aä]nder)?", r"Kommentar", r"Sonstige\s+Anmerkungen",
    r"Bemerkungen", r"Stammdaten(?:\s*\(Auszug\))?", r"Personendaten",
    r"Zertifizierungen?", r"Top[- ]Skills",
]
SKILL_SECTIONS = [
    r"Hardware(?:plattform)?", r"Betriebssysteme", r"Programmiersprachen?",
    r"Datenbank(?:en)?", r"Datenkommunikation",
    r"Software(?:\s*/\s*Tools(?:\s*/\s*Methoden)?)?", r"Tools?", r"Office\s+Tools?",
    r"Web\s*/\s*Portal-Server", r"Repositories", r"J2EE\s+Technologien",
    r"J2SE\s+Technologien", r"Methodisches\s+Vorgehen", r"Methoden",
    r"Produkte\s*/\s*Standards\s*/\s*Erfahrungen",
    r"Produkte\s*\|\s*Standards(?:\s*\|\s*Erfahrungen)?",
    r"Kenntnisse", r"EDV[- ]Kenntnisse",
    r"Design/Entwicklung/Konstruktion",
    r"Berechnung/Simulation/Versuch/Validierung", r"Middleware",
]
PROJECT_FIELDS = [
    r"Zeitraum", r"Dauer", r"Rolle(?:\s+im\s+Projekt)?", r"Kunde",
    r"Firma(?:/Institut)?", r"Firma", r"Auftrag",
    r"Aufgaben(?:\s+im\s+Projekt)?", r"Aufgabenstellung", r"Projektinhalte",
    r"Beschreibung", r"Kenntnisse", r"Eingesetzte\s+Produkte", r"Technologie",
    r"Projektumgebung", r"Systemumgebung", r"Verantwortung", r"Referenzen",
    r"T[aä]tigkeiten",
]
STAMM_FIELDS = [
    r"Personen[- ]?ID", r"Wohnort", r"Jahrgang", r"Staatsb[uü]rgerschaft",
    r"Stundensatz", r"Verf[uü]gbar\s+ab", r"verf[uü]gbar\s+zu",
    r"davon\s+vor\s+Ort", r"Remote[- ]Einsatz", r"Kontaktwunsch",
    r"Unternehmensgr[oö]ße", r"Profil\s+erstellt\s+am",
    r"Profil\s+zuletzt\s+ge[aä]ndert\s+am", r"EDV[- ]Erfahrung\s+seit",
]

def compile_label(pat: str):
    return re.compile(rf"(?im)(?:^|(?<=\s{{2}})|(?<=\t))(?:{pat})\s*:?\s*")

compiled = []
for group, pats in [
    ("core", CORE_SECTIONS),
    ("skill", SKILL_SECTIONS),
    ("proj", PROJECT_FIELDS),
    ("stamm", STAMM_FIELDS),
]:
    for p in pats:
        compiled.append((group, p, compile_label(p)))

ZEITRAUM_LOOSE = re.compile(r"(?im)(?:^|(?<=\s))Zeitraum\s*:")
DATE_LED = re.compile(
    r"(?m)^\s*(?:"
    r"\d{1,2}[./]\d{1,2}[./]\d{2,4}\s*[-–]\s*\d{1,2}[./]\d{1,2}[./]\d{2,4}"
    r"|"
    r"(?:0?[1-9]|1[0-2])[/.-](?:19|20)\d{2}\s*[-–]\s*(?:0?[1-9]|1[0-2]|heute|aktuell|laufend)"
    r"|"
    r"(?:19|20)\d{2}[-/.](?:0?[1-9]|1[0-2])(?:[-/.]\d{1,2})?\s*[-–]\s*"
    r"(?:(?:19|20)\d{2}[-/.](?:0?[1-9]|1[0-2])(?:[-/.]\d{1,2})?|heute|aktuell|laufend)"
    r"|"
    r"(?:Jan|Feb|Mär|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)[a-zä.]*\s+(?:19|20)\d{2}\s*[-–]"
    r")",
    re.IGNORECASE,
)

qs = (
    CrmContactCstm.objects.exclude(gulp_profil_c__isnull=True)
    .exclude(gulp_profil_c="")
    .values_list("contact_id", "gulp_id_c", "gulp_profil_c")
)

n = 0
ok = 0
skip_short = 0
fails = []
stats = Counter()
pattern_docs = defaultdict(Counter)

for contact_id, gulp_id, profil in qs.iterator(chunk_size=200):
    text = (profil or "").strip()
    if len(text) < MIN_LEN:
        skip_short += 1
        continue
    n += 1
    if LIMIT and n > LIMIT:
        n -= 1
        break
    text = norm_text(text)
    hit = defaultdict(set)
    for group, name, rx in compiled:
        if rx.search(text):
            hit[group].add(name)
            pattern_docs[group][name] += 1

    has_zeitraum = ("Zeitraum" in hit["proj"]) or bool(ZEITRAUM_LOOSE.search(text))
    has_date_led = bool(DATE_LED.search(text))
    has_projekte = any("Projekte" in x or "Projekt" in x for x in hit["core"])
    has_schwerpunkt = any("Schwerpunkt" in x for x in hit["core"])
    has_position = "Position" in hit["core"]
    has_ausbildung = "Ausbildung" in hit["core"] or any(
        "Werdegang" in x for x in hit["core"]
    )
    has_skills = len(hit["skill"]) >= 2
    proj_rich = len(hit["proj"]) >= 3 or any(
        "Projektinhalte" in x or "Rolle" in x for x in hit["proj"]
    )
    project_signal = has_projekte or has_zeitraum or has_date_led
    identity = has_schwerpunkt or has_position

    stats["projekte"] += int(has_projekte)
    stats["project_signal"] += int(project_signal)
    stats["schwerpunkt"] += int(has_schwerpunkt)
    stats["position"] += int(has_position)
    stats["ausbildung"] += int(has_ausbildung)
    stats["skills"] += int(has_skills)
    stats["zeitraum"] += int(has_zeitraum)
    stats["date_led"] += int(has_date_led)
    stats["proj_rich"] += int(proj_rich)

    is_ok = False
    if project_signal:
        if identity and (has_skills or has_ausbildung or proj_rich):
            is_ok = True
        elif has_ausbildung and has_skills:
            is_ok = True
    if is_ok:
        ok += 1
    else:
        # resolve name lazily only for fails
        try:
            cid_int = int(contact_id)
        except (TypeError, ValueError):
            cid_int = contact_id
        c = CrmContact.objects.filter(id=cid_int).only("first_name", "last_name").first()
        last = (getattr(c, "last_name", None) or "") if c else ""
        first = (getattr(c, "first_name", None) or "") if c else ""
        reason = []
        if not project_signal:
            reason.append("no_project_signal")
        if not identity:
            reason.append("no_identity")
        if not (has_skills or has_ausbildung or proj_rich):
            reason.append("no_skills_edu_projrich")
        fails.append(
            f"{contact_id}\t{gulp_id or ''}\t{last}\t{first}\t{len(text)}\t{','.join(reason)}"
        )
    if n % 500 == 0:
        print(f"... scanned={n} ok={ok} fails={len(fails)}")

summary = {
    "version": "v1.2-dryrun",
    "min_len": MIN_LEN,
    "n_scanned": n,
    "skip_short": skip_short,
    "ok_min_structure": ok,
    "ok_pct": round(100 * ok / n, 2) if n else 0,
    "fails_n": len(fails),
    "stats": dict(stats),
}
(OUT / "summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
(OUT / "fails.tsv").write_text(
    "contact_id\tgulp_id\tlast\tfirst\tlen\treason\n"
    + "\n".join(fails)
    + ("\n" if fails else ""),
    encoding="utf-8",
)
# top pattern coverage
lines = ["group\tpattern\tdocs\tpct"]
for group, ctr in pattern_docs.items():
    for pat, d in sorted(ctr.items(), key=lambda x: -x[1]):
        lines.append(f"{group}\t{pat}\t{d}\t{100 * d / n:.1f}")
(OUT / "pattern_coverage.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")

print("======== Gulp Keyword DRY-RUN v1.2 ALL ========")
print(json.dumps(summary, ensure_ascii=False, indent=2))
print(f"fails: {OUT / 'fails.tsv'}")
print(f"OUT={OUT}")
PY
