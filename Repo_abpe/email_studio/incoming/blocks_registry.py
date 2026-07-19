"""
MCID — Blöcke und Format-Modul-Hüllen (Regel 9–10).

Variable = Rohdaten
Modul    = Format-Hülle ({{block:id}} / {{block:id}}…{{/block}} + {{content}})
Block    = Modul + gebundene Variablen (Komposition)
"""
from __future__ import annotations

import re
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
    """Einfüge-Syntax: innen nur Plaintext / {variablen}, kein HTML."""
    samples = {
        'fmt_aufzaehlung': 'Hund\nKatze\nPferd',
        'fmt_key_value': 'Hund: 45 €\nKatze: 30 €\nPferd: 120 €',
        'fmt_tabelle': 'Tier | Futter/Monat\nHund | 45 €\nKatze | 30 €',
        'fmt_zwei_spalten': 'Links\n---\nRechts',
        'fmt_hinweis': 'Kurzer Hinweis an den Empfänger.',
    }
    if is_paired_module(module_id):
        sample = samples.get(module_id, 'Inhalt hier\noder {variable}')
        return f'{{{{block:{module_id}}}}}\n{sample}\n{{{{/block}}}}'
    return f'{{{{block:{module_id}}}}}'


def block_insert_syntax(block_id: str) -> str:
    b = get_block(block_id)
    if not b:
        return f'{{{{block:{block_id}}}}}'
    # Inhalts-Blöcke meist selbstschließend (Daten kommen aus Variablen)
    if b.get('paired'):
        return f'{{{{block:{block_id}}}}}\n{{{{/block}}}}'
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


def _looks_like_html(text: str) -> bool:
    t = (text or '').strip().lower()
    return any(tag in t for tag in ('<ul', '<ol', '<li', '<table', '<tr', '<p', '<div', '<br'))


def format_inner_for_module(module_id: str, content: str, *, html: bool = True) -> str:
    """
    MCID Regel 6/9: Inner-Content ist Plaintext + {variablen}.
    Das Format-Modul formatiert — der Nutzer tippt kein <ul>/<li>.
    Bereits vorhandenes HTML (Migration/KI) wird durchgereicht.
    """
    raw = (content or '').strip()
    if not raw:
        return ''
    if _looks_like_html(raw):
        return raw

    if module_id == 'fmt_aufzaehlung':
        return plain_list_to_html(raw) if html else plain_list_to_text(raw)
    if module_id == 'fmt_key_value':
        return key_value_to_html(raw) if html else key_value_to_text(raw)
    if module_id == 'fmt_tabelle':
        return pipe_table_to_html(raw) if html else pipe_table_to_text(raw)
    if module_id == 'fmt_zwei_spalten':
        return two_col_to_html(raw) if html else two_col_to_text(raw)
    if module_id == 'fmt_hinweis':
        return hint_to_html(raw) if html else raw
    # Unbekanntes Format-Modul: Zeilen → <br> / unverändert
    if html:
        return '<br>'.join(_esc_keep_vars(line) for line in raw.splitlines() if line.strip())
    return raw


def plain_list_to_html(plain: str) -> str:
    """Zeilen oder 'A, B' → <ul><li>…</ul>. Kein HTML vom Nutzer nötig."""
    parts = _list_items(plain)
    if not parts:
        return ''
    items = ''.join(
        f'<li style="margin:0 0 6px 0;">{_esc_keep_vars(p)}</li>' for p in parts
    )
    return (
        f'<ul style="margin:0;padding-left:22px;list-style-type:disc;'
        f'font-family:Arial;font-size:14px;color:#333333;">{items}</ul>'
    )


def plain_list_to_text(plain: str) -> str:
    parts = _list_items(plain)
    return '\n'.join(f'• {p}' for p in parts)


def key_value_to_html(plain: str) -> str:
    rows = _key_value_rows(plain)
    if not rows:
        return plain_list_to_html(plain)
    parts = []
    for lab, val in rows:
        parts.append(
            f'<div style="margin:0 0 8px 0;line-height:1.5;">'
            f'<strong>{_esc_keep_vars(lab)}:</strong> {_esc_keep_vars(val)}</div>'
        )
    return ''.join(parts)


def key_value_to_text(plain: str) -> str:
    rows = _key_value_rows(plain)
    if not rows:
        return plain_list_to_text(plain)
    return '\n'.join(f'{lab}: {val}' for lab, val in rows)


def pipe_table_to_html(plain: str) -> str:
    lines = [ln.strip() for ln in (plain or '').splitlines() if ln.strip()]
    # Einzeiler: „A | B C | D E | F“ → Zeilen zu je 2 Spalten (Label|Wert)
    if len(lines) == 1 and lines[0].count('|') >= 3:
        cells = [c.strip() for c in lines[0].split('|') if c.strip()]
        if len(cells) >= 4 and len(cells) % 2 == 0:
            lines = [
                f'{cells[i]} | {cells[i + 1]}'
                for i in range(0, len(cells), 2)
            ]
    if not lines:
        return ''
    rows = [ [c.strip() for c in ln.split('|')] for ln in lines ]
    if len(rows) == 1 and len(rows[0]) == 1:
        return plain_list_to_html(plain)
    head, *body = rows
    th = ''.join(
        f'<th align="left" style="padding:6px 8px;border-bottom:1px solid #dee2e6;'
        f'font-family:Arial;font-size:12px;color:#333333;">{_esc_keep_vars(c)}</th>'
        for c in head
    )
    trs = [
        '<tr>' + ''.join(
            f'<td style="padding:6px 8px;border-bottom:1px solid #dee2e6;'
            f'font-family:Arial;font-size:14px;color:#333333;">{_esc_keep_vars(c)}</td>'
            for c in row
        ) + '</tr>'
        for row in body
    ]
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        'style="border-collapse:collapse;width:100%;">'
        f'<tr>{th}</tr>{"".join(trs)}</table>'
    )


def pipe_table_to_text(plain: str) -> str:
    lines = [ln.strip() for ln in (plain or '').splitlines() if ln.strip()]
    return '\n'.join(lines)


def two_col_to_html(plain: str) -> str:
    left, right = _split_two_cols(plain)
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        '<tr>'
        f'<td width="50%" valign="top" style="padding:8px 12px 8px 0;font-family:Arial;'
        f'font-size:14px;color:#333333;border-right:1px solid #dee2e6;">{_esc_keep_vars(left).replace(chr(10), "<br>")}</td>'
        f'<td width="50%" valign="top" style="padding:8px 0 8px 12px;font-family:Arial;'
        f'font-size:14px;color:#333333;">{_esc_keep_vars(right).replace(chr(10), "<br>")}</td>'
        '</tr></table>'
    )


def two_col_to_text(plain: str) -> str:
    left, right = _split_two_cols(plain)
    return f'{left}\n\n{right}'


def hint_to_html(plain: str) -> str:
    paras = [p.strip() for p in re.split(r'\n\s*\n', plain or '') if p.strip()]
    if not paras:
        return ''
    return ''.join(
        f'<p style="margin:0 0 8px 0;">{_esc_keep_vars(p).replace(chr(10), "<br>")}</p>'
        for p in paras
    )


def _list_items(text: str) -> list[str]:
    """
    MCID Aufzählung — vereinbarte Trenner (Priorität):

    1. Zeilenumbruch (Standard): eine Zeile = ein Bullet
    2. Semikolon (Einzeiler): ``Hund; Katze; Pferd``
    3. Komma / Mittelpunkt (Fallback)
    4. Leerzeichen nur bei kurzen Einzelwörtern (KI-Fallback)

    Der Nutzer tippt keine ``*`` / ``-`` — der Renderer setzt die Bullets.
    """
    raw = (text or '').strip()
    if not raw:
        return []

    def _clean(line: str) -> str:
        s = line.strip().rstrip(';').strip()
        return re.sub(r'^[\-\*\u2022\u25B8•▸·]+\s*', '', s).strip()

    if '\n' in raw:
        lines = [_clean(ln) for ln in raw.splitlines()]
        return [ln for ln in lines if ln]

    # Semikolon = offizielle Einzeiler-Form (auch ohne Leerzeichen, trailing ;)
    if ';' in raw:
        parts = [_clean(p) for p in raw.split(';')]
        parts = [p for p in parts if p]
        if len(parts) >= 2:
            return parts

    # Weitere explizite Trenner
    for sep in (r'\s*[·•]\s*', r'\s*,\s+'):
        parts = [_clean(p) for p in re.split(sep, raw)]
        parts = [p for p in parts if p]
        if len(parts) >= 2:
            return parts

    # „Pferd Hund Schildkröte“ — kurze Wörter, kein Satz (KI-Fallback)
    if not re.search(r'[.!?]', raw):
        words = [_clean(w) for w in raw.split()]
        words = [w for w in words if w]
        if 2 <= len(words) <= 16 and all(len(w) <= 40 for w in words):
            return words

    return [_clean(raw)] if _clean(raw) else []


def _key_value_rows(plain: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in (plain or '').splitlines():
        s = line.strip()
        if not s:
            continue
        if '|' in s and s.count('|') == 1:
            a, b = s.split('|', 1)
            rows.append((a.strip(), b.strip()))
            continue
        if ':' in s:
            a, b = s.split(':', 1)
            rows.append((a.strip(), b.strip()))
            continue
        rows.append((s, ''))
    return rows


def _split_two_cols(plain: str) -> tuple[str, str]:
    text = (plain or '').strip()
    for sep in ('\n---\n', '\n--\n', '\n|\n'):
        if sep in text:
            a, b = text.split(sep, 1)
            return a.strip(), b.strip()
    parts = [p.strip() for p in text.split('\n\n') if p.strip()]
    if len(parts) >= 2:
        return parts[0], '\n\n'.join(parts[1:])
    lines = text.splitlines()
    mid = max(1, len(lines) // 2)
    return '\n'.join(lines[:mid]).strip(), '\n'.join(lines[mid:]).strip()


def re_split_list(text: str) -> list[str]:
    return _list_items(text)


def _esc(s: str) -> str:
    return (
        s.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


def _esc_keep_vars(s: str) -> str:
    """HTML-escapen, {variable}-Tokens unangetastet lassen."""
    parts = re.split(r'(\{[a-zA-Z_][a-zA-Z0-9_]*\})', s or '')
    return ''.join(p if (p.startswith('{') and p.endswith('}')) else _esc(p) for p in parts)


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
