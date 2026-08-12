"""
deepseek_api_label.py - DeepSeek API fuer Block-Labeling
Wie deepseek_api.py aber parst JSON-Arrays [ ] statt nur Dicts { }
"""
import os, json, re, time, requests
from typing import Optional
from dataclasses import dataclass
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

@dataclass
class LabelResult:
    success: bool
    data: object  # List oder Dict
    raw_response: str = ""
    error: Optional[str] = None

class DeepSeekLabelAPI:
    def __init__(self):
        cfg = json.load(open('/opt/abpe/backend/settings.json'))
        self.api_key = cfg.get('ai_models',{}).get('deepseek',{}).get('api_key')
        self.base_url = "https://api.deepseek.com/v1/chat/completions"

    def extract(self, prompt: str, system_prompt: str = "Antworte NUR mit JSON.") -> LabelResult:
        if not self.api_key:
            return LabelResult(False, None, error="Kein API Key")
        for _attempt in range(2):
          try:
            import urllib3; urllib3.disable_warnings()
            r = requests.post(
                self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": "deepseek-chat", "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": prompt}
                ], "temperature": 0},
                timeout=90, verify=False
            )
            content = r.json()['choices'][0]['message']['content']
            import logging as _log
            _log.getLogger('deepseek_label_api').info(
                f"[DeepSeekLabel] raw Laenge={len(content)} | "
                f"erste 80={repr(content[:80])} | "
                f"letzte 80={repr(content[-80:])}"
            )
            # 1. Direkt parsen (sauberste Antwort)
            stripped = content.strip()
            if stripped.startswith(('```json', '```')):
                stripped = re.sub(r'^```(?:json)?\s*', '', stripped)
                stripped = re.sub(r'\s*```$', '', stripped)
                stripped = stripped.strip()
            try:
                return LabelResult(True, json.loads(stripped), raw_response=content)
            except Exception:
                pass

            # 2. Groesstes JSON-Objekt oder Array extrahieren
            for start_char, end_char in [('[', ']'), ('{', '}')]:
                start_idx = stripped.find(start_char)
                if start_idx == -1:
                    continue
                # Von hinten das passende Ende suchen
                depth = 0
                end_idx = -1
                in_string = False
                escape = False
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
                if end_idx != -1:
                    candidate = stripped[start_idx:end_idx+1]
                    try:
                        parsed = json.loads(candidate)
                        _log.getLogger('deepseek_label_api').info(
                            f"[DeepSeekLabel] JSON OK via bracket-matching: {len(candidate)} Zeichen"
                        )
                        return LabelResult(True, parsed, raw_response=content)
                    except Exception as je:
                        _log.getLogger('deepseek_label_api').warning(
                            f"[DeepSeekLabel] JSON parse Fehler: {je} | Laenge={len(candidate)}"
                        )
            return LabelResult(False, None, raw_response=content, error="Kein JSON")
          except Exception as e:
            if _attempt == 0:
                import time; time.sleep(3)
                continue
            return LabelResult(False, None, error=str(e))
          break

deepseek_label_api = DeepSeekLabelAPI()
