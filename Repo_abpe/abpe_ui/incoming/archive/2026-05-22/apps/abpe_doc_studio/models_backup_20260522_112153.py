"""
ABpE Doc Studio — Models
========================
Generischer Word/PDF Generator mit 4-Ebenen-Baukasten.

Abgeleitet aus realen Vorlagen-Analysen (Mai 2026):
  - Rahmenvertrag (5 Seiten, 12 Paragraphen, 1 Signaturtabelle)
  - Sub-Dienstvertrag (3 Seiten, 5 Label-Tabellen, Signaturtabelle)
  - Rechnung Zeitaufwand (1 Seite, 5-spaltige Positionstabelle)
  - Rechnung Arbeitspakete (2 Seiten, 21 AP-Positionen, auto page-break)

Architektur:
  Ebene 1 — PageLayout     : Seitenformat, Margins, Header/Footer-Slots
  Ebene 2 — StyleKit        : Abcona CD, alle Formatierungen, DB-gesteuert
  Ebene 3 — ContentBlock    : Wiederverwendbare Bausteine
  Ebene 4 — VariableEngine  : Serienbrief-API, {var} + {liste[]}

Zentrale Python-API:
  from apps.abpe_doc_studio.api import DocStudio
  DocStudio.generate(template='sub_dienstvertrag', context_ref='ANF-2026-0042')
"""
import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


# ── Konstanten ────────────────────────────────────────────────────────────────

class DocEngine(models.TextChoices):
    DOCX = 'DOCX', 'Word Dokument (.docx)'
    PDF  = 'PDF',  'PDF via LibreOffice'
    BOTH = 'BOTH', 'DOCX + PDF'


class DocStatus(models.TextChoices):
    DRAFT   = 'DRAFT',   'Entwurf'
    ACTIVE  = 'ACTIVE',  'Aktiv'
    ARCHIVE = 'ARCHIVE', 'Archiv'


class DocScope(models.TextChoices):
    CONTRACT = 'contract', 'Verträge (Rahmen/Sub)'
    INVOICE  = 'invoice',  'Rechnungen'
    OFFER    = 'offer',    'Angebote'
    PORTAL   = 'portal',   'Portal / System'
    GENERAL  = 'general',  'Allgemein'


class BlockType(models.TextChoices):
    # Layout-Blöcke
    LOGO         = 'LOGO',         'Logo'
    PAGE_HEADER  = 'PAGE_HEADER',  'Seitenkopf'
    PAGE_FOOTER  = 'PAGE_FOOTER',  'Seitenfuß'
    PAGE_BREAK   = 'PAGE_BREAK',   'Seitenumbruch'
    SEPARATOR    = 'SEPARATOR',    'Trennlinie'
    # Text-Blöcke
    DOC_TITLE    = 'DOC_TITLE',    'Dokumenttitel'
    SECTION_HEAD = 'SECTION_HEAD', 'Abschnittsüberschrift'
    PARAGRAPH    = 'PARAGRAPH',    'Fließtext-Absatz'
    LABEL_VALUE  = 'LABEL_VALUE',  'Label + Wert (2-spaltig)'
    # Vertrags-Blöcke
    PARTY_BLOCK  = 'PARTY_BLOCK',  'Vertragspartei-Block'
    CLAUSE       = 'CLAUSE',       'Vertragsklausel §'
    SIGNATURE    = 'SIGNATURE',    'Signatur-Tabelle'
    # Rechnungs-Blöcke
    INV_HEADER   = 'INV_HEADER',   'Rechnungskopf 2-spaltig'
    INV_META     = 'INV_META',     'Rechnungs-Metadaten'
    INV_SUBJECT  = 'INV_SUBJECT',  'Betreff / Beratungsleistung'
    TIME_TABLE   = 'TIME_TABLE',   'Positionen Zeitaufwand'
    AP_TABLE     = 'AP_TABLE',     'Positionen Arbeitspakete'
    TOTAL_BLOCK  = 'TOTAL_BLOCK',  'Summen-Block (Netto/MwSt/Brutto)'
    CLOSING      = 'CLOSING',      'Grußformel + Unterschrift'


class StyleType(models.TextChoices):
    TEXT      = 'TEXT',      'Textformat'
    TABLE     = 'TABLE',     'Tabellenformat'
    COLOR     = 'COLOR',     'Farbpalette'
    LINE      = 'LINE',      'Linienformat'
    IMAGE     = 'IMAGE',     'Bildformat'
    PAGE      = 'PAGE',      'Seitenformat'


class LogStatus(models.TextChoices):
    OK      = 'OK',      'Erfolgreich'
    FAILED  = 'FAILED',  'Fehlgeschlagen'
    QUEUED  = 'QUEUED',  'In Warteschlange'


class QueueStatus(models.TextChoices):
    PENDING   = 'PENDING',   'Ausstehend'
    RUNNING   = 'RUNNING',   'Läuft'
    DONE      = 'DONE',      'Erledigt'
    FAILED    = 'FAILED',    'Fehlgeschlagen'
    CANCELLED = 'CANCELLED', 'Abgebrochen'


# ════════════════════════════════════════════════════════════════════════════
# EBENE 1 — PAGE LAYOUT
# ════════════════════════════════════════════════════════════════════════════

class PageLayout(models.Model):
    """
    Seitenstruktur — entspricht dem base.html in Django.
    Definiert A4-Format, Margins, Header/Footer-Slots, Spaltigkeit.

    Aus Dokumentenanalyse:
      Verträge:   Margin L/R 3.0/3.0cm, T/B 4.2/5.2cm
      Rechnungen: Margin L/R 2.5/2.5cm, T/B 2.5/2.0cm
    """
    identifier   = models.SlugField(max_length=100, unique=True,
                                    verbose_name='Bezeichner',
                                    help_text='z.B. "a4_vertraege" oder "a4_rechnung"')
    name         = models.CharField(max_length=200, verbose_name='Anzeigename')
    description  = models.TextField(blank=True)

    # Seitenformat
    page_width_cm  = models.FloatField(default=21.0,  verbose_name='Breite cm')
    page_height_cm = models.FloatField(default=29.7,  verbose_name='Höhe cm')

    # Margins — aus realen Dokumenten extrahiert
    margin_left_cm   = models.FloatField(default=3.0, verbose_name='Rand links cm')
    margin_right_cm  = models.FloatField(default=3.0, verbose_name='Rand rechts cm')
    margin_top_cm    = models.FloatField(default=4.2, verbose_name='Rand oben cm')
    margin_bottom_cm = models.FloatField(default=5.2, verbose_name='Rand unten cm')
    header_distance_cm = models.FloatField(default=1.5, verbose_name='Header-Abstand cm')

    # Slots — JSON-Liste der verfügbaren Block-Positionen
    # z.B. ["logo", "header_left", "header_right", "body", "footer_impressum", "footer_bank"]
    slot_order   = models.JSONField(
        default=list, blank=True,
        verbose_name='Slot-Reihenfolge',
        help_text='["logo","body","signature","footer_impressum","footer_bank"]'
    )

    # Spaltigkeit
    columns      = models.PositiveSmallIntegerField(default=1,
                                                     verbose_name='Spalten')
    column_widths_cm = models.JSONField(
        default=list, blank=True,
        verbose_name='Spaltenbreiten cm',
        help_text='[15.0] oder [7.5, 7.5] für 2-spaltig'
    )

    # Seitennummerierung
    show_page_numbers = models.BooleanField(default=True)
    page_number_format = models.CharField(
        max_length=50, default='Seite {page} von {total}',
        verbose_name='Format',
        help_text='Seite {page} von {total}'
    )
    page_number_position = models.CharField(
        max_length=20, default='top_right',
        choices=[('top_right','Oben rechts'),('top_center','Oben Mitte'),
                 ('bottom_right','Unten rechts'),('bottom_center','Unten Mitte')]
    )

    is_active    = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name} ({self.margin_left_cm}/{self.margin_right_cm}cm)'

    class Meta:
        verbose_name        = 'Seiten-Layout'
        verbose_name_plural = 'Seiten-Layouts'
        ordering            = ['name']


# ════════════════════════════════════════════════════════════════════════════
# EBENE 2 — STYLE KIT
# ════════════════════════════════════════════════════════════════════════════

class StyleKit(models.Model):
    """
    Sammlung von Formatierungen — das Abcona Corporate Design in der DB.
    Ein StyleKit ist eine benannte Gruppe von Styles.

    Aus Dokumentenanalyse extrahiert:
      - brand_blue: #163258 (Überschriften, Labels, Linien)
      - text_dark:  #1A1A1A (Fließtext)
      - text_gray:  #888888 (Sekundärtext, Stempel-Hinweise)
      - Font: Arial (Verträge) / Helvetica (Rechnungen) → vereinheitlicht auf Arial
    """
    identifier  = models.SlugField(max_length=100, unique=True,
                                   help_text='z.B. "abcona_standard"')
    name        = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_default  = models.BooleanField(default=False)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.is_default:
            StyleKit.objects.exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name        = 'Style-Kit'
        verbose_name_plural = 'Style-Kits'


class StyleDefinition(models.Model):
    """
    Einzelne Formatdefinition innerhalb eines StyleKits.
    Referenziert via style_key in ContentBlocks.

    Bekannte Keys aus Dokumentenanalyse:
      doc_title      → Arial 16pt Bold #1A1A1A
      section_head   → Arial 12pt Bold #163258 + Unterlinie
      sub_section    → Arial 10pt Bold #163258
      body_text      → Arial 10pt #1A1A1A, Blocksatz, Zeilenabstand 1.15
      party_bold     → Arial 10pt Bold #1A1A1A (Vertragspartei)
      party_italic   → Arial 10pt Bold Italic #1A1A1A (Firma-Name)
      label_blue     → Arial 10pt Bold #163258 (Tabellen-Labels Sub-Vertrag)
      footer_text    → Arial 8pt #1A1A1A
      inv_rgnr       → Helvetica/Arial 11pt Bold #163258 (Rg-Nummer)
      inv_subject    → 10pt Bold #163258
      inv_body       → 8pt #1A1A1A
      table_header   → 10pt Bold White, Hintergrund #163258
      table_body     → 9pt #1A1A1A
      total_row      → 10pt Bold White, Hintergrund #163258
      sig_label      → 10pt Bold #1A1A1A
      sig_hint       → 9pt #888888 (Stempel/Unterschrift)
    """
    style_kit    = models.ForeignKey(StyleKit, on_delete=models.CASCADE,
                                     related_name='definitions')
    style_key    = models.SlugField(max_length=100,
                                    verbose_name='Style-Key',
                                    help_text='z.B. "section_head", "body_text"')
    style_type   = models.CharField(max_length=20, choices=StyleType.choices,
                                    default=StyleType.TEXT)
    name         = models.CharField(max_length=200, verbose_name='Anzeigename')

    # Text-Formatierung
    font_family  = models.CharField(max_length=100, default='Arial',
                                    verbose_name='Schriftart')
    font_size_pt = models.FloatField(default=10.0, verbose_name='Schriftgröße pt')
    bold         = models.BooleanField(default=False)
    italic       = models.BooleanField(default=False)
    underline    = models.BooleanField(default=False)
    color_hex    = models.CharField(max_length=10, default='1A1A1A',
                                    verbose_name='Textfarbe (Hex ohne #)')

    # Absatz-Formatierung
    alignment    = models.CharField(
        max_length=20, default='left',
        choices=[('left','Links'),('right','Rechts'),
                 ('center','Zentriert'),('justify','Blocksatz')]
    )
    space_before_pt = models.FloatField(default=0.0, verbose_name='Abstand vor pt')
    space_after_pt  = models.FloatField(default=6.0, verbose_name='Abstand nach pt')
    line_spacing    = models.FloatField(default=1.15, verbose_name='Zeilenabstand')
    indent_left_cm  = models.FloatField(default=0.0, verbose_name='Einzug links cm')

    # Rahmen-Linien (für section_head Unterlinie)
    border_bottom       = models.BooleanField(default=False)
    border_bottom_color = models.CharField(max_length=10, default='163258',
                                           verbose_name='Linienfarbe (Hex)')
    border_bottom_pt    = models.FloatField(default=0.5, verbose_name='Liniendicke pt')
    border_bottom_style = models.CharField(
        max_length=20, default='single',
        choices=[('single','Einfach'),('dashed','Gestrichelt'),('thick','Dick')]
    )

    # Tabellen-Formatierung (nur wenn style_type=TABLE)
    table_header_bg_hex    = models.CharField(max_length=10, blank=True, default='163258')
    table_header_text_hex  = models.CharField(max_length=10, blank=True, default='FFFFFF')
    table_row_alt_bg_hex   = models.CharField(max_length=10, blank=True, default='F8FAFC')
    table_border_color_hex = models.CharField(max_length=10, blank=True, default='E5E7EB')
    table_border_pt        = models.FloatField(default=0.5)

    # Hintergrundfarbe (für total_row, highlight)
    bg_color_hex = models.CharField(max_length=10, blank=True, default='',
                                     verbose_name='Hintergrundfarbe (leer=transparent)')

    class Meta:
        verbose_name        = 'Style-Definition'
        verbose_name_plural = 'Style-Definitionen'
        unique_together     = ['style_kit', 'style_key']
        ordering            = ['style_kit', 'style_key']

    def __str__(self):
        return f'{self.style_kit.identifier}.{self.style_key}'


# ════════════════════════════════════════════════════════════════════════════
# EBENE 3 — CONTENT BLOCKS
# ════════════════════════════════════════════════════════════════════════════

class ContentBlock(models.Model):
    """
    Wiederverwendbarer Baustein.
    Referenziert StyleDefinitions via style_key.
    Inhalt kann statischen Text UND {variablen} enthalten.
    Listen: {positionen[]} → wird zu Tabellenzeilen expandiert.

    Syntax:
      Einfache Variable:  {berater_name}
      Liste für Tabelle:  {positionen[]}  mit columns-Definition
      Bedingt:            {{if:mwst_pflichtig}} ... {{endif}}
      Block einbetten:    {{block:footer_impressum}}
    """
    identifier   = models.SlugField(max_length=150, unique=True,
                                    verbose_name='Block-Identifier')
    name         = models.CharField(max_length=200, verbose_name='Anzeigename')
    block_type   = models.CharField(max_length=30, choices=BlockType.choices,
                                    verbose_name='Block-Typ')
    description  = models.TextField(blank=True)

    # Style-Referenz
    style_kit    = models.ForeignKey(StyleKit, on_delete=models.PROTECT,
                                     related_name='blocks',
                                     verbose_name='Style-Kit')
    style_key    = models.CharField(max_length=100, blank=True,
                                    verbose_name='Style-Key',
                                    help_text='Referenz auf StyleDefinition.style_key')

    # Inhalt — Text mit Variablen-Platzhaltern
    # Für CLAUSE-Blöcke: vollständiger Paragraphen-Text (§1 Gegenstand des Vertrages...)
    # Für LABEL_VALUE: "Leistungsbeschreibung:" | "{leistungsbeschreibung}"
    content      = models.TextField(blank=True, verbose_name='Inhalt',
                                    help_text='Statischer Text mit {variablen}-Platzhaltern')

    # Tabellen-Konfiguration (für TIME_TABLE, AP_TABLE, LABEL_VALUE)
    columns      = models.JSONField(
        default=list, blank=True,
        verbose_name='Spalten-Definition',
        help_text='''
        Für TIME_TABLE:
        [
          {"key": "pos_nr",    "label": "Pos.-Nr.", "width_pct": 8,  "align": "left",  "style_key": "table_header"},
          {"key": "zeitraum",  "label": "Zeitraum", "width_pct": 22, "align": "left"},
          {"key": "stunden",   "label": "Stunden",  "width_pct": 14, "align": "right"},
          {"key": "satz_euro", "label": "Stundensatz in €", "width_pct": 28, "align": "right"},
          {"key": "betrag",    "label": "Betrag in €",      "width_pct": 28, "align": "right"}
        ]

        Für AP_TABLE:
        [
          {"key": "ap_nr",        "label": "AP",           "width_pct": 6},
          {"key": "beschreibung", "label": "Arbeitspakete-Beschreibung", "width_pct": 46},
          {"key": "anzahl",       "label": "Anzahl",  "width_pct": 12, "align": "right"},
          {"key": "preis_euro",   "label": "Preis in €",   "width_pct": 18, "align": "right"},
          {"key": "betrag_euro",  "label": "Betrag in €",  "width_pct": 18, "align": "right"}
        ]
        '''
    )

    # Variablen, die dieser Block erwartet
    expected_variables = models.JSONField(
        default=list, blank=True,
        verbose_name='Erwartete Variablen',
        help_text='[{"name": "stundensatz", "type": "currency", "required": true}]'
    )

    # Wiederholung / Bedingung
    repeatable   = models.BooleanField(default=False,
                                        verbose_name='Wiederholbar',
                                        help_text='True bei Tabellenzeilen-Blöcken')
    conditional  = models.CharField(max_length=200, blank=True,
                                     verbose_name='Bedingung',
                                     help_text='Variable die true sein muss, z.B. "mwst_pflichtig"')

    is_active    = models.BooleanField(default=True)
    created_by   = models.ForeignKey(User, on_delete=models.SET_NULL,
                                     null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name} [{self.identifier}]'

    class Meta:
        verbose_name        = 'Content-Block'
        verbose_name_plural = 'Content-Blöcke'
        ordering            = ['block_type', 'name']
        indexes             = [models.Index(fields=['identifier'])]


# ════════════════════════════════════════════════════════════════════════════
# DOKUMENT-TEMPLATE (Zusammenstellung aller 4 Ebenen)
# ════════════════════════════════════════════════════════════════════════════

class DocTemplate(models.Model):
    """
    Vollständige Vorlage — kombiniert Layout + StyleKit + Blöcke.
    Definiert welche ContentBlocks in welcher Reihenfolge zusammengebaut werden.

    Vordefinierte Templates (aus Vorlagen-Analyse):
      rahmenvertrag          → 5 Seiten, 12 Klauseln, 1 Signatur
      sub_dienstvertrag      → 3 Seiten, Leistungs-/Vergütungs-/Laufzeittabellen
      rechnung_zeitaufwand   → 1 Seite, 5-spaltige Positionstabelle
      rechnung_arbeitspakete → 2 Seiten, AP-Tabelle mit auto page-break
    """
    identifier   = models.SlugField(max_length=200, unique=True,
                                    verbose_name='Technischer Name',
                                    help_text='z.B. "sub_dienstvertrag" — für DocStudio.generate()')
    name         = models.CharField(max_length=200, verbose_name='Anzeigename')
    description  = models.TextField(blank=True)
    scope        = models.CharField(max_length=30, choices=DocScope.choices,
                                    default=DocScope.CONTRACT, verbose_name='Bereich')
    engine       = models.CharField(max_length=10, choices=DocEngine.choices,
                                    default=DocEngine.BOTH, verbose_name='Format')
    status       = models.CharField(max_length=20, choices=DocStatus.choices,
                                    default=DocStatus.DRAFT, verbose_name='Status')

    # Verknüpfungen Ebene 1 + 2
    layout       = models.ForeignKey(PageLayout, on_delete=models.PROTECT,
                                     verbose_name='Seiten-Layout')
    style_kit    = models.ForeignKey(StyleKit, on_delete=models.PROTECT,
                                     verbose_name='Style-Kit')

    # Blöcke — geordnete Liste (via DocTemplateBlock)
    # Reihenfolge: logo → [doc_title] → [party_blocks] → [clauses] → signature → footer

    # Versionierung
    active_version = models.PositiveIntegerField(default=1)

    # Variablen-Schema — alle Variablen die dieses Template erwartet
    variables    = models.JSONField(
        default=list, blank=True,
        verbose_name='Variablen-Schema',
        help_text='''
        [
          {"name": "an_firma",            "type": "string",   "source": "consultant", "required": true},
          {"name": "an_ansprechpartner",  "type": "string",   "source": "consultant"},
          {"name": "stundensatz",         "type": "currency",  "source": "project"},
          {"name": "laufzeit_von",        "type": "date",      "source": "project"},
          {"name": "positionen",          "type": "list",      "source": "invoice",  "item_schema": {
            "zeitraum": "string", "stunden": "decimal", "satz_euro": "currency", "betrag_euro": "currency"
          }}
        ]
        '''
    )

    # Sprachen
    translation_languages = models.JSONField(default=list, blank=True,
                                              verbose_name='Übersetzungssprachen')

    # Tracking
    usage_count  = models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_by   = models.ForeignKey(User, on_delete=models.SET_NULL,
                                     null=True, blank=True,
                                     related_name='created_doc_templates')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name} [{self.identifier}]'

    class Meta:
        verbose_name        = 'Dokument-Vorlage'
        verbose_name_plural = 'Dokument-Vorlagen'
        ordering            = ['scope', 'name']
        indexes             = [
            models.Index(fields=['identifier']),
            models.Index(fields=['scope', 'status']),
        ]


class DocTemplateBlock(models.Model):
    """
    Verknüpfung Template ↔ ContentBlock mit Reihenfolge und Slot.
    Analog zu einem Django Template-Tag der Blöcke in Slots einfügt.
    """
    template     = models.ForeignKey(DocTemplate, on_delete=models.CASCADE,
                                     related_name='template_blocks')
    block        = models.ForeignKey(ContentBlock, on_delete=models.PROTECT,
                                     related_name='template_usages')
    slot         = models.CharField(max_length=100, default='body',
                                    verbose_name='Slot',
                                    help_text='z.B. "logo", "body", "footer_impressum"')
    order        = models.PositiveSmallIntegerField(default=10,
                                                     verbose_name='Reihenfolge')

    # Block-spezifische Überschreibungen (optional)
    style_override = models.JSONField(
        default=dict, blank=True,
        verbose_name='Style-Überschreibung',
        help_text='{"font_size_pt": 14} — überschreibt StyleDefinition für diesen Block'
    )
    content_override = models.TextField(
        blank=True,
        verbose_name='Inhalt-Überschreibung',
        help_text='Überschreibt ContentBlock.content für dieses Template'
    )
    conditional  = models.CharField(max_length=200, blank=True,
                                     help_text='Variablenname — Block nur wenn True')
    page_break_before = models.BooleanField(default=False)

    class Meta:
        verbose_name        = 'Template-Block'
        verbose_name_plural = 'Template-Blöcke'
        ordering            = ['slot', 'order']
        unique_together     = ['template', 'slot', 'order']


class DocTemplateVersion(models.Model):
    """
    Versionsverlauf einer Vorlage.
    Speichert den vollständigen Block-Snapshot als JSON.
    """
    template     = models.ForeignKey(DocTemplate, on_delete=models.CASCADE,
                                     related_name='versions')
    version      = models.PositiveIntegerField()
    snapshot     = models.JSONField(
        verbose_name='Block-Snapshot',
        help_text='Vollständiger Zustand: layout, style_kit, blocks[] zum Zeitpunkt'
    )
    change_note  = models.CharField(max_length=500, blank=True)
    created_by   = models.ForeignKey(User, on_delete=models.SET_NULL,
                                     null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['template', 'version']
        ordering        = ['-version']


# ════════════════════════════════════════════════════════════════════════════
# EBENE 4 — INVOICE / VERTRAGS-KONTEXT (Datenquellen für VariableEngine)
# ════════════════════════════════════════════════════════════════════════════

class InvoiceRecord(models.Model):
    """
    Rechnungsdaten — Quelle für VariableEngine bei scope=invoice.
    Verknüpft mit ProjectConsultant (wer wird abgerechnet).

    Abgeleitet aus realen Rechnungen:
      - Rechnung Zeitaufwand: 1 Position mit Zeitraum/Stunden/Satz
      - Rechnung Arbeitspakete: bis zu 21 AP-Positionen, Anzahl kann 0 (—) sein
    """

    INVOICE_TYPE = [
        ('zeitaufwand',   'Zeitaufwand (Stunden)'),
        ('arbeitspakete', 'Arbeitspakete (AP)'),
        ('festpreis',     'Festpreis'),
    ]

    STATUS = [
        ('draft',    'Entwurf'),
        ('sent',     'Versendet'),
        ('paid',     'Bezahlt'),
        ('overdue',  'Überfällig'),
        ('cancelled','Storniert'),
    ]

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4,
                                        editable=False)
    invoice_number   = models.CharField(max_length=50, unique=True,
                                         verbose_name='Rechnungsnummer',
                                         help_text='Format: JJ/MM/NNNN z.B. 26/04/0121')
    invoice_type     = models.CharField(max_length=20, choices=INVOICE_TYPE,
                                         default='zeitaufwand')
    status           = models.CharField(max_length=20, choices=STATUS,
                                         default='draft')

    # Verknüpfung
    project_consultant = models.ForeignKey(
        'abpe_matching_workflow.ProjectConsultant',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='invoices',
        verbose_name='Projekt-Berater'
    )
    # Alternativ: manuell ohne Matching-Verknüpfung
    consultant_name  = models.CharField(max_length=200, blank=True,
                                         verbose_name='Berater-Name (manuell)')
    customer_name    = models.CharField(max_length=200, blank=True,
                                         verbose_name='Rechnungsempfänger')
    customer_address = models.TextField(blank=True, verbose_name='Empfänger-Adresse')

    # Kopfdaten
    invoice_date     = models.DateField(verbose_name='Rechnungsdatum')
    subject          = models.CharField(max_length=500, verbose_name='Betreff',
                                         help_text='Beratungsleistung bei {endkunde} vertreten durch {berater}')
    billing_month    = models.CharField(max_length=50, blank=True,
                                         verbose_name='Abrechnungsmonat',
                                         help_text='z.B. "April 2026"')
    payment_term_days = models.PositiveSmallIntegerField(default=30,
                                                           verbose_name='Zahlungsziel Tage')

    # Positionen — JSONField für beide Rechnungstypen
    # Zeitaufwand:
    # [{"pos_nr": "1.", "zeitraum": "April 2026", "stunden": 80.0,
    #   "satz_euro": 99.00, "betrag_euro": 7920.00}]
    #
    # Arbeitspakete:
    # [{"ap_nr": 1, "beschreibung": "Kleines Projekt", "anzahl": null,
    #   "preis_euro": 380.00, "betrag_euro": 0.00},
    #  {"ap_nr": 2, "beschreibung": "Mittleres Projekt", "anzahl": 4,
    #   "preis_euro": 570.00, "betrag_euro": 2280.00}]
    positions        = models.JSONField(default=list, verbose_name='Positionen')

    # Summen (berechnet, gecacht)
    netto_euro       = models.DecimalField(max_digits=12, decimal_places=2,
                                            default=0, verbose_name='Netto €')
    mwst_satz        = models.DecimalField(max_digits=5, decimal_places=2,
                                            default=19.0, verbose_name='MwSt %')
    mwst_euro        = models.DecimalField(max_digits=12, decimal_places=2,
                                            default=0, verbose_name='MwSt €')
    brutto_euro      = models.DecimalField(max_digits=12, decimal_places=2,
                                            default=0, verbose_name='Brutto €')

    # Generiertes Dokument
    doc_log          = models.ForeignKey('DocLog', on_delete=models.SET_NULL,
                                          null=True, blank=True,
                                          related_name='invoices')

    created_by       = models.ForeignKey(User, on_delete=models.SET_NULL,
                                          null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    def calculate_totals(self):
        """Summen aus positions[] berechnen."""
        netto = sum(
            p.get('betrag_euro', 0) or 0
            for p in self.positions
        )
        self.netto_euro  = round(netto, 2)
        self.mwst_euro   = round(netto * float(self.mwst_satz) / 100, 2)
        self.brutto_euro = round(netto + float(self.mwst_euro), 2)

    def save(self, *args, **kwargs):
        self.calculate_totals()
        if not self.invoice_number:
            # Auto-Nummer: JJ/MM/NNNN
            from django.utils import timezone
            now = timezone.now()
            count = InvoiceRecord.objects.filter(
                created_at__year=now.year,
                created_at__month=now.month
            ).count() + 1
            self.invoice_number = f'{str(now.year)[2:]}/{now.month:02d}/{count:04d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Rg. {self.invoice_number} — {self.customer_name}'

    class Meta:
        verbose_name        = 'Rechnung'
        verbose_name_plural = 'Rechnungen'
        ordering            = ['-invoice_date']


# ════════════════════════════════════════════════════════════════════════════
# DOC LOG — Protokoll aller generierten Dokumente
# ════════════════════════════════════════════════════════════════════════════

class DocLog(models.Model):
    """
    Vollständiges Protokoll jedes generierten Dokuments.
    Analog zu EmailLog im Email Studio.

    Pfad-Struktur:
      /data/doc_out/{scope}/{context_ref}/{filename}
      z.B.: /data/doc_out/contract/ANF-2026-0042/sub_dienstvertrag_Troschke_20260522.docx
    """
    log_id       = models.UUIDField(primary_key=True, default=uuid.uuid4,
                                     editable=False)
    template     = models.ForeignKey(DocTemplate, on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='logs')
    template_version = models.PositiveIntegerField(null=True, blank=True)

    # Erzeugtes Format
    engine_used  = models.CharField(max_length=10, choices=DocEngine.choices)

    # Ablage
    file_path_docx = models.CharField(max_length=500, blank=True,
                                       verbose_name='Pfad .docx')
    file_path_pdf  = models.CharField(max_length=500, blank=True,
                                       verbose_name='Pfad .pdf')
    file_size_bytes = models.PositiveIntegerField(default=0)

    # Kontext
    context_ref  = models.CharField(max_length=200, blank=True,
                                     verbose_name='Kontext-Referenz',
                                     help_text='z.B. ANF-2026-0042 oder AID-12345')
    scope        = models.CharField(max_length=30, choices=DocScope.choices,
                                     blank=True)
    variables_used = models.JSONField(default=dict, blank=True,
                                       verbose_name='Verwendete Variablen')

    # E-Mail-Versand
    sent_via_email  = models.BooleanField(default=False)
    email_log_id    = models.CharField(max_length=200, blank=True,
                                        verbose_name='EmailLog UUID',
                                        help_text='FK auf abpe_email_studio.EmailLog')

    # Status
    status       = models.CharField(max_length=20, choices=LogStatus.choices,
                                     default=LogStatus.OK)
    error_message = models.TextField(blank=True)

    # Metadaten
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                      null=True, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        name = self.template.identifier if self.template else 'unbekannt'
        return f'{name} / {self.context_ref} [{self.status}]'

    class Meta:
        verbose_name        = 'Dokument-Log'
        verbose_name_plural = 'Dokument-Logs'
        ordering            = ['-generated_at']
        indexes             = [
            models.Index(fields=['context_ref']),
            models.Index(fields=['scope', 'generated_at']),
            models.Index(fields=['template', 'status']),
        ]


# ════════════════════════════════════════════════════════════════════════════
# DOC QUEUE — Celery-Warteschlange
# ════════════════════════════════════════════════════════════════════════════

class DocQueue(models.Model):
    """
    Asynchrone Generierung via Celery.
    Gibt sofort queue_id zurück, generiert im Hintergrund.
    """
    queue_id     = models.UUIDField(primary_key=True, default=uuid.uuid4,
                                     editable=False)
    template     = models.ForeignKey(DocTemplate, on_delete=models.CASCADE,
                                      related_name='queue_items')
    engine       = models.CharField(max_length=10, choices=DocEngine.choices,
                                     default=DocEngine.BOTH)
    variables    = models.JSONField(default=dict)
    context_ref  = models.CharField(max_length=200, blank=True)
    scope        = models.CharField(max_length=30, blank=True)

    # E-Mail nach Generierung
    send_email_to = models.JSONField(default=list, blank=True,
                                      verbose_name='E-Mail senden an')
    email_template = models.CharField(max_length=200, blank=True,
                                       verbose_name='Email-Template Identifier')

    status         = models.CharField(max_length=20, choices=QueueStatus.choices,
                                       default=QueueStatus.PENDING)
    celery_task_id = models.CharField(max_length=200, blank=True)
    retry_count    = models.PositiveSmallIntegerField(default=0)
    max_retries    = models.PositiveSmallIntegerField(default=3)
    error_message  = models.TextField(blank=True)

    user_id        = models.IntegerField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    processed_at   = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'Queue {self.queue_id} → {self.template.identifier} [{self.status}]'

    class Meta:
        ordering = ['created_at']
        indexes  = [models.Index(fields=['status', 'created_at'])]

