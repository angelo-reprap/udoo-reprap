"""
Erfolgs-Reply nach abgeschlossener CV-Pipeline
Umgestellt auf EmailStudio.send() — kein direktes SMTP mehr.
"""
import logging

logger = logging.getLogger(__name__)


class PipelineSuccessReply:
    """Sendet Erfolgs-E-Mail via EmailStudio"""

    def send_success(self, to_email, data, subject):
        try:
            from apps.abpe_email_studio.api import EmailStudio

            EmailStudio.send(
                template      = 'pipeline_success',
                recipient     = to_email,
                variables     = {
                    'name':           data.get('name', '-'),
                    'aid':            data.get('aid', '-'),
                    'projects':       str(data.get('projects', 0)),
                    'skills':         str(data.get('skills', 0)),
                    'duration':       str(data.get('duration', '-')),
                    'de_editor_url':  data.get('de_editor_url', '#'),
                    'de_html_url':    data.get('de_html_url', '#'),
                    'en_html_url':    data.get('en_html_url', '#'),
                },
                app_reference = 'ingest_email',
            )
            logger.info(f"✅ Success-Reply (pipeline_success) gesendet an {to_email}")
            return True

        except Exception as e:
            logger.error(f"❌ Success-Reply Fehler: {e}")
            return False
