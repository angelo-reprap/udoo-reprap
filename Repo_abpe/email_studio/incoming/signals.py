"""
ABpE Email Studio — Signals
============================
Automatische Versionierung beim Speichern eines Templates.
"""
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone


@receiver(pre_save, sender='abpe_email_studio.EmailTemplate')
def create_version_on_save(sender, instance, **kwargs):
    """
    Vor dem Speichern: neue Version anlegen wenn sich Inhalt geändert hat.
    """
    if not instance.pk:
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    content_changed = (
        old.subject   != instance.subject   or
        old.html_body != instance.html_body or
        old.text_body != instance.text_body or
        old.sender_mode != instance.sender_mode
    )
    if not content_changed:
        return

    from .models import EmailTemplateVersion
    next_version = (
        EmailTemplateVersion.objects
        .filter(template=old)
        .order_by('-version')
        .values_list('version', flat=True)
        .first() or 0
    ) + 1

    EmailTemplateVersion.objects.create(
        template    = old,
        version     = next_version,
        subject     = old.subject,
        html_body   = old.html_body,
        text_body   = old.text_body,
        variables   = old.variables,
        sender_mode = old.sender_mode,
        change_note = f'Auto-Version vor Änderung',
    )
    instance.active_version = next_version + 1


@receiver(post_save, sender='abpe_email_studio.EmailTemplate')
def set_first_version(sender, instance, created, **kwargs):
    """
    Bei neuem Template: erste Version anlegen.
    """
    if not created:
        return
    from .models import EmailTemplateVersion
    EmailTemplateVersion.objects.get_or_create(
        template = instance,
        version  = 1,
        defaults = {
            'subject':     instance.subject,
            'html_body':   instance.html_body,
            'text_body':   instance.text_body,
            'variables':   instance.variables,
            'sender_mode': instance.sender_mode,
            'change_note': 'Initiale Version',
        }
    )
