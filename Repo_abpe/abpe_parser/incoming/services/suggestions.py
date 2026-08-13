"""
AI-Verbesserungsvorschläge (pushkar suggestions + Omkar coach).

Ohne JD: allgemeine ATS-/Profil-Qualität.
Mit JD: priorisierte Anpassungen (kann jd_match nutzen oder separat).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from .deepseek_client import deepseek_client

logger = logging.getLogger(__name__)

SYSTEM = (
    'You are a career coach for IT consultants (German market / abcona-style profiles). '
    'Give concrete, actionable advice. Output valid JSON only. Prefer German.'
)

PROMPT = """
Analyze this structured resume and give improvement suggestions.

Return JSON:
{{
  "overall_assessment": "2-3 sentences",
  "ats_tips": ["..."],
  "content_tips": ["..."],
  "structure_tips": ["..."],
  "skill_tips": ["..."],
  "priority_actions": ["top 5 next steps"]
}}

{jd_block}

RESUME JSON:
{resume_json}
"""


def suggest_improvements(
    resume: dict,
    jd_text: Optional[str] = None,
) -> Dict[str, Any]:
    jd_block = ''
    if jd_text and jd_text.strip():
        jd_block = f'JOB DESCRIPTION (tailor suggestions):\n{jd_text.strip()[:6000]}\n'
    else:
        jd_block = 'No JD provided — give general profile quality tips.\n'

    slim = {
        'basics': resume.get('basics'),
        'skills': resume.get('skills'),
        'skill_categories': resume.get('skill_categories'),
        'work_count': len(resume.get('work') or []),
        'work_sample': (resume.get('work') or [])[:5],
        'education': resume.get('education'),
        'certifications': resume.get('certifications'),
        'ai_summary': resume.get('ai_summary'),
    }
    prompt = PROMPT.format(
        jd_block=jd_block,
        resume_json=json.dumps(slim, ensure_ascii=False, indent=2)[:12000],
    )
    result = deepseek_client.chat_json(
        user_prompt=prompt,
        system_prompt=SYSTEM,
        max_tokens=2000,
        temperature=0.2,
    )
    return {
        'success': result.success,
        'error': result.error,
        'processing_time': round(result.processing_time, 2),
        'usage': result.usage,
        'data': result.data if result.success else None,
    }
