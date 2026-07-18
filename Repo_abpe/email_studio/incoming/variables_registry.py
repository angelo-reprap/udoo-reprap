"""
Zentrale Registry aller Email-Studio-Platzhalter.

Quelle MeetMe: apps.abpe_meetme.email_helpers.build_meetme_variables()
"""

from __future__ import annotations

from typing import Any

# app_scope-Werte, unter denen MeetMe-Variablen angezeigt werden
MEETME_SCOPES = frozenset({'telefon', 'meetme'})

# Reihenfolge der Sidebar-Gruppen
GROUP_ORDER = ('context', 'meetme', 'user', 'system', 'module')

GROUP_META: dict[str, dict[str, str]] = {
    'context': {'label': 'Aus Kontext', 'label_i18n': 'es.vars_context', 'chip_class': 'context'},
    'meetme':  {'label': 'MeetMe / Telefon', 'label_i18n': 'es.vars_meetme', 'chip_class': 'meetme'},
    'user':    {'label': 'Benutzerprofil', 'label_i18n': 'es.vars_user', 'chip_class': 'user'},
    'system':  {'label': 'System', 'label_i18n': 'es.vars_system', 'chip_class': 'system'},
    'module':  {'label': 'Module', 'label_i18n': 'es.vars_module', 'chip_class': 'module'},
}


def _v(
    name: str,
    source: str,
    description: str,
    example: str = '',
    type_: str = 'string',
    scopes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        'name': name,
        'source': source,
        'type': type_,
        'description': description,
        'example': example,
        'scopes': scopes or ['*'],
    }


# scopes: ['*'] = immer; sonst nur bei passendem app_scope / meetme_-Identifier
ALL_VARIABLES: list[dict[str, Any]] = [
    # ── Allgemein / Kontext ───────────────────────────────────────────────
    _v('name', 'context', 'Vollständiger Name des Empfängers', 'Max Mustermann'),
    _v('first_name', 'context', 'Vorname', 'Max'),
    _v('last_name', 'context', 'Nachname', 'Mustermann'),
    _v('email', 'context', 'E-Mail-Adresse des Empfängers', 'max@example.de'),
    _v('cv_link', 'context', 'Direktlink zum CV', 'https://…/cv/…', 'url',
       ['intake', 'matching', 'workflow', 'general']),
    _v('cv_version', 'context', 'CV-Versionsnummer', 'v3',
       scopes=['intake', 'matching', 'workflow', 'general']),
    _v('created_date', 'context', 'Erstellungsdatum', '15.07.2026', 'date'),
    _v('task_ref', 'context', 'Task- oder Vorgangsreferenz', 'TASK-4711'),
    _v('berater_name', 'context', 'Name des Beraters (Matching)', 'Tanja Groß',
       scopes=['matching']),
    _v('kandidat_name', 'context', 'Name des Kandidaten (Matching)', 'Max Mustermann',
       scopes=['matching']),

    # ── MeetMe / Telefon (build_meetme_variables) ─────────────────────────
    _v('title', 'meetme', 'Titel / Betreff des Termins (Überschrift)', 'Kurze Abstimmung',
       scopes=['telefon', 'meetme']),
    _v('termin_datum', 'meetme', 'Termin-Datum formatiert', 'Montag, der 15.07.2026',
       scopes=['telefon', 'meetme']),
    _v('termin_uhrzeit', 'meetme', 'Termin-Uhrzeit formatiert', '14:00 Uhr',
       scopes=['telefon', 'meetme']),
    _v('termin_zeit', 'meetme', 'Alias für termin_uhrzeit (Vorschau/Legacy)', '14:00 Uhr',
       scopes=['telefon', 'meetme']),
    _v('raum', 'meetme', 'Konferenzraum-Durchwahl', '035',
       scopes=['telefon', 'meetme']),
    _v('einwahl_info', 'meetme', 'Einwahlnummer und PIN', 'Einwahl: 06171 8867035, PIN: 0350',
       scopes=['telefon', 'meetme']),
    _v('teilnehmer_liste', 'meetme', 'Teilnehmer als Textliste (Plaintext)', 'Max M., +49…',
       scopes=['telefon', 'meetme']),
    _v('teilnehmer_liste_html', 'meetme', 'Teilnehmer als HTML (z. B. mit <br>)',
       '<ul><li>Max Mustermann</li></ul>', scopes=['telefon', 'meetme']),

    # ── User-Profil (automatisch) ───────────────────────────────────────────
    _v('sender_name', 'user', 'Name des Absenders (eingeloggter User)', 'Angelo Malagò'),
    _v('sender_email', 'user', 'E-Mail des Absenders', 'angelo@abcona.de', 'email'),
    _v('reply_to', 'user', 'Reply-To-Adresse', 'angelo@abcona.de', 'email'),

    # ── System ──────────────────────────────────────────────────────────────
    _v('portal_url', 'system', 'Portal-URL', 'https://abpe.win.abcona.info', 'url'),
    _v('date', 'system', 'Aktuelles Datum', '15.07.2026', 'date'),
    _v('year', 'system', 'Aktuelles Jahr', '2026'),
    _v('subject', 'system', 'Betreff der Vorlage', 'Kurze Abstimmung am …'),

    # ── Module (CTA-Blöcke) ─────────────────────────────────────────────────
    _v('button_text', 'module', 'Button-Beschriftung in CTA-Modulen', 'Zum Portal'),
    _v('button_url', 'module', 'Button-Ziel-URL in CTA-Modulen',
       'https://abpe.win.abcona.info', 'url'),
]


def _is_meetme_context(app_scope: str | None, template_identifier: str | None) -> bool:
    scope = (app_scope or '').lower()
    ident = (template_identifier or '').lower()
    return scope in MEETME_SCOPES or ident.startswith('meetme_')


def _variable_visible(
    var: dict[str, Any],
    app_scope: str | None,
    template_identifier: str | None,
) -> bool:
    scopes = var.get('scopes') or ['*']
    if '*' in scopes:
        return True
    scope = (app_scope or 'general').lower()
    if scope in scopes:
        return True
    if _is_meetme_context(app_scope, template_identifier):
        if 'meetme' in scopes or 'telefon' in scopes:
            return True
    ident = (template_identifier or '').lower()
    if ident.startswith('meetme_') and any(s in scopes for s in ('meetme', 'telefon')):
        return True
    return False


def get_variables(
    app_scope: str | None = None,
    template_identifier: str | None = None,
) -> list[dict[str, Any]]:
    """Flache Liste für API."""
    return [
        v for v in ALL_VARIABLES
        if _variable_visible(v, app_scope, template_identifier)
    ]


def get_sidebar_variable_groups(
    app_scope: str | None = None,
    template_identifier: str | None = None,
) -> list[dict[str, Any]]:
    """Gruppierte Liste für Sidebar-Template."""
    visible = get_variables(app_scope, template_identifier)
    by_source: dict[str, list[dict[str, Any]]] = {k: [] for k in GROUP_ORDER}
    for v in visible:
        src = v['source']
        if src not in by_source:
            by_source[src] = []
        by_source[src].append(v)

    groups = []
    for key in GROUP_ORDER:
        vars_ = by_source.get(key) or []
        if not vars_:
            continue
        meta = GROUP_META.get(key, {'label': key, 'label_i18n': '', 'chip_class': key})
        groups.append({
            'key': key,
            'label': meta['label'],
            'label_i18n': meta['label_i18n'],
            'chip_class': meta['chip_class'],
            'vars': vars_,
        })
    return groups


def variable_count(
    app_scope: str | None = None,
    template_identifier: str | None = None,
) -> int:
    return len(get_variables(app_scope, template_identifier))
