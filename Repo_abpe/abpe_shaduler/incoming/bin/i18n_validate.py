#!/usr/bin/env python3
"""
i18n_validate.py — Shaduler-Modul
=================================
Prüft nur modules/shaduler/ unter dem Portal-i18n-Baum.

  1. Struktur — Dateien wie in DE vorhanden
  2. Keys     — Keys identisch wie DE
  3. Sprache  — Inhalt in Zielsprache (Deepseek, optional)
  4. Titles   — titles.<lang> in Shaduler module.json
  5. --fix    — fehlerhafte JSONs löschen + Translator aufrufen

Aufruf:
  python3 apps/abpe_shaduler/bin/i18n_validate.py
  python3 apps/abpe_shaduler/bin/i18n_validate.py --fix
  python3 apps/abpe_shaduler/bin/i18n_validate.py --lang en --fix

Sprachdatei:
  /opt/abpe/backend/apps/abpe_ui/static/abpe_ui/i18n/<lang>/modules/shaduler/shaduler.json
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import requests
import urllib3

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import (  # noqa: E402
    BASE_DIR,
    MODULE_REL,
    REF_LANG,
    SETTINGS,
    resolve_i18n_dir,
    resolve_module_json,
    resolve_translator,
    shaduler_json,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LANG_NAMES = {
    "de": "German", "en": "English", "fr": "French", "it": "Italian",
    "es": "Spanish", "pt": "Portuguese", "nl": "Dutch", "pl": "Polish",
    "ru": "Russian", "tr": "Turkish", "ar": "Arabic", "zh": "Chinese",
    "ja": "Japanese", "ko": "Korean", "cs": "Czech", "hu": "Hungarian",
    "ro": "Romanian", "sv": "Swedish", "da": "Danish", "fi": "Finnish",
    "no": "Norwegian",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("shaduler_i18n_validate")


def _load_settings() -> dict:
    if SETTINGS.exists():
        try:
            return json.loads(SETTINGS.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _load_api_key() -> Optional[str]:
    return _load_settings().get("ai_models", {}).get("deepseek", {}).get("api_key")


def _load_workers() -> int:
    return _load_settings().get("pipeline", {}).get("parallel_workers_i18n", 10)


def _extract_text_values(data, results=None):
    if results is None:
        results = []
    if isinstance(data, dict):
        for v in data.values():
            _extract_text_values(v, results)
    elif isinstance(data, list):
        for item in data:
            _extract_text_values(item, results)
    elif isinstance(data, str) and len(data.strip()) > 10:
        clean = re.sub(r"<[^>]+>", " ", data).strip()
        if len(clean) > 10:
            results.append(clean[:500])
    return results


def _check_language_with_llm(
    file_path: Path, target_lang: str, api_key: str, retries: int = 3
) -> tuple[bool, str, list]:
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, "unknown", [f"Lesefehler: {e}"]

    texts = _extract_text_values(data)
    if not texts:
        return True, target_lang, []

    combined = "\n".join(texts[:50])
    target_name = LANG_NAMES.get(target_lang, target_lang.upper())
    prompt = (
        f"You are a language detection expert. "
        f"Analyze the following text content from a JSON file that should be in {target_name}.\n\n"
        f"TEXT:\n{combined}\n\n"
        f"Answer ONLY with valid JSON:\n"
        f'If consistently in {target_name}: {{"valid": true, "lang_detected": "{target_lang}"}}\n'
        f'If NOT: {{"valid": false, "lang_detected": "XX", "issues": ["description"]}}\n'
        f"Note: Product names (Gulp, Freelancermap, Hays, CRM) and technical terms may stay."
    )

    for attempt in range(retries):
        try:
            resp = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 200,
                },
                timeout=60,
                verify=False,
            )
            if resp.status_code != 200:
                time.sleep(2 ** attempt)
                continue
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                raw = raw.rsplit("```", 1)[0].strip()
            result = json.loads(raw)
            return (
                result.get("valid", False),
                result.get("lang_detected", "unknown"),
                result.get("issues", []),
            )
        except Exception:
            time.sleep(2 ** attempt)
    return False, "unknown", ["API-Fehler nach Retries"]


def _ref_files(i18n_dir: Path) -> list[Path]:
    ref = i18n_dir / REF_LANG / MODULE_REL
    if not ref.is_dir():
        return []
    return sorted(ref.rglob("*.json"))


def check_structure(i18n_dir: Path, target_langs: list[str]) -> dict[str, list[str]]:
    ref_files = _ref_files(i18n_dir)
    report = {lang: [] for lang in target_langs}
    for lang in target_langs:
        for ref_file in ref_files:
            rel = ref_file.relative_to(i18n_dir / REF_LANG)
            tgt = i18n_dir / lang / rel
            if not tgt.exists():
                report[lang].append(f"FEHLT: {rel}")
    return report


def check_keys(i18n_dir: Path, target_langs: list[str]) -> dict[str, list[str]]:
    ref_files = _ref_files(i18n_dir)
    report = {lang: [] for lang in target_langs}

    def _rec(ref_data, tgt_data, path=""):
        missing = []
        for k, v in ref_data.items():
            full = f"{path}.{k}" if path else k
            if k not in tgt_data:
                missing.append(full)
            elif isinstance(v, dict) and isinstance(tgt_data.get(k), dict):
                missing.extend(_rec(v, tgt_data[k], full))
        return missing

    for lang in target_langs:
        for ref_file in ref_files:
            rel = ref_file.relative_to(i18n_dir / REF_LANG)
            tgt = i18n_dir / lang / rel
            if not tgt.exists():
                continue
            try:
                ref_data = json.loads(ref_file.read_text(encoding="utf-8"))
                tgt_data = json.loads(tgt.read_text(encoding="utf-8"))
                missing = _rec(ref_data, tgt_data)
                if missing:
                    report[lang].append(
                        f"KEYS FEHLEN in {rel}: {', '.join(missing[:3])}"
                        + (f" (+{len(missing) - 3})" if len(missing) > 3 else "")
                    )
            except Exception as e:
                report[lang].append(f"LESEFEHLER: {rel} — {e}")
    return report


def check_language(
    i18n_dir: Path, target_langs: list[str], api_key: str, workers: int = 10
) -> dict[str, list[tuple[Path, str, list]]]:
    report = {lang: [] for lang in target_langs}
    tasks = []
    for lang in target_langs:
        mod = i18n_dir / lang / MODULE_REL
        if not mod.is_dir():
            continue
        for tgt_file in sorted(mod.rglob("*.json")):
            if tgt_file.name in ("meta.json", "manifest.json"):
                continue
            tasks.append((tgt_file, lang, api_key))

    log.info("  Sprach-Check: %s Dateien mit %s Workern", len(tasks), workers)

    def _worker(args):
        tgt_file, lang, key = args
        valid, detected, issues = _check_language_with_llm(tgt_file, lang, key)
        return tgt_file, lang, valid, detected, issues

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_worker, t): t for t in tasks}
        done = 0
        for future in as_completed(futures):
            tgt_file, lang, valid, detected, issues = future.result()
            done += 1
            rel = tgt_file.relative_to(i18n_dir / lang)
            if not valid:
                report[lang].append((tgt_file, str(rel), issues))
                log.warning(
                    "  ✗ [%3d/%d] %s/%s — erkannt: %s",
                    done, len(tasks), lang, rel, detected,
                )
    return report


def check_nav_titles(target_langs: list[str]) -> dict[str, list[str]]:
    report = {lang: [] for lang in target_langs}
    path = resolve_module_json()
    if not path.exists():
        for lang in target_langs:
            report[lang].append(f"FEHLT module.json: {path}")
        return report
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        for lang in target_langs:
            report[lang].append(f"LESEFEHLER module.json: {e}")
        return report

    mid = data.get("id", "shaduler")
    blocks = [(data.get("titles"), mid)]
    for sp in data.get("subpages") or []:
        blocks.append((sp.get("titles"), f"{mid}.{sp.get('id', '?')}"))

    for titles, label in blocks:
        if not isinstance(titles, dict) or REF_LANG not in titles:
            continue
        for lang in target_langs:
            if lang not in titles:
                report[lang].append(label)
    return report


def fix_nav_titles(nav_report: dict[str, list[str]]) -> list[str]:
    affected = [lang for lang, issues in nav_report.items() if issues]
    if not affected:
        return []
    translator = resolve_translator()
    fixed = []
    for lang in affected:
        log.info("  Navigation titles: %s ...", lang)
        try:
            proc = subprocess.run(
                [sys.executable, str(translator), "--modules-only", "--lang", lang],
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(BASE_DIR),
            )
            if proc.returncode == 0:
                fixed.append(lang)
            else:
                log.error("  ✗ %s: %s", lang, (proc.stderr or proc.stdout)[:200])
        except Exception as e:
            log.error("  ✗ %s: %s", lang, e)
    return fixed


def fix_issues(
    i18n_dir: Path,
    key_report: dict,
    lang_report: dict,
) -> list[str]:
    deleted = []
    translator = resolve_translator()

    for lang, issues in lang_report.items():
        for tgt_file, rel, _ in issues:
            try:
                tgt_file.unlink()
                deleted.append(f"{lang}/{rel}")
                log.info("  🗑 Gelöscht: %s/%s", lang, rel)
            except Exception as e:
                log.error("  ✗ Löschen: %s/%s — %s", lang, rel, e)

    for lang, issues in key_report.items():
        for issue in issues:
            if issue.startswith("KEYS FEHLEN in "):
                rel = issue.split("KEYS FEHLEN in ")[1].split(":")[0].strip()
                tgt_file = i18n_dir / lang / rel
                if tgt_file.exists():
                    try:
                        tgt_file.unlink()
                        deleted.append(f"{lang}/{rel}")
                        log.info("  🗑 Gelöscht (fehlende Keys): %s/%s", lang, rel)
                    except Exception as e:
                        log.error("  ✗ Löschen: %s/%s — %s", lang, rel, e)

    if not deleted:
        log.info("  Keine Dateien zu löschen.")
        return deleted

    affected = list({d.split("/")[0] for d in deleted})
    for lang in affected:
        log.info("  Übersetze: %s ...", lang)
        try:
            proc = subprocess.run(
                [sys.executable, str(translator), "--lang", lang],
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(BASE_DIR),
            )
            if proc.returncode == 0:
                log.info("  ✓ %s: Übersetzung abgeschlossen", lang)
            else:
                log.error("  ✗ %s: %s", lang, (proc.stderr or "")[:200])
        except Exception as e:
            log.error("  ✗ %s: %s", lang, e)
    return deleted


def run(args):
    print("\n╔══════════════════════════════════════════════════════╗")
    print("║  i18n_validate.py — Shaduler Modul-Sprach-Validator  ║")
    print("╚══════════════════════════════════════════════════════╝\n")

    i18n_dir = resolve_i18n_dir()
    workers = _load_workers()
    log.info("i18n-Basis: %s", i18n_dir)
    log.info("DE-Datei:   %s", shaduler_json(REF_LANG, i18n_dir))
    log.info("Workers:    %s", workers)

    all_langs = sorted(
        d.name for d in i18n_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
    )
    target_langs = [l for l in all_langs if l != REF_LANG]
    if args.lang:
        if args.lang not in all_langs and args.lang != REF_LANG:
            # erlauben wenn nur Modul fehlt
            target_langs = [args.lang]
        elif args.lang == REF_LANG:
            log.error("DE ist Referenz.")
            sys.exit(1)
        else:
            target_langs = [args.lang]

    log.info("Prüfe Sprachen: %s\n", target_langs)

    print("── Check 1: Dateistruktur (modules/shaduler) ──────────")
    struct_report = check_structure(i18n_dir, target_langs)
    struct_issues = sum(len(v) for v in struct_report.values())
    for lang, issues in struct_report.items():
        print(f"  {lang.upper()}: {'✓' if not issues else f'{len(issues)} fehlend'}")
        for i in issues[:3]:
            print(f"    • {i}")

    print("\n── Check 2: Key-Vollständigkeit ────────────────────────")
    key_report = check_keys(i18n_dir, target_langs)
    key_issues = sum(len(v) for v in key_report.values())
    for lang, issues in key_report.items():
        print(f"  {lang.upper()}: {'✓' if not issues else f'{len(issues)} Probleme'}")
        for i in issues[:3]:
            print(f"    • {i}")

    print("\n── Check 3: Sprach-Validierung (Deepseek) ──────────────")
    api_key = _load_api_key()
    lang_report = {lang: [] for lang in target_langs}
    if not api_key:
        print("  ⚠ Kein API-Key — Sprach-Check übersprungen")
    else:
        lang_report = check_language(i18n_dir, target_langs, api_key, workers)
        for lang, issues in lang_report.items():
            print(f"  {lang.upper()}: {'✓' if not issues else f'{len(issues)} fehlerhaft'}")

    print("\n── Check 4: Shaduler module.json titles ────────────────")
    nav_report = check_nav_titles(target_langs)
    nav_issues = sum(len(v) for v in nav_report.values())
    for lang, issues in nav_report.items():
        print(f"  {lang.upper()}: {'✓' if not issues else f'{len(issues)} fehlende titles'}")
        for i in issues[:5]:
            print(f"    • {i}")

    total = (
        struct_issues
        + key_issues
        + sum(len(v) for v in lang_report.values())
        + nav_issues
    )
    print(f"\n{'=' * 58}")
    print(f"  Gesamt: {total} Problem(e)")
    print(f"  Sprachdatei DE: {shaduler_json(REF_LANG, i18n_dir)}")
    print(f"  Sprachdatei EN: {shaduler_json('en', i18n_dir)}")

    if total == 0:
        print("  ✅ Alles in Ordnung!")
        print(f"{'=' * 58}\n")
        return

    if args.fix:
        print("\n── Auto-Fix ────────────────────────────────────────────")
        deleted = fix_issues(i18n_dir, key_report, lang_report)
        print(f"  {len(deleted)} Datei(en) gelöscht/neu übersetzt")
        if nav_issues > 0:
            fixed_nav = fix_nav_titles(nav_report)
            print(f"  Titles ergänzt für: {fixed_nav or '—'}")
        print("\n  python manage.py collectstatic --noinput")
        print("  supervisorctl restart abpe-django")
    else:
        print("\n  → Zum Reparieren: python3 apps/abpe_shaduler/bin/i18n_validate.py --fix")
    print(f"{'=' * 58}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Shaduler i18n Validator")
    parser.add_argument("--fix", action="store_true")
    parser.add_argument("--lang", type=str, default=None)
    run(parser.parse_args())
