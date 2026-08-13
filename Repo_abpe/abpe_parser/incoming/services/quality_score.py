"""
Struktur-/Qualitäts-Score ohne spaCy/Java (pushkar scoring.py Idee, leichtgewichtig).

Dimensionen:
  - completeness (Coverage)
  - experience_depth (Anzahl work + Highlights)
  - skills_breadth
  - structure (Sections vorhanden)
"""
from __future__ import annotations

from typing import Any, Dict

from .schema import coverage_report


def score_resume(resume: dict) -> Dict[str, Any]:
    cov = coverage_report(resume)
    work = resume.get('work') or []
    skills = resume.get('skills') or []
    if not skills and isinstance(resume.get('skill_categories'), dict):
        for v in resume['skill_categories'].values():
            skills.extend(v or [])

    # Experience: bis 10 Einträge voll, Highlights bonus
    n_work = len(work)
    highlights = sum(len(w.get('highlights') or []) for w in work if isinstance(w, dict))
    exp_score = min(100, n_work * 12 + min(40, highlights * 2))

    # Skills: bis 20 Skills = 100
    skill_score = min(100, len(set(str(s).lower() for s in skills)) * 5)

    # Structure: Kern-Sektionen
    struct_pts = 0
    if cov['coverage_percent'] >= 50:
        struct_pts += 30
    if n_work >= 1:
        struct_pts += 25
    if skills:
        struct_pts += 20
    if resume.get('education'):
        struct_pts += 15
    if resume.get('certifications') or resume.get('languages'):
        struct_pts += 10
    structure_score = min(100, struct_pts)

    completeness = cov['coverage_percent']
    overall = round(
        completeness * 0.35 + exp_score * 0.30 + skill_score * 0.20 + structure_score * 0.15
    )

    feedback = {
        'completeness': (
            'Gute Abdeckung der Kernfelder.'
            if completeness >= 70
            else f'Fehlend: {", ".join(cov["missing_fields"][:5]) or "—"}'
        ),
        'experience': (
            f'{n_work} Stationen, {highlights} Bullet-Punkte.'
            if n_work
            else 'Keine Berufserfahrung extrahiert.'
        ),
        'skills': (
            f'{len(skills)} Skills erkannt.'
            if skills
            else 'Keine Skills erkannt — Kategorie-Blöcke prüfen.'
        ),
    }

    return {
        'overall_score': overall,
        'completeness_score': round(completeness),
        'experience_score': round(exp_score),
        'skills_score': round(skill_score),
        'structure_score': round(structure_score),
        'coverage': cov,
        'feedback': feedback,
    }
