"""
Matching-Anfrage aus E-Mail extrahieren.

Prompt kommt aus WizardPrompt (DB), Key: wiz_matching_anfrage_generate.
DeepSeek only — kein Ollama.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

from apps.abpe_ki_wiz.providers.matching_anfrage import (
    PROMPT_KEY,
    MatchingAnfrageWizardProvider,
    map_extract_to_form_fields,
)
from apps.abpe_ki_wiz.services.deepseek_client import call_wizard_prompt
from apps.abpe_ki_wiz.services.json_utils import parse_ai_json
from apps.abpe_ki_wiz.services.prompt_loader import get_prompt_by_key

log = logging.getLogger('abpe_ki_wiz.matching_anfrage_extract')


def build_user_email_payload(
    email_text: str,
    *,
    subject: str = '',
    outer_from: str = '',
) -> str:
    parts = [
        'Extrahiere Matching-Anfrage als JSON.',
        '',
    ]
    if subject:
        parts.append(f'Betreff: {subject}')
    if outer_from:
        parts.append(
            f'Weiterleitung von / äußerer Absender (nicht der Auftraggeber): {outer_from}'
        )
    if subject or outer_from:
        parts.append('')
    parts.append('E-Mail-Inhalt:')
    parts.append(email_text or '')
    return '\n'.join(parts)


def _fold(s: str) -> str:
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()


def _name_parts(s: str) -> list[str]:
    return [p for p in _fold(s).split() if p]


def _confident_contact(m: dict[str, Any], name: str, email: str) -> bool:
    """Nur sichere Treffer — verhindert Fuzzy „Treder“→„Teufel“."""
    m_email = (m.get('email') or '').strip().lower()
    if email and m_email and m_email == email.lower().strip():
        return True
    want = _name_parts(name)
    got = _name_parts(m.get('full_name') or '')
    if not want or not got:
        return False
    # Nachname muss exakt matchen
    if want[-1] != got[-1]:
        return False
    # Vorname wenn vorhanden ebenfalls
    if len(want) >= 2 and len(got) >= 2 and want[0] != got[0]:
        return False
    return True


def resolve_crm_suggestions(fields: dict[str, Any]) -> dict[str, Any]:
    """
    Prüft SuiteCRM auf Firma/Ansprechpartner.
    Nur sichere Treffer (E-Mail exakt oder Vor+Nachname) — keine Fuzzy-Falschzuordnung.
    """
    out: dict[str, Any] = {
        'account_matches': [],
        'contact_matches': [],
        'contact_missing': False,
        'suggest_create_contact': False,
        'contact_needs_email_or_phone': False,
        'contact_match_confidence': 'none',
    }
    try:
        from apps.abpe_ki_wiz.services.context_fetcher import (
            search_crm_accounts,
            search_crm_contacts,
        )
    except Exception as exc:
        log.warning('CRM-Lookup nicht verfügbar: %s', exc)
        return out

    customer = (fields.get('customer_name') or '').strip()
    contact = (fields.get('contact_name') or '').strip()
    email = (fields.get('contact_email') or '').strip()
    phone = (fields.get('contact_phone') or '').strip()

    if customer:
        try:
            accounts = search_crm_accounts(customer, limit=8) or []
            cust_f = _fold(customer)
            exact_acc = [a for a in accounts if _fold(a.get('name') or '') == cust_f]
            out['account_matches'] = exact_acc or accounts
        except Exception as exc:
            log.warning('Account-Suche fehlgeschlagen: %s', exc)

    raw: list[dict[str, Any]] = []
    if email:
        try:
            raw = search_crm_contacts(email, limit=8) or []
        except Exception as exc:
            log.warning('Kontakt-Suche (E-Mail) fehlgeschlagen: %s', exc)
    if contact:
        try:
            by_name = search_crm_contacts(contact, limit=8) or []
            seen = {m.get('crm_id') for m in raw}
            for m in by_name:
                if m.get('crm_id') not in seen:
                    raw.append(m)
        except Exception as exc:
            log.warning('Kontakt-Suche (Name) fehlgeschlagen: %s', exc)

    confident = [m for m in raw if _confident_contact(m, contact, email)]
    if email:
        email_l = email.lower()
        confident.sort(
            key=lambda m: 0 if (m.get('email') or '').lower() == email_l else 1,
        )

    out['contact_matches'] = confident
    if confident:
        out['contact_match_confidence'] = (
            'email' if email and any(
                (m.get('email') or '').lower() == email.lower() for m in confident
            ) else 'name'
        )
        out['contact_missing'] = False
    else:
        out['contact_missing'] = bool(contact)
        out['contact_match_confidence'] = 'none'

    has_reach = bool(email or phone)
    out['contact_needs_email_or_phone'] = bool(contact) and not has_reach
    out['suggest_create_contact'] = (
        out['contact_missing'] and bool(contact) and has_reach
    )
    return out


def extract_matching_anfrage(
    email_text: str,
    *,
    subject: str = '',
    outer_from: str = '',
) -> dict[str, Any]:
    """
    Lädt Prompt aus DB, ruft DeepSeek, liefert Extrakt + Formularfelder.
    """
    text = (email_text or '').strip()
    if len(text) < 20:
        return {'success': False, 'error': 'E-Mail-Text zu kurz (min. 20 Zeichen)'}

    prompt = get_prompt_by_key(PROMPT_KEY)
    if not prompt:
        return {
            'success': False,
            'error': (
                f'Prompt „{PROMPT_KEY}“ nicht in DB. '
                'Bitte: python manage.py sync_wizard_prompts --wizard-id matching_anfrage'
            ),
        }

    briefing = build_user_email_payload(text, subject=subject, outer_from=outer_from)
    ds = call_wizard_prompt(prompt, briefing=briefing)

    provider = MatchingAnfrageWizardProvider()
    if not ds.success or not ds.text:
        fallback = provider.generate_fallback(text)
        applied = provider.apply_result(fallback)
        fields = applied.get('fields') or map_extract_to_form_fields(fallback)
        return {
            'success': False,
            'error': ds.error or 'DeepSeek Extraktion fehlgeschlagen',
            'extract': fallback,
            'fields': fields,
            'crm': resolve_crm_suggestions(fields),
            'prompt_key': PROMPT_KEY,
            'source': 'rules',
        }

    try:
        extract = parse_ai_json(ds.text)
    except ValueError as exc:
        log.warning('Matching-Anfrage JSON parse failed: %s', exc)
        fallback = provider.generate_fallback(text)
        applied = provider.apply_result(fallback)
        fields = applied.get('fields') or map_extract_to_form_fields(fallback)
        return {
            'success': False,
            'error': f'KI-Antwort kein gültiges JSON: {exc}',
            'raw': (ds.text or '')[:2000],
            'extract': fallback,
            'fields': fields,
            'crm': resolve_crm_suggestions(fields),
            'prompt_key': PROMPT_KEY,
            'source': 'rules',
        }

    extract['source'] = 'ai'
    validation = provider.validate_output(extract)
    applied = provider.apply_result(extract)
    fields = applied.get('fields') or map_extract_to_form_fields(extract)
    crm = resolve_crm_suggestions(fields)
    return {
        'success': True,
        'extract': extract,
        'fields': fields,
        'crm': crm,
        'validation': {
            'ok': validation.ok,
            'errors': validation.errors,
            'warnings': validation.warnings,
        },
        'prompt_key': PROMPT_KEY,
        'source': 'ai',
    }
