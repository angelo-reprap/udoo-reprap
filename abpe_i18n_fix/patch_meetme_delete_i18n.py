#!/usr/bin/env python3
"""Nur DE: fehlende MeetMe-Archiv-Löschen-Keys in crm_telefon.json ergänzen.

Workflow (ucs5):
  1. python3 patch_meetme_delete_i18n.py          # nur DE
  2. python manage.py sync_i18n …                 # euer übliches Sprachpaket-Tool
  3. python manage.py collectstatic --noinput

Optional: --deepseek-all  (falls kein sync_i18n — DeepSeek für alle Sprachen)
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

LANG_LABEL = {
    'en': 'Englisch', 'fr': 'Französisch', 'it': 'Italienisch', 'es': 'Spanisch',
    'nl': 'Niederländisch', 'pl': 'Polnisch', 'cs': 'Tschechisch', 'tr': 'Türkisch',
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


def patch_de() -> int:
    path = _json_path('de')
    if not path.is_file():
        print(f'FEHLER: {path} nicht gefunden', file=sys.stderr)
        return 1
    flat = _load_flat(path)
    n = 0
    for key, val in KEYS_DE.items():
        if flat.get(key) != val:
            flat[key] = val
            n += 1
            print(f'  DE {key}: {val!r}')
    if n:
        _save_flat(path, flat)
    print(f'DE: {n} Key(s) ergänzt/aktualisiert')
    return 0


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


def deepseek_all() -> int:
    _setup_django()
    total = 0
    for lang_dir in sorted(I18N_ROOT.iterdir()):
        if not lang_dir.is_dir() or lang_dir.name == 'de':
            continue
        path = _json_path(lang_dir.name)
        if not path.is_file():
            continue
        flat = _load_flat(path)
        lang = lang_dir.name
        for key, de_val in KEYS_DE.items():
            if key in flat and flat[key]:
                continue
            try:
                flat[key] = _deepseek_translate(de_val, lang)
                total += 1
                print(f'  {lang} {key}: {flat[key]!r}')
            except Exception as exc:
                print(f'  {lang} {key}: DeepSeek fehlgeschlagen ({exc})')
        _save_flat(path, flat)
    print(f'DeepSeek: {total} Key(s) ergänzt')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='MeetMe-Archiv-Löschen: DE-Keys ergänzen')
    parser.add_argument('--deepseek-all', action='store_true',
                        help='Fallback: alle Sprachen via DeepSeek (sonst euer sync_i18n nutzen)')
    parser.add_argument('--backend', default=str(BACKEND))
    args = parser.parse_args()

    global BACKEND, I18N_ROOT
    BACKEND = Path(args.backend)
    I18N_ROOT = BACKEND / 'apps/abpe_crm/static/abpe_crm/i18n'

    rc = patch_de()
    if rc:
        return rc
    if args.deepseek_all:
        return deepseek_all()
    print('\nNächster Schritt: euer Sprachpaket-Sync (z.B. python manage.py sync_i18n …)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
