#!/usr/bin/env bash
# Schnellcheck: Cleaner → experience[] für gulp-samples (ohne Pipeline).
# Auf ucs5 nach git pull:
#   bash scripts/VERIFY-gulp-clean-experience.sh
set -euo pipefail
REPO="${REPO:-/mnt/public/udoo-reprap}"
cd "$REPO"
python3 <<'PY'
from pathlib import Path
import importlib.util

repo = Path(".").resolve()
mod_path = repo / "Repo_abpe/cv_extractor/incoming/services/gulp_profile_clean.py"
spec = importlib.util.spec_from_file_location("gpc", mod_path)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)
print(f"cleaner={mod_path}")
print(f"mtime={mod_path.stat().st_mtime}")

samples = repo / "artifacts/gulp-samples/txt"
names = [
    "arnold_jens", "ungureanu_lucian", "ahmad_ahmad", "ackermann_stefan",
    "anacker_ellen", "aydin_andac", "baker_ashraf", "bauchmueller_peter",
    "bauer_joachim", "beemers_heiko",
]
ok = fail = 0
for name in names:
    fp = samples / f"{name}.txt"
    if not fp.is_file():
        print(f"MISS {name}")
        fail += 1
        continue
    last, first = name.rsplit("_", 1)
    prof = g.clean_gulp_profile(
        fp.read_text(encoding="utf-8", errors="replace"),
        first=first.title(),
        last=last.replace("_", " ").title(),
    )
    n = len(prof.get("experience") or [])
    plain = g.profile_to_aid_plain(prof)
    z = plain.count("Zeitraum:")
    status = "OK" if n >= 1 else "FAIL"
    if n >= 1:
        ok += 1
    else:
        fail += 1
    print(f"{status:4} {name:22} experience={n:2} Zeitraum:={z:2}")

print(f"\nSumme: ok={ok} fail={fail}")
if fail:
    raise SystemExit(1)
PY
