"""
ABpE KI Wizard — Models
========================
WizardPrompt  : zentrale KI-Prompts pro Wizard + Phase
WizardSession : Laufende Wizard-Instanz (Phase 1+ API)
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class WizardPhase(models.TextChoices):
    ANALYZE      = 'analyze',       'Briefing analysieren'
    CLARIFY      = 'clarify',       'Klärfragen'
    SUGGEST_META = 'suggest_meta',  'Metadaten vorschlagen'
    GENERATE     = 'generate',      'Inhalt generieren'
    REFINE       = 'refine',        'Nachbearbeitung'
    GENERAL      = 'general',       'Allgemein / Shared'


class WizardPrompt(models.Model):
    """
    Zentraler Prompt-Katalog für alle KI-Wizards.
    DeepSeek-Platzhalter: [[INSTRUCTION]] [[TEXT]] [[NOTES]] [[CONTEXT]] [[KOPF]]
    """
    key = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name='Prompt-Key',
        help_text='Eindeutig, z. B. wiz_email_analyze',
    )
    wizard_id = models.CharField(
        max_length=64,
        db_index=True,
        default='general',
        verbose_name='Wizard-ID',
        help_text='z. B. email_template, matching_berater, doc_letter',
    )
    phase = models.CharField(
        max_length=32,
        choices=WizardPhase.choices,
        default=WizardPhase.GENERAL,
        verbose_name='Phase',
    )
    name = models.CharField(max_length=128, verbose_name='Anzeigename')
    description = models.TextField(blank=True, verbose_name='Beschreibung')
    app_scope = models.CharField(
        max_length=32,
        default='general',
        verbose_name='App-Bereich',
        help_text='general, telefon, matching, crm, doc, …',
    )
    system = models.TextField(
        verbose_name='System-Prompt',
        help_text='System-Prompt für DeepSeek',
    )
    user_template = models.TextField(
        verbose_name='User-Template',
        help_text='User-Template mit [[CONTEXT]], [[INSTRUCTION]], …',
    )
    instruction_default = models.TextField(
        blank=True,
        verbose_name='Standard-Instruction',
        help_text='Fallback wenn API keine Instruction übergibt',
    )
    checklist_template = models.TextField(
        blank=True,
        verbose_name='Checklist-Vorlage',
        help_text='Optional: Regeln für prompt_builder (eine Zeile pro Punkt)',
    )
    aktiv = models.BooleanField(default=True, verbose_name='Aktiv')
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wizard_prompts_updated',
        verbose_name='Zuletzt geändert von',
    )

    class Meta:
        db_table = 'abpe_ki_wiz_prompt'
        verbose_name = 'KI-Wizard-Prompt'
        verbose_name_plural = 'KI-Wizard-Prompts'
        ordering = ['wizard_id', 'phase', 'name']
        indexes = [
            models.Index(fields=['wizard_id', 'phase']),
        ]

    def __str__(self):
        return f'{self.key} ({self.wizard_id}/{self.phase})'


class WizardSessionStatus(models.TextChoices):
    OPEN      = 'open',      'Offen'
    COMPLETED = 'completed', 'Abgeschlossen'
    CANCELLED = 'cancelled', 'Abgebrochen'
    FAILED    = 'failed',    'Fehlgeschlagen'


class WizardSession(models.Model):
    """
    Eine laufende oder abgeschlossene Wizard-Instanz.
    Phase 0: Model + Admin (readonly). Phase 1: API befüllt dieses Model.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wizard_id = models.CharField(max_length=64, db_index=True, verbose_name='Wizard-ID')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wizard_sessions',
        verbose_name='Benutzer',
    )
    status = models.CharField(
        max_length=20,
        choices=WizardSessionStatus.choices,
        default=WizardSessionStatus.OPEN,
        verbose_name='Status',
    )
    phase = models.CharField(
        max_length=32,
        choices=WizardPhase.choices,
        default=WizardPhase.ANALYZE,
        verbose_name='Aktuelle Phase',
    )
    briefing = models.TextField(blank=True, verbose_name='Briefing (Freitext)')
    answers = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Klär-Antworten',
        help_text='question_id → Antwort',
    )
    meta_suggestions = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Metadaten-Vorschläge',
    )
    result = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Generiertes Ergebnis',
    )
    error_message = models.TextField(blank=True, verbose_name='Fehler')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Abgeschlossen am')

    class Meta:
        db_table = 'abpe_ki_wiz_session'
        verbose_name = 'KI-Wizard-Session'
        verbose_name_plural = 'KI-Wizard-Sessions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wizard_id', 'status']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f'{self.wizard_id} · {self.id} · {self.status}'

    def mark_completed(self):
        self.status = WizardSessionStatus.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])

    def mark_failed(self, message: str = ''):
        self.status = WizardSessionStatus.FAILED
        self.error_message = message or self.error_message
        self.save(update_fields=['status', 'error_message', 'updated_at'])
