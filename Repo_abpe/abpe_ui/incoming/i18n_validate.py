#!/usr/bin/env python3
"""
i18n_validate.py
================
Vollständiger Validierungs- und Reparatur-Check für das ABpE Portal i18n-System.

Funktionen:
  1. Struktur-Check   — alle JSON-Dateien in allen Sprachen vorhanden (wie DE)
  2. Key-Check        — alle Keys in allen Sprachen identisch wie DE
  3. Sprach-Check     — Inhalt wirklich in der Zielsprache (Deepseek, parallel)
  4. Auto-Fix         — fehlerhafte JSONs löschen + i18n_translator.py aufrufen

Aufruf:
  python3 i18n_validate.py              # Alles prüfen (kein Fix)
  python3 i18n_validate.py --fix        # Prüfen + automatisch reparieren
  python3 i18n_validate.py --lang fr    # Nur eine Sprache prüfen
  python3 i18n_validate.py --lang fr --fix

Workers: settings.json → pipeline.parallel_workers_i18n
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Konfiguration ─────────────────────────────────────────────────────────────
BASE_DIR    = Path('/opt/abpe/backend')
I18N_DIR    = BASE_DIR / 'apps/abpe_ui/static/abpe_ui/i18n'
SETTINGS    = BASE_DIR / 'settings.json'
TRANSLATOR  = BASE_DIR / 'apps/abpe_ui/bin/i18n_translator.py'
REF_LANG    = 'de'

LANG_NAMES = {
    'de': 'German', 'en': 'English', 'fr': 'French', 'it': 'Italian',
    'es': 'Spanish', 'pt': 'Portuguese', 'nl': 'Dutch', 'pl': 'Polish',
    'ru': 'Russian', 'tr': 'Turkish', 'ar': 'Arabic', 'zh': 'Chinese',
    'ja': 'Japanese', 'ko': 'Korean', 'cs': 'Czech', 'hu': 'Hungarian',
    'ro': 'Romanian', 'sv': 'Swedish', 'da': 'Danish', 'fi': 'Finnish',
    'no': 'Norwegian',
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-7s  %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger('i18n_validate')


# ── Settings laden ────────────────────────────────────────────────────────────

def _load_settings() -> dict:
    if SETTINGS.exists():
        try:
            return json.loads(SETTINGS.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {}

def _load_api_key() -> Optional[str]:
    cfg = _load_settings()
    return cfg.get('ai_models', {}).get('deepseek', {}).get('api_key')

def _load_workers() -> int:
    cfg = _load_settings()
    return cfg.get('pipeline', {}).get('parallel_workers_i18n', 10)


# ── Deepseek Sprach-Check ──────────────────────────────────────────────────────

def _extract_text_values(data, results=None):
    """Alle String-Values aus JSON rekursiv extrahieren."""
    if results is None:
        results = []
    if isinstance(data, dict):
        for v in data.values():
            _extract_text_values(v, results)
    elif isinstance(data, list):
        for item in data:
            _extract_text_values(item, results)
    elif isinstance(data, str) and len(data.strip()) > 10:
        # HTML-Tags entfernen für saubereren Text-Check
        import re
        clean = re.sub(r'<[^>]+>', ' ', data).strip()
        if len(clean) > 10:
            results.append(clean[:500])  # Max 500 Zeichen pro Value
    return results


def _check_language_with_llm(file_path: Path, target_lang: str, api_key: str,
                               retries: int = 3) -> tuple[bool, str, list]:
    """
    Prüft ob der Inhalt einer JSON-Datei wirklich in der Zielsprache ist.
    Gibt zurück: (valid, detected_lang, issues)
    """
    data = None
    try:
        data = json.loads(file_path.read_text(encoding='utf-8'))
    except Exception as e:
        return False, 'unknown', [f'Lesefehler: {e}']

    texts = _extract_text_values(data)
    if not texts:
        return True, target_lang, []  # Keine Text-Values → OK

    # Alle Texte zusammenfügen für einen einzigen API-Call
    combined = '\n'.join(texts[:50])  # Max 50 Values
    target_name = LANG_NAMES.get(target_lang, target_lang.upper())

    prompt = (
        f"You are a language detection expert. "
        f"Analyze the following text content from a JSON file that should be in {target_name}.\n\n"
        f"TEXT:\n{combined}\n\n"
        f"Answer ONLY with valid JSON, no explanation:\n"
        f"If the text is consistently in {target_name}: {{\"valid\": true, \"lang_detected\": \"{target_lang}\"}}\n"
        f"If the text is NOT in {target_name} or mixed: {{\"valid\": false, \"lang_detected\": \"XX\", \"issues\": [\"description\"]}}\n"
        f"Note: Technical terms, code, URLs, proper names can be in any language."
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
                    'messages': [{'role': 'user', 'content': prompt}],
                    'temperature': 0.0,
                    'max_tokens': 200
                },
                timeout=60,
                verify=False
            )

            if resp.status_code != 200:
                time.sleep(2 ** attempt)
                continue

            raw = resp.json()['choices'][0]['message']['content'].strip()
            if raw.startswith('```'):
                raw = raw.split('\n', 1)[1] if '\n' in raw else raw[3:]
                raw = raw.rsplit('```', 1)[0].strip()

            result = json.loads(raw)
            valid = result.get('valid', False)
            detected = result.get('lang_detected', 'unknown')
            issues = result.get('issues', [])
            return valid, detected, issues

        except Exception as e:
            time.sleep(2 ** attempt)

    return False, 'unknown', ['API-Fehler nach Retries']


# ── Checks ────────────────────────────────────────────────────────────────────

def check_structure(target_langs: list[str]) -> dict[str, list[str]]:
    """Check 1: Alle Dateien vorhanden wie in DE."""
    ref_dir = I18N_DIR / REF_LANG
    ref_files = sorted(ref_dir.rglob('*.json'))
    report = {lang: [] for lang in target_langs}

    for lang in target_langs:
        tgt_dir = I18N_DIR / lang
        for ref_file in ref_files:
            rel = ref_file.relative_to(ref_dir)
            tgt_file = tgt_dir / rel
            if not tgt_file.exists():
                report[lang].append(f"FEHLT: {rel}")

    return report


def check_keys(target_langs: list[str]) -> dict[str, list[str]]:
    """Check 2: Alle Keys identisch wie in DE."""
    ref_dir = I18N_DIR / REF_LANG
    ref_files = sorted(ref_dir.rglob('*.json'))
    report = {lang: [] for lang in target_langs}

    def _check_keys_recursive(ref_data, tgt_data, path=''):
        missing = []
        for k, v in ref_data.items():
            full_key = f"{path}.{k}" if path else k
            if k not in tgt_data:
                missing.append(full_key)
            elif isinstance(v, dict) and isinstance(tgt_data.get(k), dict):
                missing.extend(_check_keys_recursive(v, tgt_data[k], full_key))
        return missing

    for lang in target_langs:
        tgt_dir = I18N_DIR / lang
        for ref_file in ref_files:
            rel = ref_file.relative_to(ref_dir)
            tgt_file = tgt_dir / rel
            if not tgt_file.exists():
                continue
            try:
                ref_data = json.loads(ref_file.read_text(encoding='utf-8'))
                tgt_data = json.loads(tgt_file.read_text(encoding='utf-8'))
                missing = _check_keys_recursive(ref_data, tgt_data)
                if missing:
                    report[lang].append(
                        f"KEYS FEHLEN in {rel}: {', '.join(missing[:3])}"
                        + (f" (+{len(missing)-3})" if len(missing) > 3 else "")
                    )
            except Exception as e:
                report[lang].append(f"LESEFEHLER: {rel} — {e}")

    return report


def check_language(target_langs: list[str], api_key: str,
                   workers: int = 10) -> dict[str, list[tuple[Path, str, list]]]:
    """Check 3: Inhalt wirklich in Zielsprache (Deepseek, parallel)."""
    report = {lang: [] for lang in target_langs}

    # Alle zu prüfenden Dateien sammeln
    tasks = []
    for lang in target_langs:
        tgt_dir = I18N_DIR / lang
        for tgt_file in sorted(tgt_dir.rglob('*.json')):
            # meta.json und manifest.json überspringen
            if tgt_file.name in ('meta.json', 'manifest.json'):
                continue
            tasks.append((tgt_file, lang, api_key))

    log.info(f"  Sprach-Check: {len(tasks)} Dateien mit {workers} Workern")

    def _worker(args):
        tgt_file, lang, api_key = args
        valid, detected, issues = _check_language_with_llm(tgt_file, lang, api_key)
        return tgt_file, lang, valid, detected, issues

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_worker, t): t for t in tasks}
        done = 0
        for future in as_completed(futures):
            tgt_file, lang, valid, detected, issues = future.result()
            done += 1
            rel = tgt_file.relative_to(I18N_DIR / lang)
            if not valid:
                report[lang].append((tgt_file, str(rel), issues))
                log.warning(f"  ✗ [{done:3d}/{len(tasks)}] {lang}/{rel} — erkannt: {detected}")
            else:
                log.debug(f"  ✓ [{done:3d}/{len(tasks)}] {lang}/{rel}")

    return report


# ── Fix ───────────────────────────────────────────────────────────────────────

def fix_issues(struct_report: dict, key_report: dict,
               lang_report: dict, target_langs: list[str]) -> list[str]:
    """
    Löscht fehlerhafte/unvollständige JSONs und ruft i18n_translator.py auf.
    Gibt Liste der gelöschten Dateien zurück.
    """
    deleted = []

    # Dateien mit falscher Sprache löschen
    for lang, issues in lang_report.items():
        for tgt_file, rel, _ in issues:
            try:
                tgt_file.unlink()
                deleted.append(f"{lang}/{rel}")
                log.info(f"  🗑 Gelöscht: {lang}/{rel}")
            except Exception as e:
                log.error(f"  ✗ Löschen fehlgeschlagen: {lang}/{rel} — {e}")

    # Dateien mit fehlenden Keys löschen (werden neu übersetzt)
    ref_dir = I18N_DIR / REF_LANG
    for lang, issues in key_report.items():
        for issue in issues:
            if issue.startswith('KEYS FEHLEN in '):
                rel = issue.split('KEYS FEHLEN in ')[1].split(':')[0].strip()
                tgt_file = I18N_DIR / lang / rel
                if tgt_file.exists():
                    try:
                        tgt_file.unlink()
                        deleted.append(f"{lang}/{rel}")
                        log.info(f"  🗑 Gelöscht (fehlende Keys): {lang}/{rel}")
                    except Exception as e:
                        log.error(f"  ✗ Löschen fehlgeschlagen: {lang}/{rel} — {e}")

    if not deleted:
        log.info("  Keine Dateien zu löschen.")
        return deleted

    # i18n_translator.py aufrufen für betroffene Sprachen
    affected_langs = list(set(d.split('/')[0] for d in deleted))
    log.info(f"\n  Starte i18n_translator.py für: {affected_langs}")

    for lang in affected_langs:
        log.info(f"  Übersetze: {lang} ...")
        try:
            proc = subprocess.run(
                [sys.executable, str(TRANSLATOR), '--lang', lang],
                capture_output=True, text=True, timeout=600,
                cwd=str(BASE_DIR)
            )
            if proc.returncode == 0:
                log.info(f"  ✓ {lang}: Übersetzung abgeschlossen")
            else:
                log.error(f"  ✗ {lang}: {proc.stderr[:200]}")
        except Exception as e:
            log.error(f"  ✗ {lang}: {e}")

    return deleted


# ── Hauptlogik ────────────────────────────────────────────────────────────────

def run(args):
    print("\n╔══════════════════════════════════════════════════════╗")
    print("║   i18n_validate.py — ABpE Portal Sprach-Validator    ║")
    print("╚══════════════════════════════════════════════════════╝\n")

    workers = _load_workers()
    log.info(f"Workers (aus settings.json): {workers}")

    # Sprachen ermitteln
    all_langs = sorted([
        d.name for d in I18N_DIR.iterdir()
        if d.is_dir() and not d.name.startswith('.')
    ])
    target_langs = [l for l in all_langs if l != REF_LANG]

    if args.lang:
        if args.lang not in all_langs:
            log.error(f"Sprache '{args.lang}' nicht gefunden. Verfügbar: {all_langs}")
            sys.exit(1)
        target_langs = [args.lang]

    log.info(f"Prüfe Sprachen: {target_langs}\n")

    # ── Check 1: Struktur ─────────────────────────────────────────────────
    print("── Check 1: Dateistruktur ──────────────────────────────")
    struct_report = check_structure(target_langs)
    struct_issues = sum(len(v) for v in struct_report.values())
    for lang, issues in struct_report.items():
        if issues:
            print(f"  {lang.upper()}: {len(issues)} fehlende Dateien")
            for i in issues[:3]:
                print(f"    • {i}")
            if len(issues) > 3:
                print(f"    ... (+{len(issues)-3} weitere)")
        else:
            print(f"  {lang.upper()}: ✓ vollständig")

    # ── Check 2: Keys ─────────────────────────────────────────────────────
    print("\n── Check 2: Key-Vollständigkeit ────────────────────────")
    key_report = check_keys(target_langs)
    key_issues = sum(len(v) for v in key_report.values())
    for lang, issues in key_report.items():
        if issues:
            print(f"  {lang.upper()}: {len(issues)} Probleme")
            for i in issues[:3]:
                print(f"    • {i}")
            if len(issues) > 3:
                print(f"    ... (+{len(issues)-3} weitere)")
        else:
            print(f"  {lang.upper()}: ✓ alle Keys vorhanden")

    # ── Check 3: Sprach-Check ─────────────────────────────────────────────
    print("\n── Check 3: Sprach-Validierung (Deepseek) ──────────────")
    api_key = _load_api_key()
    lang_report = {lang: [] for lang in target_langs}

    if not api_key:
        print("  ⚠ Kein API-Key — Sprach-Check übersprungen")
    else:
        lang_report = check_language(target_langs, api_key, workers)
        lang_issues = sum(len(v) for v in lang_report.values())
        for lang, issues in lang_report.items():
            if issues:
                print(f"  {lang.upper()}: {len(issues)} fehlerhafte Dateien")
                for _, rel, errs in issues[:3]:
                    print(f"    • {rel}: {', '.join(errs[:2])}")
            else:
                print(f"  {lang.upper()}: ✓ Sprache korrekt")

    # ── Zusammenfassung ───────────────────────────────────────────────────
    total = struct_issues + key_issues + sum(len(v) for v in lang_report.values())
    print(f"\n{'='*58}")
    print(f"  Gesamt: {total} Problem(e) gefunden")
    print(f"  Struktur: {struct_issues} | Keys: {key_issues} | Sprache: {sum(len(v) for v in lang_report.values())}")

    if total == 0:
        print("  ✅ Alles in Ordnung!")
        print(f"{'='*58}\n")
        return

    # ── Fix ───────────────────────────────────────────────────────────────
    if args.fix:
        print(f"\n── Auto-Fix ────────────────────────────────────────────")
        deleted = fix_issues(struct_report, key_report, lang_report, target_langs)
        print(f"  {len(deleted)} Datei(en) gelöscht und neu übersetzt")
        print("\nNächste Schritte:")
        print("  python manage.py collectstatic --noinput")
        print("  supervisorctl restart abpe-django")
    else:
        print(f"\n  → Zum Reparieren: python3 i18n_validate.py --fix")

    print(f"{'='*58}\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='ABpE Portal i18n Validator — Struktur + Keys + Sprache'
    )
    parser.add_argument('--fix',  action='store_true',
                        help='Fehlerhafte Dateien löschen + neu übersetzen')
    parser.add_argument('--lang', type=str, default=None,
                        help='Nur eine Sprache prüfen (z.B. --lang fr)')
    args = parser.parse_args()
    run(args)
