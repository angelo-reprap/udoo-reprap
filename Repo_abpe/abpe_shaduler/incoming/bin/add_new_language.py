#!/usr/bin/env python3
"""
add_new_language.py — Shaduler-Modul
====================================
Füllt modules/shaduler/ für eine Portal-Sprache (aus DE via Deepseek).

Das legt KEINE komplette Portal-Sprache an (das macht apps/abpe_ui/bin/).
Hier nur: Shaduler-JSON + optional module.json titles.

Aufruf:
  python3 apps/abpe_shaduler/bin/add_new_language.py --list
  python3 apps/abpe_shaduler/bin/add_new_language.py --missing
  python3 apps/abpe_shaduler/bin/add_new_language.py --add fr
  python3 apps/abpe_shaduler/bin/add_new_language.py --sync-all

Sprachdatei:
  /opt/abpe/backend/apps/abpe_ui/static/abpe_ui/i18n/<lang>/modules/shaduler/shaduler.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import (  # noqa: E402
    BASE_DIR,
    MODULE_REL,
    REF_LANG,
    module_dir,
    resolve_i18n_dir,
    resolve_translator,
    shaduler_json,
)

LANG_MAP_JSON = Path(__file__).resolve().parent / "lang_map.json"

LANG_MAP = {
    "en": {"name": "English", "native": "English", "flag": "🇬🇧"},
    "fr": {"name": "French", "native": "Français", "flag": "🇫🇷"},
    "it": {"name": "Italian", "native": "Italiano", "flag": "🇮🇹"},
    "es": {"name": "Spanish", "native": "Español", "flag": "🇪🇸"},
    "nl": {"name": "Dutch", "native": "Nederlands", "flag": "🇳🇱"},
    "pl": {"name": "Polish", "native": "Polski", "flag": "🇵🇱"},
    "pt": {"name": "Portuguese", "native": "Português", "flag": "🇵🇹"},
    "ru": {"name": "Russian", "native": "Русский", "flag": "🇷🇺"},
    "tr": {"name": "Turkish", "native": "Türkçe", "flag": "🇹🇷"},
    "hu": {"name": "Hungarian", "native": "Magyar", "flag": "🇭🇺"},
    "ar": {"name": "Arabic", "native": "العربية", "flag": "🇸🇦"},
    "ja": {"name": "Japanese", "native": "日本語", "flag": "🇯🇵"},
    "ko": {"name": "Korean", "native": "한국어", "flag": "🇰🇷"},
    "zh": {"name": "Chinese", "native": "中文", "flag": "🇨🇳"},
}


def _load_lang_map() -> dict:
    if LANG_MAP_JSON.exists():
        try:
            ext = json.loads(LANG_MAP_JSON.read_text(encoding="utf-8"))
            return {**LANG_MAP, **ext}
        except Exception:
            pass
    return LANG_MAP


def _portal_langs(i18n_dir: Path) -> list[str]:
    return sorted(
        d.name for d in i18n_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
    )


def _has_shaduler(i18n_dir: Path, lang: str) -> bool:
    return shaduler_json(lang, i18n_dir).is_file()


def list_status(i18n_dir: Path) -> None:
    info = _load_lang_map()
    print(f"i18n: {i18n_dir}")
    print(f"Modul: {MODULE_REL}\n")
    for code in _portal_langs(i18n_dir):
        meta = info.get(code, {})
        flag = meta.get("flag", "🏳️")
        name = meta.get("name", code.upper())
        ok = _has_shaduler(i18n_dir, code)
        ref = " (Ref)" if code == REF_LANG else ""
        mark = "✓" if ok else "✗ fehlt"
        print(f"  {flag} {code:<4} {name:<15} {mark}{ref}")
        if ok:
            print(f"       → {shaduler_json(code, i18n_dir)}")


def list_missing(i18n_dir: Path) -> list[str]:
    missing = [
        c for c in _portal_langs(i18n_dir) if c != REF_LANG and not _has_shaduler(i18n_dir, c)
    ]
    if not missing:
        print("Alle Portal-Sprachen haben modules/shaduler/shaduler.json")
    else:
        print("Fehlendes Shaduler-Modul:")
        for c in missing:
            print(f"  ✗ {c}  → würde anlegen: {shaduler_json(c, i18n_dir)}")
    return missing


def add_language(lang_code: str, i18n_dir: Path) -> dict:
    lang_code = lang_code.lower().strip()
    if lang_code == REF_LANG:
        return {"success": False, "error": "DE ist Referenzsprache."}

    module_dir(lang_code, i18n_dir).mkdir(parents=True, exist_ok=True)
    translator = resolve_translator()
    log_lines = [
        f"Shaduler-Modul für {lang_code}",
        f"Ziel: {shaduler_json(lang_code, i18n_dir)}",
        f"Translator: {translator}",
    ]

    try:
        proc = subprocess.run(
            [sys.executable, str(translator), "--lang", lang_code],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(BASE_DIR) if (BASE_DIR / "manage.py").exists() else str(Path.cwd()),
        )
        log_lines.append(proc.stdout.strip())
        if proc.stderr:
            log_lines.append(proc.stderr.strip())
        if proc.returncode != 0:
            return {"success": False, "error": proc.stderr or "Translator failed", "log": "\n".join(log_lines)}
    except Exception as e:
        return {"success": False, "error": str(e), "log": "\n".join(log_lines)}

    ok = _has_shaduler(i18n_dir, lang_code)
    log_lines.append(f"{'✅' if ok else '✗'} {lang_code} — {date.today().isoformat()}")
    return {
        "success": ok,
        "code": lang_code,
        "path": str(shaduler_json(lang_code, i18n_dir)),
        "log": "\n".join(log_lines),
    }


def sync_all(i18n_dir: Path) -> None:
    missing = list_missing(i18n_dir)
    for code in missing:
        print(f"\n── {code} ──")
        r = add_language(code, i18n_dir)
        print(r.get("log") or r.get("error"))


def main():
    parser = argparse.ArgumentParser(description="Shaduler Modul-Sprachpaket")
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--list", action="store_true", help="Status je Portal-Sprache")
    grp.add_argument("--missing", action="store_true", help="Sprachen ohne Shaduler-JSON")
    grp.add_argument("--add", metavar="CODE", help="Shaduler-Modul für Sprache anlegen/übersetzen")
    grp.add_argument("--sync-all", action="store_true", help="Alle fehlenden Sprachen nachziehen")
    args = parser.parse_args()

    i18n_dir = resolve_i18n_dir()
    if not i18n_dir.exists():
        print(f"i18n nicht gefunden: {i18n_dir}")
        sys.exit(1)

    if args.list:
        list_status(i18n_dir)
    elif args.missing:
        list_missing(i18n_dir)
    elif args.add:
        r = add_language(args.add, i18n_dir)
        print(r.get("log") or "")
        print(("✅" if r["success"] else "✗"), r.get("path") or r.get("error"))
        sys.exit(0 if r["success"] else 1)
    elif args.sync_all:
        sync_all(i18n_dir)


if __name__ == "__main__":
    main()
