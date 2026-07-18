"""
ABpE UI Models
Nur für UI-spezifische Daten (Theme, Sprache, Einstellungen)
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _


class UserSettings(models.Model):
    """Benutzereinstellungen für UI"""
    
    class ThemeChoices(models.TextChoices):
        LIGHT = 'light', _('Hell')
        DARK = 'dark', _('Dunkel')
        SYSTEM = 'system', _('System folgen')
    
    class LanguageChoices(models.TextChoices):
        DE = 'de', _('Deutsch')
        EN = 'en', _('English')
    
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE,
        related_name='ui_settings'
    )
    
    # Theme Einstellungen
    theme = models.CharField(
        max_length=10,
        choices=ThemeChoices.choices,
        default=ThemeChoices.SYSTEM,
        verbose_name=_('Theme')
    )
    
    # Spracheinstellungen
    language = models.CharField(
        max_length=5,
        choices=LanguageChoices.choices,
        default=LanguageChoices.DE,
        verbose_name=_('Sprache')
    )
    
    # UI Einstellungen
    sidebar_collapsed = models.BooleanField(
        default=False,
        verbose_name=_('Sidebar eingeklappt')
    )
    
    # Zeitstempel
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Benutzereinstellungen')
        verbose_name_plural = _('Benutzereinstellungen')
    
    def __str__(self):
        return f"{self.user.username} - {self.theme}/{self.language}"
