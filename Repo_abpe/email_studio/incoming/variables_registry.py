"""
Zentrale Registry aller Email-Studio-Platzhalter.

Sidebar-Gruppen + KI-Wizard CONTEXT / Validierung.
MeetMe-Quelle: apps.abpe_meetme.email_helpers.build_meetme_variables()
"""
from __future__ import annotations

from typing import Any

# app_scope-Werte, unter denen MeetMe-Variablen angezeigt werden
MEETME_SCOPES = frozenset({'telefon', 'meetme'})

# Reihenfolge der Sidebar-Gruppen
GROUP_ORDER = ('context', 'meetme', 'scope', 'user', 'system', 'status', 'module')

GROUP_META: dict[str, dict[str, str]] = {
    'context': {'label': 'Aus Kontext', 'label_i18n': 'es.vars_context', 'chip_class': 'context'},
    'meetme':  {'label': 'MeetMe / Telefon', 'label_i18n': 'es.vars_meetme', 'chip_class': 'meetme'},
    'scope':   {'label': 'App-Bereich', 'label_i18n': 'es.vars_scope', 'chip_class': 'scope'},
    'user':    {'label': 'Benutzerprofil', 'label_i18n': 'es.vars_user', 'chip_class': 'user'},
    'system':  {'label': 'System', 'label_i18n': 'es.vars_system', 'chip_class': 'system'},
    'status':  {'label': 'System-Status', 'label_i18n': 'es.vars_status', 'chip_class': 'status'},
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

    # ── App-Bereich (scope-spezifisch) ────────────────────────────────────
    _v('vertretung_name', 'scope', 'Name der Vertretung', 'Tanja Groß',
       scopes=['general']),
    _v('vertretung_email', 'scope', 'E-Mail der Vertretung', 'tanja@abcona.de', 'email',
       scopes=['general']),
    _v('vertretung_telefon', 'scope', 'Telefon der Vertretung', '+49 6171 …',
       scopes=['general']),
    _v('mobil_nummer', 'scope', 'Mobilnummer', '+49 170 …',
       scopes=['general']),
    _v('abwesenheit_von', 'scope', 'Abwesenheit von', '20.07.2026', 'date',
       scopes=['general']),
    _v('abwesenheit_bis', 'scope', 'Abwesenheit bis', '01.08.2026', 'date',
       scopes=['general']),
    _v('firma', 'scope', 'Firma / Unternehmen', 'Muster GmbH',
       scopes=['general', 'matching']),
    _v('unternehmen', 'scope', 'Unternehmen (Alias)', 'Muster GmbH',
       scopes=['general']),
    _v('berater_name', 'scope', 'Name des Beraters (Matching)', 'Tanja Groß',
       scopes=['matching']),
    _v('kandidat_name', 'scope', 'Name des Kandidaten (Matching)', 'Max Mustermann',
       scopes=['matching']),

    # ── MeetMe / Telefon (immer in Sidebar; Kontext füllt Werte bei MeetMe-Mails) ──
    _v('title', 'meetme', 'Titel / Betreff des Termins (Überschrift)', 'Kurze Abstimmung'),
    _v('termin_datum', 'meetme', 'Termin-Datum formatiert', 'Montag, der 15.07.2026', 'date'),
    _v('termin_uhrzeit', 'meetme', 'Termin-Uhrzeit formatiert', '14:00 Uhr'),
    _v('termin_zeit', 'meetme', 'Alias für termin_uhrzeit (Vorschau/Legacy)', '14:00 Uhr'),
    _v('raum', 'meetme', 'Konferenzraum-Durchwahl', '035'),
    _v('einwahl_info', 'meetme', 'Einwahlnummer und PIN', 'Einwahl: 06171 8867035, PIN: 0350'),
    _v('teilnehmer_liste', 'meetme', 'Teilnehmer als Textliste (Plaintext)', 'Max M., +49…'),
    _v('teilnehmer_liste_html', 'meetme', 'Teilnehmer als HTML (z. B. mit <br>)',
       '<ul><li>Max Mustermann</li></ul>'),

    # ── User-Profil ───────────────────────────────────────────────────────
    _v('sender_name', 'user', 'Name des Absenders (eingeloggter User)', 'Angelo Malaguarnera'),
    _v('sender_email', 'user', 'E-Mail des Absenders', 'angelo@abcona.de', 'email'),
    _v('reply_to', 'user', 'Reply-To-Adresse', 'angelo@abcona.de', 'email'),

    # ── System ────────────────────────────────────────────────────────────
    _v('portal_url', 'system', 'Portal-URL', 'https://abpe.win.abcona.info', 'url'),
    _v('date', 'system', 'Aktuelles Datum', '15.07.2026', 'date'),
    _v('year', 'system', 'Aktuelles Jahr', '2026'),
    _v('subject', 'system', 'Betreff der Vorlage', 'Kurze Abstimmung am …'),

    # ── System-Status (Live-Snapshot: Disk, Django, DB, Celery, Scheduler) ─
    _v('disk_free', 'status', 'Freier Speicherplatz auf dem Server', '12.4 GB'),
    _v('disk_used_pct', 'status', 'Belegter Speicherplatz in Prozent', '67%'),
    _v('django_ok', 'status', 'Django-App erreichbar (OK/FAIL)', 'OK'),
    _v('db_ok', 'status', 'Datenbank erreichbar (OK/FAIL)', 'OK'),
    _v('celery_ok', 'status', 'Celery-Worker erreichbar (OK/FAIL)', 'OK'),
    _v('scheduler_ok', 'status', 'Celery-Beat/Scheduler aktiv (OK/WARN/FAIL)', 'OK'),
    _v('system_status', 'status', 'Gesamtstatus (aggregiert)', 'OK'),
    _v('system_status_list', 'status',
       'Statusliste als mehrzeiliger Text (Disk, Django, DB, Celery, Scheduler)',
       'Disk frei: 12.4 GB …'),

    # ── Module (CTA-Blöcke) ───────────────────────────────────────────────
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
    return False


def get_variables(
    app_scope: str | None = None,
    template_identifier: str | None = None,
) -> list[dict[str, Any]]:
    """Flache Liste für API / KI-Wizard CONTEXT."""
    return [
        v for v in ALL_VARIABLES
        if _variable_visible(v, app_scope, template_identifier)
    ]


def get_allowed_var_names(
    app_scope: str | None = None,
    template_identifier: str | None = None,
) -> set[str]:
    return {v['name'] for v in get_variables(app_scope, template_identifier)}


def get_sidebar_variable_groups(
    app_scope: str | None = None,
    template_identifier: str | None = None,
) -> list[dict[str, Any]]:
    """Gruppierte Liste für Sidebar-Template (Accordion pro Sektor)."""
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
    """Anzahl verfügbarer Variablen (Sidebar-Badge)."""
    return len(get_variables(app_scope, template_identifier))
