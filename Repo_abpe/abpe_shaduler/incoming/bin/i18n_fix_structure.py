#!/usr/bin/env python3
"""
i18n_fix_structure.py — Shaduler Key-Struktur an Portal-Loader anpassen

Problem:
  Portal _resolveKey / Matching-_t splittet Keys an '.':
    "sh.tab_kalender" → i18nData["sh"]["tab_kalender"]

  Alte Dateien hatten:
    { "shaduler": { "sh.tab_kalender": "Kalender", ... } }
  → Lookup schlägt fehl → Fallback Deutsch.

Ziel:
    { "sh": { "tab_kalender": "Kalender", ... } }

Aufruf (Live):
  python3 apps/abpe_shaduler/bin/i18n_fix_structure.py
  python3 apps/abpe_shaduler/bin/i18n_fix_structure.py --check
  python manage.py collectstatic --noinput
  supervisorctl restart abpe-django
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import MODULE_REL, resolve_i18n_dir  # noqa: E402


def convert(data: dict) -> dict:
    """Normalize to { "sh": { "tab_kalender": "...", ... } }."""
    if not isinstance(data, dict):
        return {"sh": {}}

    # Already correct
    if "sh" in data and isinstance(data["sh"], dict):
        sample_keys = list(data["sh"].keys())[:5]
        if sample_keys and all(not k.startswith("sh.") for k in sample_keys):
            # still flatten any leftover sh.* inside
            inner = {}
            for k, v in data["sh"].items():
                if k.startswith("sh."):
                    inner[k[3:]] = v
                else:
                    inner[k] = v
            return {"sh": inner}

    src = data.get("shaduler") if isinstance(data.get("shaduler"), dict) else data
    if not isinstance(src, dict):
        return {"sh": {}}

    # If nested again under sh with dotted keys
    if "sh" in src and isinstance(src["sh"], dict) and len(src) == 1:
        src = src["sh"]

    inner = {}
    for k, v in src.items():
        if k in ("shaduler", "sh") and isinstance(v, dict):
            for k2, v2 in v.items():
                if k2.startswith("sh."):
                    inner[k2[3:]] = v2
                else:
                    inner[k2] = v2
            continue
        if k.startswith("sh."):
            inner[k[3:]] = v
        else:
            inner[k] = v
    return {"sh": inner}


def needs_convert(data: dict) -> bool:
    if not isinstance(data, dict):
        return True
    if "shaduler" in data:
        return True
    sh = data.get("sh")
    if not isinstance(sh, dict):
        return True
    return any(k.startswith("sh.") for k in sh.keys())


def main() -> None:
    parser = argparse.ArgumentParser(description="Fix Shaduler i18n key structure")
    parser.add_argument("--check", action="store_true", help="Nur prüfen, nicht schreiben")
    parser.add_argument("--dir", type=str, default=None, help="i18n-Basis überschreiben")
    args = parser.parse_args()

    i18n_dir = Path(args.dir).resolve() if args.dir else resolve_i18n_dir()
    print(f"i18n: {i18n_dir}")
    print(f"Modul: {MODULE_REL}\n")

    changed = 0
    checked = 0
    for lang_dir in sorted(i18n_dir.iterdir()):
        if not lang_dir.is_dir() or lang_dir.name.startswith("."):
            continue
        path = lang_dir / MODULE_REL / "shaduler.json"
        if not path.is_file():
            print(f"  {lang_dir.name}: — fehlt")
            continue
        checked += 1
        data = json.loads(path.read_text(encoding="utf-8"))
        if not needs_convert(data):
            # spot-check
            sh = data.get("sh", {})
            sample = {k: sh[k] for k in ("tab_kalender", "task_new", "stat_geplant") if k in sh}
            print(f"  {lang_dir.name}: ✓ OK  sample={sample}")
            continue
        fixed = convert(data)
        sample = {
            k: fixed["sh"][k]
            for k in ("tab_kalender", "task_new", "stat_geplant")
            if k in fixed["sh"]
        }
        print(f"  {lang_dir.name}: FIX → nested sh.*  sample={sample}")
        if not args.check:
            path.write_text(
                json.dumps(fixed, ensure_ascii=False, indent=4) + "\n",
                encoding="utf-8",
            )
            changed += 1

    print(f"\nGeprüft: {checked}, geändert: {changed}")
    if args.check and changed:
        sys.exit(1)


if __name__ == "__main__":
    main()
