"""
Matching-Anfrage aus E-Mail extrahieren.

Prompt kommt aus WizardPrompt (DB), Key: wiz_matching_anfrage_generate.
DeepSeek only — kein Ollama.
"""
from __future__ import annotations

import logging
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
        parts.append(f'Äußerer Absender: {outer_from}')
    if subject or outer_from:
        parts.append('')
    parts.append('E-Mail-Inhalt:')
    parts.append(email_text or '')
    return '\n'.join(parts)


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
        return {
            'success': False,
            'error': ds.error or 'DeepSeek Extraktion fehlgeschlagen',
            'extract': fallback,
            'fields': applied.get('fields') or map_extract_to_form_fields(fallback),
            'prompt_key': PROMPT_KEY,
            'source': 'rules',
        }

    try:
        extract = parse_ai_json(ds.text)
    except ValueError as exc:
        log.warning('Matching-Anfrage JSON parse failed: %s', exc)
        fallback = provider.generate_fallback(text)
        applied = provider.apply_result(fallback)
        return {
            'success': False,
            'error': f'KI-Antwort kein gültiges JSON: {exc}',
            'raw': (ds.text or '')[:2000],
            'extract': fallback,
            'fields': applied.get('fields') or map_extract_to_form_fields(fallback),
            'prompt_key': PROMPT_KEY,
            'source': 'rules',
        }

    extract['source'] = 'ai'
    validation = provider.validate_output(extract)
    applied = provider.apply_result(extract)
    return {
        'success': True,
        'extract': extract,
        'fields': applied.get('fields') or map_extract_to_form_fields(extract),
        'validation': {
            'ok': validation.ok,
            'errors': validation.errors,
            'warnings': validation.warnings,
        },
        'prompt_key': PROMPT_KEY,
        'source': 'ai',
    }
