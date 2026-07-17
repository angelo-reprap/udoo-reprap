"""
ABpE Doc Studio — Models
========================
Generischer Word/PDF Generator basierend auf OOXML-Grundbausteinen.

10 OOXML-Grundbausteine (WordprocessingML):
  1. PARAGRAPH      <w:p>              Text, Überschriften, Leerzeilen
  2. TABLE          <w:tbl>            Tabelle mit Zeilen + Zellen
  3. DRAWING        <w:drawing>        Bilder (DrawingML)
  4. FIELD          <w:fldChar>        Feldfunktionen (PAGE, NUMPAGES, DATE)
  5. PAGE_BREAK     <w:br type="page"> Seitenumbruch
  6. CONTENT_CONTROL <w:sdt>           Inhaltssteuerelemente
  7. SECTION        <w:sectPr>         Abschnittseigenschaften
  8. HEADER_FOOTER  <w:hdr>/<w:ftr>    Kopf-/Fußzeile
  9. HYPERLINK      <w:hyperlink>      Hyperlinks
  10. BOOKMARK      <w:bookmarkStart>  Lesezeichen

Konfigurationsquellen:
  blocks.json  → block_type, content, row_styles, col_styles, layout_ref
  styles.json  → Formatierung (font, size, bold, color, spacing, borders)
  layout.json  → Geometrie (Seitenmaße, Spaltenbreiten, layout_refs, image_refs)
  template.json → Reihenfolge, header_block_id, footer_block_id, logo_block_id

Zentrale Python-API:
  from apps.abpe_doc_studio.api import DocStudio
  DocStudio.generate(template='rahmenvertrag', context_ref='ANF-2026-0042')
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
    """
    20 OOXML-Grundbausteine ISO 29500 Kapitel 17.
    """
    PARAGRAPH       = 'PARAGRAPH',       'Paragraph <w:p>'
    LINE_BREAK      = 'LINE_BREAK',      'Zeilenumbruch <w:br type=textWrapping>'
    PAGE_BREAK      = 'PAGE_BREAK',      'Seitenumbruch <w:br type=page>'
    TABLE           = 'TABLE',           'Tabelle <w:tbl>'
    CONTENT_CONTROL = 'CONTENT_CONTROL', 'Inhaltssteuerelement <w:sdt>'
    SECTION         = 'SECTION',         'Abschnitt <w:sectPr>'
    COLUMN_BREAK    = 'COLUMN_BREAK',    'Spaltenumbruch <w:br type=column>'
    LIST            = 'LIST',            'Liste/Aufzaehlung <w:numPr>'
    HEADER          = 'HEADER',          'Kopfzeile <w:hdr>'
    FOOTER          = 'FOOTER',          'Fusszeile <w:ftr>'
    FOOTNOTE        = 'FOOTNOTE',        'Fussnote <w:footnote>'
    ENDNOTE         = 'ENDNOTE',         'Endnote <w:endnote>'
    BOOKMARK        = 'BOOKMARK',        'Lesezeichen <w:bookmarkStart>'
    COMMENT         = 'COMMENT',         'Kommentar <w:comment>'
    FIELD           = 'FIELD',           'Feldfunktion <w:fldChar>'
    HYPERLINK       = 'HYPERLINK',       'Hyperlink <w:hyperlink>'
    DRAWING         = 'DRAWING',         'Bild/Zeichnung <w:drawing>'
    TEXTBOX         = 'TEXTBOX',         'Textbox <wp:anchor+wps:txbx>'
    SUBDOCUMENT     = 'SUBDOCUMENT',     'Unterdokument <w:subDoc>'
    RAW_XML         = 'RAW_XML',         'Direktes OOXML Fallback'



class FieldType(models.TextChoices):
    """Typen fuer FIELD-Bloecke."""
    PAGE_NUMBER  = 'PAGE_NUMBER',  'Seitennummer (PAGE)'
    TOTAL_PAGES  = 'TOTAL_PAGES',  'Gesamtseiten (NUMPAGES)'
    DATE         = 'DATE',         'Datum (DATE)'
    TIME         = 'TIME',         'Uhrzeit (TIME)'
    AUTHOR       = 'AUTHOR',       'Autor (AUTHOR)'
    FILENAME     = 'FILENAME',     'Dateiname (FILENAME)'


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
    RUNNING   = 'RUNNING',   'Laeuft'
    DONE      = 'DONE',      'Erledigt'
    FAILED    = 'FAILED',    'Fehlgeschlagen'
    CANCELLED = 'CANCELLED', 'Abgebrochen'


# ════════════════════════════════════════════════════════════════════════════
# EBENE 1 — PAGE LAYOUT
# ════════════════════════════════════════════════════════════════════════════

class PageLayout(models.Model):
    """
    Seitenstruktur — alle Geometrie-Werte fuer den Assembler.

    layout_refs: JSON-Dictionary mit benannten Geometrie-Konfigurationen
      fuer TABLE, DRAWING und N_COLUMN Bloecke.
      Beispiel:
      {
        "invoice_table": {"width_cm": 16.0, "alt_row_color": "F8FAFC"},
        "logo_image":    {"height_cm": 2.0, "width_cm": 5.0, "alignment": "right"},
        "signature":     {"column_widths_cm": [6.0, 1.5, 6.0]},
        "label_value":   {"column_widths_cm": [5.0, 10.0]},
        "total":         {"column_widths_cm": [3.0, 8.0, 4.0]}
      }

    image_refs: JSON-Dictionary mit Bildpfaden
      Beispiel:
      {
        "logo_abcona": "data/cv/adds/logo_abcona.png",
        "logo_klein":  "apps/abpe_ui/static/abpe_ui/img/logo_abcona.png"
      }
    """
    identifier   = models.SlugField(max_length=100, unique=True,
                                    verbose_name='Bezeichner')
    name         = models.CharField(max_length=200, verbose_name='Anzeigename')
    description  = models.TextField(blank=True)

    # Seitenformat
    page_width_cm    = models.FloatField(default=21.0,  verbose_name='Breite cm')
    page_height_cm   = models.FloatField(default=29.7,  verbose_name='Hoehe cm')
    orientation      = models.CharField(
        max_length=10, default='portrait',
        choices=[('portrait', 'Hochformat'), ('landscape', 'Querformat')]
    )

    # Seitenraender
    margin_left_cm   = models.FloatField(default=3.0, verbose_name='Rand links cm')
    margin_right_cm  = models.FloatField(default=3.0, verbose_name='Rand rechts cm')
    margin_top_cm    = models.FloatField(default=4.2, verbose_name='Rand oben cm')
    margin_bottom_cm = models.FloatField(default=5.2, verbose_name='Rand unten cm')

    # Header/Footer Abstände
    header_distance_cm = models.FloatField(default=1.5, verbose_name='Header-Abstand cm')
    footer_distance_cm = models.FloatField(default=1.5, verbose_name='Footer-Abstand cm')

    # Spaltigkeit
    columns          = models.PositiveSmallIntegerField(default=1,
                                                        verbose_name='Spalten')
    column_widths_cm = models.JSONField(
        default=list, blank=True,
        verbose_name='Spaltenbreiten cm',
        help_text='[15.0] oder [7.5, 7.5] fuer 2-spaltig'
    )

    # Seitennummerierung
    show_page_numbers    = models.BooleanField(default=True)
    page_number_format   = models.CharField(
        max_length=50, default='Seite {page} von {total}',
        verbose_name='Seitenzahl-Format',
        help_text='Seite {page} von {total}'
    )
    page_number_position = models.CharField(
        max_length=20, default='top_right',
        choices=[
            ('top_right',    'Oben rechts'),
            ('top_center',   'Oben Mitte'),
            ('bottom_right', 'Unten rechts'),
            ('bottom_center','Unten Mitte'),
        ]
    )

    # Geometrie-Referenzen fuer Bloecke (TABLE, DRAWING, N_COLUMN)
    layout_refs = models.JSONField(
        default=dict, blank=True,
        verbose_name='Layout-Referenzen',
        help_text='''
        Benannte Geometrie-Konfigurationen fuer Bloecke.
        Beispiel:
        {
          "invoice_table": {
            "width_cm": 16.0,
            "alt_row_color": "F8FAFC",
            "white_row_color": "FFFFFF"
          },
          "logo": {
            "column_widths_cm": [9.0, 6.0],
            "image_height_cm": 2.0
          },
          "signature": {
            "column_widths_cm": [6.0, 1.5, 6.0],
            "space_before_pt": 40.0
          },
          "label_value": {
            "column_widths_cm": [5.0, 10.0]
          },
          "total": {
            "column_widths_cm": [3.0, 8.0, 4.0]
          },
          "inv_header": {
            "column_widths_cm": [8.0, 8.0]
          }
        }
        '''
    )

    # Bild-Referenzen fuer DRAWING-Bloecke
    image_refs = models.JSONField(
        default=dict, blank=True,
        verbose_name='Bild-Referenzen',
        help_text='''
        Pfade zu Bilddateien relativ zu BASE_DIR.
        Beispiel:
        {
          "logo_abcona": "data/cv/adds/logo_abcona.png",
          "logo_small":  "apps/abpe_ui/static/abpe_ui/img/logo_abcona.png"
        }
        '''
    )

    # Normal-Style Basis
    normal_font_size_pt = models.FloatField(
        default=10.0,
        verbose_name='Normal-Style Schriftgroesse (pt)'
    )

    # Tabellen-Farben (Fallback wenn nicht in layout_refs)
    table_alt_row_color   = models.CharField(max_length=7, default='F8FAFC', blank=True)
    table_white_row_color = models.CharField(max_length=7, default='FFFFFF', blank=True)

    # Slot-Reihenfolge
    slot_order = models.JSONField(
        default=list, blank=True,
        verbose_name='Slot-Reihenfolge',
        help_text='["header", "body", "footer"]'
    )

    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name} ({self.identifier})'

    class Meta:
        verbose_name        = 'Seiten-Layout'
        verbose_name_plural = 'Seiten-Layouts'
        ordering            = ['name']


# ════════════════════════════════════════════════════════════════════════════
# EBENE 2 — STYLE KIT
# ════════════════════════════════════════════════════════════════════════════

class StyleKit(models.Model):
    """
    Sammlung von Formatierungen — Corporate Design in der DB.
    Alle Werte werden von _apply_style() im Assembler gelesen.
    """
    identifier  = models.SlugField(max_length=100, unique=True)
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
    Einzelne Formatdefinition — wird von _apply_style() im Assembler gelesen.
    Kein hardcoded Wert im Assembler — alles kommt von hier.
    """
    style_kit    = models.ForeignKey(StyleKit, on_delete=models.CASCADE,
                                     related_name='definitions')
    style_key    = models.SlugField(max_length=100, verbose_name='Style-Key')
    style_type   = models.CharField(max_length=20, choices=StyleType.choices,
                                    default=StyleType.TEXT)
    name         = models.CharField(max_length=200, verbose_name='Anzeigename')

    # Text-Formatierung
    font_family     = models.CharField(max_length=100, default='Arial')
    font_size_pt    = models.FloatField(default=10.0)
    bold            = models.BooleanField(default=False)
    italic          = models.BooleanField(default=False)
    underline       = models.BooleanField(default=False)
    color_hex       = models.CharField(max_length=10, default='1A1A1A')

    # Absatz-Formatierung
    alignment       = models.CharField(
        max_length=20, default='left',
        choices=[
            ('left',    'Links'),
            ('right',   'Rechts'),
            ('center',  'Zentriert'),
            ('justify', 'Blocksatz'),
        ]
    )
    space_before_pt = models.FloatField(default=0.0)
    space_after_pt  = models.FloatField(default=6.0)
    line_spacing    = models.FloatField(default=1.15)
    indent_left_cm  = models.FloatField(default=0.0)

    # Rahmen-Linien
    border_bottom       = models.BooleanField(default=False)
    border_bottom_color = models.CharField(max_length=10, default='163258')
    border_bottom_pt    = models.FloatField(default=0.5)
    border_bottom_style = models.CharField(
        max_length=20, default='single',
        choices=[
            ('single',  'Einfach'),
            ('dashed',  'Gestrichelt'),
            ('thick',   'Dick'),
        ]
    )

    # Tabellen-Formatierung
    table_header_bg_hex    = models.CharField(max_length=10, blank=True, default='163258')
    table_header_text_hex  = models.CharField(max_length=10, blank=True, default='FFFFFF')
    table_row_alt_bg_hex   = models.CharField(max_length=10, blank=True, default='F8FAFC')
    table_border_color_hex = models.CharField(max_length=10, blank=True, default='E5E7EB')
    table_border_pt        = models.FloatField(default=0.5)

    # Hintergrundfarbe
    bg_color_hex = models.CharField(max_length=10, blank=True, default='')

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
    Wiederverwendbarer OOXML-Baustein.

    Jeder Block entspricht einem der 10 OOXML-Grundbausteine.
    Der Assembler liest block_type und rendert entsprechend.

    Konfigurationsfelder je block_type:

    PARAGRAPH:
      content      → Text mit {variablen}, Zeilen mit \\n getrennt
      row_styles   → ["section_head", "body_text"] — Style pro Zeile
      style_key    → Fallback-Style wenn row_styles leer

    TABLE:
      columns      → Spalten-Definition mit label, width_pct, style_key
      layout_ref   → Referenz auf layout.layout_refs fuer Geometrie
      content      → optional statischer Tabelleninhalt (|separiert)

    DRAWING:
      image_ref    → Referenz auf layout.image_refs fuer Bildpfad
      layout_ref   → Referenz auf layout.layout_refs fuer Groesse/Position

    FIELD:
      field_type   → PAGE_NUMBER, TOTAL_PAGES, DATE etc.
      content      → Format-String z.B. "Seite {PAGE} von {NUMPAGES}"
      style_key    → Style fuer den Text

    PAGE_BREAK:
      (keine weiteren Felder noetig)

    CONTENT_CONTROL:
      control_title → Titel des Steuerelements (fuer Binding)
      control_id    → Eindeutige ID
      content       → Platzhalter-Text mit {variablen}
      style_key     → Style fuer den Inhalt

    SECTION:
      (wird direkt aus PageLayout gelesen — kein Block noetig)

    HEADER / FOOTER:
      content      → Text mit {variablen}
      row_styles   → Style pro Zeile
      layout_ref   → optionale Geometrie (z.B. fuer Logo im Header)

    HYPERLINK:
      content      → Anzeigetext mit {variablen}
      url          → URL mit {variablen}, z.B. "http://{ag_web}"
      style_key    → Style (z.B. "hyperlink")

    BOOKMARK:
      bookmark_name → Name des Lesezeichens
      bookmark_id   → Eindeutige numerische ID
    """
    identifier   = models.SlugField(max_length=150, unique=True,
                                    verbose_name='Block-Identifier')
    name         = models.CharField(max_length=200, verbose_name='Anzeigename')
    block_type   = models.CharField(max_length=30, choices=BlockType.choices,
                                    verbose_name='Block-Typ (OOXML-Grundbaustein)')
    description  = models.TextField(blank=True)

    # Style-Referenz
    style_kit    = models.ForeignKey(StyleKit, on_delete=models.PROTECT,
                                     related_name='blocks')
    style_key    = models.CharField(max_length=100, blank=True,
                                    verbose_name='Style-Key (Fallback)')

    # ── PARAGRAPH / HEADER / FOOTER ──────────────────────────────────────
    # content: Text mit {variablen}, Zeilen mit \n getrennt
    content      = models.TextField(blank=True, verbose_name='Inhalt')

    # row_styles: Style-Key pro Zeile
    # ["section_head", "body_text", "body_text"]
    # Wenn kuerzer als Anzahl Zeilen → letzter Style wird wiederholt
    row_styles   = models.JSONField(
        default=list, blank=True,
        verbose_name='Zeilen-Styles',
        help_text='["section_head", "body_text"] — Style pro Zeile in content'
    )

    # col_styles: Style-Key pro Spalte (fuer TABLE mit statischem content)
    # ["label_blue", "body_text"]
    col_styles   = models.JSONField(
        default=list, blank=True,
        verbose_name='Spalten-Styles',
        help_text='["label_blue", "body_text"] — Style pro Spalte'
    )

    # col_alignments: Ausrichtung pro Spalte
    # ["left", "right"]
    col_alignments = models.JSONField(
        default=list, blank=True,
        verbose_name='Spalten-Ausrichtung',
        help_text='["left", "right"] — Ausrichtung pro Spalte'
    )

    # row_border_bottom: Zeilenindizes die eine Unterlinie bekommen
    # [0] → nur erste Zeile hat Unterlinie
    row_border_bottom = models.JSONField(
        default=list, blank=True,
        verbose_name='Unterlinie bei Zeilen',
        help_text='[0, 2] — Zeilenindizes mit Unterlinie'
    )

    # row_borders: vollständige Zellenrand-Konfiguration pro Zeile
    row_borders = models.JSONField(
        default=dict, blank=True,
        verbose_name='Zellenränder pro Zeile',
        help_text='''
        {
          "0": {"bottom": {"style": "single", "sz": 4, "color": "163258"}},
          "2": {"bottom": {"style": "double", "sz": 4, "color": "163258"}}
        }
        Styles: single, thick, double, dashed, dotted, nil
        sz: 4=0.5pt, 6=0.75pt, 8=1pt, 12=1.5pt, 18=2.25pt
        '''
    )

    # row_bg: Hintergrundfarben pro Zeile (überschreibt alt/white_row_color)
    row_bg = models.JSONField(
        default=dict, blank=True,
        verbose_name='Hintergrundfarben pro Zeile',
        help_text='''
        {"0": "F8FAFC", "2": "163258"}
        — Zeilenindex: Hex-Farbe
        '''
    )

    # col_borders: Spaltenränder-Konfiguration
    col_borders = models.JSONField(
        default=dict, blank=True,
        verbose_name='Spaltenränder',
        help_text='''
        {
          "0": {"right": {"style": "single", "sz": 4, "color": "163258"}},
          "2": {"left":  {"style": "single", "sz": 4, "color": "163258"}}
        }
        '''
    )

    # ── TABLE ─────────────────────────────────────────────────────────────
    # columns: Spalten-Definition fuer dynamische Tabellen
    columns      = models.JSONField(
        default=list, blank=True,
        verbose_name='Spalten-Definition',
        help_text='''
        [
          {"key": "zeitraum", "label": "Zeitraum",
           "width_pct": 30, "align": "left", "style_key": "table_body"},
          {"key": "stunden",  "label": "Stunden",
           "width_pct": 20, "align": "right", "style_key": "table_body"}
        ]
        '''
    )

    # ── DRAWING ───────────────────────────────────────────────────────────
    # image_ref: Schluessel in layout.image_refs
    image_ref    = models.CharField(max_length=200, blank=True,
                                    verbose_name='Bild-Referenz',
                                    help_text='Schluessel in layout.image_refs')

    # ── TABLE + DRAWING + N_COLUMN ────────────────────────────────────────
    # layout_ref: Schluessel in layout.layout_refs
    layout_ref   = models.CharField(max_length=200, blank=True,
                                    verbose_name='Layout-Referenz',
                                    help_text='Schluessel in layout.layout_refs')

    # ── FIELD ─────────────────────────────────────────────────────────────
    field_type   = models.CharField(
        max_length=20, blank=True,
        choices=FieldType.choices,
        verbose_name='Feld-Typ',
        help_text='PAGE_NUMBER, TOTAL_PAGES, DATE etc.'
    )

    # ── CONTENT_CONTROL ───────────────────────────────────────────────────
    control_title = models.CharField(max_length=200, blank=True,
                                     verbose_name='Steuerelement-Titel')
    control_id    = models.CharField(max_length=50, blank=True,
                                     verbose_name='Steuerelement-ID')

    # ── HYPERLINK ─────────────────────────────────────────────────────────
    url          = models.CharField(max_length=500, blank=True,
                                    verbose_name='URL',
                                    help_text='URL mit {variablen}, z.B. http://{ag_web}')

    # ── BOOKMARK ──────────────────────────────────────────────────────────
    bookmark_name = models.CharField(max_length=200, blank=True,
                                     verbose_name='Lesezeichen-Name')
    bookmark_id   = models.CharField(max_length=50, blank=True,
                                     verbose_name='Lesezeichen-ID')

    # ── Gemeinsame Felder ─────────────────────────────────────────────────
    expected_variables = models.JSONField(
        default=list, blank=True,
        verbose_name='Erwartete Variablen',
        help_text='[{"name": "stundensatz", "type": "currency", "required": true}]'
    )
    repeatable   = models.BooleanField(default=False,
                                        verbose_name='Wiederholbar')
    conditional  = models.CharField(max_length=200, blank=True,
                                     verbose_name='Bedingung',
                                     help_text='Variable die true sein muss')

    is_active    = models.BooleanField(default=True)
    created_by   = models.ForeignKey(User, on_delete=models.SET_NULL,
                                     null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name} [{self.identifier}]'

    class Meta:
        verbose_name        = 'Content-Block'
        verbose_name_plural = 'Content-Bloecke'
        ordering            = ['block_type', 'name']
        indexes             = [models.Index(fields=['identifier'])]


# ════════════════════════════════════════════════════════════════════════════
# DOKUMENT-TEMPLATE
# ════════════════════════════════════════════════════════════════════════════

class DocTemplate(models.Model):
    """
    Vollstaendige Vorlage — kombiniert Layout + StyleKit + Bloecke.

    Referenzen auf Shared-Bloecke:
      logo_block_id   → identifier des DRAWING-Blocks fuer das Logo
      header_block_id → identifier des HEADER-Blocks
      footer_block_id → identifier des FOOTER-Blocks
    """
    identifier   = models.SlugField(max_length=200, unique=True,
                                    verbose_name='Technischer Name')
    name         = models.CharField(max_length=200, verbose_name='Anzeigename')
    description  = models.TextField(blank=True)
    scope        = models.CharField(max_length=30, choices=DocScope.choices,
                                    default=DocScope.CONTRACT)
    engine       = models.CharField(max_length=10, choices=DocEngine.choices,
                                    default=DocEngine.BOTH)
    status       = models.CharField(max_length=20, choices=DocStatus.choices,
                                    default=DocStatus.DRAFT)

    # Layout + StyleKit
    layout       = models.ForeignKey(PageLayout, on_delete=models.PROTECT,
                                     verbose_name='Seiten-Layout')
    style_kit    = models.ForeignKey(StyleKit, on_delete=models.PROTECT,
                                     verbose_name='Style-Kit')

    # Shared Block-Referenzen
    logo_block_id   = models.CharField(max_length=200, blank=True,
                                        default='abcona_logo',
                                        verbose_name='Logo-Block Identifier')
    header_block_id = models.CharField(max_length=200, blank=True,
                                        default='page_header',
                                        verbose_name='Header-Block Identifier')
    footer_block_id = models.CharField(max_length=200, blank=True,
                                        default='abcona_footer',
                                        verbose_name='Footer-Block Identifier')
    template_dir    = models.CharField(max_length=200, blank=True,
                                        default='',
                                        verbose_name='Template-Verzeichnis',
                                        help_text='Unterverzeichnis in generator/templates/')

    # Versionierung
    active_version = models.PositiveIntegerField(default=1)

    # Variablen-Schema
    variables    = models.JSONField(
        default=list, blank=True,
        verbose_name='Variablen-Schema',
        help_text='''
        [
          {"name": "an_firma",   "type": "string",   "source": "consultant", "required": true},
          {"name": "stundensatz","type": "currency",  "source": "project"},
          {"name": "positionen", "type": "list",      "source": "invoice",
           "item_schema": {
             "zeitraum": "string", "stunden": "decimal",
             "satz_euro": "currency", "betrag_euro": "currency"
           }}
        ]
        '''
    )

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
    Verknuepfung Template <-> ContentBlock mit Reihenfolge und Slot.
    """
    template     = models.ForeignKey(DocTemplate, on_delete=models.CASCADE,
                                     related_name='template_blocks')
    block        = models.ForeignKey(ContentBlock, on_delete=models.PROTECT,
                                     related_name='template_usages')
    slot         = models.CharField(max_length=100, default='body',
                                    verbose_name='Slot',
                                    help_text='"header", "body", "footer"')
    order        = models.PositiveSmallIntegerField(default=10)

    # Floating-Element Anker: Identifier des Blocks an dessen ersten Paragraph
    # ein TEXTBOX/DRAWING Anchor eingehängt wird (z.B. Kontaktblock neben AG-Adresse)
    anchor_to_block = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='Anchor zu Block',
        help_text='Identifier des Blocks an dessen ersten Paragraph dieser Block verankert wird'
    )
    # Block-spezifische Ueberschreibungen
    style_override = models.JSONField(
        default=dict, blank=True,
        verbose_name='Style-Ueberschreibung'
    )
    content_override = models.TextField(
        blank=True,
        verbose_name='Inhalt-Ueberschreibung'
    )
    conditional      = models.CharField(max_length=200, blank=True)
    page_break_before = models.BooleanField(default=False)

    class Meta:
        verbose_name        = 'Template-Block'
        verbose_name_plural = 'Template-Bloecke'
        ordering            = ['slot', 'order']
        unique_together     = ['template', 'slot', 'order']


class DocTemplateVersion(models.Model):
    """Versionsverlauf einer Vorlage."""
    template     = models.ForeignKey(DocTemplate, on_delete=models.CASCADE,
                                     related_name='versions')
    version      = models.PositiveIntegerField()
    snapshot     = models.JSONField(verbose_name='Block-Snapshot')
    change_note  = models.CharField(max_length=500, blank=True)
    created_by   = models.ForeignKey(User, on_delete=models.SET_NULL,
                                     null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['template', 'version']
        ordering        = ['-version']


# ════════════════════════════════════════════════════════════════════════════
# INVOICE RECORD
# ════════════════════════════════════════════════════════════════════════════

class InvoiceRecord(models.Model):
    """Rechnungsdaten — Quelle fuer VariableEngine bei scope=invoice."""

    INVOICE_TYPE = [
        ('zeitaufwand',   'Zeitaufwand (Stunden)'),
        ('arbeitspakete', 'Arbeitspakete (AP)'),
        ('festpreis',     'Festpreis'),
    ]
    STATUS = [
        ('draft',     'Entwurf'),
        ('sent',      'Versendet'),
        ('paid',      'Bezahlt'),
        ('overdue',   'Ueberfaellig'),
        ('cancelled', 'Storniert'),
    ]

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4,
                                        editable=False)
    invoice_number   = models.CharField(max_length=50, unique=True,
                                         verbose_name='Rechnungsnummer')
    invoice_type     = models.CharField(max_length=20, choices=INVOICE_TYPE,
                                         default='zeitaufwand')
    status           = models.CharField(max_length=20, choices=STATUS,
                                         default='draft')

    project_consultant = models.ForeignKey(
        'abpe_matching_workflow.ProjectConsultant',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='invoices'
    )
    consultant_name  = models.CharField(max_length=200, blank=True)
    customer_name    = models.CharField(max_length=200, blank=True)
    customer_address = models.TextField(blank=True)

    invoice_date      = models.DateField(verbose_name='Rechnungsdatum')
    subject           = models.CharField(max_length=500, verbose_name='Betreff')
    billing_month     = models.CharField(max_length=50, blank=True)
    payment_term_days = models.PositiveSmallIntegerField(default=30)

    positions  = models.JSONField(default=list, verbose_name='Positionen')
    netto_euro = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mwst_satz  = models.DecimalField(max_digits=5,  decimal_places=2, default=19.0)
    mwst_euro  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    brutto_euro= models.DecimalField(max_digits=12, decimal_places=2, default=0)

    doc_log    = models.ForeignKey('DocLog', on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='invoices')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                    null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def calculate_totals(self):
        netto = sum(p.get('betrag_euro', 0) or 0 for p in self.positions)
        self.netto_euro  = round(netto, 2)
        self.mwst_euro   = round(netto * float(self.mwst_satz) / 100, 2)
        self.brutto_euro = round(netto + float(self.mwst_euro), 2)

    def save(self, *args, **kwargs):
        self.calculate_totals()
        if not self.invoice_number:
            from django.utils import timezone
            now   = timezone.now()
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
# DOC LOG
# ════════════════════════════════════════════════════════════════════════════

class DocLog(models.Model):
    """Protokoll aller generierten Dokumente."""

    log_id       = models.UUIDField(primary_key=True, default=uuid.uuid4,
                                     editable=False)
    template     = models.ForeignKey(DocTemplate, on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='logs')
    template_version = models.PositiveIntegerField(null=True, blank=True)
    engine_used  = models.CharField(max_length=10, choices=DocEngine.choices)

    file_path_docx  = models.CharField(max_length=500, blank=True)
    file_path_pdf   = models.CharField(max_length=500, blank=True)
    file_size_bytes = models.PositiveIntegerField(default=0)

    context_ref    = models.CharField(max_length=200, blank=True)
    scope          = models.CharField(max_length=30, choices=DocScope.choices,
                                       blank=True)
    variables_used = models.JSONField(default=dict, blank=True)

    sent_via_email = models.BooleanField(default=False)
    email_log_id   = models.CharField(max_length=200, blank=True)

    status        = models.CharField(max_length=20, choices=LogStatus.choices,
                                      default=LogStatus.OK)
    error_message = models.TextField(blank=True)

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
# DOC QUEUE
# ════════════════════════════════════════════════════════════════════════════

class DocQueue(models.Model):
    """Asynchrone Generierung via Celery."""

    queue_id     = models.UUIDField(primary_key=True, default=uuid.uuid4,
                                     editable=False)
    template     = models.ForeignKey(DocTemplate, on_delete=models.CASCADE,
                                      related_name='queue_items')
    engine       = models.CharField(max_length=10, choices=DocEngine.choices,
                                     default=DocEngine.BOTH)
    variables    = models.JSONField(default=dict)
    context_ref  = models.CharField(max_length=200, blank=True)
    scope        = models.CharField(max_length=30, blank=True)

    send_email_to  = models.JSONField(default=list, blank=True)
    email_template = models.CharField(max_length=200, blank=True)

    status         = models.CharField(max_length=20, choices=QueueStatus.choices,
                                       default=QueueStatus.PENDING)
    celery_task_id = models.CharField(max_length=200, blank=True)
    retry_count    = models.PositiveSmallIntegerField(default=0)
    max_retries    = models.PositiveSmallIntegerField(default=3)
    error_message  = models.TextField(blank=True)

    user_id      = models.IntegerField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'Queue {self.queue_id} → {self.template.identifier} [{self.status}]'

    class Meta:
        ordering = ['created_at']
        indexes  = [models.Index(fields=['status', 'created_at'])]
