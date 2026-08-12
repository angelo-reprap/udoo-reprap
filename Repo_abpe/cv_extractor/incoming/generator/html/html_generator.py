import os
import json
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from apps.cv_extractor.models import Consultant


class HTMLGenerator:
    def __init__(self, config_path='templates_config.json'):
        self.config_path = os.path.join(settings.BASE_DIR, 'apps/cv_extractor', config_path)
        self.config = self.load_config()

    def load_config(self):
        with open(self.config_path, 'r') as f:
            return json.load(f)

    def get_consultant_data(self, consultant):
        # Persoenliche Daten
        personal = {
            'first_name':           consultant.first_name or '',
            'last_name':            consultant.last_name or '',
            'full_name':            f"{consultant.first_name} {consultant.last_name}".strip() if consultant.show_name else consultant.aid,
            'birth_year':           consultant.birth_year,
            'nationality':          consultant.nationality or 'Deutsch',
            'email':                consultant.email or '',
            'phone':                consultant.phone or '',
            'location':             consultant.location or 'nach Absprache',
            'availability':         consultant.availability or 'nach Absprache',
            'edv_experience_since': consultant.edv_experience_since,
            'headline':             consultant.headline or '',
            'summary':              consultant.summary or '',
            'degree':               consultant.degree or '',
        }

        # Firmendaten
        company = {
            'name':    consultant.company or 'abcona e. K.',
            'address': consultant.address or 'Bornhohl 26, 61449 Steinbach',
            'website': consultant.website or 'http://www.abcona.de',
            'stand':   consultant.stand or '',
        }

        # Sprachen
        languages = []
        for lang in consultant.languages.all().select_related('language'):
            level = f" ({lang.get_level_display()})" if lang.level else ''
            languages.append(f"{lang.language.name}{level}")
        if not languages:
            languages = ['Deutsch', 'Englisch']

        # Ausbildung
        education = []
        for edu in consultant.education.filter(education_type='degree').order_by('-sort_order'):
            desc = edu.degree or edu.description or ''
            if edu.institution:
                desc += f" @ {edu.institution}"
            education.append({
                'period':      edu.period or '',
                'description': desc,
            })

        # Fachbereiche
        focus_areas = [
            fa.focus_area.name
            for fa in consultant.focus_areas.all().select_related('focus_area')
        ]

        # Zertifizierungen
        certifications = [
            cert.certification.name
            for cert in consultant.certifications.all().select_related('certification')
        ]
        products = [fi.name for fi in consultant.focus_experience_items.all()]
        trainings = [
            cert.certification.name
            for cert in consultant.certifications.all().select_related('certification')
            if any(kw in cert.certification.name.lower()
                   for kw in ['kurs', 'schulung', 'engineer', 'administrator',
                               'analyst', 'core', 'operator', 'training', 'support'])
        ] or []

        # Branchen
        industries = [
            ind.industry.name
            for ind in consultant.industries.all().select_related('industry')
        ]

        # Skills nach Kategorie
        # WICHTIG: cs.category_name hat Vorrang vor skill.category.name
        # cs.category_name wird von main_skill_normalizer pro Consultant gesetzt
        # skill.category ist das globale Skill-Objekt das veraltet sein kann
        skills_by_cat = {}
        all_skill_names = []
        for cs in consultant.skills.all().select_related('skill', 'skill__category'):
            name = cs.skill.name
            all_skill_names.append(name)
            # cs.category_name ist die korrekte Kategorie für diesen Consultant
            cat = (cs.category_name or
                   (cs.skill.category.name if cs.skill.category else 'other'))
            skills_by_cat.setdefault(cat, []).append(name)

        # Kategorie-Mapping: DB-Name → Schlüssel
        cat_aliases = {
            'Programmiersprachen':        ['Programmiersprachen', 'programming_languages'],
            'Betriebssysteme':            ['Betriebssysteme', 'operating_system'],
            'Hardware':                   ['Hardware', 'hardware'],
            'Netzwerkprotokolle':         ['Netzwerkprotokolle', 'network_protocol'],
            'Security Tools':             ['Security Tools', 'security_tool'],
            'Cloud-Plattformen':          ['Cloud-Plattformen', 'cloud_platform'],
            'DevOps Tools':               ['DevOps Tools', 'devops_tool'],
            'Datenbanken':                ['Datenbanken', 'database'],
            'Frameworks und Bibliotheken':['Frameworks und Bibliotheken', 'framework'],
            'Virtualisierung':            ['Virtualisierung', 'virtualization'],
            'Methoden':                   ['Methoden', 'methodology'],
            'IT-Infrastruktur':           ['IT-Infrastruktur', 'it_infrastructure'],
        }

        def get_cat(cat_name):
            aliases = cat_aliases.get(cat_name, [cat_name])
            for alias in aliases:
                vals = skills_by_cat.get(alias, [])
                if vals:
                    return list(dict.fromkeys(vals))
            return []

        # Projekte – neueste zuerst
        experiences = []
        for exp in consultant.experience.all().prefetch_related(
            'activities', 'technologies__skill'
        ):
            activities   = [a.activity_text for a in exp.activities.all()]
            technologies = [t.skill.name for t in exp.technologies.all()]
            experiences.append({
                'period':       exp.period or '',
                'company':      exp.company or '',
                'role':         exp.role or exp.title or '',
                'activities':   activities,
                'technologies': technologies,
            })

        def sort_key(e):
            p = e['period']
            m = __import__('re').search(r'(\d{2})/(\d{4})', p[:15] if p else '')
            if m:
                return (int(m.group(2)), int(m.group(1)))
            return (0, 0)

        experiences.sort(key=sort_key, reverse=True)

        # Alle befüllten Kategorien dynamisch — nach Gewichtung sortiert
        from collections import defaultdict
        cat_weights = defaultdict(list)
        for cs in consultant.skills.all().select_related('skill'):
            # cs.category_name hat Vorrang
            cat = (cs.category_name or
                   (cs.skill.category.name if cs.skill.category else None))
            if cat and cat not in ('IT-Infrastruktur',):
                cat_weights[cat].append(cs.weight)

        sorted_cats = sorted(
            [(cat, sum(w)/len(w), skills_by_cat.get(cat, []))
             for cat, w in cat_weights.items()
             if skills_by_cat.get(cat)],
            key=lambda x: x[1],
            reverse=True
        )

        SKILL_CAT_DE_EN = {
            'Programmiersprachen':        'Programming Languages',
            'Betriebssysteme':            'Operating Systems',
            'Datenbanken':                'Databases',
            'Frameworks':                 'Frameworks',
            'Entwicklungsumgebungen':     'Development Environments',
            'Versionsverwaltung':         'Version Control',
            'Projektmanagement':          'Project Management',
            'Netzwerk':                   'Networking',
            'Cloud':                      'Cloud',
            'Testing':                    'Testing',
            'Soft Skills':                'Soft Skills',
            'Sonstiges':                  'Other',
            'Methodiken':                 'Methodologies',
            'Kommunikation':              'Communication',
            'Embedded':                   'Embedded',
            'Hardware':                   'Hardware',
            'Sicherheit':                 'Security',
            'IT-Infrastruktur':           'IT Infrastructure',
            'Netzwerkprotokolle':         'Network Protocols',
            'Dokumentationstools':        'Documentation Tools',
            'Spezielle Konzepte':         'Special Concepts',
            'Kommunikationstools':        'Communication Tools',
            'Architekturmuster':          'Architecture Patterns',
            'Datenmanagement':            'Data Management',
            'Sonstige Skills':            'Other Skills',
            'Frameworks und Bibliotheken':'Frameworks and Libraries',
            'Business Software':          'Business Software',
            'Testing Tools':              'Testing Tools',
            'DevOps Tools':               'DevOps Tools',
            'Virtualisierung':            'Virtualization',
            'CI/CD Tools':                'CI/CD Tools',
            'Methoden':                   'Methodologies',
            'Cloud-Plattformen':          'Cloud Platforms',
            'Security Tools':             'Security Tools',
            'Projektmanagement Tools':    'Project Management Tools',
            'Monitoring Tools':           'Monitoring Tools',
            'Identity Management':        'Identity Management',
            'Datenformate':               'Data Formats',
        }

        _lang = getattr(consultant, 'language', 'de') or 'de'
        skills_sections = [
            {'name': SKILL_CAT_DE_EN.get(cat, cat) if _lang == 'en' else cat,
             'skills': list(dict.fromkeys(skills))}
            for cat, avg_weight, skills in sorted_cats
            if skills
        ]

        # Schulungen aus Education
        schulungen = [
            edu.degree
            for edu in consultant.education.filter(education_type='course')
            if edu.degree
        ]

        # Sonstige Inhalte (OtherContent)
        from apps.cv_extractor.models import OtherContent
        other_content = [
            o.content
            for o in OtherContent.objects.filter(consultant=consultant).order_by('sort_order')
            if o.content and o.content.strip()
            and 'keine sonstigen' not in o.content.lower()
        ]

        return {
            'personal':        personal,
            'company':         company,
            'languages':       languages,
            'education':       [e for e in education if e.get('period') or e.get('description')],
            'focus_areas':     focus_areas,
            'certifications':  certifications,
            'products':        products,
            'courses':         schulungen or trainings,
            'industries':      industries,
            'experiences':     experiences,
            'skills_sections': skills_sections,
            'all_skills':      list(dict.fromkeys(all_skill_names)),
            'other_content':   other_content,
            'date':            timezone.now(),
        }

    def generate(self, template_name, consultant, aid=None, version=None):
        template_config = self.config['templates'].get(template_name)
        if not template_config:
            raise ValueError(f"Template {template_name} nicht gefunden")

        aid     = aid     or consultant.aid
        version = version or consultant.version

        context            = self.get_consultant_data(consultant)
        context['aid']     = aid
        context['version'] = version

        lang      = getattr(consultant, 'language', 'de') or 'de'
        tpl_file  = 'template-en.html' if lang == 'en' else 'template.html'
        template_path = f"{template_config['source_dir']}/{tpl_file}"

        from django.template.loader import get_template
        from django.template.exceptions import TemplateDoesNotExist
        try:
            get_template(template_path)
        except TemplateDoesNotExist:
            template_path = f"{template_config['source_dir']}/template.html"

        html_content = render_to_string(template_path, context)

        dir_name = consultant.consultant_dir or f"{consultant.last_name.lower()}_{consultant.first_name.lower()}"
        if not dir_name.strip('_'):
            dir_name = consultant.aid.lower()

        target_dir = os.path.join(settings.BASE_DIR, template_config['target_dir'], dir_name)
        os.makedirs(target_dir, exist_ok=True)

        filename = f"{aid}{template_config['filename_suffix']}.html"
        filepath = os.path.join(target_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

        try:
            relative_path = os.path.relpath(filepath, settings.BASE_DIR)
            url = f"/{relative_path}"
        except ValueError:
            url = filepath

        return {'filepath': filepath, 'url': url, 'filename': filename, 'directory': dir_name}

    def generate_all(self, consultant, aid=None, version=None):
        results = {}
        for template_name in self.config['templates']:
            if self.config['templates'][template_name].get('format') == 'docx':
                continue
            results[template_name] = self.generate(template_name, consultant, aid, version)
        return results
