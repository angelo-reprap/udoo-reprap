#!/usr/bin/env python3
"""DE: Reporting-Modul i18n-Keys in crm_reporting.json ergänzen.

Workflow (ucs5):
  1. python3 patch_reporting_i18n.py
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
MODULE = 'crm_reporting'

KEYS_DE = {
    'reporting_sync': 'Reporting & Sync',
    'sync_starten': 'Sync starten',
    'sync_gestartet': 'Sync wird gestartet — bitte warten...',
    'rep_loading': 'Lade Reporting…',
    'rep_load_err': 'Reporting konnte nicht geladen werden',
    'rep_never': 'Noch nie',
    'rep_no_data': 'Keine Daten',
    'rep_refresh': 'Aktualisieren',
    'rep_last_sync': 'Letzter Sync',
    'rep_sync_ok': 'OK',
    'rep_sync_unknown': 'Unbekannt',
    'rep_sync_empty': 'Leer',
    'rep_legacy_api': 'Erweiterte API noch nicht installiert — Basis-Zähler aus /crm/api/sync/status/',
    'rep_sync_unavailable': 'Sync-Endpoint noch nicht verfügbar. Bitte reporting_views.py installieren.',
    'rep_sync_not_wired': 'Sync-Job ist noch nicht angebunden — Daten kommen live aus der DB.',
    'rep_generated': 'Stand',
    'rep_kpi_contacts': 'Kontakte',
    'rep_kpi_accounts': 'Accounts',
    'rep_kpi_emails': 'E-Mails',
    'rep_kpi_documents': 'Dokumente',
    'rep_kpi_notes': 'Notizen',
    'rep_section_overview': 'Datenübersicht',
    'rep_section_quality': 'Datenqualität',
    'rep_section_growth': 'Wachstum (30 Tage)',
    'rep_section_meetme': 'Konferenz / MeetMe',
    'rep_q_no_email': 'Kontakte ohne E-Mail',
    'rep_q_opt_out': 'E-Mails Opt-out',
    'rep_q_invalid': 'Ungültige E-Mail-Adressen',
    'rep_q_active_emails': 'Aktive E-Mail-Adressen',
    'rep_q_linked': 'Primäre Kontakt-E-Mails',
    'rep_growth_contacts': 'Neue Kontakte (30 Tage)',
    'rep_growth_accounts': 'Neue Accounts (30 Tage)',
    'rep_growth_documents': 'Neue Dokumente (30 Tage)',
    'rep_mm_meetings': 'Termine gesamt',
    'rep_mm_upcoming': 'Anstehende Termine',
    'rep_mm_cancelled': 'Abgesagte Termine',
    'rep_mm_guests': 'Aktive Gäste',
    'rep_mm_reminders': 'Offene Erinnerungen',
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
            print(f'  DE {key}')
    if n:
        _save_flat(path, flat, wrapped)
    print(f'DE: {n} Key(s) ergänzt/aktualisiert')

    manifest_path = i18n_root / 'de' / 'modules' / MODULE / 'manifest.json'
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {'files': [f'{MODULE}.json']}
    if not manifest_path.is_file() or json.loads(manifest_path.read_text()) != manifest:
        manifest_path.write_text(json.dumps(manifest, indent=4) + '\n', encoding='utf-8')
        print(f'  manifest.json: {manifest_path}')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Reporting-Modul: DE-Keys ergänzen')
    parser.add_argument('--backend', default=str(DEFAULT_BACKEND))
    args = parser.parse_args()
    rc = patch_de(Path(args.backend) / 'apps/abpe_crm/static/abpe_crm/i18n')
    if not rc:
        print('\nNächster Schritt: python apps/abpe_crm/bin/i18n_translator.py')
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
