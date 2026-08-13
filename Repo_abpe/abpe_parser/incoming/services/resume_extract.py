"""
Kern-Extraktion: Rohtext → DeepSeek → einheitliches Schema.

Inspiriert von:
  OmkarPathak/ResumeParser (Agent extract + summary/strengths)
  orasik/resume-parser (reiches Schema)
  pushkar-hue/AI-Resume-Parser (personal/work/projects/education)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .deepseek_client import deepseek_client
from .schema import SCHEMA_HINT, normalize_resume
from .text_extract import extract_text

logger = logging.getLogger(__name__)

DEFAULT_MAX_CHARS = 24000

SYSTEM_PROMPT = (
    'You are an expert resume/CV parser for IT consultants and German Qualifikationsprofile '
    '(AID/abcona). Extract factual details into strict JSON matching the schema. '
    'Do not invent information. Missing fields → empty string, null, or []. '
    'Keep German content in German. Capture as many work periods as possible.'
)

USER_PROMPT_TEMPLATE = """
Extract structured data from the resume text. Output MUST match this JSON shape:

{schema}

Rules:
1. "work" = berufliche Stationen / Projekte mit Zeitraum (Berufliche Erfahrungen).
   Include Weiterbildung entries. Do not drop periods.
2. "projects" = standalone project section if distinct from work; else [].
3. "skill_categories" = map PDF section headers (Programmiersprachen, Hardware, …)
   to skill lists when present; also fill flat "skills".
4. "certifications" vs education courses: certs in certifications; Schulungen/Kurse in education
   with education_type="course".
5. "ai_summary": 3 sentences; "ai_strengths": 3-5 bullets.
6. Sort work most recent first. Keep highlights as bullet list, not one line.

Resume Text:
{resume_text}
"""


class AbpeResumeParser:
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
                'raw_llm': None,
            }

        truncated = False
        if max_chars and len(text) > max_chars:
            text = text[:max_chars]
            truncated = True

        prompt = USER_PROMPT_TEMPLATE.format(
            schema=SCHEMA_HINT,
            resume_text=text,
        )
        result = deepseek_client.chat_json(
            user_prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            max_tokens=6000,
            temperature=0.0,
        )

        data = None
        if result.success and result.data is not None:
            data = normalize_resume(result.data)

        out: Dict[str, Any] = {
            'success': bool(result.success and data is not None),
            'error': result.error,
            'source_path': source_path,
            'backend': 'deepseek-api',
            'model': deepseek_client.model,
            'text_chars': len(text),
            'truncated': truncated,
            'processing_time': round(result.processing_time, 2),
            'usage': result.usage,
            'data': data,
            'raw_llm': result.data if result.success else None,
        }
        if out['success']:
            n_work = len((data or {}).get('work') or [])
            logger.info(
                '[abpe_parser] parse OK work=%s time=%.1fs truncated=%s',
                n_work, result.processing_time, truncated,
            )
        else:
            logger.warning('[abpe_parser] parse failed: %s', result.error)
        return out


abpe_resume_parser = AbpeResumeParser()
