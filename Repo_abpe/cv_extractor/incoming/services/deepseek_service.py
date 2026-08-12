"""
deepseek_service.py - DeepSeek API Integration für cv_extractor
Mit SSL deaktiviert für Entwicklungsumgebung
"""

import json
import logging
import re
import time
import requests
from typing import Dict, Any, Optional
from dataclasses import dataclass

# SSL-Warnungen unterdrücken
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


@dataclass
class DeepSeekResult:
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    confidence: float = 0.0
    processing_time: float = 0.0
    raw_response: str = ""
    usage: Dict[str, int] = None


class DeepSeekService:
    """Service für DeepSeek API"""

    def __init__(self):
        self.api_key = None
        self.model = "deepseek-chat"
        self.base_url = "https://api.deepseek.com/v1/chat/completions"
        self.timeout = 120
        self._load_config()

    def _load_config(self):
        """Lädt API-Key aus settings.json"""
        import os
        import json
        
        # Zuerst aus settings.json
        settings_path = '/opt/abpe/backend/settings.json'
        if os.path.exists(settings_path):
            try:
                with open(settings_path, 'r') as f:
                    config = json.load(f)
                    self.api_key = config.get('ai_models', {}).get('deepseek', {}).get('api_key')
                    if self.api_key:
                        return
            except:
                pass
        
        # Dann aus Django settings
        try:
            from django.conf import settings
            self.api_key = getattr(settings, 'DEEPSEEK_API_KEY', None)
        except:
            pass

    def is_available(self) -> bool:
        return bool(self.api_key)

    def extract(self, prompt: str, system_prompt: str = "Du bist ein präziser CV-Analyst.") -> DeepSeekResult:
        """Sendet Prompt an DeepSeek API"""
        start_time = time.time()

        if not self.is_available():
            return DeepSeekResult(False, {}, error="Kein API Key")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 4000
        }

        try:
            # SSL deaktivieren für Entwicklung (verify=False)
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
                verify=False  # Wichtig: SSL deaktivieren
            )

            if response.status_code != 200:
                return DeepSeekResult(False, {}, error=f"HTTP {response.status_code}")

            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            usage = result.get('usage', {})

            json_data = self._extract_json(content)

            return DeepSeekResult(
                success=bool(json_data),
                data=json_data or {},
                raw_response=content,
                processing_time=time.time() - start_time,
                confidence=0.9 if json_data else 0.0,
                usage=usage
            )

        except Exception as e:
            return DeepSeekResult(False, {}, error=str(e))

    def _extract_json(self, text: str) -> Optional[Dict]:
        """Extrahiert JSON aus Antwort"""
        if not text:
            return None
        
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except:
                pass

        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass

        return None
    
    def group_projects(self, lines: list, max_lines: int = 100) -> DeepSeekResult:
        """Gruppiert Zeilen in Projekte"""
        test_lines = lines[:max_lines]
        
        # Kompakte Darstellung
        compact = []
        for i, line in enumerate(test_lines):
            if any(kw in line for kw in ['Zeitraum:', 'Kunde / Branche:', 'Rolle / Position:']):
                compact.append(f"{i}: {line[:80]}")
        
        prompt = f"""Analysiere diese Lebenslauf-Zeilen. Ein Projekt beginnt mit einem Datum.
Gib für JEDEN Projekt-Start den Index zurück.

{chr(10).join(compact[:50])}

Antworte NUR JSON: {{"starts": [0, 7, 15]}}"""
        
        return self.extract(prompt, system_prompt="Du bist ein präziser CV-Analyst. Antworte nur mit JSON.")


deepseek_service = DeepSeekService()
