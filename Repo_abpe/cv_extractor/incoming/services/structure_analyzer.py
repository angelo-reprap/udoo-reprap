"""
structure_analyzer.py - Erkennt Struktur von Textzeilen

Dynamische Erkennung basierend auf Formatierungsattributen:
  - Schriftgröße (normal_size, heading_size, max_size)
  - Bold, Italic
  - Schriftart (font)
  - Y-Abstand (normal_gap, threshold)
  - Seitenposition

Keine festen Zahlenwerte — alles wird aus dem Dokument berechnet.
"""
import re
from typing import List, Dict, Optional, Tuple
from collections import Counter


class StructureAnalyzer:

    def __init__(self, spans: List, normal_gap: int, max_size: float):
        """
        spans:      Liste von Span-Objekten oder Dicts mit text/size/bold/x/y/page
        normal_gap: häufigster Y-Abstand im Dokument
        max_size:   größte Schriftgröße im Dokument
        """
        self.spans      = spans
        self.normal_gap = normal_gap
        self.max_size   = max_size
        self.threshold  = normal_gap * 2

        # Dynamisch berechnen
        self._normal_size  = self._calc_normal_size()
        self._heading_size = self._normal_size + 1.0
        self._pages_first_y = self._calc_pages_first_y()

    # ── Interne Berechnungen ──────────────────────────────────────────────────

    def _get(self, span, attr, default=None):
        """Span kann Dict oder Objekt sein."""
        if isinstance(span, dict):
            return span.get(attr, default)
        return getattr(span, attr, default)

    def _calc_normal_size(self) -> float:
        """Häufigste Schriftgröße = normaler Fließtext."""
        sizes = Counter(round(self._get(s, 'size', 12.0), 1) for s in self.spans)
        return sizes.most_common(1)[0][0] if sizes else 12.0

    def _calc_pages_first_y(self) -> Dict[int, float]:
        """Erste Y-Position pro Seite."""
        result = {}
        for s in sorted(self.spans, key=lambda x: (self._get(x, 'page', 1),
                                                     self._get(x, 'y', 0))):
            page = self._get(s, 'page', 1)
            if page not in result:
                result[page] = self._get(s, 'y', 0)
        return result

    # ── Öffentliche Eigenschaften ─────────────────────────────────────────────

    @property
    def normal_size(self) -> float:
        return self._normal_size

    @property
    def heading_size(self) -> float:
        return self._heading_size

    # ── Block-Split Entscheidung ──────────────────────────────────────────────

    def should_split(self, span, prev_span) -> Tuple[bool, str]:
        """
        Entscheidet ob zwischen prev_span und span ein neuer Block beginnt.
        Gibt (split: bool, reason: str) zurück.

        Regeln (NUR Formatierung, keine festen Inhalts-Keywords):
          1. Seitenumbruch + Formatwechsel → neuer Block
          2. Seitenumbruch + gleiche Formatierung → Fortsetzung (kein Split)
          3. Großer Y-Abstand (> threshold * 1.5) → neuer Block
          4. Y-Abstand >= threshold + Formatwechsel → neuer Block
        """
        if prev_span is None:
            return False, ''

        page      = self._get(span, 'page', 1)
        prev_page = self._get(prev_span, 'page', 1)
        size      = round(self._get(span, 'size', 12.0), 1)
        prev_size = round(self._get(prev_span, 'size', 12.0), 1)
        bold      = self._get(span, 'bold', False)
        prev_bold = self._get(prev_span, 'bold', False)
        italic    = self._get(span, 'italic', False)
        prev_italic = self._get(prev_span, 'italic', False)
        font      = self._get(span, 'font', '')
        prev_font = self._get(prev_span, 'font', '')
        y         = self._get(span, 'y', 0)
        prev_y    = self._get(prev_span, 'y', 0)

        bold_change   = bold != prev_bold
        size_change   = abs(size - prev_size) >= 1.0
        font_change   = bool(font and prev_font and font != prev_font)
        italic_change = italic != prev_italic
        fmt_change    = bold_change or size_change or font_change or italic_change

        # ── Seitenumbruch ─────────────────────────────────────────────────────
        if page != prev_page:
            if fmt_change:
                return True, 'page+fmt(p%d→p%d)' % (prev_page, page)
            # Gleiche Formatierung = Fortsetzung des vorherigen Blocks
            return False, ''

        # ── Gleiche Seite ─────────────────────────────────────────────────────
        gap = y - prev_y

        # Großer Sprung allein reicht
        if gap > self.threshold * 1.5:
            return True, 'gap_large(%d)' % gap

        # Normaler Sprung + Formatwechsel
        if gap >= self.threshold and fmt_change:
            parts = []
            if bold_change:   parts.append('bold')
            if size_change:   parts.append('size')
            if font_change:   parts.append('font')
            if italic_change: parts.append('italic')
            return True, 'gap(%d)+%s' % (gap, '+'.join(parts))

        return False, ''

    # ── Bestehende Methoden (unverändert) ─────────────────────────────────────

    def is_bullet(self, text: str) -> bool:
        """Prüft ob Text mit Bullet beginnt."""
        if not text:
            return False
        stripped = text.lstrip()
        if not stripped:
            return False
        bullet_chars = ['•', '●', '○', '■', '▪', '▫', '►', '➢', '→',
                        '❯', '›', '-', '–', '—', '*', '+']
        if stripped[0] in bullet_chars:
            return True
        if stripped.startswith('- ') or stripped.startswith('– ') or \
           stripped.startswith('— '):
            return True
        if re.match(r'^\d+[\.\)]\s', stripped):
            return True
        if re.match(r'^[a-zA-Z][\.\)]\s', stripped):
            return True
        if re.match(r'^[ivxlcdm]+[\.\)]\s', stripped, re.IGNORECASE):
            return True
        return False

    def is_heading(self, span, is_first_on_page: bool = False) -> bool:
        """
        Prüft ob Span eine Überschrift ist.
        Dynamisch basierend auf normal_size und max_size.
        """
        if isinstance(span, dict):
            text = span.get('text', '')
            size = span.get('size', 12.0)
            bold = span.get('bold', False)
        else:
            text = getattr(span, 'text', '')
            size = getattr(span, 'size', 12.0)
            bold = getattr(span, 'bold', False)

        # Ausschlusskriterien
        has_date = bool(re.search(r'\d{1,2}/\d{4}|\d{4}\s*[-–]', text))
        is_label = bool(re.match(r'^\w[\w\s/]+:\s', text))
        is_long  = len(text.strip()) > 80

        if has_date or is_label or is_long:
            return False

        # Regel 1: Größer als Fließtext + bold
        if size >= self._heading_size and bold:
            return True

        # Regel 2: GROSSBUCHSTABEN + bold + kurz
        if bold and text.strip().isupper() and len(text.strip()) < 60:
            return True

        return False

    def is_label(self, text: str) -> bool:
        """Prüft ob Text ein Label ist (endet mit Doppelpunkt)."""
        return text.strip().endswith(':') if text else False

    def is_sentence(self, text: str) -> bool:
        """Prüft ob Text ein Satz ist."""
        if not text:
            return False
        return text.strip().endswith(('.', '!', '?'))

    def is_paragraph(self, block_spans: List) -> bool:
        """Erkennt Absätze (mehrere Zeilen, keine Bullets, konsistente Formatierung)."""
        if len(block_spans) < 2:
            return False
        for span in block_spans:
            text = self._get(span, 'text', '')
            if self.is_bullet(text):
                return False
        x_positions = list(set(self._get(s, 'x', 0) for s in block_spans))
        if len(x_positions) > 2:
            return False
        sizes = list(set(round(self._get(s, 'size', 12.0), 1) for s in block_spans))
        if len(sizes) > 2:
            return False
        return True

    # ── Block-Merge Erkennung (Fortsetzung) ───────────────────────────────────

    @staticmethod
    def line_fingerprint(line_spans, text: str) -> tuple:
        """
        Struktureller Fingerprint einer Zeile.
        NUR Formatierung + Zahlenmuster — keine Wörter.
        Returns: (hat_datum, hat_doppelpunkt, hat_bullet, bold, size_cat, indent_cat)
        """
        import re
        rep = line_spans[0]
        t = text.strip()
        return (
            bool(re.search(r'\d{1,2}/\d{4}|\b(19|20)\d{2}\b', t)),  # hat_datum
            bool(re.search(r':\s', t)),                               # hat_doppelpunkt
            bool(re.match(r'^[•\-–►\-]', t)),                        # hat_bullet
            getattr(rep, 'bold', False),                              # bold
            'H' if getattr(rep, 'size', 12.0) >= 13.0 else 'N',      # size_cat
            'R' if getattr(rep, 'x', 0) > 100 else 'L',              # indent_cat
        )

    @staticmethod
    def block_fingerprint(block: list) -> list:
        """Fingerprint der ersten 5 Zeilen eines Blocks."""
        fps = []
        for item in block[:5]:
            if len(item) == 3:
                line, text, _ = item
            else:
                continue
            fps.append(StructureAnalyzer.line_fingerprint(line, text))
        return fps

    @staticmethod
    def fingerprint_similarity(fps_a: list, fps_b: list) -> float:
        """Strukturelle Ähnlichkeit zweier Block-Fingerprints (0.0 - 1.0)."""
        if not fps_a or not fps_b:
            return 0.0
        n = min(len(fps_a), len(fps_b), 5)
        return sum(fps_a[i] == fps_b[i] for i in range(n)) / n

    @staticmethod
    def should_merge_continuation(block_a: list, block_b: list) -> bool:
        """
        Prüft ob Block B eine Fortsetzung von Block A ist.

        Regel (nur Muster, keine Wörter):
        - A beginnt mit Datum-Muster
        - B beginnt NICHT mit Datum-Muster
        - B ist keine Überschrift (heading)
        - B hat mehr als 1 Zeile ODER beginnt mit Doppelpunkt-Muster
        - Fingerprint-Ähnlichkeit < 0.5 (verschiedene Struktur)
        """
        if not block_a or not block_b:
            return False

        fps_a = StructureAnalyzer.block_fingerprint(block_a)
        fps_b = StructureAnalyzer.block_fingerprint(block_b)

        if not fps_a or not fps_b:
            return False

        a_hat_datum  = fps_a[0][0]
        b_hat_datum  = fps_b[0][0]
        b_ist_heading = fps_b[0][3] and fps_b[0][4] == 'H'
        b_hat_doppelpunkt = fps_b[0][1]
        b_mehr_zeilen = len(block_b) > 1
        sim = StructureAnalyzer.fingerprint_similarity(fps_a, fps_b)

        return (
            a_hat_datum and
            not b_hat_datum and
            not b_ist_heading and
            (b_hat_doppelpunkt or b_mehr_zeilen) and
            sim < 0.5
        )
