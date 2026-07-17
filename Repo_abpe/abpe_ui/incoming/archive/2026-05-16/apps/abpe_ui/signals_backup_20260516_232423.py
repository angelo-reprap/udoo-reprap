"""
signals.py - Automatische Erstellung von UserSettings + BeraterProfil
bei jedem neuen Django User
"""
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=User)
def create_user_profiles(sender, instance, created, **kwargs):
    """Erstellt UserSettings + BeraterProfil automatisch bei neuem User"""
    if not created:
        return

    # 1. UserSettings anlegen
    try:
        from apps.abpe_ui.models import UserSettings
        UserSettings.objects.get_or_create(user=instance)
        logger.info(f"✓ UserSettings für '{instance.username}' erstellt")
    except Exception as e:
        logger.warning(f"⚠ UserSettings für '{instance.username}' fehlgeschlagen: {e}")

    # 2. BeraterProfil anlegen (nur für nicht-Staff User)
    if not instance.is_staff and not instance.is_superuser:
        try:
            from apps.abpe_ui.models import BeraterProfil
            # Eindeutige Berater-ID generieren
            berater_id = f"B{instance.id:06d}"
            BeraterProfil.objects.get_or_create(
                user=instance,
                defaults={'berater_id': berater_id}
            )
            logger.info(f"✓ BeraterProfil '{berater_id}' für '{instance.username}' erstellt")
        except Exception as e:
            logger.warning(f"⚠ BeraterProfil für '{instance.username}' fehlgeschlagen: {e}")
