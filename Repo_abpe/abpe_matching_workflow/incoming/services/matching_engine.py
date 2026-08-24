"""
ABpE Matching Engine v2.1
Direkt gegen cv_extractor.Consultant — Stufen:
  1. ORM Vorfilter (status, skills, location) + optional ES-Recall (Probe-Index)
  2. Python Scoring mit ConsultantSkill.weight (Coverage + Strength)
  3. Synonym-Erweiterung via SkillRelation
"""
import logging
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple

logger = logging.getLogger(__name__)


def _cfg() -> Dict:
    try:
        p = Path(__file__).resolve().parent.parent.parent.parent / 'settings.json'
        return json.loads(p.read_text(encoding='utf-8')).get('matching', {})
    except Exception:
        return {}


def _es_hosts() -> List[str]:
    try:
        p = Path(__file__).resolve().parent.parent.parent.parent / 'settings.json'
        cfg = json.loads(p.read_text(encoding='utf-8'))
        hosts = (cfg.get('elasticsearch') or {}).get('hosts') or ['http://localhost:9200']
    except Exception:
        hosts = ['http://localhost:9200']
    out = []
    for h in hosts:
        h = (h or '').strip()
        if not h:
            continue
        if '://' not in h:
            h = f'http://{h}'
        out.append(h)
    return out or ['http://localhost:9200']


class MatchingEngine:

    def __init__(self):
        cfg = _cfg()
        s = cfg.get('scoring', {})
        self.w_req = s.get('weight_skills_required', 0.50)
        self.w_nice = s.get('weight_skills_nice', 0.20)
        self.w_industry = s.get('weight_industry', 0.15)
        self.w_exp = s.get('weight_experience', 0.10)
        self.w_loc = s.get('weight_location', 0.05)
        self.min_score = s.get('min_score_threshold', 0.30)
        # Skill-Score: Anteil Treffer vs. Stärke (ConsultantSkill.weight)
        self.cov_blend = float(s.get('skill_coverage_blend', 0.45))
        self.str_blend = float(s.get('skill_strength_blend', 0.55))
        # Soft-Default-Gewicht wenn ConsultantSkill.weight fehlt
        self.default_skill_weight = float(s.get('default_skill_weight', 0.50))
        self.es_recall_cfg = dict(cfg.get('es_recall') or {})

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

        # Projekt-Gewichtungen überschreiben settings-Defaults
        w_req = getattr(project, 'weight_skills_required', None) or self.w_req
        w_nice = getattr(project, 'weight_skills_nice', None) or self.w_nice
        w_industry = getattr(project, 'weight_industry', None) or self.w_industry
        w_exp = getattr(project, 'weight_experience', None) or self.w_exp
        w_loc = getattr(project, 'weight_location', None) or self.w_loc

        required_skills = self._skill_names(project.required_skills)
        nice_skills = self._skill_names(project.nice_to_have_skills)
        required_skills += list(project.extracted_technologies or [])
        required_skills = list(dict.fromkeys(required_skills))  # stabil dedupe

        req_weights = self._skill_request_weights(project.required_skills, required_skills)

        if not required_skills and not nice_skills:
            logger.warning(
                "Matching abgebrochen: Anfrage %s hat keine required_skills/"
                "extracted_technologies — würde Blindlinge liefern.",
                getattr(project, 'project_number', project.id),
            )
            return []

        required_expanded = self._expand_with_synonyms(required_skills)
        nice_expanded = self._expand_with_synonyms(nice_skills)

        candidates = self._stage1_filter(project, required_expanded)
        logger.info(f"Stage1 ORM: {len(candidates)} Kandidaten für {project.project_number}")

        es_extra = self._stage1_es_recall(project, required_skills, {c.id for c in candidates})
        if es_extra:
            candidates = list(candidates) + es_extra
            logger.info(
                f"Stage1 ES-Recall: +{len(es_extra)} → {len(candidates)} "
                f"für {project.project_number}"
            )

        scored = []
        for c in candidates:
            result = self._stage2_score(
                c, project,
                required_expanded, nice_expanded,
                required_skills,
                req_weights,
                w_req=w_req, w_nice=w_nice, w_industry=w_industry,
                w_exp=w_exp, w_loc=w_loc,
            )
            if result['overall_score'] >= min_score:
                scored.append(result)

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

        if project.location and not project.remote_possible:
            qs = qs.filter(location__icontains=project.location)

        if project.min_experience_years:
            qs = qs.filter(
                statistics__total_experience_years__gte=project.min_experience_years
            )

        if required_expanded:
            from apps.cv_extractor.models import Skill
            skill_ids = Skill.objects.filter(
                name__in=required_expanded
            ).values_list('id', flat=True)
            if skill_ids:
                qs = qs.filter(skills__skill_id__in=skill_ids).distinct()

        qs = qs.exclude(aid__endswith='-en')

        from collections import defaultdict

        def _aid_version(aid):
            try:
                parts = (aid or '').split('_')[-1].split('.')
                return tuple(int(x) for x in parts if x.isdigit())
            except Exception:
                return (0,)

        groups = defaultdict(list)
        for c in qs.only('id', 'aid', 'consultant_dir', 'first_name', 'last_name', 'created_at')[:500]:
            key = (c.consultant_dir or f"{c.last_name}_{c.first_name}").lower().strip()
            groups[key].append((c.id, c.aid, c.created_at))

        best_ids = []
        for _key, entries in groups.items():
            def _sort_key(entry):
                _id, aid, created_at = entry
                ts = created_at.timestamp() if created_at else 0
                return (_aid_version(aid), ts)
            best_id = max(entries, key=_sort_key)[0]
            best_ids.append(best_id)

        qs = Consultant.objects.filter(id__in=best_ids).prefetch_related(
            'skills__skill',
            'industries__industry',
            'languages__language',
            'statistics',
        )

        return list(qs[:200])

    # ──────────────────────────────────────────────────────
    # STUFE 1b — ES RECALL (Probe-Index, fail-open)
    # ──────────────────────────────────────────────────────

    def _stage1_es_recall(self, project, required_skills: List[str], existing_ids: Set[int]):
        """
        Holt zusätzliche Kandidaten aus abpe_matching_profiles_probe (Contact-Docs).
        Nur Docs mit aid / Name → Consultant. Fehler → leere Liste (ORM bleibt).
        """
        cfg = self.es_recall_cfg
        if cfg.get('enabled') is False:
            return []
        if not required_skills:
            return []

        index = cfg.get('index') or 'abpe_matching_profiles_probe'
        size = int(cfg.get('size') or 50)

        try:
            from elasticsearch import Elasticsearch
        except Exception:
            logger.info('ES-Recall skip: elasticsearch-Paket fehlt')
            return []

        try:
            es = Elasticsearch(_es_hosts(), verify_certs=False, request_timeout=30)
            if not es.ping():
                logger.warning('ES-Recall skip: ping failed')
                return []
            if not es.indices.exists(index=index):
                logger.info('ES-Recall skip: Index %s fehlt', index)
                return []

            q_skills = [s.lower() for s in required_skills[:8]]
            should = [{'term': {'skill_names': s}} for s in q_skills]
            should += [{'match': {'body_text': {'query': s, 'boost': 0.3}}} for s in q_skills]
            # nested weight boost — optional, soft
            should.append({
                'nested': {
                    'path': 'skill_weight_pairs',
                    'query': {
                        'bool': {
                            'must': [
                                {'terms': {'skill_weight_pairs.skill': q_skills}},
                            ]
                        }
                    },
                    'score_mode': 'sum',
                    'boost': 2.0,
                }
            })

            res = es.search(
                index=index,
                size=size,
                query={'bool': {'should': should, 'minimum_should_match': 1}},
                _source=[
                    'aid', 'consultant_dir', 'full_name', 'first_name', 'last_name',
                    'crm_contact_id', 'skill_names', 'skill_weight_pairs', 'weight_source',
                ],
            )
        except Exception as e:
            logger.warning('ES-Recall fehlgeschlagen: %s', e)
            return []

        hits = (res.get('hits') or {}).get('hits') or []
        if not hits:
            return []

        aids: List[str] = []
        dirs: List[str] = []
        name_pairs: List[Tuple[str, str]] = []
        for h in hits:
            src = h.get('_source') or {}
            aid = (src.get('aid') or '').strip()
            cdir = (src.get('consultant_dir') or '').strip()
            fn = (src.get('first_name') or '').strip()
            ln = (src.get('last_name') or '').strip()
            if aid:
                aids.append(aid)
            if cdir:
                dirs.append(cdir)
            if fn and ln:
                name_pairs.append((fn, ln))

        from apps.cv_extractor.models import Consultant

        found = {}
        if aids:
            for c in Consultant.objects.filter(
                aid__in=aids, status__in=['completed', 'validated']
            ).exclude(aid__endswith='-en').prefetch_related(
                'skills__skill', 'industries__industry', 'statistics',
            ):
                if c.id not in existing_ids:
                    found[c.id] = c

        if dirs:
            for c in Consultant.objects.filter(
                consultant_dir__in=dirs, status__in=['completed', 'validated']
            ).exclude(aid__endswith='-en').prefetch_related(
                'skills__skill', 'industries__industry', 'statistics',
            ):
                if c.id not in existing_ids and c.id not in found:
                    found[c.id] = c

        # Name-Fallback nur wenn eindeutig
        for fn, ln in name_pairs[:30]:
            qs = Consultant.objects.filter(
                first_name__iexact=fn,
                last_name__iexact=ln,
                status__in=['completed', 'validated'],
            ).exclude(aid__endswith='-en')
            if qs.count() != 1:
                continue
            c = qs.prefetch_related(
                'skills__skill', 'industries__industry', 'statistics',
            ).first()
            if c and c.id not in existing_ids and c.id not in found:
                found[c.id] = c

        extra = list(found.values())
        max_extra = int(cfg.get('max_extra') or 80)
        return extra[:max_extra]

    # ──────────────────────────────────────────────────────
    # STUFE 2 — SCORING
    # ──────────────────────────────────────────────────────

    def _stage2_score(
        self, consultant, project,
        required_expanded, nice_expanded,
        required_original,
        req_weights: Optional[Dict[str, float]] = None,
        *,
        w_req=None, w_nice=None, w_industry=None, w_exp=None, w_loc=None,
    ) -> Dict:
        w_req = self.w_req if w_req is None else w_req
        w_nice = self.w_nice if w_nice is None else w_nice
        w_industry = self.w_industry if w_industry is None else w_industry
        w_exp = self.w_exp if w_exp is None else w_exp
        w_loc = self.w_loc if w_loc is None else w_loc
        req_weights = req_weights or {}

        # name_lc → max ConsultantSkill.weight
        consultant_weights = self._consultant_skill_weights(consultant)
        consultant_skills = set(consultant_weights.keys())

        matched_required = []
        missing_required = []
        matched_weights = []  # (skill, c_weight, req_weight)
        coverage_num = 0.0
        coverage_den = 0.0
        strength_sum = 0.0

        if not required_original:
            req_score = 0.0
            coverage = 0.0
            strength = 0.0
        else:
            for skill in required_original:
                skill_l = skill.lower()
                rw = float(req_weights.get(skill_l, 1.0) or 1.0)
                coverage_den += rw

                hit_name, hit_w = self._best_skill_hit(
                    skill_l, required_expanded, consultant_weights
                )
                if hit_name is not None:
                    matched_required.append(skill)
                    matched_weights.append({
                        'skill': skill,
                        'matched_as': hit_name,
                        'consultant_weight': round(hit_w, 4),
                        'request_weight': round(rw, 4),
                    })
                    coverage_num += rw
                    strength_sum += hit_w * rw
                else:
                    missing_required.append(skill)

            coverage = coverage_num / max(coverage_den, 1e-9)
            strength = strength_sum / max(coverage_den, 1e-9)
            # Blend; Summe der Blends normalisieren falls Config unsauber
            blend = max(self.cov_blend + self.str_blend, 1e-9)
            req_score = (self.cov_blend * coverage + self.str_blend * strength) / blend

        matched_nice = [
            s for s in nice_expanded
            if s.lower() in consultant_skills
        ]
        nice_score = (
            len(matched_nice) / max(len(nice_expanded), 1)
        ) if nice_expanded else 0.0

        industry_score = self._industry_score(consultant, project)
        exp_score = self._experience_score(consultant, project)
        loc_score = self._location_score(consultant, project)

        overall = (
            req_score * w_req +
            nice_score * w_nice +
            industry_score * w_industry +
            exp_score * w_exp +
            loc_score * w_loc
        )

        return {
            'consultant_cv': consultant,
            'overall_score': round(overall, 4),
            'skill_score': round(req_score, 4),
            'industry_score': round(industry_score, 4),
            'experience_score': round(exp_score, 4),
            'location_score': round(loc_score, 4),
            'cert_score': 0.0,
            'matched_skills': matched_required,
            'missing_skills': missing_required,
            'score': round(overall, 4),
            'match_reason': '',
            'skill_details': {
                'mode': 'weighted_v1',
                'coverage': round(coverage if required_original else 0.0, 4),
                'strength': round(strength if required_original else 0.0, 4),
                'coverage_blend': self.cov_blend,
                'strength_blend': self.str_blend,
                'matched_required': matched_required,
                'missing_required': missing_required,
                'matched_nice': matched_nice,
                'matched_weights': matched_weights,
            },
        }

    def _consultant_skill_weights(self, consultant) -> Dict[str, float]:
        out: Dict[str, float] = {}
        try:
            skills = consultant.skills.all()
        except Exception:
            return out
        for cs in skills:
            raw = getattr(getattr(cs, 'skill', None), 'name', None) or ''
            name = raw.strip().lower()
            if not name:
                continue
            try:
                w = float(getattr(cs, 'weight', None))
            except (TypeError, ValueError):
                w = self.default_skill_weight
            if w != w:  # NaN
                w = self.default_skill_weight
            w = max(0.0, min(float(w), 1.0))
            if name not in out or w > out[name]:
                out[name] = w
        return out

    def _best_skill_hit(
        self,
        skill_l: str,
        required_expanded: List[str],
        consultant_weights: Dict[str, float],
    ) -> Tuple[Optional[str], float]:
        """Beste (Name, Weight)-Treffer für ein Required-Skill inkl. Synonyme."""
        if skill_l in consultant_weights:
            return skill_l, consultant_weights[skill_l]

        best_name = None
        best_w = -1.0
        for name, w in consultant_weights.items():
            # Direkt-Fuzzy (wie v2)
            if skill_l in name or name in skill_l:
                if w > best_w:
                    best_name, best_w = name, w
                continue
            # Synonym-Menge: expanded-Token liegt in consultant-skill oder umgekehrt
            for syn in required_expanded:
                syn_l = syn.lower()
                if skill_l not in syn_l and syn_l not in skill_l:
                    continue
                if syn_l == name or syn_l in name or name in syn_l:
                    if w > best_w:
                        best_name, best_w = name, w
        if best_name is None:
            return None, 0.0
        return best_name, best_w

    # ──────────────────────────────────────────────────────
    # TEIL-SCORER
    # ──────────────────────────────────────────────────────

    def _industry_score(self, consultant, project) -> float:
        if not project.extracted_requirements:
            return 0.5

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
            return 0.8
        loc = (consultant.location or '').lower()
        req = project.location.lower()
        if req in loc or loc in req:
            return 1.0
        return 0.2

    # ──────────────────────────────────────────────────────
    # SYNONYM-ERWEITERUNG
    # ──────────────────────────────────────────────────────

    def _expand_with_synonyms(self, skills: List[str]) -> List[str]:
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

    def _skill_request_weights(
        self, skills_field, required_names: List[str]
    ) -> Dict[str, float]:
        """name_lc → Anfrage-Gewicht (Default 1.0; extracted_technologies ohne Extra-Gewicht)."""
        out = {n.lower(): 1.0 for n in required_names}
        if not skills_field:
            return out
        for s in skills_field:
            if isinstance(s, dict):
                n = (s.get('name') or '').strip().lower()
                if not n:
                    continue
                try:
                    w = float(s.get('weight', 1.0))
                except (TypeError, ValueError):
                    w = 1.0
                out[n] = max(0.0, min(w, 5.0))
        return out
