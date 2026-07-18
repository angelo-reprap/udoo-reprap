#!/usr/bin/env python3
"""
i18n_translator.py
==================
Automatischer Sprachübersetzer für das ABpE Portal i18n-System.

Funktionen:
  - Erkennt alle Sprachverzeichnisse unter i18n/ automatisch
  - Verwendet DE als Referenzsprache
  - Übersetzt alle fehlenden / veralteten JSON-Dateien via Deepseek API
  - Prüft Konsistenz: alle Sprachen müssen alle Keys haben
  - 10 parallele Worker (kleine Dateien = kein Token-Problem)
  - Neue Sprache anlegen: mkdir i18n/it/ → Programm erkennt und übersetzt alles

Aufruf:
  python3 i18n_translator.py              # Alle Sprachen prüfen + übersetzen
  python3 i18n_translator.py --check      # Nur Konsistenz prüfen, nicht übersetzen
  python3 i18n_translator.py --lang it    # Nur eine Sprache übersetzen
  python3 i18n_translator.py --force      # Alle Dateien neu übersetzen (auch vorhandene)

Pfade:
  Basis: /opt/abpe/backend/apps/abpe_ui/static/abpe_ui/i18n/
  Referenz: de/
  Ziel:     en/, fr/, it/, ... (alle anderen Verzeichnisse)
"""

import argparse
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Konfiguration ─────────────────────────────────────────────────────────────
BASE_DIR   = Path("/opt/abpe/backend")
I18N_DIR   = BASE_DIR / 'apps/abpe_ui/static/abpe_ui/i18n'
SETTINGS   = BASE_DIR / 'settings.json'
REF_LANG   = 'de'
MAX_WORKERS = 10

# Sprach-Namen für den Prompt (ISO-Code → Name)
LANG_NAMES = {
    'de': 'German',
    'en': 'English',
    'fr': 'French',
    'it': 'Italian',
    'es': 'Spanish',
    'pt': 'Portuguese',
    'nl': 'Dutch',
    'pl': 'Polish',
    'ru': 'Russian',
    'tr': 'Turkish',
    'ar': 'Arabic',
    'zh': 'Chinese',
    'ja': 'Japanese',
    'ko': 'Korean',
    'cs': 'Czech',
    'hu': 'Hungarian',
    'ro': 'Romanian',
    'sv': 'Swedish',
    'da': 'Danish',
    'fi': 'Finnish',
    'no': 'Norwegian',
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
    """
    Sendet JSON-Inhalt an Deepseek und gibt die übersetzte Version zurück.
    Behält Struktur, Keys, HTML-Tags, CSS, Code-Blöcke exakt bei.
    Gibt None zurück bei Fehler.
    """
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

            # Markdown-Fences entfernen
            if raw.startswith('```'):
                raw = raw.split('\n', 1)[1] if '\n' in raw else raw[3:]
                raw = raw.rsplit('```', 1)[0].strip()

            if is_string:
                parsed = json.loads(raw)
                return parsed.get('translation', None)
            else:
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
        path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding='utf-8')
        return True
    except Exception as e:
        log.error(f"Schreiben fehlgeschlagen: {path} — {e}")
        return False


def _collect_ref_files(ref_dir: Path) -> list[Path]:
    """Alle JSON-Dateien im Referenz-Verzeichnis (rekursiv), sortiert."""
    return sorted(ref_dir.rglob('*.json'))


def _target_path(ref_file: Path, ref_dir: Path, target_dir: Path) -> Path:
    """Berechnet den Zielpfad einer Datei."""
    rel = ref_file.relative_to(ref_dir)
    return target_dir / rel


# ── Konsistenz-Prüfung ────────────────────────────────────────────────────────

def _check_keys(ref_data: dict, target_data: dict, path: str = '') -> list[str]:
    """Gibt fehlende Keys zurück (rekursiv)."""
    missing = []
    for k, v in ref_data.items():
        full_key = f"{path}.{k}" if path else k
        if k not in target_data:
            missing.append(full_key)
        elif isinstance(v, dict) and isinstance(target_data.get(k), dict):
            missing.extend(_check_keys(v, target_data[k], full_key))
    return missing


def check_consistency(languages: list[str]) -> dict:
    """Prüft alle Sprachen auf Vollständigkeit. Gibt Report zurück."""
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
                lang_issues.append(f"KEYS FEHLEN in {rel}: {', '.join(missing[:5])}"
                                   + (f" ... (+{len(missing)-5})" if len(missing) > 5 else ""))

        report[lang] = lang_issues

    return report


# ── Übersetzungs-Worker ───────────────────────────────────────────────────────

def _translate_file(args: tuple) -> tuple[str, bool, str]:
    """
    Worker-Funktion für ThreadPoolExecutor.
    args: (ref_file, tgt_file, source_lang, target_lang, api_key, force)
    Gibt zurück: (rel_path, success, message)
    """
    ref_file, tgt_file, source_lang, target_lang, api_key, force = args
    rel = str(ref_file.relative_to(I18N_DIR / source_lang))

    # manifest.json wird nicht übersetzt — 1:1 kopiert
    if ref_file.name == 'manifest.json':
        ref_data = _read_json(ref_file)
        if ref_data and (not tgt_file.exists() or force):
            _write_json(tgt_file, ref_data)
            return rel, True, 'kopiert (manifest)'
        return rel, True, 'übersprungen (manifest vorhanden)'

    # meta.json: unterscheiden ob Root-Sprachdatei oder Unterverzeichnis
    if ref_file.name == "meta.json":
        ref_data = _read_json(ref_file)
        if not ref_data:
            return rel, False, 'meta.json Lesefehler'

        # Root meta.json (z.B. de/meta.json) → Sprachdaten anpassen
        if ref_file.parent.name not in ('de', 'en', 'fr', 'it', 'es', 'pt', 'nl', 'pl', 'ru', 'tr', 'zh', 'ja', 'ko', 'ar', 'cs', 'hu', 'ro', 'sv', 'da', 'fi', 'no', 'uk', 'vi', 'bg', 'hr', 'sk', 'sl', 'sq', 'sr', 'lt', 'lv', 'et', 'el', 'af'):
            # Unterverzeichnis meta.json → Inhalte übersetzen (toc + sections)
            if tgt_file.exists() and not force:
                return rel, True, 'OK (vollständig)'
            translated = _deepseek_translate(ref_data, source_lang, target_lang, api_key)
            if translated and isinstance(translated, dict):
                _write_json(tgt_file, translated)
                return rel, True, f'meta.json übersetzt ({len(json.dumps(translated))} chars)'
            return rel, False, 'meta.json Übersetzung fehlgeschlagen'

        # Root meta.json → Sprachdaten setzen
        meta = dict(ref_data)
        meta['code']         = target_lang
        meta['name']         = LANG_NAMES.get(target_lang, target_lang.upper())
        meta['native']       = LANG_NAMES.get(target_lang, target_lang.upper())
        meta['completeness'] = 0
        _write_json(tgt_file, meta)
        return rel, True, 'meta.json angelegt'

    # Datei schon vorhanden und kein Force?
    if tgt_file.exists() and not force:
        # Konsistenz prüfen — nur übersetzen wenn Keys fehlen
        ref_data = _read_json(ref_file)
        tgt_data = _read_json(tgt_file)
        if ref_data and tgt_data:
            missing = _check_keys(ref_data, tgt_data)
            if not missing:
                return rel, True, 'OK (vollständig)'
            # Fehlende Keys ergänzen
            log.info(f"  ∆ {rel} [{target_lang}]: {len(missing)} Keys fehlen — ergänze...")
            # Nur fehlende Teile übersetzen ist komplex → ganze Datei neu
        force = True  # Neu übersetzen

    ref_data = _read_json(ref_file)
    if ref_data is None:
        return rel, False, 'Quelldatei nicht lesbar'

    translated = _deepseek_translate(ref_data, source_lang, target_lang, api_key)
    if translated is None:
        return rel, False, 'Deepseek Fehler nach Retries'

    if not isinstance(translated, dict):
        return rel, False, f'Ungültiger Rückgabetyp: {type(translated)}'

    ok = _write_json(tgt_file, translated)
    if ok:
        return rel, True, f'übersetzt ({len(json.dumps(translated))} chars)'
    return rel, False, 'Schreibfehler'


# ── Hauptlogik ────────────────────────────────────────────────────────────────

def discover_languages() -> list[str]:
    """Alle Sprachverzeichnisse unter i18n/ finden."""
    if not I18N_DIR.exists():
        log.error(f"i18n-Verzeichnis nicht gefunden: {I18N_DIR}")
        sys.exit(1)
    langs = sorted([
        d.name for d in I18N_DIR.iterdir()
        if d.is_dir() and not d.name.startswith('.')
    ])
    return langs


def translate_language(target_lang: str, api_key: str, force: bool = False,
                        workers: int = MAX_WORKERS) -> dict:
    """Übersetzt alle fehlenden Dateien für eine Sprache."""
    ref_dir    = I18N_DIR / REF_LANG
    target_dir = I18N_DIR / target_lang
    ref_files  = _collect_ref_files(ref_dir)

    tasks = []
    for ref_file in ref_files:
        tgt_file = _target_path(ref_file, ref_dir, target_dir)
        tasks.append((ref_file, tgt_file, REF_LANG, target_lang, api_key, force))

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
                    log.debug(f"    ✓ {rel}: {msg}")
                else:
                    results['ok'] += 1
                    log.info(f"    ✓ [{done:2d}/{len(tasks)}] {rel}: {msg}")
            else:
                results['fail'] += 1
                results['errors'].append(f"{rel}: {msg}")
                log.error(f"    ✗ [{done:2d}/{len(tasks)}] {rel}: {msg}")

    return results


def run(args) -> None:
    print("\n╔══════════════════════════════════════════════════════╗")
    print("║   i18n_translator.py — ABpE Portal Sprachgenerator   ║")
    print("╚══════════════════════════════════════════════════════╝\n")

    # Sprachen ermitteln
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

    # ── Konsistenz-Check ──────────────────────────────────────────────────
    log.info("\n── Konsistenz-Prüfung ──────────────────────────────────")
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

    if args.check:
        print(f"\nErgebnis: {total_issues} Problem(e) gefunden.")
        sys.exit(0 if total_issues == 0 else 1)

    if total_issues == 0 and not args.force:
        print("\n✅ Alle Sprachen vollständig — nichts zu tun.")
        return

    # ── API-Key laden ─────────────────────────────────────────────────────
    api_key = _load_api_key()
    if not api_key:
        log.error("Kein Deepseek API-Key in settings.json gefunden!")
        sys.exit(1)
    log.info(f"Deepseek API-Key: sk-...{api_key[-8:]}")

    # ── Übersetzen — alle Sprachen parallel ──────────────────────────────
    grand_ok = grand_fail = 0
    lang_results = {}

    def _translate_lang(lang):
        lang_name = LANG_NAMES.get(lang, lang.upper())
        log.info(f"  Starte: DE → {lang.upper()} ({lang_name})")
        return lang, translate_language(
            target_lang=lang,
            api_key=api_key,
            force=args.force,
            workers=MAX_WORKERS
        )

    with ThreadPoolExecutor(max_workers=len(target_langs)) as executor:
        futures = {executor.submit(_translate_lang, lang): lang for lang in target_langs}
        for future in as_completed(futures):
            lang, result = future.result()
            lang_results[lang] = result

    for lang in sorted(lang_results):
        result = lang_results[lang]
        grand_ok   += result['ok']
        grand_fail += result['fail']
        print(f"\n  Ergebnis {lang.upper()}:")
        print(f"    ✓ Übersetzt:    {result['ok']}")
        print(f"    → Übersprungen: {result['skip']}")
        print(f"    ✗ Fehler:       {result['fail']}")
        if result['errors']:
            for err in result['errors']:
                print(f"      • {err}")

    # ── Abschluss ─────────────────────────────────────────────────────────
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


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='ABpE Portal i18n Übersetzer — Deepseek API'
    )
    parser.add_argument(
        '--check', action='store_true',
        help='Nur Konsistenz prüfen, nicht übersetzen'
    )
    parser.add_argument(
        '--lang', type=str, default=None,
        help='Nur eine bestimmte Sprache übersetzen (z.B. --lang it)'
    )
    parser.add_argument(
        '--force', action='store_true',
        help='Alle Dateien neu übersetzen, auch vorhandene'
    )
    args = parser.parse_args()
    run(args)

