"""
Wizard-Orchestrierung — Phase 1
analyze → clarify → suggest_meta → generate → apply
"""
from __future__ import annotations

import logging
import re
from typing import Any

from apps.abpe_ki_wiz.services.context_fetcher import resolve_facts
from apps.abpe_ki_wiz.services.prompt_loader import get_prompt_by_key
from apps.abpe_ki_wiz.models import WizardPhase, WizardSession
from apps.abpe_ki_wiz.registry import get_provider
from apps.abpe_ki_wiz.services.deepseek_client import call_wizard_prompt
from apps.abpe_ki_wiz.services.json_utils import dumps_compact, parse_ai_json
from apps.abpe_ki_wiz.services.prompt_builder import build_context_json
from apps.abpe_ki_wiz.services.session_store import merge_answers, session_to_dict

log = logging.getLogger('abpe_ki_wiz.orchestrator')

_MEETME_KW = re.compile(
    r'meetme|telefon(?:-)?abstimmung|pbx|konferenz(?:einladung)?|einwahl',
    re.IGNORECASE,
)
_MATCHING_KW = re.compile(r'matching|kandidat|berater|cv[\s-]?upload', re.IGNORECASE)
_ABSENCE_KW = re.compile(r'abwesenheit|vertretung|urlaub|krank|out[\s-]?of[\s-]?office', re.IGNORECASE)
_GREETING_KW = re.compile(r'weihnacht|festtag|silvester|neujahr|grüße|gruesse|season', re.IGNORECASE)


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
    app_scope = 'general'
    event_type = 'info'
    missing: list[str] = []

    if _MATCHING_KW.search(text):
        app_scope = 'matching'
        event_type = 'info'
    elif _MEETME_KW.search(text) or (
        re.search(r'termin|einladung|meetme', text, re.I) and re.search(r'telefon|pbx|meetme', text, re.I)
    ):
        app_scope = 'telefon'
        event_type = 'invite'
        if re.search(r'erinnerung|reminder', text, re.I):
            event_type = 'reminder'
        if re.search(r'absage|cancel', text, re.I):
            event_type = 'cancel'
        if re.search(r'teilnehmer', text, re.I):
            missing.append('M2')
    elif _ABSENCE_KW.search(text):
        app_scope = 'general'
        event_type = 'info'
    elif _GREETING_KW.search(text):
        app_scope = 'general'
        event_type = 'info'

    summary = text[:200] + ('…' if len(text) > 200 else '')
    return {
        'understood': len(text.strip()) >= 20,
        'summary': summary,
        'app_scope': app_scope,
        'event_type': event_type,
        'missing_topics': missing,
        'source': 'rules',
    }


def _scope_from_session(session: WizardSession, analyze: dict[str, Any] | None = None) -> str:
    answers = session.answers or {}
    analyze = analyze or {}
    meta = session.meta_suggestions or {}
    return (
        answers.get('S1')
        or analyze.get('app_scope')
        or meta.get('app_scope')
        or (meta.get('analyze') or {}).get('app_scope')
        or 'general'
    )


def analyze_session(session: WizardSession) -> dict[str, Any]:
    provider = get_provider(session.wizard_id)
    briefing = session.briefing or ''
    analyze: dict[str, Any]

    prompt = get_prompt_by_key(_prompt_key(session.wizard_id, 'analyze'))
    if prompt:
        facts = resolve_facts(
            wizard_id=session.wizard_id,
            user=session.user,
            briefing=briefing,
            answers=session.answers,
            meta=session.meta_suggestions,
        )
        ctx = build_context_json(
            provider, session.answers, app_scope='general', facts=facts,
        )
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
    analyze = (session.meta_suggestions or {}).get('analyze') or {}
    briefing = session.briefing or ''
    scope = _scope_from_session(session, analyze)
    facts = resolve_facts(
        wizard_id=session.wizard_id,
        user=session.user,
        briefing=briefing,
        answers=answers,
        meta=session.meta_suggestions,
    )
    ctx = build_context_json(provider, answers, app_scope=scope, facts=facts)

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


def _resolve_current_bodies(
    session: WizardSession,
    html_body: str = '',
    text_body: str = '',
) -> tuple[str, str]:
    html = (html_body or '').strip()
    text = (text_body or '').strip()
    if html:
        return html, text

    result = session.result or {}
    fields = result.get('fields') if isinstance(result.get('fields'), dict) else result
    if isinstance(fields, dict):
        html = (fields.get('html_body') or '').strip()
        text = (fields.get('text_body') or text).strip()
    return html, text


def _build_refine_instruction(
    refinement: str,
    *,
    current_html: str = '',
    current_text: str = '',
) -> str:
    parts = [
        f'Verfeinerung/Korrektur vom User: {refinement}.',
        'Passe html_body und text_body an; Metadaten nur ändern wenn nötig.',
        'Behalte gültige {{block:…}} und {variablen} bei.',
        'Firmenadresse/Impressum: nur facts.company_abcona oder {{block:signature}} — nie erfinden.',
        'User-Absender: facts.user als {sender_name}/{sender_email}.',
        'CRM-Daten: facts.contact / facts.account / facts.crm_candidates — Werte aus facts.*.variables.',
    ]
    if current_html:
        parts.append(f'Aktueller html_body (Ausgangsbasis):\n{current_html[:12000]}')
    if current_text:
        parts.append(f'Aktueller text_body:\n{current_text[:8000]}')
    return '\n'.join(parts)


def generate_session(
    session: WizardSession,
    refinement: str = '',
    *,
    meta_override: dict[str, Any] | None = None,
    html_body: str = '',
    text_body: str = '',
) -> dict[str, Any]:
    provider = get_provider(session.wizard_id)
    answers = session.answers or {}

    if meta_override:
        clean_meta = {
            k: v for k, v in meta_override.items()
            if v is not None and v != ''
        }
        if clean_meta:
            session.meta_suggestions = {**(session.meta_suggestions or {}), **clean_meta}
            session.save(update_fields=['meta_suggestions', 'updated_at'])

    meta = session.meta_suggestions or {}
    current_html, current_text = _resolve_current_bodies(session, html_body, text_body)
    facts = resolve_facts(
        wizard_id=session.wizard_id,
        user=session.user,
        briefing=session.briefing or '',
        answers=answers,
        meta=meta,
        refinement=refinement,
    )
    ctx = build_context_json(
        provider,
        answers,
        app_scope=meta.get('app_scope', ''),
        identifier=meta.get('identifier', ''),
        facts=facts,
    )

    prompt = get_prompt_by_key(_prompt_key(session.wizard_id, 'generate'))
    generated: dict[str, Any]

    ai_error = ''
    refine_instr = ''
    if refinement:
        refine_instr = _build_refine_instruction(
            refinement,
            current_html=current_html,
            current_text=current_text,
        )
    if prompt:
        ds = call_wizard_prompt(
            prompt,
            context=ctx,
            briefing=session.briefing or '',
            answers=dumps_compact(answers),
            meta=dumps_compact(meta),
            instruction=refine_instr,
        )
        if ds.success and ds.text:
            try:
                generated = parse_ai_json(ds.text)
                generated['source'] = 'ai'
            except ValueError as exc:
                ai_error = f'Generate JSON ungültig: {exc}'
                generated = {}
        else:
            ai_error = ds.error or 'DeepSeek Generate fehlgeschlagen'
            generated = {}
    else:
        ai_error = 'Generate-Prompt nicht gefunden'
        generated = {}

    if not generated.get('html_body'):
        if refinement and current_html:
            generated = {
                'html_body': current_html,
                'text_body': current_text or current_html,
                'source': 'unchanged',
            }
            if ai_error:
                generated['ai_error'] = ai_error
        else:
            fallback_fn = getattr(provider, 'generate_fallback', None)
            if callable(fallback_fn):
                generated = fallback_fn(session.briefing or '', answers, meta)
                if ai_error:
                    generated['ai_error'] = ai_error
            elif ai_error:
                return {'error': ai_error}

    # MCID: Layout-Vorschläge (KI oder Heuristik) für Vorschau-Nachfrage
    suggestions = generated.get('layout_suggestions') or []
    if not isinstance(suggestions, list):
        suggestions = []
    if not suggestions:
        try:
            from apps.abpe_email_studio.blocks_registry import suggest_blocks_for_text
            suggestions = suggest_blocks_for_text(
                f"{session.briefing or ''}\n{generated.get('html_body') or ''}"
            )
        except ImportError:
            suggestions = []
    # Normalisieren für Frontend
    norm = []
    for s in suggestions:
        if not isinstance(s, dict):
            continue
        norm.append({
            'id': s.get('id') or '',
            'question': s.get('question') or s.get('question_de') or s.get('name') or '',
            'syntax': s.get('syntax') or '',
            'name': s.get('name') or s.get('id') or '',
            'description': s.get('description') or '',
        })
    generated['layout_suggestions'] = norm

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
