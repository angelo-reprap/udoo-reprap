"""
ABpE Email Studio — Models
==========================
EmailTemplate      : Vorlage mit HTML + TXT Body, Variablen, Absender-Modus
EmailTemplateVersion: Versionierung jeder Vorlage
EmailSignature     : Signaturen pro Absender-Adresse
EmailSenderAccount : Bekannte Absender-Adressen (Template/User/Auto)
EmailLog           : Protokoll aller gesendeten E-Mails
EmailQueue         : Celery-Warteschlange für async Versand
"""
import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


# ── Konstanten ────────────────────────────────────────────────────────────────

class SenderMode(models.TextChoices):
    USER     = 'USER',     'User (From = eingeloggter User)'
    TEMPLATE = 'TEMPLATE', 'Template (feste Adresse)'
    AUTO     = 'AUTO',     'Auto (maschinell / noreply)'


class TemplateStatus(models.TextChoices):
    ACTIVE  = 'ACTIVE',  'Aktiv'
    DRAFT   = 'DRAFT',   'Entwurf'
    ARCHIVE = 'ARCHIVE', 'Archiv'


class AppScope(models.TextChoices):
    INTAKE    = 'intake',    'Intake / CV Upload'
    MATCHING  = 'matching',  'Matching'
    WORKFLOW  = 'workflow',  'Workflow'
    TELEFON   = 'telefon',   'Telefon / PBX'
    PORTAL    = 'portal',    'Portal / System'
    GENERAL   = 'general',   'Allgemein'
    SYSTEM    = 'system',    'System / Auto'


class LogStatus(models.TextChoices):
    OK      = 'OK',      'Erfolgreich'
    FAILED  = 'FAILED',  'Fehlgeschlagen'
    QUEUED  = 'QUEUED',  'In Warteschlange'
    SENDING = 'SENDING', 'Wird gesendet'


class QueueStatus(models.TextChoices):
    PENDING   = 'PENDING',   'Ausstehend'
    RUNNING   = 'RUNNING',   'Läuft'
    DONE      = 'DONE',      'Erledigt'
    FAILED    = 'FAILED',    'Fehlgeschlagen'
    CANCELLED = 'CANCELLED', 'Abgebrochen'


class SignatureMode(models.TextChoices):
    NONE    = 'NONE',    'Keine Signatur'
    TEAM    = 'TEAM',    'Allgemein — abcona Team'
    USER    = 'USER',    'User des Absenders'
    FIXED   = 'FIXED',   'Feste Signatur wählen'
    DYNAMIC = 'DYNAMIC', 'Beim Versand wählbar'


# ── EmailSenderAccount ────────────────────────────────────────────────────────

class EmailSenderAccount(models.Model):
    """
    Bekannte Absender-Adressen des Systems.
    SMTP Auth läuft immer über den konfigurierten SMTP-User (task@abcona.de).
    From/Reply-To werden per Header gesetzt.
    """
    email        = models.EmailField(unique=True, verbose_name='E-Mail Adresse')
    display_name = models.CharField(max_length=200, verbose_name='Anzeigename',
                                    help_text='z.B. "abcona e. K. Vertrieb"')
    sender_mode  = models.CharField(max_length=20, choices=SenderMode.choices,
                                    default=SenderMode.TEMPLATE,
                                    verbose_name='Absender-Modus')
    is_default   = models.BooleanField(default=False,
                                       verbose_name='Standard-Absender')
    is_active    = models.BooleanField(default=True, verbose_name='Aktiv')
    description  = models.TextField(blank=True, verbose_name='Beschreibung')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.display_name} <{self.email}>'

    def save(self, *args, **kwargs):
        if self.is_default:
            EmailSenderAccount.objects.exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name        = 'Absender-Konto'
        verbose_name_plural = 'Absender-Konten'
        ordering            = ['-is_default', 'email']


# ── EmailSignature ────────────────────────────────────────────────────────────

class EmailSignature(models.Model):
    """
    Signatur-Vorlagen.
    Können einem Absender-Konto oder einem User zugeordnet werden.
    Priorität: User-Signatur > Konto-Signatur > System-Default
    """
    name         = models.CharField(max_length=200, verbose_name='Name')
    identifier   = models.SlugField(max_length=100, unique=True,
                                    verbose_name='Technischer Name')
    html_body    = models.TextField(verbose_name='HTML Signatur',
                                    help_text='HTML-Signatur mit {variablen}')
    text_body    = models.TextField(blank=True, verbose_name='Text Signatur',
                                    help_text='Plaintext Fallback')
    sender_account = models.ForeignKey(
        EmailSenderAccount, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='signatures',
        verbose_name='Zugeordnetes Absender-Konto'
    )
    is_default   = models.BooleanField(default=False,
                                       verbose_name='Standard-Signatur')
    is_public    = models.BooleanField(default=False,
                                       verbose_name='Öffentliche Signatur',
                                       help_text='Sichtbar für alle User')
    created_by   = models.ForeignKey(User, on_delete=models.SET_NULL,
                                     null=True, blank=True,
                                     verbose_name='Erstellt von')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name        = 'Signatur'
        verbose_name_plural = 'Signaturen'
        ordering            = ['-is_default', 'name']



# ── EmailTemplate ─────────────────────────────────────────────────────────────

class EmailTemplate(models.Model):
    """
    Haupt-Model für E-Mail Vorlagen.
    Jede Vorlage hat einen technischen Identifier (für API-Aufrufe),
    einen Absender-Modus und vollständigen HTML + TXT Body.
    """
    identifier   = models.SlugField(max_length=200, unique=True,
                                    verbose_name='Technischer Name',
                                    help_text='Für API: EmailStudio.send(template="cv_generated_berater")')
    name         = models.CharField(max_length=200, verbose_name='Anzeigename')
    description  = models.TextField(blank=True, verbose_name='Beschreibung')

    # Kategorisierung
    app_scope    = models.CharField(max_length=50, choices=AppScope.choices,
                                    default=AppScope.GENERAL,
                                    verbose_name='App-Bereich')
    event_type   = models.CharField(max_length=100, default='general',
                                    verbose_name='Event-Typ',
                                    help_text='z.B. cv_generated, match_found')

    # Absender
    sender_mode  = models.CharField(max_length=20, choices=SenderMode.choices,
                                    default=SenderMode.TEMPLATE,
                                    verbose_name='Absender-Modus')
    sender_account = models.ForeignKey(
        EmailSenderAccount, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='templates',
        verbose_name='Absender-Konto',
        help_text='Nur relevant bei Modus TEMPLATE'
    )
    signature    = models.ForeignKey(
        EmailSignature, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='templates',
        verbose_name='Signatur'
    )

    # CC / BCC (immer hinzugefügt)
    cc_emails    = models.TextField(blank=True, verbose_name='CC',
                                    help_text='Komma-getrennt')
    bcc_emails   = models.TextField(blank=True, verbose_name='BCC',
                                    help_text='Komma-getrennt')

    # Inhalt
    subject      = models.CharField(max_length=500, verbose_name='Betreff',
                                    help_text='Kann {variablen} enthalten')
    html_body    = models.TextField(verbose_name='HTML Body')
    text_body    = models.TextField(blank=True, verbose_name='Text Fallback',
                                    help_text='Plaintext für Mail-Clients ohne HTML')

    # Variablen-Definiton
    variables    = models.JSONField(default=list, blank=True,
                                    verbose_name='Variablen',
                                    help_text='[{"name": "name", "type": "string", "source": "context", "required": true}]')

    # Sprach-Konfiguration
    translation_languages = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Übersetzungssprachen',
        help_text='z.B. ["en", "fr"] — DE ist immer Referenz'
    )

    # Status & Versionierung
    status       = models.CharField(max_length=20, choices=TemplateStatus.choices,
                                    default=TemplateStatus.DRAFT,
                                    verbose_name='Status')
    active_version = models.PositiveIntegerField(default=1,
                                                  verbose_name='Aktive Version')
    include_signature = models.BooleanField(default=True,
                                             verbose_name='Signatur anhängen')
    signature_mode = models.CharField(
        max_length=20,
        choices=SignatureMode.choices,
        default=SignatureMode.USER,
        verbose_name='Signatur-Modus',
        help_text='Steuert welche Signatur beim Versand angehängt wird'
    )

    # Tracking
    usage_count  = models.PositiveIntegerField(default=0,
                                               verbose_name='Verwendungen')
    last_used_at = models.DateTimeField(null=True, blank=True,
                                        verbose_name='Zuletzt verwendet')

    # Meta
    created_by   = models.ForeignKey(User, on_delete=models.SET_NULL,
                                     null=True, blank=True,
                                     related_name='created_templates',
                                     verbose_name='Erstellt von')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name} [{self.identifier}]'

    def get_cc_list(self):
        if not self.cc_emails:
            return []
        return [e.strip() for e in self.cc_emails.split(',') if e.strip()]

    def get_bcc_list(self):
        if not self.bcc_emails:
            return []
        return [e.strip() for e in self.bcc_emails.split(',') if e.strip()]

    def get_variables_dict(self):
        return {v['name']: v for v in self.variables if isinstance(v, dict)}

    class Meta:
        verbose_name        = 'E-Mail Vorlage'
        verbose_name_plural = 'E-Mail Vorlagen'
        ordering            = ['app_scope', 'name']
        indexes             = [
            models.Index(fields=['identifier']),
            models.Index(fields=['app_scope', 'event_type']),
            models.Index(fields=['status']),
        ]


# ── EmailTemplateVersion ──────────────────────────────────────────────────────

class EmailTemplateVersion(models.Model):
    """
    Versionsverlauf einer Vorlage.
    Beim Speichern wird automatisch eine neue Version angelegt.
    """
    template     = models.ForeignKey(EmailTemplate, on_delete=models.CASCADE,
                                     related_name='versions',
                                     verbose_name='Vorlage')
    version      = models.PositiveIntegerField(verbose_name='Version')
    subject      = models.CharField(max_length=500)
    html_body    = models.TextField()
    text_body    = models.TextField(blank=True)
    variables    = models.JSONField(default=list)
    sender_mode  = models.CharField(max_length=20, choices=SenderMode.choices,
                                    default=SenderMode.TEMPLATE)
    change_note  = models.CharField(max_length=500, blank=True,
                                    verbose_name='Änderungsnotiz')
    is_milestone = models.BooleanField(
        default=False,
        verbose_name='Meilenstein',
        help_text='Vom User manuell gesetzter Merke-Stand'
    )
    milestone_label = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Meilenstein-Bezeichnung',
        help_text='z.B. "vor Farb-Test"'
    )
    created_by   = models.ForeignKey(User, on_delete=models.SET_NULL,
                                     null=True, blank=True,
                                     verbose_name='Gespeichert von')
    created_at   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.template.identifier} v{self.version}'

    class Meta:
        verbose_name        = 'Template Version'
        verbose_name_plural = 'Template Versionen'
        ordering            = ['-version']
        unique_together     = ['template', 'version']



# ── EmailLog ──────────────────────────────────────────────────────────────────

class EmailLog(models.Model):
    """
    Vollständiges Protokoll aller gesendeten E-Mails.
    Wird automatisch von sender.py befüllt.
    """
    log_id       = models.UUIDField(primary_key=True, default=uuid.uuid4,
                                    editable=False)
    template     = models.ForeignKey(EmailTemplate, on_delete=models.SET_NULL,
                                     null=True, blank=True,
                                     related_name='logs',
                                     verbose_name='Vorlage')
    template_version = models.PositiveIntegerField(null=True, blank=True,
                                                    verbose_name='Template Version')

    # Absender
    from_email   = models.EmailField(verbose_name='Von')
    from_name    = models.CharField(max_length=200, blank=True,
                                    verbose_name='Von Name')
    sender_mode  = models.CharField(max_length=20, choices=SenderMode.choices,
                                    default=SenderMode.TEMPLATE,
                                    verbose_name='Absender-Modus')
    sent_by_user = models.ForeignKey(User, on_delete=models.SET_NULL,
                                     null=True, blank=True,
                                     related_name='sent_emails',
                                     verbose_name='Gesendet von User')

    # Empfänger
    to_emails    = models.JSONField(default=list, verbose_name='An')
    cc_emails    = models.JSONField(default=list, verbose_name='CC')
    bcc_emails   = models.JSONField(default=list, verbose_name='BCC')
    reply_to     = models.EmailField(blank=True, verbose_name='Reply-To')

    # Inhalt
    subject      = models.CharField(max_length=500, verbose_name='Betreff')
    html_body    = models.TextField(blank=True, verbose_name='HTML Body')
    text_body    = models.TextField(blank=True, verbose_name='Text Body')

    # Variablen die verwendet wurden
    variables_used = models.JSONField(default=dict, blank=True,
                                       verbose_name='Verwendete Variablen')

    # Status
    status       = models.CharField(max_length=20, choices=LogStatus.choices,
                                    default=LogStatus.OK, verbose_name='Status')
    error_message = models.TextField(blank=True, verbose_name='Fehlermeldung')

    # Referenz für andere Apps
    task_reference = models.CharField(max_length=200, blank=True,
                                       verbose_name='Task Referenz',
                                       help_text='z.B. TASK-2026-00123 oder AID-12345')
    app_reference  = models.CharField(max_length=100, blank=True,
                                       verbose_name='App Referenz',
                                       help_text='Welche App hat gesendet')

    # Zeitstempel
    sent_at      = models.DateTimeField(auto_now_add=True,
                                        verbose_name='Gesendet am')

    def __str__(self):
        return f'{self.subject[:60]} → {self.to_emails}'

    @property
    def to_emails_display(self):
        if isinstance(self.to_emails, list):
            return ', '.join(self.to_emails)
        return str(self.to_emails)

    class Meta:
        verbose_name        = 'E-Mail Log'
        verbose_name_plural = 'E-Mail Logs'
        ordering            = ['-sent_at']
        indexes             = [
            models.Index(fields=['status', 'sent_at']),
            models.Index(fields=['from_email', 'sent_at']),
            models.Index(fields=['task_reference']),
            models.Index(fields=['app_reference']),
            models.Index(fields=['sent_by_user', 'sent_at']),
        ]


# ── EmailQueue ────────────────────────────────────────────────────────────────

class EmailQueue(models.Model):
    """
    Celery-Warteschlange für asynchronen E-Mail Versand.
    Wird von tasks.py verarbeitet.
    """
    queue_id     = models.UUIDField(primary_key=True, default=uuid.uuid4,
                                    editable=False)
    template     = models.ForeignKey(EmailTemplate, on_delete=models.CASCADE,
                                     related_name='queue_items',
                                     verbose_name='Vorlage')
    to_emails    = models.JSONField(default=list, verbose_name='Empfänger')
    cc_emails    = models.JSONField(default=list, verbose_name='CC')
    bcc_emails   = models.JSONField(default=list, verbose_name='BCC')
    variables    = models.JSONField(default=dict, verbose_name='Variablen')
    sender_mode  = models.CharField(max_length=20, choices=SenderMode.choices,
                                    default=SenderMode.TEMPLATE)
    user_id      = models.IntegerField(null=True, blank=True,
                                       verbose_name='User ID (für User-Modus)')
    task_reference = models.CharField(max_length=200, blank=True)
    app_reference  = models.CharField(max_length=100, blank=True)
    status       = models.CharField(max_length=20, choices=QueueStatus.choices,
                                    default=QueueStatus.PENDING,
                                    verbose_name='Status')
    celery_task_id = models.CharField(max_length=200, blank=True,
                                       verbose_name='Celery Task ID')
    retry_count  = models.PositiveSmallIntegerField(default=0,
                                                     verbose_name='Versuche')
    max_retries  = models.PositiveSmallIntegerField(default=3,
                                                     verbose_name='Max Versuche')
    error_message = models.TextField(blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True,
                                         verbose_name='Geplant für')
    created_at   = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True,
                                         verbose_name='Verarbeitet am')

    def __str__(self):
        return f'Queue {self.queue_id} → {self.template.identifier} [{self.status}]'

    class Meta:
        verbose_name        = 'E-Mail Warteschlange'
        verbose_name_plural = 'E-Mail Warteschlange'
        ordering            = ['created_at']
        indexes             = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['celery_task_id']),
        ]


# ── EmailTemplateTranslation ──────────────────────────────────────────────────

class EmailTemplateTranslation(models.Model):
    """
    Übersetzungen eines E-Mail Templates.
    Ref-Sprache ist immer DE (im Template selbst).
    Übersetzungen werden via Deepseek API erstellt.
    """
    template   = models.ForeignKey(EmailTemplate, on_delete=models.CASCADE,
                                   related_name='translations',
                                   verbose_name='Vorlage')
    lang       = models.CharField(max_length=10, verbose_name='Sprache',
                                  help_text='ISO-Code z.B. en, fr, it')
    subject    = models.CharField(max_length=500, verbose_name='Betreff')
    html_body  = models.TextField(verbose_name='HTML Body')
    text_body  = models.TextField(blank=True, verbose_name='Text Body')
    auto_translated = models.BooleanField(default=True,
                                          verbose_name='Auto-übersetzt')
    translated_at   = models.DateTimeField(auto_now=True,
                                            verbose_name='Übersetzt am')
    reviewed        = models.BooleanField(default=False,
                                          verbose_name='Geprüft')

    def __str__(self):
        return f'{self.template.identifier} [{self.lang}]'

    class Meta:
        verbose_name        = 'Template Übersetzung'
        verbose_name_plural = 'Template Übersetzungen'
        unique_together     = ['template', 'lang']
        ordering            = ['lang']


# ── EmailModule ───────────────────────────────────────────────────────────────

class ModuleType(models.TextChoices):
    HEADER     = 'HEADER',     'Header'
    FOOTER     = 'FOOTER',     'Footer'
    SIGNATURE  = 'SIGNATURE',  'Signatur'
    BUTTON     = 'BUTTON',     'Button / CTA'
    SECTION    = 'SECTION',    'Inhaltsbereich'
    DISCLAIMER = 'DISCLAIMER', 'Disclaimer'


class EmailModule(models.Model):
    """
    Wiederverwendbare HTML-Blöcke für E-Mail Templates.
    Einbindung im Template: {{block:identifier}}
    """
    identifier   = models.SlugField(max_length=100, unique=True,
                                    verbose_name='Technischer Name')
    name         = models.CharField(max_length=200, verbose_name='Anzeigename')
    module_type  = models.CharField(max_length=20, choices=ModuleType.choices,
                                    default=ModuleType.SECTION,
                                    verbose_name='Typ')
    description  = models.TextField(blank=True, verbose_name='Beschreibung')
    html_body    = models.TextField(verbose_name='HTML Block',
                                    help_text='Kann {variablen} enthalten')
    text_body    = models.TextField(blank=True, verbose_name='Text Block',
                                    help_text='Plaintext Fallback')
    preview_bg   = models.CharField(max_length=20, default='#ffffff',
                                    verbose_name='Vorschau Hintergrund')
    is_active    = models.BooleanField(default=True, verbose_name='Aktiv')
    created_by   = models.ForeignKey(User, on_delete=models.SET_NULL,
                                     null=True, blank=True,
                                     verbose_name='Erstellt von')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name} [{self.identifier}]'

    class Meta:
        verbose_name        = 'E-Mail Modul'
        verbose_name_plural = 'E-Mail Module'
        ordering            = ['module_type', 'name']
