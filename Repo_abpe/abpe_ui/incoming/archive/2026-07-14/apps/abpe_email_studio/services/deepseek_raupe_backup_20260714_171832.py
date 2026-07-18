"""
DeepSeek-Raupe — generischer Kern (MeetMe, Matching, …).
"""
from __future__ import annotations

import re
from typing import Any, Optional

from apps.abpe_email_studio.services.renderer import EmailRenderer


# Markdown / DeepSeek-Artefakte vor Variablen-Ersetzung
_RE_SUBJECT_LINE = re.compile(
    r'^\s*\*{0,2}\s*Betreff\s*:\s*\*{0,2}\s*.+\n?',
    re.IGNORECASE | re.MULTILINE,
)
_RE_BOLD = re.compile(r'\*\*(.+?)\*\*')
_RE_BRACKET_NAME = re.compile(r'\[Ihr Name\]', re.IGNORECASE)


class DeepSeekRaupe:
    """KI-Vorschlag + Normalisierung + Variablen-Ersetzung."""

    def __init__(self):
        self._renderer = EmailRenderer()

    def get_instruction(self, key: str, override: Optional[str] = None) -> str:
        from apps.abpe_crm.services.deepseek_api_pbx import get_prompt_config
        cfg = get_prompt_config(key)
        return (override or cfg.get('instruction_default') or '').strip()

    def suggest(
        self,
        text: str,
        *,
        prompt_key: str = 'summarize',
        instruction: Optional[str] = None,
    ):
        from apps.abpe_crm.services.deepseek_api_pbx import deepseek_pbx, get_prompt_config
        cfg = get_prompt_config(prompt_key)
        instr = (instruction or cfg.get('instruction_default') or 'Formuliere den Text um.').strip()
        # summarize-Pipeline: system/user aus cfg, instruction separat
        system = cfg.get('system') or ''
        user_tpl = cfg.get('user_template') or '[[INSTRUCTION]]\n\n[[TEXT]]'
        from apps.abpe_crm.services.deepseek_api_pbx import _fill
        user_prompt = _fill(user_tpl, INSTRUCTION=instr, TEXT=text)
        return deepseek_pbx._chat(system, user_prompt)

    def build_all_vars(
        self,
        variables: dict,
        user=None,
        subject: str = '',
    ) -> dict:
        all_vars = {
            **self._renderer._get_system_vars(),
            **self._renderer._get_user_vars(user),
            **(variables or {}),
        }
        if subject:
            all_vars['subject'] = subject
        return all_vars

    def apply_variables(self, text: str, variables: dict, user=None, subject: str = '') -> str:
        return self._renderer._render(text, self.build_all_vars(variables, user, subject))

    def normalize(
        self,
        raw: str,
        variables: dict,
        user=None,
        subject: str = '',
        fmt: str = 'text',
    ) -> str:
        text = raw or ''
        text = _RE_SUBJECT_LINE.sub('', text)
        text = _RE_BOLD.sub(r'\1', text)
        text = text.replace('\r\n', '\n').strip()
        if fmt == 'text':
            # Einfache Listenzeilen
            text = re.sub(r'^\s*[-*]\s+', '', text, flags=re.MULTILINE)
        all_vars = self.build_all_vars(variables, user, subject)
        text = self._renderer._render(text, all_vars)
        text = _RE_BRACKET_NAME.sub(all_vars.get('sender_name', ''), text)
        return text.strip()

    def full_pipeline(
        self,
        text: str,
        variables: dict,
        user=None,
        *,
        prompt_key: str = 'meetme_email',
        instruction: Optional[str] = None,
        subject: str = '',
        fmt: str = 'text',
    ) -> dict[str, Any]:
        result = self.suggest(text, prompt_key=prompt_key, instruction=instruction)
        if not result.success:
            return {
                'success': False,
                'error': result.error or 'DeepSeek-Fehler',
                'raw': '',
                'suggestion': '',
            }
        raw = result.text or ''
        suggestion = self.normalize(raw, variables, user, subject, fmt)
        return {
            'success': True,
            'error': None,
            'raw': raw,
            'suggestion': suggestion,
        }


deepseek_raupe = DeepSeekRaupe()
