"""
tasks.py – Celery Tasks fuer CV-Extraktion (2-stufige Pipeline)

Stufe 1 (process_pdf_task) – synchron, ~60s:
  1. PDF extrahieren + DB speichern (pipeline.run)
  2. HTML Profile generieren
  3. search_enricher: searchable_text + facets + ES
  4. self_learning_pipeline: TrainingTerms aktualisieren
  → Status: 'profile_ready' → Frontend zeigt Editor-Link

Stufe 2 (enrich_consultant_task) – parallel, ~3-5min:
  1. db_enricher: summary + matching + statistics (LLM)
  2. skill_graph_builder: nodes + globale Edges (LLM)
  → Status: 'completed'

Signal start_pipeline_on_new_pdf startet process_pdf_task.
process_pdf_task startet enrich_consultant_task parallel.
"""

import logging
import os
import shutil
import traceback

from celery import shared_task
from django.conf import settings

from .models import ExtractionJob, UploadedPDF
from .pipeline import CvExtractionPipeline  # legacy, nur für Fallback
from .services.main_pipeline_controller import main_pipeline_controller

logger = logging.getLogger(__name__)


# ============================================================
# STUFE 1: Extraktion + HTML + Schnell-Enricher
# ============================================================

@shared_task(bind=True, name='cv_extractor.process_pdf', max_retries=3)
def process_pdf_task(self, upload_id):
    """
    Stufe 1: PDF → DB → HTML → SearchEnricher → SelfLearning
    Startet anschliessend enrich_consultant_task parallel.
    """
    uploaded = None
    job      = None

    try:
        uploaded         = UploadedPDF.objects.get(id=upload_id)
        file_path        = uploaded.file.path
        first_name       = uploaded.first_name
        last_name        = uploaded.last_name
        target_directory = uploaded.target_directory or ''
        action_type      = uploaded.action_type      or 'new_version'

        import time as _time
        _t1_start = _time.time()
        logger.info(f"Stufe 1 Start: {first_name} {last_name} | action={action_type} | dir={target_directory}")

        # Datei ablegen und ggf. konvertieren
        filename = os.path.basename(file_path)
        is_doc   = filename.lower().endswith('.doc') and not filename.lower().endswith('.docx')

        doc_dir = os.path.join(settings.BASE_DIR, 'data', 'doc')
        pdf_dir = os.path.join(settings.BASE_DIR, 'data', 'pdf')
        os.makedirs(doc_dir, exist_ok=True)
        os.makedirs(pdf_dir, exist_ok=True)

        if is_doc:
            # .doc -> data/doc/ + nach PDF konvertieren
            doc_dest = os.path.join(doc_dir, filename)
            shutil.copy2(file_path, doc_dest)
            import subprocess
            result = subprocess.run([
                'libreoffice', '--headless', '--nofirststartwizard',
                '--norestore', '--convert-to', 'pdf',
                doc_dest, '--outdir', pdf_dir
            ], capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                raise RuntimeError(f"LibreOffice Fehler: {result.stderr}")
            pdf_name = os.path.splitext(os.path.basename(doc_dest))[0] + '.pdf'
            dest = os.path.join(pdf_dir, pdf_name)
            if not os.path.exists(dest):
                raise RuntimeError(f"PDF nicht erstellt: {dest}")
            logger.info(f"DOC -> PDF: {doc_dest} -> {dest}")
        elif filename.lower().endswith('.docx'):
            # .docx -> data/doc/ ablegen, bleibt als docx fuer word_extractor
            doc_dest = os.path.join(doc_dir, filename)
            shutil.copy2(file_path, doc_dest)
            dest = doc_dest
            logger.info(f"DOCX abgelegt: {dest}")
        else:
            # PDF -> data/pdf/
            dest = os.path.join(pdf_dir, filename)
            shutil.copy2(file_path, dest)

        # ExtractionJob anlegen
        job = ExtractionJob.objects.create(
            file_name=filename, file_path=dest, status='processing'
        )

        # ── Pipeline ausfuehren (main_pipeline_controller) ──
        result = main_pipeline_controller.run(
            pdf_path         = dest,
            first_name       = first_name,
            last_name        = last_name,
            dir_name         = target_directory or '',
            consultant_type  = 'IT-Freelancer',
        )

        if not result.get('success'):
            raise RuntimeError(result.get('error', 'Pipeline fehlgeschlagen'))

        aid            = result.get('aid', '')
        version        = result.get('version', '')
        consultant_dir = result.get('consultant_dir', '')

        # Consultant aus DB holen
        from .models import Consultant
        consultant = Consultant.objects.filter(aid=aid).first() if aid else None

        # Jobs + Upload aktualisieren
        job.status      = 'completed'
        job.result_json = result
        job.save(update_fields=['status', 'result_json'])

        uploaded.status         = 'profile_ready'
        uploaded.aid            = aid
        uploaded.version        = version
        uploaded.consultant_dir = consultant_dir
        if consultant:
            uploaded.consultant_id = consultant.id
        uploaded.save(update_fields=[
            'status', 'aid', 'version', 'consultant_dir', 'consultant_id'
        ])

        # Stufe 2 wird von main_db_importer gestartet — nicht doppelt starten

        _t1_end = _time.time()
        _t1_dur = int(_t1_end - _t1_start)
        _n_proj  = consultant.experience.count() if consultant else 0
        _n_skill = consultant.skills.count()     if consultant else 0
        logger.info("=" * 60)
        logger.info(f"✅ {aid} | {first_name} {last_name} | erfolgreich angelegt")
        logger.info(f"   Dauer: {_t1_dur}s | Projekte: {_n_proj} | Skills: {_n_skill}")
        logger.info("=" * 60)

        return {
            'success':        True,
            'job_id':         job.id,
            'aid':            aid,
            'version':        version,
            'consultant_dir': consultant_dir,
            'consultant':     consultant.id if consultant else None,
            'status':         'profile_ready',
            'editor_url':     f'/cv-extractor/editor/{aid}/' if aid else '',
        }

    except UploadedPDF.DoesNotExist:
        logger.error(f"Upload {upload_id} nicht gefunden")
        return {'success': False, 'error': f'Upload {upload_id} nicht gefunden'}

    except Exception as exc:
        logger.error(f"Stufe 1 fehlgeschlagen: {exc}")
        logger.error(traceback.format_exc())

        if uploaded:
            uploaded.status = 'failed'
            uploaded.save(update_fields=['status'])
        if job:
            job.status        = 'failed'
            job.error_message = str(exc)
            job.save(update_fields=['status', 'error_message'])

        try:
            raise self.retry(exc=exc, countdown=60)
        except self.MaxRetriesExceededError:
            return {'success': False, 'error': str(exc)}


# ============================================================
# STUFE 2: LLM Enricher (parallel)
# ============================================================

@shared_task(name='cv_extractor.enrich_consultant', max_retries=2)
def enrich_consultant_task(consultant_id):
    """
    Stufe 2: LLM-basierter Enricher – laeuft parallel zu Stufe 1.
    db_enricher: summary + matching + statistics
    skill_graph_builder: nodes + globale Edges
    """
    try:
        from .models import Consultant
        consultant = Consultant.objects.get(id=consultant_id)

        import time as _time
        _t2_start = _time.time()
        logger.info(f"Stufe 2 Start: {consultant.aid}")

        master_json = consultant.extracted_json_export or {}

        # ── DBEnricher (LLM) ──────────────────────────────────
        try:
            from .enricher.db_enricher import db_enricher
            master_json = db_enricher.enrich(consultant, master_json)
            logger.info(f"DBEnricher abgeschlossen fuer {consultant.aid}")
        except Exception as e:
            logger.error(f"DBEnricher Fehler: {e}")

        # ── SkillGraphBuilder (LLM) ───────────────────────────
        try:
            from .enricher.skill_graph_builder import skill_graph_builder
            master_json = skill_graph_builder.enrich(consultant, master_json)
            logger.info(f"SkillGraphBuilder abgeschlossen fuer {consultant.aid}")
        except Exception as e:
            logger.error(f"SkillGraphBuilder Fehler: {e}")

        # ── Master-JSON speichern ────────────────────────────
        consultant.extracted_json_export = master_json
        consultant.status         = 'completed'
        consultant.pipeline_step  = 'enriched'
        consultant.save(update_fields=[
            'extracted_json_export', 'status',
            'pipeline_step', 'updated_at'
        ])

        # ── UploadedPDF Status aktualisieren ─────────────────
        from .models import UploadedPDF
        UploadedPDF.objects.filter(
            consultant_id=consultant_id
        ).update(status='completed')

        # ── Erfolgs-E-Mail senden ────────────────────────────
        try:
            from apps.ingest_email.pipeline_notify import send_pipeline_success
            
            # Links generieren NUR mit DE Editor und HTML Links
            de_editor_url = f"https://abpe.win.abcona.info/cv-extractor/editor/{consultant.aid}/"
            de_html_url = f"https://abpe.win.abcona.info/data/html_out/{consultant.consultant_dir}/{consultant.aid}.html"
            en_html_url = f"https://abpe.win.abcona.info/data/html_out/{consultant.consultant_dir}/{consultant.aid}-en.html"

            # E-Mail Empfänger aus consultant.email oder Fallback
            email_to = consultant.email
            if not email_to:
                try:
                    upload = UploadedPDF.objects.filter(consultant_id=consultant.id).first()
                    if upload and upload.from_email:
                        email_to = upload.from_email
                except:
                    pass
            if not email_to:
                email_to = 'am@abcona.de'

            send_pipeline_success(
                email_to=email_to,
                name=f"{consultant.first_name} {consultant.last_name}",
                aid=consultant.aid,
                projects=consultant.experience.count(),
                skills=consultant.skills.count(),
                duration=int(_time.time() - _t2_start),
                de_editor_url=de_editor_url,
                de_html_url=de_html_url,
                en_html_url=en_html_url
            )
        except Exception as e:
            logger.warning(f"Erfolgs-E-Mail konnte nicht gesendet werden: {e}")

        _t2_end  = _time.time()
        _t2_dur  = int(_t2_end - _t2_start)
        logger.info("=" * 60)
        logger.info(f"✅ {consultant.aid} | Stufe 2 abgeschlossen")
        logger.info("=" * 60)
        logger.info(f"   Stufe 2:  {_t2_dur}s  ({_t2_dur//60} min {_t2_dur%60}s)")
        logger.info("=" * 60)

        # ── Stufe 3: EN-HTML im Hintergrund starten ─────────────────
        if consultant.language == 'de' and not consultant.aid_base:
            try:
                generate_en_html_task.delay(consultant.id)
                logger.info(f"Stufe 3 EN-HTML gestartet fuer {consultant.aid}")
            except Exception as e:
                logger.warning(f"Stufe 3 Start fehlgeschlagen: {e}")

        return {
            'success':      True,
            'aid':          consultant.aid,
            'status':       'completed',
            'editor_url':   f'/cv-extractor/editor/{consultant.aid}/',
        }

    except Exception as e:
        logger.error(f"Stufe 2 fehlgeschlagen (consultant_id={consultant_id}): {e}")
        logger.error(traceback.format_exc())
        return {'success': False, 'error': str(e)}


# ============================================================
# STUFE 2b: Self-Learning LLM (async, nach Stufe 2)
# ============================================================

@shared_task(name='cv_extractor.process_unknown_skills', max_retries=2)
def process_unknown_skills_task(consultant_id, unknown_skills):
    """
    Stufe 2b: Self-Learning LLM fuer unbekannte Skills.
    Startet sofort — wartet intern bis Experience-Objekte in DB verfuegbar.
    Laeuft parallel zu Stufe 2 (enrich_consultant_task).

    unknown_skills: Liste von Dicts aus main_skill_normalizer.normalize():
      [{'key': 'OSPF.AID-mm_1.2.3.1.exp_42&45.Mustermann.Max',
        'skill': 'OSPF',
        'context': 'Projekt: ...',
        'exp_ids': [42, 45],
        'count': 3}, ...]
    """
    try:
        if not unknown_skills:
            logger.info(f"process_unknown_skills_task: keine unbekannten Skills")
            return {'success': True, 'processed': 0}

        logger.info(
            f"Stufe 2b Start: consultant_id={consultant_id}, "
            f"{len(unknown_skills)} unbekannte Skills"
        )

        from .enricher.self_learning_pipeline import self_learning_pipeline
        stats = self_learning_pipeline.process_unknown_skills(unknown_skills)

        logger.info(f"Stufe 2b abgeschlossen: {stats}")
        return {'success': True, **stats}

    except Exception as e:
        logger.error(f"Stufe 2b fehlgeschlagen (consultant_id={consultant_id}): {e}")
        logger.error(traceback.format_exc())
        return {'success': False, 'error': str(e)}


# ============================================================
# STUFE 3: EN-HTML generieren (parallel, im Hintergrund)
# ============================================================

@shared_task(name='cv_extractor.generate_en_html', max_retries=2)
def generate_en_html_task(consultant_id):
    """
    Stufe 3: DE-Consultant → EN-Consultant + EN-HTML.
    Laeuft im Hintergrund nach Stufe 2.
    """
    try:
        from .services.main_generate_en_html_task import main_generate_en_html_task
        result = main_generate_en_html_task.run(consultant_id)
        logger.info(f"Stufe 3 EN-HTML: {result}")
        return result
    except Exception as e:
        logger.error(f"Stufe 3 fehlgeschlagen: {e}")
        return {'success': False, 'error': str(e)}


# ============================================================
# BATCH PROCESSING
# ============================================================

@shared_task(name='cv_extractor.generate_html')
def generate_html_task(consultant_id, template_name='aid-profile'):
    """Asynchrone HTML-Generierung fuer einen Consultant."""
    try:
        from .models import Consultant
        from .generator.html.html_generator import HTMLGenerator
        consultant = Consultant.objects.get(id=consultant_id)
        result     = HTMLGenerator().generate(template_name, consultant)
        return {'success': True, 'url': result['url']}
    except Exception as e:
        logger.error(f"HTML Fehler: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(name='cv_extractor.generate_word')
def generate_word_task(consultant_id):
    """Asynchrone Word-Generierung fuer einen Consultant."""
    try:
        from .models import Consultant
        from .generator.word.word_generator import WordGenerator
        consultant = Consultant.objects.get(id=consultant_id)
        result     = WordGenerator().generate(consultant)
        return {'success': True, 'url': result['url']}
    except Exception as e:
        logger.error(f"Word Fehler: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(name='cv_extractor.batch_process')
def batch_process_task(consultant_ids, template_names=None, include_word=False):
    """
    Batch-Verarbeitung: HTML + optional Word + Enricher.
    Beispiel: batch_process_task.delay([1,2,3], include_word=True)
    """
    results   = []
    templates = template_names or ['aid-profile', 'aid-short']

    for cid in consultant_ids:
        for tpl in templates:
            t = generate_html_task.delay(cid, tpl)
            results.append({'consultant_id': cid, 'template': tpl, 'task_id': t.id})
        if include_word:
            t = generate_word_task.delay(cid)
            results.append({'consultant_id': cid, 'template': 'word', 'task_id': t.id})
        # Enricher fuer existierende Consultants nachholen
        enrich_consultant_task.delay(cid)

    return {'success': True, 'tasks': results, 'total': len(results)}
