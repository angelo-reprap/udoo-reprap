"""
main_extracted_to_db.py - Schreibt main_pipeline pre_json in die relationale DB

Unterschiede zu extracted_to_db.py:
- Liest headline auch aus personal{} nicht nur aus metadata{}
- Schulungen + Ausbildung kommen als education[] mit education_type='degree'/'course'
- consultant.degree wird aus education[] gefüllt wenn personal.degree leer
- skill_ablage wird ignoriert (geht direkt in main_db_importer)
- Keine ExperienceTechnology hier — kommt vom skill_normalizer
"""
import re
import logging
from typing import Dict, Any
from django.db import transaction

from ..models import (
    Consultant, Skill, Certification, Issuer, ConsultantCertification,
    Education, Experience, Industry, ConsultantIndustry,
    FocusArea, ConsultantFocusArea, Language, ConsultantLanguage,
    FocusExperience, ConsultantSkill, SkillCategory,
    ExperienceActivity, OtherContent
)

logger = logging.getLogger(__name__)

CATEGORY_DISPLAY = {
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

LEVEL_MAP = {
    'muttersprache': 'C2', 'native': 'C2',
    'verhandlungssicher': 'C1', 'fliessend': 'C1',
    'fließend': 'C1', 'fluent': 'C1',
    'gut': 'B2', 'fortgeschritten': 'B2', 'good': 'B2', 'advanced': 'B2',
    'grundkenntnisse': 'A2', 'basic': 'A2',
}


class MainExtractedToDB:

    def __init__(self):
        logger.info("✅ MainExtractedToDB initialisiert")

    def _clean(self, text: str) -> str:
        if not text:
            return ''
        for ch in ['□','☐','☑','☒','▪','▫','']:
            text = text.replace(ch, '')
        return text.strip()

    def _skill(self, name: str, cat_name: str = '') -> Skill:
        if not name or len(name) < 2:
            return None
        cat = SkillCategory.objects.filter(name=cat_name).first() if cat_name else None
        skill, created = Skill.objects.get_or_create(
            name=name[:200],
            defaults={'frequency': 1, 'category': cat,
                      'category_name': cat_name[:100] if cat_name else ''}
        )
        if not created:
            skill.frequency += 1
            skill.save(update_fields=['frequency'])
        return skill

    def _issuer(self, name: str) -> Issuer:
        if not name:
            return None
        issuer, created = Issuer.objects.get_or_create(
            name=name[:200], defaults={'frequency': 1}
        )
        if not created:
            issuer.frequency += 1
            issuer.save(update_fields=['frequency'])
        return issuer

    def _parse_language(self, lang_item) -> tuple:
        if isinstance(lang_item, dict):
            return lang_item.get('name', ''), lang_item.get('level', '')[:2]
        s = str(lang_item).strip()
        m = re.match(r'^(.+?)\s*\((.+?)\)\s*$', s)
        if m:
            return m.group(1).strip(), LEVEL_MAP.get(m.group(2).strip().lower(), '')
        return s, ''

    @transaction.atomic
    def save(self, consultant: Consultant, extracted_data: Dict[str, Any]) -> Consultant:
        logger.info(f"💾 MainExtractedToDB: Speichere {consultant.aid}")

        extracted = extracted_data.get('extracted_data', {}) or {}
        metadata  = extracted_data.get('metadata', {})  or {}
        personal  = extracted.get('personal', {})        or {}

        # ── Persönliche Daten ─────────────────────────────────────────────────
        if personal.get('first_name'):
            consultant.first_name = personal['first_name'][:100]
        if personal.get('last_name'):
            consultant.last_name = personal['last_name'][:100]
        if personal.get('birth_year'):
            consultant.birth_year = personal['birth_year']
        if personal.get('nationality'):
            consultant.nationality = personal['nationality'][:100]
        if personal.get('email'):
            consultant.email = personal['email'][:500]
        if personal.get('phone'):
            consultant.phone = personal['phone'][:300]
        if personal.get('location'):
            consultant.location = personal['location'][:200]
        if personal.get('availability'):
            consultant.availability = personal['availability'][:100]
        if personal.get('edv_experience_since'):
            consultant.edv_experience_since = personal['edv_experience_since']
        if personal.get('degree'):
            consultant.degree = personal['degree'][:200]
        if personal.get('summary'):
            consultant.summary = personal['summary'][:2000]
        if personal.get('website'):
            consultant.website = personal['website'][:500]

        # Headline: aus personal oder metadata
        headline = (personal.get('headline') or metadata.get('headline') or '').strip()
        if headline:
            consultant.headline = headline[:500]

        consultant.save()

        # ── Sprachen ──────────────────────────────────────────────────────────
        consultant.languages.all().delete()
        for lang_item in (personal.get('languages') or []):
            if not lang_item:
                continue
            name, level = self._parse_language(lang_item)
            if name:
                lang, _ = Language.objects.get_or_create(name=name[:100])
                ConsultantLanguage.objects.create(
                    consultant=consultant, language=lang, level=level
                )

        # ── Skills aus pre_json.skills{} ──────────────────────────────────────
        # Projekt-Technologien kommen NICHT hier — kommen vom skill_normalizer
        consultant.skills.all().delete()
        skill_count = 0
        for cat_key, skill_list in (extracted.get('skills') or {}).items():
            if not skill_list:
                continue
            cat_name = CATEGORY_DISPLAY.get(cat_key, cat_key)
            for name in skill_list:
                if name and isinstance(name, str) and len(name) > 2:
                    skill = self._skill(name, cat_name)
                    if skill:
                        ConsultantSkill.objects.get_or_create(
                            consultant=consultant, skill=skill,
                            defaults={'weight': 0.8, 'category_name': cat_name}
                        )
                        skill_count += 1
        logger.info(f"   - Skills gespeichert: {skill_count} Einträge")

        # ── Zertifikate ───────────────────────────────────────────────────────
        consultant.certifications.all().delete()
        for cert in (extracted.get('certifications') or []):
            if not cert or not cert.get('name'):
                continue
            name = self._clean(cert['name'])
            if not name:
                continue
            issuer   = self._issuer(cert.get('issuer', ''))
            cert_obj, cert_created = Certification.objects.get_or_create(
                name=name[:200],
                defaults={'issuer': issuer,
                          'issuer_name': cert.get('issuer', '')[:200]}
            )
            # issuer_name nachträglich setzen wenn leer
            if not cert_created and not cert_obj.issuer_name and cert.get('issuer'):
                cert_obj.issuer_name = cert['issuer'][:200]
                if issuer and not cert_obj.issuer:
                    cert_obj.issuer = issuer
                cert_obj.save(update_fields=['issuer_name', 'issuer'])
            ConsultantCertification.objects.get_or_create(
                consultant=consultant, certification=cert_obj,
                defaults={'date_obtained': (cert.get('date_obtained') or '')[:50]}
            )

        # ── Ausbildung + Schulungen ───────────────────────────────────────────
        # education[] enthält degree (Studium) + course (Schulungen)
        # education_type='degree' → consultant.degree setzen falls leer
        consultant.education.all().delete()
        for edu in (extracted.get('education') or []):
            if not edu:
                continue
            degree = (edu.get('degree') or edu.get('name') or edu.get('description') or '').strip()
            if not degree:
                continue
            edu_type = edu.get('education_type', 'degree')
            if edu_type not in ('degree', 'course', 'certification'):
                edu_type = 'degree'
            if str(edu_type).lower() in ('schulung', 'schulungen', 'training', 'kurs'):
                edu_type = 'course'
            Education.objects.create(
                consultant    = consultant,
                degree        = degree[:200],
                institution   = (edu.get('institution') or '')[:200],
                period        = (edu.get('period') or '')[:100],
                description   = (edu.get('description') or '')[:500],
                education_type= edu_type,
                issuer        = (edu.get('issuer') or '')[:200],
            )

        # Degree aus education[] ableiten wenn personal.degree leer
        if not consultant.degree:
            for edu in (extracted.get('education') or []):
                if (edu.get('education_type') == 'degree' and
                        edu.get('degree')):
                    consultant.degree = edu['degree'][:200]
                    consultant.save(update_fields=['degree', 'updated_at'])
                    break

        # Fallback: personal.degree → Education-Zeile wenn keine degree-Einträge
        if (consultant.degree and
                not consultant.education.filter(education_type='degree').exists()):
            Education.objects.create(
                consultant=consultant,
                degree=consultant.degree[:200],
                education_type='degree',
            )
        # ── Projekte ──────────────────────────────────────────────────────────
        # ExperienceTechnology wird NICHT hier geschrieben
        # → kommt vom skill_normalizer in main_db_importer
        consultant.experience.all().delete()
        for idx, exp in enumerate(extracted.get('experience') or []):
            if not exp:
                continue
            exp_obj = Experience.objects.create(
                consultant = consultant,
                period     = (exp.get('period') or '')[:50],
                title      = (exp.get('title') or '')[:200],
                company    = (exp.get('company') or '')[:200],
                industry   = (exp.get('industry') or '')[:100],
                role       = (exp.get('role') or '')[:200],
                location   = (exp.get('location') or '')[:200],
                sort_order = idx,
            )
            for act in (exp.get('activities') or []):
                if act:
                    ExperienceActivity.objects.create(
                        experience    = exp_obj,
                        activity_text = str(act)[:500],
                    )

        # ── Branchen ──────────────────────────────────────────────────────────
        consultant.industries.all().delete()
        for name in (extracted.get('industries') or []):
            name = self._clean(name)
            if name:
                ind, _ = Industry.objects.get_or_create(name=name[:200])
                ConsultantIndustry.objects.get_or_create(
                    consultant=consultant, industry=ind,
                    defaults={'weight': 0.5}
                )

        # ── Fachbereiche ──────────────────────────────────────────────────────
        consultant.focus_areas.all().delete()
        for name in (extracted.get('focus_areas') or []):
            if name:
                fa, _ = FocusArea.objects.get_or_create(name=str(name)[:200])
                ConsultantFocusArea.objects.get_or_create(
                    consultant=consultant, focus_area=fa,
                    defaults={'weight': 0.5}
                )

        # ── Focus Experience ──────────────────────────────────────────────────
        consultant.focus_experience_items.all().delete()
        for idx, item in enumerate(extracted.get('focus_experience') or []):
            if not item:
                continue
            if isinstance(item, dict):
                name  = self._clean(item.get('name') or '')
                cat   = (item.get('category') or 'product_standard')[:100]
                order = item.get('sort_order', idx)
            else:
                name  = self._clean(str(item))
                cat   = 'product_standard'
                order = idx
            if name:
                FocusExperience.objects.create(
                    consultant=consultant, name=name[:500],
                    category=cat, sort_order=order
                )

        # ── Other Content ─────────────────────────────────────────────────────
        consultant.other_content.all().delete()
        other = extracted.get('other', '')
        if isinstance(other, list):
            for idx, item in enumerate(other):
                if isinstance(item, dict) and item.get('content'):
                    OtherContent.objects.create(
                        consultant   = consultant,
                        content      = item['content'][:5000],
                        content_type = item.get('content_type', 'text')[:100],
                        source       = item.get('source', '')[:200],
                        sort_order   = item.get('sort_order', idx),
                    )
        elif isinstance(other, str) and other.strip():
            OtherContent.objects.create(
                consultant=consultant, content=other[:5000],
                content_type='text', source='pre_json', sort_order=0
            )

        # ── Logging ───────────────────────────────────────────────────────────
        logger.info(f"✅ Daten gespeichert für {consultant.aid}")
        logger.info(f"   - Projekte:         {consultant.experience.count()}")
        logger.info(f"   - Skills:           {consultant.skills.count()}")
        logger.info(f"   - Zertifikate:      {consultant.certifications.count()}")
        logger.info(f"   - Ausbildung:       {consultant.education.filter(education_type='degree').count()}")
        logger.info(f"   - Schulungen:       {consultant.education.filter(education_type='course').count()}")
        logger.info(f"   - Focus Experience: {consultant.focus_experience_items.count()}")
        logger.info(f"   - Branchen:         {consultant.industries.count()}")
        logger.info(f"   - Fachbereiche:     {consultant.focus_areas.count()}")
        logger.info(f"   - Headline:         {consultant.headline}")
        logger.info(f"   - Degree:           {consultant.degree}")

        return consultant


main_extracted_to_db = MainExtractedToDB()
