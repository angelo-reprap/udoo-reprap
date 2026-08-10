import logging
from .success_reply import PipelineSuccessReply
from .error_reply import PipelineErrorReply

logger = logging.getLogger(__name__)

def send_pipeline_success(email_to, name, aid, projects, skills, duration, de_editor_url, de_html_url, en_html_url):
    """Sendet Erfolgs-E-Mail nach erfolgreicher Pipeline"""
    try:
        data = {
            'name': name,
            'aid': aid,
            'projects': projects,
            'skills': skills,
            'duration': duration,
            'de_editor_url': de_editor_url,
            'de_html_url': de_html_url,
            'en_html_url': en_html_url,
        }
        reply = PipelineSuccessReply()
        subject = f"✅ CV erfolgreich verarbeitet und zur Validierung bereit: {name} ({aid})"
        return reply.send_success(email_to, data, subject)
    except Exception as e:
        logger.error(f"Fehler beim Senden der Erfolgs-E-Mail: {e}")
        return False

def send_pipeline_error(email_to, name, aid, error_code, error_detail, email_id):
    """Sendet Fehler-E-Mail bei Pipeline-Fehler"""
    try:
        data = {
            'name': name,
            'aid': aid,
            'email_id': email_id,
            'error': error_code,
            'error_detail': error_detail,
        }
        reply = PipelineErrorReply()
        subject = f"❌ CV-Verarbeitung fehlgeschlagen {error_code}: {name} ({aid})"
        return reply.send_error(email_to, data, subject)
    except Exception as e:
        logger.error(f"Fehler beim Senden der Fehler-E-Mail: {e}")
        return False
