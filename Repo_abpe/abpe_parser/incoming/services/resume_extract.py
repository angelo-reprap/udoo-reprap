"""
ResumeParser-Stil: Rohtext → DeepSeek → striktes JSON.

Unterschied zu OmkarPathak/ResumeParser:
  - DeepSeek API statt lokalem Qwen/llama-cpp/Ollama
  - mehr Kontext (nicht auf ~1500–4000 Zeichen hart gekürzt, wenn Config erlaubt)
  - noch NICHT in cv_extractor-Pipeline eingehängt — nur Vergleich/Experiment
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .deepseek_client import deepseek_client
from .text_extract import extract_text

logger = logging.getLogger(__name__)

# AID-Profile sind oft lang — Default großzügig; via max_chars begrenzbar
DEFAULT_MAX_CHARS = 24000

SYSTEM_PROMPT = (
    'You are an expert Data Extractor for IT consultant CVs / Qualifikationsprofile. '
    'Extract factual details into strict JSON. Do not invent information. '
    'If a field is missing, use null or empty string / empty list. '
    'Prefer German section labels when present (Berufliche Erfahrungen, Ausbildung, …).'
)

USER_PROMPT_TEMPLATE = """
Analyze the resume text and extract structured information into JSON.

Fields:
- name, email, mobile_number: strings
- skills: list of strings (technologies, tools, languages)
- skill_categories: object mapping category name → list of skills
  (e.g. "Programmiersprachen", "Betriebssysteme", "Datenbanken", "Hardware")
- company_names: list of strings
- education: list of objects {{degree, institution, period, description}}
- designation, total_experience: strings
- ai_summary: 3 sentence professional summary (German if CV is German)
- ai_strengths: list of 3-5 strings
- experiences: list of objects:
  - designation, company, start_date, end_date, period: strings
  - location, industry: strings
  - job_description: list of achievement/activity bullet strings
  - technologies: list of strings

RULES for experiences:
1. Include professional roles AND Weiterbildung entries if present.
2. Do not drop projects — capture as many distinct periods as possible.
3. Keep job_description bullets; do not collapse to one line.
4. Sort by date, most recent first.

Output valid JSON only.

Resume Text:
{resume_text}
"""


class AbpeResumeParser:
    """Experimenteller Parser — DeepSeek JSON, ResumeParser-inspiriert."""

    def parse_file(
        self,
        file_path: str,
        max_chars: int = DEFAULT_MAX_CHARS,
    ) -> Dict[str, Any]:
        text = extract_text(file_path)
        return self.parse_text(text, source_path=file_path, max_chars=max_chars)

    def parse_text(
        self,
        text: str,
        source_path: Optional[str] = None,
        max_chars: int = DEFAULT_MAX_CHARS,
    ) -> Dict[str, Any]:
        text = (text or '').strip()
        if not text:
            return {
                'success': False,
                'error': 'Kein Text extrahiert',
                'source_path': source_path,
                'data': None,
            }

        truncated = False
        if max_chars and len(text) > max_chars:
            text = text[:max_chars]
            truncated = True

        prompt = USER_PROMPT_TEMPLATE.format(resume_text=text)
        result = deepseek_client.chat_json(
            user_prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            max_tokens=4000,
            temperature=0.0,
        )

        out: Dict[str, Any] = {
            'success': result.success,
            'error': result.error,
            'source_path': source_path,
            'backend': 'deepseek-api',
            'model': deepseek_client.model,
            'text_chars': len(text),
            'truncated': truncated,
            'processing_time': round(result.processing_time, 2),
            'usage': result.usage,
            'data': result.data if result.success else None,
        }
        if not result.success:
            logger.warning('[abpe_parser] parse failed: %s', result.error)
        else:
            n_exp = 0
            if isinstance(result.data, dict):
                n_exp = len(result.data.get('experiences') or [])
            logger.info(
                '[abpe_parser] OK experiences=%s time=%.1fs truncated=%s',
                n_exp, result.processing_time, truncated,
            )
        return out


abpe_resume_parser = AbpeResumeParser()
