"""
Wizard-Orchestrierung — Phase 1
analyze → clarify → suggest_meta → generate → apply
"""
from __future__ import annotations

import logging
import re
from typing import Any

from apps.abpe_ki_wiz.services.prompt_loader import get_prompt_by_key
from apps.abpe_ki_wiz.models import WizardPhase, WizardSession
from apps.abpe_ki_wiz.registry import get_provider
from apps.abpe_ki_wiz.services.deepseek_client import call_wizard_prompt
from apps.abpe_ki_wiz.services.json_utils import dumps_compact, parse_ai_json
from apps.abpe_ki_wiz.services.prompt_builder import build_context_json
from apps.abpe_ki_wiz.services.session_store import merge_answers, session_to_dict

log = logging.getLogger('abpe_ki_wiz.orchestrator')

_MEETME_KW = re.compile(
    r'meetme|telefon|termin|abstimmung|einladung|konferenz|pbx',
    re.IGNORECASE,
)
_MATCHING_KW = re.compile(r'matching|kandidat|berater|kunde|cv', re.IGNORECASE)


def _prompt_key(wizard_id: str, phase: str) -> str:
    mapping = {
        ('email_template', 'analyze'): 'wiz_email_analyze',
        ('email_template', 'clarify'): 'wiz_email_clarify',
        ('email_template', 'suggest_meta'): 'wiz_email_suggest_meta',
        ('email_template', 'generate'): 'wiz_email_generate',
    }
    return mapping.get((wizard_id, phase), f'wiz_shared_analyze')


def _rule_based_analyze(wizard_id: str, briefing: str) -> dict[str, Any]:
    text = briefing or ''
    missing = []
    app_scope = 'general'
    event_type = 'info'

    if wizard_id == 'email_template' or _MEETME_KW.search(text):
        app_scope = 'telefon'
        event_type = 'invite'
        if re.search(r'erinnerung|reminder', text, re.I):
            event_type = 'reminder'
        if re.search(r'absage|cancel', text, re.I):
            event_type = 'cancel'
        missing = ['I1', 'M1', 'G1', 'A1']
        if re.search(r'aufzählung|liste|bullet', text, re.I):
            pass  # I1 likely answered
        if re.search(r'teilnehmer', text, re.I):
            missing = [m for m in missing if m != 'M2'] or missing

    summary = text[:200] + ('…' if len(text) > 200 else '')
    return {
        'understood': len(text.strip()) >= 20,
        'summary': summary,
        'app_scope': app_scope,
        'event_type': event_type,
        'missing_topics': missing,
        'source': 'rules',
    }


def analyze_session(session: WizardSession) -> dict[str, Any]:
    provider = get_provider(session.wizard_id)
    briefing = session.briefing or ''
    analyze: dict[str, Any]

    prompt = get_prompt_by_key(_prompt_key(session.wizard_id, 'analyze'))
    if prompt:
        ctx = build_context_json(provider, session.answers)
        ds = call_wizard_prompt(prompt, context=ctx, briefing=briefing)
        if ds.success and ds.text:
            try:
                analyze = parse_ai_json(ds.text)
                analyze['source'] = 'ai'
            except ValueError as exc:
                log.warning('Analyze JSON parse failed: %s', exc)
                analyze = _rule_based_analyze(session.wizard_id, briefing)
        else:
            analyze = _rule_based_analyze(session.wizard_id, briefing)
            if ds.error:
                analyze['ai_error'] = ds.error
    else:
        analyze = _rule_based_analyze(session.wizard_id, briefing)

    session.meta_suggestions = {**(session.meta_suggestions or {}), 'analyze': analyze}
    session.phase = WizardPhase.CLARIFY
    session.save(update_fields=['meta_suggestions', 'phase', 'updated_at'])

    pending = provider.resolve_questions(briefing, session.answers, analyze)
    questions = [q for q in provider.get_question_catalog() if q['id'] in pending]

    return {
        **session_to_dict(session),
        'analyze': analyze,
        'pending_question_ids': pending,
        'questions': questions,
    }


def clarify_session(session: WizardSession, new_answers: dict[str, Any]) -> dict[str, Any]:
    provider = get_provider(session.wizard_id)
    answers = merge_answers(session, new_answers)
    analyze = (session.meta_suggestions or {}).get('analyze') or {}

    pending = provider.resolve_questions(session.briefing, answers, analyze)
    complete = len(pending) == 0

    if complete:
        session.phase = WizardPhase.SUGGEST_META
        session.save(update_fields=['phase', 'updated_at'])

    questions = [q for q in provider.get_question_catalog() if q['id'] in pending]

    return {
        **session_to_dict(session),
        'complete': complete,
        'pending_question_ids': pending,
        'questions': questions,
    }


def suggest_meta_session(session: WizardSession) -> dict[str, Any]:
    provider = get_provider(session.wizard_id)
    answers = session.answers or {}
    ctx = build_context_json(provider, answers)
    briefing = session.briefing or ''

    prompt = get_prompt_by_key(_prompt_key(session.wizard_id, 'suggest_meta'))
    suggestions: dict[str, Any]

    if prompt:
        ds = call_wizard_prompt(
            prompt,
            context=ctx,
            briefing=briefing,
            answers=dumps_compact(answers),
        )
        if ds.success and ds.text:
            try:
                suggestions = parse_ai_json(ds.text)
            except ValueError:
                suggestions = provider.default_meta_suggestions(briefing, answers)
        else:
            suggestions = provider.default_meta_suggestions(briefing, answers)
            if ds.error:
                suggestions['ai_error'] = ds.error
    else:
        suggestions = provider.default_meta_suggestions(briefing, answers)

    session.meta_suggestions = {**(session.meta_suggestions or {}), **suggestions}
    session.phase = WizardPhase.GENERATE
    session.save(update_fields=['meta_suggestions', 'phase', 'updated_at'])

    return {
        **session_to_dict(session),
        'suggestions': suggestions,
    }


def generate_session(session: WizardSession) -> dict[str, Any]:
    provider = get_provider(session.wizard_id)
    answers = session.answers or {}
    meta = session.meta_suggestions or {}
    ctx = build_context_json(
        provider,
        answers,
        app_scope=meta.get('app_scope', ''),
        identifier=meta.get('identifier', ''),
    )

    prompt = get_prompt_by_key(_prompt_key(session.wizard_id, 'generate'))
    generated: dict[str, Any]

    if prompt:
        ds = call_wizard_prompt(
            prompt,
            context=ctx,
            briefing=session.briefing or '',
            answers=dumps_compact(answers),
            meta=dumps_compact(meta),
        )
        if ds.success and ds.text:
            try:
                generated = parse_ai_json(ds.text)
            except ValueError as exc:
                return {'error': f'Generate JSON ungültig: {exc}', 'raw': ds.text[:500]}
        else:
            return {'error': ds.error or 'DeepSeek Generate fehlgeschlagen'}
    else:
        return {'error': 'Generate-Prompt nicht gefunden'}

    validation = provider.validate_output({**meta, **generated})
    result = provider.apply_result({**meta, **generated}, session_meta=meta)
    result['validation'] = {
        'ok': validation.ok,
        'errors': validation.errors,
        'warnings': validation.warnings,
    }

    session.result = result
    session.phase = WizardPhase.GENERATE
    session.save(update_fields=['result', 'phase', 'updated_at'])

    return {
        **session_to_dict(session),
        'generated': generated,
        'apply': result,
    }


def apply_session(session: WizardSession) -> dict[str, Any]:
    provider = get_provider(session.wizard_id)
    if not session.result:
        return {'error': 'Kein Ergebnis — zuerst generate aufrufen'}
    applied = provider.apply_result(session.result, session_meta=session.meta_suggestions)
    session.mark_completed()
    return {
        **session_to_dict(session),
        'apply': applied,
    }
