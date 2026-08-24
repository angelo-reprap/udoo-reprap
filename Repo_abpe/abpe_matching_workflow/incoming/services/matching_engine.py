"""
ABpE Matching Engine v2.1
Direkt gegen cv_extractor.Consultant — Stufen:
  1. ORM Vorfilter (status, skills, location) + optional ES-Recall (Probe-Index)
  2. Python Scoring mit ConsultantSkill.weight (Coverage + Strength)
  3. Synonym-Erweiterung via SkillRelation
"""
import logging
import json
import re
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
        # Skill-Score: Coverage × Gewichts-Modulation (kein Doppel-Penalty)
        self.cov_blend = float(s.get('skill_coverage_blend', 0.45))
        self.str_blend = float(s.get('skill_strength_blend', 0.55))
        # coverage^power: bei vielen Required-Skills (z.B. 10) sind 5/10 Treffer
        # sonst strukturell unter threshold 0.5 (w_req=0.5 + Neutrals ≈0.22).
        self.coverage_power = float(s.get('skill_coverage_power', 0.62))
        # Soft-Default-Gewicht wenn ConsultantSkill.weight fehlt
        self.default_skill_weight = float(s.get('default_skill_weight', 0.50))
        self.es_recall_cfg = dict(cfg.get('es_recall') or {})
        self.last_external_meta: Dict[str, Any] = {}

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

        required_expanded = self._expand_with_synonyms(
            required_skills, include_related=True,
        )
        nice_expanded = self._expand_with_synonyms(
            nice_skills, include_related=True,
        )

        candidates = self._stage1_filter(project, required_expanded)
        logger.info(f"Stage1 ORM: {len(candidates)} Kandidaten für {project.project_number}")

        db_ids = {c.id for c in candidates}
        es_extra = self._stage1_es_recall(project, required_skills, db_ids)
        es_ids = {c.id for c in es_extra}
        if es_extra:
            candidates = list(candidates) + es_extra
            logger.info(
                f"Stage1 ES-Recall: +{len(es_extra)} → {len(candidates)} "
                f"für {project.project_number}"
            )

        # Quellen-Tag (db / es; gulp/flm über External-Recall)
        source_by_id = {cid: 'db' for cid in db_ids}
        for cid in es_ids:
            source_by_id[cid] = 'es'

        # Gulp/FLM: bekannt+kontaktierbar mergen; Rest → Backoffice (kein Duplikat)
        external_meta = {'known_results': [], 'backoffice': [], 'stats': {}}
        try:
            from .matching_external_recall import (
                classify_external_hits,
                store_backoffice_on_project,
            )
            ext_cfg = dict((_cfg().get('external_recall') or {}))
            if ext_cfg.get('enabled') is not False:
                external_meta = classify_external_hits(
                    project,
                    existing_consultant_ids=set(source_by_id.keys()),
                    min_overlap=int(ext_cfg.get('min_overlap') or 1),
                    gulp_pages=int(ext_cfg.get('gulp_pages') or 2),
                    flm_pages=int(ext_cfg.get('flm_pages') or 2),
                )
                for kr in external_meta.get('known_results') or []:
                    cons = kr.get('consultant_cv')
                    if cons is None or cons.id in source_by_id:
                        continue
                    candidates.append(cons)
                    source_by_id[cons.id] = kr.get('match_source') or 'gulp'
                    # CRM-Link an Consultant hängen für Stage2-Nacharbeit
                    setattr(cons, '_matching_external', kr)
                self.last_external_meta = external_meta

                logger.info(
                    'Stage1 External: known=%s backoffice=%s stats=%s',
                    len(external_meta.get('known_results') or []),
                    len(external_meta.get('backoffice') or []),
                    external_meta.get('stats'),
                )
        except Exception as exc:
            logger.warning('External-Recall fehlgeschlagen: %s', exc)
            self.last_external_meta = {}

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
            src = source_by_id.get(c.id, 'db')
            result['match_source'] = src
            result['match_sources'] = [src]
            sd = result.get('skill_details') or {}
            sd['match_source'] = src
            sd['match_sources'] = [src]
            ext = getattr(c, '_matching_external', None)
            if isinstance(ext, dict):
                sd['crm_link'] = ext.get('crm_link')
                sd['crm_link_status'] = ext.get('crm_link_status')
                sd['profile_refresh_suggested'] = ext.get('profile_refresh_suggested')
                sd['external_hit'] = ext.get('external_hit')
                result['email'] = ext.get('email') or ''
                result['phone'] = ext.get('phone') or ''
                result['crm_link_status'] = ext.get('crm_link_status')
            result['skill_details'] = sd
            if result['overall_score'] >= min_score:
                scored.append(result)

        scored.sort(key=lambda x: x['overall_score'], reverse=True)
        for i, r in enumerate(scored):
            r['rank'] = i + 1

        # Backoffice-Counts für Task/API
        # (bereits in self.last_external_meta)

        logger.info(
            f"Stage2: {len(scored)} Treffer ≥ {min_score:.2f} "
            f"für {project.project_number} "
            f"(db={sum(1 for r in scored if r.get('match_source')=='db')} "
            f"es={sum(1 for r in scored if r.get('match_source')=='es')} "
            f"gulp={sum(1 for r in scored if r.get('match_source')=='gulp')} "
            f"flm={sum(1 for r in scored if r.get('match_source')=='flm')})"
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
        strength_num = 0.0  # nur Treffer — Misses nicht nochmal als 0 einrechnen
        strength_den = 0.0
        syn_cache: Dict[str, List[str]] = {}

        if not required_original:
            req_score = 0.0
            coverage = 0.0
            strength = 0.0
            quality = 0.0
        else:
            for skill in required_original:
                skill_l = skill.lower()
                rw = float(req_weights.get(skill_l, 1.0) or 1.0)
                coverage_den += rw

                # Per-Skill-Synonyme (nicht die flache Gesamt-Liste) —
                # sonst greifen Relationen ohne Substring-Überlappung (Java↔JVM) nicht.
                if skill_l not in syn_cache:
                    # Scoring: nur echte Synonyme — "related" (Docker↔K8s) erzeugt False-Positives
                    syn_cache[skill_l] = self._expand_with_synonyms(
                        [skill], include_related=False,
                    )
                hit_name, hit_w = self._best_skill_hit(
                    skill_l, syn_cache[skill_l], consultant_weights
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
                    strength_num += hit_w * rw
                    strength_den += rw
                else:
                    missing_required.append(skill)

            coverage = coverage_num / max(coverage_den, 1e-9)
            # Strength = Ø Gewicht nur unter den Treffern (Ranking-Signal).
            # Misses stecken schon in coverage — sonst Doppel-Penalty → oft 0 Shortlist.
            strength = (
                strength_num / max(strength_den, 1e-9)
            ) if strength_den > 0 else 0.0
            blend = max(self.cov_blend + self.str_blend, 1e-9)
            quality = (self.cov_blend * 1.0 + self.str_blend * strength) / blend
            # Soft-Coverage: 5/10 Skills → nicht halb so „schlecht“ wie binär
            power = self.coverage_power if self.coverage_power > 0 else 1.0
            coverage_eff = coverage ** power if coverage > 0 else 0.0
            req_score = coverage_eff * quality

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
                'mode': 'weighted_v4',
                'coverage': round(coverage if required_original else 0.0, 4),
                'coverage_eff': round(
                    (
                        (coverage ** self.coverage_power)
                        if (required_original and coverage > 0 and self.coverage_power > 0)
                        else (coverage if required_original else 0.0)
                    ),
                    4,
                ),
                'strength': round(strength if required_original else 0.0, 4),
                'quality': round(quality if required_original else 0.0, 4),
                'coverage_blend': self.cov_blend,
                'strength_blend': self.str_blend,
                'coverage_power': self.coverage_power,
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
            name = self._normalize_skill_label(raw)
            if not name or not self._is_matchable_skill_label(name):
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
        skill_synonyms: List[str],
        consultant_weights: Dict[str, float],
    ) -> Tuple[Optional[str], float]:
        """
        Strikter Match: Exact / Whole-Word / Synonym — kein Substring (java≠javascript).
        """
        req_norm = self._normalize_skill_label(skill_l)
        want = set()
        if req_norm:
            want.add(req_norm)
            want |= self._skill_match_tokens(req_norm)
        for syn in skill_synonyms or []:
            sn = self._normalize_skill_label(syn)
            if not sn or not self._is_matchable_skill_label(sn):
                continue
            want.add(sn)
            want |= self._skill_match_tokens(sn)
        # nur brauchbare Tokens
        want = {t for t in want if t and len(t) >= 2}
        if not want:
            return None, 0.0

        best_name = None
        best_w = -1.0
        best_rank = 99  # niedriger = besser (exact vor whole-word)

        for name, w in consultant_weights.items():
            if self._is_blocked_alias(req_norm, name):
                continue
            rank = self._match_rank(want, req_norm, name)
            if rank is None:
                continue
            if rank < best_rank or (rank == best_rank and w > best_w):
                best_rank = rank
                best_name = name
                best_w = w

        if best_name is None:
            return None, 0.0
        return best_name, best_w

    def _match_rank(self, want: Set[str], req_norm: str, name: str) -> Optional[int]:
        """0=exact, 1=token-exact, 2=whole-word; None=kein Treffer."""
        if name == req_norm or name in want:
            return 0
        name_tokens = self._skill_match_tokens(name)
        if not self._is_matchable_skill_label(name):
            return None
        primary = self._primary_token(req_norm)
        # primäres Required-Token muss als Ganzes vorkommen (kein Generic)
        if (
            primary
            and primary not in self._GENERIC_MATCH_TOKENS
            and primary in name_tokens
            and primary in want
        ):
            if self._is_blocked_alias(req_norm, name):
                return None
            return 1
        # weitere Want-Tokens ≥ 4 Zeichen als Whole-Word im Namen
        for tok in want:
            if len(tok) < 4 or tok in self._GENERIC_MATCH_TOKENS:
                continue
            # Generische Tokens dürfen nicht allein matchen (tools, test, …)
            if self._whole_word(tok, name):
                if self._is_blocked_alias(req_norm, name):
                    return None
                # Whole-word auf Consultant-Label: Token sollte „nah“ am Required sein
                # (gleicher Primary oder Exact-Synonym-Label), sonst mercury testtools etc.
                if tok == primary or tok == req_norm or tok in {
                    self._primary_token(w) for w in want if ' ' not in w
                }:
                    return 2
        return None

    _GENERIC_MATCH_TOKENS = frozenset({
        'test', 'tools', 'tool', 'web', 'start', 'pipeline', 'pipelines',
        'script', 'server', 'client', 'data', 'cloud', 'api', 'rpc',
        'ide', 'framework', 'library', 'service', 'services',
    })

    # Bekannte Cross-Tech-False-Positives (auch bei DB-Synonym/Related)
    _ALIAS_BLOCKS = {
        'docker': frozenset({
            'kubernetes', 'k8s', 'openshift', 'helm', 'rancher', 'aks', 'eks', 'gke',
        }),
        'kubernetes': frozenset({'docker', 'docker-compose', 'docker swarm'}),
        'jenkins': frozenset({
            'bitbucket', 'gitlab', 'github', 'gitea', 'svn', 'mercurial',
        }),
        'java': frozenset({'rpc', 'xml-rpc', 'json-rpc', 'grpc'}),
        'groovy': frozenset({'jenkins'}),  # „jenkins (groovy)“ ok via exact name; pure jenkins≠groovy
    }

    @staticmethod
    def _is_blocked_alias(req: str, name: str) -> bool:
        """Bekannte False-Positives: java≠javascript, docker≠k8s, jenkins≠bitbucket."""
        r = (req or '').strip().lower()
        n = (name or '').strip().lower()
        n_compact = n.replace(' ', '')

        if r == 'java' or r.startswith('java '):
            if 'javascript' in n_compact or 'typescript' in n_compact:
                return True
            if 'java' in n_compact and 'script' in n_compact:
                return True

        if r in ('js', 'javascript') and n == 'java':
            return True

        # Primary-Key der Request gegen Alias-Block des Match-Namens
        req_primary = MatchingEngine._primary_token(r)
        name_primary = MatchingEngine._primary_token(n)
        # „jenkins (groovy)“ darf Groovy matchen
        if req_primary == 'groovy' and 'groovy' in n:
            return False
        blocks = MatchingEngine._ALIAS_BLOCKS.get(req_primary) or MatchingEngine._ALIAS_BLOCKS.get(r)
        if blocks:
            if name_primary in blocks or n in blocks or n_compact in blocks:
                return True
            for b in blocks:
                if MatchingEngine._whole_word(b, n):
                    return True

        if req_primary == 'groovy' and name_primary == 'jenkins' and 'groovy' not in n:
            return True

        return False

    def _expand_with_synonyms(
        self, skills: List[str], *, include_related: bool = False,
    ) -> List[str]:
        if not skills:
            return []
        try:
            from apps.cv_extractor.models import SkillRelation
            expanded = list(skills)
            types = ['synonym', 'related'] if include_related else ['synonym']
            relations = SkillRelation.objects.filter(
                term_from__in=skills,
                relation_type__in=types,
            ).values_list('term_to', flat=True)
            expanded += list(relations)
            # Rückrichtung nur für echte Synonyme
            relations_rev = SkillRelation.objects.filter(
                term_to__in=skills,
                relation_type='synonym',
            ).values_list('term_from', flat=True)
            expanded += list(relations_rev)
            return list(set(expanded))
        except Exception as e:
            logger.warning(f"Synonym-Erweiterung fehlgeschlagen: {e}")
            return skills
    @staticmethod
    def _primary_token(skill_l: str) -> str:
        s = (skill_l or '').strip().lower()
        if not s:
            return ''
        compact = ''.join(ch for ch in s if ch.isalnum())
        if s in ('ci/cd', 'ci-cd') or compact == 'cicd':
            return 'cicd'
        parts = re.split(r'[\s/|,;+]+', s)
        parts = [p.strip().strip('.') for p in parts if p.strip()]
        if not parts:
            return compact or s
        best = max(parts, key=len)
        if best.endswith('.js') and len(best) > 3:
            return best[:-3]
        return best

    @staticmethod
    def _whole_word(tok: str, text: str) -> bool:
        if not tok or not text:
            return False
        return re.search(
            rf'(?<![a-z0-9]){re.escape(tok)}(?![a-z0-9])',
            text,
            flags=re.IGNORECASE,
        ) is not None

    @staticmethod
    def _normalize_skill_label(raw: str) -> str:
        s = (raw or '').strip().lower()
        s = s.replace('\uf0b7', ' ').replace('', ' ')
        s = re.sub(r'\s+', ' ', s).strip(' .-•\t')
        return s

    @staticmethod
    def _is_matchable_skill_label(name: str) -> bool:
        """Verwirft Prosa/Müll-Skills aus der CV-Pipeline fürs Matching."""
        n = (name or '').strip()
        if len(n) < 2 or len(n) > 40:
            return False
        low = n.lower()
        if low.count(' ') > 3:
            return False
        junk = (
            'kenntnisse', 'erfahrung', 'grundlagen', 'dokumentation',
            'erstellung', 'migration', 'bereitstellung', 'konfiguration mit',
            'für die', ' mit ', ' und ', ' von ', ' einiger ', 'pipelines',
        )
        if low in ('dokumentation', 'documentation'):
            return False
        if any(j in low for j in junk) and low.count(' ') >= 1:
            return False
        if re.search(r'(für die|mit der|erstellung von|migration von)', low):
            return False
        return True

    @staticmethod
    def _skill_match_tokens(raw: str) -> Set[str]:
        """Normalisierte Match-Tokens: 'CI/CD'→{ci/cd,cicd}, 'nut.js'→{nut.js,nut}."""
        s = (raw or '').strip().lower()
        if not s:
            return set()
        out = {s}
        compact = ''.join(ch for ch in s if ch.isalnum())
        if compact and compact != s:
            out.add(compact)
        for part in re.split(r'[\s/|,;+]+', s):
            part = part.strip().strip('.')
            if not part:
                continue
            out.add(part)
            if part.endswith('.js') and len(part) > 3:
                out.add(part[:-3])
            if '.' in part:
                out.add(part.replace('.', ''))
        cleaned = set()
        for t in out:
            if len(t) >= 3 or t == s:
                cleaned.add(t)
        return cleaned

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
