#!/usr/bin/env python3
"""i18n-Keys für Archiv-Löschen (MeetMe) in crm_telefon.json.

Auf ucs5:
  cd /opt/abpe/backend
  python3 abpe_i18n_fix/patch_meetme_delete_i18n.py
  python3 abpe_i18n_fix/patch_meetme_delete_i18n.py --deepseek   # weitere Sprachen via DeepSeek
  python manage.py collectstatic --noinput
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BACKEND = Path(os.environ.get('ABPE_BACKEND', '/opt/abpe/backend'))
I18N_ROOT = BACKEND / 'apps/abpe_crm/static/abpe_crm/i18n'
MODULE = 'crm_telefon'

KEYS_DE = {
    'pbx_meetme_delete': 'Löschen',
    'pbx_meetme_delete_confirm': (
        'Termin „{title}“ wirklich endgültig löschen?\n\n'
        'Der Termin wird dauerhaft aus der Datenbank entfernt. '
        'Dies kann nicht rückgängig gemacht werden.'
    ),
    'pbx_meetme_deleted': 'Termin gelöscht',
    'pbx_meetme_delete_err': 'Löschen fehlgeschlagen',
}

KEYS_EN = {
    'pbx_meetme_delete': 'Delete',
    'pbx_meetme_delete_confirm': (
        'Permanently delete meeting "{title}"?\n\n'
        'The meeting will be removed from the database. '
        'This cannot be undone.'
    ),
    'pbx_meetme_deleted': 'Meeting deleted',
    'pbx_meetme_delete_err': 'Delete failed',
}

LANG_LABEL = {
    'en': 'Englisch',
    'fr': 'Französisch',
    'it': 'Italienisch',
    'es': 'Spanisch',
    'nl': 'Niederländisch',
    'pl': 'Polnisch',
    'cs': 'Tschechisch',
    'tr': 'Türkisch',
}


def _json_path(lang: str) -> Path:
    return I18N_ROOT / lang / 'modules' / MODULE / f'{MODULE}.json'


def _load_flat(path: Path) -> dict:
    data = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(data.get(MODULE), dict):
        return data[MODULE]
    return data


def _save_flat(path: Path, flat: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(flat, ensure_ascii=False, indent=4) + '\n', encoding='utf-8')


def _patch_lang(lang: str, keys: dict) -> int:
    path = _json_path(lang)
    if not path.is_file():
        print(f'  {lang}: {path} fehlt — übersprungen')
        return 0
    flat = _load_flat(path)
    n = 0
    for key, val in keys.items():
        if flat.get(key) != val:
            flat[key] = val
            n += 1
            print(f'  {lang} {key}: {val!r}')
    if n:
        _save_flat(path, flat)
    return n


def _setup_django() -> None:
    os.chdir(BACKEND)
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abpe.settings')
    import django
    django.setup()


def _deepseek_translate(text: str, lang: str) -> str:
    from apps.abpe_crm.services.deepseek_api_pbx import deepseek_pbx
    label = LANG_LABEL.get(lang, lang)
    instruction = (
        f'Übersetze den folgenden UI-Text für eine CRM-Oberfläche ins {label}. '
        'Behalte Platzhalter wie {title} exakt bei. '
        'Antworte nur mit der Übersetzung, ohne Anführungszeichen oder Erklärung.'
    )
    result = deepseek_pbx.summarize(text, instruction)
    if hasattr(result, 'text'):
        return (result.text or text).strip()
    if isinstance(result, dict):
        return (result.get('text') or result.get('suggestion') or text).strip()
    return str(result or text).strip()


def _deepseek_fill(lang: str, source: dict[str, str]) -> int:
    path = _json_path(lang)
    if not path.is_file():
        print(f'  {lang}: Datei fehlt — übersprungen')
        return 0
    flat = _load_flat(path)
    n = 0
    for key, de_val in source.items():
        if key in flat and flat[key]:
            continue
        try:
            translated = _deepseek_translate(de_val, lang)
        except Exception as exc:
            print(f'  {lang} {key}: DeepSeek fehlgeschlagen ({exc})')
            continue
        flat[key] = translated
        n += 1
        print(f'  {lang} {key}: {translated!r}')
    if n:
        _save_flat(path, flat)
    return n


def main() -> int:
    parser = argparse.ArgumentParser(description='MeetMe-Archiv-Löschen i18n patchen')
    parser.add_argument('--deepseek', action='store_true', help='Fehlende Keys in anderen Sprachen via DeepSeek übersetzen')
    parser.add_argument('--backend', default=str(BACKEND), help='Pfad zu /opt/abpe/backend')
    args = parser.parse_args()

    global BACKEND, I18N_ROOT
    BACKEND = Path(args.backend)
    I18N_ROOT = BACKEND / 'apps/abpe_crm/static/abpe_crm/i18n'

    if not I18N_ROOT.is_dir():
        print(f'FEHLER: {I18N_ROOT} nicht gefunden', file=sys.stderr)
        return 1

    print('=== DE Keys ===')
    de_n = _patch_lang('de', KEYS_DE)
    print(f'DE: {de_n} Key(s) gesetzt\n')

    print('=== EN Keys ===')
    en_n = _patch_lang('en', KEYS_EN)
    print(f'EN: {en_n} Key(s) gesetzt\n')

    if not args.deepseek:
        print('Hinweis: --deepseek für automatische Übersetzung in weitere Sprachen')
        return 0

    print('=== DeepSeek-Übersetzer ===')
    _setup_django()
    total = 0
    for lang_dir in sorted(I18N_ROOT.iterdir()):
        if not lang_dir.is_dir() or lang_dir.name in ('de', 'en'):
            continue
        print(f'\n{lang_dir.name}:')
        total += _deepseek_fill(lang_dir.name, KEYS_DE)
    print(f'\nDeepSeek: {total} Key(s) ergänzt')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
