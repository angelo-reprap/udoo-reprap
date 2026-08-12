"""
services/aid_generator.py – LLM-basierte AID-Erzeugung

AID-Format: AID-{initials}_{role}.{landscape}.{level}.{version}
Beispiel:   AID-tt_1.2.4.2

Ablauf:
  1. Initialen aus Vor-/Nachname
  2. Versioning: consultant_dir + version aus ConsultantDirectory (DB)
  3. LLM klassifiziert: role_code, landscape_code, level_code
  4. AID zusammensetzen

Hinweis:
  Die gleiche Klassifikation wird spaeter vom db_enricher (Stufe 2)
  nochmal verfeinert und in matching.role_classification gespeichert.
  Die AID bleibt unveraendert – sie ist die eindeutige ID.
"""

import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional

from ..services.deepseek_api import deepseek_api
from .versioning import version_manager

logger = logging.getLogger(__name__)


class AIDGenerator:
    """Generiert AIDs basierend auf CV-Daten mit LLM-Klassifikation."""

    # Muss mit classify_aid PromptTemplate uebereinstimmen
    ROLE_NAMES = {
        1: 'Administrator',
        2: 'Entwickler',
        3: 'Architekt',
        4: 'Projektleiter',
        5: 'Berater',
    }

    LANDSCAPE_NAMES = {
        1: 'Client/Server',
        2: 'Netzwerk/Security',
        3: 'Web/Software',
        4: 'Cloud/DevOps',
        5: 'Embedded/IoT',
    }

    LEVEL_NAMES = {
        1: 'Junior',
        2: 'Senior',
        3: 'Experte',
        4: 'Senior Experte',
        5: 'Master',
    }

    # Standardwerte wenn LLM fehlschlaegt
    DEFAULT_CLASSIFICATION = {
        'role_code':      1,
        'landscape_code': 1,
        'level_code':     3,
    }

    def __init__(self):
        logger.info("AIDGenerator (LLM-basiert) initialisiert")

    # ── Hilfsmethoden ────────────────────────────────────────────────────────

    @staticmethod
    def _extract_initials(first_name: str, last_name: str) -> str:
        """Erstellt Kuerzel aus Vor- und Nachname: Thomas Troschke → tt"""
        initials = ""
        if first_name:
            initials += first_name[0].lower()
        if last_name:
            initials += last_name[0].lower()
        return initials or "xx"

    @staticmethod
    def _calculate_experience_years(extracted_data: Dict) -> int:
        """
        Berechnet Gesamterfahrung aus Projekt-Zeitraeumen.
        Erkennt: dato, heute, now, present, aktuell, bis heute
        """
        total_years  = 0
        current_year = datetime.now().year
        current_words = {'dato', 'heute', 'now', 'present', 'aktuell', 'bis heute'}

        for exp in extracted_data.get('experience', []):
            period = exp.get('period', '')
            if not period:
                continue

            period_lower = period.lower()
            years_found  = re.findall(r'(\d{4})', period)

            if len(years_found) >= 2:
                start = int(years_found[0])
                # Endjahr: aktuell wenn Gegenwartswort vorhanden
                is_current = any(w in period_lower for w in current_words)
                end        = current_year if is_current else int(years_found[-1])
                total_years += max(0, min(50, end - start))
            elif len(years_found) == 1:
                total_years += 1

        return min(total_years, 60)

    # ── LLM-Klassifikation ───────────────────────────────────────────────────

    def _get_llm_classification(self, extracted_data: Dict,
                                 headline: str = "") -> Dict:
        """
        Ruft classify_aid PromptTemplate auf und gibt Klassifikation zurueck.
        Fallback: DEFAULT_CLASSIFICATION wenn LLM fehlschlaegt.
        """
        # Daten fuer Prompt aufbereiten
        summary = (extracted_data.get('summary', '') or '')[:500]

        all_skills = []
        for skills in extracted_data.get('skills', {}).values():
            if isinstance(skills, list):
                all_skills.extend(skills[:5])
        top_skills = ", ".join(all_skills[:15])

        project_roles = [
            exp['role']
            for exp in extracted_data.get('experience', [])[:5]
            if exp.get('role')
        ]
        project_roles_str = ", ".join(project_roles[:5])

        # Prompt aus DB laden
        from ..models import PromptTemplate
        pt = PromptTemplate.objects.filter(
            stage='classify_aid', is_active=True
        ).first()

        if not pt:
            logger.warning("Kein classify_aid Prompt – verwende Standardwerte")
            return self.DEFAULT_CLASSIFICATION.copy()

        try:
            prompt = pt.prompt_text.format(
                headline=headline[:200],
                summary=summary,
                top_skills=top_skills,
                project_roles=project_roles_str,
            )
        except KeyError as e:
            logger.warning(f"Prompt-Format Fehler: {e} – verwende Standardwerte")
            return self.DEFAULT_CLASSIFICATION.copy()

        # LLM-Call
        result = deepseek_api.extract(
            prompt,
            system_prompt="Du bist ein praeziser CV-Analyst. Antworte NUR mit JSON."
        )

        if result.success and result.data:
            data = result.data
            # Normalisieren: String → Dict
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except Exception:
                    data = None

            if isinstance(data, dict):
                # Sicherstellen dass alle Keys vorhanden sind
                classification = {
                    'role_code':      int(data.get('role_code',      self.DEFAULT_CLASSIFICATION['role_code'])),
                    'landscape_code': int(data.get('landscape_code', self.DEFAULT_CLASSIFICATION['landscape_code'])),
                    'level_code':     int(data.get('level_code',     self.DEFAULT_CLASSIFICATION['level_code'])),
                }
                # Codes validieren (1-5)
                for key in ('role_code', 'landscape_code', 'level_code'):
                    if not (1 <= classification[key] <= 5):
                        classification[key] = self.DEFAULT_CLASSIFICATION[key]

                logger.info(f"LLM Klassifikation: {classification}")
                return classification

        logger.warning("LLM Klassifikation fehlgeschlagen – verwende Standardwerte")
        return self.DEFAULT_CLASSIFICATION.copy()

    # ── Haupt-API ────────────────────────────────────────────────────────────

    def generate_from_cv(self, extracted_data: Dict,
                          first_name: str,
                          last_name:  str,
                          target_directory: str = "",
                          action_type: str = "new_version",
                          version_info: dict = None) -> Optional[Dict]:
        """
        Generiert eine AID fuer einen Consultant.

        Rueckgabe:
        {
            'aid':            'AID-tt_1.2.4.2',
            'initials':       'tt',
            'consultant_dir': 'troschke_thomas',
            'role':           {'code': 1, 'name': 'Administrator', 'confidence': 0.8},
            'landscape':      {'code': 2, 'name': 'Netzwerk/Security', 'confidence': 0.8},
            'level':          {'code': 4, 'name': 'Senior Experte', 'years': 28, 'confidence': 0.8},
            'version':        2,
            'version_string': '1.2.4.2',
        }
        """
        try:
            initials       = self._extract_initials(first_name, last_name)
            # version_info wird von aussen uebergeben wenn vorhanden
            # → kein doppelter get_next_version() Aufruf
            if version_info is None:
                version_info = version_manager.get_next_version(
                    first_name, last_name,
                    target_directory=target_directory,
                    action_type=action_type
                )
            consultant_dir = version_info['consultant_dir']

            # LLM-Klassifikation
            headline       = extracted_data.get('headline', '') or ''
            classification = self._get_llm_classification(
                extracted_data, headline
            )

            role_code      = classification['role_code']
            landscape_code = classification['landscape_code']
            level_code     = classification['level_code']

            role_name      = self.ROLE_NAMES.get(role_code,      'Administrator')
            landscape_name = self.LANDSCAPE_NAMES.get(landscape_code, 'Client/Server')
            level_name     = self.LEVEL_NAMES.get(level_code,    'Experte')

            # Erfahrungsjahre
            total_years  = self._calculate_experience_years(extracted_data)

            # Version: letzter Teil der Versionsnummer (z.B. "1.2.4.2" → "2")
            version_parts = version_info['version'].split('.')
            version_num   = version_parts[3] if len(version_parts) >= 4 else '1'

            # AID zusammensetzen
            aid = f"AID-{initials}_{role_code}.{landscape_code}.{level_code}.{version_num}"

            logger.info(f"AID generiert: {aid}")
            logger.info(f"  Rolle:      {role_name} ({role_code})")
            logger.info(f"  Landschaft: {landscape_name} ({landscape_code})")
            logger.info(f"  Level:      {level_name} ({level_code})")
            logger.info(f"  Verzeichnis:{consultant_dir}")

            return {
                'aid':            aid,
                'initials':       initials,
                'consultant_dir': consultant_dir,
                'role': {
                    'code':       role_code,
                    'name':       role_name,
                    'confidence': 0.8,
                },
                'landscape': {
                    'code':       landscape_code,
                    'name':       landscape_name,
                    'confidence': 0.8,
                },
                'level': {
                    'code':       level_code,
                    'name':       level_name,
                    'years':      total_years,
                    'confidence': 0.8,
                },
                'version':        int(version_num),
                'version_string': f"{role_code}.{landscape_code}.{level_code}.{version_num}",
            }

        except Exception as e:
            logger.error(f"AID Generierung fehlgeschlagen: {e}")
            raise


aid_generator = AIDGenerator()
