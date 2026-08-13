"""
Job-Description Matching (Omkar OptimizationAgent + Pushkar Job Match).

DeepSeek vergleicht Resume-JSON / Text gegen eine JD und liefert
match_score, matched/missing skills, suggestions, action_items.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from .deepseek_client import deepseek_client

logger = logging.getLogger(__name__)

SYSTEM = (
    'You are a Senior Technical Recruiter. Compare a candidate resume to a Job Description. '
    'Be strict and factual. Output valid JSON only.'
)

PROMPT = """
Compare the candidate data to the Job Description.

Scoring (strict):
1. Required technical skills (60%)
2. Years & depth of experience (30%)
3. Education & certifications (10%)

Return JSON:
{{
  "match_score": 0-100,
  "score_reasoning": "one sentence",
  "matched_skills": ["..."],
  "missing_skills": ["..."],
  "strengths": ["..."],
  "gaps": ["..."],
  "suggestions": ["prioritized modifications"],
  "action_items": ["3-5 immediate steps"]
}}

CANDIDATE (JSON):
{resume_json}

JOB DESCRIPTION:
{jd_text}
"""


def match_resume_to_jd(
    resume: dict,
    jd_text: str,
    max_jd_chars: int = 8000,
) -> Dict[str, Any]:
    jd = (jd_text or '').strip()
    if not jd:
        return {'success': False, 'error': 'Leere Job Description', 'data': None}
    if len(jd) > max_jd_chars:
        jd = jd[:max_jd_chars]

    # Kompaktes Resume für Prompt
    slim = {
        'basics': resume.get('basics'),
        'skills': resume.get('skills'),
        'skill_categories': resume.get('skill_categories'),
        'work': (resume.get('work') or [])[:12],
        'education': resume.get('education'),
        'certifications': resume.get('certifications'),
        'ai_summary': resume.get('ai_summary'),
        'ai_strengths': resume.get('ai_strengths'),
    }
    prompt = PROMPT.format(
        resume_json=json.dumps(slim, ensure_ascii=False, indent=2)[:14000],
        jd_text=jd,
    )
    result = deepseek_client.chat_json(
        user_prompt=prompt,
        system_prompt=SYSTEM,
        max_tokens=2000,
        temperature=0.1,
    )
    return {
        'success': result.success,
        'error': result.error,
        'processing_time': round(result.processing_time, 2),
        'usage': result.usage,
        'data': result.data if result.success else None,
    }
