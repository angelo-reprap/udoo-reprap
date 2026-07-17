"""
ABpE Matching Engine v2
Direkt gegen cv_extractor.Consultant — 3 Stufen:
  1. ORM Vorfilter (status, skills, location)
  2. Python Scoring (gewichtet)
  3. Synonym-Erweiterung via SkillRelation
"""
import logging
import json
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def _cfg() -> Dict:
    try:
        p = Path(__file__).resolve().parent.parent.parent.parent / 'settings.json'
        return json.loads(p.read_text(encoding='utf-8')).get('matching', {})
    except Exception:
        return {}


class MatchingEngine:

    def __init__(self):
        cfg = _cfg()
        s = cfg.get('scoring', {})
        self.w_req      = s.get('weight_skills_required', 0.50)
        self.w_nice     = s.get('weight_skills_nice',     0.20)
        self.w_industry = s.get('weight_industry',        0.15)
        self.w_exp      = s.get('weight_experience',      0.10)
        self.w_loc      = s.get('weight_location',        0.05)
        self.min_score  = s.get('min_score_threshold',    0.30)

    # ──────────────────────────────────────────────────────
    # PUBLIC
    # ──────────────────────────────────────────────────────

    def run(self, project, limit: int = 20, min_score: float = None) -> List[Dict]:
        """
        Vollständiger Matching-Lauf für ein ProjectRequest.
        Gibt Liste von Dicts zurück — bereit für ProjectConsultant.
        """
        if min_score is None:
            min_score = project.shortlist_threshold or self.min_score

        # Anforderungen aus Projekt extrahieren
        required_skills  = self._skill_names(project.required_skills)
        nice_skills      = self._skill_names(project.nice_to_have_skills)
        required_skills += project.extracted_technologies  # ArrayField
        required_skills  = list(set(required_skills))

        # Synonyme erweitern
        required_expanded = self._expand_with_synonyms(required_skills)
        nice_expanded     = self._expand_with_synonyms(nice_skills)

        # Stufe 1: Vorfilter
        candidates = self._stage1_filter(project, required_expanded)
        logger.info(f"Stage1: {len(candidates)} Kandidaten für {project.project_number}")

        # Stufe 2: Scoring
        scored = []
        for c in candidates:
            result = self._stage2_score(
                c, project,
                required_expanded, nice_expanded,
                required_skills,
            )
            if result['overall_score'] >= min_score:
                scored.append(result)

        # Sortieren + Rank vergeben
        scored.sort(key=lambda x: x['overall_score'], reverse=True)
        for i, r in enumerate(scored):
            r['rank'] = i + 1

        logger.info(
            f"Stage2: {len(scored)} Treffer ≥ {min_score:.2f} "
            f"für {project.project_number}"
        )
        return scored[:limit]

    # ──────────────────────────────────────────────────────
    # STUFE 1 — ORM VORFILTER
    # ──────────────────────────────────────────────────────

    def _stage1_filter(self, project, required_expanded: List[str]):
        from apps.cv_extractor.models import Consultant

        qs = Consultant.objects.filter(
            status__in=['completed', 'validated']
        ).prefetch_related(
            'skills__skill',
            'industries__industry',
            'languages__language',
            'statistics',
        )

        # Standort / Remote
        if project.location and not project.remote_possible:
            qs = qs.filter(location__icontains=project.location)

        # Mindesterfahrung
        if project.min_experience_years:
            qs = qs.filter(
                statistics__total_experience_years__gte=project.min_experience_years
            )

        # Mindestens 1 required Skill vorhanden
        if required_expanded:
            from apps.cv_extractor.models import ConsultantSkill, Skill
            skill_ids = Skill.objects.filter(
                name__in=required_expanded
            ).values_list('id', flat=True)
            if skill_ids:
                qs = qs.filter(skills__skill_id__in=skill_ids).distinct()

        # Keine -en Versionen
        qs = qs.exclude(aid__endswith='-en')

        # Deduplizieren über consultant_dir — nur neueste Version pro Person
        # MUSS vor prefetch_related passieren
        from collections import defaultdict
        def _aid_version(aid):
            try:
                parts = (aid or '').split('_')[-1].split('.')
                return tuple(int(x) for x in parts if x.isdigit())
            except:
                return (0,)

        groups = defaultdict(list)
        for c in qs.only('id', 'aid', 'consultant_dir', 'first_name', 'last_name', 'created_at')[:500]:
            key = (c.consultant_dir or f"{c.last_name}_{c.first_name}").lower().strip()
            groups[key].append((c.id, c.aid, c.created_at))

        best_ids = []
        for key, entries in groups.items():
            def _sort_key(entry):
                _id, aid, created_at = entry
                ts = created_at.timestamp() if created_at else 0
                return (_aid_version(aid), ts)
            best_id = max(entries, key=_sort_key)[0]
            best_ids.append(best_id)

        qs = Consultant.objects.filter(id__in=best_ids)

        return list(qs[:200])  # Max 200 für Scoring

    # ──────────────────────────────────────────────────────
    # STUFE 2 — SCORING
    # ──────────────────────────────────────────────────────

    def _stage2_score(
        self, consultant, project,
        required_expanded, nice_expanded,
        required_original,
    ) -> Dict:
        # Berater-Skills sammeln
        consultant_skills = {
            cs.skill.name.lower()
            for cs in consultant.skills.all()
        }

        # Skill Score (required)
        matched_required = []
        missing_required = []
        for skill in required_original:
            skill_l = skill.lower()
            # Direkt oder über Synonym
            hit = (
                skill_l in consultant_skills or
                any(s in consultant_skills for s in required_expanded
                    if skill_l in s or s in skill_l)
            )
            if hit:
                matched_required.append(skill)
            else:
                missing_required.append(skill)

        req_score = (
            len(matched_required) / max(len(required_original), 1)
        ) if required_original else 1.0

        # Skill Score (nice-to-have)
        matched_nice = [
            s for s in nice_expanded
            if s.lower() in consultant_skills
        ]
        nice_score = (
            len(matched_nice) / max(len(nice_expanded), 1)
        ) if nice_expanded else 0.0

        # Industry Score
        industry_score = self._industry_score(consultant, project)

        # Experience Score
        exp_score = self._experience_score(consultant, project)

        # Location Score
        loc_score = self._location_score(consultant, project)

        # Gesamt
        overall = (
            req_score      * self.w_req +
            nice_score     * self.w_nice +
            industry_score * self.w_industry +
            exp_score      * self.w_exp +
            loc_score      * self.w_loc
        )

        return {
            'consultant_cv':    consultant,
            'overall_score':    round(overall, 4),
            'skill_score':      round(req_score, 4),
            'industry_score':   round(industry_score, 4),
            'experience_score': round(exp_score, 4),
            'location_score':   round(loc_score, 4),
            'cert_score':       0.0,
            'matched_skills':   matched_required,
            'missing_skills':   missing_required,
            'score':            round(overall, 4),  # Alias für MatchingService
            'match_reason':     '',  # wird von AI Reranker gefüllt
            'skill_details':    {
                'matched_required': matched_required,
                'missing_required': missing_required,
                'matched_nice':     matched_nice,
            },
        }

    # ──────────────────────────────────────────────────────
    # TEIL-SCORER
    # ──────────────────────────────────────────────────────

    def _industry_score(self, consultant, project) -> float:
        if not project.extracted_requirements:
            return 0.5  # Neutral wenn keine Branche gefordert

        req_industries = []
        if isinstance(project.extracted_requirements, dict):
            req_industries = project.extracted_requirements.get('industries', [])
        if not req_industries:
            return 0.5

        consultant_industries = {
            ci.industry.name.lower()
            for ci in consultant.industries.all()
        }
        matches = sum(
            1 for ind in req_industries
            if ind.lower() in consultant_industries
        )
        return min(matches / max(len(req_industries), 1), 1.0)

    def _experience_score(self, consultant, project) -> float:
        if not project.min_experience_years:
            return 1.0
        try:
            years = consultant.statistics.total_experience_years
        except Exception:
            years = 0
        if years >= project.min_experience_years:
            return 1.0
        if years > 0:
            return round(years / project.min_experience_years, 2)
        return 0.0

    def _location_score(self, consultant, project) -> float:
        if not project.location:
            return 1.0
        if project.remote_possible:
            return 0.8  # Remote immer ok
        loc = (consultant.location or '').lower()
        req = project.location.lower()
        if req in loc or loc in req:
            return 1.0
        return 0.2

    # ──────────────────────────────────────────────────────
    # SYNONYM-ERWEITERUNG
    # ──────────────────────────────────────────────────────

    def _expand_with_synonyms(self, skills: List[str]) -> List[str]:
        """Erweitert Skills um Synonyme aus SkillRelation"""
        if not skills:
            return []
        try:
            from apps.cv_extractor.models import SkillRelation
            expanded = list(skills)
            relations = SkillRelation.objects.filter(
                term_from__in=skills,
                relation_type__in=['synonym', 'related'],
            ).values_list('term_to', flat=True)
            expanded += list(relations)
            # Auch umgekehrt
            relations_rev = SkillRelation.objects.filter(
                term_to__in=skills,
                relation_type='synonym',
            ).values_list('term_from', flat=True)
            expanded += list(relations_rev)
            return list(set(expanded))
        except Exception as e:
            logger.warning(f"Synonym-Erweiterung fehlgeschlagen: {e}")
            return skills

    # ──────────────────────────────────────────────────────
    # HILFSMETHODEN
    # ──────────────────────────────────────────────────────

    def _skill_names(self, skills_field) -> List[str]:
        """Extrahiert Skill-Namen aus JSONField [{"name":"SAP",...}] oder [str]"""
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
