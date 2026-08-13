"""
Zielschema für abpe_parser.

Quellen:
  - orasik/resume-parser: JSON-Resume-ähnliches, konfigurierbares Schema
  - OmkarPathak/ResumeParser: ai_summary, ai_strengths, experiences
  - pushkar-hue/AI-Resume-Parser: projects getrennt, personal_info, skills-Listen
  - ABpE/AID: skill_categories, industries, focus_areas
"""
from __future__ import annotations

from typing import Any, Dict, List

# Kompakte Schema-Beschreibung für den LLM-Prompt (nicht volles JSON-Schema — spart Tokens)
SCHEMA_HINT = """
{
  "basics": {
    "name": "", "first_name": "", "last_name": "",
    "email": "", "phone": "", "location": "",
    "label": "", "summary": "",
    "url": "", "linkedin": "",
    "availability": "", "nationality": "", "birth_year": null
  },
  "skills": ["..."],
  "skill_categories": {"Programmiersprachen": ["..."], "Betriebssysteme": ["..."]},
  "work": [{
    "company": "", "position": "", "period": "",
    "start_date": "", "end_date": "",
    "location": "", "industry": "",
    "summary": "",
    "highlights": ["..."],
    "technologies": ["..."]
  }],
  "projects": [{
    "name": "", "description": "", "technologies": ["..."],
    "start_date": "", "end_date": ""
  }],
  "education": [{
    "institution": "", "degree": "", "period": "",
    "start_date": "", "end_date": "", "description": "",
    "education_type": "degree|course|other"
  }],
  "certifications": [{"name": "", "issuer": "", "date": ""}],
  "languages": [{"language": "", "fluency": ""}],
  "industries": ["..."],
  "focus_areas": ["..."],
  "ai_summary": "",
  "ai_strengths": ["..."]
}
"""

# Pflicht-/Kernfelder für Coverage (orasik completeness + OpenResume-Gedanke)
COVERAGE_FIELDS = [
    ('basics.name', 'name'),
    ('basics.email', 'email'),
    ('basics.phone', 'phone'),
    ('basics.label', 'headline/label'),
    ('skills', 'skills'),
    ('skill_categories', 'skill_categories'),
    ('work', 'work/experience'),
    ('education', 'education'),
    ('certifications', 'certifications'),
    ('languages', 'languages'),
]


def empty_resume() -> Dict[str, Any]:
    return {
        'basics': {
            'name': '', 'first_name': '', 'last_name': '',
            'email': '', 'phone': '', 'location': '',
            'label': '', 'summary': '',
            'url': '', 'linkedin': '',
            'availability': '', 'nationality': '', 'birth_year': None,
        },
        'skills': [],
        'skill_categories': {},
        'work': [],
        'projects': [],
        'education': [],
        'certifications': [],
        'languages': [],
        'industries': [],
        'focus_areas': [],
        'ai_summary': '',
        'ai_strengths': [],
    }


def _as_list(v: Any) -> List:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        parts = [p.strip() for p in v.replace(';', ',').split(',') if p.strip()]
        return parts
    return [v]


def _get_path(data: dict, path: str) -> Any:
    cur: Any = data
    for part in path.split('.'):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def normalize_resume(raw: Any) -> Dict[str, Any]:
    """
    Mappt flache Omkar-/Pushkar-Antworten auf das einheitliche Schema.
    """
    out = empty_resume()
    if not isinstance(raw, dict):
        return out

    # Bereits strukturiert?
    if isinstance(raw.get('basics'), dict) or isinstance(raw.get('work'), list):
        b = raw.get('basics') or {}
        if not isinstance(b, dict):
            b = {}
        # Pushkar: personal_info
        pi = raw.get('personal_info') or {}
        if isinstance(pi, dict):
            b = {**pi, **b}
        out['basics'].update({k: b.get(k, out['basics'].get(k)) for k in out['basics']})
        if b.get('name') and not out['basics'].get('name'):
            out['basics']['name'] = b.get('name') or ''
        for key in (
            'skills', 'skill_categories', 'work', 'projects', 'education',
            'certifications', 'languages', 'industries', 'focus_areas',
            'ai_summary', 'ai_strengths',
        ):
            if key in raw and raw[key] is not None:
                out[key] = raw[key]
        # Aliases
        if raw.get('work_experience') and not out['work']:
            out['work'] = raw['work_experience']
        if raw.get('experiences') and not out['work']:
            out['work'] = _map_experiences(raw['experiences'])
        out['skills'] = _as_list(out.get('skills'))
        out['ai_strengths'] = _as_list(out.get('ai_strengths'))
        if isinstance(out.get('skill_categories'), list):
            # selten: Liste → dict Sonstige
            out['skill_categories'] = {'Sonstige Skills': _as_list(out['skill_categories'])}
        if not isinstance(out.get('skill_categories'), dict):
            out['skill_categories'] = {}
        _ensure_basics_name(out)
        return out

    # Flaches Omkar-Format
    name = raw.get('name') or ''
    out['basics']['name'] = name
    parts = name.split(None, 1)
    if len(parts) == 2:
        out['basics']['first_name'], out['basics']['last_name'] = parts[0], parts[1]
    elif parts:
        out['basics']['last_name'] = parts[0]
    out['basics']['email'] = raw.get('email') or ''
    out['basics']['phone'] = raw.get('mobile_number') or raw.get('phone') or ''
    out['basics']['location'] = raw.get('location') or ''
    out['basics']['label'] = raw.get('designation') or raw.get('label') or ''
    out['basics']['summary'] = raw.get('summary') or raw.get('ai_summary') or ''
    out['skills'] = _as_list(raw.get('skills'))
    out['skill_categories'] = raw.get('skill_categories') or {}
    if not isinstance(out['skill_categories'], dict):
        out['skill_categories'] = {}
    out['work'] = _map_experiences(raw.get('experiences') or raw.get('work') or [])
    out['projects'] = raw.get('projects') or []
    out['education'] = _map_education(raw.get('education'))
    out['certifications'] = raw.get('certifications') or []
    out['languages'] = _map_languages(raw.get('languages'))
    out['industries'] = _as_list(raw.get('industries'))
    out['focus_areas'] = _as_list(raw.get('focus_areas'))
    out['ai_summary'] = raw.get('ai_summary') or out['basics']['summary']
    out['ai_strengths'] = _as_list(raw.get('ai_strengths'))
    if raw.get('company_names') and not out['work']:
        # nur Namen — als leere work-Stubs behalten wir sie nicht
        pass
    _ensure_basics_name(out)
    return out


def _ensure_basics_name(out: dict) -> None:
    b = out['basics']
    if not b.get('name'):
        fn, ln = (b.get('first_name') or '').strip(), (b.get('last_name') or '').strip()
        b['name'] = f'{fn} {ln}'.strip()


def _map_experiences(items: Any) -> List[dict]:
    if not isinstance(items, list):
        return []
    mapped = []
    for it in items:
        if not isinstance(it, dict):
            continue
        highlights = it.get('highlights') or it.get('job_description') or it.get('activities')
        if isinstance(highlights, str):
            highlights = [highlights] if highlights.strip() else []
        mapped.append({
            'company': it.get('company') or '',
            'position': it.get('position') or it.get('designation') or it.get('role') or '',
            'period': it.get('period') or '',
            'start_date': it.get('start_date') or '',
            'end_date': it.get('end_date') or '',
            'location': it.get('location') or '',
            'industry': it.get('industry') or '',
            'summary': it.get('summary') or it.get('title') or '',
            'highlights': highlights or [],
            'technologies': _as_list(it.get('technologies')),
        })
    return mapped


def _map_education(edu: Any) -> List[dict]:
    if edu is None:
        return []
    if isinstance(edu, str):
        return [{
            'institution': '', 'degree': edu, 'period': '',
            'start_date': '', 'end_date': '', 'description': '',
            'education_type': 'degree',
        }]
    if not isinstance(edu, list):
        return []
    out = []
    for e in edu:
        if isinstance(e, str):
            out.append({
                'institution': '', 'degree': e, 'period': '',
                'start_date': '', 'end_date': '', 'description': '',
                'education_type': 'degree',
            })
        elif isinstance(e, dict):
            out.append({
                'institution': e.get('institution') or '',
                'degree': e.get('degree') or e.get('studyType') or '',
                'period': e.get('period') or '',
                'start_date': e.get('start_date') or e.get('startDate') or '',
                'end_date': e.get('end_date') or e.get('endDate') or '',
                'description': e.get('description') or '',
                'education_type': e.get('education_type') or 'degree',
            })
    return out


def _map_languages(langs: Any) -> List[dict]:
    if not langs:
        return []
    if isinstance(langs, str):
        return [{'language': p.strip(), 'fluency': ''} for p in langs.split(',') if p.strip()]
    if isinstance(langs, list):
        out = []
        for L in langs:
            if isinstance(L, str):
                out.append({'language': L, 'fluency': ''})
            elif isinstance(L, dict):
                out.append({
                    'language': L.get('language') or L.get('name') or '',
                    'fluency': L.get('fluency') or L.get('level') or '',
                })
        return out
    return []


def coverage_report(resume: dict) -> Dict[str, Any]:
    """Feld-Vollständigkeit (Pushkar/orasik completeness, ohne spaCy)."""
    filled = []
    missing = []
    for path, label in COVERAGE_FIELDS:
        val = _get_path(resume, path)
        ok = False
        if isinstance(val, (list, dict)):
            ok = bool(val)
        elif val is not None and str(val).strip():
            ok = True
        (filled if ok else missing).append(label)

    n_work = len(resume.get('work') or [])
    n_skills = len(resume.get('skills') or [])
    if not n_skills and isinstance(resume.get('skill_categories'), dict):
        n_skills = sum(len(v or []) for v in resume['skill_categories'].values())

    ratio = len(filled) / max(1, len(COVERAGE_FIELDS))
    return {
        'coverage_percent': round(ratio * 100, 1),
        'filled_fields': filled,
        'missing_fields': missing,
        'work_count': n_work,
        'skill_count': n_skills,
        'education_count': len(resume.get('education') or []),
        'certification_count': len(resume.get('certifications') or []),
    }
