"""DeepSeek-Aufrufe für WizardPrompt (aus WizardPrompt DB, nicht CRM-Defaults)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from apps.abpe_ki_wiz.models import WizardPrompt

log = logging.getLogger('abpe_ki_wiz.deepseek')


@dataclass
class DeepSeekResult:
    success: bool
    text: str = ''
    error: Optional[str] = None


def _coerce_result(result) -> DeepSeekResult:
    try:
        from apps.abpe_crm.services.deepseek_api_pbx import PbxAIResult
        if isinstance(result, PbxAIResult):
            return DeepSeekResult(
                success=bool(result.success),
                text=(result.text or '').strip(),
                error=result.error,
            )
    except ImportError:
        pass
    if isinstance(result, tuple) and len(result) >= 2:
        ok, text = result[0], result[1]
        err = result[2] if len(result) > 2 else None
        return DeepSeekResult(success=bool(ok), text=(text or '').strip(), error=err)
    if hasattr(result, 'success'):
        return DeepSeekResult(
            success=bool(result.success),
            text=(getattr(result, 'text', '') or '').strip(),
            error=getattr(result, 'error', None),
        )
    if isinstance(result, str):
        t = result.strip()
        return DeepSeekResult(success=bool(t), text=t)
    return DeepSeekResult(success=False, error='Unbekanntes DeepSeek-Antwortformat')


def fill_prompt_template(
    prompt: WizardPrompt,
    *,
    context: str = '',
    briefing: str = '',
    answers: str = '',
    meta: str = '',
    instruction: str = '',
) -> str:
    user = prompt.user_template or ''
    repl = {
        '[[CONTEXT]]': context,
        '[[BRIEFING]]': briefing,
        '[[ANSWERS]]': answers,
        '[[META]]': meta,
        '[[INSTRUCTION]]': instruction or prompt.instruction_default or '',
        '[[TEXT]]': briefing,
        '[[NOTES]]': briefing,
    }
    for key, val in repl.items():
        user = user.replace(key, val)
    return user


def call_wizard_prompt(
    prompt: WizardPrompt,
    *,
    context: str = '',
    briefing: str = '',
    answers: str = '',
    meta: str = '',
    instruction: str = '',
) -> DeepSeekResult:
    """Ruft DeepSeek mit System/User aus WizardPrompt auf."""
    user_msg = fill_prompt_template(
        prompt,
        context=context,
        briefing=briefing,
        answers=answers,
        meta=meta,
        instruction=instruction,
    )
    system_msg = (prompt.system or '').strip()

    try:
        from apps.abpe_crm.services import deepseek_api_pbx as pbx
    except ImportError as exc:
        log.error('deepseek_api_pbx nicht verfügbar: %s', exc)
        return DeepSeekResult(success=False, error='DeepSeek-Service nicht installiert')

    # Bevorzugt: dedizierte Chat-API falls vorhanden
    for method_name in ('wizard_completion', 'chat_completion', 'complete'):
        fn = getattr(pbx, method_name, None)
        if callable(fn):
            try:
                return _coerce_result(fn(system=system_msg, user=user_msg))
            except TypeError:
                try:
                    return _coerce_result(fn(system_msg, user_msg))
                except Exception as exc:
                    log.warning('%s fehlgeschlagen: %s', method_name, exc)

    # Fallback: suggest_with_key mit Wizard-Prompt-Key (wenn in CRM registriert)
    if hasattr(pbx, 'suggest_with_key'):
        try:
            return _coerce_result(
                pbx.suggest_with_key(user_msg, prompt.key, instruction or prompt.instruction_default)
            )
        except Exception as exc:
            log.warning('suggest_with_key fehlgeschlagen: %s', exc)

    # Letzter Fallback: summarize mit System+User kombiniert
    combined = f'{system_msg}\n\n{user_msg}'.strip()
    instr = instruction or prompt.instruction_default or 'Antworte gemäß System-Anweisung.'
    try:
        return _coerce_result(pbx.summarize(combined, instr))
    except Exception as exc:
        log.exception('DeepSeek summarize fehlgeschlagen')
        return DeepSeekResult(success=False, error=str(exc))
