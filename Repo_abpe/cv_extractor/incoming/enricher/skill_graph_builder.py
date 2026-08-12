"""
skill_graph_builder.py – Stufe 2, parallel, LLM (DeepSeek)

Aufgaben:
  Pro Consultant:
    - skill_graph.nodes: Skill-Gewichtungen (weight, years=null)

  Global (SkillRelation Tabelle, ab frequency >= 2):
    - edges: belongs_to, related, domain
    - Nur neue Relationen anlegen (keine Duplikate)
    - weight erhoehen wenn schon vorhanden
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from django.db import transaction

logger = logging.getLogger(__name__)

MIN_FREQ_FOR_EDGE = 2   # Ab dieser Frequenz Edges anlegen
MAX_NODES         = 30  # Max Nodes pro Consultant
MAX_NEW_EDGES     = 20  # Max neue Edges pro Durchlauf


class SkillGraphBuilder:

    def __init__(self):
        logger.info("SkillGraphBuilder initialisiert")

    @transaction.atomic
    def enrich(self, consultant, master_json: Dict[str, Any]) -> Dict[str, Any]:
        """Hauptmethode – baut skill_graph.nodes + globale Edges."""
        logger.info(f"SkillGraphBuilder (LLM) fuer {consultant.aid}")

        extracted  = master_json.get('extracted_data', {})
        experience = extracted.get('experience', [])

        # Alle Skills aus DB lesen (inkl. Projekt-Skills)
        from apps.cv_extractor.models import ConsultantSkill
        all_skills: Dict[str, str] = {}
        for cs in ConsultantSkill.objects.filter(
            consultant=consultant
        ).select_related('skill').order_by('-weight'):
            if cs.skill.name and len(cs.skill.name) > 2:
                all_skills[cs.skill.name] = cs.skill.category_name or ''

        if not all_skills:
            logger.info(f"Keine Skills fuer {consultant.aid}")
            return master_json

        # 1. Nodes: LLM bewertet Gewichtungen
        nodes = self._build_nodes_with_llm(
            all_skills, experience, consultant
        )
        master_json['skill_graph'] = {
            'nodes': nodes,
            'edges': []  # Edges sind global in SkillRelation Tabelle
        }

        # 2. Globale Edges in SkillRelation Tabelle
        self._update_global_edges(all_skills)

        logger.info(
            f"SkillGraphBuilder abgeschlossen: "
            f"{len(nodes)} nodes, globale Edges aktualisiert"
        )
        return master_json

    def _build_nodes_with_llm(self, all_skills: Dict[str, str],
                               experience: list,
                               consultant) -> List[Dict]:
        """LLM bewertet Skill-Gewichtungen basierend auf Projekthaeufigkeit."""
        try:
            from apps.cv_extractor.services.deepseek_api_enricher import deepseek_api

            # Skill-Haeufigkeit in Projekten zaehlen
            skill_freq: Dict[str, int] = {}
            for exp in experience:
                for tech in exp.get('technologies', []):
                    if tech in all_skills:
                        skill_freq[tech] = skill_freq.get(tech, 0) + 1

            # Top Skills fuer LLM vorbereiten (max 25)
            top_skills = sorted(
                all_skills.items(),
                key=lambda x: skill_freq.get(x[0], 0),
                reverse=True
            )[:25]

            skills_info = [
                {
                    'skill':    s,
                    'category': cat,
                    'projects': skill_freq.get(s, 0),
                }
                for s, cat in top_skills
            ]

            prompt = f"""Bewerte die Skill-Gewichtungen fuer diesen IT-Consultant.

Consultant: {consultant.headline or consultant.aid}
Erfahrungsjahre: {datetime.now().year - (consultant.edv_experience_since or 2000) if consultant.edv_experience_since else 'unbekannt'}

Skills (mit Anzahl Projekt-Nennungen):
{json.dumps(skills_info, ensure_ascii=False)}

Erstelle eine JSON-Liste mit Gewichtungen (0.1-1.0):
- weight 0.9-1.0: Kernkompetenz (sehr haeufig, zentral fuer Rolle)
- weight 0.7-0.8: Hauptkompetenz (regelmaessig eingesetzt)
- weight 0.5-0.6: Nebenkompetenz (gelegentlich eingesetzt)
- weight 0.1-0.4: Grundkenntnisse (selten oder nur erwaehnt)

Antworte NUR mit JSON-Array:
[{{"id": "SkillName", "category": "category_key", "weight": 0.9, "years": null}}]"""


            from apps.cv_extractor.services.llm_rate_limiter import llm_slot
            with llm_slot(label='skill_graph_builder:nodes'):
                result = deepseek_api.extract(
                    prompt,
                    system_prompt="Du bist ein CV-Analyst. Antworte NUR mit einem JSON-Array."
                )

            if result.success and result.data:
                data = result.data
                if isinstance(data, str):
                    data = json.loads(data)
                if isinstance(data, list):
                    # Validieren
                    nodes = []
                    for item in data:
                        if isinstance(item, dict) and item.get('id'):
                            nodes.append({
                                'id':       str(item['id']),
                                'category': str(item.get('category', '')),
                                'weight':   float(item.get('weight', 0.5)),
                                'years':    None,
                            })
                    return nodes[:MAX_NODES]

        except Exception as e:
            logger.error(f"LLM Nodes fehlgeschlagen: {e}")

        # Fallback: einfache Gewichtung aus Projekt-Frequenz
        return self._build_nodes_fallback(all_skills, experience)

    def _build_nodes_fallback(self, all_skills: Dict[str, str],
                               experience: list) -> List[Dict]:
        """Fallback: Gewichtung ohne LLM aus Projekt-Frequenz."""
        skill_freq: Dict[str, int] = {}
        for exp in experience:
            for tech in exp.get('technologies', []):
                if tech in all_skills:
                    skill_freq[tech] = skill_freq.get(tech, 0) + 1

        max_freq = max(skill_freq.values()) if skill_freq else 1
        nodes = []
        for skill, cat in all_skills.items():
            freq   = skill_freq.get(skill, 0)
            weight = round(0.3 + (freq / max(max_freq, 1)) * 0.6, 2)
            nodes.append({
                'id':       skill,
                'category': cat,
                'weight':   min(weight, 1.0),
                'years':    None,
            })

        return sorted(nodes, key=lambda x: x['weight'], reverse=True)[:MAX_NODES]

    def _update_global_edges(self, all_skills: Dict[str, str]):
        """
        Aktualisiert SkillRelation Tabelle (globale Edges).
        Nur fuer Skills mit TrainingTerm.frequency >= MIN_FREQ_FOR_EDGE.
        Typen: belongs_to, related, domain
        """
        try:
            from apps.cv_extractor.models import TrainingTerm, SkillRelation

            # Skills mit ausreichender Frequenz
            qualified_skills = set(
                TrainingTerm.objects.filter(
                    term__in=list(all_skills.keys()),
                    frequency__gte=MIN_FREQ_FOR_EDGE,
                ).values_list('term', flat=True)
            )

            if not qualified_skills:
                return

            # Fuer neue Skills Edges per LLM generieren
            new_skills = [
                s for s in qualified_skills
                if not SkillRelation.objects.filter(term_from=s).exists()
            ][:MAX_NEW_EDGES]

            if not new_skills:
                # Nur Frequenz erhoehen fuer bekannte
                SkillRelation.objects.filter(
                    term_from__in=list(qualified_skills)
                ).update(frequency=models_F('frequency') + 1)
                return

            # LLM generiert Edges
            edges = self._generate_edges_with_llm(new_skills, all_skills)

            # In DB speichern
            created = 0
            for edge in edges:
                obj, was_created = SkillRelation.objects.get_or_create(
                    term_from=edge['from'],
                    term_to=edge['to'],
                    relation_type=edge['type'],
                    defaults={
                        'weight':     edge.get('weight', 0.7),
                        'frequency':  1,
                        'confidence': 0.8,
                        'source':     'skill_graph_builder',
                    }
                )
                if not was_created:
                    obj.frequency += 1
                    obj.weight     = min(1.0, obj.weight + 0.01)
                    obj.save(update_fields=['frequency', 'weight'])
                else:
                    created += 1

            if created > 0:
                logger.info(f"SkillRelation: {created} neue Edges angelegt")

        except Exception as e:
            logger.error(f"_update_global_edges Fehler: {e}")

    def _generate_edges_with_llm(self, skills: List[str],
                                  all_skills: Dict[str, str]) -> List[Dict]:
        """LLM generiert Edges fuer neue Skills."""
        try:
            from apps.cv_extractor.services.deepseek_api_enricher import deepseek_api

            skills_with_cat = [
                f"{s} ({all_skills.get(s, '')})" for s in skills
            ]

            prompt = f"""Erstelle Skill-Relationen fuer folgende IT-Skills.

Skills: {', '.join(skills_with_cat)}

Erlaubte Relationstypen:
- belongs_to: Skill gehoert zu Hersteller/Produkt (Fortigate → Fortinet)
- related:    Aehnliche/verwandte Technologie (Fortigate → Checkpoint)
- domain:     Skill gehoert zu Fachbereich (Fortigate → Netzwerksicherheit)

Antworte NUR mit JSON-Array (max {MAX_NEW_EDGES} Eintraege):
[{{"from": "Skill", "to": "Ziel", "type": "belongs_to", "weight": 0.9}}]

Regeln:
- Nur tatsaechliche, sinnvolle Relationen
- weight 0.7-1.0
- Keine Duplikate
- to-Wert kann ein Hersteller, verwandter Skill oder Fachbereich sein"""

            from apps.cv_extractor.services.llm_rate_limiter import llm_slot
            with llm_slot(label='skill_graph_builder:edges'):
                result = deepseek_api.extract(
                    prompt,
                    system_prompt="Antworte NUR mit einem JSON-Array."
                )

            if result.success and result.data:
                data = result.data
                if isinstance(data, str):
                    data = json.loads(data)
                if isinstance(data, list):
                    valid = []
                    for e in data:
                        if (isinstance(e, dict) and
                                e.get('from') and e.get('to') and
                                e.get('type') in ('belongs_to', 'related', 'domain')):
                            valid.append({
                                'from':   str(e['from']),
                                'to':     str(e['to']),
                                'type':   str(e['type']),
                                'weight': float(e.get('weight', 0.7)),
                            })
                    return valid

        except Exception as e:
            logger.error(f"LLM Edges Fehler: {e}")

        return []


def models_F(field):
    from django.db.models import F
    return F(field)



skill_graph_builder = SkillGraphBuilder()
