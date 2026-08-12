"""
search_enricher.py – Stufe 1, synchron, kein LLM

Aufgaben:
  - searchable_text aufbauen (flacher String fuer ES Volltext)
  - facets aufbauen (Filter-Werte fuer ES)
  - ElasticSearch Index 'abpe_consultants_index' aktualisieren
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# ES Index fuer Consultants (getrennt von abpe_skills_index)
CONSULTANTS_INDEX = 'abpe_consultants_index'


class SearchEnricher:

    def __init__(self):
        self._es = None
        logger.info("SearchEnricher initialisiert")

    def _get_es(self):
        """Lazy ES-Verbindung."""
        if self._es is None:
            try:
                from elasticsearch import Elasticsearch
                import json as _json
                cfg = _json.load(open('/opt/abpe/backend/settings.json'))
                hosts = cfg.get('elasticsearch', {}).get('hosts', ['http://localhost:9200'])
                self._es = Elasticsearch(hosts)
            except Exception as e:
                logger.warning(f"ES nicht verfuegbar: {e}")
        return self._es

    def enrich(self, consultant, master_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Hauptmethode – baut searchable_text + facets + ES-Index.
        Gibt aktualisiertes master_json zurueck.
        """
        logger.info(f"SearchEnricher fuer {consultant.aid}")

        extracted = master_json.get('extracted_data', {})
        personal  = extracted.get('personal', {})

        # 1. searchable_text aufbauen
        master_json['searchable_text'] = self._build_searchable_text(
            extracted, master_json.get('metadata', {}), consultant
        )

        # 2. facets aufbauen
        master_json['facets'] = self._build_facets(extracted, personal)

        # 3. ES Index aktualisieren
        self._index_consultant(consultant, master_json)

        logger.info(f"SearchEnricher abgeschlossen fuer {consultant.aid}")
        return master_json

    def _build_searchable_text(self, extracted: Dict,
                                metadata: Dict,
                                consultant=None) -> str:
        """Baut flachen Volltext-String fuer ES."""
        parts = []

        # Headline + AID
        if metadata.get('headline'):
            parts.append(metadata['headline'])
        if metadata.get('aid'):
            parts.append(metadata['aid'])

        # Persoenliche Daten
        personal = extracted.get('personal', {})
        for field in ['first_name', 'last_name', 'location', 'nationality']:
            if personal.get(field):
                parts.append(personal[field])
        if personal.get('languages'):
            for lang in personal['languages']:
                if isinstance(lang, dict):
                    parts.append(lang.get('name', ''))
                elif isinstance(lang, str):
                    parts.append(lang)
        if personal.get('degree'):
            parts.append(personal['degree'])

        # Skills aus DB (inkl. Projekt-Skills)
        if consultant is not None:
            from apps.cv_extractor.models import ConsultantSkill
            db_skills = ConsultantSkill.objects.filter(
                consultant=consultant
            ).select_related('skill').order_by('-weight')
            parts.extend([cs.skill.name for cs in db_skills if cs.skill.name])

        # Zertifikate
        for cert in extracted.get('certifications', []):
            if cert.get('name'):
                parts.append(cert['name'])
            if cert.get('issuer'):
                parts.append(cert['issuer'])

        # Projekte: company + role + technologies
        for exp in extracted.get('experience', []):
            for field in ['company', 'role', 'title', 'industry']:
                if exp.get(field):
                    parts.append(exp[field])
            parts.extend([t for t in exp.get('technologies', []) if t])

        # Branchen + Fachbereiche
        parts.extend([i for i in extracted.get('industries', []) if i])
        parts.extend([f for f in extracted.get('focus_areas', []) if f])
        parts.extend([fe for fe in extracted.get('focus_experience', []) if fe])

        # Education
        for edu in extracted.get('education', []):
            if edu.get('degree'):
                parts.append(edu['degree'])
            if edu.get('institution'):
                parts.append(edu['institution'])

        # Deduplizieren + zusammenfuegen
        seen = set()
        unique = []
        for p in parts:
            p_clean = str(p).strip()
            if p_clean and p_clean not in seen:
                seen.add(p_clean)
                unique.append(p_clean)

        return ' '.join(unique)

    def _build_facets(self, extracted: Dict,
                      personal: Dict) -> Dict[str, Any]:
        """Baut Filter-Werte fuer ES-Facetten-Suche."""

        # Top Skills (alle, dedupliziert)
        all_skills = []
        for skill_list in extracted.get('skills', {}).values():
            all_skills.extend([s for s in skill_list if s])
        # Deduplizieren, Reihenfolge beibehalten
        seen = set()
        top_skills = []
        for s in all_skills:
            if s not in seen:
                seen.add(s)
                top_skills.append(s)

        # Rollen aus Projekten
        roles = list({
            exp.get('role', '') or exp.get('title', '')
            for exp in extracted.get('experience', [])
            if exp.get('role') or exp.get('title')
        })

        # Locations aus Projekten + personal
        locations = list({
            exp.get('location', '')
            for exp in extracted.get('experience', [])
            if exp.get('location')
        })
        if personal.get('location'):
            locations.insert(0, personal['location'])
        locations = list(dict.fromkeys(locations))  # deduplizieren

        # Experience years range
        stats = extracted.get('professional', {})
        years = stats.get('total_experience_years', 0) or 0
        if years >= 20:
            years_range = '20+'
        elif years >= 15:
            years_range = '15-20'
        elif years >= 10:
            years_range = '10-15'
        elif years >= 5:
            years_range = '5-10'
        elif years > 0:
            years_range = f'0-{years}'
        else:
            years_range = ''

        # Skill-Kategorien die vorhanden sind
        skill_categories = [
            k for k, v in extracted.get('skills', {}).items() if v
        ]

        return {
            'industries':            extracted.get('industries', []),
            'roles':                 roles[:10],
            'skill_categories':      skill_categories,
            'top_skills':            top_skills[:20],
            'locations':             locations[:5],
            'certifications':        [
                c['name'] for c in extracted.get('certifications', [])
                if c.get('name')
            ],
            'experience_years_range': years_range,
            'availability':          personal.get('availability', ''),
            'languages':             [
                lang.get('name','') if isinstance(lang, dict) else str(lang)
                for lang in personal.get('languages', [])
                if lang
            ],
            'degree':                personal.get('degree', ''),
        }

    def _index_consultant(self, consultant,
                          master_json: Dict[str, Any]):
        """Schreibt Consultant in ES abpe_consultants_index."""
        es = self._get_es()
        if not es:
            logger.warning("ES nicht verfuegbar – Index uebersprungen")
            return

        try:
            self._ensure_index(es)

            doc = {
                'aid':             consultant.aid,
                'version':         consultant.version,
                'first_name':      consultant.first_name,
                'last_name':       consultant.last_name,
                'full_name':       f"{consultant.first_name} {consultant.last_name}".strip(),
                'headline':        consultant.headline,
                'location':        consultant.location,
                'availability':    consultant.availability,
                'searchable_text': master_json.get('searchable_text', ''),
                'facets':          master_json.get('facets', {}),
                'statistics':      master_json.get('statistics', {}),
                'indexed_at':      datetime.now().isoformat(),
            }

            es.index(
                index=CONSULTANTS_INDEX,
                id=consultant.aid,
                document=doc
            )
            logger.info(f"ES indexiert: {consultant.aid}")

        except Exception as e:
            logger.error(f"ES Indexierung fehlgeschlagen: {e}")

    def _ensure_index(self, es):
        """Erstellt ES-Index falls nicht vorhanden."""
        if es.indices.exists(index=CONSULTANTS_INDEX):
            return
        mapping = {
            'mappings': {
                'properties': {
                    'aid':             {'type': 'keyword'},
                    'version':         {'type': 'keyword'},
                    'first_name':      {'type': 'text', 'fields': {'keyword': {'type': 'keyword'}}},
                    'last_name':       {'type': 'text', 'fields': {'keyword': {'type': 'keyword'}}},
                    'full_name':       {'type': 'text'},
                    'headline':        {'type': 'text'},
                    'location':        {'type': 'keyword'},
                    'availability':    {'type': 'keyword'},
                    'searchable_text': {'type': 'text', 'analyzer': 'standard'},
                    'facets':          {'type': 'object'},
                    'statistics':      {'type': 'object'},
                    'indexed_at':      {'type': 'date'},
                }
            },
            'settings': {
                'number_of_shards':   1,
                'number_of_replicas': 0,
            }
        }
        es.indices.create(index=CONSULTANTS_INDEX, body=mapping)
        logger.info(f"ES Index erstellt: {CONSULTANTS_INDEX}")


search_enricher = SearchEnricher()
