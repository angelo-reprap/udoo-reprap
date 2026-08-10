"""
ingest_email models - E-Mail Import Engine
"""
from django.db import models

class BaseModel(models.Model):
    """Basis-Model für alle ABpE Models"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

# Konkrete Models für E-Mail Import
class EmailImportConfig(models.Model):
    """E-Mail Import Konfiguration"""
    PROTOCOL_CHOICES = [
        ('IMAP', 'IMAP'),
        ('POP3', 'POP3'),
    ]
    
    name = models.CharField(max_length=200, verbose_name="Name")
    
    # Email Server Settings
    email_address = models.EmailField(verbose_name="E-Mail Adresse")
    protocol = models.CharField(max_length=10, choices=PROTOCOL_CHOICES, default='IMAP', verbose_name="Protokoll")
    imap_server = models.CharField(max_length=200, verbose_name="IMAP Server")
    imap_port = models.IntegerField(default=993, verbose_name="IMAP Port")
    smtp_server = models.CharField(max_length=200, blank=True, verbose_name="SMTP Server")
    smtp_port = models.IntegerField(default=587, verbose_name="SMTP Port")
    
    # Authentication
    username = models.CharField(max_length=200, verbose_name="Benutzername")
    password = models.CharField(max_length=500, verbose_name="Passwort")
    use_ssl = models.BooleanField(default=True, verbose_name="SSL verwenden")
    
    # Import Settings
    mailbox = models.CharField(max_length=100, default="INBOX", verbose_name="Mailbox")
    check_frequency = models.IntegerField(default=15, verbose_name="Prüf-Frequenz (Minuten)")
    delete_after_import = models.BooleanField(default=False, verbose_name="Nach Import löschen")
    
    # Processing Rules
    process_attachments = models.BooleanField(default=True, verbose_name="Anhänge verarbeiten")
    attachment_types = models.JSONField(default=list, verbose_name="Anhang-Typen")
    keywords = models.JSONField(default=list, verbose_name="Such-Keywords")
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    last_check = models.DateTimeField(null=True, blank=True, verbose_name="Letzte Prüfung")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")
    
    def __str__(self):
        return f"{self.name} ({self.email_address})"
    
    class Meta:
        verbose_name = "E-Mail Import Konfiguration"
        verbose_name_plural = "E-Mail Import Konfigurationen"

# ==================== EMAIL MESSAGE MODEL ====================

class EmailMessage(BaseModel):
    """
    Gespeicherte E-Mail Nachricht
    """
    STATUS_CHOICES = [
        ('NEW', 'Neu'),
        ('PROCESSING', 'In Verarbeitung'),
        ('PROCESSED', 'Verarbeitet'),
        ('ERROR', 'Fehler'),
        ('ARCHIVED', 'Archiviert'),
    ]
    
    # Email Header
    message_id = models.CharField(max_length=500, unique=True, verbose_name="Message-ID")
    subject = models.CharField(max_length=1000, blank=True, verbose_name="Betreff")
    from_email = models.EmailField(verbose_name="Absender")
    to_email = models.EmailField(verbose_name="Empfänger")
    cc = models.TextField(blank=True, verbose_name="CC")
    bcc = models.TextField(blank=True, verbose_name="BCC")
    
    # Content
    body_plain = models.TextField(blank=True, verbose_name="Text-Inhalt")
    body_html = models.TextField(blank=True, verbose_name="HTML-Inhalt")
    
    # Metadata
    received_date = models.DateTimeField(verbose_name="Empfangsdatum")
    sent_date = models.DateTimeField(null=True, blank=True, verbose_name="Sendedatum")
    size = models.IntegerField(default=0, verbose_name="Größe (Bytes)")
    
    # Attachments Info
    has_attachments = models.BooleanField(default=False, verbose_name="Hat Anhänge")
    attachment_count = models.IntegerField(default=0, verbose_name="Anzahl Anhänge")
    attachment_info = models.JSONField(default=list, verbose_name="Anhang-Informationen")
    
    # Processing
    config = models.ForeignKey(
        EmailImportConfig, 
        on_delete=models.SET_NULL, 
        null=True, 
        verbose_name="Import Konfiguration"
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='NEW',
        verbose_name="Status"
    )
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name="Verarbeitet am")
    error_message = models.TextField(blank=True, verbose_name="Fehlermeldung")
    
    # Raw Data (für Debugging/Backup)
    raw_headers = models.TextField(blank=True, verbose_name="Raw Headers")
    raw_body = models.TextField(blank=True, verbose_name="Raw Body")
    
    # Tags für Kategorisierung
    tags = models.JSONField(default=list, verbose_name="Tags")
    
    # Relations (später für ABpE Integration)
    intake_rawinput_id = models.UUIDField(null=True, blank=True, verbose_name="Intake RawInput ID")
    
    def __str__(self):
        return f"{self.subject[:50]}... ({self.from_email} → {self.to_email})"
    
    class Meta:
        verbose_name = "E-Mail Nachricht"
        verbose_name_plural = "E-Mail Nachrichten"
        indexes = [
            models.Index(fields=['message_id']),
            models.Index(fields=['from_email']),
            models.Index(fields=['received_date']),
            models.Index(fields=['status']),
            models.Index(fields=['intake_rawinput_id']),
        ]
        ordering = ['-received_date']


class EmailAttachment(BaseModel):
    """
    E-Mail Anhang
    """
    email = models.ForeignKey(
        EmailMessage, 
        on_delete=models.CASCADE, 
        related_name='attachments',
        verbose_name="E-Mail"
    )
    
    filename = models.CharField(max_length=500, verbose_name="Dateiname")
    content_type = models.CharField(max_length=200, verbose_name="Content-Type")
    size = models.IntegerField(verbose_name="Größe (Bytes)")
    
    # Storage
    file_path = models.CharField(max_length=1000, blank=True, verbose_name="Dateipfad")
    storage_backend = models.CharField(max_length=100, default='local', verbose_name="Storage Backend")
    
    # Content
    content_text = models.TextField(blank=True, verbose_name="Extrahiertes Text")
    is_processed = models.BooleanField(default=False, verbose_name="Verarbeitet")
    processing_error = models.TextField(blank=True, verbose_name="Verarbeitungsfehler")
    
    # Metadata
    metadata = models.JSONField(default=dict, verbose_name="Metadaten")
    
    def __str__(self):
        return self.filename
    
    class Meta:
        verbose_name = "E-Mail Anhang"
        verbose_name_plural = "E-Mail Anhänge"
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['content_type']),
        ]

