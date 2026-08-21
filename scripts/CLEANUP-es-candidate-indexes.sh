#!/usr/bin/env bash
# Löscht NUR explizit genannte ES-Indizes (Test/Experiment/leer).
# Default DRY. Kein Wildcard-Löschen.
#
#   bash scripts/CLEANUP-es-candidate-indexes.sh
#   EXECUTE=1 INDEXES=abpe_profiles_v2,abpe_profile_versions bash scripts/CLEANUP-es-candidate-indexes.sh
#
set -euo pipefail

BACKEND="${BACKEND:-/opt/abpe/backend}"
EXECUTE="${EXECUTE:-0}"
INDEXES="${INDEXES:-}"

# Harte Sperrliste — nie löschen
PROTECTED='abpe_consultants_index abpe_namazu_profiles abpe_radar_berater abpe_emails content content_firma dms abpe_skills_index'

cd "$BACKEND"
# shellcheck disable=SC1091
[[ -f /opt/abpe/venv311/bin/activate ]] && source /opt/abpe/venv311/bin/activate
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-abpe_backend.settings}"
export EXECUTE INDEXES PROTECTED

python3 manage.py shell <<'PY'
import os, json
from elasticsearch import Elasticsearch

EXECUTE = os.environ.get("EXECUTE", "0") in ("1", "true", "TRUE", "yes")
raw = (os.environ.get("INDEXES") or "").strip()
protected = set((os.environ.get("PROTECTED") or "").split())
wanted = [x.strip() for x in raw.split(",") if x.strip()]

if not wanted:
    print("Keine INDEXES=… angegeben.")
    print("Beispiel: EXECUTE=1 INDEXES=abpe_profiles_v2,abpe_profile_versions bash scripts/CLEANUP-es-candidate-indexes.sh")
    raise SystemExit(0)

cfg = {}
try:
    cfg = json.load(open("/opt/abpe/backend/settings.json"))
except Exception:
    pass
hosts = (cfg.get("elasticsearch") or {}).get("hosts") or ["http://localhost:9200"]
es = Elasticsearch(hosts, verify_certs=False, request_timeout=60)

for name in wanted:
    if name in protected:
        print(f"BLOCKED (protected): {name}")
        continue
    exists = es.indices.exists(index=name)
    docs = 0
    if exists:
        try:
            docs = es.count(index=name)["count"]
        except Exception:
            pass
    print(f"{'DELETE' if EXECUTE else 'DRY'} {name} exists={exists} docs={docs}")
    if EXECUTE and exists:
        es.indices.delete(index=name)
        print(f"  → deleted {name}")
PY
