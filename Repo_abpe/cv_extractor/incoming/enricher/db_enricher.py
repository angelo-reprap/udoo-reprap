"""
db_enricher.py – Stufe 2, parallel, LLM (DeepSeek)

Aufgaben (ein LLM-Call):
  - normalized.professional.summary (3 Saetze, Deutsch)
  - matching: preferred_roles, preferred_industries,
              must_have_skills, nice_to_have_skills,
              role_classification, overall_score
  - statistics: total_experience_years (edv_experience_since oder LLM),
                demand_index, top_skills, top_certifications

Spiegel in DB-Tabellen:
  - ConsultantStatistics
  - ConsultantMatching
"""

import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional

from django.db import transaction

logger = logging.getLogger(__name__)

ROLE_NAMES = {
    1: 'Administrator', 2: 'Entwickler', 3: 'Architekt',
    4: 'Projektleiter',  5: 'Berater'
}
LANDSCAPE_NAMES = {
    1: 'Client/Server', 2: 'Netzwerk/Security', 3: 'Web/Software',
    4: 'Cloud/DevOps',  5: 'Embedded/IoT'
}
LEVEL_NAMES = {
    1: 'Junior', 2: 'Senior', 3: 'Experte',
    4: 'Senior Experte', 5: 'Master'
}


class DBEnricher:

    def __init__(self):
        logger.info("DBEnricher initialisiert")

    @transaction.atomic
    def enrich(self, consultant, master_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Hauptmethode – LLM analysiert den Consultant und fuellt:
        normalized.professional.summary, matching, statistics
        """
        logger.info(f"DBEnricher (LLM) fuer {consultant.aid}")

        # Stufe 1: Statistiken berechnen (kein LLM)
        master_json = self._calculate_statistics(consultant, master_json)

        # Stufe 2: LLM-Analyse (ein Call fuer alles)
        llm_result = self._run_llm_analysis(consultant, master_json)

        if llm_result:
            master_json = self._apply_llm_result(
                master_json, llm_result, consultant
            )
        else:
            logger.warning(f"LLM-Analyse fehlgeschlagen fuer {consultant.aid}")
            master_json = self._apply_defaults(master_json, consultant)

        # DB-Tabellen spiegeln
        self._save_to_db_tables(consultant, master_json)

        # pipeline.step aktualisieren
        master_json.setdefault('metadata', {}).setdefault(
            'pipeline', {}
        )['step'] = 'enriched'
        master_json.setdefault('audit', {})['enriched_at']  = datetime.now().isoformat()
        master_json['audit']['enriched_by']  = 'deepseek-chat'

        # Consultant-Status aktualisieren
        consultant.pipeline_step = 'enriched'
        consultant.status        = 'enriched'
        consultant.save(update_fields=['pipeline_step', 'status', 'updated_at'])

        logger.info(f"DBEnricher abgeschlossen fuer {consultant.aid}")
        return master_json

    def _calculate_statistics(self, consultant,
                               master_json: Dict) -> Dict:
        """Berechnet Statistiken ohne LLM."""
        extracted = master_json.get('extracted_data', {})

        # Erfahrungsjahre: zuerst edv_experience_since
        total_years = 0
        if consultant.edv_experience_since:
            total_years = datetime.now().year - consultant.edv_experience_since
        # Fallback: aus Projekt-Zeitraeumen berechnen
        if total_years == 0:
            total_years = self._calc_years_from_projects(
                extracted.get('experience', [])
            )

        project_count = len(extracted.get('experience', []))
        cert_count    = len(extracted.get('certifications', []))

        # Skill-Zaehlung - aus DB (inkl. Projekt-Skills aus Schritt 10)
        from apps.cv_extractor.models import ConsultantSkill
        db_skills = list(ConsultantSkill.objects.filter(
            consultant=consultant
        ).select_related('skill').order_by('-weight'))

        all_skills  = [cs.skill.name for cs in db_skills]
        skill_count = len(all_skills)

        # Unique Kategorien aus DB
        unique_cats = len(set(
            cs.skill.category_name for cs in db_skills
            if cs.skill.category_name
        ))

        # Top Skills nach Gewichtung aus DB
        top_skills = [cs.skill.name for cs in db_skills[:10]]

        # Top Certifications
        top_certs = [
            c['name'] for c in extracted.get('certifications', [])
            if c.get('name')
        ][:5]

        # Demand Index aus ES-Frequenzen
        demand_index = self._calc_demand_index(all_skills)

        stats = master_json.setdefault('statistics', {})
        stats.update({
            'total_experience_years':  total_years,
            'total_months':            total_years * 12,
            'project_count':           project_count,
            'skill_count':             skill_count,
            'unique_categories':      unique_cats,
            'certification_count':     cert_count,
            'top_skills':              top_skills,
            'top_certifications':      top_certs,
            'demand_index':            round(demand_index, 2),
            'placement_probability':   0.0,
            'market_value_estimate':   0,
        })

        # metadata.statistics auch aktualisieren
        meta_stats = master_json.setdefault('metadata', {}).setdefault('statistics', {})
        meta_stats.update({
            'total_categories':  unique_cats,
            'has_personal':      bool(consultant.first_name),
            'has_skills':        skill_count > 0,
            'has_experience':    project_count > 0,
            'total_experience_years': total_years,
            'skill_count':       skill_count,
            'project_count':     project_count,
        })

        # professional.total_experience_years
        master_json.setdefault('extracted_data', {}).setdefault(
            'professional', {}
        )['total_experience_years'] = total_years

        return master_json

    def _calc_years_from_projects(self, experience: list) -> int:
        """Berechnet Erfahrungsjahre aus Projekt-Zeitraeumen."""
        total = 0
        current_year = datetime.now().year
        for exp in experience:
            period = exp.get('period', '')
            if not period:
                continue
            years = re.findall(r'(\d{4})', period)
            if len(years) >= 2:
                start = int(years[0])
                end   = current_year if any(
                    w in period.lower()
                    for w in ['dato', 'heute', 'now', 'present', 'aktuell']
                ) else int(years[-1])
                total += max(0, min(50, end - start))
            elif len(years) == 1:
                total += 1
        return min(total, 60)

    def _get_top_skills(self, skills: list, limit: int = 10) -> list:
        """Gibt Top-Skills nach TrainingTerm-Frequenz sortiert zurueck."""
        try:
            from apps.cv_extractor.models import TrainingTerm
            skill_set = list(set(skills))
            terms = TrainingTerm.objects.filter(
                term__in=skill_set
            ).order_by('-frequency').values_list('term', flat=True)[:limit]
            result = list(terms)
            # Fehlende Skills auffuellen
            for s in skill_set:
                if s not in result and len(result) < limit:
                    result.append(s)
            return result[:limit]
        except Exception:
            return list(set(skills))[:limit]

    def _calc_demand_index(self, skills: list) -> float:
        """Berechnet Demand-Index aus ES Skill-Frequenzen."""
        try:
            from apps.cv_extractor.models import TrainingTerm
            if not skills:
                return 0.0
            skill_set  = list(set(skills))
            total_freq = TrainingTerm.objects.filter(
                term__in=skill_set
            ).values_list('frequency', flat=True)
            freqs = list(total_freq)
            if not freqs:
                return 0.0
            avg_freq  = sum(freqs) / len(freqs)
            max_freq  = max(freqs)
            demand    = min(1.0, (avg_freq / max(max_freq, 1)) + (len(skill_set) / 200))
            return round(demand, 2)
        except Exception:
            return 0.0

    def _run_llm_analysis(self, consultant,
                           master_json: Dict) -> Optional[Dict]:
        """Ein LLM-Call fuer summary + matching. Gibt Dict oder None zurueck."""
        try:
            from apps.cv_extractor.services.deepseek_api_enricher import deepseek_api

            extracted  = master_json.get('extracted_data', {})
            personal   = extracted.get('personal', {})
            skills_all = []
            for lst in extracted.get('skills', {}).values():
                skills_all.extend([s for s in lst if s])
            top_skills = skills_all[:15]

            roles = [
                exp.get('role', '') or exp.get('title', '')
                for exp in extracted.get('experience', [])[:8]
                if exp.get('role') or exp.get('title')
            ]
            companies = [
                exp.get('company', '')
                for exp in extracted.get('experience', [])[:8]
                if exp.get('company')
            ]

            prompt = f"""Analysiere diesen IT-Consultant und antworte NUR mit JSON (kein anderer Text).

CONSULTANT DATEN:
Headline: {consultant.headline or ''}
Erfahrung seit: {personal.get('edv_experience_since', '')} | Jahre: {master_json.get('statistics', {}).get('total_experience_years', 0)}
Top Skills: {', '.join(top_skills)}
Rollen in Projekten: {', '.join(roles[:5])}
Firmen/Kunden: {', '.join(companies[:5])}
Branchen: {', '.join(extracted.get('industries', [])[:5])}
Zertifizierungen: {', '.join([c.get('name','') for c in extracted.get('certifications',[])[:3]])}

Erstelle folgendes JSON auf DEUTSCH:
{{
  "summary": "3 Saetze professionelle Zusammenfassung des Consultants fuer Kunden",
  "preferred_roles": ["Rolle1", "Rolle2", "Rolle3"],
  "preferred_industries": ["Branche1", "Branche2"],
  "must_have_skills": ["TopSkill1", "TopSkill2", "TopSkill3", "TopSkill4", "TopSkill5"],
  "nice_to_have_skills": ["Skill1", "Skill2", "Skill3"],
  "role_code": 1,
  "landscape_code": 1,
  "level_code": 3,
  "overall_score": 0.85
}}

WICHTIG fuer role_code:
1=Administrator(Netzwerk/System/Firewall/Ops), 2=Entwickler, 3=Architekt,
4=Projektleiter, 5=Berater/Consultant

WICHTIG fuer landscape_code:
1=Client/Server(inkl.Mainframe/Citrix), 2=Netzwerk/Security(Firewall/Router/VPN),
3=Web/Software, 4=Cloud/DevOps, 5=Embedded/IoT

WICHTIG fuer level_code:
1=Junior(0-3J), 2=Senior(3-7J), 3=Experte(7-12J), 4=SeniorExperte(12-20J), 5=Master(20+J)

overall_score: 0.0-1.0 basierend auf Skill-Tiefe und Erfahrung"""

            from apps.cv_extractor.services.llm_rate_limiter import llm_slot
            with llm_slot(label='db_enricher'):
                result = deepseek_api.extract(
                    prompt,
                    system_prompt="Du bist ein praeziser CV-Analyst. Antworte NUR mit validem JSON."
                )

            if result.success and result.data:
                if isinstance(result.data, dict):
                    return result.data
                if isinstance(result.data, str):
                    return json.loads(result.data)

        except Exception as e:
            logger.error(f"LLM-Analyse Fehler: {e}")

        return None

    def _apply_llm_result(self, master_json: Dict,
                          llm: Dict, consultant) -> Dict:
        """Uebernimmt LLM-Ergebnisse ins master_json."""

        # normalized.professional.summary
        master_json.setdefault('normalized', {}).setdefault(
            'professional', {}
        )['summary'] = llm.get('summary', '')

        # matching
        role_code      = int(llm.get('role_code', 1))
        landscape_code = int(llm.get('landscape_code', 1))
        level_code     = int(llm.get('level_code', 3))

        master_json['matching'] = {
            'overall_score':       float(llm.get('overall_score', 0.5)),
            'skill_match_score':   float(llm.get('overall_score', 0.5)),
            'role_match_score':    0.0,
            'industry_match_score': 0.0,
            'preferred_roles':     llm.get('preferred_roles', []),
            'preferred_industries': llm.get('preferred_industries', []),
            'preferred_locations': [consultant.location] if consultant.location else [],
            'min_experience_years': master_json.get('statistics', {}).get(
                'total_experience_years', 0
            ),
            'must_have_skills':    llm.get('must_have_skills', []),
            'nice_to_have_skills': llm.get('nice_to_have_skills', []),
            'role_classification': {
                'role_code':      role_code,
                'role_name':      ROLE_NAMES.get(role_code, ''),
                'landscape_code': landscape_code,
                'landscape_name': LANDSCAPE_NAMES.get(landscape_code, ''),
                'level_code':     level_code,
                'level_name':     LEVEL_NAMES.get(level_code, ''),
            }
        }

        return master_json

    def _apply_defaults(self, master_json: Dict, consultant) -> Dict:
        """Setzt Standardwerte wenn LLM fehlschlaegt."""
        master_json.setdefault('normalized', {}).setdefault(
            'professional', {}
        )['summary'] = ''

        master_json['matching'] = {
            'overall_score': 0.0, 'skill_match_score': 0.0,
            'role_match_score': 0.0, 'industry_match_score': 0.0,
            'preferred_roles': [], 'preferred_industries': [],
            'preferred_locations': [],
            'min_experience_years': 0,
            'must_have_skills': [], 'nice_to_have_skills': [],
            'role_classification': {
                'role_code': 0, 'role_name': '',
                'landscape_code': 0, 'landscape_name': '',
                'level_code': 0, 'level_name': '',
            }
        }
        return master_json

    def _save_to_db_tables(self, consultant, master_json: Dict):
        """Spiegelt statistics + matching in DB-Tabellen."""
        from apps.cv_extractor.models import (
            ConsultantStatistics, ConsultantMatching
        )

        stats   = master_json.get('statistics', {})
        matching = master_json.get('matching', {})
        rc      = matching.get('role_classification', {})

        ConsultantStatistics.objects.update_or_create(
            consultant=consultant,
            defaults={
                'total_experience_years': stats.get('total_experience_years', 0),
                'total_months':           stats.get('total_months', 0),
                'project_count':          stats.get('project_count', 0),
                'skill_count':            stats.get('skill_count', 0),
                'unique_categories':      stats.get('unique_categories', 0),
                'certification_count':    stats.get('certification_count', 0),
                'top_skills':             stats.get('top_skills', []),
                'top_certifications':     stats.get('top_certifications', []),
                'demand_index':           stats.get('demand_index', 0.0),
                'placement_probability':  matching.get('overall_score', 0.0),
                'market_value_estimate':  0,
            }
        )

        ConsultantMatching.objects.update_or_create(
            consultant=consultant,
            defaults={
                'overall_score':         matching.get('overall_score', 0.0),
                'skill_match_score':     matching.get('skill_match_score', 0.0),
                'role_match_score':      matching.get('role_match_score', 0.0),
                'industry_match_score':  matching.get('industry_match_score', 0.0),
                'preferred_roles':       matching.get('preferred_roles', []),
                'preferred_industries':  matching.get('preferred_industries', []),
                'preferred_locations':   matching.get('preferred_locations', []),
                'min_experience_years':  matching.get('min_experience_years', 0),
                'must_have_skills':      matching.get('must_have_skills', []),
                'nice_to_have_skills':   matching.get('nice_to_have_skills', []),
                'skill_weights':         {},
                'role_weights':          {},
                'industry_weights':      {},
            }
        )


db_enricher = DBEnricher()
