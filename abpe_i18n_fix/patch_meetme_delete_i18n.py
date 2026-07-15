#!/usr/bin/env python3
"""Nur DE: fehlende MeetMe-Archiv-Löschen-Keys in crm_telefon.json ergänzen.

Workflow (ucs5):
  1. python3 patch_meetme_delete_i18n.py
  2. python apps/abpe_crm/bin/i18n_translator.py
  3. python apps/abpe_crm/bin/i18n_validate.py
  4. python manage.py collectstatic --noinput
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

DEFAULT_BACKEND = Path(os.environ.get('ABPE_BACKEND', '/opt/abpe/backend'))
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


def _json_path(i18n_root: Path, lang: str) -> Path:
    return i18n_root / lang / 'modules' / MODULE / f'{MODULE}.json'


def _load_flat(path: Path) -> tuple[dict, bool]:
    data = json.loads(path.read_text(encoding='utf-8'))
    wrapped = isinstance(data.get(MODULE), dict)
    if wrapped:
        return data[MODULE], True
    return data, False


def _save_flat(path: Path, flat: dict, wrapped: bool) -> None:
    if wrapped:
        data = json.loads(path.read_text(encoding='utf-8'))
        data[MODULE] = flat
    else:
        data = flat
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4) + '\n', encoding='utf-8')


def patch_de(i18n_root: Path) -> int:
    path = _json_path(i18n_root, 'de')
    if not path.is_file():
        print(f'FEHLER: {path} nicht gefunden', file=sys.stderr)
        return 1
    flat, wrapped = _load_flat(path)
    n = 0
    for key, val in KEYS_DE.items():
        if flat.get(key) != val:
            flat[key] = val
            n += 1
            print(f'  DE {key}: {val!r}')
    if n:
        _save_flat(path, flat, wrapped)
    print(f'DE: {n} Key(s) ergänzt/aktualisiert')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='MeetMe-Archiv-Löschen: DE-Keys ergänzen')
    parser.add_argument('--backend', default=str(DEFAULT_BACKEND))
    args = parser.parse_args()

    backend = Path(args.backend)
    i18n_root = backend / 'apps/abpe_crm/static/abpe_crm/i18n'
    rc = patch_de(i18n_root)
    if rc:
        return rc
    print('\nNächster Schritt: python apps/abpe_crm/bin/i18n_translator.py')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
