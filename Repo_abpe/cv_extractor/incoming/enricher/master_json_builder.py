"""
master_json_builder.py - Erstellt das Master-JSON aus der Datenbank
"""

import json
import logging
from typing import Dict, List, Any, Optional
from django.db import models

logger = logging.getLogger(__name__)


class MasterJsonBuilder:
    """Baut das Master-JSON aus den Datenbank-Einträgen"""

    def __init__(self):
        logger.info("✅ MasterJsonBuilder initialisiert")

    def build(self, consultant) -> Dict[str, Any]:
        """Baut das komplette JSON für einen Consultant"""
        result = {
            "metadata": {
                "aid": consultant.aid,
                "version": consultant.version,
                "consultant_dir": consultant.consultant_dir,
                "first_name": consultant.first_name,
                "last_name": consultant.last_name,
                "headline": consultant.headline,
                "source": {
                    "type": "database",
                    "filename": "",
                    "filesize": 0,
                    "import_id": "",
                    "import_date": consultant.created_at.isoformat() if consultant.created_at else ""
                },
                "pipeline": {
                    "version": consultant.pipeline_version,
                    "step": consultant.pipeline_step,
                    "extractor": "cv_extractor",
                    "model": "deepseek-chat",
                    "self_learning": True
                }
            },
            "extracted_data": {
                "personal": {
                    "first_name": consultant.first_name,
                    "last_name": consultant.last_name,
                    "birth_year": consultant.birth_year,
                    "nationality": consultant.nationality,
                    "languages": [lang.language.name for lang in consultant.languages.all()],
                    "email": consultant.email,
                    "phone": consultant.phone,
                    "location": consultant.location,
                    "availability": consultant.availability,
                    "edv_experience_since": consultant.edv_experience_since,
                    "degree": consultant.degree  # ⭐ DEGREE hinzugefügt
                },
                "education": [
                    {
                        "degree": edu.degree,
                        "institution": edu.institution,
                        "period": edu.period,
                        "description": edu.description,
                        "education_type": edu.education_type,  # ⭐ neu
                        "issuer": edu.issuer  # ⭐ neu
                    }
                    for edu in consultant.education.all().order_by('sort_order')
                ],
                "certifications": [
                    {
                        "name": cert.certification.name,
                        "issuer": cert.certification.issuer.name if cert.certification.issuer else "",
                        "date_obtained": cert.date_obtained,
                        "expiry_date": cert.expiry_date
                    }
                    for cert in consultant.certifications.all()
                ],
                "industries": [ci.industry.name for ci in consultant.industries.all()],
                "focus_areas": [cfa.focus_area.name for cfa in consultant.focus_areas.all()],
                "focus_experience": [fe.name for fe in consultant.focus_experience_items.all().order_by('sort_order')],
                "experience": [
                    {
                        "period": exp.period,
                        "title": exp.title,
                        "company": exp.company,
                        "role": exp.role,
                        "activities":   [a.activity_text for a in exp.activities.all()],
                        "technologies": [t.skill.name   for t in exp.technologies.all()]
                    }
                    for exp in consultant.experience.all().order_by('sort_order')
                ],
                "skills": self._build_skills_dict(consultant),
                "other": ""
            }
        }
        return result

    def _build_skills_dict(self, consultant) -> Dict[str, List[str]]:
        """Baut das Skills-Dictionary aus den ConsultantSkills mit Kategorien"""
        # 28 Kategorien initialisieren
        skills_dict = {
            "architecture_pattern": [],
            "business_software": [],
            "ci_cd_tool": [],
            "cloud_platform": [],
            "communication_tool": [],
            "database": [],
            "data_format": [],
            "data_management": [],
            "development_environment": [],
            "devops_tool": [],
            "documentation_tool": [],
            "framework": [],
            "hardware": [],
            "identity_management": [],
            "it_infrastructure": [],
            "methodology": [],
            "monitoring_tool": [],
            "network_protocol": [],
            "operating_system": [],
            "programming_languages": [],
            "project_management": [],
            "security_tool": [],
            "soft_skill": [],
            "special_concept": [],
            "special_skill": [],  # ⭐ für nicht zuordenbare Skills
            "testing_tool": [],
            "version_control": [],
            "virtualization": [],
        }

        # Kategorie-Mapping von deutschem Namen zu JSON-Key
        category_to_key = {
            'Architekturmuster': 'architecture_pattern',
            'Business Software': 'business_software',
            'CI/CD Tools': 'ci_cd_tool',
            'Cloud-Plattformen': 'cloud_platform',
            'Kommunikationstools': 'communication_tool',
            'Datenbanken': 'database',
            'Datenformate': 'data_format',
            'Datenmanagement': 'data_management',
            'Entwicklungsumgebungen': 'development_environment',
            'DevOps Tools': 'devops_tool',
            'Dokumentationstools': 'documentation_tool',
            'Frameworks und Bibliotheken': 'framework',
            'Hardware': 'hardware',
            'Identity Management': 'identity_management',
            'IT-Infrastruktur': 'it_infrastructure',
            'Methoden': 'methodology',
            'Monitoring Tools': 'monitoring_tool',
            'Netzwerkprotokolle': 'network_protocol',
            'Betriebssysteme': 'operating_system',
            'Programmiersprachen': 'programming_languages',
            'Projektmanagement Tools': 'project_management',
            'Security Tools': 'security_tool',
            'Soft Skills': 'soft_skill',
            'Spezielle Konzepte': 'special_concept',
            'Sonstige Skills': 'special_skill',
            'Testing Tools': 'testing_tool',
            'Versionsverwaltung': 'version_control',
            'Virtualisierung': 'virtualization',
        }

        # Skills nach Kategorien sortieren
        for cs in consultant.skills.all().select_related('skill'):
            cat_name = cs.skill.category_name
            if cat_name:
                key = category_to_key.get(cat_name)
                if key and key in skills_dict:
                    skills_dict[key].append(cs.skill.name)
                else:
                    # Fallback: unbekannte Kategorie
                    skills_dict['special_skill'].append(cs.skill.name)
            else:
                # Keine Kategorie -> special_skill
                skills_dict['special_skill'].append(cs.skill.name)

        # Leere Kategorien entfernen
        return {k: v for k, v in skills_dict.items() if v}

master_json_builder = MasterJsonBuilder()
