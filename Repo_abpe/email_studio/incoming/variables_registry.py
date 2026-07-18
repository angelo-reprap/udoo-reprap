"""
Email Studio — Variablen-Katalog für KI-Wizard CONTEXT und Validierung.

Single Source of Truth für Sidebar, VariableListAPI und Wizard-Validierung.
Scope-spezifische Variablen werden ergänzt; User-/System-Variablen gelten überall.
"""
from __future__ import annotations

from typing import Any


_CONTEXT_VARS: list[dict[str, Any]] = [
    {'name': 'name', 'source': 'context', 'type': 'string', 'description': 'Vollständiger Name'},
    {'name': 'first_name', 'source': 'context', 'type': 'string', 'description': 'Vorname'},
    {'name': 'last_name', 'source': 'context', 'type': 'string', 'description': 'Nachname'},
    {'name': 'email', 'source': 'context', 'type': 'string', 'description': 'E-Mail Adresse'},
    {'name': 'cv_link', 'source': 'context', 'type': 'url', 'description': 'CV Direktlink'},
    {'name': 'cv_version', 'source': 'context', 'type': 'string', 'description': 'CV Versionsnummer'},
    {'name': 'created_date', 'source': 'context', 'type': 'date', 'description': 'Erstellungsdatum'},
    {'name': 'task_ref', 'source': 'context', 'type': 'string', 'description': 'Task Referenz'},
    # CTA-Module (cta_blau / cta_gruen) — global verfügbar
    {'name': 'button_url', 'source': 'context', 'type': 'url', 'description': 'Button-Ziel-URL'},
    {'name': 'button_text', 'source': 'context', 'type': 'string', 'description': 'Button-Text'},
]

_USER_VARS: list[dict[str, Any]] = [
    {'name': 'sender_name', 'source': 'user', 'type': 'string', 'description': 'Name des Absenders (User-Profil)'},
    {'name': 'sender_email', 'source': 'user', 'type': 'email', 'description': 'E-Mail des Absenders (User-Profil)'},
    {'name': 'reply_to', 'source': 'user', 'type': 'email', 'description': 'Reply-To Adresse'},
]

_SYSTEM_VARS: list[dict[str, Any]] = [
    {'name': 'portal_url', 'source': 'system', 'type': 'url', 'description': 'Portal URL'},
    {'name': 'date', 'source': 'system', 'type': 'date', 'description': 'Aktuelles Datum'},
    {'name': 'year', 'source': 'system', 'type': 'string', 'description': 'Aktuelles Jahr'},
    {'name': 'subject', 'source': 'template', 'type': 'string', 'description': 'Betreff der E-Mail'},
]

_SCOPE_VARS: dict[str, list[dict[str, Any]]] = {
    'telefon': [
        {'name': 'termin_datum', 'source': 'context', 'type': 'date', 'description': 'Termin-Datum'},
        {'name': 'termin_uhrzeit', 'source': 'context', 'type': 'string', 'description': 'Termin-Uhrzeit'},
        {'name': 'termin_zeit', 'source': 'context', 'type': 'string', 'description': 'Termin-Uhrzeit (alias)'},
        {'name': 'raum', 'source': 'context', 'type': 'string', 'description': 'Raum / Ort'},
        {'name': 'einwahl_info', 'source': 'context', 'type': 'string', 'description': 'Einwahl-Informationen'},
        {'name': 'title', 'source': 'context', 'type': 'string', 'description': 'Termin-Titel'},
        {'name': 'teilnehmer_liste', 'source': 'context', 'type': 'string', 'description': 'Teilnehmer (Plaintext)'},
        {'name': 'teilnehmer_liste_html', 'source': 'context', 'type': 'html', 'description': 'Teilnehmer (HTML)'},
    ],
    'general': [
        {'name': 'vertretung_name', 'source': 'context', 'type': 'string', 'description': 'Name der Vertretung'},
        {'name': 'vertretung_email', 'source': 'context', 'type': 'email', 'description': 'E-Mail der Vertretung'},
        {'name': 'vertretung_telefon', 'source': 'context', 'type': 'string', 'description': 'Telefon der Vertretung'},
        {'name': 'mobil_nummer', 'source': 'context', 'type': 'string', 'description': 'Mobilnummer'},
        {'name': 'abwesenheit_von', 'source': 'context', 'type': 'date', 'description': 'Abwesenheit von'},
        {'name': 'abwesenheit_bis', 'source': 'context', 'type': 'date', 'description': 'Abwesenheit bis'},
        {'name': 'firma', 'source': 'context', 'type': 'string', 'description': 'Firma / Unternehmen'},
        {'name': 'unternehmen', 'source': 'context', 'type': 'string', 'description': 'Unternehmen (alias)'},
        {'name': 'berater_anzahl', 'source': 'context', 'type': 'string', 'description': 'Anzahl Berater (CRM)'},
        {'name': 'body', 'source': 'context', 'type': 'html', 'description': 'Freitext-Body (manuelle CRM-Mail)'},
    ],
    'matching': [
        {'name': 'berater_name', 'source': 'context', 'type': 'string', 'description': 'Berater-Name'},
        {'name': 'kandidat_name', 'source': 'context', 'type': 'string', 'description': 'Kandidaten-Name'},
        {'name': 'firma', 'source': 'context', 'type': 'string', 'description': 'Firma des Kandidaten'},
    ],
    'intake': [
        {'name': 'cv_link', 'source': 'context', 'type': 'url', 'description': 'CV Upload Link'},
        {'name': 'cv_version', 'source': 'context', 'type': 'string', 'description': 'CV Version'},
        {'name': 'aid', 'source': 'context', 'type': 'string', 'description': 'AID / Profil-ID'},
        {'name': 'email_id', 'source': 'context', 'type': 'string', 'description': 'E-Mail / Import-ID'},
        {'name': 'error_code', 'source': 'context', 'type': 'string', 'description': 'Fehlercode'},
        {'name': 'error_detail', 'source': 'context', 'type': 'string', 'description': 'Fehlerdetail'},
        {'name': 'import_time', 'source': 'context', 'type': 'string', 'description': 'Import-Zeitpunkt'},
        {'name': 'original_subject', 'source': 'context', 'type': 'string', 'description': 'Original-Betreff'},
        {'name': 'solution', 'source': 'context', 'type': 'string', 'description': 'Lösungsvorschlag'},
        {'name': 'attachment_count', 'source': 'context', 'type': 'string', 'description': 'Anzahl Anhänge'},
        {'name': 'de_editor_url', 'source': 'context', 'type': 'url', 'description': 'DE Editor URL'},
        {'name': 'de_html_url', 'source': 'context', 'type': 'url', 'description': 'DE HTML URL'},
        {'name': 'en_html_url', 'source': 'context', 'type': 'url', 'description': 'EN HTML URL'},
        {'name': 'duration', 'source': 'context', 'type': 'string', 'description': 'Verarbeitungszeit (Sekunden)'},
        {'name': 'projects', 'source': 'context', 'type': 'string', 'description': 'Projekte (Kurz)'},
        {'name': 'skills', 'source': 'context', 'type': 'string', 'description': 'Skills (Kurz)'},
    ],
    'portal': [
        {'name': 'portal_url', 'source': 'system', 'type': 'url', 'description': 'Portal URL'},
        {'name': 'button_url', 'source': 'context', 'type': 'url', 'description': 'Button-Ziel-URL'},
        {'name': 'button_text', 'source': 'context', 'type': 'string', 'description': 'Button-Text'},
    ],
}


def _resolve_scopes(app_scope: str, identifier: str | None) -> list[str]:
    """Scope + Heuristik: meetme_* Identifier → Telefon-Variablen auch bei anderem app_scope."""
    scope = (app_scope or 'general').strip() or 'general'
    scopes = [scope]
    ident = (identifier or '').strip().lower()
    if ident.startswith('meetme_') and 'telefon' not in scopes:
        scopes.append('telefon')
    if ident.startswith(('cv_', 'upload_', 'pipeline_')) and 'intake' not in scopes:
        scopes.append('intake')
    if ident.startswith('crm_') and 'general' not in scopes:
        scopes.append('general')
    return scopes


def get_variables(app_scope: str = 'general', identifier: str | None = None) -> list[dict[str, Any]]:
    """Variablen für KI-Wizard CONTEXT / Validierung (scope + global)."""
    merged: dict[str, dict[str, Any]] = {}
    rows = list(_CONTEXT_VARS + _USER_VARS + _SYSTEM_VARS)
    for scope in _resolve_scopes(app_scope, identifier):
        rows.extend(_SCOPE_VARS.get(scope, []))
    for row in rows:
        merged[row['name']] = row
    return list(merged.values())


def get_allowed_var_names(app_scope: str = 'general', identifier: str | None = None) -> set[str]:
    return {v['name'] for v in get_variables(app_scope, identifier)}


def _sidebar_item(row: dict[str, Any]) -> dict[str, str]:
    return {
        'name': row['name'],
        'description': row.get('description', ''),
    }


def get_sidebar_variable_groups(
    app_scope: str = 'general',
    identifier: str | None = None,
) -> dict[str, list[dict[str, str]]]:
    """
    Variablen-Gruppen für Email Studio Sidebar.

    Keys: context, user, system, scope
    """
    scope = (app_scope or 'general').strip() or 'general'
    variables = get_variables(scope, identifier)

    base_context = {v['name'] for v in _CONTEXT_VARS}
    base_user = {v['name'] for v in _USER_VARS}
    base_system = {v['name'] for v in _SYSTEM_VARS}
    scope_names: set[str] = set()
    for s in _resolve_scopes(scope, identifier):
        scope_names |= {v['name'] for v in _SCOPE_VARS.get(s, [])}

    groups: dict[str, list[dict[str, str]]] = {
        'context': [],
        'user': [],
        'system': [],
        'scope': [],
    }

    seen: set[str] = set()
    for row in variables:
        name = row['name']
        if name in seen:
            continue
        seen.add(name)
        item = _sidebar_item(row)
        source = row.get('source', 'context')

        if name in scope_names and name not in base_context:
            groups['scope'].append(item)
        elif source == 'user' or name in base_user:
            groups['user'].append(item)
        elif source in ('system', 'template') or name in base_system:
            groups['system'].append(item)
        elif name in base_context or source == 'context':
            groups['context'].append(item)
        else:
            groups['scope'].append(item)

    return groups


def variable_count(app_scope: str = 'general', identifier: str | None = None) -> int:
    """Anzahl verfügbarer Variablen (Sidebar-Badge)."""
    return len(get_variables(app_scope, identifier))
