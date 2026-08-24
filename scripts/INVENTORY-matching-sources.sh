#!/usr/bin/env bash
# Inventur: Matching-Quellen (DB / ES / Namazu) — was Shortlist HEUTE nutzt vs. was existiert.
#
# ucs5:
#   cd /mnt/public/udoo-reprap
#   git fetch origin cursor/matching-sources-inventory-1532
#   git checkout cursor/matching-sources-inventory-1532   # oder: bash <(git show …)
#   bash scripts/INVENTORY-matching-sources.sh
#
# Optional:
#   SAMPLE_LAST=Abbady SAMPLE_FIRST=Brahim bash scripts/INVENTORY-matching-sources.sh
#   PROJECT_ID=<uuid> bash scripts/INVENTORY-matching-sources.sh
#
set -euo pipefail

REPO="${REPO:-/mnt/public/udoo-reprap}"
BACKEND="${BACKEND:-/opt/abpe/backend}"
OUT="${OUT:-/tmp/matching-sources-$(date +%Y%m%d-%H%M%S)}"
NAMAZU_DIR="${NAMAZU_DIR:-/var/www/namazu/index}"
SAMPLE_LAST="${SAMPLE_LAST:-Abbady}"
SAMPLE_FIRST="${SAMPLE_FIRST:-Brahim}"
PROJECT_ID="${PROJECT_ID:-}"

mkdir -p "$OUT"
cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"
export OUT SAMPLE_LAST SAMPLE_FIRST PROJECT_ID NAMAZU_DIR REPO

python3 manage.py shell <<'PY'
import json, os, re, sys
from pathlib import Path
from collections import Counter

OUT = Path(os.environ["OUT"])
SAMPLE_LAST = (os.environ.get("SAMPLE_LAST") or "").strip()
SAMPLE_FIRST = (os.environ.get("SAMPLE_FIRST") or "").strip()
PROJECT_ID = (os.environ.get("PROJECT_ID") or "").strip()
NAMAZU_DIR = Path(os.environ.get("NAMAZU_DIR") or "/var/www/namazu/index")
report = {"out": str(OUT), "sources": {}, "notes": []}

def section(title):
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)

# ── 1) MatchingEngine weights / code path ──────────────────────────
section("1) MatchingEngine (Shortlist) — was der Code WIRKLICH nutzt")
try:
    from apps.abpe_matching_workflow.services.matching_engine import MatchingEngine
    eng = MatchingEngine()
    engine_info = {
        "module": MatchingEngine.__module__,
        "weights": {
            "required_skills": eng.w_req,
            "nice_skills": eng.w_nice,
            "industry": eng.w_industry,
            "experience": eng.w_exp,
            "location": eng.w_loc,
        },
        "min_score_default": eng.min_score,
        "uses_elasticsearch": "elasticsearch" in Path(
            sys.modules[MatchingEngine.__module__].__file__
        ).read_text(encoding="utf-8", errors="replace").lower(),
        "uses_namazu": "namazu" in Path(
            sys.modules[MatchingEngine.__module__].__file__
        ).read_text(encoding="utf-8", errors="replace").lower(),
        "data_source": (
            "cv_extractor.Consultant + ConsultantSkill.weight (ORM) "
            "+ optional ES recall abpe_matching_profiles_probe"
        ),
        "skill_blends": {
            "coverage": getattr(eng, "cov_blend", None),
            "strength": getattr(eng, "str_blend", None),
        },
        "es_recall": getattr(eng, "es_recall_cfg", {}),
        "formula": (
            "req = cov_blend*coverage + str_blend*strength(ConsultantSkill.weight); "
            "overall = req*w_req + nice*w_nice + industry*w_ind + exp*w_exp + loc*w_loc"
        ),
    }
    print(json.dumps(engine_info, indent=2, ensure_ascii=False))
    report["sources"]["matching_engine"] = engine_info
except Exception as e:
    print(f"FAIL MatchingEngine: {e}")
    report["notes"].append(f"MatchingEngine: {e}")

# settings.json matching block
try:
    settings_path = Path("/opt/abpe/backend/settings.json")
    cfg = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.is_file() else {}
    mcfg = cfg.get("matching") or {}
    escfg = cfg.get("elasticsearch") or {}
    print("\nsettings.json matching.scoring:", json.dumps(mcfg.get("scoring") or {}, indent=2))
    print("settings.json elasticsearch.hosts:", escfg.get("hosts"))
    report["sources"]["settings_matching"] = mcfg
    report["sources"]["settings_elasticsearch"] = {"hosts": escfg.get("hosts")}
except Exception as e:
    print(f"settings.json: {e}")

# ── 2) DB Consultant pool ──────────────────────────────────────────
section("2) DB — cv_extractor.Consultant (Matching-Pool)")
from django.apps import apps
Consultant = apps.get_model("cv_extractor", "Consultant")
fields = [f.name for f in Consultant._meta.get_fields() if hasattr(f, "column")]
print("Consultant fields (sample):", sorted(fields)[:40], "… total", len(fields))
gulp_fields = [f for f in fields if "gulp" in f.lower()]
print("gulp* fields:", gulp_fields or "(keine)")

status_counts = Counter(
    Consultant.objects.values_list("status", flat=True)
)
print("status counts:", dict(status_counts))
pool = Consultant.objects.filter(status__in=["completed", "validated"])
print("pool completed|validated:", pool.count())
print("exclude -en:", pool.exclude(aid__endswith="-en").count())
print("with location set:", pool.exclude(location__isnull=True).exclude(location="").count())

# Skills model
try:
    ConsultantSkill = apps.get_model("cv_extractor", "ConsultantSkill")
    Skill = apps.get_model("cv_extractor", "Skill")
    print("Skill rows:", Skill.objects.count())
    print("ConsultantSkill rows:", ConsultantSkill.objects.count())
    # weight field?
    cs_fields = [f.name for f in ConsultantSkill._meta.get_fields() if hasattr(f, "column")]
    print("ConsultantSkill fields:", cs_fields)
    report["sources"]["db"] = {
        "status_counts": dict(status_counts),
        "pool_completed_validated": pool.count(),
        "skills": Skill.objects.count(),
        "consultant_skills": ConsultantSkill.objects.count(),
        "consultant_skill_fields": cs_fields,
        "gulp_fields_on_consultant": gulp_fields,
    }
except Exception as e:
    print(f"Skills: {e}")

# Sample person
if SAMPLE_LAST:
    section(f"2b) Stichprobe DB: {SAMPLE_FIRST} {SAMPLE_LAST}")
    qs = Consultant.objects.filter(last_name__icontains=SAMPLE_LAST)
    if SAMPLE_FIRST:
        qs = qs.filter(first_name__icontains=SAMPLE_FIRST)
    qs = qs.order_by("-created_at")[:5]
    samples = []
    for c in qs:
        skills = []
        try:
            skills = sorted({cs.skill.name for cs in c.skills.select_related("skill").all()})[:40]
        except Exception:
            pass
        row = {
            "id": c.id,
            "aid": getattr(c, "aid", None),
            "dir": getattr(c, "consultant_dir", None),
            "status": c.status,
            "location": getattr(c, "location", None),
            "availability": getattr(c, "availability", None),
            "skills_n": len(skills),
            "skills_head": skills[:15],
        }
        for gf in gulp_fields:
            row[gf] = getattr(c, gf, None)
        samples.append(row)
        print(json.dumps(row, ensure_ascii=False, default=str))
    report["sources"]["sample_consultant"] = samples
    if not samples:
        print("(keine Treffer)")

# ── 3) Elasticsearch ───────────────────────────────────────────────
section("3) Elasticsearch — Indizes + Doc-Counts + Mapping-Felder")
es_info = {"indexes": {}}
try:
    from elasticsearch import Elasticsearch
    hosts = (report.get("sources", {}).get("settings_elasticsearch") or {}).get("hosts") or [
        "http://localhost:9200"
    ]
    es = Elasticsearch(hosts, verify_certs=False, request_timeout=20)
    print("ping:", es.ping())
    wanted = [
        "abpe_consultants_index",
        "abpe_namazu_profiles",
        "abpe_skills_index",
        "abpe_profile_versions",
        "abpe_profiles_v2",
        "abpe_radar_berater",
        "content",
        "content_firma",
    ]
    # also discover abpe_* 
    try:
        all_idx = sorted(es.indices.get_alias(index="*").keys())
        for i in all_idx:
            if i.startswith(("abpe_", ".")):
                continue
            if i.startswith("abpe") or "namazu" in i or "consultant" in i or "gulp" in i:
                if i not in wanted:
                    wanted.append(i)
        report["sources"]["es_all_abpe_ish"] = [
            i for i in all_idx if "abpe" in i or "namazu" in i or "consultant" in i
        ]
    except Exception as e:
        print("alias list:", e)

    for idx in wanted:
        try:
            if not es.indices.exists(index=idx):
                print(f"  {idx}: MISSING")
                continue
            cnt = es.count(index=idx)["count"]
            mapping = es.indices.get_mapping(index=idx)
            props = (
                mapping.get(idx, {})
                .get("mappings", {})
                .get("properties", {})
            )
            fields = sorted(props.keys())
            gulpish = [f for f in fields if "gulp" in f.lower() or f in ("aid", "skills", "location", "body", "content")]
            print(f"  {idx}: docs={cnt} fields={len(fields)} key={gulpish[:12]}")
            # sample 1 doc
            sample = None
            try:
                hits = es.search(index=idx, size=1, query={"match_all": {}}).get("hits", {}).get("hits", [])
                if hits:
                    src = hits[0].get("_source") or {}
                    sample = {k: src.get(k) for k in list(src.keys())[:20]}
            except Exception:
                pass
            es_info["indexes"][idx] = {
                "docs": cnt,
                "fields": fields[:80],
                "sample_keys": list((sample or {}).keys()),
                "sample": sample,
            }
        except Exception as e:
            print(f"  {idx}: ERR {e}")
    report["sources"]["elasticsearch"] = es_info

    # Search sample name in namazu ES + consultants ES
    if SAMPLE_LAST:
        section(f"3b) ES Stichprobe Name: {SAMPLE_FIRST} {SAMPLE_LAST}")
        for idx in ("abpe_namazu_profiles", "abpe_consultants_index", "abpe_radar_berater"):
            if idx not in es_info["indexes"]:
                continue
            q = {
                "bool": {
                    "should": [
                        {"match_phrase": {"last_name": SAMPLE_LAST}},
                        {"match_phrase": {"nachname": SAMPLE_LAST}},
                        {"match": {"name": SAMPLE_LAST}},
                        {"query_string": {"query": f"*{SAMPLE_LAST}*", "fields": ["*"]}},
                    ],
                    "minimum_should_match": 1,
                }
            }
            try:
                res = es.search(index=idx, size=3, query=q)
                hits = res.get("hits", {}).get("hits", [])
                print(f"  {idx}: hits={res.get('hits',{}).get('total')}")
                for h in hits:
                    s = h.get("_source") or {}
                    print("   ", {k: s.get(k) for k in list(s.keys())[:12]})
            except Exception as e:
                print(f"  {idx} search: {e}")
except Exception as e:
    print(f"ES FAIL: {e}")
    report["notes"].append(f"ES: {e}")

# ── 4) Namazu FS ───────────────────────────────────────────────────
section("4) Namazu Dateisystem")
namazu = {"dir": str(NAMAZU_DIR), "exists": NAMAZU_DIR.is_dir()}
if NAMAZU_DIR.is_dir():
    htmls = list(NAMAZU_DIR.glob("*.html"))
    namazu["html_count"] = len(htmls)
    # pattern name__name__uuid.html
    pat = re.compile(r"^([^_]+)__([^_]+)__([a-f0-9-]+)\.html$", re.I)
    parsed = 0
    gulpish = 0
    examples = []
    for p in htmls[:5000]:
        m = pat.match(p.name)
        if m:
            parsed += 1
            if SAMPLE_LAST and SAMPLE_LAST.lower() in p.name.lower():
                examples.append(p.name)
        if "gulp" in p.name.lower():
            gulpish += 1
    namazu["parsed_name_uuid_pattern_in_first_5k"] = parsed
    namazu["sample_name_matches"] = examples[:10]
    print(json.dumps(namazu, indent=2, ensure_ascii=False))
    # content sniff one Abbady file
    for p in NAMAZU_DIR.glob(f"*{SAMPLE_LAST}*"):
        text = p.read_text(encoding="utf-8", errors="replace")[:500]
        print(f"\nNamazu file {p.name} head:\n{text[:300]}")
        break
else:
    print("Namazu dir fehlt:", NAMAZU_DIR)
report["sources"]["namazu_fs"] = namazu

# ── 5) ProjectRequest sample (optional) ────────────────────────────
if PROJECT_ID:
    section(f"5) ProjectRequest {PROJECT_ID}")
    try:
        PR = apps.get_model("abpe_matching_workflow", "ProjectRequest")
        # uuid or project_number
        pr = None
        try:
            pr = PR.objects.filter(id=PROJECT_ID).first()
        except Exception:
            pass
        if pr is None:
            pr = PR.objects.filter(project_number__icontains=PROJECT_ID).first()
        if pr:
            print({
                "id": str(pr.id),
                "number": pr.project_number,
                "title": pr.title,
                "required_skills": pr.required_skills,
                "nice": pr.nice_to_have_skills,
                "location": pr.location,
                "remote": pr.remote_possible,
                "threshold": pr.shortlist_threshold,
                "extracted_technologies": pr.extracted_technologies,
            })
            MR = apps.get_model("abpe_matching_workflow", "MatchResult")
            print("MatchResult count:", MR.objects.filter(project=pr).count())
            top = list(
                MR.objects.filter(project=pr).order_by("-overall_score")[:10].values(
                    "consultant_id", "overall_score", "req_score", "matched_skills"
                )
            )
            print("top:", json.dumps(top, indent=2, default=str, ensure_ascii=False))
        else:
            print("Project nicht gefunden")
    except Exception as e:
        print(f"Project: {e}")

# ── 6) Verdict ─────────────────────────────────────────────────────
section("6) Kurz-Fazit")
verdict = {
    "shortlist_today": "NUR Postgres Consultant(+Skills) via MatchingEngine — kein ES, kein Namazu",
    "weights_used": "settings.json matching.scoring (req/nice/industry/exp/location)",
    "weights_NOT_used": [
        "ConsultantSkill.weight (falls vorhanden) — Engine prüft nur Skill-Name vorhanden",
        "ProjectRequest.weight_skills_* Overrides — Engine liest sie nicht",
        "ES relevance / Namazu rank",
    ],
    "es_candidates_for_merge": [
        "abpe_namazu_profiles (groß, gulp_id) — GULP-Korpus",
        "abpe_consultants_index (klein) — AID nach Import, oft hinter DB",
        "abpe_radar_berater — Radar, nicht Shortlist",
    ],
    "next_checks": [
        "Doc-Counts live bestätigen",
        "Join-Key AID consultant_dir ↔ gulp_id ↔ Namazu HTML",
        "Ob ES allein Skills+Location+Availability für Anfrage-Match trägt",
        "Dedup: ein Berater in DB+Namazu+ES → ein Shortlist-Eintrag mit Quellen-Flags",
    ],
}
print(json.dumps(verdict, indent=2, ensure_ascii=False))
report["verdict"] = verdict
(OUT / "summary.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
    encoding="utf-8",
)
print(f"\n→ {OUT}/summary.json")
PY

echo
echo "Fertig: $OUT"
echo "  summary: $OUT/summary.json"
