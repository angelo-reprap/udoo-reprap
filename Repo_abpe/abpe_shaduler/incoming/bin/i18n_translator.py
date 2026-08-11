#!/usr/bin/env python3
"""
i18n_translator.py — Shaduler-Modul
===================================
Übersetzt nur apps/abpe_ui/.../i18n/<lang>/modules/shaduler/
(+ titles in module.json für Shaduler).

Referenz: DE. Deepseek API (settings.json → ai_models.deepseek.api_key).

Aufruf:
  python3 apps/abpe_shaduler/bin/i18n_translator.py
  python3 apps/abpe_shaduler/bin/i18n_translator.py --check
  python3 apps/abpe_shaduler/bin/i18n_translator.py --lang en
  python3 apps/abpe_shaduler/bin/i18n_translator.py --force
  python3 apps/abpe_shaduler/bin/i18n_translator.py --modules-only

Sprachdatei (Live):
  /opt/abpe/backend/apps/abpe_ui/static/abpe_ui/i18n/de/modules/shaduler/shaduler.json
  /opt/abpe/backend/apps/abpe_ui/static/abpe_ui/i18n/en/modules/shaduler/shaduler.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterator, Optional

import requests
import urllib3

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import (  # noqa: E402
    BASE_DIR,
    MODULE_REL,
    REF_LANG,
    SETTINGS,
    module_dir,
    resolve_i18n_dir,
    resolve_module_json,
    shaduler_json,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MAX_WORKERS = 10

LANG_NAMES = {
    "de": "German", "en": "English", "fr": "French", "it": "Italian",
    "es": "Spanish", "pt": "Portuguese", "nl": "Dutch", "pl": "Polish",
    "ru": "Russian", "tr": "Turkish", "ar": "Arabic", "zh": "Chinese",
    "ja": "Japanese", "ko": "Korean", "cs": "Czech", "hu": "Hungarian",
    "ro": "Romanian", "sv": "Swedish", "da": "Danish", "fi": "Finnish",
    "no": "Norwegian",
}
LANG_NATIVE = {
    "de": "Deutsch", "en": "English", "fr": "Français", "it": "Italiano",
    "es": "Español", "pt": "Português", "nl": "Nederlands", "pl": "Polski",
    "ru": "Русский", "tr": "Türkçe", "ar": "العربية", "zh": "中文",
    "ja": "日本語", "ko": "한국어", "cs": "Čeština", "hu": "Magyar",
    "ro": "Română", "sv": "Svenska", "da": "Dansk", "fi": "Suomi",
    "no": "Norsk",
}
LANG_FLAGS = {
    "de": "🇩🇪", "en": "🇬🇧", "fr": "🇫🇷", "it": "🇮🇹", "es": "🇪🇸",
    "pt": "🇵🇹", "nl": "🇳🇱", "pl": "🇵🇱", "ru": "🇷🇺", "tr": "🇹🇷",
    "ar": "🇸🇦", "zh": "🇨🇳", "ja": "🇯🇵", "ko": "🇰🇷", "cs": "🇨🇿",
    "hu": "🇭🇺", "ro": "🇷🇴", "sv": "🇸🇪", "da": "🇩🇰", "fi": "🇫🇮",
    "no": "🇳🇴",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("shaduler_i18n_translator")


def _load_api_key() -> Optional[str]:
    if SETTINGS.exists():
        cfg = json.loads(SETTINGS.read_text(encoding="utf-8"))
        return cfg.get("ai_models", {}).get("deepseek", {}).get("api_key")
    return None


def _deepseek_translate(
    content: dict | str,
    source_lang: str,
    target_lang: str,
    api_key: str,
    retries: int = 3,
) -> Optional[dict | str]:
    source_name = LANG_NAMES.get(source_lang, source_lang)
    target_name = LANG_NAMES.get(target_lang, target_lang)
    is_string = isinstance(content, str)
    payload_str = content if is_string else json.dumps(content, ensure_ascii=False)

    system_prompt = (
        f"You are a professional portal UI translator. "
        f"Translate from {source_name} to {target_name}. "
        f"Rules: "
        f"1. Preserve ALL JSON structure and keys exactly as-is. "
        f"2. Preserve ALL HTML tags, attributes, CSS classes, code blocks verbatim. "
        f"3. Translate ONLY the human-readable text content. "
        f"4. Keep technical terms, product names (Gulp, Freelancermap, Hays, CRM, Outlook), "
        f"command-line examples, URLs unchanged. "
        f"5. Reply ONLY with valid JSON, no markdown, no explanation."
    )

    if is_string:
        prompt = (
            f"Translate this {source_name} text to {target_name}. "
            f'Reply ONLY with JSON: {{"translation": "..."}}\n\n'
            f"Text: {payload_str}"
        )
    else:
        prompt = (
            f"Translate all {source_name} text values in this JSON to {target_name}. "
            f"Preserve all keys and structure exactly. "
            f"Reply ONLY with the translated JSON object.\n\n{payload_str}"
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
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 32000,
                },
                timeout=120,
                verify=False,
            )
            if resp.status_code != 200:
                log.warning("HTTP %s — Versuch %s/%s", resp.status_code, attempt + 1, retries)
                time.sleep(2 ** attempt)
                continue

            raw = resp.json()["choices"][0]["message"]["content"].strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                raw = raw.rsplit("```", 1)[0].strip()

            if is_string:
                parsed = json.loads(raw)
                return parsed.get("translation")
            return json.loads(raw)
        except json.JSONDecodeError as e:
            log.warning("JSON-Parse-Fehler Versuch %s: %s", attempt + 1, e)
            time.sleep(2 ** attempt)
        except Exception as e:
            log.warning("API-Fehler Versuch %s: %s", attempt + 1, e)
            time.sleep(2 ** attempt)
    return None


def _read_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log.error("Lesen fehlgeschlagen: %s — %s", path, e)
        return None


def _write_json(path: Path, data: dict) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )
        return True
    except Exception as e:
        log.error("Schreiben fehlgeschlagen: %s — %s", path, e)
        return False


def _collect_ref_files(ref_dir: Path) -> list[Path]:
    mod = ref_dir / MODULE_REL
    if not mod.is_dir():
        log.error("Shaduler-i18n fehlt: %s", mod)
        return []
    return sorted(mod.rglob("*.json"))


def _target_path(ref_file: Path, ref_dir: Path, target_dir: Path) -> Path:
    return target_dir / ref_file.relative_to(ref_dir)


def _check_keys(ref_data: dict, target_data: dict, path: str = "") -> list[str]:
    missing = []
    for k, v in ref_data.items():
        full_key = f"{path}.{k}" if path else k
        if k not in target_data:
            missing.append(full_key)
        elif isinstance(v, dict) and isinstance(target_data.get(k), dict):
            missing.extend(_check_keys(v, target_data[k], full_key))
    return missing


def _iter_title_blocks(data: dict, module_id: str) -> Iterator[tuple[dict, str]]:
    titles = data.get("titles")
    if isinstance(titles, dict) and titles.get(REF_LANG):
        yield titles, module_id
    for sp in data.get("subpages") or []:
        sp_titles = sp.get("titles")
        sp_id = sp.get("id", "?")
        if isinstance(sp_titles, dict) and sp_titles.get(REF_LANG):
            yield sp_titles, f"{module_id}.{sp_id}"


def discover_languages(i18n_dir: Path) -> list[str]:
    if not i18n_dir.exists():
        log.error("i18n-Verzeichnis nicht gefunden: %s", i18n_dir)
        sys.exit(1)
    return sorted(
        d.name
        for d in i18n_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )


def check_consistency(i18n_dir: Path, languages: list[str]) -> dict:
    ref_dir = i18n_dir / REF_LANG
    ref_files = _collect_ref_files(ref_dir)
    report = {}
    for lang in languages:
        if lang == REF_LANG:
            continue
        target_dir = i18n_dir / lang
        lang_issues = []
        for ref_file in ref_files:
            tgt_file = _target_path(ref_file, ref_dir, target_dir)
            rel = str(ref_file.relative_to(ref_dir))
            if not tgt_file.exists():
                lang_issues.append(f"FEHLT: {rel}")
                continue
            ref_data = _read_json(ref_file)
            tgt_data = _read_json(tgt_file)
            if ref_data is None or tgt_data is None:
                lang_issues.append(f"LESEFEHLER: {rel}")
                continue
            missing = _check_keys(ref_data, tgt_data)
            if missing:
                lang_issues.append(
                    f"KEYS FEHLEN in {rel}: {', '.join(missing[:5])}"
                    + (f" ... (+{len(missing) - 5})" if len(missing) > 5 else "")
                )
        report[lang] = lang_issues
    return report


def check_module_titles(languages: list[str]) -> dict[str, list[str]]:
    report = {lang: [] for lang in languages}
    path = resolve_module_json()
    if not path.exists():
        log.warning("module.json nicht gefunden: %s", path)
        return report
    data = _read_json(path)
    if not data:
        return report
    mid = data.get("id", "shaduler")
    for titles, label in _iter_title_blocks(data, mid):
        for lang in languages:
            if lang not in titles:
                report[lang].append(label)
    return report


def translate_module_titles(target_lang: str, api_key: str, force: bool = False) -> dict:
    results = {"ok": 0, "skip": 0, "fail": 0, "errors": []}
    path = resolve_module_json()
    if not path.exists():
        results["errors"].append(f"module.json fehlt: {path}")
        results["fail"] += 1
        return results

    data = _read_json(path)
    if not data:
        results["fail"] += 1
        results["errors"].append("module.json nicht lesbar")
        return results

    mid = data.get("id", "shaduler")
    pending: dict[str, str] = {}
    refs: dict[str, dict] = {}
    for titles, label in _iter_title_blocks(data, mid):
        if target_lang in titles and not force:
            results["skip"] += 1
            continue
        de_text = titles.get(REF_LANG, "").strip()
        if not de_text:
            continue
        pending[label] = de_text
        refs[label] = titles

    if not pending:
        return results

    log.info("  module.json [%s] shaduler: %s Titel", target_lang, len(pending))
    translated = _deepseek_translate(pending, REF_LANG, target_lang, api_key)
    if not translated or not isinstance(translated, dict):
        results["fail"] += len(pending)
        results["errors"].append("module.json: Übersetzung fehlgeschlagen")
        return results

    changed = False
    for label, text in translated.items():
        if label in refs and isinstance(text, str) and text.strip():
            refs[label][target_lang] = text.strip()
            changed = True
            results["ok"] += 1

    if changed and not _write_json(path, data):
        results["fail"] += len(pending)
        results["errors"].append("module.json: Schreibfehler")
    return results


def _translate_file(args: tuple) -> tuple[str, bool, str]:
    ref_file, tgt_file, source_lang, target_lang, api_key, force, i18n_dir = args
    rel = str(ref_file.relative_to(i18n_dir / source_lang))

    if ref_file.name == "manifest.json":
        ref_data = _read_json(ref_file)
        if ref_data and (not tgt_file.exists() or force):
            _write_json(tgt_file, ref_data)
            return rel, True, "kopiert (manifest)"
        return rel, True, "übersprungen (manifest vorhanden)"

    if tgt_file.exists() and not force:
        ref_data = _read_json(ref_file)
        tgt_data = _read_json(tgt_file)
        if ref_data and tgt_data:
            missing = _check_keys(ref_data, tgt_data)
            if not missing:
                return rel, True, "OK (vollständig)"
            log.info("  ∆ %s [%s]: %s Keys fehlen — ergänze...", rel, target_lang, len(missing))
        force = True

    ref_data = _read_json(ref_file)
    if ref_data is None:
        return rel, False, "Quelldatei nicht lesbar"

    # Merge: translate full DE, then keep existing keys unless --force wipe
    translated = _deepseek_translate(ref_data, source_lang, target_lang, api_key)
    if translated is None:
        return rel, False, "Deepseek Fehler nach Retries"
    if not isinstance(translated, dict):
        return rel, False, f"Ungültiger Rückgabetyp: {type(translated)}"

    if _write_json(tgt_file, translated):
        return rel, True, f"übersetzt ({len(json.dumps(translated))} chars)"
    return rel, False, "Schreibfehler"


def translate_language(
    i18n_dir: Path,
    target_lang: str,
    api_key: str,
    force: bool = False,
    workers: int = MAX_WORKERS,
) -> dict:
    ref_dir = i18n_dir / REF_LANG
    target_dir = i18n_dir / target_lang
    # Ziel-Modulordner anlegen
    module_dir(target_lang, i18n_dir).mkdir(parents=True, exist_ok=True)

    ref_files = _collect_ref_files(ref_dir)
    tasks = [
        (
            ref_file,
            _target_path(ref_file, ref_dir, target_dir),
            REF_LANG,
            target_lang,
            api_key,
            force,
            i18n_dir,
        )
        for ref_file in ref_files
    ]

    results = {"ok": 0, "skip": 0, "fail": 0, "errors": []}
    log.info("  %s Dateien — %s Worker (Modul %s)", len(tasks), workers, MODULE_REL)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_translate_file, t): t for t in tasks}
        done = 0
        for future in as_completed(futures):
            rel, success, msg = future.result()
            done += 1
            if success:
                if "OK" in msg or "übersprungen" in msg:
                    results["skip"] += 1
                else:
                    results["ok"] += 1
                    log.info("    ✓ [%2d/%d] %s: %s", done, len(tasks), rel, msg)
            else:
                results["fail"] += 1
                results["errors"].append(f"{rel}: {msg}")
                log.error("    ✗ [%2d/%d] %s: %s", done, len(tasks), rel, msg)
    return results


def run(args) -> None:
    print("\n╔══════════════════════════════════════════════════════╗")
    print("║  i18n_translator.py — Shaduler Modul-Sprachgenerator ║")
    print("╚══════════════════════════════════════════════════════╝\n")

    i18n_dir = resolve_i18n_dir()
    log.info("i18n-Basis: %s", i18n_dir)
    log.info("Modul:      %s", MODULE_REL)
    log.info("DE-Datei:   %s", shaduler_json(REF_LANG, i18n_dir))
    log.info("module.json:%s", resolve_module_json())

    if not (i18n_dir / REF_LANG / MODULE_REL).is_dir():
        log.error("Referenz-Modul fehlt: %s", i18n_dir / REF_LANG / MODULE_REL)
        sys.exit(1)

    all_langs = discover_languages(i18n_dir)
    log.info("Gefundene Sprachen (Portal-i18n): %s", all_langs)

    target_langs = [l for l in all_langs if l != REF_LANG]
    if args.lang:
        if args.lang == REF_LANG:
            log.error("DE ist Referenz — nicht als Ziel.")
            sys.exit(1)
        # erlauben, neue Sprache anzulegen, auch wenn Portal-Ordner noch fehlt
        if args.lang not in all_langs:
            (i18n_dir / args.lang / MODULE_REL).mkdir(parents=True, exist_ok=True)
            log.info("Sprachordner angelegt: %s", i18n_dir / args.lang)
        target_langs = [args.lang]

    if not target_langs:
        log.info("Keine Zielsprachen. Fertig.")
        return

    log.info("\n── Konsistenz-Prüfung modules/shaduler/ ───────────────")
    report = check_consistency(i18n_dir, target_langs)
    total_issues = sum(len(v) for v in report.values())
    for lang, issues in report.items():
        if issues:
            log.info("  %s: %s Problem(e)", lang.upper(), len(issues))
            for issue in issues[:5]:
                log.info("    • %s", issue)
        else:
            log.info("  %s: ✓ vollständig", lang.upper())

    log.info("\n── Konsistenz-Prüfung Shaduler module.json titles ─────")
    module_report = check_module_titles(target_langs)
    module_issues = sum(len(v) for v in module_report.values())
    total_issues += module_issues
    for lang, issues in module_report.items():
        if issues:
            log.info("  %s: %s fehlende Titel", lang.upper(), len(issues))
            for issue in issues[:5]:
                log.info("    • %s", issue)
        else:
            log.info("  %s: ✓ vollständig", lang.upper())

    if args.check:
        print(f"\nErgebnis: {total_issues} Problem(e) gefunden.")
        print(f"DE-Referenz: {shaduler_json(REF_LANG, i18n_dir)}")
        sys.exit(0 if total_issues == 0 else 1)

    if total_issues == 0 and not args.force:
        print("\n✅ Shaduler-Sprachen vollständig — nichts zu tun.")
        return

    api_key = _load_api_key()
    if not api_key:
        log.error("Kein Deepseek API-Key in settings.json!")
        sys.exit(1)
    log.info("Deepseek API-Key: sk-...%s", api_key[-8:])

    grand_ok = grand_fail = 0

    if not args.modules_only:
        for lang in target_langs:
            lang_name = LANG_NAMES.get(lang, lang.upper())
            log.info("  Starte modules/shaduler/: DE → %s (%s)", lang.upper(), lang_name)
            result = translate_language(i18n_dir, lang, api_key, force=args.force)
            grand_ok += result["ok"]
            grand_fail += result["fail"]
            print(f"\n  Ergebnis {lang.upper()}:")
            print(f"    ✓ Übersetzt:    {result['ok']}")
            print(f"    → Übersprungen: {result['skip']}")
            print(f"    ✗ Fehler:       {result['fail']}")
            for err in result["errors"]:
                print(f"      • {err}")

    if module_issues > 0 or args.force or args.modules_only:
        print("\n── Shaduler module.json titles übersetzen ─────────────")
        for lang in target_langs:
            mr = translate_module_titles(lang, api_key, force=args.force)
            grand_ok += mr["ok"]
            grand_fail += mr["fail"]
            print(f"  {lang.upper()}: ✓ {mr['ok']} Titel, ✗ {mr['fail']} Fehler")
            for err in mr["errors"]:
                print(f"    • {err}")

    print(f"\n{'=' * 58}")
    print(f"  Gesamt: {grand_ok} übersetzt, {grand_fail} Fehler")
    print(f"{'=' * 58}\n")
    if grand_ok > 0:
        print("Nächste Schritte:")
        print("  python manage.py collectstatic --noinput")
        print("  supervisorctl restart abpe-django\n")
        print(f"Sprachdatei EN: {shaduler_json('en', i18n_dir)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Shaduler i18n Übersetzer — Deepseek")
    parser.add_argument("--check", action="store_true", help="Nur Konsistenz prüfen")
    parser.add_argument("--lang", type=str, default=None, help="Nur eine Sprache")
    parser.add_argument("--force", action="store_true", help="Alles neu übersetzen")
    parser.add_argument(
        "--modules-only",
        action="store_true",
        help="Nur module.json titles (Shaduler)",
    )
    run(parser.parse_args())
