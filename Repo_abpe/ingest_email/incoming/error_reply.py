"""
Fehler-Reply bei fehlgeschlagenem E-Mail Import
Umgestellt auf EmailStudio.send() — kein direktes SMTP mehr.
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

# Fehlermeldungen bleiben hier gepflegt — werden als Variablen übergeben
ERROR_MESSAGES = {
    'FORMULAR_FEHLT': {
        'error_title':    'CV-Formular nicht erkannt',
        'error_problem':  'Die E-Mail enthält kein gültiges CV-Formular.',
        'error_solution': 'Bitte verwenden Sie das Formular mit den Feldern '
                          '"Vorname *" und "Nachname *" in [ ] Klammern.',
    },
    'KEIN_ANHANG': {
        'error_title':    'Kein Anhang gefunden',
        'error_problem':  'Die E-Mail enthält keinen Anhang mit Ihrem Lebenslauf.',
        'error_solution': 'Bitte hängen Sie Ihren CV als PDF, DOC oder DOCX an.',
    },
    'UNGUELTIGER_DATEITYP': {
        'error_title':    'Ungültiger Dateityp',
        'error_problem':  'Die eingereichte Datei wird nicht unterstützt.',
        'error_solution': 'Unterstützte Formate: PDF, DOC, DOCX.',
    },
    'VORNAME_FEHLT': {
        'error_title':    'Vorname fehlt',
        'error_problem':  'Das Feld "Vorname" ist nicht ausgefüllt.',
        'error_solution': 'Format: Vorname * : [Ihr Vorname]',
    },
    'NACHNAME_FEHLT': {
        'error_title':    'Nachname fehlt',
        'error_problem':  'Das Feld "Nachname" ist nicht ausgefüllt.',
        'error_solution': 'Format: Nachname * : [Ihr Nachname]',
    },
}

DEFAULT_ERROR = {
    'error_title':    'CV-Verarbeitung fehlgeschlagen',
    'error_problem':  'Ein unerwarteter Fehler ist aufgetreten.',
    'error_solution': 'Bitte kontaktieren Sie den Support unter am@abcona.de.',
}


class PipelineErrorReply:
    """Sendet Fehler-E-Mail via EmailStudio"""

    def send_error(self, to_email, data, subject):
        try:
            from apps.abpe_email_studio.api import EmailStudio

            error_code   = data.get('error', 'UNKNOWN')
            error_detail = data.get('error_detail', '-')
            name         = data.get('name', '')
            email_id     = data.get('email_id', '-')

            msg = ERROR_MESSAGES.get(error_code, DEFAULT_ERROR).copy()

            # error_detail in problem einfließen lassen wenn vorhanden
            if error_detail and error_detail != '-':
                msg['error_problem'] = msg['error_problem'] + f' ({error_detail})'

            EmailStudio.send(
                template      = 'upload_error',
                recipient     = to_email,
                variables     = {
                    'name':           name,
                    'email_id':       str(email_id),
                    'error_code':     error_code,
                    'error_detail':   error_detail,
                    'original_subject': subject.replace('❌ CV-Import fehlgeschlagen: ', ''),
                    'date':           timezone.now().strftime('%d.%m.%Y %H:%M:%S'),
                    'import_time':    timezone.now().strftime('%d.%m.%Y %H:%M:%S'),
                    'solution':       msg.get('error_solution', ''),
                    'error_detail':   msg.get('error_problem', error_detail),
                },
                app_reference = 'ingest_email',
            )
            logger.info(f"✅ Error-Reply (upload_error) gesendet an {to_email} | Code: {error_code}")
            return True

        except Exception as e:
            logger.error(f"❌ Error-Reply Fehler: {e}")
            return False
