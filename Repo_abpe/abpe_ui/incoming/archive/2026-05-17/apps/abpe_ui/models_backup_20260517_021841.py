"""
ABpE UI Models
- UserSettings: UI-Einstellungen (Theme, Sprache)
- BeraterProfil: Brücke zwischen Django User und abpe_profile.Profile
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _


class UserSettings(models.Model):
    """Benutzereinstellungen für UI"""
    class ThemeChoices(models.TextChoices):
        LIGHT  = 'light',  _('Hell')
        DARK   = 'dark',   _('Dunkel')
        SYSTEM = 'system', _('System folgen')

    class LanguageChoices(models.TextChoices):
        DE = 'de', _('Deutsch')
        EN = 'en', _('English')

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='ui_settings'
    )
    theme = models.CharField(
        max_length=10,
        choices=ThemeChoices.choices,
        default=ThemeChoices.SYSTEM,
        verbose_name=_('Theme')
    )
    language = models.CharField(
        max_length=5,
        choices=LanguageChoices.choices,
        default=LanguageChoices.DE,
        verbose_name=_('Sprache')
    )
    sidebar_collapsed = models.BooleanField(
        default=False,
        verbose_name=_('Sidebar eingeklappt')
    )
    nav_order = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Navigations-Reihenfolge')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('Benutzereinstellungen')
        verbose_name_plural = _('Benutzereinstellungen')

    def __str__(self):
        return f"{self.user.username} - {self.theme}/{self.language}"


class BeraterProfil(models.Model):
    """
    Brücke zwischen Django User (auth_user) und abpe_profile.Profile.

    Externe Berater (abcona.de Homepage):
      - Gruppe 'berater'
      - Sehen nur ihr eigenes Profil

    Interne User (Portal):
      - Gruppen 'disponent', 'betreuer', 'admin'
      - Zugriff je nach Rolle auf alle/zugewiesene Profile
    """

    class StatusChoices(models.TextChoices):
        AKTIV      = 'aktiv',      _('Aktiv')
        INAKTIV    = 'inaktiv',    _('Inaktiv')
        GESPERRT   = 'gesperrt',   _('Gesperrt')
        IN_PRUEFUNG = 'in_pruefung', _('In Prüfung')

    # Verknüpfung zu Django User (1:1)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='berater_profil',
        verbose_name=_('Benutzer')
    )

    # Verknüpfung zu abpe_profile.Profile (optional, wird bei Registrierung gesetzt)
    profile = models.OneToOneField(
        'abpe_profile.Profile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='berater_profil',
        verbose_name=_('Profil')
    )

    # Betreuer (interner User der diesen Berater betreut)
    betreuer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='betreute_berater',
        verbose_name=_('Betreuer')
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.IN_PRUEFUNG,
        verbose_name=_('Status')
    )

    # Registrierung von abcona.de Homepage?
    ist_externer_berater = models.BooleanField(
        default=True,
        verbose_name=_('Externer Berater (Homepage)'),
        help_text=_('Berater der sich über abcona.de registriert hat')
    )

    # Notizen (intern, nur für Betreuer/Admin sichtbar)
    interne_notizen = models.TextField(
        blank=True,
        verbose_name=_('Interne Notizen')
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('Beraterprofil')
        verbose_name_plural = _('Beraterprofile')
        ordering            = ['-created_at']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.status})"

    @property
    def hat_profil(self):
        """Ist ein abpe_profile.Profile verknüpft?"""
        return self.profile is not None

    @property
    def ist_berater_gruppe(self):
        """Ist der User in der Gruppe 'berater'?"""
        return self.user.groups.filter(name='berater').exists()

    @property
    def rolle(self):
        """Gibt die primäre Rolle des Users zurück"""
        gruppen = list(self.user.groups.values_list('name', flat=True))
        for r in ['admin', 'betreuer', 'disponent', 'berater']:
            if r in gruppen:
                return r
        return 'unbekannt'


class UserModulePermission(models.Model):
    """
    User-spezifische Modul-Ausschlüsse.
    Wenn ein Eintrag existiert → User sieht dieses Modul NICHT.
    Unabhängig von der Gruppen-Rolle.
    """
    user      = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='module_permissions'
    )
    module_id = models.CharField(max_length=100)
    denied    = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together     = [['user', 'module_id']]
        verbose_name        = 'User Modul-Berechtigung'
        verbose_name_plural = 'User Modul-Berechtigungen'

    def __str__(self):
        status = 'gesperrt' if self.denied else 'erlaubt'
        return f"{self.user.username} → {self.module_id} ({status})"
