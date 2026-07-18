"""DeepSeek-Aufrufe für WizardPrompt (aus WizardPrompt DB, nicht CRM-Defaults)."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import requests
import urllib3

from apps.abpe_ki_wiz.models import WizardPrompt

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger('abpe_ki_wiz.deepseek')

SETTINGS_PATH = Path('/opt/abpe/backend/settings.json')
DEEPSEEK_URL = 'https://api.deepseek.com/v1/chat/completions'


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


def _load_deepseek_config() -> dict[str, Any]:
    try:
        if SETTINGS_PATH.exists():
            cfg = json.loads(SETTINGS_PATH.read_text(encoding='utf-8'))
            return cfg.get('ai_models', {}).get('deepseek', {}) or {}
    except Exception as exc:
        log.warning('DeepSeek settings.json nicht lesbar: %s', exc)
    return {}


def _resolve_pbx_service():
    """CRM-Instanz deepseek_pbx (Methoden sind auf der Instanz, nicht am Modul)."""
    try:
        from apps.abpe_crm.services import deepseek_api_pbx as pbx_mod
    except ImportError:
        return None, None

    for attr in ('deepseek_pbx', 'DeepSeekPBXService'):
        svc = getattr(pbx_mod, attr, None)
        if svc is None:
            continue
        if isinstance(svc, type):
            try:
                return svc(), pbx_mod
            except Exception:
                continue
        return svc, pbx_mod
    return None, pbx_mod


def _call_service_method(svc, method_name: str, *args, **kwargs) -> DeepSeekResult | None:
    fn = getattr(svc, method_name, None)
    if not callable(fn):
        return None
    try:
        return _coerce_result(fn(*args, **kwargs))
    except TypeError:
        try:
            return _coerce_result(fn(*args))
        except Exception as exc:
            log.warning('%s fehlgeschlagen: %s', method_name, exc)
            return DeepSeekResult(success=False, error=str(exc))
    except Exception as exc:
        log.warning('%s fehlgeschlagen: %s', method_name, exc)
        return DeepSeekResult(success=False, error=str(exc))


def _http_chat_completion(system_msg: str, user_msg: str) -> DeepSeekResult:
    """Direkter DeepSeek-HTTP-Call wie EmailTranslator (Fallback ohne CRM-Wrapper)."""
    ds_cfg = _load_deepseek_config()
    api_key = ds_cfg.get('api_key') or ''
    if not api_key:
        return DeepSeekResult(success=False, error='DeepSeek API-Key fehlt (settings.json)')

    model = ds_cfg.get('model', 'deepseek-chat')
    timeout = ds_cfg.get('timeout', 90)
    temperature = ds_cfg.get('temperature', 0.2)
    max_tokens = ds_cfg.get('max_tokens', 2500)

    try:
        resp = requests.post(
            DEEPSEEK_URL,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': model,
                'temperature': temperature,
                'max_tokens': max_tokens,
                'messages': [
                    {'role': 'system', 'content': system_msg},
                    {'role': 'user', 'content': user_msg},
                ],
            },
            timeout=timeout,
            verify=False,
        )
        if resp.status_code != 200:
            return DeepSeekResult(
                success=False,
                error=f'HTTP {resp.status_code}: {resp.text[:200]}',
            )
        content = resp.json()['choices'][0]['message']['content']
        text = (content or '').strip()
        return DeepSeekResult(success=bool(text), text=text)
    except Exception as exc:
        log.exception('DeepSeek HTTP-Call fehlgeschlagen')
        return DeepSeekResult(success=False, error=str(exc))


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
    instr = (instruction or prompt.instruction_default or '').strip()
    if instr and '[[INSTRUCTION]]' not in (prompt.user_template or ''):
        user_msg = f'{user_msg}\n\nAnweisung:\n{instr}'
    if not instr:
        instr = 'Antworte gemäß System-Anweisung.'

    svc, pbx_mod = _resolve_pbx_service()
    if svc is not None:
        for method_name in ('wizard_completion', 'chat_completion', 'complete'):
            result = _call_service_method(svc, method_name, system=system_msg, user=user_msg)
            if result is not None and (result.success or result.error):
                if result.success:
                    return result
            result = _call_service_method(svc, method_name, system_msg, user_msg)
            if result is not None and result.success:
                return result

        if hasattr(svc, 'suggest_with_key'):
            result = _call_service_method(
                svc,
                'suggest_with_key',
                user_msg,
                prompt.key,
                instr,
            )
            if result is not None and result.success:
                return result

        combined = f'{system_msg}\n\n{user_msg}'.strip()
        result = _call_service_method(svc, 'summarize', combined, instr)
        if result is not None and result.success:
            return result

    # Modul-Level-Fallback (ältere Installationen)
    if pbx_mod is not None:
        for method_name in ('wizard_completion', 'chat_completion', 'complete', 'summarize'):
            fn = getattr(pbx_mod, method_name, None)
            if callable(fn):
                try:
                    coerced = _coerce_result(fn(system=system_msg, user=user_msg))
                except TypeError:
                    try:
                        coerced = _coerce_result(fn(system_msg, user_msg))
                    except Exception:
                        continue
                if coerced.success:
                    return coerced

    # Letzter Fallback: direkter HTTP-Call
    return _http_chat_completion(system_msg, user_msg)
