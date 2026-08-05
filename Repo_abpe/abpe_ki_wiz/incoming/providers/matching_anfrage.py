"""Matching — KI-Anfragen-Wizard (E-Mail → Formularfelder)."""
from __future__ import annotations

import logging
from typing import Any

from apps.abpe_ki_wiz.providers.base import ValidationResult, WizardDomainProvider
from apps.abpe_ki_wiz.registry import register

log = logging.getLogger('abpe_ki_wiz.matching_anfrage')

PROMPT_KEY = 'wiz_matching_anfrage_generate'

_REQUIRED_TOP_KEYS = (
    'kunde', 'ansprechpartner', 'weiterleitung', 'titel', 'beschreibung',
    'start', 'dauer_monate', 'standort', 'remote', 'stundensatz_max',
    'skills', 'hinweise',
)


class MatchingAnfrageWizardProvider(WizardDomainProvider):
    wizard_id = 'matching_anfrage'
    title = 'KI-Anfragen-Wizard (Matching)'
    description = (
        'Extrahiert Kundendaten und Anfrage-Details aus E-Mail-Text '
        'für das Matching-Formular „Neue Anfrage“ (DeepSeek, Prompt aus DB).'
    )

    def get_catalog(self, **kwargs) -> dict[str, Any]:
        return {
            'target': 'matching_neu',
            'prompt_key': PROMPT_KEY,
            'fields': [
                'kunde', 'ansprechpartner', 'weiterleitung',
                'titel', 'beschreibung', 'start', 'dauer_monate',
                'standort', 'remote', 'stundensatz_max', 'skills', 'hinweise',
            ],
            'form_map': {
                'kunde.name': 'new-customer',
                'ansprechpartner.name': 'new-contact',
                'titel': 'new-title',
                'beschreibung': 'new-description',
                'start.datum': 'new-start',
                'dauer_monate': 'new-duration',
                'standort': 'new-location',
                'stundensatz_max': 'new-rate-max',
            },
        }

    def get_question_catalog(self) -> list[dict[str, Any]]:
        # Ein-Schritt-Extraktion — keine Klärfragen-Runde nötig
        return []

    def resolve_questions(
        self,
        briefing: str,
        answers: dict[str, Any] | None = None,
        analyze_result: dict[str, Any] | None = None,
    ) -> list[str]:
        return []

    def build_checklist(self, answers: dict[str, Any]) -> list[str]:
        return [
            'Nur Fakten aus dem E-Mail-Text',
            'Weiterleitungen: Kunde/AP aus innerem Teil',
            'Nur JSON, kein Markdown',
            'stundensatz_max nur bei klarem Kundenbudget',
        ]

    def validate_output(self, result: dict[str, Any]) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        if not isinstance(result, dict):
            return ValidationResult(ok=False, errors=['Ergebnis ist kein Objekt'])
        for key in _REQUIRED_TOP_KEYS:
            if key not in result:
                warnings.append(f'Fehlender Key: {key}')
        kunde = result.get('kunde')
        if kunde is not None and not isinstance(kunde, dict):
            errors.append('kunde muss Objekt sein')
        start = result.get('start')
        if start is not None and not isinstance(start, dict):
            errors.append('start muss Objekt sein')
        skills = result.get('skills')
        if skills is not None and not isinstance(skills, list):
            errors.append('skills muss Array sein')
        return ValidationResult(ok=not errors, errors=errors, warnings=warnings)

    def apply_result(
        self,
        result: dict[str, Any],
        session_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Mappt Extrakt auf Matching-Formularfelder."""
        fields = map_extract_to_form_fields(result)
        return {
            'target': 'matching_neu',
            'extract': result,
            'fields': fields,
            'validation': result.get('validation'),
        }

    def generate_fallback(
        self,
        briefing: str,
        answers: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Minimaler Fallback ohne KI — leeres Schema + Rohtext."""
        text = (briefing or '').strip()
        return {
            'kunde': {'name': None, 'email_domain': None, 'confidence': 0.0},
            'ansprechpartner': {'name': None, 'email': None, 'phone': None, 'confidence': 0.0},
            'weiterleitung': {'ja': False, 'von': None, 'email': None},
            'titel': None,
            'beschreibung': text[:4000] if text else None,
            'start': {'asap': False, 'datum': None},
            'dauer_monate': None,
            'standort': None,
            'remote': None,
            'stundensatz_max': None,
            'skills': [],
            'hinweise': ['KI-Extraktion fehlgeschlagen — Rohtext übernommen'],
            'source': 'rules',
        }


def map_extract_to_form_fields(extract: dict[str, Any] | None) -> dict[str, Any]:
    """Extrakt-JSON → Matching create/form Payload."""
    from datetime import date

    data = extract if isinstance(extract, dict) else {}
    kunde = data.get('kunde') if isinstance(data.get('kunde'), dict) else {}
    ap = data.get('ansprechpartner') if isinstance(data.get('ansprechpartner'), dict) else {}
    start = data.get('start') if isinstance(data.get('start'), dict) else {}
    wl = data.get('weiterleitung') if isinstance(data.get('weiterleitung'), dict) else {}

    location = data.get('standort')
    if data.get('remote') is True:
        loc = (location or '').strip()
        if loc and 'remote' not in loc.lower():
            location = f'{loc} / Remote'
        elif not loc:
            location = 'Remote'

    description = data.get('beschreibung') or ''
    hinweise = data.get('hinweise') if isinstance(data.get('hinweise'), list) else []
    skills = data.get('skills') if isinstance(data.get('skills'), list) else []
    notes: list[str] = []
    if wl.get('ja') and (wl.get('von') or wl.get('email')):
        notes.append(
            'Weiterleitung von: '
            + ', '.join(x for x in [wl.get('von'), wl.get('email')] if x)
        )
    start_asap = bool(start.get('asap'))
    start_date = start.get('datum') or None
    # Kein konkretes Datum + asap → Formular-Default = heute („sofort“)
    if not start_date and start_asap:
        start_date = date.today().isoformat()
        notes.append('Start: asap / ab sofort (Formular: heutiges Datum)')
    elif start_asap and start_date:
        notes.append(f'Start: asap / ab sofort ({start_date})')
    for h in hinweise:
        if h and str(h) not in notes:
            notes.append(str(h))
    if skills:
        notes.append('Skills: ' + ', '.join(str(s) for s in skills[:20] if s))

    if notes:
        block = '\n'.join(f'• {n}' for n in notes)
        description = (description.rstrip() + '\n\n---\n' + block).strip() if description else block

    dauer = data.get('dauer_monate')
    try:
        dauer_int = int(dauer) if dauer is not None else None
    except (TypeError, ValueError):
        dauer_int = None

    rate = data.get('stundensatz_max')
    try:
        rate_int = int(rate) if rate is not None else None
    except (TypeError, ValueError):
        rate_int = None

    return {
        'customer_name': kunde.get('name') or '',
        'contact_name': ap.get('name') or '',
        'contact_email': ap.get('email') or '',
        'contact_phone': ap.get('phone') or ap.get('telefon') or '',
        'title': data.get('titel') or '',
        'description': description,
        'start_date': start_date,
        'start_asap': start_asap,
        'duration_months': dauer_int,
        'location': location or '',
        'rate_max': rate_int,
        'skills': skills,
        'hinweise': hinweise,
        'weiterleitung': wl,
        'kunde_email_domain': kunde.get('email_domain') or '',
    }


def register_matching_anfrage_provider() -> None:
    register(MatchingAnfrageWizardProvider())
