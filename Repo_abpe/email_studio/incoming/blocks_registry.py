"""
MCID — Blöcke und Format-Modul-Hüllen (Regel 8–10).

Variable = Rohdaten
Modul    = Format-Hülle ({{block:id}} / {{block:id}}…{{/block}} + {{content}})
Block    = Modul + gebundene Variablen (Komposition)
"""
from __future__ import annotations

import html as html_mod
import re
from typing import Any

# ── Regel 8 — CI-Tokens ──────────────────────────────────────────
CI_FONT = 'Arial'
CI_SIZE = '14px'
CI_SIZE_SMALL = '12px'
CI_SIZE_HEADER = '18px'
CI_LINE = '1.5'
CI_TEXT = '#333333'
CI_BRAND = '#163258'
CI_MUTED = '#6c757d'
CI_BG = '#f8f9fa'
CI_BORDER = '#dee2e6'
CI_INFO_BG = '#e8f0f8'
CI_OK = '#28a745'
CI_WARN = '#dc3545'
CI_WHITE = '#ffffff'
CI_PAD = '16px 24px'
CI_LIST_GAP = '8px'

# Immer dasselbe Bullet (Regel 2 — Unicode, kein CSS-list-style)
LIST_BULLET = '•'

# Module die Inhalt zwischen {{block:id}}…{{/block}} erwarten
PAIRED_MODULE_IDS: frozenset[str] = frozenset({
    'fmt_aufzaehlung',
    'fmt_key_value',
    'fmt_tabelle',
    'fmt_zwei_spalten',
    'fmt_hinweis',
})

# Alle Format-Module (inkl. selbstschließend)
FORMAT_MODULE_IDS: frozenset[str] = PAIRED_MODULE_IDS | frozenset({
    'fmt_trenner',
})

_TD = (
    f'font-family:{CI_FONT};font-size:{CI_SIZE};'
    f'color:{CI_TEXT};line-height:{CI_LINE};'
)


def _husk_slot(extra_td: str = '') -> str:
    style = f'padding:{CI_PAD};{_TD}{extra_td}'
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td style="{style}">{{{{content}}}}</td></tr></table>'
    )


# Fallback-Hüllen wenn Modul noch nicht in der DB liegt
_MODULE_HUSKS: dict[str, dict[str, str]] = {
    'fmt_aufzaehlung': {
        'html': _husk_slot(),
        'text': '{{content}}',
    },
    'fmt_key_value': {
        'html': _husk_slot(),
        'text': '{{content}}',
    },
    'fmt_tabelle': {
        'html': (
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
            f'<tr><td style="padding:{CI_PAD};">{{{{content}}}}</td></tr></table>'
        ),
        'text': '{{content}}',
    },
    'fmt_zwei_spalten': {
        'html': _husk_slot(f'background-color:{CI_BG};'),
        'text': '{{content}}',
    },
    'fmt_hinweis': {
        'html': _husk_slot(
            f'background-color:{CI_BG};border-left:3px solid {CI_BRAND};'
        ),
        'text': '{{content}}',
    },
    'fmt_trenner': {
        'html': (
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
            f'<tr><td style="padding:{CI_PAD};">'
            f'<hr style="border:0;border-top:1px solid {CI_BORDER};margin:0;">'
            '</td></tr></table>'
        ),
        'text': '---',
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
    {
        'id': 'block_anhaenge',
        'name': 'Anhangsliste',
        'description': 'Dokumentnamen als Aufzählung mit •',
        'module': 'fmt_aufzaehlung',
        'variables': ['anhaenge_liste', 'dokument_1', 'dokument_2', 'dokument_3'],
        'legacy_html_var': '',
        'suggest_when': ['anhang', 'anlage', 'dokument', 'pdf', 'attachment'],
        'paired': False,
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


def is_format_module(module_id: str) -> bool:
    return module_id in FORMAT_MODULE_IDS or module_id.startswith('fmt_')


def module_insert_syntax(module_id: str) -> str:
    """Einfüge-Syntax: innen nur Plaintext / {variablen}, kein HTML."""
    samples = {
        'fmt_aufzaehlung': 'Pferd\nHund\nKatze',
        'fmt_key_value': 'Pferd: 100 €\nHund: 50 €\nKatze: 20 €',
        'fmt_tabelle': 'Tier | Kosten pro Monat\nPferd | 100 €\nHund | 50 €',
        'fmt_zwei_spalten': 'Links\n---\nRechts',
        'fmt_hinweis': 'Kurzer Hinweis an den Empfänger.',
    }
    if module_id == 'fmt_trenner':
        return f'{{{{block:{module_id}}}}}'
    if is_paired_module(module_id):
        sample = samples.get(module_id, 'Inhalt hier\noder {variable}')
        return f'{{{{block:{module_id}}}}}\n{sample}\n{{{{/block}}}}'
    return f'{{{{block:{module_id}}}}}'


def block_insert_syntax(block_id: str) -> str:
    b = get_block(block_id)
    if not b:
        return f'{{{{block:{block_id}}}}}'
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
        'block_anhaenge': 'Anhänge / Dokumente als Aufzählung anzeigen?',
    }.get(b['id'], f'Als Block „{b["name"]}“ einfügen?')


def _suggest_question_en(b: dict[str, Any]) -> str:
    return {
        'block_teilnehmer': 'Show participants as a bullet list?',
        'block_system_status': 'Show system status as a table (Check/Value/Status)?',
        'block_termin': 'Show meeting details (date, time, room) as a list?',
        'block_anhaenge': 'Show attachments / documents as a bullet list?',
    }.get(b['id'], f'Insert as block “{b["name"]}”?')


def _html_to_plain(text: str) -> str:
    """Visual-Editor/<br>/<div>/<ul> → Plaintext-Zeilen für Format-Module."""
    t = text or ''
    t = re.sub(r'(?i)<br\s*/?>', '\n', t)
    t = re.sub(r'(?i)</(p|div|li|tr|h[1-6])\s*>', '\n', t)
    t = re.sub(r'(?i)</td\s*>', '\t', t)
    t = re.sub(r'<[^>]+>', '', t)
    t = html_mod.unescape(t)
    # doppelte Leerzeilen reduzieren
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip()


def _is_our_bullet_table(text: str) -> bool:
    t = text or ''
    low = t.lower()
    return LIST_BULLET in t and '<table' in low and 'role="presentation"' in low


def _is_formatted_data_table(text: str) -> bool:
    low = (text or '').lower()
    return '<table' in low and ('<th' in low or 'border-bottom' in low)


def format_inner_for_module(module_id: str, content: str, *, html: bool = True) -> str:
    """
    MCID Regel 6/9: Inner-Content ist Plaintext + {variablen}.
    Soft-HTML aus dem Visual-Editor (<br>, <div>) wird zu Plaintext normalisiert.
    Format-Module bauen immer CI-konformes HTML (Arial 14px, • bei Listen).
    """
    raw = (content or '').strip()
    if not raw:
        return ''

    # fmt_aufzaehlung: immer • — nie CSS-list-style / nie nacktes <br>
    if module_id == 'fmt_aufzaehlung':
        if html and _is_our_bullet_table(raw):
            return raw
        plain = _html_to_plain(raw) if '<' in raw else raw
        return plain_list_to_html(plain) if html else plain_list_to_text(plain)

    if module_id == 'fmt_key_value':
        if html and '<strong>' in raw.lower() and ('<div' in raw.lower() or '<table' in raw.lower()):
            # schon formatiert — aber Soft-BR davor trotzdem vermeiden
            if '<br' not in raw.lower() or '<strong>' in raw.lower():
                if not re.search(r'(?i)<br\s*/?>', raw) or '<strong>' in raw:
                    # fertiges Key-Value durchreichen nur ohne reines BR-Chaos
                    if '<strong>' in raw:
                        return raw
        plain = _html_to_plain(raw) if '<' in raw else raw
        return key_value_to_html(plain) if html else key_value_to_text(plain)

    if module_id == 'fmt_tabelle':
        if html and _is_formatted_data_table(raw):
            return raw
        plain = _html_to_plain(raw) if '<' in raw else raw
        # Tabs aus </td> → Pipe für Einzeiler-Tabellen
        plain = plain.replace('\t', ' | ')
        return pipe_table_to_html(plain) if html else pipe_table_to_text(plain)

    if module_id == 'fmt_zwei_spalten':
        plain = _html_to_plain(raw) if '<' in raw else raw
        return two_col_to_html(plain) if html else two_col_to_text(plain)

    if module_id == 'fmt_hinweis':
        plain = _html_to_plain(raw) if '<' in raw else raw
        return hint_to_html(plain) if html else plain

    if module_id == 'fmt_trenner':
        return ''  # Hülle selbst enthält den Trenner

    # Unbekanntes Format-Modul
    plain = _html_to_plain(raw) if '<' in raw else raw
    if html:
        return '<br>'.join(
            _esc_keep_vars(line) for line in plain.splitlines() if line.strip()
        )
    return plain


def plain_list_to_html(plain: str) -> str:
    """
    Plaintext → Aufzählung mit festem Bullet ``•``.
    E-Mail-sicher: Tabelle + Zeichen, kein CSS-list-style.
    """
    parts = _list_items(plain)
    if not parts:
        return ''
    rows = ''.join(
        '<tr>'
        f'<td valign="top" style="padding:0 8px {CI_LIST_GAP} 0;width:16px;'
        f'font-family:{CI_FONT};font-size:{CI_SIZE};color:{CI_TEXT};'
        f'line-height:{CI_LINE};">{LIST_BULLET}</td>'
        f'<td valign="top" style="padding:0 0 {CI_LIST_GAP} 0;'
        f'font-family:{CI_FONT};font-size:{CI_SIZE};color:{CI_TEXT};'
        f'line-height:{CI_LINE};">{_esc_keep_vars(p)}</td>'
        '</tr>'
        for p in parts
    )
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        f'style="border-collapse:collapse;margin:0;">{rows}</table>'
    )


def plain_list_to_text(plain: str) -> str:
    parts = _list_items(plain)
    return '\n'.join(f'{LIST_BULLET} {p}' for p in parts)


def key_value_to_html(plain: str) -> str:
    rows = _key_value_rows(plain)
    if not rows:
        return plain_list_to_html(plain)
    trs = ''.join(
        '<tr>'
        f'<td valign="top" style="padding:0 12px {CI_LIST_GAP} 0;'
        f'font-family:{CI_FONT};font-size:{CI_SIZE};color:{CI_TEXT};'
        f'line-height:{CI_LINE};font-weight:bold;">{_esc_keep_vars(lab)}:</td>'
        f'<td valign="top" style="padding:0 0 {CI_LIST_GAP} 0;'
        f'font-family:{CI_FONT};font-size:{CI_SIZE};color:{CI_TEXT};'
        f'line-height:{CI_LINE};">{_esc_keep_vars(val)}</td>'
        '</tr>'
        for lab, val in rows
    )
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        f'style="border-collapse:collapse;margin:0;">{trs}</table>'
    )


def key_value_to_text(plain: str) -> str:
    rows = _key_value_rows(plain)
    if not rows:
        return plain_list_to_text(plain)
    return '\n'.join(f'{lab}: {val}' for lab, val in rows)


def pipe_table_to_html(plain: str) -> str:
    lines = [ln.strip() for ln in (plain or '').splitlines() if ln.strip()]
    # Einzeiler: „A | B C | D E | F“ → Zeilen zu je 2 Spalten
    if len(lines) == 1 and lines[0].count('|') >= 3:
        cells = [c.strip() for c in lines[0].split('|') if c.strip()]
        if len(cells) >= 4 and len(cells) % 2 == 0:
            lines = [
                f'{cells[i]} | {cells[i + 1]}'
                for i in range(0, len(cells), 2)
            ]
    if not lines:
        return ''
    rows = [[c.strip() for c in ln.split('|')] for ln in lines]
    if len(rows) == 1 and len(rows[0]) == 1:
        return plain_list_to_html(plain)
    head, *body = rows
    th = ''.join(
        f'<th align="left" style="padding:6px 8px;border-bottom:1px solid {CI_BORDER};'
        f'font-family:{CI_FONT};font-size:{CI_SIZE_SMALL};color:{CI_TEXT};'
        f'font-weight:bold;">{_esc_keep_vars(c)}</th>'
        for c in head
    )
    trs = [
        '<tr>' + ''.join(
            f'<td style="padding:6px 8px;border-bottom:1px solid {CI_BORDER};'
            f'font-family:{CI_FONT};font-size:{CI_SIZE};color:{CI_TEXT};">'
            f'{_esc_keep_vars(c)}</td>'
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
        f'<td width="50%" valign="top" style="padding:8px 12px 8px 0;{_TD}'
        f'border-right:1px solid {CI_BORDER};">'
        f'{_esc_keep_vars(left).replace(chr(10), "<br>")}</td>'
        f'<td width="50%" valign="top" style="padding:8px 0 8px 12px;{_TD}">'
        f'{_esc_keep_vars(right).replace(chr(10), "<br>")}</td>'
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
        f'<p style="margin:0 0 {CI_LIST_GAP} 0;font-family:{CI_FONT};'
        f'font-size:{CI_SIZE};color:{CI_TEXT};line-height:{CI_LINE};">'
        f'{_esc_keep_vars(p).replace(chr(10), "<br>")}</p>'
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
        s = re.sub(r'^[\-\*\u2022\u25B8•▸·]+\s*', '', s).strip()
        return s

    if '\n' in raw:
        lines = [_clean(ln) for ln in raw.splitlines()]
        return [ln for ln in lines if ln]

    if ';' in raw:
        parts = [_clean(p) for p in raw.split(';')]
        parts = [p for p in parts if p]
        if len(parts) >= 2:
            return parts

    for sep in (r'\s*[·•]\s*', r'\s*,\s+'):
        parts = [_clean(p) for p in re.split(sep, raw)]
        parts = [p for p in parts if p]
        if len(parts) >= 2:
            return parts

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
    return ''.join(
        p if (p.startswith('{') and p.endswith('}')) else _esc(p) for p in parts
    )


def termin_key_value_html(variables: dict) -> str:
    rows = [
        ('Titel', variables.get('title')),
        ('Datum', variables.get('termin_datum')),
        ('Uhrzeit', variables.get('termin_uhrzeit') or variables.get('termin_zeit')),
        ('Raum', variables.get('raum')),
        ('Einwahl', variables.get('einwahl_info')),
    ]
    plain = '\n'.join(f'{lab}: {val}' for lab, val in rows if val)
    return key_value_to_html(plain)


def termin_key_value_text(variables: dict) -> str:
    rows = [
        ('Titel', variables.get('title')),
        ('Datum', variables.get('termin_datum')),
        ('Uhrzeit', variables.get('termin_uhrzeit') or variables.get('termin_zeit')),
        ('Raum', variables.get('raum')),
        ('Einwahl', variables.get('einwahl_info')),
    ]
    return '\n'.join(f'{lab}: {val}' for lab, val in rows if val)
