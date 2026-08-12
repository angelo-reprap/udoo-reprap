"""
E-Mail-Service für Matching-Workflow
ERWEITERT mit Media-Integration und zusätzlichen Templates
"""
import logging
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from django.template import Template, Context
from django.core.mail import EmailMessage, send_mail
from django.conf import settings
from django.utils import timezone

from apps.automail_engine.services import email_sender
from ..models import EmailHistory, EmailTemplate, ProjectConsultant
from .ollama_matcher import ollama_matcher

logger = logging.getLogger(__name__)


class EmailService:
    """Service für E-Mail-Versand im Matching-Workflow"""

    # Verfügbare E-Mail-Typen
    EMAIL_TYPES = {
        'consultant_contact': 'Berater kontaktieren',
        'consultant_followup': 'Berater Nachfrage',
        'client_offer': 'Angebot an Kunde',
        'client_followup': 'Kunde Nachfrage',
        'consultant_rejection': 'Absage an Berater',
        'client_rejection': 'Absage an Kunde',
        'interview_request': 'Interview-Anfrage',
        'placement_info': 'Vermittlungsinfo',
        'consultant_no_feedback': 'Berater - kein Feedback',
        'client_no_feedback': 'Kunde - kein Feedback',
        'consultant_reminder': 'Berater Erinnerung',
        'client_reminder': 'Kunde Erinnerung',
    }

    @staticmethod
    def send_consultant_email(project_consultant: ProjectConsultant,
                              template: Optional[EmailTemplate] = None,
                              custom_text: Optional[str] = None,
                              attachments: Optional[List[Dict]] = None,
                              use_ollama: bool = True) -> bool:
        """
        Sendet E-Mail an Berater mit optionalen Anhängen

        Args:
            project_consultant: ProjectConsultant-Objekt
            template: Optional spezifisches Template
            custom_text: Optional eigener Text (überschreibt Template)
            attachments: Liste von Anhängen [{'filename': '', 'content': b'', 'mime_type': ''}]
            use_ollama: Ob Ollama für Textgenerierung genutzt werden soll

        Returns:
            True bei Erfolg, sonst False
        """
        project = project_consultant.project
        consultant = project_consultant.consultant

        # Template holen wenn nicht angegeben
        if not template:
            template = EmailTemplate.objects.filter(
                template_type='consultant_contact',
                is_active=True
            ).first()

        # Betreff und Body vorbereiten
        if custom_text:
            subject = f"Projektanfrage: {project.title}"
            body = custom_text
        elif template and template.use_ollama and use_ollama:
            # Mit Ollama generieren
            body, subject = EmailService._generate_with_ollama(
                project_consultant, template, 'consultant'
            )
        elif template:
            # Template rendern
            context = EmailService._get_context(project_consultant)
            body = EmailService._render_template(template.body, context)
            subject = EmailService._render_template(template.subject, context)
        else:
            # Fallback
            subject, body = EmailService._get_fallback_consultant_email(project_consultant)

        # Anhänge vorbereiten
        attachment_list = EmailService._prepare_attachments(attachments, project_consultant)

        # E-Mail senden
        try:
            success = email_sender.send_email(
                recipient=consultant.email,
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                attachments=attachment_list
            )

            # Verlauf speichern
            EmailHistory.objects.create(
                project_consultant=project_consultant,
                email_type=template.template_type if template else 'consultant_contact',
                recipient=consultant.email,
                subject=subject,
                body=body,
                status='sent' if success else 'failed',
                attachments=[a.get('filename') for a in attachment_list] if attachment_list else []
            )

            if success:
                # Status aktualisieren
                project_consultant.contacted_at = datetime.now()
                project_consultant.set_status('contacted', 'Erstkontakt per E-Mail')
                logger.info(f"✅ E-Mail an {consultant.email} gesendet")
            else:
                logger.error(f"❌ Fehler beim Senden an {consultant.email}")

            return success

        except Exception as e:
            logger.exception(f"❌ Fehler beim E-Mail-Versand: {e}")
            EmailHistory.objects.create(
                project_consultant=project_consultant,
                email_type=template.template_type if template else 'consultant_contact',
                recipient=consultant.email,
                subject=subject if 'subject' in locals() else '',
                body=body if 'body' in locals() else '',
                status='failed',
                error_message=str(e)
            )
            return False

    @staticmethod
    def send_client_offer(project_consultants: List[ProjectConsultant],
                          template: Optional[EmailTemplate] = None,
                          attachments: Optional[List[Dict]] = None,
                          use_ollama: bool = True) -> bool:
        """
        Sendet Matching-Angebot an Kunden

        Args:
            project_consultants: Liste von ProjectConsultant-Objekten
            template: Optional spezifisches Template
            attachments: Liste von Anhängen (Profile etc.)
            use_ollama: Ob Ollama für Textgenerierung genutzt werden soll

        Returns:
            True bei Erfolg, sonst False
        """
        if not project_consultants:
            return False

        project = project_consultants[0].project

        # Kunden-E-Mail aus Projekt
        recipient = project.customer_email
        if not recipient:
            logger.error(f"❌ Keine Kunden-E-Mail für Projekt {project.id}")
            return False

        # Template holen wenn nicht angegeben
        if not template:
            template = EmailTemplate.objects.filter(
                template_type='client_offer',
                is_active=True
            ).first()

        # Betreff und Body vorbereiten
        if template and template.use_ollama and use_ollama:
            # Mit Ollama generieren
            body, subject = EmailService._generate_client_offer_with_ollama(
                project, project_consultants, template
            )
        elif template:
            # Template rendern
            context = EmailService._get_client_context(project, project_consultants)
            body = EmailService._render_template(template.body, context)
            subject = EmailService._render_template(template.subject, context)
        else:
            # Fallback
            subject, body = EmailService._get_fallback_client_offer(project, project_consultants)

        # Anhänge vorbereiten (z.B. Beraterprofile als PDF)
        attachment_list = EmailService._prepare_attachments(attachments, project)

        try:
            success = email_sender.send_email(
                recipient=recipient,
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                attachments=attachment_list
            )

            # Für jeden Berater Verlauf speichern
            for pc in project_consultants:
                EmailHistory.objects.create(
                    project_consultant=pc,
                    email_type=template.template_type if template else 'client_offer',
                    recipient=recipient,
                    subject=subject,
                    body=body,
                    status='sent' if success else 'failed',
                    attachments=[a.get('filename') for a in attachment_list] if attachment_list else []
                )

                if success:
                    pc.offer_sent_at = datetime.now()
                    pc.set_status('offer_sent', 'Angebot an Kunde gesendet')
                    pc.save()

            if success:
                project.status = 'offers_sent'
                project.save()
                logger.info(f"✅ Angebot an {recipient} gesendet")

            return success

        except Exception as e:
            logger.exception(f"❌ Fehler beim Senden des Angebots: {e}")
            return False

    @staticmethod
    def send_followup_email(project_consultant: ProjectConsultant,
                            followup_type: str = 'consultant_followup') -> bool:
        """
        Sendet Nachfrage-E-Mail (wenn kein Feedback kam)

        Args:
            project_consultant: ProjectConsultant-Objekt
            followup_type: 'consultant_followup' oder 'client_followup'

        Returns:
            True bei Erfolg, sonst False
        """
        project = project_consultant.project
        consultant = project_consultant.consultant

        # Template holen
        template = EmailTemplate.objects.filter(
            template_type=followup_type,
            is_active=True
        ).first()

        if not template:
            logger.warning(f"⚠️ Kein Template für {followup_type} gefunden")
            return False

        # Kontext vorbereiten
        context = EmailService._get_context(project_consultant)
        context.update({
            'tage_seit_kontakt': (timezone.now().date() - project_consultant.contacted_at.date()).days,
            'letzter_kontakt': project_consultant.contacted_at.strftime('%d.%m.%Y'),
        })

        # Betreff und Body
        subject = EmailService._render_template(template.subject, context)
        body = EmailService._render_template(template.body, context)

        # Empfänger bestimmen
        if followup_type == 'consultant_followup':
            recipient = consultant.email
        else:
            recipient = project.customer_email

        if not recipient:
            logger.error(f"❌ Keine E-Mail-Adresse für Follow-up")
            return False

        try:
            success = email_sender.send_email(
                recipient=recipient,
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL
            )

            # Verlauf speichern
            EmailHistory.objects.create(
                project_consultant=project_consultant,
                email_type=followup_type,
                recipient=recipient,
                subject=subject,
                body=body,
                status='sent' if success else 'failed'
            )

            if success:
                project_consultant.set_status(
                    'followup_sent', 
                    f'Nachfrage gesendet nach {context["tage_seit_kontakt"]} Tagen'
                )
                logger.info(f"✅ Follow-up an {recipient} gesendet")

            return success

        except Exception as e:
            logger.exception(f"❌ Fehler beim Follow-up: {e}")
            return False

    @staticmethod
    def send_batch_followups(followup_type: str = 'consultant_followup',
                             days_wait: int = 7) -> Dict[str, Any]:
        """
        Sendet Follow-ups an alle, die nach X Tagen kein Feedback gaben

        Args:
            followup_type: Art des Follow-ups
            days_wait: Wartezeit in Tagen

        Returns:
            Dict mit Statistiken
        """
        from django.utils import timezone
        from datetime import timedelta

        cutoff_date = timezone.now() - timedelta(days=days_wait)

        # Finde ProjectConsultants ohne Antwort
        pending = ProjectConsultant.objects.filter(
            status='contacted',
            contacted_at__lte=cutoff_date,
            consultant_response_at__isnull=True
        ).select_related('project', 'consultant')

        sent = 0
        failed = 0

        for pc in pending:
            success = EmailService.send_followup_email(pc, followup_type)
            if success:
                sent += 1
            else:
                failed += 1

        logger.info(f"✅ Batch Follow-up: {sent} gesendet, {failed} fehlgeschlagen")
        return {
            'sent': sent,
            'failed': failed,
            'total': len(pending)
        }

    @staticmethod
    def send_reminder_email(project_consultant: ProjectConsultant,
                            reminder_type: str = 'consultant_reminder') -> bool:
        """
        Sendet Erinnerungs-E-Mail

        Args:
            project_consultant: ProjectConsultant-Objekt
            reminder_type: Art der Erinnerung

        Returns:
            True bei Erfolg, sonst False
        """
        template = EmailTemplate.objects.filter(
            template_type=reminder_type,
            is_active=True
        ).first()

        if not template:
            return False

        context = EmailService._get_context(project_consultant)
        
        subject = EmailService._render_template(template.subject, context)
        body = EmailService._render_template(template.body, context)

        recipient = project_consultant.consultant.email

        try:
            success = email_sender.send_email(
                recipient=recipient,
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL
            )

            EmailHistory.objects.create(
                project_consultant=project_consultant,
                email_type=reminder_type,
                recipient=recipient,
                subject=subject,
                body=body,
                status='sent' if success else 'failed'
            )

            return success

        except Exception as e:
            logger.error(f"❌ Fehler bei Erinnerung: {e}")
            return False

    @staticmethod
    def _get_context(project_consultant: ProjectConsultant) -> Dict[str, Any]:
        """Erstellt Kontext für Template-Rendering"""
        project = project_consultant.project
        consultant = project_consultant.consultant

        # Anrede bestimmen
        anrede = "Herr"
        if consultant.first_name and consultant.first_name.lower() in ['frau', 'fr']:
            anrede = "Frau"

        return {
            'projekt_titel': project.title,
            'projekt_id': project.project_number,
            'projekt_beschreibung': project.description,
            'berater_name': consultant.full_name,
            'berater_vorname': consultant.first_name,
            'berater_nachname': consultant.last_name,
            'berater_titel': consultant.title,
            'anrede': anrede,
            'start': project.start_date.strftime('%d.%m.%Y') if project.start_date else 'kurzfristig',
            'dauer': project.duration_months,
            'ort': project.location or 'Remote',
            'auslastung': project.workload_percent,
            'match_score': int(project_consultant.match_score * 100),
            'match_skills': project_consultant.match_details.get('matching_skills', []),
            'unternehmen': 'abcona e. K.',
            'absender': 'Angelo Malaguarnera',
            'telefon': '+49 6171 8867-12',
            'email': 'vertrieb@abcona.de',
            'datum_heute': datetime.now().strftime('%d.%m.%Y'),
        }

    @staticmethod
    def _get_client_context(project: Any, project_consultants: List[ProjectConsultant]) -> Dict[str, Any]:
        """Erstellt Kontext für Kunden-Template"""
        
        berater_liste = []
        for pc in project_consultants:
            c = pc.consultant
            berater_liste.append({
                'name': c.full_name,
                'titel': c.title,
                'match': int(pc.match_score * 100),
                'skills': c.skills_list[:5],
                'verfuegbar': c.available_from.strftime('%d.%m.%Y') if c.available_from else 'kurzfristig',
                'satz': c.hourly_rate_min or 'auf Anfrage',
            })

        return {
            'projekt_titel': project.title,
            'projekt_id': project.project_number,
            'kunde_name': project.customer_name,
            'kunde_ansprechpartner': project.customer_contact_person,
            'berater_liste': berater_liste,
            'start': project.start_date.strftime('%d.%m.%Y') if project.start_date else 'kurzfristig',
            'dauer': project.duration_months,
            'ort': project.location or 'Remote',
            'unternehmen': 'abcona e. K.',
            'absender': 'Angelo Malaguarnera',
            'telefon': '+49 6171 8867-12',
            'email': 'vertrieb@abcona.de',
            'datum_heute': datetime.now().strftime('%d.%m.%Y'),
        }

    @staticmethod
    def _render_template(template_text: str, context: Dict[str, Any]) -> str:
        """Rendert Template mit Context"""
        try:
            django_template = Template(template_text)
            return django_template.render(Context(context))
        except Exception as e:
            logger.error(f"❌ Template-Rendering Fehler: {e}")
            return template_text

    @staticmethod
    def _generate_with_ollama(project_consultant: ProjectConsultant,
                              template: EmailTemplate,
                              recipient_type: str) -> tuple:
        """
        Generiert E-Mail mit Ollama

        Returns:
            (body, subject)
        """
        try:
            if recipient_type == 'consultant':
                text = ollama_matcher.generate_consultant_email(
                    project_consultant.project,
                    project_consultant.consultant,
                    project_consultant.match_details,
                    save_result=True
                )
            else:
                text = ollama_matcher.generate_client_offer(
                    project_consultant.project,
                    [project_consultant.consultant],
                    [project_consultant.match_details],
                    save_result=True
                )

            # Subject aus erster Zeile extrahieren
            lines = text.strip().split('\n')
            subject = lines[0].replace('Betreff:', '').strip() if lines[0].startswith('Betreff:') else f"Projektanfrage: {project_consultant.project.title}"
            body = '\n'.join(lines[1:]) if lines[0].startswith('Betreff:') else text

            return body, subject

        except Exception as e:
            logger.error(f"❌ Ollama-Generierung fehlgeschlagen: {e}")
            context = EmailService._get_context(project_consultant)
            subject = EmailService._render_template(template.subject, context)
            body = EmailService._render_template(template.body, context)
            return body, subject

    @staticmethod
    def _generate_client_offer_with_ollama(project: Any,
                                          project_consultants: List[ProjectConsultant],
                                          template: EmailTemplate) -> tuple:
        """Generiert Kunden-Angebot mit Ollama"""
        try:
            consultants = [pc.consultant for pc in project_consultants]
            matches = [pc.match_details for pc in project_consultants]

            text = ollama_matcher.generate_client_offer(
                project,
                consultants,
                matches,
                save_result=True
            )

            lines = text.strip().split('\n')
            subject = lines[0].replace('Betreff:', '').strip() if lines[0].startswith('Betreff:') else f"Angebot: {project.title}"
            body = '\n'.join(lines[1:]) if lines[0].startswith('Betreff:') else text

            return body, subject

        except Exception as e:
            logger.error(f"❌ Ollama-Generierung fehlgeschlagen: {e}")
            context = EmailService._get_client_context(project, project_consultants)
            subject = EmailService._render_template(template.subject, context)
            body = EmailService._render_template(template.body, context)
            return body, subject

    @staticmethod
    def _get_fallback_consultant_email(project_consultant: ProjectConsultant) -> tuple:
        """Fallback-E-Mail für Berater"""
        pc = project_consultant
        subject = f"Projektanfrage: {pc.project.title}"
        
        body = f"""
Sehr geehrte/r {pc.consultant.full_name},

für einen unserer Kunden benötigen wir einen erfahrenen Berater:

{pc.project.title} – {pc.project.location or 'Remote'} – {pc.project.start_date or 'ab sofort'} – {pc.project.duration_months} Monate

{pc.project.description[:300]}

Ihr Profil passt sehr gut (Match: {int(pc.match_score * 100)}%).

Wenn Sie Interesse haben, freue ich mich über Ihre Rückmeldung.

Mit freundlichen Grüßen

Angelo Malaguarnera
abcona e. K.
"""
        return subject, body

    @staticmethod
    def _get_fallback_client_offer(project: Any, project_consultants: List[ProjectConsultant]) -> tuple:
        """Fallback-Angebot für Kunden"""
        subject = f"Angebot: {project.title}"
        
        body = f"""
Sehr geehrte/r {project.customer_contact_person or project.customer_name},

für Ihr Projekt **„{project.title}“** reiche ich Ihnen folgende Berater ein:

"""
        for pc in project_consultants:
            c = pc.consultant
            body += f"""
• {c.full_name} - {c.title}
  Match: {int(pc.match_score * 100)}% - Skills: {', '.join(c.skills_list[:5])}
  Verfügbar: {c.available_from or 'kurzfristig'}
"""
        body += """

**Nächste Schritte:**
• Ich sende Ihnen auf Wunsch gerne die vollständigen Profile
• Wir können kurzfristig Interviews koordinieren

Mit freundlichen Grüßen

Angelo Malaguarnera
abcona e. K.
"""
        return subject, body

    @staticmethod
    def _prepare_attachments(attachments: Optional[List[Dict]], 
                             related_object: Any) -> List[Dict]:
        """Bereitet Anhänge für E-Mail vor"""
        if not attachments:
            return []

        prepared = []
        for att in attachments:
            # Prüfe ob Datei existiert
            if 'path' in att:
                try:
                    with open(att['path'], 'rb') as f:
                        content = f.read()
                    prepared.append({
                        'filename': att.get('filename', Path(att['path']).name),
                        'content': content,
                        'mime_type': att.get('mime_type', 'application/octet-stream')
                    })
                except Exception as e:
                    logger.error(f"❌ Fehler beim Lesen von Anhang {att.get('path')}: {e}")
            elif 'content' in att:
                prepared.append(att)

        return prepared

    @staticmethod
    def get_email_statistics() -> Dict[str, Any]:
        """Liefert Statistiken über versendete E-Mails"""
        from django.db.models import Count, Q

        total = EmailHistory.objects.count()
        sent = EmailHistory.objects.filter(status='sent').count()
        failed = EmailHistory.objects.filter(status='failed').count()
        
        # Nach Typ gruppieren
        by_type = EmailHistory.objects.values('email_type').annotate(
            count=Count('id'),
            success=Count('id', filter=Q(status='sent'))
        )

        return {
            'total_emails': total,
            'sent': sent,
            'failed': failed,
            'success_rate': round(sent / total * 100, 1) if total > 0 else 0,
            'by_type': list(by_type),
            'last_24h': EmailHistory.objects.filter(
                sent_at__gte=timezone.now() - timezone.timedelta(days=1)
            ).count(),
        }


# Singleton-Instanz
email_service = EmailService()
