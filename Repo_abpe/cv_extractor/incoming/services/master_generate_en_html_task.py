"""
master_generate_en_html_task.py
Stufe 3: EN-Version eines DE-Consultants generieren.

Ablauf:
  1. DE-Consultant aus DB laden
  2. extracted_json_export im RAM via master_translator_to_en uebersetzen
  3. EN-Consultant in DB anlegen (aid=AID-xx-en, language='en', aid_base=AID-xx)
  4. Skills + Technologien vom DE-Consultant uebernehmen
  5. EN-HTML generieren (AID-xx-en.html)

Aufgerufen von: tasks.py (generate_en_html_task)
Singleton: master_generate_en_html_task
"""
import logging
import copy

logger = logging.getLogger(__name__)


class MasterGenerateEnHtmlTask:

    def run(self, consultant_id: int) -> dict:
        """Hauptmethode: DE-Consultant -> EN-Consultant + HTML."""
        import time
        start = time.time()

        try:
            from apps.cv_extractor.models import Consultant
            de_consultant = Consultant.objects.get(id=consultant_id)
        except Exception as e:
            logger.error(f"[ENTask] Consultant {consultant_id} nicht gefunden: {e}")
            return {'success': False, 'error': str(e)}

        de_aid = de_consultant.aid
        en_aid = de_aid + '-en'
        logger.info(f"[ENTask] Start: {de_aid} -> {en_aid}")

        # 1. extracted_json_export im RAM uebersetzen
        try:
            from apps.cv_extractor.services.master_translator_to_en import master_translator_to_en
            de_json = de_consultant.extracted_json_export or {}
            pre_json = {
                'metadata':       de_json.get('metadata', {}),
                'extracted_data': de_json.get('extracted_data', {}),
                'audit':          de_json.get('audit', {}),
            }
            logger.info(f"[ENTask] Uebersetze {de_aid} ins Englische...")
            en_pre_json = master_translator_to_en.translate_pre_json(pre_json)
            logger.info(f"[ENTask] Uebersetzung abgeschlossen")
        except Exception as e:
            logger.error(f"[ENTask] Uebersetzung fehlgeschlagen: {e}")
            return {'success': False, 'error': f'Uebersetzung: {e}'}

        # 2. EN-Consultant in DB anlegen / aktualisieren
        try:
            from apps.cv_extractor.models import Consultant
            from apps.cv_extractor.enricher.extracted_to_db import extracted_to_db

            en_consultant, created = Consultant.objects.get_or_create(
                aid=en_aid,
                defaults={
                    'language':       'en',
                    'aid_base':       de_aid,
                    'consultant_dir': de_consultant.consultant_dir,
                    'version':        de_consultant.version,
                    'first_name':     de_consultant.first_name,
                    'last_name':      de_consultant.last_name,
                    'source_type':    de_consultant.source_type,
                    'status':         'processing',
                }
            )

            en_ed      = en_pre_json.get('extracted_data', {})
            en_personal = en_ed.get('personal', {})

            en_consultant.language             = 'en'
            en_consultant.aid_base             = de_aid
            en_consultant.consultant_dir       = de_consultant.consultant_dir
            en_consultant.version              = de_consultant.version
            en_consultant.first_name           = de_consultant.first_name
            en_consultant.last_name            = de_consultant.last_name
            en_consultant.source_type          = de_consultant.source_type
            en_consultant.headline             = en_personal.get('headline', de_consultant.headline)
            en_consultant.birth_year           = de_consultant.birth_year
            en_consultant.nationality          = en_personal.get('nationality', de_consultant.nationality)
            en_consultant.email                = de_consultant.email
            en_consultant.phone                = de_consultant.phone
            en_consultant.location             = de_consultant.location
            en_consultant.availability         = en_personal.get('availability', de_consultant.availability)
            en_consultant.edv_experience_since = de_consultant.edv_experience_since
            en_consultant.degree               = de_consultant.degree
            en_consultant.extracted_json_export = {
                'metadata':       en_pre_json.get('metadata', {}),
                'extracted_data': en_ed,
                'raw_text':       '',
            }
            en_consultant.status = 'processing'
            en_consultant.save()

            # DB-Relations befuellen (Experience, Zertifikate, Sprachen etc.)
            en_consultant = extracted_to_db.save(
                en_consultant,
                en_consultant.extracted_json_export
            )
            logger.info(f"[ENTask] EN-Consultant {'angelegt' if created else 'aktualisiert'}: {en_aid}")

        except Exception as e:
            logger.error(f"[ENTask] DB-Speicherung fehlgeschlagen: {e}")
            import traceback; traceback.print_exc()
            return {'success': False, 'error': f'DB: {e}'}

        # 3. Skills vom DE-Consultant uebernehmen
        try:
            from apps.cv_extractor.models import ConsultantSkill
            en_consultant.skills.all().delete()
            skills_copied = 0
            for cs in de_consultant.skills.all().select_related('skill'):
                ConsultantSkill.objects.update_or_create(
                    consultant=en_consultant,
                    skill=cs.skill,
                    defaults={
                        'weight':         cs.weight,
                        'category_name':  cs.category_name,
                        'last_used_year': cs.last_used_year,
                    }
                )
                skills_copied += 1
            logger.info(f"[ENTask] Skills uebernommen: {skills_copied}")
        except Exception as e:
            logger.warning(f"[ENTask] Skills Fehler: {e}")

        # 4. Technologien pro Projekt uebernehmen
        try:
            from apps.cv_extractor.models import ExperienceTechnology
            de_exps = list(de_consultant.experience.all().order_by('sort_order', 'id'))
            en_exps = list(en_consultant.experience.all().order_by('sort_order', 'id'))
            tech_copied = 0
            for de_exp, en_exp in zip(de_exps, en_exps):
                en_exp.technologies.all().delete()
                for tech in de_exp.technologies.all().select_related('skill'):
                    ExperienceTechnology.objects.create(
                        experience=en_exp,
                        skill=tech.skill
                    )
                    tech_copied += 1
            logger.info(f"[ENTask] Technologien uebernommen: {tech_copied}")
        except Exception as e:
            logger.warning(f"[ENTask] Technologien Fehler: {e}")

        # 5. EN-HTML generieren
        try:
            from apps.cv_extractor.generator.html.html_generator import HTMLGenerator
            gen = HTMLGenerator()
            gen.generate('aid-profile', en_consultant)
            gen.generate('aid-short',   en_consultant)
            logger.info(f"[ENTask] HTML generiert: {en_aid}")
        except Exception as e:
            logger.warning(f"[ENTask] HTML Fehler: {e}")

        # 6. Status abschliessen
        en_consultant.status = 'completed'
        en_consultant.save(update_fields=['status', 'updated_at'])

        duration = round(time.time() - start, 1)
        logger.info(f"[ENTask] FERTIG: {en_aid} in {duration}s")

        return {
            'success':    True,
            'de_aid':     de_aid,
            'en_aid':     en_aid,
            'created':    created,
            'duration':   duration,
            'editor_url': f'/cv-extractor/editor/{en_aid}/',
        }


master_generate_en_html_task = MasterGenerateEnHtmlTask()
