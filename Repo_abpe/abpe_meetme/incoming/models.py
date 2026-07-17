"""
abpe_meetme models — Konferenz-/MeetMe-Planung (Reiter 1 im CRM-PBX-Cockpit).
Meeting, Guest, ReminderRule, ReminderDelivery.

Terminierung der Erinnerungen laeuft NICHT ueber eigene Scheduling-Logik,
sondern ausschliesslich ueber die abpe_scheduler-API (HTTP, kein Model-Import) —
siehe scheduler_client.py und reminder_engine.py.
"""
from django.db import models


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")

    class Meta:
        abstract = True


class MeetmeMeeting(BaseModel):
    STATUS_CHOICES = [
        ('PLANNED', 'Geplant'),
        ('CONFIRMED', 'Bestaetigt'),
        ('CANCELLED', 'Abgesagt'),
        ('COMPLETED', 'Abgeschlossen'),
    ]

    title = models.CharField(max_length=200, verbose_name="Titel")
    description = models.TextField(blank=True, verbose_name="Beschreibung")

    start_at = models.DateTimeField(verbose_name="Beginn")
    duration_minutes = models.IntegerField(default=60, verbose_name="Dauer (Minuten)")

    # Raum/Konferenznummer werden ueber die PBX (AMI, Extensions 034/035,
    # Konferenz-Basis 5555) gelesen und hier nur als gewaehlter Wert gespeichert.
    room_extension = models.CharField(max_length=20, blank=True, verbose_name="Konferenzraum (Extension)")
    meetme_number = models.CharField(max_length=20, blank=True, verbose_name="MeetMe-Nummer")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANNED', verbose_name="Status")

    # Bezug auf CRM (SuiteCRM), rein als opaker String, kein FK
    account_crm_id = models.CharField(max_length=64, blank=True, null=True, verbose_name="Kunde (crm_id)")

    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='meetme_meetings', verbose_name="Erstellt von"
    )

    def __str__(self):
        return f"{self.title} ({self.start_at:%d.%m.%Y %H:%M})"

    class Meta:
        verbose_name = "Meeting"
        verbose_name_plural = "Meetings"
        ordering = ['start_at']


class MeetmeGuest(BaseModel):
    STATUS_CHOICES = [
        ('PENDING', 'Ausstehend'),
        ('CONFIRMED', 'Bestaetigt'),
        ('DECLINED', 'Abgesagt'),
    ]

    meeting = models.ForeignKey(
        MeetmeMeeting, on_delete=models.CASCADE,
        related_name='guests', verbose_name="Meeting"
    )

    # Optionaler Bezug auf CRM-Kontakt (crm_id, string) — Gast kann auch rein extern sein.
    contact_crm_id = models.CharField(max_length=64, blank=True, null=True, verbose_name="Kontakt (crm_id)")

    name = models.CharField(max_length=200, verbose_name="Name")
    email = models.EmailField(verbose_name="E-Mail")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Telefon")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name="Status")

    # "Endgueltig aus der Erinnerungskette nehmen", ohne den Gast zu loeschen —
    # Unterscheidung von einmaligem "Ueberspringen" auf Delivery-Ebene.
    is_active = models.BooleanField(default=True, verbose_name="Aktiv (in Erinnerungen beruecksichtigen)")

    # Zeitpunkt der initialen Einladung -- getrennt von 'status' (RSVP-Antwort).
    invited_at = models.DateTimeField(null=True, blank=True, verbose_name="Eingeladen am")
    last_notified_start_at = models.DateTimeField(null=True, blank=True, verbose_name="Zuletzt informiert über Termin (Stand)")
    notified_cancelled = models.BooleanField(default=False, verbose_name="Über Absage informiert")

    def __str__(self):
        return f"{self.name} — {self.meeting.title}"

    class Meta:
        verbose_name = "Gast"
        verbose_name_plural = "Gaeste"
        ordering = ['name']


class MeetmeReminderRule(BaseModel):
    UNIT_CHOICES = [
        ('MINUTES', 'Minuten'),
        ('HOURS', 'Stunden'),
        ('DAYS', 'Tage'),
    ]
    MODE_CHOICES = [
        ('MANUAL', 'Manuell pruefen'),
        ('AUTO', 'Automatisch senden'),
    ]

    meeting = models.ForeignKey(
        MeetmeMeeting, on_delete=models.CASCADE,
        related_name='reminder_rules', verbose_name="Meeting"
    )

    # Optional: Regel gilt nur fuer diesen einen Gast statt fuer alle aktiven
    # Gaeste des Meetings. leer (None) = bestehendes Verhalten (alle Gaeste).
    guest = models.ForeignKey(
        MeetmeGuest, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='guest_reminder_rules',
        verbose_name="Nur fuer diesen Gast (leer = alle Gaeste)"
    )

    offset_value = models.IntegerField(verbose_name="Offset-Wert")
    offset_unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='HOURS', verbose_name="Einheit")

    # Nur relevant bei offset_unit='DAYS' — freie Uhrzeit statt exakter Meeting-Zeit
    time_of_day = models.TimeField(null=True, blank=True, verbose_name="Uhrzeit (nur bei Tage)")

    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default='MANUAL', verbose_name="Modus")
    send_copy_to_owner = models.BooleanField(default=False, verbose_name="Kopie an Ersteller (nur bei Automatisch)")

    # Lose Kopplung zu abpe_email_studio.EmailTemplate — nur die numerische ID,
    # kein FK/Model-Import (App-Grenze bleibt sauber getrennt).
    template_id = models.IntegerField(null=True, blank=True, verbose_name="Vorlage (EmailTemplate-ID)")

    # Kennzeichnet automatisch erzeugte "Termin hat sich geaendert"-Benachrichtigungen
    is_change_notice = models.BooleanField(default=False, verbose_name="Terminaenderungs-Hinweis")

    # Individueller Text statt/zusaetzlich zur Vorlage - ermoeglicht pro Regel
    # (und damit pro Gast, wenn 'guest' gesetzt ist) einen eigenen Betreff/Text.
    subject = models.CharField(max_length=255, blank=True, verbose_name="Betreff (individuell)")
    body = models.TextField(blank=True, verbose_name="Text (individuell)")
    attachment_refs = models.JSONField(default=list, blank=True, verbose_name="Anhaenge (Referenzen)")

    def __str__(self):
        return f"{self.meeting.title}: {self.offset_value} {self.get_offset_unit_display()} vorher ({self.get_mode_display()})"

    class Meta:
        verbose_name = "Erinnerungsregel"
        verbose_name_plural = "Erinnerungsregeln"
        ordering = ['meeting', '-offset_value']


class MeetmeReminderDelivery(BaseModel):
    """Konkrete, fuer einen Gast materialisierte Erinnerungs-Zustellung.
    Wird bei Aenderungen an Meeting/Gaesten/Regeln per reminder_engine.sync_reminder_deliveries()
    neu berechnet. Die eigentliche Terminierung laeuft ueber einen SchedulerJob
    in abpe_scheduler (referenziert per scheduler_job_id, nur als Zahl, kein FK)."""

    STATUS_CHOICES = [
        ('PENDING', 'Ausstehend'),
        ('DUE', 'Faellig'),
        ('SENT', 'Gesendet'),
        ('SKIPPED', 'Uebersprungen'),
        ('FAILED', 'Fehlgeschlagen'),
    ]

    rule = models.ForeignKey(
        MeetmeReminderRule, on_delete=models.CASCADE,
        related_name='deliveries', verbose_name="Regel"
    )
    guest = models.ForeignKey(
        MeetmeGuest, on_delete=models.CASCADE,
        related_name='reminder_deliveries', verbose_name="Gast"
    )

    scheduled_at = models.DateTimeField(verbose_name="Faellig am", db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name="Status")

    # Snapshot dessen, was tatsaechlich verschickt wurde bzw. im Sende-Assistenten
    # gerade bearbeitet wird.
    subject = models.CharField(max_length=255, blank=True, verbose_name="Betreff")
    body = models.TextField(blank=True, verbose_name="Text")

    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Gesendet am")
    failed_reason = models.TextField(blank=True, verbose_name="Fehlergrund")

    # Lose Kopplung, nur IDs — kein FK auf fremde Apps
    email_log_id = models.IntegerField(null=True, blank=True, verbose_name="E-Mail-Log-ID")
    scheduler_job_id = models.IntegerField(null=True, blank=True, verbose_name="Scheduler-Job-ID")

    def __str__(self):
        return f"{self.guest.name} — {self.rule} — {self.get_status_display()}"

    class Meta:
        verbose_name = "Erinnerungs-Zustellung"
        verbose_name_plural = "Erinnerungs-Zustellungen"
        ordering = ['scheduled_at']
        indexes = [
            models.Index(fields=['status', 'scheduled_at']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['rule', 'guest'], name='uniq_meetme_delivery_per_rule_guest'),
        ]
