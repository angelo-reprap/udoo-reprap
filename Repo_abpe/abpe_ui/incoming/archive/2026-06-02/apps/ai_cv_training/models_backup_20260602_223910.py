"""
ai_cv_training/models.py - Selbstlernende Trainingsdatenbank
LERNT aus: Namazu (20.000 HTML), AID-Registry, URL-Profilen, Email-Attachments
SPEICHERT: Begriffe, Kategorien, Beziehungen, Statistiken, REGEX-PATTERNS
NUTZT FÜR: master.json → all.json Anreicherung
"""

from django.db import models
from django.utils import timezone
import uuid


class BaseModel(models.Model):
    """Basis-Model für alle Training-Models"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TrainingTerm(BaseModel):
    """
    GELERNTER BEGRIFF - Das Herzstück des Trainings
    Speichert jeden Begriff mit seiner Kategorie und Metadaten
    """

    # Kategorie-Typen (aus Master-JSON)
    CATEGORY_CHOICES = [
        # Skills (aus normalized.skills)
        ('programming_language', 'Programmiersprache'),
        ('framework', 'Framework'),
        ('database', 'Datenbank'),
        ('cloud_platform', 'Cloud-Plattform'),
        ('devops_tool', 'DevOps-Tool'),
        ('security_tool', 'Security-Tool'),
        ('it_infrastructure', 'IT-Infrastruktur'),
        ('methodology', 'Methodik'),
        ('ai_specialization', 'AI-Spezialisierung'),
        ('soft_skill', 'Soft Skill'),

        # Andere Kategorien
        ('certification', 'Zertifikat'),
        ('industry', 'Branche'),
        ('role', 'Rolle'),
        ('language', 'Sprache'),
        ('education', 'Ausbildung'),
        ('tool', 'Werkzeug'),
        ('other', 'Sonstiges'),
    ]

    # Der gelernte Begriff (normalisiert)
    term = models.CharField(max_length=200, db_index=True, unique=True)

    # Kanonische Form (z.B. "sps" für alle Schreibweisen)
    canonical_term = models.CharField(max_length=200, db_index=True)

    # Kategorie
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, db_index=True)
    subcategory = models.CharField(max_length=100, blank=True)

    # Konfidenz (0-1) - Wie sicher sind wir?
    confidence = models.FloatField(default=0.0)

    # Häufigkeit - Wie oft gesehen?
    frequency = models.IntegerField(default=1)

    # Variationen (verschiedene Schreibweisen)
    variations = models.JSONField(default=list, blank=True)

    # Quellen, wo dieser Begriff gelernt wurde
    SOURCE_CHOICES = [
        ('namazu', 'Namazu HTML (20.000 Dokumente)'),
        ('aid_registry', 'AID Registry (hunderte Profile)'),
        ('url_profile', 'URL-Profil (Gulp/XING/LinkedIn)'),
        ('email_attachment', 'Email-Anhang'),
        ('manual_import', 'Manueller Import'),
        ('ollama_learning', 'Ollama KI-Learning'),
        ('user_feedback', 'Benutzer-Feedback'),
    ]
    sources = models.JSONField(default=list)  # Liste der Quellen

    # Referenz-IDs aus Quellen (für Nachvollziehbarkeit)
    source_ids = models.JSONField(default=list, blank=True)

    # Kontext (Beispielsätze wo der Begriff vorkam)
    example_contexts = models.JSONField(default=list, blank=True, max_length=5)

    # Verwandte Begriffe (für Skill-Graph)
    related_terms = models.JSONField(default=list, blank=True)

    # Metadaten (zusätzliche Infos)
    metadata = models.JSONField(default=dict, blank=True)

    # Zeitstempel
    first_seen = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Trainingsbegriff"
        verbose_name_plural = "Trainingsbegriffe"
        ordering = ['-frequency', '-confidence']
        indexes = [
            models.Index(fields=['term']),
            models.Index(fields=['canonical_term']),
            models.Index(fields=['category']),
            models.Index(fields=['confidence']),
            models.Index(fields=['frequency']),
            models.Index(fields=['last_seen']),
        ]

    def __str__(self):
        return f"{self.term} ({self.get_category_display()})"

    def increment_frequency(self):
        """Erhöht die Häufigkeit und aktualisiert last_seen"""
        self.frequency += 1
        self.last_seen = timezone.now()
        self.save(update_fields=['frequency', 'last_seen'])

    def add_variation(self, variation):
        """Fügt eine neue Schreibweise hinzu"""
        if variation and variation not in self.variations:
            self.variations.append(variation)
            self.save(update_fields=['variations'])

    def add_context(self, context):
        """Fügt einen Beispielkontext hinzu (max 5)"""
        if context and len(self.example_contexts) < 5:
            if context not in self.example_contexts:
                self.example_contexts.append(context[:200])
                self.save(update_fields=['example_contexts'])


class TrainingSource(BaseModel):
    """
    QUELLEN für Training
    Verfolgt, woher unsere Trainingsdaten kommen
    """

    SOURCE_TYPE_CHOICES = [
        ('namazu_index', 'Namazu-Index (20.000 HTML)'),
        ('aid_registry', 'AID Registry'),
        ('url_profile', 'URL-Profil'),
        ('email_attachment', 'Email-Anhang'),
        ('manual_profile', 'Manuelles Profil'),
        ('csv_import', 'CSV-Import'),
        ('elasticsearch', 'ElasticSearch'),
        ('ollama_suggestion', 'Ollama-Vorschlag'),
        ('user_input', 'Benutzereingabe'),
    ]

    source_type = models.CharField(max_length=30, choices=SOURCE_TYPE_CHOICES, db_index=True)
    source_name = models.CharField(max_length=200)
    source_path = models.CharField(max_length=500, blank=True)
    source_id = models.CharField(max_length=255, blank=True, db_index=True)

    metadata = models.JSONField(default=dict, blank=True)

    STATUS_CHOICES = [
        ('pending', 'Ausstehend'),
        ('processing', 'In Verarbeitung'),
        ('processed', 'Verarbeitet'),
        ('failed', 'Fehlgeschlagen'),
        ('partial', 'Teilweise verarbeitet'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    total_terms = models.IntegerField(default=0)
    new_terms = models.IntegerField(default=0)
    processing_time = models.FloatField(default=0.0)

    error_message = models.TextField(blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Trainingsquelle"
        verbose_name_plural = "Trainingsquellen"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['source_type']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.get_source_type_display()}: {self.source_name}"

    def mark_processing(self):
        self.status = 'processing'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])

    def mark_completed(self, total_terms=0, new_terms=0, processing_time=0):
        self.status = 'processed'
        self.completed_at = timezone.now()
        self.total_terms = total_terms
        self.new_terms = new_terms
        self.processing_time = processing_time
        self.save(update_fields=['status', 'completed_at', 'total_terms', 'new_terms', 'processing_time'])

    def mark_failed(self, error):
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.error_message = str(error)[:1000]
        self.save(update_fields=['status', 'completed_at', 'error_message'])


class TrainingRelation(BaseModel):
    """
    BEZIEHUNGEN zwischen Begriffen
    Für Skill-Graph und Ähnlichkeitsberechnungen
    """

    RELATION_TYPE_CHOICES = [
        ('synonym', 'Synonym'),
        ('co_occurrence', 'Gemeinsames Auftreten'),
        ('parent_child', 'Über-/Unterordnung'),
        ('related', 'Verwandt'),
        ('prerequisite', 'Voraussetzung'),
        ('complement', 'Ergänzend'),
    ]

    term_from = models.ForeignKey(TrainingTerm, on_delete=models.CASCADE, related_name='relations_from')
    term_to = models.ForeignKey(TrainingTerm, on_delete=models.CASCADE, related_name='relations_to')

    relation_type = models.CharField(max_length=20, choices=RELATION_TYPE_CHOICES)

    weight = models.FloatField(default=0.5)
    frequency = models.IntegerField(default=1)
    confidence = models.FloatField(default=0.0)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Begriffsbeziehung"
        verbose_name_plural = "Begriffsbeziehungen"
        unique_together = ['term_from', 'term_to', 'relation_type']
        indexes = [
            models.Index(fields=['term_from', 'relation_type']),
            models.Index(fields=['term_to', 'relation_type']),
            models.Index(fields=['weight']),
        ]

    def __str__(self):
        return f"{self.term_from.term} → {self.term_to.term} ({self.get_relation_type_display()})"

    def increment_frequency(self):
        self.frequency += 1
        self.save(update_fields=['frequency'])


class TrainingStatistics(BaseModel):
    """
    STATISTIKEN über den Trainingszustand
    """

    STAT_TYPE_CHOICES = [
        ('category', 'Kategorie-Statistik'),
        ('source', 'Quellen-Statistik'),
        ('performance', 'Performance'),
        ('quality', 'Qualität'),
    ]

    stat_type = models.CharField(max_length=20, choices=STAT_TYPE_CHOICES)
    category = models.CharField(max_length=50, blank=True)

    total_terms = models.IntegerField(default=0)
    unique_terms = models.IntegerField(default=0)
    avg_confidence = models.FloatField(default=0.0)
    total_relations = models.IntegerField(default=0)

    terms_last_hour = models.IntegerField(default=0)
    terms_last_day = models.IntegerField(default=0)
    terms_last_week = models.IntegerField(default=0)

    top_terms = models.JSONField(default=list, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Trainingsstatistik"
        verbose_name_plural = "Trainingsstatistiken"
        unique_together = ['stat_type', 'category']

    def __str__(self):
        if self.category:
            return f"{self.get_stat_type_display()}: {self.category}"
        return self.get_stat_type_display()


class TrainingFeedback(BaseModel):
    """
    BENUTZER-FEEDBACK für Trainingsergebnisse
    Ermöglicht manuelle Korrekturen
    """

    FEEDBACK_TYPE_CHOICES = [
        ('correction', 'Korrektur'),
        ('confirmation', 'Bestätigung'),
        ('rejection', 'Ablehnung'),
        ('suggestion', 'Vorschlag'),
    ]

    term = models.ForeignKey(TrainingTerm, on_delete=models.CASCADE, null=True, blank=True)
    relation = models.ForeignKey(TrainingRelation, on_delete=models.CASCADE, null=True, blank=True)

    feedback_type = models.CharField(max_length=20, choices=FEEDBACK_TYPE_CHOICES)

    original_category = models.CharField(max_length=50, blank=True)
    original_confidence = models.FloatField(default=0.0)

    corrected_category = models.CharField(max_length=50, blank=True)
    corrected_confidence = models.FloatField(default=0.0)

    comment = models.TextField(blank=True)

    user_id = models.UUIDField(null=True, blank=True)
    user_email = models.EmailField(blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Trainingsfeedback"
        verbose_name_plural = "Trainingsfeedbacks"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_feedback_type_display()} für {self.term or '?'}"


class TrainingBatch(BaseModel):
    """
    BATCH-VERARBEITUNG für größere Trainingsläufe
    """

    BATCH_TYPE_CHOICES = [
        ('namazu_import', 'Namazu-Import (20.000 HTML)'),
        ('aid_import', 'AID-Registry Import'),
        ('url_import', 'URL-Profil Import'),
        ('email_import', 'Email-Anhang Import'),
        ('elasticsearch_sync', 'ElasticSearch Sync'),
        ('ollama_batch', 'Ollama Batch-Learning'),
    ]

    batch_type = models.CharField(max_length=30, choices=BATCH_TYPE_CHOICES)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    parameters = models.JSONField(default=dict, blank=True)

    STATUS_CHOICES = [
        ('pending', 'Ausstehend'),
        ('running', 'Läuft'),
        ('completed', 'Abgeschlossen'),
        ('failed', 'Fehlgeschlagen'),
        ('cancelled', 'Abgebrochen'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    total_items = models.IntegerField(default=0)
    processed_items = models.IntegerField(default=0)
    new_terms = models.IntegerField(default=0)
    updated_terms = models.IntegerField(default=0)

    log_file = models.CharField(max_length=500, blank=True)
    error_log = models.TextField(blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(default=0.0)

    class Meta:
        verbose_name = "Trainingsbatch"
        verbose_name_plural = "Trainingsbatches"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_batch_type_display()}: {self.name} ({self.status})"

    @property
    def progress_percent(self):
        if self.total_items == 0:
            return 0
        return round((self.processed_items / self.total_items) * 100, 1)

    def mark_running(self):
        self.status = 'running'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])

    def mark_completed(self):
        self.status = 'completed'
        self.completed_at = timezone.now()
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_seconds = delta.total_seconds()
        self.save(update_fields=['status', 'completed_at', 'duration_seconds'])

    def mark_failed(self, error):
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.error_log = str(error)[:5000]
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_seconds = delta.total_seconds()
        self.save(update_fields=['status', 'completed_at', 'error_log', 'duration_seconds'])


# =========================================================
# NEUE MODELLE FÜR REGEX-EXTRAKTION (SELBSTLERNEND)
# =========================================================

class ExtractionRule(models.Model):
    """
    REGEX-REGELN für CV-Extraktion (selbstlernend)
    Wird von KI befüllt und für schnelle Regex-Extraktion genutzt
    """
    
    BLOCK_TYPES = [
        ('experience', '💼 Experience / Projekte'),
        ('skills', '🔧 Skills'),
        ('personal', '👤 Persönliche Daten'),
        ('header', '📌 Header / Schwerpunkt'),
        ('education', '🎓 Ausbildung'),
        ('certifications', '🏆 Zertifikate'),
        ('industries', '🏢 Branchen'),
        ('focus_areas', '🎯 Fachbereiche'),
        ('splitter', '✂️ Splitter'),
        ('other', '📦 Sonstiges'),
    ]
    
    # Welcher Block?
    block_type = models.CharField(max_length=20, choices=BLOCK_TYPES, db_index=True)
    
    # Welches Feld?
    field_name = models.CharField(max_length=50, help_text="z.B. period, role, company")
    field_label = models.CharField(max_length=100, help_text="z.B. Zeitraum, Rolle, Firma")
    
    # Das Regex-Muster
    regex_pattern = models.TextField(help_text="Python Regex Pattern, z.B. r'Zeitraum:\\s*(.*?)(?:\\n|$)'")
    
    # Kontext (vor/nach dem Pattern)
    context_before = models.CharField(max_length=200, blank=True)
    context_after = models.CharField(max_length=200, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    confidence = models.FloatField(default=0.0, help_text="Konfidenz (0-1)")
    learned_by_ai = models.BooleanField(default=False)
    
    # Nutzungsstatistik
    usage_count = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    
    # Metadaten
    notes = models.TextField(blank=True, help_text="Beschreibung oder Hinweise zur Regel")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Extraktionsregel"
        verbose_name_plural = "Extraktionsregeln"
        unique_together = ['block_type', 'field_name', 'regex_pattern']
        indexes = [
            models.Index(fields=['block_type', 'is_active']),
            models.Index(fields=['block_type', 'field_name']),
            models.Index(fields=['-confidence']),
        ]
    
    @property
    def success_rate(self):
        if self.usage_count == 0:
            return 0.0
        return self.success_count / self.usage_count
    
    def __str__(self):
        return f"[{self.get_block_type_display()}] {self.field_label}: {self.regex_pattern[:50]}"
    
    def increment_usage(self, success=True):
        self.usage_count += 1
        if success:
            self.success_count += 1
        self.save(update_fields=['usage_count', 'success_count'])


class BlockMarker(models.Model):
    """
    MARKER für Block-Erkennung (z.B. "Berufliche Erfahrungen")
    Wird von KI erkannt und gespeichert
    """
    
    BLOCK_TYPES = [
        ('experience', '💼 Experience / Projekte'),
        ('skills', '🔧 Skills'),
        ('personal', '👤 Persönliche Daten'),
        ('header', '📌 Header / Schwerpunkt'),
        ('education', '🎓 Ausbildung'),
        ('certifications', '🏆 Zertifikate'),
        ('industries', '🏢 Branchen'),
        ('focus_areas', '🎯 Fachbereiche'),
        ('splitter', '✂️ Splitter'),
        ('other', '📦 Sonstiges'),
    ]
    
    block_type = models.CharField(max_length=20, choices=BLOCK_TYPES, db_index=True)
    marker_text = models.CharField(max_length=200, help_text="z.B. 'Berufliche Erfahrungen'")
    
    # Regex für Block-Start und -Ende
    start_regex = models.CharField(max_length=500, blank=True)
    end_regex = models.CharField(max_length=500, blank=True)
    
    is_active = models.BooleanField(default=True)
    confidence = models.FloatField(default=0.0)
    learned_by_ai = models.BooleanField(default=False)
    
    usage_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Block-Marker"
        verbose_name_plural = "Block-Marker"
        unique_together = ['block_type', 'marker_text']
        indexes = [
            models.Index(fields=['block_type', 'is_active']),
        ]
    
    def __str__(self):
        return f"[{self.get_block_type_display()}] {self.marker_text}"
    
    def increment_usage(self):
        self.usage_count += 1
        self.save(update_fields=['usage_count'])


class ProcessingLog(models.Model):
    """
    LOG der Verarbeitungen für Analyse und Verbesserung
    """
    
    BLOCK_TYPES = ExtractionRule.BLOCK_TYPES
    
    block_type = models.CharField(max_length=20, choices=BLOCK_TYPES, db_index=True)
    method = models.CharField(max_length=10, choices=[('regex', 'Regex'), ('ki', 'KI')])
    success = models.BooleanField(default=False)
    duration_ms = models.IntegerField()
    marker_used = models.CharField(max_length=200, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Verarbeitungslog"
        verbose_name_plural = "Verarbeitungslogs"
        indexes = [
            models.Index(fields=['block_type', 'created_at']),
            models.Index(fields=['method', 'success']),
        ]
    
    def __str__(self):
        return f"{self.created_at.strftime('%Y-%m-%d %H:%M')} - {self.block_type} - {self.method}"
