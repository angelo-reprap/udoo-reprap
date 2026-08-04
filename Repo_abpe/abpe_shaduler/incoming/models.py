"""
ABpE Shaduler — Modelle (V1-Skelett laut Architektur_zielvorlage.md Kap. 2).

Hinweis: Cross-App-FKs als Strings. Migrationen werden in einer späteren
Etappe erzeugt (`makemigrations abpe_shaduler`), nicht blind auf Live applied.

CRM-Bezug: SuiteCRM-IDs als CharField(36), kein Django-FK auf abpe_crm
(Matching-Muster: ProjectConsultant.crm_email_id) — vermeidet Cross-DB-
Constraints und PK/crm_id-Mismatch.
"""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import F
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ─── Ergebnis / Prozess ───────────────────────────────────────────────────────

class ProzessRegel(TimeStampedModel):
    class AusloeserTyp(models.TextChoices):
        STATUS_WECHSEL = 'status_wechsel', 'Status-Wechsel'
        ERGEBNIS = 'ergebnis', 'Ergebnis'
        ZEIT_OHNE_REAKTION = 'zeit_ohne_reaktion', 'Zeit ohne Reaktion'
        RADAR_SCORE = 'radar_score', 'Radar-Score'
        MANUELL = 'manuell', 'Manuell'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    beschreibung = models.TextField(blank=True)
    aktiv = models.BooleanField(default=True)
    ausloeser_typ = models.CharField(max_length=30, choices=AusloeserTyp.choices)
    ausloeser_wert = models.CharField(max_length=60, blank=True)
    bedingung = models.JSONField(default=dict, blank=True)
    followup_rule = models.ForeignKey(
        'abpe_matching_workflow.FollowupRule',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='shaduler_regeln',
    )
    erstellt_von = models.CharField(max_length=20, default='user')  # user | ki_wizard

    class Meta:
        verbose_name = 'Prozess-Regel'
        verbose_name_plural = 'Prozess-Regeln'
        ordering = ['name']

    def __str__(self):
        return self.name


class ProzessSchritt(models.Model):
    class AktionArt(models.TextChoices):
        AUFGABE_ERZEUGEN = 'aufgabe_erzeugen', 'Aufgabe erzeugen'
        EMAIL_SENDEN = 'email_senden', 'E-Mail senden'
        WHATSAPP_VORBEREITEN = 'whatsapp_vorbereiten', 'WhatsApp vorbereiten'
        STATUS_SETZEN = 'status_setzen', 'Status setzen'
        WARTEN = 'warten', 'Warten'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    regel = models.ForeignKey(ProzessRegel, on_delete=models.CASCADE, related_name='schritte')
    reihenfolge = models.PositiveIntegerField(default=1)
    aktion_art = models.CharField(max_length=30, choices=AktionArt.choices)
    parameter = models.JSONField(default=dict, blank=True)
    frist_offset = models.CharField(max_length=10, blank=True)  # +5d, -4w
    abbruch_bei = models.CharField(max_length=30, blank=True)

    class Meta:
        verbose_name = 'Prozess-Schritt'
        verbose_name_plural = 'Prozess-Schritte'
        ordering = ['regel', 'reihenfolge']
        unique_together = [('regel', 'reihenfolge')]

    def __str__(self):
        return f'{self.regel.name} · {self.reihenfolge}'


class ErgebnisTyp(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    label = models.CharField(max_length=100)
    label_i18n_key = models.CharField(max_length=60, blank=True)
    kontext = models.CharField(max_length=30, db_index=True)
    wirkung_status = models.CharField(max_length=30, blank=True)
    wirkung_regel = models.ForeignKey(
        ProzessRegel, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='ergebnis_typen',
    )
    eingabefelder = models.JSONField(default=list, blank=True)
    zeigt_dialog = models.BooleanField(default=False)
    schliesst_vorgang = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=100)
    aktiv = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Ergebnis-Typ'
        verbose_name_plural = 'Ergebnis-Typen'
        ordering = ['kontext', 'sort_order', 'label']

    def __str__(self):
        return f'{self.code} — {self.label}'


# ─── Aufgabe / Aktivität ──────────────────────────────────────────────────────

class Aufgabe(TimeStampedModel):
    class Art(models.TextChoices):
        ANRUF = 'anruf', 'Anruf'
        TERMIN = 'termin', 'Termin'
        EMAIL = 'email', 'E-Mail'
        SMS_MESSENGER = 'sms_messenger', 'SMS / Messenger'
        DOKUMENT = 'dokument', 'Dokument'
        POST = 'post', 'Post'
        WIEDERVORLAGE = 'wiedervorlage', 'Wiedervorlage'
        INTERN = 'intern', 'Intern'

    class Status(models.TextChoices):
        OFFEN = 'offen', 'Offen'
        ERLEDIGT = 'erledigt', 'Erledigt'
        VERWORFEN = 'verworfen', 'Verworfen'
        DELEGIERT = 'delegiert', 'Delegiert'

    class Quelle(models.TextChoices):
        REGEL = 'regel', 'Regel'
        STATUS = 'status', 'Status'
        MANUELL = 'manuell', 'Manuell'
        KI = 'ki', 'KI'
        RADAR = 'radar', 'Radar'
        MAIL = 'mail', 'Mail'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    art = models.CharField(max_length=20, choices=Art.choices, db_index=True)
    kanal = models.CharField(max_length=20, blank=True)
    titel = models.CharField(max_length=200)
    beschreibung = models.TextField(blank=True)
    faellig_am = models.DateField(db_index=True)
    faellig_zeit = models.TimeField(null=True, blank=True)
    prioritaet = models.PositiveSmallIntegerField(default=3)
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.OFFEN, db_index=True,
    )
    zugewiesen_an = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='shaduler_aufgaben', db_index=True,
    )
    ref_type = models.CharField(max_length=20, blank=True, db_index=True)
    ref_id = models.CharField(max_length=64, blank=True, db_index=True)
    quelle = models.CharField(max_length=15, choices=Quelle.choices, default=Quelle.MANUELL)
    regel = models.ForeignKey(
        ProzessRegel, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='aufgaben',
    )
    ergebnis = models.ForeignKey(
        ErgebnisTyp, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='aufgaben',
    )
    ergebnis_daten = models.JSONField(default=dict, blank=True)
    erledigt_am = models.DateTimeField(null=True, blank=True)
    erledigt_von = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='shaduler_erledigt',
    )
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='kinder',
    )
    gruppe_id = models.UUIDField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = 'Aufgabe'
        verbose_name_plural = 'Aufgaben'
        ordering = ['faellig_am', 'prioritaet', 'titel']
        indexes = [
            models.Index(fields=['status', 'faellig_am']),
            models.Index(fields=['zugewiesen_an', 'status']),
            models.Index(fields=['ref_type', 'ref_id']),
        ]

    def __str__(self):
        return f'{self.titel} ({self.get_status_display()})'


class Aktivitaet(models.Model):
    class Medium(models.TextChoices):
        TELEFON = 'telefon', 'Telefon'
        EMAIL = 'email', 'E-Mail'
        WHATSAPP = 'whatsapp', 'WhatsApp'
        SMS = 'sms', 'SMS'
        DOKUMENT = 'dokument', 'Dokument'
        POST = 'post', 'Post'
        TERMIN = 'termin', 'Termin'
        SYSTEM = 'system', 'System'
        RADAR = 'radar', 'Radar'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zeitpunkt = models.DateTimeField(default=timezone.now, db_index=True)
    medium = models.CharField(max_length=20, choices=Medium.choices)
    titel = models.CharField(max_length=250)
    ref_type = models.CharField(max_length=20, blank=True, db_index=True)
    ref_id = models.CharField(max_length=64, blank=True, db_index=True)
    deeplink_url = models.CharField(max_length=500, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='shaduler_aktivitaeten',
    )
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Aktivität'
        verbose_name_plural = 'Aktivitäten'
        ordering = ['-zeitpunkt']
        indexes = [
            models.Index(fields=['ref_type', 'ref_id']),
        ]

    def __str__(self):
        return f'{self.zeitpunkt:%Y-%m-%d %H:%M} · {self.titel}'


# ─── Radar / Sperrliste ───────────────────────────────────────────────────────

class RadarSource(TimeStampedModel):
    class Typ(models.TextChoices):
        RSS = 'rss', 'RSS'
        EMAIL_ALERT = 'email_alert', 'E-Mail-Alert'
        HTML_PUBLIC = 'html_public', 'HTML öffentlich'
        MANUELL = 'manuell', 'Manuell'

    class Ziel(models.TextChoices):
        ANFRAGEN = 'anfragen', 'Anfragen'
        BERATER = 'berater', 'Berater'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    typ = models.CharField(max_length=20, choices=Typ.choices)
    url = models.CharField(max_length=500, blank=True)
    query = models.CharField(max_length=200, blank=True)
    ziel = models.CharField(max_length=20, choices=Ziel.choices)
    intervall_min = models.PositiveIntegerField(default=5)
    aktiv = models.BooleanField(default=True)
    letzter_lauf = models.DateTimeField(null=True, blank=True)
    letzter_status = models.CharField(max_length=120, blank=True)

    class Meta:
        verbose_name = 'Radar-Quelle'
        verbose_name_plural = 'Radar-Quellen'

    def __str__(self):
        return self.name


class RadarItemGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merkmal_hash = models.CharField(max_length=64, db_index=True)
    titel_norm = models.CharField(max_length=250)
    anbieter_anzahl = models.PositiveIntegerField(default=1)
    erstellt_am = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Radar-Gruppe'
        verbose_name_plural = 'Radar-Gruppen'

    def __str__(self):
        return self.titel_norm


class RadarItemQuerySet(models.QuerySet):
    def order_by_score(self):
        """Postgres: DESC ohne nulls_last setzt NULLs zuerst — ungescorte oben."""
        return self.order_by(
            F('quick_score').desc(nulls_last=True),
            '-eingegangen_am',
        )


class RadarItemManager(models.Manager.from_queryset(RadarItemQuerySet)):
    def get_queryset(self):
        return super().get_queryset().order_by_score()


class RadarItem(TimeStampedModel):
    class Status(models.TextChoices):
        NEU = 'neu', 'Neu'
        INTERESSANT = 'interessant', 'Interessant'
        UEBERNOMMEN = 'uebernommen', 'Übernommen'
        VERWORFEN = 'verworfen', 'Verworfen'
        GESPERRT = 'gesperrt', 'Gesperrt'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quelle = models.ForeignKey(RadarSource, on_delete=models.CASCADE, related_name='items')
    external_url = models.CharField(max_length=600, blank=True)
    dedup_hash = models.CharField(max_length=64, db_index=True)
    gruppe = models.ForeignKey(
        RadarItemGroup, null=True, blank=True, on_delete=models.SET_NULL, related_name='items',
    )
    headline = models.CharField(max_length=250)
    beschreibung = models.TextField(blank=True)
    skills = models.JSONField(default=list, blank=True)
    eckdaten = models.JSONField(default=dict, blank=True)
    quick_score = models.FloatField(null=True, blank=True)
    top_berater = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NEU, db_index=True,
    )
    project_request = models.ForeignKey(
        'abpe_matching_workflow.ProjectRequest',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='radar_items',
    )
    eingegangen_am = models.DateTimeField(auto_now_add=True)

    objects = RadarItemManager()

    class Meta:
        verbose_name = 'Radar-Anfrage'
        verbose_name_plural = 'Radar-Anfragen'
        # Sortierung über Manager (nulls_last) — Meta.ordering allein setzt
        # in Postgres NULLs bei DESC zuerst.
        ordering = ['-eingegangen_am']

    def __str__(self):
        return self.headline


class RadarConsultantItem(TimeStampedModel):
    class MatchStatus(models.TextChoices):
        BEKANNT = 'bekannt', 'Bekannt'
        UNSICHER = 'unsicher', 'Unsicher'
        UNBEKANNT = 'unbekannt', 'Unbekannt'

    class Status(models.TextChoices):
        NEU = 'neu', 'Neu'
        BESTAETIGT = 'bestaetigt', 'Bestätigt'
        BEOBACHTEN = 'beobachten', 'Beobachten'
        VERWORFEN = 'verworfen', 'Verworfen'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quelle = models.ForeignKey(RadarSource, on_delete=models.CASCADE, related_name='consultant_items')
    profil_url = models.CharField(max_length=600, blank=True)
    dedup_hash = models.CharField(max_length=64, db_index=True)
    name = models.CharField(max_length=200, blank=True)
    skills = models.JSONField(default=list, blank=True)
    verfuegbar_ab = models.DateField(null=True, blank=True)
    satz = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    ort = models.CharField(max_length=120, blank=True)
    match_status = models.CharField(
        max_length=20, choices=MatchStatus.choices, default=MatchStatus.UNBEKANNT, db_index=True,
    )
    consultant = models.ForeignKey(
        'cv_extractor.Consultant',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='radar_items',
    )
    match_confidence = models.FloatField(null=True, blank=True)
    vorschlag = models.JSONField(default=dict, blank=True)
    auto_update_log = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NEU, db_index=True,
    )

    class Meta:
        verbose_name = 'Radar-Berater'
        verbose_name_plural = 'Radar-Berater'
        ordering = ['-updated_at']

    def __str__(self):
        return self.name or self.profil_url or str(self.id)


class Sperrliste(TimeStampedModel):
    class Richtung(models.TextChoices):
        DIE_NICHT_MIT_UNS = 'die_nicht_mit_uns', 'Die nicht mit uns'
        WIR_NICHT_MIT_DENEN = 'wir_nicht_mit_denen', 'Wir nicht mit denen'
        BEIDE = 'beide', 'Beide'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firma_name = models.CharField(max_length=200)
    firma_name_norm = models.CharField(max_length=200, blank=True, db_index=True)
    # SuiteCRM Account-ID (UUID), kein Django-FK — siehe Modul-Docstring.
    crm_account_id = models.CharField(max_length=36, blank=True, db_index=True)
    richtung = models.CharField(max_length=30, choices=Richtung.choices)
    grund = models.TextField(blank=True)
    seit = models.DateField()
    angelegt_von = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='shaduler_sperren',
    )
    aktiv = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Sperrliste-Eintrag'
        verbose_name_plural = 'Sperrliste'

    def __str__(self):
        return f'{self.firma_name} ({self.get_richtung_display()})'

    def save(self, *args, **kwargs):
        from .services.firma_normalizer import normalize_firma_name
        self.firma_name_norm = normalize_firma_name(self.firma_name)
        super().save(*args, **kwargs)
