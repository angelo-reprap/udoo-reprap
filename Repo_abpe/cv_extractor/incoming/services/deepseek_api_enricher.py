"""
deepseek_api.py - DeepSeek API für zuverlässige Extraktion
Mit deaktivierter SSL-Verifikation für Entwicklungsumgebung
"""

import os
import json
import requests
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@dataclass
class DeepSeekResult:
    success: bool
    data: Dict[str, Any]
    raw_response: str = ""
    error: Optional[str] = None
    processing_time: float = 0.0


class DeepSeekAPIService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or self._load_api_key()
        self.base_url = "https://api.deepseek.com/v1/chat/completions"
        self.model = "deepseek-chat"
        self.session = requests.Session()
        self.session.verify = False

    def _load_api_key(self) -> Optional[str]:
        settings_path = '/opt/abpe/backend/settings.json'
        if os.path.exists(settings_path):
            try:
                with open(settings_path, 'r') as f:
                    config = json.load(f)
                    return config.get('ai_models', {}).get('deepseek', {}).get('api_key')
            except:
                pass
        return None

    def is_available(self) -> bool:
        return bool(self.api_key)

    def extract(self, prompt: str, system_prompt: str = "Du bist ein präziser CV-Analyst. Antworte nur mit JSON.") -> DeepSeekResult:
        """Sendet Prompt an DeepSeek API und parst JSON-Antwort"""
        import time
        start_time = time.time()

        if not self.is_available():
            return DeepSeekResult(success=False, data={}, error="Kein API Key")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.session.post(
                self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0,
                    "max_tokens": 4000
                },
                timeout=60
            )

            if response.status_code != 200:
                return DeepSeekResult(success=False, data={}, error=f"HTTP {response.status_code}")

            result = response.json()
            content = result['choices'][0]['message']['content']

            # JSON extrahieren - Array zuerst, dann Dict
            for pat in [r'\[[\s\S]*\]', r'\{[\s\S]*\}']:
                m = re.search(pat, content)
                if m:
                    try:
                        data = json.loads(m.group())
                        return DeepSeekResult(success=True, data=data, raw_response=content, processing_time=time.time() - start_time)
                    except Exception:
                        pass
            return DeepSeekResult(success=False, data={}, error="Kein JSON in Antwort", raw_response=content)
        except Exception as e:
            return DeepSeekResult(success=False, data={}, error=str(e))

    def group_projects(self, lines: List[str]) -> List[int]:
        """Extrahiert Projekt-Starts aus Zeilen"""
        relevant = []
        for i, line in enumerate(lines):
            if any(kw in line for kw in ['Zeitraum:', 'Kunde / Branche:', 'Rolle / Position:']):
                relevant.append(f"{i}: {line[:100]}")

        prompt = f"""Analysiere diese Lebenslauf-Zeilen. Ein Projekt beginnt mit einem Datum.
Gib für JEDEN Projekt-Start den Index zurück.

{chr(10).join(relevant[:60])}

Antworte NUR mit JSON: {{"starts": [0, 7, 15]}}"""

        result = self.extract(prompt)
        if result.success:
            return result.data.get('starts', [])
        return []

    def build_projects(self, lines: List[str], starts: List[int]) -> List[Dict]:
        """Baut Projekte aus den Starts"""
        projects = []
        for i in range(len(starts)):
            start = starts[i]
            end = starts[i+1] - 1 if i + 1 < len(starts) else len(lines) - 1
            projects.append({'start': start, 'end': end})
        return projects


deepseek_api = DeepSeekAPIService()
