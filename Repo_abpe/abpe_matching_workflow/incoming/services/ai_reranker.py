"""
ABpE Matching Workflow — AI Reranker
Generiert LLM-Begründungen warum ein Berater zur Anfrage passt
"""
import logging
import json
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _llm_cfg():
    try:
        p = Path(__file__).resolve().parent.parent.parent.parent / 'settings.json'
        cfg = json.loads(p.read_text(encoding='utf-8'))
        return cfg.get('matching', {}).get('llm', {}), cfg.get('ai_models', {})
    except Exception:
        return {}, {}


class AIReranker:
    """Generiert Begründungen via Ollama (qwen2.5:7b) oder Deepseek Fallback"""

    def __init__(self):
        llm_cfg, ai_cfg = _llm_cfg()
        self.model       = llm_cfg.get('reranker_model',    'qwen2.5:7b')
        self.fallback    = llm_cfg.get('reranker_fallback', 'deepseek-chat')
        self.max_tokens  = llm_cfg.get('reason_max_tokens', 300)
        self.lang        = llm_cfg.get('reason_language',   'de')
        self.ollama_cfg  = ai_cfg.get('ollama', {})
        self.deepseek_cfg= ai_cfg.get('deepseek', {})
        self.model_used  = ''

    def generate_reason(self, project, consultant) -> str:
        """
        Generiert 3-5 Sätze Begründung warum dieser Berater zur Anfrage passt.
        Versucht zuerst Ollama, dann Deepseek als Fallback.
        """
        prompt = self._build_prompt(project, consultant)

        # Versuch 1: Ollama
        reason = self._try_ollama(prompt)
        if reason:
            self.model_used = self.model
            return reason

        # Versuch 2: Deepseek
        reason = self._try_deepseek(prompt)
        if reason:
            self.model_used = self.fallback
            return reason

        # Fallback: Regelbasiert
        self.model_used = 'rule_based'
        return self._rule_based_reason(project, consultant)

    def _build_prompt(self, project, consultant) -> str:
        # Skills des Beraters (max 10)
        skills = [cs.skill.name for cs in consultant.skills.all()[:10]]

        lang_instruction = (
            "Antworte auf Deutsch." if self.lang == 'de'
            else "Answer in English."
        )

        return f"""Du bist ein erfahrener Personalvermittler.

Projektanfrage: {project.title}
Beschreibung: {project.description[:300] if project.description else ''}
Gesuchte Skills: {', '.join(self._skill_names(project.required_skills)[:8])}

Berater: {consultant.full_name}
Skills: {', '.join(skills)}
Erfahrung: {getattr(getattr(consultant, 'statistics', None), 'total_experience_years', '?')} Jahre
Standort: {consultant.location or 'unbekannt'}

Erkläre in 3-5 Sätzen warum dieser Berater gut zur Projektanfrage passt.
Sei konkret und nenne spezifische Skills.
{lang_instruction}
Nur die Begründung, keine Überschrift."""

    def _try_ollama(self, prompt: str) -> Optional[str]:
        try:
            import requests
            host    = 'http://localhost:11434'
            timeout = self.ollama_cfg.get('timeout', 60)

            resp = requests.post(
                f'{host}/api/generate',
                json={
                    'model':  self.model,
                    'prompt': prompt,
                    'stream': False,
                    'options': {'temperature': 0.3, 'num_predict': self.max_tokens},
                },
                timeout=timeout,
            )
            if resp.status_code == 200:
                text = resp.json().get('response', '').strip()
                if text:
                    return text
        except Exception as e:
            logger.debug(f"Ollama nicht verfügbar: {e}")
        return None

    def _try_deepseek(self, prompt: str) -> Optional[str]:
        try:
            import requests
            api_key = self.deepseek_cfg.get('api_key', '')
            if not api_key:
                return None

            resp = requests.post(
                'https://api.deepseek.com/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type':  'application/json',
                },
                json={
                    'model':       self.deepseek_cfg.get('model', 'deepseek-chat'),
                    'messages':    [{'role': 'user', 'content': prompt}],
                    'max_tokens':  self.max_tokens,
                    'temperature': 0.3,
                },
                timeout=self.deepseek_cfg.get('timeout', 30),
            )
            if resp.status_code == 200:
                text = resp.json()['choices'][0]['message']['content'].strip()
                if text:
                    return text
        except Exception as e:
            logger.debug(f"Deepseek nicht verfügbar: {e}")
        return None

    def _rule_based_reason(self, project, consultant) -> str:
        """Einfache regelbasierte Begründung ohne LLM"""
        req_skills  = self._skill_names(project.required_skills)
        cons_skills = {cs.skill.name.lower() for cs in consultant.skills.all()}
        matched     = [s for s in req_skills if s.lower() in cons_skills]

        if self.lang == 'de':
            if matched:
                return (
                    f"{consultant.full_name} verfügt über relevante Kenntnisse in "
                    f"{', '.join(matched[:3])} und passt damit zu den Anforderungen "
                    f"des Projekts '{project.title}'."
                )
            return (
                f"{consultant.full_name} wurde aufgrund des Gesamtprofils als "
                f"möglicher Kandidat für '{project.title}' identifiziert."
            )
        else:
            if matched:
                return (
                    f"{consultant.full_name} has relevant experience in "
                    f"{', '.join(matched[:3])}, matching the requirements of '{project.title}'."
                )
            return f"{consultant.full_name} was identified as a potential candidate for '{project.title}'."

    def _skill_names(self, skills_field) -> list:
        if not skills_field:
            return []
        names = []
        for s in skills_field:
            if isinstance(s, dict):
                n = s.get('name', '')
                if n:
                    names.append(n)
            elif isinstance(s, str) and s:
                names.append(s)
        return names
