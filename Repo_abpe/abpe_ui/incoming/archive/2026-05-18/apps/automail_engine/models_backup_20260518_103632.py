"""
automail_engine models - E-Mail Automation mit Corporate Design
ERWEITERT für ABpE Email & Task System
MIT ABSENDER-AUSWAHL, CC/BCC und HTML PREVIEW Support
"""
from django.db import models
import uuid

class BaseModel(models.Model):
    """Basis-Model für alle ABpE Models"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

# Konkrete Models für E-Mail Automation
class EmailTemplate(models.Model):
    """E-Mail Template mit Corporate Design"""
    TEMPLATE_TYPE_CHOICES = [
        ('MATCH_NOTIFICATION', 'Match Benachrichtigung'),
        ('CONSULTANT_WELCOME', 'Berater Willkommen'),
        ('CLIENT_UPDATE', 'Kunden Update'),
        ('SYSTEM_ALERT', 'System Alarm'),
        ('CUSTOM', 'Benutzerdefiniert'),
        # NEUE TEMPLATE TYPES für ABpE
        ('UPLOAD_RECEIVED', 'Upload Empfangsbestätigung'),
        ('CV_GENERATED', 'CV erstellt'),
        ('MATCH_FOUND', 'Match gefunden'),
        ('INTERVIEW_SCHEDULED', 'Interview terminiert'),
        ('TASK_ASSIGNED', 'Task zugewiesen'),
    ]

    DESIGN_CHOICES = [
        ('CORPORATE_BLUE', 'Abcona Corporate Blau'),
        ('NOTIFICATION', 'Benachrichtigung'),
        ('CONFIRMATION', 'Bestätigung'),
        ('ERROR', 'Fehler'),
    ]
    
    # === NEUE ABSENDER AUSWAHL ===
    SENDER_CHOICES = [
        ('task@abcona.de', 'task@abcona.de (Default)'),
        ('vertrieb@abcona.de', 'vertrieb@abcona.de'),
        ('office@abcona.de', 'office@abcona.de'),
        ('rechnung@abcona.de', 'rechnung@abcona.de'),
        ('cv_scan@abcona.de', 'cv_scan@abcona.de (System)'),
    ]

    # Identifikation
    identifier = models.CharField(max_length=200, unique=True, verbose_name="Technischer Name",
                                  help_text="Technischer Name für API (z.B. 'upload_received')")
    name = models.CharField(max_length=200, verbose_name="Anzeigename")
    template_type = models.CharField(max_length=30, choices=TEMPLATE_TYPE_CHOICES, verbose_name="Template Typ")

    # App/Event Zuordnung
    app_scope = models.CharField(max_length=100, default='general', verbose_name="App Bereich",
                                 help_text="Welche App nutzt dieses Template (intake, matching, etc.)")
    event_type = models.CharField(max_length=100, default='general', verbose_name="Event Typ",
                                  help_text="Welches Event löst dieses Template aus")

    # === NEUE FELDER: ABSENDER & CC/BCC ===
    sender_email = models.CharField(
        max_length=255,
        choices=SENDER_CHOICES,
        default='task@abcona.de',
        verbose_name="Absender E-Mail",
        help_text="Absenderadresse für dieses Template"
    )
    
    cc_emails = models.TextField(
        blank=True,
        verbose_name="CC Empfänger",
        help_text="Komma-getrennte CC-Empfänger (werden bei jeder Sendung hinzugefügt)"
    )
    
    bcc_emails = models.TextField(
        blank=True,
        verbose_name="BCC Empfänger", 
        help_text="Komma-getrennte BCC-Empfänger (werden bei jeder Sendung hinzugefügt)"
    )

    # Design & Content
    design_template = models.CharField(max_length=30, choices=DESIGN_CHOICES, default='CORPORATE_BLUE',
                                       verbose_name="Design Template")
    subject = models.CharField(max_length=500, verbose_name="Betreff")
    body_html = models.TextField(verbose_name="HTML Body")
    body_text = models.TextField(blank=True, verbose_name="Text Body")

    # Variables
    variables = models.JSONField(default=list, verbose_name="Variablen",
                                 help_text="Liste der verfügbaren Variablen: [{'name': 'filename', 'type': 'string'}]")
    default_values = models.JSONField(default=dict, blank=True, verbose_name="Standardwerte")

    # Attachments Configuration
    attachments_config = models.JSONField(default=list, blank=True, verbose_name="Anhänge Konfiguration",
                                          help_text="Konfiguration für automatische Anhänge")

    # Signatur
    include_signature = models.BooleanField(default=True, verbose_name="Signatur einfügen")
    signature_template = models.CharField(max_length=100, default='standard', verbose_name="Signatur Template")

    # Status & Tracking
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    usage_count = models.IntegerField(default=0, verbose_name="Verwendungszähler")
    last_used = models.DateTimeField(null=True, blank=True, verbose_name="Zuletzt verwendet")

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name="Erstellt von")

    def __str__(self):
        return f"{self.name} ({self.identifier})"
    
    def get_sender_email(self):
        """Gibt die konfigurierte Absender-Email zurück"""
        return self.sender_email
    
    def get_cc_list(self):
        """Gibt CC als Liste zurück"""
        if not self.cc_emails:
            return []
        return [email.strip() for email in self.cc_emails.split(',') if email.strip()]
    
    def get_bcc_list(self):
        """Gibt BCC als Liste zurück"""
        if not self.bcc_emails:
            return []
        return [email.strip() for email in self.bcc_emails.split(',') if email.strip()]

    class Meta:
        verbose_name = "E-Mail Template"
        verbose_name_plural = "E-Mail Templates"
        ordering = ['app_scope', 'event_type']
        indexes = [
            models.Index(fields=['identifier']),
            models.Index(fields=['app_scope', 'event_type']),
            models.Index(fields=['is_active']),
            models.Index(fields=['sender_email']),  # NEU: Index für Absender
        ]


class TemplateAttachment(models.Model):
    """Statische Anhänge für Templates"""
    template = models.ForeignKey(EmailTemplate, on_delete=models.CASCADE, related_name='template_attachments')

    ATTACHMENT_TYPE_CHOICES = [
        ('STATIC', 'Statisch'),
        ('DYNAMIC', 'Dynamisch'),
    ]

    attachment_type = models.CharField(max_length=20, choices=ATTACHMENT_TYPE_CHOICES, default='STATIC')
    identifier = models.CharField(max_length=200, verbose_name="Technischer Name")
    display_name = models.CharField(max_length=200, verbose_name="Anzeigename")

    # File Info
    filename = models.CharField(max_length=500, verbose_name="Dateiname")
    file_path = models.CharField(max_length=1000, verbose_name="Dateipfad")
    content_type = models.CharField(max_length=200, default='application/pdf', verbose_name="Content-Type")

    # Conditions
    conditions = models.JSONField(default=list, blank=True, verbose_name="Bedingungen",
                                  help_text="JSON Liste von Bedingungen wann angehängt wird")

    # Status
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.display_name} ({self.filename})"

    class Meta:
        verbose_name = "Template Anhang"
        verbose_name_plural = "Template Anhänge"
        unique_together = ['template', 'identifier']


class EmailLog(models.Model):
    """Log für gesendete Emails - ERWEITERT für ABpE"""
    DIRECTION_CHOICES = [
        ('SENT', 'Gesendet'),
        ('RECEIVED', 'Empfangen'),
    ]

    # Identifikation
    log_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email_id = models.CharField(max_length=500, blank=True, verbose_name="Message-ID")

    # Direction & Person
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, verbose_name="Richtung")
    person = models.ForeignKey('abpe_profile.Profile', on_delete=models.SET_NULL, null=True, blank=True,
                               verbose_name="Person", related_name='email_logs')

    # Content
    subject = models.CharField(max_length=1000, verbose_name="Betreff")
    body_preview = models.TextField(blank=True, verbose_name="Body Vorschau")
    body_html = models.TextField(blank=True, verbose_name="HTML Body")
    body_text = models.TextField(blank=True, verbose_name="Text Body")

    # Participants
    from_email = models.EmailField(verbose_name="Absender")
    from_name = models.CharField(max_length=200, blank=True, verbose_name="Absender Name")
    to_emails = models.JSONField(default=list, verbose_name="Empfänger")
    cc_emails = models.JSONField(default=list, blank=True, verbose_name="CC")
    bcc_emails = models.JSONField(default=list, blank=True, verbose_name="BCC")

    # Template Info
    template_used = models.ForeignKey(EmailTemplate, on_delete=models.SET_NULL, null=True, blank=True,
                                      verbose_name="Verwendetes Template")
    template_variables = models.JSONField(default=dict, blank=True, verbose_name="Template Variablen")

    # Attachments
    attachments_count = models.IntegerField(default=0, verbose_name="Anzahl Anhänge")
    attachments_info = models.JSONField(default=list, blank=True, verbose_name="Anhang Informationen")

    # Task Reference
    task_reference = models.CharField(max_length=100, blank=True, verbose_name="Task Referenz",
                                      help_text="z.B. 'TASK-2025-00123'")

    # Timestamps
    sent_received_at = models.DateTimeField(verbose_name="Gesendet/Empfangen am")
    created_at = models.DateTimeField(auto_now_add=True)

    # Search Optimization
    indexed_at = models.DateTimeField(null=True, blank=True, verbose_name="Indexiert am")

    def __str__(self):
        return f"{self.direction}: {self.subject[:50]}..."

    class Meta:
        verbose_name = "Email Log"
        verbose_name_plural = "Email Logs"
        ordering = ['-sent_received_at']
        indexes = [
            models.Index(fields=['person', 'sent_received_at']),
            models.Index(fields=['from_email', 'sent_received_at']),
            models.Index(fields=['direction', 'sent_received_at']),
            models.Index(fields=['task_reference']),
        ]
