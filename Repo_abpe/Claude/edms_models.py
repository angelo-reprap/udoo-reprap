# -*- coding: utf-8 -*-
"""
apps/abpe_edms/models.py
================================================================================
ABpE EDMS — Datenbankschema (High-Level, vollständig angelegt)

Designprinzipien
----------------
1.  Der ORDNER (Samba) ist die Wahrheit. Dieses Schema ist das *Register*, das
    das Dateisystem spiegelt — Pfad + Prüfsumme leben in CrmDocumentVersion.
2.  Owner-Schlüssel ist die kanonische `crm_id` als String (NICHT als harte FK
    auf abpe_crm), damit die App entkoppelt migrierbar bleibt — exakt das Muster
    von CrmCallRecording (contact_crm_id / account_crm_id).
3.  Drei Beziehungs-Muster, die das echte Geschäft abbilden:
      - Dokument <-> Owner            : n:m mit Rolle   (CrmDocumentOwner)
        (ein Rahmenvertrag gehört Kunde + mehreren Beratern)
      - Dokument  -> Gewerk           : n:1 optional    (CrmDocument.gewerk)
        (Leistungsnachweise & Rechnungen gruppieren sich am Gewerk)
      - Dokument <-> Dokument         : n:m lose        (DmsDocumentLink)
        (Ausgangsrechnung bezieht sich auf n Eingangs-Leistungsnachweise,
         OHNE 1:1-Zwang — Eingang != Ausgang ist erlaubt)
4.  Zwei Uhren, niemals dasselbe Feld:
      - Gültigkeit  (valid_until)     = Geschäfts-Laufzeit des Dokuments
      - Aufbewahrung (retention_until)= gesetzliche Pflicht (GoBD/§147 AO),
        berechnet aus document_date + retention_years, gerundet auf Jahresende.
5.  Soft-Delete/Archiv über in_trash + trashed_at (Mayan-Muster). Endgültiges
    Löschen ist eine bewusste, protokollierte Aktion (DmsDocumentEvent).
6.  Versionierung wie Mayan DocumentFile: jede Datei-Generation ist eine
    CrmDocumentVersion; genau eine ist is_active, ältere wandern ins Archiv.

Vorbild: Mayan EDMS (DocumentType/Document/DocumentFile, Metadata, Tags) +
Paperless-ngx (StoragePath-Template, is_inbox_tag, Matching, content/Volltext).
================================================================================
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


# =============================================================================
#  AUFZÄHLUNGEN (TextChoices) — zentral, damit Werte stabil & migrationsfest sind
# =============================================================================

class OwnerType(models.TextChoices):
    CONTACT = "contact", "Berater (CrmContact)"
    ACCOUNT = "account", "Kunde (CrmAccount)"


class OwnerRole(models.TextChoices):
    PRIMAER = "primaer", "Primärer Eigentümer"
    GETEILT = "geteilt", "Geteilt (mehrere Berater)"
    KUNDE = "kunde", "Kunde / Auftraggeber"
    KOPIE = "kopie", "Nur Kopie / Kenntnis"


class StorageVolume(models.TextChoices):
    OFFICE = "office", "O: office (Geschäftsdokumente)"
    PUBLIC = "public", "X: public (CVs / Profile)"


class DocSource(models.TextChoices):
    GENERIERT = "generiert", "Generiert (studio_doc)"
    HOCHGELADEN = "hochgeladen", "Hochgeladen (Web)"
    GESCANNT = "gescannt", "Gescannt (Samba-Sync)"
    EMAIL = "email", "Per E-Mail (Posteingang)"


class DocStatus(models.TextChoices):
    ENTWURF = "entwurf", "Entwurf"
    GUELTIG = "gueltig", "Gültig"
    ABGELAUFEN = "abgelaufen", "Abgelaufen (Gültigkeit)"
    ARCHIVIERT = "archiviert", "Archiviert"


class DocDirection(models.TextChoices):
    KEINE = "keine", "—"
    EINGANG = "eingang", "Eingang (von Berater an abcona)"
    AUSGANG = "ausgang", "Ausgang (von abcona an Kunde)"


class MatchingAlgorithm(models.IntegerChoices):
    NONE = 0, "Keine"
    ANY = 1, "Irgendein Wort"
    ALL = 2, "Alle Wörter"
    LITERAL = 3, "Exakte Zeichenkette"
    REGEX = 4, "Regulärer Ausdruck"
    FUZZY = 5, "Unscharf"
    AUTO = 6, "Auto (KI / Deepseek)"


class GewerkStatus(models.TextChoices):
    AKTIV = "aktiv", "Aktiv"
    PAUSIERT = "pausiert", "Pausiert"
    ABGESCHLOSSEN = "abgeschlossen", "Abgeschlossen"


class LinkType(models.TextChoices):
    BEZIEHT_SICH_AUF = "bezieht_sich_auf", "Bezieht sich auf"
    RECHNUNG_ZU_LEISTUNG = "rechnung_zu_leistung", "Rechnung ↔ Leistungsnachweis"
    ERSETZT = "ersetzt", "Ersetzt"
    ANLAGE_ZU = "anlage_zu", "Anlage zu"


class EventType(models.TextChoices):
    ERSTELLT = "erstellt", "Erstellt"
    VERSION_NEU = "version_neu", "Neue Version"
    VERSCHOBEN = "verschoben", "Verschoben / umbenannt"
    KLASSIFIZIERT = "klassifiziert", "Klassifiziert"
    OWNER_GEAENDERT = "owner_geaendert", "Owner geändert"
    METADATEN = "metadaten", "Metadaten geändert"
    ARCHIVIERT = "archiviert", "Archiviert (Papierkorb)"
    WIEDERHERGESTELLT = "wiederhergestellt", "Wiederhergestellt"
    ENDG_GELOESCHT = "endgueltig_geloescht", "Endgültig gelöscht"


class SyncTrigger(models.TextChoices):
    CRON = "cron", "Zeitplan"
    MANUELL = "manuell", "Manuell"


class SyncStatus(models.TextChoices):
    LAEUFT = "laeuft", "Läuft"
    OK = "ok", "OK"
    FEHLER = "fehler", "Fehler"


# =============================================================================
#  KONFIGURATION — DocTypes, Tags, Metadaten-Schema
# =============================================================================

class DmsDocType(models.Model):
    """Kategorie eines Dokuments + Aufbewahrungs-Vorgabe + Ablageregel.
    Vorbild: Mayan DocumentType (trash/delete time) + Paperless StoragePath."""

    key = models.SlugField(
        max_length=64, unique=True,
        help_text="Stabiler Schlüssel, z. B. 'vertrag', 'rechnung'."
    )
    label = models.CharField(max_length=128)
    description = models.TextField(blank=True)

    # Aufbewahrung (GoBD) — editierbar, weil sich Recht ändert (BEG IV: 10->8 J.)
    retention_years = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Gesetzliche Mindest-Aufbewahrung in Jahren. Leer = unbegrenzt/keine."
    )
    delete_after_days = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Gnadenfrist nach Fristablauf, bevor endgültig löschbar."
    )

    # Ablage
    default_volume = models.CharField(
        max_length=8, choices=StorageVolume.choices, default=StorageVolume.OFFICE
    )
    path_template = models.CharField(
        max_length=255, blank=True,
        help_text="Pfad-Template unter der abpe/-Wurzel, "
                  "z. B. '{owner_bucket}/{owner_slug}/Vertraege'."
    )

    # UI / Sortierung
    icon_class = models.CharField(
        max_length=64, blank=True,
        help_text="CSS-Klasse für das Datei-Icon, z. B. 'crm-doc-contract'."
    )
    sort_order = models.PositiveIntegerField(default=100)
    is_system = models.BooleanField(
        default=False, help_text="Systemtyp — vor Löschen geschützt."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "DMS-Dokumenttyp"
        verbose_name_plural = "DMS-Dokumenttypen"
        ordering = ("sort_order", "label")

    def __str__(self):
        return self.label


class DmsTag(models.Model):
    """Schlagwort. Posteingang-Markierung + optionale Auto-Klassifikation."""

    label = models.CharField(max_length=128, unique=True)
    slug = models.SlugField(max_length=128, unique=True)
    color = models.CharField(max_length=16, default="#163258")

    is_inbox_tag = models.BooleanField(
        default=False,
        help_text="Markiert frisch eingegangene, noch nicht abgelegte Dokumente."
    )
    is_system = models.BooleanField(default=False)

    # Auto-Klassifikation (Paperless-Muster), AUTO = Deepseek
    match = models.CharField(max_length=256, blank=True)
    matching_algorithm = models.PositiveSmallIntegerField(
        choices=MatchingAlgorithm.choices, default=MatchingAlgorithm.NONE
    )
    is_insensitive = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "DMS-Tag"
        verbose_name_plural = "DMS-Tags"
        ordering = ("label",)

    def __str__(self):
        return self.label


class DmsMetadataType(models.Model):
    """Definition eines flexiblen Metadaten-Feldes (EAV). Vorbild: Mayan."""

    name = models.SlugField(max_length=64, unique=True)
    label = models.CharField(max_length=128)
    default = models.CharField(max_length=255, blank=True)
    validation = models.CharField(
        max_length=128, blank=True,
        help_text="Optionaler Validierungs-Backend (Dotted-Path)."
    )
    parser = models.CharField(max_length=128, blank=True)
    help_text = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "DMS-Metadatentyp"
        verbose_name_plural = "DMS-Metadatentypen"
        ordering = ("label",)

    def __str__(self):
        return self.label


class DmsDocTypeMetadata(models.Model):
    """Welche Metadaten-Felder ein DocType führt (+ Pflicht-Flag)."""

    doctype = models.ForeignKey(
        DmsDocType, on_delete=models.CASCADE, related_name="metadata_fields"
    )
    metadata_type = models.ForeignKey(
        DmsMetadataType, on_delete=models.CASCADE, related_name="doctype_links"
    )
    required = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=100)

    class Meta:
        verbose_name = "DocType-Metadatenfeld"
        verbose_name_plural = "DocType-Metadatenfelder"
        ordering = ("sort_order",)
        constraints = [
            models.UniqueConstraint(
                fields=("doctype", "metadata_type"),
                name="uq_doctype_metadata"
            )
        ]


# =============================================================================
#  GEWERK — zentrale Gruppierungs-Klammer (Kunde + n Berater + n Dokumente)
# =============================================================================

class DmsGewerk(models.Model):
    """Ein Auftrag/Projekt beim Kunden, an dem mehrere Berater arbeiten.
    Klammert Leistungsnachweise, Eingangs- und Ausgangsrechnungen zusammen."""

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    nummer = models.CharField(
        max_length=64, unique=True, help_text="Gewerk-/Projektnummer."
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    account_crm_id = models.CharField(
        max_length=64, db_index=True, help_text="Kunde (CrmAccount.crm_id)."
    )

    status = models.CharField(
        max_length=16, choices=GewerkStatus.choices, default=GewerkStatus.AKTIV
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Gewerk"
        verbose_name_plural = "Gewerke"
        ordering = ("-start_date", "nummer")
        indexes = [
            models.Index(fields=("account_crm_id",), name="idx_gewerk_account"),
            models.Index(fields=("status",), name="idx_gewerk_status"),
        ]

    def __str__(self):
        return f"{self.nummer} · {self.title}"


class DmsGewerkBerater(models.Model):
    """n:m — welche Berater am Gewerk mitarbeiten (+ Zeitraum/Rolle)."""

    gewerk = models.ForeignKey(
        DmsGewerk, on_delete=models.CASCADE, related_name="berater"
    )
    contact_crm_id = models.CharField(
        max_length=64, db_index=True, help_text="Berater (CrmContact.crm_id)."
    )
    role = models.CharField(max_length=64, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Gewerk-Berater"
        verbose_name_plural = "Gewerk-Berater"
        constraints = [
            models.UniqueConstraint(
                fields=("gewerk", "contact_crm_id"),
                name="uq_gewerk_berater"
            )
        ]


# =============================================================================
#  DOKUMENT — logischer Kern (Mayan Document) + Lifecycle + Volltext
# =============================================================================

class CrmDocument(models.Model):
    """Das logische Dokument. Die physische(n) Datei(en) hängen als
    CrmDocumentVersion dran. Eigentum n:m über CrmDocumentOwner."""

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    doctype = models.ForeignKey(
        DmsDocType, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="documents"
    )
    gewerk = models.ForeignKey(
        DmsGewerk, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="documents",
        help_text="Optional — gruppiert Leistungsnachweise & Rechnungen."
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Eingang/Ausgang — für Rechnungen & Leistungsnachweise zentral
    direction = models.CharField(
        max_length=8, choices=DocDirection.choices, default=DocDirection.KEINE
    )

    # --- Zwei Uhren -----------------------------------------------------------
    document_date = models.DateField(
        null=True, blank=True,
        help_text="Dokumentdatum — Anker für die Aufbewahrungsberechnung."
    )
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(
        null=True, blank=True, help_text="Geschäfts-Gültigkeit (z. B. Vertragsende)."
    )
    retention_years_override = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Übersteuert die DocType-Frist für dieses eine Dokument."
    )
    retention_until = models.DateField(
        null=True, blank=True, db_index=True,
        help_text="Berechnetes Ende der Aufbewahrungspflicht (Jahresende)."
    )
    status = models.CharField(
        max_length=16, choices=DocStatus.choices, default=DocStatus.GUELTIG
    )

    # --- Posteingang / Stub ---------------------------------------------------
    is_stub = models.BooleanField(
        default=False, help_text="Platzhalter für angefordertes, noch fehlendes Dok."
    )
    needs_review = models.BooleanField(
        default=False, db_index=True,
        help_text="Im Posteingang — noch nicht final zugeordnet."
    )

    # --- Archiv / Soft-Delete -------------------------------------------------
    in_trash = models.BooleanField(default=False, db_index=True)
    trashed_at = models.DateTimeField(null=True, blank=True)
    trashed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )
    trashed_reason = models.CharField(max_length=255, blank=True)

    # --- Herkunft & Volltext --------------------------------------------------
    source = models.CharField(
        max_length=16, choices=DocSource.choices, default=DocSource.HOCHGELADEN
    )
    language = models.CharField(max_length=8, default="de")
    content = models.TextField(
        blank=True,
        help_text="Extrahierter/OCR-Text — Quelle für den Elasticsearch-Index."
    )

    tags = models.ManyToManyField(
        DmsTag, through="DmsDocumentTag", related_name="documents", blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "Dokument"
        verbose_name_plural = "Dokumente"
        ordering = ("-document_date", "-created_at")
        indexes = [
            models.Index(fields=("doctype",), name="idx_doc_doctype"),
            models.Index(fields=("gewerk",), name="idx_doc_gewerk"),
            models.Index(fields=("direction",), name="idx_doc_direction"),
            models.Index(fields=("in_trash", "needs_review"), name="idx_doc_state"),
            models.Index(fields=("retention_until",), name="idx_doc_retention"),
            models.Index(fields=("document_date",), name="idx_doc_date"),
        ]

    def __str__(self):
        return self.title

    # Hinweis: retention_until wird in services/lifecycle.py berechnet
    # (document_date + retention_years, aufgerundet auf 31.12.) und beim
    # Speichern gesetzt — nicht von Hand gepflegt.


class CrmDocumentOwner(models.Model):
    """n:m — ein Dokument kann mehreren Beratern UND einem Kunden gehören
    (z. B. Firmen-Rahmenvertrag). Owner-Schlüssel ist die kanonische crm_id."""

    document = models.ForeignKey(
        CrmDocument, on_delete=models.CASCADE, related_name="owners"
    )
    owner_crm_id = models.CharField(max_length=64, db_index=True)
    owner_type = models.CharField(max_length=8, choices=OwnerType.choices)
    role = models.CharField(
        max_length=16, choices=OwnerRole.choices, default=OwnerRole.PRIMAER
    )
    is_primary = models.BooleanField(default=False)
    is_suggestion = models.BooleanField(
        default=False, db_index=True,
        help_text="Unsicherer Match — muss bestätigt werden",
    )
    match_source = models.CharField(
        max_length=16, blank=True, default="",
        help_text="Wie der Match kam (exact/normalized/substring/path/manual)",
    )

    added_at = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "Dokument-Eigentümer"
        verbose_name_plural = "Dokument-Eigentümer"
        constraints = [
            models.UniqueConstraint(
                fields=("document", "owner_crm_id", "owner_type"),
                name="uq_document_owner"
            )
        ]
        indexes = [
            models.Index(
                fields=("owner_crm_id", "owner_type"), name="idx_owner_lookup"
            ),
        ]

    def __str__(self):
        return f"{self.owner_type}:{self.owner_crm_id} → {self.document_id}"


class CrmDocumentVersion(models.Model):
    """Eine physische Datei-Generation auf Samba. Genau eine ist is_active;
    ältere wandern via in_trash ins Archiv. Vorbild: Mayan DocumentFile."""

    document = models.ForeignKey(
        CrmDocument, on_delete=models.CASCADE, related_name="versions"
    )
    version_no = models.PositiveIntegerField(default=1)

    # --- Ablageort (die Wahrheit) --------------------------------------------
    volume = models.CharField(max_length=8, choices=StorageVolume.choices)
    relative_path = models.CharField(
        max_length=1024,
        help_text="Pfad innerhalb des Shares — maßgeblich für den Datei-Zugriff."
    )
    filename = models.CharField(
        max_length=512,
        help_text="Dateiname — behält Original-/Erzeuger-Name (vgl. CrmCallRecording)."
    )

    # --- Datei-Metadaten ------------------------------------------------------
    mimetype = models.CharField(max_length=128, blank=True)
    encoding = models.CharField(max_length=64, blank=True)
    size_bytes = models.BigIntegerField(default=0)
    checksum = models.CharField(
        max_length=128, blank=True, db_index=True,
        help_text="Hash der Datei — Dedup & Integritätsprüfung."
    )
    checksum_algo = models.CharField(max_length=16, default="sha256")
    page_count = models.PositiveIntegerField(null=True, blank=True)

    # --- Zustand --------------------------------------------------------------
    is_active = models.BooleanField(default=True, db_index=True)
    in_trash = models.BooleanField(default=False)
    trashed_at = models.DateTimeField(null=True, blank=True)
    replaced_by = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="replaces"
    )
    comment = models.CharField(
        max_length=255, blank=True, help_text="Grund/Notiz, z. B. 'ersetzt durch v3'."
    )

    # --- Sync-Herkunft (Scanner) ---------------------------------------------
    source_path_original = models.CharField(
        max_length=1024, blank=True,
        help_text="Ursprünglicher Fundort beim Samba-Scan (Abgleich/Reconcile)."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "Dokument-Version"
        verbose_name_plural = "Dokument-Versionen"
        ordering = ("document", "-version_no")
        constraints = [
            models.UniqueConstraint(
                fields=("document", "version_no"), name="uq_document_version"
            )
        ]
        indexes = [
            models.Index(fields=("volume", "relative_path"), name="idx_version_path"),
        ]

    def __str__(self):
        return f"{self.document_id} v{self.version_no}"


# =============================================================================
#  METADATEN-WERTE, TAG-VERKNÜPFUNG, DOKUMENT-LINKS
# =============================================================================

class DmsDocumentMetadata(models.Model):
    """EAV-Wert eines Metadaten-Feldes an einem Dokument."""

    document = models.ForeignKey(
        CrmDocument, on_delete=models.CASCADE, related_name="metadata"
    )
    metadata_type = models.ForeignKey(
        DmsMetadataType, on_delete=models.CASCADE, related_name="values"
    )
    value = models.CharField(max_length=512, blank=True)

    class Meta:
        verbose_name = "Dokument-Metadatum"
        verbose_name_plural = "Dokument-Metadaten"
        constraints = [
            models.UniqueConstraint(
                fields=("document", "metadata_type"), name="uq_document_metadata"
            )
        ]


class DmsDocumentTag(models.Model):
    """Through-Tabelle Dokument <-> Tag (wer/wann gesetzt)."""

    document = models.ForeignKey(CrmDocument, on_delete=models.CASCADE)
    tag = models.ForeignKey(DmsTag, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("document", "tag"), name="uq_document_tag"
            )
        ]


class DmsDocumentLink(models.Model):
    """LOSE Verknüpfung Dokument <-> Dokument, ohne 1:1-Zwang.
    Trägt das Szenario 'Ausgangsrechnung bezieht sich auf n Eingangs-LN'."""

    source_document = models.ForeignKey(
        CrmDocument, on_delete=models.CASCADE, related_name="links_out"
    )
    target_document = models.ForeignKey(
        CrmDocument, on_delete=models.CASCADE, related_name="links_in"
    )
    link_type = models.CharField(
        max_length=24, choices=LinkType.choices, default=LinkType.BEZIEHT_SICH_AUF
    )
    note = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "Dokument-Verknüpfung"
        verbose_name_plural = "Dokument-Verknüpfungen"
        constraints = [
            models.UniqueConstraint(
                fields=("source_document", "target_document", "link_type"),
                name="uq_document_link"
            )
        ]


# =============================================================================
#  PROTOKOLLE — Audit (GoBD) & Scanner-Läufe
# =============================================================================

class DmsDocumentEvent(models.Model):
    """Audit-Trail. Wichtig für GoBD: wer hat wann archiviert/wiederhergestellt/
    endgültig gelöscht. Von Tag 1 dabei, weil nachrüsten teuer ist."""

    document = models.ForeignKey(
        CrmDocument, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="events"
    )
    document_uuid = models.UUIDField(
        null=True, blank=True,
        help_text="Bewahrt die Referenz auch nach endgültigem Löschen."
    )
    event_type = models.CharField(max_length=24, choices=EventType.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )
    actor_label = models.CharField(
        max_length=64, blank=True, help_text="Z. B. 'scanner', 'cron', 'deepseek'."
    )
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    detail = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Dokument-Ereignis"
        verbose_name_plural = "Dokument-Ereignisse"
        ordering = ("-timestamp",)
        indexes = [
            models.Index(fields=("event_type",), name="idx_event_type"),
        ]


class DmsSyncRun(models.Model):
    """Protokoll eines Samba->DB-Scans. Speist Steuerungs-Status & Aktivitäts-Report."""

    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    volume = models.CharField(
        max_length=8, choices=StorageVolume.choices, null=True, blank=True
    )

    files_seen = models.PositiveIntegerField(default=0)
    files_new = models.PositiveIntegerField(default=0)
    files_updated = models.PositiveIntegerField(default=0)
    files_removed = models.PositiveIntegerField(default=0)
    documents_indexed = models.PositiveIntegerField(default=0)

    status = models.CharField(
        max_length=8, choices=SyncStatus.choices, default=SyncStatus.LAEUFT
    )
    triggered_by = models.CharField(
        max_length=8, choices=SyncTrigger.choices, default=SyncTrigger.CRON
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )
    message = models.TextField(blank=True)

    class Meta:
        verbose_name = "Sync-Lauf"
        verbose_name_plural = "Sync-Läufe"
        ordering = ("-started_at",)

    def __str__(self):
        return f"Sync {self.started_at:%Y-%m-%d %H:%M} [{self.status}]"


# =============================================================================
#  OPTIONAL / VORGESEHEN — Arbeitspaket-Positionen (jetzt leer lassbar)
#  Additiv erweiterbar; Kerntabellen oben müssen dafür NICHT migriert werden.
#  Aktivieren, sobald Eingang/Ausgang strukturiert abgeglichen werden soll.
# =============================================================================

class DmsArbeitspaket(models.Model):
    """Arbeitspaket innerhalb eines Gewerks (AP1, AP2, ...)."""

    gewerk = models.ForeignKey(
        DmsGewerk, on_delete=models.CASCADE, related_name="arbeitspakete"
    )
    key = models.CharField(max_length=32, help_text="z. B. 'AP1'.")
    label = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=32, blank=True, help_text="z. B. 'Tag', 'Stück'.")
    sort_order = models.PositiveIntegerField(default=100)

    class Meta:
        verbose_name = "Arbeitspaket"
        verbose_name_plural = "Arbeitspakete"
        ordering = ("gewerk", "sort_order", "key")
        constraints = [
            models.UniqueConstraint(
                fields=("gewerk", "key"), name="uq_gewerk_arbeitspaket"
            )
        ]

    def __str__(self):
        return f"{self.key} · {self.label}"


class DmsLeistungsposition(models.Model):
    """Eine Positionszeile aus einem Leistungsnachweis oder einer Rechnung.
    Ermöglicht später: Summe Eingang AP1 vs. Ausgang AP1, Margen, Fehlt-Prüfung."""

    document = models.ForeignKey(
        CrmDocument, on_delete=models.CASCADE, related_name="positionen"
    )
    arbeitspaket = models.ForeignKey(
        DmsArbeitspaket, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="positionen"
    )
    direction = models.CharField(
        max_length=8, choices=DocDirection.choices, default=DocDirection.KEINE,
        help_text="Eingang (Berater->abcona) oder Ausgang (abcona->Kunde)."
    )
    owner_crm_id = models.CharField(
        max_length=64, blank=True, db_index=True,
        help_text="Berater der Eingangs-Position (für Summen je Berater)."
    )

    beschreibung = models.CharField(max_length=512, blank=True)
    menge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    einheit = models.CharField(max_length=32, blank=True)
    einzelpreis = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    betrag = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Leistungsposition"
        verbose_name_plural = "Leistungspositionen"
        indexes = [
            models.Index(fields=("direction",), name="idx_pos_direction"),
            models.Index(fields=("arbeitspaket",), name="idx_pos_ap"),
        ]

