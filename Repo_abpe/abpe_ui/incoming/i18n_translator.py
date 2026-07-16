#!/usr/bin/env python3
"""
i18n_translator.py
==================
Automatischer Sprachübersetzer für das ABpE Portal i18n-System.

Funktionen:
  - Erkennt alle Sprachverzeichnisse unter i18n/ automatisch
  - Verwendet DE als Referenzsprache
  - Übersetzt alle fehlenden / veralteten JSON-Dateien via Deepseek API
  - Übersetzt module.json titles (Sidebar-Navigation) aus titles.de
  - Prüft Konsistenz: alle Sprachen müssen alle Keys haben
  - 10 parallele Worker (kleine Dateien = kein Token-Problem)
  - Neue Sprache anlegen: mkdir i18n/hu/ → Programm erkennt und übersetzt alles

Aufruf:
  python3 i18n_translator.py              # Alle Sprachen prüfen + übersetzen
  python3 i18n_translator.py --check      # Nur Konsistenz prüfen, nicht übersetzen
  python3 i18n_translator.py --lang it    # Nur eine Sprache übersetzen
  python3 i18n_translator.py --force      # Alle Dateien neu übersetzen (auch vorhandene)
  python3 i18n_translator.py --modules-only   # Nur module.json titles

Pfade:
  Basis:    /opt/abpe/backend/apps/abpe_ui/static/abpe_ui/i18n/
  Referenz: de/
  Module:   /opt/abpe/backend/apps/abpe_ui/templates/abpe_ui/modules/*/module.json
"""

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

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Konfiguration ─────────────────────────────────────────────────────────────
BASE_DIR    = Path("/opt/abpe/backend")
I18N_DIR    = BASE_DIR / 'apps/abpe_ui/static/abpe_ui/i18n'
MODULES_DIR = BASE_DIR / 'apps/abpe_ui/templates/abpe_ui/modules'
SETTINGS    = BASE_DIR / 'settings.json'
REF_LANG    = 'de'
MAX_WORKERS = 10

LANG_NAMES = {
    'de': 'German', 'en': 'English', 'fr': 'French', 'it': 'Italian',
    'es': 'Spanish', 'pt': 'Portuguese', 'nl': 'Dutch', 'pl': 'Polish',
    'ru': 'Russian', 'tr': 'Turkish', 'ar': 'Arabic', 'zh': 'Chinese',
    'ja': 'Japanese', 'ko': 'Korean', 'cs': 'Czech', 'hu': 'Hungarian',
    'ro': 'Romanian', 'sv': 'Swedish', 'da': 'Danish', 'fi': 'Finnish',
    'no': 'Norwegian',
}

LANG_NATIVE = {
    'de': 'Deutsch', 'en': 'English', 'fr': 'Français', 'it': 'Italiano',
    'es': 'Español', 'pt': 'Português', 'nl': 'Nederlands', 'pl': 'Polski',
    'ru': 'Русский', 'tr': 'Türkçe', 'ar': 'العربية', 'zh': '中文',
    'ja': '日本語', 'ko': '한국어', 'cs': 'Čeština', 'hu': 'Magyar',
    'ro': 'Română', 'sv': 'Svenska', 'da': 'Dansk', 'fi': 'Suomi',
    'no': 'Norsk',
}

LANG_FLAGS = {
    'de': '🇩🇪', 'en': '🇬🇧', 'fr': '🇫🇷', 'it': '🇮🇹', 'es': '🇪🇸',
    'pt': '🇵🇹', 'nl': '🇳🇱', 'pl': '🇵🇱', 'ru': '🇷🇺', 'tr': '🇹🇷',
    'ar': '🇸🇦', 'zh': '🇨🇳', 'ja': '🇯🇵', 'ko': '🇰🇷', 'cs': '🇨🇿',
    'hu': '🇭🇺', 'ro': '🇷🇴', 'sv': '🇸🇪', 'da': '🇩🇰', 'fi': '🇫🇮',
    'no': '🇳🇴',
}
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-7s  %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger('i18n_translator')


# ── Deepseek API ──────────────────────────────────────────────────────────────

def _load_api_key() -> Optional[str]:
    if SETTINGS.exists():
        cfg = json.loads(SETTINGS.read_text())
        return cfg.get('ai_models', {}).get('deepseek', {}).get('api_key')
    return None


def _deepseek_translate(content: dict | str, source_lang: str, target_lang: str,
                         api_key: str, retries: int = 3) -> Optional[dict | str]:
    source_name = LANG_NAMES.get(source_lang, source_lang)
    target_name = LANG_NAMES.get(target_lang, target_lang)

    is_string = isinstance(content, str)
    payload_str = content if is_string else json.dumps(content, ensure_ascii=False)

    system_prompt = (
        f"You are a professional portal UI translator. "
        f"Translate from {source_name} to {target_name}. "
        f"Rules: "
        f"1. Preserve ALL JSON structure and keys exactly as-is. "
        f"2. Preserve ALL HTML tags, attributes, CSS classes, code blocks, <pre>, <code> verbatim. "
        f"3. Translate ONLY the human-readable text content between tags and in JSON string values. "
        f"4. Keep technical terms, product names, command-line examples, URLs unchanged. "
        f"5. Reply ONLY with valid JSON, no markdown, no explanation."
    )

    if is_string:
        prompt = (
            f"Translate this {source_name} text to {target_name}. "
            f"Reply ONLY with JSON: {{\"translation\": \"...\"}}\n\n"
            f"Text: {payload_str}"
        )
    else:
        prompt = (
            f"Translate all {source_name} text values in this JSON to {target_name}. "
            f"Preserve all keys, HTML tags, code blocks, and structure exactly. "
            f"Reply ONLY with the translated JSON object, nothing else.\n\n"
            f"{payload_str}"
        )

    for attempt in range(retries):
        try:
            resp = requests.post(
                'https://api.deepseek.com/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'deepseek-chat',
                    'messages': [
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user',   'content': prompt}
                    ],
                    'temperature': 0.1,
                    'max_tokens': 32000
                },
                timeout=120,
                verify=False
            )

            if resp.status_code != 200:
                log.warning(f"HTTP {resp.status_code} — Versuch {attempt+1}/{retries}")
                time.sleep(2 ** attempt)
                continue

            raw = resp.json()['choices'][0]['message']['content'].strip()

            if raw.startswith('```'):
                raw = raw.split('\n', 1)[1] if '\n' in raw else raw[3:]
                raw = raw.rsplit('```', 1)[0].strip()

            if is_string:
                parsed = json.loads(raw)
                return parsed.get('translation', None)
            return json.loads(raw)

        except json.JSONDecodeError as e:
            log.warning(f"JSON-Parse-Fehler Versuch {attempt+1}: {e}")
            time.sleep(2 ** attempt)
        except Exception as e:
            log.warning(f"API-Fehler Versuch {attempt+1}: {e}")
            time.sleep(2 ** attempt)

    return None


# ── Datei-Operationen ─────────────────────────────────────────────────────────

def _read_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as e:
        log.error(f"Lesen fehlgeschlagen: {path} — {e}")
        return None


def _write_json(path: Path, data: dict) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=4) + '\n', encoding='utf-8')
        return True
    except Exception as e:
        log.error(f"Schreiben fehlgeschlagen: {path} — {e}")
        return False


def _collect_ref_files(ref_dir: Path) -> list[Path]:
    return sorted(ref_dir.rglob('*.json'))


def _target_path(ref_file: Path, ref_dir: Path, target_dir: Path) -> Path:
    return target_dir / ref_file.relative_to(ref_dir)


# ── module.json titles (Sidebar) ──────────────────────────────────────────────

def _iter_title_blocks(data: dict, module_id: str) -> Iterator[tuple[dict, str]]:
    """Alle titles-Blöcke (Modul + Subpages) mit DE-Referenztext."""
    titles = data.get('titles')
    if isinstance(titles, dict) and titles.get(REF_LANG):
        yield titles, module_id
    for sp in data.get('subpages') or []:
        sp_titles = sp.get('titles')
        sp_id = sp.get('id', '?')
        if isinstance(sp_titles, dict) and sp_titles.get(REF_LANG):
            yield sp_titles, f"{module_id}.{sp_id}"


def check_module_titles(languages: list[str]) -> dict[str, list[str]]:
    """Prüft fehlende titles.<lang> in allen module.json."""
    report = {lang: [] for lang in languages}
    if not MODULES_DIR.exists():
        log.warning(f"module.json Verzeichnis nicht gefunden: {MODULES_DIR}")
        return report

    for mod_dir in sorted(MODULES_DIR.iterdir()):
        if not mod_dir.is_dir():
            continue
        path = mod_dir / 'module.json'
        if not path.exists():
            continue
        data = _read_json(path)
        if not data:
            continue
        mid = data.get('id', mod_dir.name)
        for titles, label in _iter_title_blocks(data, mid):
            for lang in languages:
                if lang not in titles:
                    report[lang].append(label)

    return report


def translate_module_titles(target_lang: str, api_key: str, force: bool = False) -> dict:
    """Übersetzt fehlende titles.<lang> in module.json aus titles.de."""
    results = {'ok': 0, 'skip': 0, 'fail': 0, 'errors': []}
    if not MODULES_DIR.exists():
        return results

    for mod_dir in sorted(MODULES_DIR.iterdir()):
        if not mod_dir.is_dir():
            continue
        path = mod_dir / 'module.json'
        if not path.exists():
            continue
        data = _read_json(path)
        if not data:
            continue
        mid = data.get('id', mod_dir.name)

        pending: dict[str, str] = {}
        refs: dict[str, dict] = {}
        for titles, label in _iter_title_blocks(data, mid):
            if target_lang in titles and not force:
                results['skip'] += 1
                continue
            de_text = titles.get(REF_LANG, '').strip()
            if not de_text:
                continue
            pending[label] = de_text
            refs[label] = titles

        if not pending:
            continue

        log.info(f"  module.json [{target_lang}] {mid}: {len(pending)} Titel")
        translated = _deepseek_translate(pending, REF_LANG, target_lang, api_key)
        if not translated or not isinstance(translated, dict):
            results['fail'] += len(pending)
            results['errors'].append(f"{mid}: Übersetzung fehlgeschlagen")
            continue

        changed = False
        for label, text in translated.items():
            if label in refs and isinstance(text, str) and text.strip():
                refs[label][target_lang] = text.strip()
                changed = True
                results['ok'] += 1

        if changed and not _write_json(path, data):
            results['fail'] += len(pending)
            results['errors'].append(f"{mid}: Schreibfehler")

    return results


# ── Konsistenz-Prüfung i18n/ ─────────────────────────────────────────────────

def _check_keys(ref_data: dict, target_data: dict, path: str = '') -> list[str]:
    missing = []
    for k, v in ref_data.items():
        full_key = f"{path}.{k}" if path else k
        if k not in target_data:
            missing.append(full_key)
        elif isinstance(v, dict) and isinstance(target_data.get(k), dict):
            missing.extend(_check_keys(v, target_data[k], full_key))
    return missing


def check_consistency(languages: list[str]) -> dict:
    ref_dir   = I18N_DIR / REF_LANG
    ref_files = _collect_ref_files(ref_dir)
    report    = {}

    for lang in languages:
        if lang == REF_LANG:
            continue
        target_dir = I18N_DIR / lang
        lang_issues = []

        for ref_file in ref_files:
            tgt_file = _target_path(ref_file, ref_dir, target_dir)
            rel      = str(ref_file.relative_to(ref_dir))

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
                    + (f" ... (+{len(missing)-5})" if len(missing) > 5 else "")
                )

        report[lang] = lang_issues

    return report


# ── Übersetzungs-Worker i18n/ ────────────────────────────────────────────────

def _translate_file(args: tuple) -> tuple[str, bool, str]:
    ref_file, tgt_file, source_lang, target_lang, api_key, force = args
    rel = str(ref_file.relative_to(I18N_DIR / source_lang))

    if ref_file.name == 'manifest.json':
        ref_data = _read_json(ref_file)
        if ref_data and (not tgt_file.exists() or force):
            _write_json(tgt_file, ref_data)
            return rel, True, 'kopiert (manifest)'
        return rel, True, 'übersprungen (manifest vorhanden)'

    if ref_file.name == "meta.json":
        if tgt_file.exists() and not force:
            return rel, True, 'OK (meta.json vorhanden)'

        meta = {
            'code':         target_lang,
            'name':         LANG_NAMES.get(target_lang, target_lang),
            'native':       LANG_NATIVE.get(target_lang, LANG_NAMES.get(target_lang, target_lang)),
            'flag':         LANG_FLAGS.get(target_lang, '🏳️'),
            'enabled':      True,
            'completeness': 0,
        }
        _write_json(tgt_file, meta)
        return rel, True, 'meta.json angelegt'

    if tgt_file.exists() and not force:
        ref_data = _read_json(ref_file)
        tgt_data = _read_json(tgt_file)
        if ref_data and tgt_data:
            missing = _check_keys(ref_data, tgt_data)
            if not missing:
                return rel, True, 'OK (vollständig)'
            log.info(f"  ∆ {rel} [{target_lang}]: {len(missing)} Keys fehlen — ergänze...")
        force = True

    ref_data = _read_json(ref_file)
    if ref_data is None:
        return rel, False, 'Quelldatei nicht lesbar'

    translated = _deepseek_translate(ref_data, source_lang, target_lang, api_key)
    if translated is None:
        return rel, False, 'Deepseek Fehler nach Retries'

    if not isinstance(translated, dict):
        return rel, False, f'Ungültiger Rückgabetyp: {type(translated)}'

    if _write_json(tgt_file, translated):
        return rel, True, f'übersetzt ({len(json.dumps(translated))} chars)'
    return rel, False, 'Schreibfehler'


def discover_languages() -> list[str]:
    if not I18N_DIR.exists():
        log.error(f"i18n-Verzeichnis nicht gefunden: {I18N_DIR}")
        sys.exit(1)
    return sorted([
        d.name for d in I18N_DIR.iterdir()
        if d.is_dir() and not d.name.startswith('.')
    ])


def translate_language(target_lang: str, api_key: str, force: bool = False,
                        workers: int = MAX_WORKERS) -> dict:
    ref_dir    = I18N_DIR / REF_LANG
    target_dir = I18N_DIR / target_lang
    ref_files  = _collect_ref_files(ref_dir)

    tasks = [
        (ref_file, _target_path(ref_file, ref_dir, target_dir), REF_LANG, target_lang, api_key, force)
        for ref_file in ref_files
    ]

    results = {'ok': 0, 'skip': 0, 'fail': 0, 'errors': []}
    log.info(f"  {len(tasks)} Dateien — {workers} Worker")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_translate_file, t): t for t in tasks}
        done = 0
        for future in as_completed(futures):
            rel, success, msg = future.result()
            done += 1
            if success:
                if 'OK' in msg or 'übersprungen' in msg:
                    results['skip'] += 1
                else:
                    results['ok'] += 1
                    log.info(f"    ✓ [{done:2d}/{len(tasks)}] {rel}: {msg}")
            else:
                results['fail'] += 1
                results['errors'].append(f"{rel}: {msg}")
                log.error(f"    ✗ [{done:2d}/{len(tasks)}] {rel}: {msg}")

    return results


# ── Hauptlogik ────────────────────────────────────────────────────────────────

def run(args) -> None:
    print("\n╔══════════════════════════════════════════════════════╗")
    print("║   i18n_translator.py — ABpE Portal Sprachgenerator   ║")
    print("╚══════════════════════════════════════════════════════╝\n")

    all_langs = discover_languages()
    log.info(f"Gefundene Sprachen: {all_langs}")

    target_langs = [l for l in all_langs if l != REF_LANG]
    if args.lang:
        if args.lang not in all_langs:
            log.error(f"Sprache '{args.lang}' nicht gefunden. Verfügbar: {all_langs}")
            sys.exit(1)
        target_langs = [args.lang]

    if not target_langs:
        log.info("Keine Zielsprachen gefunden (nur DE vorhanden). Fertig.")
        return

    # ── Konsistenz i18n/ ──────────────────────────────────────────────────
    log.info("\n── Konsistenz-Prüfung i18n/ ───────────────────────────")
    report = check_consistency(target_langs)
    total_issues = sum(len(v) for v in report.values())

    for lang, issues in report.items():
        if issues:
            log.info(f"  {lang.upper()}: {len(issues)} Problem(e)")
            for issue in issues[:5]:
                log.info(f"    • {issue}")
            if len(issues) > 5:
                log.info(f"    ... (+{len(issues)-5} weitere)")
        else:
            log.info(f"  {lang.upper()}: ✓ vollständig")

    # ── Konsistenz module.json titles ─────────────────────────────────────
    log.info("\n── Konsistenz-Prüfung module.json titles ───────────────")
    module_report = check_module_titles(target_langs)
    module_issues = sum(len(v) for v in module_report.values())
    total_issues += module_issues

    for lang, issues in module_report.items():
        if issues:
            log.info(f"  {lang.upper()}: {len(issues)} fehlende Titel")
            for issue in issues[:5]:
                log.info(f"    • {issue}")
            if len(issues) > 5:
                log.info(f"    ... (+{len(issues)-5} weitere)")
        else:
            log.info(f"  {lang.upper()}: ✓ vollständig")

    if args.check:
        print(f"\nErgebnis: {total_issues} Problem(e) gefunden.")
        sys.exit(0 if total_issues == 0 else 1)

    if total_issues == 0 and not args.force:
        print("\n✅ Alle Sprachen vollständig — nichts zu tun.")
        return

    api_key = _load_api_key()
    if not api_key:
        log.error("Kein Deepseek API-Key in settings.json gefunden!")
        sys.exit(1)
    log.info(f"Deepseek API-Key: sk-...{api_key[-8:]}")

    grand_ok = grand_fail = 0
    lang_results = {}

    if not args.modules_only:
        def _translate_lang(lang):
            lang_name = LANG_NAMES.get(lang, lang.upper())
            log.info(f"  Starte i18n/: DE → {lang.upper()} ({lang_name})")
            return lang, translate_language(lang, api_key, force=args.force)

        with ThreadPoolExecutor(max_workers=len(target_langs)) as executor:
            futures = {executor.submit(_translate_lang, lang): lang for lang in target_langs}
            for future in as_completed(futures):
                lang, result = future.result()
                lang_results[lang] = result

        for lang in sorted(lang_results):
            result = lang_results[lang]
            grand_ok   += result['ok']
            grand_fail += result['fail']
            print(f"\n  Ergebnis i18n/ {lang.upper()}:")
            print(f"    ✓ Übersetzt:    {result['ok']}")
            print(f"    → Übersprungen: {result['skip']}")
            print(f"    ✗ Fehler:       {result['fail']}")
            if result['errors']:
                for err in result['errors']:
                    print(f"      • {err}")

    # ── module.json titles ────────────────────────────────────────────────
    if module_issues > 0 or args.force or args.modules_only:
        print("\n── module.json titles übersetzen ───────────────────────")
        mod_ok = mod_fail = 0
        for lang in target_langs:
            log.info(f"  Starte module.json: DE → {lang.upper()}")
            mr = translate_module_titles(lang, api_key, force=args.force)
            mod_ok   += mr['ok']
            mod_fail += mr['fail']
            print(f"  {lang.upper()}: ✓ {mr['ok']} Titel, ✗ {mr['fail']} Fehler")
            for err in mr['errors']:
                print(f"    • {err}")
        grand_ok   += mod_ok
        grand_fail += mod_fail

    print(f"\n{'='*58}")
    print(f"  Gesamt: {grand_ok} übersetzt, {grand_fail} Fehler")
    if grand_fail == 0:
        print("  ✅ Alle Übersetzungen erfolgreich!")
    else:
        print("  ⚠  Einige Dateien konnten nicht übersetzt werden.")
    print(f"{'='*58}\n")

    if grand_ok > 0:
        print("Nächste Schritte:")
        print("  python manage.py collectstatic --noinput")
        print("  supervisorctl restart abpe-django\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='ABpE Portal i18n Übersetzer — Deepseek API'
    )
    parser.add_argument('--check', action='store_true',
                        help='Nur Konsistenz prüfen, nicht übersetzen')
    parser.add_argument('--lang', type=str, default=None,
                        help='Nur eine bestimmte Sprache (z.B. --lang hu)')
    parser.add_argument('--force', action='store_true',
                        help='Alle Dateien neu übersetzen')
    parser.add_argument('--modules-only', action='store_true',
                        help='Nur module.json titles übersetzen')
    args = parser.parse_args()
    run(args)
