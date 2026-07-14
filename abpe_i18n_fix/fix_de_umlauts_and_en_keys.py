#!/usr/bin/env python3
"""DE: ae/oe/ue -> Umlaute. EN: 7 fehlende crm_telefon Keys."""
from __future__ import annotations

import json
from pathlib import Path

DE_PATH = Path('apps/abpe_crm/static/abpe_crm/i18n/de/modules/crm_telefon/crm_telefon.json')
EN_PATH = Path('apps/abpe_crm/static/abpe_crm/i18n/en/modules/crm_telefon/crm_telefon.json')

# Explizit (aus JS-Fallbacks / cat-Ausgabe)
DE_FIX = {
    'pbx_no_parked': 'Keine Parkplätze',
    'pbx_transfer': 'Übergeben',
    'pbx_transfer_title': 'An Nebenstelle übergeben',
    'pbx_dnd': 'nicht stören',
    'pbx_wiz_summary_none': 'Keine Empfänger in der Warteschlange',
    'pbx_wiz_summary_recipients': 'Empfänger',
    'pbx_wiz_summary_hint': (
        'Hinweis: Diese Zusammenfassung ist ein erster Entwurf - Betreff/Text werden '
        'noch nicht aus dem Compose-Reiter übernommen (bekannter Bug, folgt).'
    ),
    'pbx_wiz_back': 'Zurück',
    'pbx_mm_reminder_manual': 'Manuell prüfen',
    'pbx_no_contact': 'Kein Kontakt – über „ändern“ suchen',
    'pbx_meetme_delete': 'Löschen',
    'pbx_meetme_delete_confirm': (
        'Termin „{title}“ wirklich endgültig löschen?\n\n'
        'Der Termin wird dauerhaft aus der Datenbank entfernt. '
        'Dies kann nicht rückgängig gemacht werden.'
    ),
    'pbx_meetme_deleted': 'Termin gelöscht',
    'pbx_meetme_delete_err': 'Löschen fehlgeschlagen',
}

# Wort-Ersetzungen in allen DE-String-Werten (längere zuerst)
DE_WORDS = [
    ('Parkplaetze', 'Parkplätze'),
    ('Empfaenger', 'Empfänger'),
    ('uebernommen', 'übernommen'),
    ('uebergeben', 'übergeben'),
    ('Uebergeben', 'Übergeben'),
    ('Zurueck', 'Zurück'),
    ('stoeren', 'stören'),
    ('pruefen', 'prüfen'),
    ('ueberlagern', 'überlagern'),
]

EN_ADD = {
    'pbx_meetme_invite': 'Proceed to invitations',
    'pbx_meetme_reminders_manage': 'Manage reminders',
    'pbx_mm_decline_confirm': 'Mark guest as "not attending"?',
    'pbx_mm_status_agreed': 'Appointment confirmed',
    'pbx_mm_status_none_invited': 'No invitations sent yet',
    'pbx_mm_status_pending': 'Invitation pending',
    'pbx_no_contact': 'No contact – search via “change”',
    'pbx_meetme_delete': 'Delete',
    'pbx_meetme_delete_confirm': (
        'Permanently delete meeting "{title}"?\n\n'
        'The meeting will be removed from the database. '
        'This cannot be undone.'
    ),
    'pbx_meetme_deleted': 'Meeting deleted',
    'pbx_meetme_delete_err': 'Delete failed',
}


def _load_flat(path: Path) -> dict:
    data = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(data.get('crm_telefon'), dict):
        return data['crm_telefon']
    return data


def _save_flat(path: Path, flat: dict) -> None:
    path.write_text(
        json.dumps(flat, ensure_ascii=False, indent=4) + '\n',
        encoding='utf-8',
    )


def fix_de() -> int:
    flat = _load_flat(DE_PATH)
    n = 0
    for key, val in DE_FIX.items():
        if flat.get(key) != val:
            flat[key] = val
            n += 1
            print(f'  DE {key}: {val!r}')
    for key, val in list(flat.items()):
        if not isinstance(val, str):
            continue
        new = val
        for old, rep in DE_WORDS:
            new = new.replace(old, rep)
        if new != val:
            flat[key] = new
            n += 1
            print(f'  DE {key}: {val!r} -> {new!r}')
    if n:
        _save_flat(DE_PATH, flat)
    print(f'DE: {n} Aenderung(en)')
    return n


def fix_en() -> int:
    flat = _load_flat(EN_PATH)
    n = 0
    for key, val in EN_ADD.items():
        if key not in flat or flat[key] != val:
            flat[key] = val
            n += 1
            print(f'  EN + {key}: {val!r}')
    if n:
        _save_flat(EN_PATH, flat)
    print(f'EN: {n} Key(s) ergaenzt/aktualisiert')
    return n


if __name__ == '__main__':
    print('=== DE Umlaut-Bereinigung ===')
    fix_de()
    print('\n=== EN fehlende Keys ===')
    fix_en()
