"""
ABpE Email Studio — Email Sender Service
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from django.conf import settings
from django.utils import timezone

log = logging.getLogger('abpe_email_studio.sender')


class EmailSender:

    def __init__(self):
        self.host     = getattr(settings, 'EMAIL_HOST',          'smtp.ionos.de')
        self.port     = getattr(settings, 'EMAIL_PORT',          587)
        self.use_tls  = getattr(settings, 'EMAIL_USE_TLS',       True)
        self.username = getattr(settings, 'EMAIL_HOST_USER',     '')
        self.password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')

    def _resolve_from(self, template, user=None) -> tuple[str, str]:
        """Gibt (from_email, from_name) zurück je nach Sender-Modus."""
        from apps.abpe_email_studio.models import SenderMode
        if template.sender_mode == SenderMode.USER and user and user.email:
            name = f'{user.first_name} {user.last_name}'.strip() or user.username
            return user.email, name
        elif template.sender_mode == SenderMode.AUTO:
            return 'noreply@abcona.de', 'ABpE System'
        elif template.sender_account:
            return template.sender_account.email, template.sender_account.display_name
        return self.username or 'task@abcona.de', 'ABpE Portal'

    def _resolve_reply_to(self, template, user=None) -> str:
        from apps.abpe_email_studio.models import SenderMode
        if template.sender_mode == SenderMode.USER and user and user.email:
            return user.email
        return ''

    def send(self, template, to_emails: list, variables: dict = None,
             user=None, cc_extra: list = None, bcc_extra: list = None,
             task_reference: str = '', app_reference: str = '') -> dict:

        from apps.abpe_email_studio.services.renderer import EmailRenderer
        from apps.abpe_email_studio.models import EmailLog, LogStatus

        variables = variables or {}
        renderer  = EmailRenderer()

        from_email, from_name = self._resolve_from(template, user)
        reply_to              = self._resolve_reply_to(template, user)

        subject   = renderer.render_subject(template.subject, variables)
        html_body = renderer.render_html(template, variables, user)
        text_body = renderer.render_text(template, variables)

        cc  = template.get_cc_list() + (cc_extra or [])
        bcc = template.get_bcc_list() + (bcc_extra or [])

        status = LogStatus.OK
        error  = ''
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From']    = f'{from_name} <{from_email}>' if from_name else from_email
            msg['To']      = ', '.join(to_emails)
            if cc:
                msg['Cc']  = ', '.join(cc)
            if reply_to:
                msg['Reply-To'] = reply_to

            if template.sender_mode == 'AUTO':
                msg['X-Auto-Response-Suppress'] = 'All'
                msg['Auto-Submitted']            = 'auto-generated'

            if text_body:
                msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))

            all_recipients = to_emails + cc + bcc

            with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
                if self.use_tls:
                    smtp.starttls()
                if self.username and self.password:
                    smtp.login(self.username, self.password)
                smtp.sendmail(from_email, all_recipients, msg.as_string())

            log.info(f'Gesendet: {subject} → {to_emails}')

        except Exception as exc:
            status = LogStatus.FAILED
            error  = str(exc)
            log.error(f'Versand fehlgeschlagen: {exc}')

        # Template usage tracken
        template.usage_count += 1
        template.last_used_at = timezone.now()
        template.save(update_fields=['usage_count', 'last_used_at'])

        entry = EmailLog.objects.create(
            template         = template,
            template_version = template.active_version,
            from_email       = from_email,
            from_name        = from_name,
            sender_mode      = template.sender_mode,
            sent_by_user     = user,
            to_emails        = to_emails,
            cc_emails        = cc,
            bcc_emails       = bcc,
            reply_to         = reply_to,
            subject          = subject,
            html_body        = html_body,
            text_body        = text_body,
            variables_used   = variables,
            status           = status,
            error_message    = error,
            task_reference   = task_reference,
            app_reference    = app_reference,
        )

        if status == LogStatus.FAILED:
            raise Exception(error)

        return {'success': True, 'log_id': str(entry.log_id)}

    def test_connection(self):
        with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
            if self.use_tls:
                smtp.starttls()
            if self.username and self.password:
                smtp.login(self.username, self.password)
        return True
