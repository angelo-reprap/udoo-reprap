"""
Orchestrierung der sinnvollen Features aus den drei OSS-Projekten:

  1) Text extrahieren          (alle)
  2) LLM → strukturiertes JSON (Omkar / orasik / Pushkar)
  3) Coverage + Quality Score  (Pushkar scoring, ohne spaCy)
  4) optional JD-Match         (Omkar optimize + Pushkar match)
  5) optional Suggestions      (Pushkar / Omkar coach)

Alles über DeepSeek API. Nicht in cv_extractor eingehängt.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .jd_match import match_resume_to_jd
from .quality_score import score_resume
from .resume_extract import abpe_resume_parser
from .schema import coverage_report
from .suggestions import suggest_improvements
from .text_extract import extract_text

logger = logging.getLogger(__name__)


def run_pipeline(
    file_path: Optional[str] = None,
    text: Optional[str] = None,
    jd_text: Optional[str] = None,
    jd_path: Optional[str] = None,
    *,
    do_score: bool = True,
    do_match: bool = False,
    do_suggest: bool = False,
    max_chars: int = 24000,
) -> Dict[str, Any]:
    """
    Vollständiger Durchlauf. Mindestens file_path oder text.
    """
    source = file_path
    if text is None:
        if not file_path:
            return {'success': False, 'error': 'file_path oder text erforderlich'}
        parse = abpe_resume_parser.parse_file(file_path, max_chars=max_chars)
    else:
        parse = abpe_resume_parser.parse_text(
            text, source_path=file_path, max_chars=max_chars,
        )

    result: Dict[str, Any] = {
        'success': parse.get('success', False),
        'error': parse.get('error'),
        'source_path': source,
        'backend': parse.get('backend'),
        'model': parse.get('model'),
        'parse_meta': {
            'text_chars': parse.get('text_chars'),
            'truncated': parse.get('truncated'),
            'token_capped': parse.get('token_capped'),
            'finish_reason': parse.get('finish_reason'),
            'processing_time': parse.get('processing_time'),
            'usage': parse.get('usage'),
            'debug': parse.get('debug'),
        },
        'resume': parse.get('data'),
        'raw_llm': parse.get('raw_llm'),
        'analysis': {},
    }

    resume = result.get('resume')
    # Score auch bei partial/fail (zeigt leere Coverage)
    analysis: Dict[str, Any] = {}
    if resume and do_score:
        analysis['coverage'] = coverage_report(resume)
        analysis['quality'] = score_resume(resume)
        result['analysis'] = analysis

    if not result['success'] or not resume:
        return result

    # JD laden
    jd = (jd_text or '').strip()
    if not jd and jd_path:
        p = Path(jd_path)
        if p.suffix.lower() in ('.pdf', '.docx', '.doc'):
            jd = extract_text(str(p))
        else:
            jd = p.read_text(encoding='utf-8', errors='replace')

    want_match = do_match or bool(jd)
    if want_match and jd:
        analysis['jd_match'] = match_resume_to_jd(resume, jd)

    if do_suggest:
        analysis['suggestions'] = suggest_improvements(
            resume, jd_text=jd if jd else None,
        )

    result['analysis'] = analysis
    return result
