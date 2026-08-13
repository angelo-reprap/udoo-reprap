"""
Thin DeepSeek Chat API client (settings.json) — kein Ollama / llama-cpp.
Gleiche Config wie cv_extractor: /opt/abpe/backend/settings.json → ai_models.deepseek
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)


@dataclass
class DeepSeekResult:
    success: bool
    data: Any = None
    error: Optional[str] = None
    raw_response: str = ''
    processing_time: float = 0.0
    usage: Dict[str, int] = field(default_factory=dict)
    finish_reason: Optional[str] = None


class DeepSeekClient:
    def __init__(self):
        self.api_key: Optional[str] = None
        self.model = 'deepseek-chat'
        self.base_url = 'https://api.deepseek.com/v1/chat/completions'
        self.timeout = 180
        self._load_config()

    def _load_config(self) -> None:
        settings_path = os.environ.get(
            'ABPE_SETTINGS_JSON', '/opt/abpe/backend/settings.json'
        )
        if os.path.exists(settings_path):
            try:
                with open(settings_path, encoding='utf-8') as f:
                    cfg = json.load(f)
                ds = (cfg.get('ai_models') or {}).get('deepseek') or {}
                self.api_key = ds.get('api_key') or self.api_key
                self.model = ds.get('model') or self.model
            except Exception as e:
                logger.warning('settings.json DeepSeek: %s', e)
        if not self.api_key:
            try:
                from django.conf import settings
                self.api_key = getattr(settings, 'DEEPSEEK_API_KEY', None)
            except Exception:
                pass

    def is_available(self) -> bool:
        return bool(self.api_key)

    def chat_json(
        self,
        user_prompt: str,
        system_prompt: str = 'Antworte NUR mit gültigem JSON.',
        max_tokens: int = 4000,
        temperature: float = 0.0,
    ) -> DeepSeekResult:
        start = time.time()
        if not self.is_available():
            return DeepSeekResult(False, error='Kein DeepSeek API Key')

        payload = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            'temperature': temperature,
            'max_tokens': max_tokens,
        }
        try:
            r = requests.post(
                self.base_url,
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                },
                json=payload,
                timeout=self.timeout,
                verify=False,
            )
            r.raise_for_status()
            body = r.json()
            choice = (body.get('choices') or [{}])[0]
            content = (choice.get('message') or {}).get('content') or ''
            finish_reason = choice.get('finish_reason')
            usage = body.get('usage') or {}
            data = _parse_json_content(content)
            if data is None:
                err = 'JSON parse failed'
                if finish_reason == 'length':
                    err += ' (finish_reason=length — max_tokens zu klein)'
                return DeepSeekResult(
                    False,
                    error=err,
                    raw_response=content,
                    processing_time=time.time() - start,
                    usage=usage,
                    finish_reason=finish_reason,
                )
            return DeepSeekResult(
                True,
                data=data,
                raw_response=content,
                processing_time=time.time() - start,
                usage=usage,
                finish_reason=finish_reason,
            )
        except Exception as e:
            return DeepSeekResult(
                False,
                error=str(e),
                processing_time=time.time() - start,
            )


def _parse_json_content(content: str) -> Any:
    stripped = (content or '').strip()
    if stripped.startswith(('```json', '```')):
        stripped = re.sub(r'^```(?:json)?\s*', '', stripped)
        stripped = re.sub(r'\s*```$', '', stripped).strip()
    try:
        return json.loads(stripped)
    except Exception:
        pass
    for start_char, end_char in (('{', '}'), ('[', ']')):
        start_idx = stripped.find(start_char)
        if start_idx < 0:
            continue
        depth = 0
        in_string = False
        escape = False
        end_idx = -1
        for i, ch in enumerate(stripped[start_idx:], start_idx):
            if escape:
                escape = False
                continue
            if ch == '\\' and in_string:
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == start_char:
                depth += 1
            elif ch == end_char:
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break
        if end_idx > start_idx:
            try:
                return json.loads(stripped[start_idx : end_idx + 1])
            except Exception:
                continue
    return None


deepseek_client = DeepSeekClient()
