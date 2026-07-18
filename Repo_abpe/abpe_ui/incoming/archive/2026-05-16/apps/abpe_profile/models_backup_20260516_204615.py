from django.db import models
from django.contrib.postgres.fields import JSONField
from django.utils import timezone
import uuid
import json


class BaseModel(models.Model):
    """Basisklasse für alle Modelle mit UUID und Timestamps"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Profile(BaseModel):
    """Beraterprofil - Zentrales Profil für Beraterdaten"""
    # Stammdaten
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=50, blank=True)
    mobile = models.CharField(max_length=50, blank=True)

    # Berufliche Daten
    title = models.CharField(max_length=200, blank=True)
    experience_years = models.IntegerField(default=0)
    available_from = models.DateField(null=True, blank=True)
    hourly_rate_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    hourly_rate_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Skills und Qualifikationen (als JSON)
    skills = models.JSONField(default=dict, blank=True)
    certifications = models.JSONField(default=list, blank=True)
    languages = models.JSONField(default=list, blank=True)
    industries = models.JSONField(default=list, blank=True)

    # Verknüpfungen
    user_id = models.UUIDField(null=True, blank=True)  # Django User
    consultant_id = models.UUIDField(null=True, blank=True)  # Consultant aus matching_workflow

    # Status
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    verification_date = models.DateTimeField(null=True, blank=True)

    # Metadaten
    data = models.JSONField(default=dict, blank=True)  # Zusätzliche flexible Daten
    source = models.CharField(max_length=50, default='manual')  # manual, import, email, etc.
    source_id = models.CharField(max_length=255, blank=True)  # ID im Quellsystem

    class Meta:
        verbose_name = "Profil"
        verbose_name_plural = "Profile"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['last_name', 'first_name']),
            models.Index(fields=['email']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def aid(self):
        """Gibt die zugehörige AID zurück, falls vorhanden"""
        if not self.data:
            return None
        return self.data.get('aid', {}).get('id')


class AIDRegistry(models.Model):
    """
    AID (Abcona Qualifikations Identifikationsnummer) Registry
    Eindeutige Identifikation für Beraterprofile

    Format: AID-[initials]_[role].[landscape].[experience].[index]
    Beispiel: AID-jm_2.1.3.1
    """

    # Rollen-Codes
    ROLE_ADMIN = 1
    ROLE_DEVELOPER = 2
    ROLE_ARCHITECT = 3
    ROLE_PROJECT_MANAGER = 4
    ROLE_OTHER = 5

    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Administrator'),
        (ROLE_DEVELOPER, 'Entwickler'),
        (ROLE_ARCHITECT, 'Technischer Architekt'),
        (ROLE_PROJECT_MANAGER, 'Projektleiter (IT Organisatorisch)'),
        (ROLE_OTHER, 'Sonstiges'),
    ]

    # Landschafts-Codes
    LANDSCAPE_CLIENT_SERVER = 1
    LANDSCAPE_MAINFRAME = 2
    LANDSCAPE_WEB = 3
    LANDSCAPE_CLOUD = 4
    LANDSCAPE_EMBEDDED = 5

    LANDSCAPE_CHOICES = [
        (LANDSCAPE_CLIENT_SERVER, 'Client Server'),
        (LANDSCAPE_MAINFRAME, 'Host/Mainframe'),
        (LANDSCAPE_WEB, 'Web'),
        (LANDSCAPE_CLOUD, 'Cloud & DevOps'),
        (LANDSCAPE_EMBEDDED, 'Embedded & IoT'),
    ]

    # Erfahrungslevel
    LEVEL_JUNIOR = 1
    LEVEL_SENIOR = 2
    LEVEL_EXPERT = 3
    LEVEL_SENIOR_EXPERT = 4
    LEVEL_OTHER = 5

    LEVEL_CHOICES = [
        (LEVEL_JUNIOR, 'Junior (0-3 Jahre)'),
        (LEVEL_SENIOR, 'Senior (3-7 Jahre)'),
        (LEVEL_EXPERT, 'Experte (7-12 Jahre)'),
        (LEVEL_SENIOR_EXPERT, 'Senior Experte (12+ Jahre)'),
        (LEVEL_OTHER, 'Sonstiges'),
    ]

    # Pflichtfelder
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    aid = models.CharField(max_length=50, unique=True, db_index=True)
    initials = models.CharField(max_length=10, db_index=True)
    role_code = models.IntegerField(choices=ROLE_CHOICES, db_index=True)
    landscape_code = models.IntegerField(choices=LANDSCAPE_CHOICES, db_index=True)
    experience_level = models.IntegerField(choices=LEVEL_CHOICES, db_index=True)
    duplicate_index = models.IntegerField(default=1)

    # ERWEITERUNG: Zusätzliche Felder für bessere Informationen
    role_name = models.CharField(max_length=50, blank=True, help_text="Ausgeschriebener Rollenname")
    landscape_name = models.CharField(max_length=50, blank=True, help_text="Ausgeschriebener Landschaftsname")
    confidence_score = models.FloatField(default=0.0, help_text="Konfidenzwert der Klassifikation (0-1)")

    # Verknüpfungen
    profile_id = models.UUIDField(null=True, blank=True, db_index=True)
    entity_id = models.UUIDField(null=True, blank=True, db_index=True)

    # Metadaten
    years_experience = models.IntegerField(default=0)
    profile_data = models.JSONField(default=dict, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AID Registry"
        verbose_name_plural = "AID Registry"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['initials', 'role_code', 'landscape_code', 'experience_level']),
            models.Index(fields=['profile_id']),
            models.Index(fields=['entity_id']),
            models.Index(fields=['created_at']),
        ]
        unique_together = [
            ['initials', 'role_code', 'landscape_code', 'experience_level', 'duplicate_index'],
        ]

    def __str__(self):
        return self.aid

    @property
    def full_aid(self):
        return self.aid

    @property
    def role_display(self):
        return dict(self.ROLE_CHOICES).get(self.role_code, 'Unbekannt')

    @property
    def landscape_display(self):
        return dict(self.LANDSCAPE_CHOICES).get(self.landscape_code, 'Unbekannt')

    @property
    def level_display(self):
        return dict(self.LEVEL_CHOICES).get(self.experience_level, 'Unbekannt')


class ProfileVersion(BaseModel):
    """Versionierung von Profil-Änderungen"""
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='versions')
    version = models.IntegerField()
    data = models.JSONField()
    change_summary = models.TextField(blank=True)
    created_by = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Profilversion"
        verbose_name_plural = "Profilversionen"
        ordering = ['-version']
        unique_together = ['profile', 'version']

    def __str__(self):
        return f"{self.profile} v{self.version}"
