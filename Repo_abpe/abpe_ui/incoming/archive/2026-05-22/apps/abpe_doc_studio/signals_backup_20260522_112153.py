"""
ABpE Doc Studio — Signals

Aufgaben:
  - DocTemplateVersion automatisch anlegen wenn DocTemplate gespeichert wird
  - DocTemplate usage_count + last_used_at via DocLog-Signal aktualisieren
  - InvoiceRecord: auto invoice_number generieren (Fallback)
"""
import json
import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch           import receiver
from django.utils              import timezone

log = logging.getLogger('abpe_doc_studio.signals')


@receiver(pre_save, sender='abpe_doc_studio.DocTemplate')
def snapshot_template_version(sender, instance, **kwargs):
    """
    Vor jedem Speichern: prüfen ob sich html/blocks geändert haben.
    Wenn ja → neue Version anlegen (post_save macht das sauber).
    Flag setzen damit post_save weiß ob Version nötig.
    """
    if not instance.pk:
        instance._create_version = False
        return
    try:
        from .models import DocTemplate
        old = DocTemplate.objects.get(pk=instance.pk)
        # Version anlegen wenn sich irgendetwas Wesentliches ändert
        changed = (
            old.layout_id    != instance.layout_id    or
            old.style_kit_id != instance.style_kit_id or
            old.variables    != instance.variables     or
            old.status       != instance.status
        )
        instance._create_version = changed
    except Exception:
        instance._create_version = False


@receiver(post_save, sender='abpe_doc_studio.DocTemplate')
def create_template_version(sender, instance, created, **kwargs):
    """
    Nach dem Speichern: Version anlegen wenn Flag gesetzt oder neu erstellt.
    """
    from .models import DocTemplateVersion, DocTemplateBlock

    if not (created or getattr(instance, '_create_version', False)):
        return

    try:
        # Block-Snapshot bauen
        blocks_snapshot = list(
            DocTemplateBlock.objects
            .filter(template=instance)
            .order_by('slot', 'order')
            .values(
                'slot', 'order', 'block__identifier',
                'style_override', 'content_override',
                'conditional', 'page_break_before'
            )
        )

        snapshot = {
            'layout':     instance.layout.identifier if instance.layout_id else None,
            'style_kit':  instance.style_kit.identifier if instance.style_kit_id else None,
            'variables':  instance.variables,
            'status':     instance.status,
            'blocks':     blocks_snapshot,
        }

        # Nächste Versionsnummer
        last = DocTemplateVersion.objects.filter(
            template=instance
        ).order_by('-version').first()
        next_v = (last.version + 1) if last else 1

        DocTemplateVersion.objects.create(
            template    = instance,
            version     = next_v,
            snapshot    = snapshot,
            change_note = 'Auto-Snapshot bei Speicherung',
        )

        # active_version aktualisieren (ohne weiteres Signal)
        DocTemplate = sender
        DocTemplate.objects.filter(pk=instance.pk).update(active_version=next_v)

        log.info(f'DocTemplate {instance.identifier} → Version {next_v} angelegt')

    except Exception as e:
        log.warning(f'Version-Snapshot fehlgeschlagen für {instance.identifier}: {e}')


@receiver(post_save, sender='abpe_doc_studio.DocLog')
def update_template_usage(sender, instance, created, **kwargs):
    """
    Nach jedem erfolgreichen DocLog-Eintrag:
    Template usage_count + last_used_at aktualisieren.
    """
    if not created or not instance.template_id:
        return
    if instance.status == 'OK':
        from .models import DocTemplate
        DocTemplate.objects.filter(pk=instance.template_id).update(
            usage_count  = models_F('usage_count') + 1,
            last_used_at = timezone.now(),
        )


def models_F(field):
    """Lazy import von F um zirkuläre Imports zu vermeiden."""
    from django.db.models import F
    return F(field)
