"""
abpe_scheduler models — generischer, app-uebergreifender Zeitplaner.
Reines Backend mit API-Schnittstelle. Keine fachliche Logik hier —
das weiss nur die aufrufende App (owner_app/owner_type/owner_ref sind
fuer diese App reine, opake Strings).
"""
from django.db import models


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")

    class Meta:
        abstract = True


class SchedulerJob(BaseModel):
    SCHEDULE_TYPE_CHOICES = [
        ('ONCE', 'Einmalig'),
        ('RECURRING', 'Wiederkehrend (RRULE)'),
    ]
    DELIVERY_CHOICES = [
        ('PUSH', 'Push (Callback-URL)'),
        ('PULL', 'Pull (App holt selbst ab)'),
    ]
    STATUS_CHOICES = [
        ('ACTIVE', 'Aktiv'),
        ('PAUSED', 'Pausiert'),
        ('CANCELLED', 'Abgebrochen'),
        ('COMPLETED', 'Abgeschlossen'),
    ]

    owner_app = models.CharField(max_length=64, db_index=True, verbose_name="Aufrufende App")
    owner_type = models.CharField(max_length=64, db_index=True, verbose_name="Fachlicher Typ")
    owner_ref = models.CharField(max_length=128, db_index=True, verbose_name="Referenz-ID der App")

    job_key = models.CharField(max_length=128, blank=True, db_index=True, verbose_name="Job-Key (idempotent)")

    schedule_type = models.CharField(max_length=12, choices=SCHEDULE_TYPE_CHOICES, verbose_name="Typ")
    run_at = models.DateTimeField(null=True, blank=True, verbose_name="Zeitpunkt (bei Einmalig)")
    rrule_string = models.CharField(max_length=255, blank=True, verbose_name="RRULE (bei Wiederkehrend)")
    dtstart = models.DateTimeField(null=True, blank=True, verbose_name="Start der Wiederholung")
    until = models.DateTimeField(null=True, blank=True, verbose_name="Ende der Wiederholung (optional)")
    timezone = models.CharField(max_length=64, default='Europe/Berlin', verbose_name="Zeitzone")

    next_run_at = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name="Naechste Ausfuehrung")

    delivery_mode = models.CharField(max_length=4, choices=DELIVERY_CHOICES, default='PUSH', verbose_name="Zustellart")
    callback_url = models.URLField(max_length=500, blank=True, verbose_name="Callback-URL (bei Push)")
    payload = models.JSONField(default=dict, blank=True, verbose_name="Payload")

    lock_key = models.CharField(max_length=128, blank=True, db_index=True, verbose_name="Lock-Key")

    max_retries = models.IntegerField(default=3, verbose_name="Max. Wiederholungen")
    retry_backoff_seconds = models.IntegerField(default=300, verbose_name="Retry-Backoff (Sekunden)")

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='ACTIVE', db_index=True, verbose_name="Status")

    def __str__(self):
        return f"{self.owner_app}:{self.owner_type}:{self.owner_ref} @ {self.next_run_at}"

    class Meta:
        verbose_name = "Scheduler-Job"
        verbose_name_plural = "Scheduler-Jobs"
        ordering = ['next_run_at']
        indexes = [
            models.Index(fields=['status', 'next_run_at']),
            models.Index(fields=['owner_app', 'owner_type', 'owner_ref']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['owner_app', 'owner_type', 'owner_ref', 'job_key'],
                condition=~models.Q(job_key=''),
                name='uniq_scheduler_job_key',
            ),
        ]


class SchedulerJobRun(BaseModel):
    STATUS_CHOICES = [
        ('PENDING', 'Ausstehend'),
        ('RUNNING', 'Laeuft'),
        ('SUCCESS', 'Erfolgreich'),
        ('FAILED', 'Fehlgeschlagen'),
        ('SKIPPED', 'Uebersprungen'),
    ]

    job = models.ForeignKey(SchedulerJob, on_delete=models.CASCADE, related_name='runs', verbose_name="Job")

    scheduled_for = models.DateTimeField(verbose_name="Geplant fuer")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="Gestartet am")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="Beendet am")

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='PENDING', db_index=True, verbose_name="Status")
    attempt = models.IntegerField(default=1, verbose_name="Versuch")

    leased_at = models.DateTimeField(null=True, blank=True, verbose_name="Abgeholt am (Pull)")
    leased_until = models.DateTimeField(null=True, blank=True, verbose_name="Lease gueltig bis")

    response_status = models.IntegerField(null=True, blank=True, verbose_name="HTTP-Status Antwort")
    response_body = models.TextField(blank=True, verbose_name="Antwort (gekuerzt)")
    error_message = models.TextField(blank=True, verbose_name="Fehlermeldung")

    def __str__(self):
        return f"{self.job_id} @ {self.scheduled_for} — {self.get_status_display()}"

    class Meta:
        verbose_name = "Job-Ausfuehrung"
        verbose_name_plural = "Job-Ausfuehrungen"
        ordering = ['-scheduled_for']
        indexes = [
            models.Index(fields=['status', 'scheduled_for']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['job', 'scheduled_for'],
                name='uniq_job_run_per_schedule',
            ),
        ]
