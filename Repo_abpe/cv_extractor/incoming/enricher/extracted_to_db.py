import re
"""
extracted_to_db.py - Schreibt extrahierte Daten in die relationale DB
MIT get_or_create für Skills (verhindert Duplikate)

Changelog:
  2026-04-22: BUG-03 gefixt — courses_list + schulungen_list (vor education.delete)
              entfernt. Schulungen werden nur noch NACH dem delete geschrieben.
  2026-04-23: ExperienceTechnology wird NICHT mehr hier geschrieben.
              Technologien bleiben im RAM → skill_normalizer in Schritt 10
              schreibt ExperienceTechnology mit Kategorie + Gewichtung.
"""

import logging
from typing import Dict, Any
from django.db import transaction

from ..models import (
    Consultant, Skill, Certification, Issuer, ConsultantCertification,
    Education, Experience, Industry, ConsultantIndustry,
    FocusArea, ConsultantFocusArea, Language, ConsultantLanguage,
    FocusExperience, ConsultantSkill, SkillCategory,
    ExperienceActivity, ExperienceTechnology
)

logger = logging.getLogger(__name__)


class ExtractedToDB:
    def __init__(self):
        logger.info("✅ ExtractedToDB initialisiert (mit get_or_create)")

    def _get_or_create_skill(self, name: str, category_name: str = '') -> Skill:
        if not name or len(name) < 2:
            return None

        category = None
        if category_name:
            category = SkillCategory.objects.filter(name=category_name).first()

        skill, created = Skill.objects.get_or_create(
            name=name[:200],
            defaults={
                'frequency': 1,
                'category': category,
                'category_name': category_name[:100] if category_name else ''
            }
        )
        if not created:
            skill.frequency += 1
            # Spezifischere Kategorie gewinnt
            priority = {
                'Programmiersprachen': 10, 'Betriebssysteme': 10,
                'Datenbanken': 9, 'Cloud-Plattformen': 9,
                'Security Tools': 8, 'Netzwerkprotokolle': 8,
                'DevOps Tools': 7, 'Virtualisierung': 7,
                'Frameworks und Bibliotheken': 7, 'Hardware': 5,
                'IT-Infrastruktur': 3,
            }
            old_prio = priority.get(skill.category_name or '', 0)
            new_prio = priority.get(category_name or '', 0)
            if category and new_prio >= old_prio:
                skill.category = category
                skill.category_name = category_name
            skill.save(update_fields=['frequency', 'category', 'category_name'])
        return skill

    def _get_or_create_issuer(self, name: str) -> Issuer:
        if not name:
            return None
        issuer, created = Issuer.objects.get_or_create(
            name=name[:200],
            defaults={'frequency': 1}
        )
        if not created:
            issuer.frequency += 1
            issuer.save(update_fields=['frequency'])
        return issuer

    def _clean_text(self, text: str) -> str:
        """Entfernt unerwuenschte Unicode-Zeichen aus Texten."""
        if not text:
            return text
        for ch in ['□','☐','☑','☒','▪','▫','']:
            text = text.replace(ch, '')
        return text.strip()

    def _get_or_create_certification(self, name: str, issuer_name: str) -> Certification:
        if not name:
            return None
        name = self._clean_text(name)
        if not name:
            return None
        issuer = self._get_or_create_issuer(issuer_name) if issuer_name else None
        certification, created = Certification.objects.get_or_create(
            name=name[:200],
            defaults={'issuer': issuer, 'issuer_name': issuer_name[:200] if issuer_name else ''}
        )
        return certification

    def _get_or_create_industry(self, name: str) -> Industry:
        if not name:
            return None
        industry, created = Industry.objects.get_or_create(
            name=name[:200],
            defaults={'frequency': 1}
        )
        if not created:
            industry.frequency += 1
            industry.save(update_fields=['frequency'])
        return industry

    def _get_or_create_focus_area(self, name: str) -> FocusArea:
        if not name:
            return None
        focus_area, created = FocusArea.objects.get_or_create(
            name=name[:200],
            defaults={'frequency': 1}
        )
        if not created:
            focus_area.frequency += 1
            focus_area.save(update_fields=['frequency'])
        return focus_area

    def _get_or_create_language(self, name: str) -> Language:
        if not name:
            return None
        language, created = Language.objects.get_or_create(name=name[:100])
        return language

    @transaction.atomic
    def save(self, consultant: Consultant, extracted_data: Dict[str, Any]) -> Consultant:
        logger.info(f"💾 Speichere extrahierte Daten für {consultant.aid}")

        extracted = extracted_data.get('extracted_data', {})
        if extracted is None:
            extracted = {}

        metadata = extracted_data.get('metadata', {})
        if metadata is None:
            metadata = {}

        raw_text = extracted_data.get('raw_text', '')

        # ============================================================
        # Persönliche Daten (mit degree)
        # ============================================================
        personal = extracted.get('personal', {})
        if personal is None:
            personal = {}

        consultant.first_name = personal.get('first_name', '')[:100] if personal.get('first_name') else consultant.first_name
        consultant.last_name = personal.get('last_name', '')[:100] if personal.get('last_name') else consultant.last_name
        consultant.birth_year = personal.get('birth_year') or consultant.birth_year
        consultant.nationality = personal.get('nationality', '')[:100] if personal.get('nationality') else consultant.nationality
        consultant.email = personal.get('email', '')[:500] if personal.get('email') else consultant.email
        consultant.phone = personal.get('phone', '')[:300] if personal.get('phone') else consultant.phone
        consultant.location = personal.get('location', '')[:200] if personal.get('location') else consultant.location
        consultant.availability = personal.get('availability', '')[:100] if personal.get('availability') else consultant.availability
        consultant.edv_experience_since = personal.get('edv_experience_since') or consultant.edv_experience_since
        consultant.headline = metadata.get('headline', '')[:500] if metadata.get('headline') else consultant.headline
        consultant.raw_text = raw_text

        # Metadaten
        consultant.company = metadata.get('company', '')[:200] if metadata.get('company') else consultant.company
        consultant.address = metadata.get('address', '')[:300] if metadata.get('address') else consultant.address
        consultant.website = metadata.get('website', '')[:500] if metadata.get('website') else consultant.website
        consultant.stand = metadata.get('stand', '')[:50] if metadata.get('stand') else consultant.stand

        # Akademischer Grad
        consultant.degree = personal.get('degree', '')[:200] if personal.get('degree') else consultant.degree

        consultant.save()

        # ============================================================
        # Sprachen
        # ============================================================
        consultant.languages.all().delete()
        languages_list = personal.get('languages', [])
        if languages_list:
            for lang_item in languages_list:
                if not lang_item:
                    continue
                # Beide Formate: str "Deutsch" oder dict {"name": "Deutsch", "level": "C2"}
                if isinstance(lang_item, dict):
                    lang_name = lang_item.get('name', '')
                    lang_level = lang_item.get('level', '')[:2]
                else:
                    # String-Format parsen: "Deutsch (Muttersprache)" -> name + level
                    s = str(lang_item).strip()
                    m = re.match(r'^(.+?)\s*\((.+?)\)\s*$', s)
                    if m:
                        lang_name  = m.group(1).strip()
                        level_text = m.group(2).strip().lower()
                        _level_map = {
                            'muttersprache': 'C2', 'native': 'C2',
                            'verhandlungssicher': 'C1', 'fliessend': 'C1',
                            'fließend': 'C1', 'fluent': 'C1',
                            'gut': 'B2', 'fortgeschritten': 'B2',
                            'good': 'B2', 'advanced': 'B2',
                            'grundkenntnisse': 'A2', 'basic': 'A2',
                        }
                        lang_level = _level_map.get(level_text, '')
                    else:
                        lang_name  = s
                        lang_level = ''
                if lang_name:
                    lang, _ = Language.objects.get_or_create(name=lang_name[:100])
                    ConsultantLanguage.objects.create(
                        consultant=consultant, language=lang, level=lang_level
                    )

        # ============================================================
        # SKILLS - aus Bloecken (Schritt 7) mit Kategorien
        # Projekt-Technologien kommen NICHT hier rein!
        # → werden in Schritt 10 via skill_normalizer geschrieben
        # ============================================================
        consultant.skills.all().delete()
        skills_data = extracted.get('skills', {})
        if skills_data is None:
            skills_data = {}

        skill_count = 0

        category_display = {
            'architecture_pattern':    'Architekturmuster',
            'business_software':       'Business Software',
            'ci_cd_tool':              'CI/CD Tools',
            'cloud_platform':          'Cloud-Plattformen',
            'communication_tool':      'Kommunikationstools',
            'database':                'Datenbanken',
            'data_format':             'Datenformate',
            'data_management':         'Datenmanagement',
            'development_environment': 'Entwicklungsumgebungen',
            'devops_tool':             'DevOps Tools',
            'documentation_tool':      'Dokumentationstools',
            'framework':               'Frameworks und Bibliotheken',
            'hardware':                'Hardware',
            'identity_management':     'Identity Management',
            'it_infrastructure':       'IT-Infrastruktur',
            'methodology':             'Methoden',
            'monitoring_tool':         'Monitoring Tools',
            'network_protocol':        'Netzwerkprotokolle',
            'operating_system':        'Betriebssysteme',
            'programming_languages':   'Programmiersprachen',
            'project_management':      'Projektmanagement Tools',
            'security_tool':           'Security Tools',
            'soft_skill':              'Soft Skills',
            'special_concept':         'Spezielle Konzepte',
            'special_skill':           'Sonstige Skills',
            'testing_tool':            'Testing Tools',
            'version_control':         'Versionsverwaltung',
            'virtualization':          'Virtualisierung',
        }

        for category_key, skills_list in skills_data.items():
            display_name = category_display.get(category_key, category_key)
            if skills_list:
                for skill_name in skills_list:
                    if skill_name and isinstance(skill_name, str) and len(skill_name) > 2:
                        skill = self._get_or_create_skill(skill_name, display_name)
                        if skill:
                            ConsultantSkill.objects.get_or_create(
                                consultant=consultant,
                                skill=skill,
                                defaults={'weight': 0.8}
                            )
                            skill_count += 1

        logger.info(f"   - Skills gespeichert: {skill_count} Einträge")

        # ============================================================
        # Zertifikate
        # Typ 'course' → Education (education_type='course')
        # Typ 'certification' → Certification + ConsultantCertification
        # ============================================================
        consultant.certifications.all().delete()
        certifications_list = extracted.get('certifications', [])
        if certifications_list:
            for cert_data in certifications_list:
                name        = cert_data.get('name', '')
                issuer_name = cert_data.get('issuer', '')
                date_obtained = cert_data.get('date_obtained', '')
                entry_type  = cert_data.get('type', 'certification')
                if name:
                    if entry_type == 'course':
                        Education.objects.get_or_create(
                            consultant=consultant,
                            degree=name[:200],
                            defaults={
                                'institution':    issuer_name[:200] if issuer_name else '',
                                'education_type': 'course',
                            }
                        )
                    else:
                        issuer = None
                        if issuer_name:
                            issuer, _ = Issuer.objects.get_or_create(name=issuer_name[:200])
                        cert, _ = Certification.objects.get_or_create(
                            name=name[:200],
                            defaults={'issuer': issuer}
                        )
                        ConsultantCertification.objects.get_or_create(
                            consultant=consultant,
                            certification=cert,
                            defaults={'date_obtained': date_obtained[:50] if date_obtained else ''}
                        )

        # ============================================================
        # Ausbildung + Schulungen
        # Reihenfolge: delete → education (degree) → schulungen (course)
        # ============================================================
        consultant.education.all().delete()

        # 1. Akademische Abschlüsse (education_type='degree')
        education_list = extracted.get('education', [])
        if education_list:
            for edu_data in education_list:
                if edu_data.get('degree') or edu_data.get('description'):
                    Education.objects.create(
                        consultant=consultant,
                        degree=(edu_data.get('degree', '') or '')[:200],
                        institution=(edu_data.get('institution', '') or '')[:200],
                        period=(edu_data.get('period', '') or '')[:100],
                        description=(edu_data.get('description', '') or '')[:500],
                        education_type=edu_data.get('education_type', 'degree') or 'degree',
                        issuer=(edu_data.get('issuer', '') or '')[:200]
                    )

        # 2. Schulungen/Kurse (education_type='course')
        schulungen_list = extracted.get('schulungen', [])
        if schulungen_list:
            for s in schulungen_list:
                name = s.get('name', '') if isinstance(s, dict) else str(s)
                if name:
                    Education.objects.get_or_create(
                        consultant=consultant,
                        degree=name[:200],
                        defaults={'education_type': 'course'}
                    )
            logger.info(f"   - Schulungen gespeichert: {len(schulungen_list)}")

        # ============================================================
        # Berufserfahrung (Projekte)
        # WICHTIG: ExperienceTechnology wird NICHT hier geschrieben!
        # Technologien bleiben im RAM → skill_normalizer Schritt 10
        # schreibt ExperienceTechnology mit Kategorie + Gewichtung.
        # ============================================================
        consultant.experience.all().delete()
        experience_list = extracted.get('experience', [])
        if experience_list:
            for idx, exp_data in enumerate(experience_list):
                exp = Experience.objects.create(
                    consultant=consultant,
                    period=(exp_data.get('period', '') or '')[:50],
                    title=(exp_data.get('title', '') or '')[:200],
                    company=(exp_data.get('company', '') or '')[:200],
                    industry=(exp_data.get('industry', '') or '')[:100],
                    role=(exp_data.get('role', '') or '')[:200],
                    location=(exp_data.get('location', '') or '')[:200],
                    sort_order=idx
                )
                if exp_data.get('activities'):
                    for act in exp_data.get('activities', []):
                        if act:
                            ExperienceActivity.objects.create(
                                experience=exp,
                                activity_text=act[:500]
                            )
                # ExperienceTechnology → wird in Schritt 10 via skill_normalizer geschrieben

        # ============================================================
        # Branchen
        # ============================================================
        consultant.industries.all().delete()
        industries_list = extracted.get('industries', [])
        if industries_list:
            for industry_name in industries_list:
                if industry_name:
                    industry_name = self._clean_text(industry_name)
                    if not industry_name: continue
                    industry, _ = Industry.objects.get_or_create(name=industry_name[:200])
                    ConsultantIndustry.objects.get_or_create(
                        consultant=consultant,
                        industry=industry,
                        defaults={'weight': 0.5}
                    )

        # ============================================================
        # Fachbereiche
        # ============================================================
        consultant.focus_areas.all().delete()
        focus_areas_list = extracted.get('focus_areas', [])
        if focus_areas_list:
            for focus_name in focus_areas_list:
                if focus_name:
                    focus, _ = FocusArea.objects.get_or_create(name=focus_name[:200])
                    ConsultantFocusArea.objects.get_or_create(
                        consultant=consultant,
                        focus_area=focus,
                        defaults={'weight': 0.5}
                    )

        # ============================================================
        # Focus Experience (Produkte | Standards | Erfahrungen)
        # ============================================================
        consultant.focus_experience_items.all().delete()
        focus_experience_list = extracted.get('focus_experience', [])
        if focus_experience_list:
            for idx, item in enumerate(focus_experience_list):
                if item:
                    # Nur Strings durch _clean_text jagen, Dictionaries überspringen
                    if isinstance(item, str):
                        item = self._clean_text(item)
                        if not item: continue
                    if isinstance(item, dict):
                        fe_name     = (item.get('name', '') or '')[:500]
                        fe_category = (item.get('category', '') or '')[:100]
                        fe_order    = item.get('sort_order', idx)
                    else:
                        # Prüfe ob der String wie ein Dictionary aussieht
                        item_str = str(item)
                        if item_str.strip().startswith('{'):
                            try:
                                import ast
                                parsed = ast.literal_eval(item_str)
                                if isinstance(parsed, dict):
                                    fe_name     = (parsed.get('name', '') or '')[:500]
                                    fe_category = (parsed.get('category', '') or '')[:100]
                                    fe_order    = parsed.get('sort_order', idx)
                                else:
                                    fe_name     = item_str[:500]
                                    fe_category = 'product_standard'
                                    fe_order    = idx
                            except:
                                fe_name     = item_str[:500]
                                fe_category = 'product_standard'
                                fe_order    = idx
                        else:
                            fe_name     = item_str[:500]
                            fe_category = 'product_standard'
                            fe_order    = idx
                    if fe_name:
                        FocusExperience.objects.create(
                            consultant=consultant,
                            name=fe_name,
                            category=fe_category,
                            sort_order=fe_order
                        )

        # ============================================================
        # Other Content
        # ============================================================
        consultant.other_content.all().delete()
        other_list = extracted.get('other', [])
        if isinstance(other_list, list):
            for idx, item in enumerate(other_list):
                if isinstance(item, dict) and item.get('content'):
                    from ..models import OtherContent
                    OtherContent.objects.create(
                        consultant=consultant,
                        content=item.get('content', '')[:5000],
                        content_type=item.get('content_type', 'text')[:100],
                        source=item.get('source', '')[:200],
                        sort_order=item.get('sort_order', idx)
                    )
        elif isinstance(other_list, str) and other_list.strip():
            from ..models import OtherContent
            OtherContent.objects.create(
                consultant=consultant,
                content=other_list[:5000],
                content_type='text',
                source='pre_json',
                sort_order=0
            )

        logger.info(f"✅ Daten gespeichert für {consultant.aid}")
        logger.info(f"   - Projekte:        {consultant.experience.count()}")
        logger.info(f"   - Skills:          {consultant.skills.count()}")
        logger.info(f"   - Zertifikate:     {consultant.certifications.count()}")
        logger.info(f"   - Ausbildung:      {consultant.education.filter(education_type='degree').count()}")
        logger.info(f"   - Schulungen:      {consultant.education.filter(education_type='course').count()}")
        logger.info(f"   - Focus Experience:{consultant.focus_experience_items.count()}")
        logger.info(f"   - Degree:          {consultant.degree}")

        return consultant


extracted_to_db = ExtractedToDB()
