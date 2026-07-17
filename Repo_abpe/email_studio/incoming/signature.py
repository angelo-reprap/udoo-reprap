"""
ABpE Email Studio — Signatur Resolver
"""
import logging
log = logging.getLogger('abpe_email_studio.signature')


class SignatureResolver:

    def resolve(self, template, user=None):
        """
        Priorität:
        1. Am Template direkt zugewiesene Signatur
        2. Signatur des Absender-Kontos
        3. User-spezifische Signatur (per E-Mail Match)
        4. System-Default Signatur
        """
        from apps.abpe_email_studio.models import EmailSignature

        if template.signature:
            return template.signature

        if user and user.email:
            sig = EmailSignature.objects.filter(
                sender_account__email=user.email
            ).first()
            if sig:
                return sig

        if template.sender_account:
            sig = EmailSignature.objects.filter(
                sender_account=template.sender_account,
                is_default=True
            ).first()
            if sig:
                return sig

        return EmailSignature.objects.filter(is_default=True).first()
