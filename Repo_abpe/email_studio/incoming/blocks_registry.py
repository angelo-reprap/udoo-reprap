"""
MCID — Blöcke und Format-Modul-Hüllen (Regel 9–10).

Variable = Rohdaten
Modul    = Format-Hülle ({{block:id}} / {{block:id}}…{{/block}} + {{content}})
Block    = Modul + gebundene Variablen (Komposition)
"""
from __future__ import annotations

from typing import Any

# Module die Inhalt zwischen {{block:id}}…{{/block}} erwarten
PAIRED_MODULE_IDS: frozenset[str] = frozenset({
    'fmt_aufzaehlung',
    'fmt_key_value',
    'fmt_tabelle',
    'fmt_zwei_spalten',
    'fmt_hinweis',
})

# Fallback-Hüllen wenn Modul noch nicht in der DB liegt (Regel 8 CI)
_MODULE_HUSKS: dict[str, dict[str, str]] = {
    'fmt_aufzaehlung': {
        'html': (
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
            '<tr><td style="padding:16px 24px;font-family:Arial;font-size:14px;'
            'color:#333333;line-height:1.5;">{{content}}</td></tr></table>'
        ),
        'text': '{{content}}',
    },
    'fmt_key_value': {
        'html': (
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
            '<tr><td style="padding:16px 24px;font-family:Arial;font-size:14px;'
            'color:#333333;">{{content}}</td></tr></table>'
        ),
        'text': '{{content}}',
    },
    'fmt_tabelle': {
        'html': (
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
            '<tr><td style="padding:16px 24px;">{{content}}</td></tr></table>'
        ),
        'text': '{{content}}',
    },
    'fmt_zwei_spalten': {
        'html': (
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
            '<tr><td style="padding:16px 24px;background-color:#f8f9fa;">{{content}}</td></tr></table>'
        ),
        'text': '{{content}}',
    },
    'fmt_hinweis': {
        'html': (
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
            '<tr><td style="padding:16px 24px;background-color:#f8f9fa;border-left:3px solid #163258;'
            'font-family:Arial;font-size:14px;color:#333333;">{{content}}</td></tr></table>'
        ),
        'text': '{{content}}',
    },
}

# MCID-Blöcke (Kompositionen)
BLOCKS: list[dict[str, Any]] = [
    {
        'id': 'block_teilnehmer',
        'name': 'Teilnehmerliste',
        'description': 'Aufzählung der Gesprächsteilnehmer (MeetMe)',
        'module': 'fmt_aufzaehlung',
        'variables': ['teilnehmer_liste', 'teilnehmer_liste_html'],
        'legacy_html_var': 'teilnehmer_liste_html',
        'suggest_when': ['teilnehmer', 'meetme', 'konferenz', 'einladung'],
        'paired': True,
    },
    {
        'id': 'block_system_status',
        'name': 'System-Status',
        'description': 'Status als Tabelle (Check / Wert / Status)',
        'module': 'fmt_tabelle',
        'variables': ['system_status_html', 'system_status'],
        'legacy_html_var': 'system_status_html',
        'suggest_when': ['status', 'system', 'monitoring', 'ampel'],
        'paired': False,
    },
    {
        'id': 'block_termin',
        'name': 'Termin-Fakten',
        'description': 'Datum, Uhrzeit, Raum, Einwahl als Key-Value',
        'module': 'fmt_key_value',
        'variables': ['termin_datum', 'termin_uhrzeit', 'raum', 'einwahl_info', 'title'],
        'legacy_html_var': '',
        'suggest_when': ['termin', 'datum', 'uhrzeit', 'einladung', 'meetme'],
        'paired': True,
    },
]


def get_block(block_id: str) -> dict[str, Any] | None:
    for b in BLOCKS:
        if b['id'] == block_id:
            return b
    return None


def get_blocks() -> list[dict[str, Any]]:
    return list(BLOCKS)


def get_module_husk(module_id: str, kind: str = 'html') -> str:
    husk = _MODULE_HUSKS.get(module_id)
    if not husk:
        return ''
    return husk.get(kind, '')


def is_paired_module(module_id: str) -> bool:
    if module_id in PAIRED_MODULE_IDS:
        return True
    b = get_block(module_id)
    return bool(b and b.get('paired'))


def module_insert_syntax(module_id: str) -> str:
    if is_paired_module(module_id):
        return f'{{{{block:{module_id}}}}}\n\n{{{{/block}}}}'
    return f'{{{{block:{module_id}}}}}'


def block_insert_syntax(block_id: str) -> str:
    b = get_block(block_id)
    if not b:
        return f'{{{{block:{block_id}}}}}'
    if b.get('paired'):
        return f'{{{{block:{block_id}}}}}\n\n{{{{/block}}}}'
    return f'{{{{block:{block_id}}}}}'


def suggest_blocks_for_text(text: str) -> list[dict[str, Any]]:
    """Heuristik: welche Blöcke passen zum Briefing/HTML (für KI-UI)."""
    low = (text or '').lower()
    out: list[dict[str, Any]] = []
    for b in BLOCKS:
        keys = b.get('suggest_when') or []
        if any(k in low for k in keys):
            out.append({
                'id': b['id'],
                'name': b['name'],
                'description': b['description'],
                'module': b['module'],
                'syntax': block_insert_syntax(b['id']),
                'question_de': _suggest_question_de(b),
                'question_en': _suggest_question_en(b),
            })
    return out


def _suggest_question_de(b: dict[str, Any]) -> str:
    return {
        'block_teilnehmer': 'Teilnehmer von–bis als Aufzählung anzeigen?',
        'block_system_status': 'System-Status als Tabelle (Check/Wert/Status) anzeigen?',
        'block_termin': 'Termin-Daten (Datum, Uhrzeit, Raum) als Liste darstellen?',
    }.get(b['id'], f'Als Block „{b["name"]}“ einfügen?')


def _suggest_question_en(b: dict[str, Any]) -> str:
    return {
        'block_teilnehmer': 'Show participants as a bullet list?',
        'block_system_status': 'Show system status as a table (Check/Value/Status)?',
        'block_termin': 'Show meeting details (date, time, room) as a list?',
    }.get(b['id'], f'Insert as block “{b["name"]}”?')


def plain_list_to_html(plain: str) -> str:
    """'A, B' oder Zeilen → <ul><li>…</ul>."""
    text = (plain or '').strip()
    if not text:
        return ''
    if '<' in text and '>' in text:
        return text
    parts = [p.strip() for p in re_split_list(text) if p.strip()]
    if not parts:
        return ''
    items = ''.join(f'<li>{_esc(p)}</li>' for p in parts)
    return f'<ul>{items}</ul>'


def plain_list_to_text(plain: str) -> str:
    text = (plain or '').strip()
    if not text:
        return ''
    parts = [p.strip() for p in re_split_list(text) if p.strip()]
    return '\n'.join(f'• {p}' for p in parts)


def re_split_list(text: str) -> list[str]:
    import re
    if '\n' in text:
        return text.splitlines()
    return re.split(r'\s*,\s*', text)


def _esc(s: str) -> str:
    return (
        s.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


def termin_key_value_html(variables: dict) -> str:
    rows = [
        ('Titel', variables.get('title')),
        ('Datum', variables.get('termin_datum')),
        ('Uhrzeit', variables.get('termin_uhrzeit') or variables.get('termin_zeit')),
        ('Raum', variables.get('raum')),
        ('Einwahl', variables.get('einwahl_info')),
    ]
    parts = []
    for label, val in rows:
        if val:
            parts.append(f'<div><strong>{_esc(str(label))}:</strong> {_esc(str(val))}</div>')
    return ''.join(parts)


def termin_key_value_text(variables: dict) -> str:
    rows = [
        ('Titel', variables.get('title')),
        ('Datum', variables.get('termin_datum')),
        ('Uhrzeit', variables.get('termin_uhrzeit') or variables.get('termin_zeit')),
        ('Raum', variables.get('raum')),
        ('Einwahl', variables.get('einwahl_info')),
    ]
    return '\n'.join(f'{lab}: {val}' for lab, val in rows if val)
