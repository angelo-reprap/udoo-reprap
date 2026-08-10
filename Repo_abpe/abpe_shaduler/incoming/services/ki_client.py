"""
ki_client — dünner DeepSeek-Zugang für Shaduler (Kap. 6 / V3-Vorbau).

Im Architektur-Dok:
  - DeepSeek: i18n-Restsprachen (V1.1) + LLM-Service Ollama/DeepSeek (V3)
  - V1 nutzt Ollama-Aufrufe direkt für Radar; DeepSeek-API liegt in settings.json

Dieser Client liest denselben Key wie CRM/ki_wiz (`settings.json` → ai_models.deepseek)
und ist optional — ohne Key schlägt suggest_* fehl, Kernfunktionen laufen weiter.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import requests

log = logging.getLogger('abpe_shaduler.ki')

SETTINGS_PATH = Path('/opt/abpe/backend/settings.json')
DEEPSEEK_URL = 'https://api.deepseek.com/v1/chat/completions'


@dataclass
class KiResult:
    success: bool
    text: str = ''
    error: Optional[str] = None


def _load_cfg() -> dict[str, Any]:
    try:
        if SETTINGS_PATH.exists():
            cfg = json.loads(SETTINGS_PATH.read_text(encoding='utf-8'))
            return cfg.get('ai_models', {}).get('deepseek', {}) or {}
    except Exception as exc:
        log.warning('settings.json DeepSeek nicht lesbar: %s', exc)
    return {}


def available() -> bool:
    return bool(_load_cfg().get('api_key'))


def chat(system: str, user: str, *, max_tokens: int = 800) -> KiResult:
    cfg = _load_cfg()
    api_key = cfg.get('api_key') or ''
    if not api_key:
        return KiResult(success=False, error='DeepSeek API-Key fehlt (settings.json ai_models.deepseek)')
    try:
        resp = requests.post(
            DEEPSEEK_URL,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': cfg.get('model', 'deepseek-chat'),
                'messages': [
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': user},
                ],
                'temperature': float(cfg.get('temperature', 0.2)),
                'max_tokens': int(cfg.get('max_tokens', max_tokens)),
            },
            timeout=int(cfg.get('timeout', 90)),
        )
        if not resp.ok:
            return KiResult(success=False, error=f'HTTP {resp.status_code}: {resp.text[:300]}')
        data = resp.json()
        text = (
            data.get('choices', [{}])[0]
            .get('message', {})
            .get('content', '')
            or ''
        ).strip()
        return KiResult(success=bool(text), text=text)
    except Exception as exc:
        log.warning('DeepSeek chat fehlgeschlagen: %s', exc)
        return KiResult(success=False, error=str(exc))


def suggest_naechste_aktion(aufgabe_titel: str, stand: str = '', hist: Optional[list] = None) -> KiResult:
    """V1-Hilfe: kurze Empfehlung fürs Popup (kein Auto-Apply)."""
    hist_txt = '\n'.join(f'- {h}' for h in (hist or [])[:8])
    return chat(
        'Du bist Assistent für Recruiter-Aufgaben. Antworte kurz auf Deutsch '
        '(max. 3 Bullet-Punkte): empfohlene nächste Aktion und warum.',
        f'Aufgabe: {aufgabe_titel}\nStand: {stand}\nHistorie:\n{hist_txt or "—"}',
        max_tokens=400,
    )
