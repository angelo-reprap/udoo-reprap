"""
ABpE Matching Workflow — Models v2
Consultant-Model ENTFERNT → FK auf cv_extractor.Consultant
Neue Modelle: FollowupRule, ProjectContact, MatchResult
CRM-Felder auf ProjectRequest + ProjectConsultant
"""
from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
from datetime import date


# ============================================================
# SETTINGS LOADER
# ============================================================

def get_matching_settings():
    """Lädt matching-Block aus settings.json"""
    import json
    from pathlib import Path
    try:
        p = Path(__file__).resolve().parent.parent.parent / 'settings.json'
        cfg = json.loads(p.read_text(encoding='utf-8'))
        return cfg.get('matching', {})
    except Exception:
        return {}


# ============================================================
# 1. FOLLOWUP RULE
# ============================================================

class FollowupRule(models.Model):
    """Wiedervorlage-Regeln pro Kontakt / Projekt konfigurierbar"""

    CHANNEL_CHOICES = [
        ('phone',    'Telefon'),
        ('email',    'E-Mail'),
        ('teams',    'Microsoft Teams'),
        ('personal', 'Persönlich'),
    ]

    id   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name="Name der Regel")

    # Erreichbarkeit
    available_from  = models.TimeField(default='08:00', verbose_name="Erreichbar ab")
    available_until = models.TimeField(default='17:00', verbose_name="Erreichbar bis")

    # Kanal + Frequenz
    preferred_channel        = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='email')
    followup_delay_hours     = models.IntegerField(default=48, help_text="Stunden bis zur Wiedervorlage")
    auto_email_on_no_reach   = models.BooleanField(default=True, help_text="Auto-E-Mail wenn nicht erreicht")
    reminder_days            = models.JSONField(default=list, help_text="[1, 3, 7] — nach x Tagen erneut")

    is_default  = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Wiedervorlage-Regel"
        verbose_name_plural = "Wiedervorlage-Regeln"
        ordering            = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_preferred_channel_display()}, +{self.followup_delay_hours}h)"

    def save(self, *args, **kwargs):
        """Nur eine Regel kann Default sein"""
        if self.is_default:
            FollowupRule.objects.exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_default(cls):
        return cls.objects.filter(is_default=True).first()


# ============================================================
# 2. EMAIL TEMPLATE
# ============================================================

class EmailTemplate(models.Model):
    """E-Mail-Vorlagen für alle Anlässe"""

    TEMPLATE_TYPES = [
        ('consultant_contact',    'Berater kontaktieren'),
        ('consultant_followup',   'Berater Nachfrage'),
        ('consultant_rejection',  'Absage an Berater'),
        ('consultant_no_feedback','Berater - kein Feedback'),
        ('consultant_reminder',   'Berater Erinnerung'),
        ('consultant_unavailable','Berater nicht mehr verfügbar'),
        ('client_offer',          'Angebot an Kunde'),
        ('client_followup',       'Kunde Nachfrage'),
        ('client_rejection',      'Absage an Kunde'),
        ('client_no_feedback',    'Kunde - kein Feedback'),
        ('client_reminder',       'Kunde Erinnerung'),
        ('interview_request',     'Interview-Anfrage'),
        ('placement_info',        'Vermittlungsinfo'),
        ('placement_start',       'Projektstart-Info an Berater'),
        ('contract_preparation',  'Vertragsvorbereitung'),
        ('availability_alert',    'Berater wieder verfügbar'),
        ('project_end',           'Projektende-Info'),
        ('feedback_request',      'Feedback-Anfrage'),
    ]

    id                     = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name                   = models.CharField(max_length=100)
    template_type          = models.CharField(max_length=30, choices=TEMPLATE_TYPES)
    subject                = models.CharField(max_length=200)
    body                   = models.TextField(help_text="Platzhalter: {{projekt_titel}}, {{berater_name}}, {{anfragen_id}}")
    use_ollama             = models.BooleanField(default=True)
    ollama_prompt_template = models.TextField(blank=True)
    is_active              = models.BooleanField(default=True)
    sort_order             = models.IntegerField(default=0)
    created_at             = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "E-Mail-Vorlage"
        verbose_name_plural = "E-Mail-Vorlagen"
        ordering            = ['template_type', 'sort_order', 'name']

    def __str__(self):
        return f"{self.get_template_type_display()}: {self.name}"


# ============================================================
# 3. PROJECT REQUEST
# ============================================================

class ProjectRequest(models.Model):
    """Projektanfrage vom Kunden"""

    STATUS_CHOICES = [
        ('draft',       'Entwurf'),
        ('active',      'Aktiv'),
        ('matching',    'Beratersuche'),
        ('offers_sent', 'Angebote versendet'),
        ('interviews',  'Im Gespräch'),
        ('placed',      'Vermittelt'),
        ('not_placed',  'Nicht vermittelt'),
        ('cancelled',   'Storniert'),
        ('lost',        'Verloren'),
        ('archived',    'Archiviert'),
    ]

    PRIORITY_CHOICES = [
        (1, 'Hoch'),
        (2, 'Mittel'),
        (3, 'Niedrig'),
    ]

    CLOSE_REASON_CHOICES = [
        ('placed',            'Berater vermittelt'),
        ('no_budget',         'Kein Budget'),
        ('other_provider',    'Anderer Anbieter'),
        ('project_postponed', 'Projekt verschoben'),
        ('filled_internally', 'Intern besetzt'),
        ('no_feedback',       'Kein Feedback'),
        ('cancelled',         'Projekt storniert'),
        ('other',             'Sonstiger Grund'),
    ]

    RATE_TYPE_CHOICES = [
        ('hourly', 'Stundensatz'),
        ('daily',  'Tagessatz'),
        ('fixed',  'Festpreis'),
    ]

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project_number = models.CharField(max_length=50, unique=True, blank=True, db_index=True)

    # ── Kunde ──────────────────────────────────────────────
    customer_name           = models.CharField(max_length=200, db_index=True)
    customer_contact_person = models.CharField(max_length=200, blank=True)
    customer_email          = models.EmailField(blank=True)
    customer_phone          = models.CharField(max_length=50, blank=True)
    customer_id             = models.CharField(max_length=100, blank=True, help_text="Interne Kunden-ID")

    # ── SuiteCRM IDs ───────────────────────────────────────
    crm_account_id     = models.CharField(max_length=36, blank=True, db_index=True, help_text="SuiteCRM accounts.id")
    crm_contact_id     = models.CharField(max_length=36, blank=True, help_text="SuiteCRM contacts.id (Haupt-AP)")
    crm_opportunity_id = models.CharField(max_length=36, blank=True, db_index=True, help_text="SuiteCRM opportunities.id")
    crm_synced_at      = models.DateTimeField(null=True, blank=True, help_text="Letzter CRM-Sync")

    # ── Projektdetails ─────────────────────────────────────
    title       = models.CharField(max_length=200)
    description = models.TextField()

    # Strukturierte Daten (von Ollama extrahiert)
    required_skills        = models.JSONField(default=list, blank=True,
                                help_text='[{"name":"SAP","weight":1.0}]')
    nice_to_have_skills    = models.JSONField(default=list, blank=True,
                                help_text='[{"name":"Python","weight":0.5}]')
    extracted_technologies = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    extracted_requirements = models.JSONField(default=dict, blank=True)

    # Matching-Gewichtungen (überschreiben settings.json-Defaults)
    weight_skills_required = models.FloatField(default=0.50)
    weight_skills_nice     = models.FloatField(default=0.20)
    weight_industry        = models.FloatField(default=0.15)
    weight_experience      = models.FloatField(default=0.10)
    weight_location        = models.FloatField(default=0.05)
    shortlist_threshold    = models.FloatField(default=0.50,
                                help_text="Schwellwert für Shortlist (0.0–1.0)")

    # ── Rahmenbedingungen ──────────────────────────────────
    start_date       = models.DateField(null=True, blank=True)
    duration_months  = models.IntegerField(default=0)
    location         = models.CharField(max_length=200, blank=True)
    remote_possible  = models.BooleanField(default=True)
    workload_percent = models.IntegerField(default=100,
                        validators=[MinValueValidator(1), MaxValueValidator(100)])
    min_experience_years = models.IntegerField(default=0)
    required_languages   = models.JSONField(default=list, blank=True,
                                help_text='[{"lang":"de","min_level":"B2"}]')
    required_certs       = models.JSONField(default=list, blank=True)

    # ── Budget ─────────────────────────────────────────────
    rate_min  = models.IntegerField(null=True, blank=True, help_text="Min. Stundensatz €")
    rate_max  = models.IntegerField(null=True, blank=True, help_text="Max. Stundensatz €")
    rate_type = models.CharField(max_length=20, choices=RATE_TYPE_CHOICES, default='hourly')

    # ── Status ─────────────────────────────────────────────
    status   = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True)
    priority = models.IntegerField(default=3, choices=PRIORITY_CHOICES, db_index=True)

    # ── Eingabe-Quelle ─────────────────────────────────────
    source_text       = models.TextField(blank=True, help_text="Originaler E-Mail-Text / Freitext")
    source_email_id   = models.CharField(max_length=255, blank=True)
    source_email_date = models.DateTimeField(null=True, blank=True)
    source_document   = models.FileField(upload_to='matching/requests/%Y/%m/',
                            null=True, blank=True, help_text="PDF/TXT Upload")

    # ── Projektabschluss ───────────────────────────────────
    is_archived   = models.BooleanField(default=False, db_index=True)
    open_positions  = models.PositiveIntegerField(default=1, help_text="Anzahl gesuchter Berater")
    close_reason  = models.CharField(max_length=30, choices=CLOSE_REASON_CHOICES, blank=True)
    close_note    = models.TextField(blank=True, help_text="Interne Notiz zum Abschluss")
    closed_at     = models.DateTimeField(null=True, blank=True)

    # Vermittlungsdetails (wenn placed)
    placed_consultant  = models.ForeignKey(
        'cv_extractor.Consultant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='placed_in_projects',
        help_text="Vermittelter Berater"
    )
    placed_at          = models.DateTimeField(null=True, blank=True)
    placed_rate        = models.IntegerField(null=True, blank=True, help_text="Vereinbarter Stundensatz €")
    placed_start       = models.DateField(null=True, blank=True, help_text="Erster Arbeitstag")
    placed_end         = models.DateField(null=True, blank=True, help_text="Vertragsende")
    placed_notes       = models.TextField(blank=True, help_text="Infos zum ersten Tag, Ansprechpartner vor Ort etc.")

    # ── Storage ────────────────────────────────────────────
    storage_paths = models.JSONField(default=dict, blank=True)

    # ── Metadaten ──────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name        = "Projektanfrage"
        verbose_name_plural = "Projektanfragen"
        ordering            = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['project_number']),
            models.Index(fields=['customer_name']),
            models.Index(fields=['priority']),
            models.Index(fields=['crm_account_id']),
            models.Index(fields=['crm_opportunity_id']),
            models.Index(fields=['is_archived', 'status']),
        ]

    def __str__(self):
        return f"{self.project_number or 'NEU'}: {self.title}"

    def save(self, *args, **kwargs):
        if not self.project_number:
            year = date.today().year
            count = ProjectRequest.objects.filter(
                created_at__year=year
            ).count() + 1
            self.project_number = f"ANF-{year}-{count:04d}"
        super().save(*args, **kwargs)

    def get_storage_path(self, file_type):
        return self.storage_paths.get(file_type, {})

    @property
    def subject_prefix(self):
        """Betreff-Präfix für E-Mails: [ANF-2026-0042]"""
        return f"[{self.project_number}]"


# ============================================================
# 4. PROJECT CONTACT  (mehrere AP pro Projekt)
# ============================================================

class ProjectContact(models.Model):
    """Ansprechpartner für ein Projekt — mehrere möglich"""

    ROLE_CHOICES = [
        ('decision_maker', 'Entscheider'),
        ('technical',      'Fachverantwortlicher'),
        ('admin',          'Sachbearbeiter'),
        ('cc_only',        'Nur CC'),
    ]

    id      = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        ProjectRequest, on_delete=models.CASCADE,
        related_name='contacts'
    )

    # SuiteCRM Verknüpfung
    crm_contact_id = models.CharField(max_length=36, blank=True, db_index=True,
                        help_text="SuiteCRM contacts.id")

    # Stammdaten (aus CRM oder manuell)
    first_name  = models.CharField(max_length=100)
    last_name   = models.CharField(max_length=100)
    email       = models.EmailField(blank=True)
    phone       = models.CharField(max_length=50, blank=True)
    mobile      = models.CharField(max_length=50, blank=True)
    department  = models.CharField(max_length=100, blank=True)

    # Rolle im Projekt
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='admin')

    # Persönliche Notiz
    personal_note = models.TextField(blank=True,
                        help_text="Nur vormittags, bevorzugt Teams, sehr entscheidungsfreudig...")

    # Individuelle Wiedervorlage-Regel
    followup_rule = models.ForeignKey(
        FollowupRule, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contacts'
    )

    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Projekt-Ansprechpartner"
        verbose_name_plural = "Projekt-Ansprechpartner"
        ordering            = ['sort_order', 'last_name']
        indexes = [
            models.Index(fields=['project', 'role']),
            models.Index(fields=['crm_contact_id']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_role_display()}) — {self.project.project_number}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


# ============================================================
# 5. PROJECT CONSULTANT  (Verknüpfung Projekt ⇔ Berater)
# ============================================================

class ProjectConsultant(models.Model):
    """Verknüpfung Projekt ⇔ Berater mit vollständigem Status-Tracking"""

    STATUS_CHOICES = [
        # Initial
        ('identified',          'Identifiziert'),
        ('contacted',           'Kontaktiert'),
        # Berater-Reaktion
        ('interested',          'Berater interessiert'),
        ('not_interested',      'Berater nicht interessiert'),
        ('unavailable',         'Berater nicht verfügbar'),
        # Angebot
        ('offer_prepared',      'Angebot erstellt'),
        ('offer_sent',          'Angebot gesendet'),
        # Kunden-Reaktion
        ('client_interested',   'Kunde interessiert'),
        ('client_not_interested','Kunde nicht interessiert'),
        ('client_no_feedback',  'Kein Feedback vom Kunden'),
        # Interview
        ('interview_scheduled', 'Interview geplant'),
        ('interview_done',      'Interview durchgeführt'),
        ('interview_cancelled', 'Interview abgesagt'),
        # Abschluss
        ('accepted',            'Zusage'),
        ('rejected',            'Absage'),
        ('placed',              'Vermittelt'),
        # Follow-up
        ('followup_sent',       'Nachfrage gesendet'),
        ('reminder_sent',       'Erinnerung gesendet'),
    ]

    REJECTION_REASONS = [
        ('price',            'Stundensatz zu hoch'),
        ('skills',           'Skills passen nicht'),
        ('availability',     'Nicht verfügbar'),
        ('location',         'Falscher Standort'),
        ('experience',       'Erfahrung nicht ausreichend'),
        ('personal',         'Persönliche Chemie'),
        ('other_client',     'Anderer Berater gewählt'),
        ('project_cancelled','Projekt storniert'),
        ('no_feedback',      'Keine Rückmeldung erhalten'),
        ('other',            'Sonstiger Grund'),
    ]

    id      = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        ProjectRequest, on_delete=models.CASCADE,
        related_name='consultants'
    )

    # ── FK auf cv_extractor.Consultant (ersetzt alten Consultant) ──
    consultant_cv = models.ForeignKey(
        'cv_extractor.Consultant',
        on_delete=models.CASCADE,
        related_name='project_matches',
        help_text="Berater aus cv_extractor DB"
    )

    # ── Matching-Ergebnis ──────────────────────────────────
    match_score   = models.FloatField(default=0,
                        validators=[MinValueValidator(0), MaxValueValidator(1)])
    match_details = models.JSONField(default=dict, blank=True)
    match_reason  = models.TextField(blank=True,
                        help_text="LLM-generierte Begründung warum dieser Berater passt")
    matched_at    = models.DateTimeField(auto_now_add=True)
    matched_by    = models.CharField(max_length=100, default='system')

    # ── CRM + Email Studio Verknüpfung ─────────────────────
    crm_email_id     = models.CharField(max_length=36, blank=True,
                            help_text="SuiteCRM emails.id")
    email_studio_id  = models.IntegerField(null=True, blank=True,
                            help_text="Email Studio Nachricht ID")

    # ── Status ─────────────────────────────────────────────
    status         = models.CharField(max_length=30, choices=STATUS_CHOICES, default='identified', db_index=True)
    status_history = models.JSONField(default=list, blank=True)

    # ── Berater-Kommunikation ──────────────────────────────
    contacted_at              = models.DateTimeField(null=True, blank=True)
    consultant_response_at    = models.DateTimeField(null=True, blank=True)
    consultant_response_note  = models.TextField(blank=True)

    # ── Nicht-Verfügbarkeit im Prozess ─────────────────────
    unavailable_at   = models.DateTimeField(null=True, blank=True,
                            help_text="Wann wurde Nicht-Verfügbarkeit gemeldet")
    unavailable_note = models.TextField(blank=True)

    # ── Follow-up ──────────────────────────────────────────
    followup_sent_at = models.DateTimeField(null=True, blank=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)

    # ── Angebot ────────────────────────────────────────────
    offer_text      = models.TextField(blank=True)
    offer_sent_at   = models.DateTimeField(null=True, blank=True)
    offer_documents = models.JSONField(default=dict, blank=True)

    # ── Kunden-Kommunikation ───────────────────────────────
    client_contacted_at  = models.DateTimeField(null=True, blank=True)
    client_response_at   = models.DateTimeField(null=True, blank=True)
    client_response_note = models.TextField(blank=True)

    # ── Interview ──────────────────────────────────────────
    interview_date     = models.DateTimeField(null=True, blank=True)
    interview_notes    = models.TextField(blank=True)
    interview_feedback = models.JSONField(default=dict, blank=True)

    # ── Absage ─────────────────────────────────────────────
    rejection_reason = models.CharField(max_length=50, choices=REJECTION_REASONS, blank=True)
    rejection_note   = models.TextField(blank=True)
    rejected_at      = models.DateTimeField(null=True, blank=True)
    rejected_by      = models.CharField(max_length=20,
                            choices=[('consultant','Berater'),('client','Kunde')], blank=True)

    # ── Zusage / Vermittlung ───────────────────────────────
    accepted_at        = models.DateTimeField(null=True, blank=True)
    placed_at          = models.DateTimeField(null=True, blank=True)
    agreed_rate        = models.IntegerField(null=True, blank=True)
    agreed_start_date  = models.DateField(null=True, blank=True)
    agreed_duration    = models.IntegerField(null=True, blank=True)

    # ── Vertragseingang vom Kunden ───────────────────────────
    client_contract_received     = models.BooleanField(default=False)
    client_contract_received_at  = models.DateTimeField(null=True, blank=True)
    client_contract_channel      = models.CharField(max_length=20, blank=True, default="",
                                   choices=[("email","E-Mail"),("post","Post"),("fax","Fax"),("portal","Portal"),("other","Sonstiges")])
    client_contract_note         = models.CharField(max_length=255, blank=True, default="")
    client_contract_sender       = models.CharField(max_length=100, blank=True, default="")
    client_contract_sender       = models.CharField(max_length=100, blank=True, default="")
    # ── Generierte Dokumente ───────────────────────────────
    generated_documents = models.JSONField(default=dict, blank=True)

    # ── Metadaten ──────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Projekt-Berater"
        verbose_name_plural = "Projekt-Berater"
        unique_together     = [['project', 'consultant_cv']]
        ordering            = ['-match_score']
        indexes = [
            models.Index(fields=['project', 'status']),
            models.Index(fields=['consultant_cv', 'status']),
            models.Index(fields=['status']),
            models.Index(fields=['contacted_at']),
            models.Index(fields=['followup_sent_at']),
            models.Index(fields=['crm_email_id']),
        ]

    def __str__(self):
        return f"{self.project.project_number} ↔ {self.consultant_cv.full_name} ({self.match_score:.2f})"

    def set_status(self, new_status, note="", user="system"):
        """Status mit vollständiger Historie ändern"""
        from django.utils import timezone
        self.status_history.append({
            'from': self.status,
            'to':   new_status,
            'at':   timezone.now().isoformat(),
            'note': note,
            'user': user,
        })
        self.status = new_status
        if new_status == 'followup_sent':
            self.followup_sent_at = timezone.now()
        elif new_status == 'reminder_sent':
            self.reminder_sent_at = timezone.now()
        elif new_status == 'contacted':
            self.contacted_at = timezone.now()
        elif new_status == 'unavailable':
            self.unavailable_at = timezone.now()
        self.save()

    @property
    def full_name(self):
        return self.consultant_cv.full_name

    @property
    def days_since_contacted(self):
        if self.contacted_at:
            return (date.today() - self.contacted_at.date()).days
        return None

    @property
    def needs_followup(self):
        """7 Tage ohne Antwort nach Kontaktaufnahme"""
        if self.status == 'contacted' and self.contacted_at:
            return (
                (date.today() - self.contacted_at.date()).days >= 7
                and not self.consultant_response_at
            )
        return False


# ============================================================
# 6. MATCH RESULT  (Scoring-Ergebnis pro Berater)
# ============================================================

class MatchResult(models.Model):
    """
    Scoring-Ergebnis eines Matching-Laufs.
    Getrennt von ProjectConsultant — ein Berater kann
    mehrfach gematcht werden (verschiedene Läufe).
    """

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project_request = models.ForeignKey(
        ProjectRequest, on_delete=models.CASCADE,
        related_name='match_results'
    )
    consultant_cv   = models.ForeignKey(
        'cv_extractor.Consultant',
        on_delete=models.CASCADE,
        related_name='match_results'
    )

    # ── Scores ─────────────────────────────────────────────
    overall_score    = models.FloatField(default=0.0, db_index=True)
    skill_score      = models.FloatField(default=0.0)
    industry_score   = models.FloatField(default=0.0)
    experience_score = models.FloatField(default=0.0)
    location_score   = models.FloatField(default=0.0)
    cert_score       = models.FloatField(default=0.0)
    rank             = models.IntegerField(default=0, db_index=True)

    # ── Detail-Daten ───────────────────────────────────────
    matched_skills  = models.JSONField(default=list, blank=True,
                            help_text='["SAP S/4HANA", "ABAP"]')
    missing_skills  = models.JSONField(default=list, blank=True,
                            help_text='["Fiori"]')
    skill_details   = models.JSONField(default=dict, blank=True)

    # ── LLM-Begründung ─────────────────────────────────────
    match_reason      = models.TextField(blank=True,
                            help_text="LLM-generierte Begründung")
    match_reason_lang = models.CharField(max_length=5, default='de')
    reason_model      = models.CharField(max_length=50, blank=True,
                            help_text="z.B. qwen2.5:7b oder deepseek-chat")

    # ── Meta ───────────────────────────────────────────────
    calculated_at  = models.DateTimeField(auto_now_add=True)
    calculated_by  = models.CharField(max_length=100, default='matching_engine')

    class Meta:
        verbose_name        = "Match-Ergebnis"
        verbose_name_plural = "Match-Ergebnisse"
        ordering            = ['-overall_score']
        indexes = [
            models.Index(fields=['project_request', 'overall_score']),
            models.Index(fields=['consultant_cv', 'calculated_at']),
            models.Index(fields=['rank']),
        ]

    def __str__(self):
        return f"{self.project_request.project_number} → {self.consultant_cv.full_name} ({self.overall_score:.2f})"


# ============================================================
# 7. EMAIL HISTORY
# ============================================================

class EmailHistory(models.Model):
    """Alle versendeten E-Mails tracken"""

    STATUS_CHOICES = [
        ('sent',    'Gesendet'),
        ('failed',  'Fehlgeschlagen'),
        ('opened',  'Geöffnet'),
        ('replied', 'Geantwortet'),
        ('bounced', 'Zurückgewiesen'),
        ('spam',    'Als Spam markiert'),
    ]

    id                 = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project_consultant = models.ForeignKey(
        ProjectConsultant, on_delete=models.CASCADE,
        related_name='emails', null=True, blank=True
    )
    project            = models.ForeignKey(
        ProjectRequest, on_delete=models.CASCADE,
        related_name='emails', null=True, blank=True
    )
    consultant_cv      = models.ForeignKey(
        'cv_extractor.Consultant', on_delete=models.CASCADE,
        related_name='match_emails', null=True, blank=True
    )

    email_type  = models.CharField(max_length=30, choices=EmailTemplate.TEMPLATE_TYPES)
    recipient   = models.EmailField()
    subject     = models.CharField(max_length=200)
    body        = models.TextField()
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sent')
    sent_at     = models.DateTimeField(auto_now_add=True)

    # SuiteCRM Sync
    crm_email_id = models.CharField(max_length=36, blank=True,
                        help_text="SuiteCRM emails.id nach Sync")

    # Tracking
    opened_at  = models.DateTimeField(null=True, blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)

    # Anhänge
    attachments   = models.JSONField(default=list, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        verbose_name        = "E-Mail-Verlauf"
        verbose_name_plural = "E-Mail-Verläufe"
        ordering            = ['-sent_at']
        indexes = [
            models.Index(fields=['recipient']),
            models.Index(fields=['email_type']),
            models.Index(fields=['status']),
            models.Index(fields=['crm_email_id']),
        ]

    def __str__(self):
        return f"{self.email_type} → {self.recipient} ({self.sent_at.date() if self.sent_at else 'pending'})"
