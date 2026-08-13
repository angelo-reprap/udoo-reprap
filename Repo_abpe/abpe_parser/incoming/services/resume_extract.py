"""
Kern-Extraktion: Rohtext → DeepSeek → einheitliches Schema.

Bei langen AID-Profilen (DE oft länger als EN): 2-Pass
  Pass A: basics / skills / education / certs / languages / …
  Pass B: work[] (Berufliche Erfahrungen / Projects)

Sonst bricht DeepSeek bei max_tokens ab → leeres Schema (Abbady DE).
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from .deepseek_client import deepseek_client
from .schema import SCHEMA_HINT, empty_resume, normalize_resume
from .text_extract import extract_text

logger = logging.getLogger(__name__)

DEFAULT_MAX_CHARS = 24000
MAX_TOKENS_PROFILE = 4096
MAX_TOKENS_WORK = 8192

SYSTEM_PROMPT = (
    'You are an expert resume/CV parser for IT consultants and German Qualifikationsprofile '
    '(AID/abcona). Extract factual details into strict JSON. '
    'Do not invent information. Missing fields → empty string, null, or []. '
    'Keep German content in German. Output valid JSON only — no markdown.'
)

PROFILE_PROMPT = """
Extract PROFILE fields only (NO work/projects list) from this AID/CV text.

Return JSON with this shape (omit work/projects or set them to []):
{{
  "basics": {{
    "name": "", "first_name": "", "last_name": "",
    "email": "", "phone": "", "location": "",
    "label": "", "summary": "",
    "url": "", "linkedin": "",
    "availability": "", "nationality": "", "birth_year": null
  }},
  "skills": ["..."],
  "skill_categories": {{"Programmiersprachen": ["..."], "Betriebssysteme": ["..."],
    "Hardware": ["..."], "Datenbanken": ["..."],
    "Produkte | Standards | Erfahrungen": ["..."]}},
  "education": [{{"institution":"","degree":"","period":"","education_type":"degree|course"}}],
  "certifications": [{{"name":"","issuer":"","date":""}}],
  "languages": [{{"language":"","fluency":""}}],
  "industries": ["..."],
  "focus_areas": ["..."],
  "ai_summary": "3 sentences",
  "ai_strengths": ["..."]
}}

Notes:
- German headers: Persönliche Daten, Fachbereiche, Zertifizierungen, Branchen,
  Programmiersprachen, Betriebssysteme, Hardware, Datenbanken,
  Produkte | Standards | Erfahrungen, Schwerpunkt/Focus.
- Do NOT put Berufliche Erfahrungen / Projects into this response.

Resume Text:
{resume_text}
"""

WORK_PROMPT = """
Extract ALL work/project periods from this CV section into JSON:

{{
  "work": [{{
    "company": "",
    "position": "",
    "period": "",
    "start_date": "",
    "end_date": "",
    "location": "",
    "industry": "",
    "summary": "",
    "highlights": ["..."],
    "technologies": ["..."]
  }}]
}}

Rules:
1. Every "Zeitraum:" / "Period:" starts a new work item — miss none.
2. Firma/Institut / Customer / Kunde → company; Project description / Rolle → position/summary.
3. Tools: / Systemumgebung / Technologien → technologies.
4. Bullet activities → highlights (keep bullets, German if source is German).
5. Include Weiterbildung. Sort most recent first.
6. Output valid JSON only.

Section text:
{work_text}
"""


def _split_work_section(text: str) -> Tuple[str, str]:
    """Profil-Teil vs. Berufliche Erfahrungen / Projects."""
    m = re.search(
        r'(?im)^\s*(Berufliche\s+Erfahrungen?|Projects?|Projektübersicht)\s*$',
        text,
    )
    if not m:
        # Fallback: ab erstem Zeitraum/Period
        m = re.search(r'(?im)^\s*(Zeitraum|Period)\s*:', text)
    if not m:
        return text, text
    return text[: m.start()], text[m.start():]


def _is_empty_resume(data: Optional[dict]) -> bool:
    if not data:
        return True
    if data.get('work'):
        return False
    if data.get('skills') or data.get('skill_categories'):
        return False
    b = data.get('basics') or {}
    if any(b.get(k) for k in ('name', 'email', 'label', 'phone')):
        return False
    return True


def _token_capped(usage: dict, max_tokens: int) -> bool:
    try:
        return int(usage.get('completion_tokens') or 0) >= max_tokens - 5
    except Exception:
        return False


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

        profile_text, work_text = _split_work_section(text)
        # Pass A: Profil ohne lange Work-Liste
        r_profile = deepseek_client.chat_json(
            user_prompt=PROFILE_PROMPT.format(resume_text=profile_text[:max_chars]),
            system_prompt=SYSTEM_PROMPT,
            max_tokens=MAX_TOKENS_PROFILE,
            temperature=0.0,
        )
        # Pass B: nur Work
        r_work = deepseek_client.chat_json(
            user_prompt=WORK_PROMPT.format(work_text=work_text[:max_chars]),
            system_prompt=SYSTEM_PROMPT,
            max_tokens=MAX_TOKENS_WORK,
            temperature=0.0,
        )

        usage = {
            'profile': r_profile.usage,
            'work': r_work.usage,
            'completion_tokens': (
                int((r_profile.usage or {}).get('completion_tokens') or 0)
                + int((r_work.usage or {}).get('completion_tokens') or 0)
            ),
            'prompt_tokens': (
                int((r_profile.usage or {}).get('prompt_tokens') or 0)
                + int((r_work.usage or {}).get('prompt_tokens') or 0)
            ),
            'total_tokens': (
                int((r_profile.usage or {}).get('total_tokens') or 0)
                + int((r_work.usage or {}).get('total_tokens') or 0)
            ),
        }
        finish = {
            'profile': getattr(r_profile, 'finish_reason', None),
            'work': getattr(r_work, 'finish_reason', None),
        }
        capped = (
            _token_capped(r_profile.usage or {}, MAX_TOKENS_PROFILE)
            or _token_capped(r_work.usage or {}, MAX_TOKENS_WORK)
            or finish.get('profile') == 'length'
            or finish.get('work') == 'length'
        )

        merged_raw: Dict[str, Any] = {}
        if r_profile.success and isinstance(r_profile.data, dict):
            merged_raw.update(r_profile.data)
        if r_work.success and isinstance(r_work.data, dict):
            if r_work.data.get('work') is not None:
                merged_raw['work'] = r_work.data.get('work')
            if r_work.data.get('projects') is not None:
                merged_raw['projects'] = r_work.data.get('projects')

        # Fallback: ein Pass wenn 2-Pass beide scheitern
        if not merged_raw and (not r_profile.success and not r_work.success):
            single = deepseek_client.chat_json(
                user_prompt=USER_PROMPT_SINGLE.format(
                    schema=SCHEMA_HINT, resume_text=text,
                ),
                system_prompt=SYSTEM_PROMPT,
                max_tokens=MAX_TOKENS_WORK,
                temperature=0.0,
            )
            usage['single'] = single.usage
            if single.success and isinstance(single.data, dict):
                merged_raw = single.data
                r_profile = single  # for error messaging

        data = normalize_resume(merged_raw) if merged_raw else empty_resume()
        empty = _is_empty_resume(data)
        n_work = len((data or {}).get('work') or [])

        # Zeitraum im Text aber 0 work → klarer Fehler
        text_periods = len(re.findall(r'(?im)^\s*(Zeitraum|Period)\s*:', text))
        error = None
        if not r_profile.success and not r_work.success:
            error = r_profile.error or r_work.error or 'DeepSeek fehlgeschlagen'
        elif empty:
            error = 'Leeres Extraktionsergebnis'
            if capped:
                error += ' (Antwort an max_tokens abgeschnitten — 2-Pass Retry nötig)'
        elif text_periods >= 3 and n_work == 0:
            error = (
                f'Text hat ~{text_periods} Zeitraum/Period-Einträge, '
                f'aber work[] ist leer (Work-Pass fehlgeschlagen?)'
            )
            if r_work.error:
                error += f' | work_error={r_work.error}'
            if capped:
                error += ' | token_cap'

        success = (not empty) and error is None
        # Teil-Erfolg: Profil ok, work leer aber Perioden erwartet → success False
        if n_work == 0 and text_periods >= 3:
            success = False

        out: Dict[str, Any] = {
            'success': success,
            'error': error,
            'source_path': source_path,
            'backend': 'deepseek-api',
            'model': deepseek_client.model,
            'text_chars': len(text),
            'truncated': truncated,
            'token_capped': capped,
            'finish_reason': finish,
            'processing_time': round(
                (r_profile.processing_time or 0) + (r_work.processing_time or 0), 2
            ),
            'usage': usage,
            'data': data,
            'raw_llm': {
                'profile': r_profile.data if r_profile.success else None,
                'work': r_work.data if r_work.success else None,
                'profile_error': r_profile.error,
                'work_error': r_work.error,
                'work_raw_excerpt': (r_work.raw_response or '')[:500],
            },
            'debug': {
                'profile_chars': len(profile_text),
                'work_chars': len(work_text),
                'text_period_markers': text_periods,
                'work_count': n_work,
            },
        }
        if success:
            logger.info(
                '[abpe_parser] parse OK work=%s periods_in_text=%s time=%.1fs capped=%s',
                n_work, text_periods, out['processing_time'], capped,
            )
        else:
            logger.warning(
                '[abpe_parser] parse weak/fail: %s | work=%s periods=%s capped=%s',
                error, n_work, text_periods, capped,
            )
        return out


USER_PROMPT_SINGLE = """
Extract structured data from the resume text. Output MUST match this JSON shape:

{schema}

Rules:
1. "work" = every Zeitraum:/Period: station under Berufliche Erfahrungen / Projects.
2. skill_categories from section headers (Programmiersprachen, Betriebssysteme, …).
3. Keep German. Sort work most recent first.

Resume Text:
{resume_text}
"""


abpe_resume_parser = AbpeResumeParser()
