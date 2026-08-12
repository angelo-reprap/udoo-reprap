"""
block_detector.py - Erkennt Blöcke und gruppiert Projekte

UNIVERSELLE ERKENNUNG (format-unabhaengig):
- Erfahrungsbereich: Liste bekannter Ueberschriften (DE+EN+Varianten)
- Projekt-Start:     Datum PLUS mindestens 3 weitere Projekt-Signale
- Block-Bildung:     6 Formatattribute (size, bold, italic, font, y-gap, page)
- Seitenumbruch:     Fortsetzung wenn gleiche Formatierung, sonst neuer Block
- Merge:             StructureAnalyzer.should_merge_continuation() (Muster-basiert)

Changelog:
  2026-04-22: Block-Split auf 6 Formatattribute erweitert (statt nur y-Abstand)
              Seitenumbruch-Logik: Fortsetzung bei gleicher Formatierung
              StructureAnalyzer.should_merge_continuation() als Post-Processing
"""

import re
from typing import List, Tuple, Optional
from dataclasses import dataclass, field
from collections import Counter


# ── Erfahrungsbereich-Erkennung ───────────────────────────────────────────────
EXPERIENCE_SECTION_KEYWORDS = [
    # Deutsch
    'berufliche erfahrungen', 'berufserfahrung', 'berufliche tätigkeiten',
    'berufstätigkeit', 'beruflicher werdegang', 'werdegang',
    'projekthistorie', 'projekterfahrung', 'projektübersicht',
    'projekttätigkeiten', 'berufliche stationen',
    # Englisch
    'work experience', 'professional experience', 'employment history',
    'career history', 'project experience', 'work history',
    'professional background', 'career overview',
]

# ── Projekt-Signal-Patterns ───────────────────────────────────────────────────
PERIOD_PATTERNS = [
    re.compile(r'\b\d{1,2}/\d{4}\b'),
    re.compile(r'\b\d{4}\s*[-–—]\s*(\d{4}|dato|heute|present|current)\b', re.I),
    re.compile(r'\b(dato|heute|present|current)\b', re.I),
    re.compile(r'\b(zeitraum|periode|von[/\s]bis|period|duration)\s*[:.]', re.I),
]

COMPANY_PATTERNS = [
    re.compile(r'\b(kunde|firma|unternehmen|arbeitgeber|auftraggeber)\s*[:./]', re.I),
    re.compile(r'\b(company|client|employer|organization)\s*[:./]', re.I),
    re.compile(r'\b(gmbh|ag|kg|inc|ltd|llc|corp|se\b|ug\b)\b', re.I),
    re.compile(r'\b(bank|versicherung|ministerium|rechenzentrum|institut)\b', re.I),
]

ROLE_PATTERNS = [
    re.compile(r'\b(rolle|position|funktion|titel|designation)\s*[:./]', re.I),
    re.compile(r'\b(role|job title|title)\s*[:./]', re.I),
    re.compile(r'\b(engineer|architekt|architect|developer|entwickler|'
               r'consultant|berater|manager|administrator|experte|'
               r'spezialist|analyst|lead|senior|junior)\b', re.I),
]

ACTIVITY_PATTERNS = [
    re.compile(r'\b(aufgabe|aufgaben|tätigkeit|projekttätigkeit|'
               r'verantwortlich|zuständig|durchführung)\s*[:./]', re.I),
    re.compile(r'\b(activities|responsibilities|tasks|duties)\s*[:./]', re.I),
    re.compile(r'^\s*[•·▪▸\-–]\s+\w', re.MULTILINE),
    re.compile(r'\b(administration|konfiguration|installation|'
               r'implementierung|migration|betrieb|entwicklung)\b', re.I),
]

TECHNOLOGY_PATTERNS = [
    re.compile(r'\b(umfeld|technolog|systemumgebung|eingesetzt|verwendet)\s*[:./]', re.I),
    re.compile(r'\b(technologies|tools|stack|environment|tech stack)\s*[:./]', re.I),
    re.compile(r'\b(linux|windows|cisco|fortigate|python|java|sql|'
               r'ansible|docker|kubernetes|vmware|azure|aws)\b', re.I),
]

LOCATION_PATTERNS = [
    re.compile(r'\b(einsatzort|standort|ort|location|place)\s*[:./]', re.I),
    re.compile(r'\bin\s+[A-ZÄÖÜ][a-zäöü]+\b'),
]

INDUSTRY_PATTERNS = [
    re.compile(r'\b(branche|industrie|sektor|industry|sector)\s*[:./]', re.I),
    re.compile(r'\b(pharma|banking|versicherung|logistik|automotive|'
               r'telekommunikation|luftfahrt|energie|handel|gesundheit)\b', re.I),
]

PROJECT_MIN_SCORE = 4


@dataclass
class Block:
    index:      int
    start_y:    int
    end_y:      int
    spans:      List
    text:       str
    first_line: str


@dataclass
class Project:
    index:  int
    blocks: List[Block] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join([b.text for b in self.blocks])

    @property
    def first_line(self) -> str:
        return self.blocks[0].first_line if self.blocks else ""


class SimpleSpan:
    def __init__(self, page, y, x, size, bold, italic, font, text):
        self.page   = page
        self.y      = y
        self.x      = x
        self.size   = size
        self.bold   = bold
        self.italic = italic
        self.font   = font
        self.text   = text


class BlockDetector:

    def __init__(self):
        self.block_threshold = 28
        self._learned_experience_keywords = []
        self._load_learned_keywords()

    # ── Self-Learning ─────────────────────────────────────────────────────────

    def _load_learned_keywords(self):
        try:
            from apps.cv_extractor.models import TrainingTerm
            terms = TrainingTerm.objects.filter(
                category='experience_section',
                confidence__gte=0.7
            ).values_list('term', flat=True)
            self._learned_experience_keywords = [t.lower() for t in terms]
        except Exception:
            pass

    def _save_learned_keyword(self, keyword: str, category: str):
        try:
            from apps.cv_extractor.models import TrainingTerm
            TrainingTerm.objects.update_or_create(
                term=keyword.lower()[:200],
                defaults={
                    'category':   category,
                    'confidence': 0.8,
                    'source':     'block_detector',
                }
            )
        except Exception:
            pass

    # ── OCR-Modus Erkennung ──────────────────────────────────────────────────

    def _is_ocr_mode(self, spans: List) -> bool:
        """True wenn >= 80% der Spans font=OCR haben."""
        if not spans:
            return False
        ocr_count = sum(1 for s in spans if getattr(s, 'font', '') == 'OCR')
        return (ocr_count / len(spans)) >= 0.8

    # ── Erfahrungsbereich-Erkennung ───────────────────────────────────────────

    def _is_experience_section(self, text: str) -> bool:
        text_lower = text.lower().strip()
        for kw in EXPERIENCE_SECTION_KEYWORDS:
            if kw in text_lower:
                return True
        for kw in self._learned_experience_keywords:
            if kw in text_lower:
                return True
        return False

    # ── Projekt-Start-Erkennung ───────────────────────────────────────────────

    def _project_score(self, text: str) -> int:
        score = 0
        period_found = any(p.search(text) for p in PERIOD_PATTERNS)
        if period_found:
            score += 3
        else:
            return 0
        if any(p.search(text) for p in COMPANY_PATTERNS):  score += 1
        if any(p.search(text) for p in ROLE_PATTERNS):     score += 1
        if any(p.search(text) for p in ACTIVITY_PATTERNS): score += 1
        if any(p.search(text) for p in TECHNOLOGY_PATTERNS): score += 1
        if any(p.search(text) for p in LOCATION_PATTERNS): score += 1
        if any(p.search(text) for p in INDUSTRY_PATTERNS): score += 1
        return score

    def _is_project_start(self, text: str) -> bool:
        return self._project_score(text) >= PROJECT_MIN_SCORE

    # ── Spans zusammenfuehren (gleiche Y-Position) ────────────────────────────

    def _merge_spans_same_y(self, spans: List) -> List:
        if not spans:
            return []
        spans_sorted = sorted(spans, key=lambda s: (s.page, getattr(s, "column_id", -1), s.y, s.x))
        merged = []
        current_group = []
        current_y = None

        for span in spans_sorted:
            y = span.y
            if current_y is None or abs(y - current_y) <= 10:
                current_group.append(span)
                current_y = y
            else:
                merged_text = " ".join([s.text for s in current_group])
                first = current_group[0]
                sp = SimpleSpan(
                    page=first.page, y=current_y, x=first.x,
                    size=first.size, bold=first.bold, italic=first.italic,
                    font=first.font, text=merged_text
                )
                sp.column_id = getattr(first, 'column_id', -1)
                merged.append(sp)
                current_group = [span]
                current_y = y

        if current_group:
            merged_text = " ".join([s.text for s in current_group])
            first = current_group[0]
            sp = SimpleSpan(
                page=first.page, y=current_y, x=first.x,
                size=first.size, bold=first.bold, italic=first.italic,
                font=first.font, text=merged_text
            )
            sp.column_id = getattr(first, 'column_id', -1)
            merged.append(sp)
        return merged

    # ── Haupt-Methode ─────────────────────────────────────────────────────────

    def detect(self, spans: List) -> Tuple[List[Project], dict]:
        """
        Hauptmethode: Spans → Blöcke → Gruppen/Projekte.

        Schritt 1: Y-Abstände analysieren → block_threshold
        Schritt 2: Spans auf gleicher Y-Position zusammenführen
        Schritt 3: Initiale Blöcke durch 6 Formatattribute erkennen
        Schritt 4: Fortsetzungs-Merge via StructureAnalyzer (Muster-basiert)
        Schritt 5: Block-Objekte erstellen
        Schritt 6: Projekte gruppieren
        """

        # ── OCR-Modus: an OCRBlockDetector delegieren ───────────────────────────
        if self._is_ocr_mode(spans):
            from .block_detector_ocr import OCRBlockDetector
            return OCRBlockDetector().detect(spans)

        # ── Schritt 1: Y-Abstände analysieren → block_threshold ───────────────
        spans_sorted = sorted(spans, key=lambda s: (s.page, getattr(s, "column_id", -1), s.y))

        y_gaps = []
        for i in range(1, len(spans_sorted)):
            if spans_sorted[i].page == spans_sorted[i-1].page:
                gap = spans_sorted[i].y - spans_sorted[i-1].y
                if 0 < gap < 100:
                    y_gaps.append(gap)

        if y_gaps:
            gap_counter = Counter(y_gaps)
            normal_gap = gap_counter.most_common(1)[0][0]
            self.block_threshold = normal_gap * 1.5

        # ── Schritt 2: Spans auf gleicher Y-Position zusammenführen ──────────
        y_spans = self._merge_spans_same_y(spans)
        y_spans_sorted = sorted(y_spans, key=lambda s: (s.page, getattr(s, "column_id", -1), s.y))

        # ── Schritt 3: Initiale Blöcke durch 6 Formatattribute ───────────────
        # Attribute: size, bold, italic, font, y-gap, page
        # Seitenumbruch: Fortsetzung wenn gleiche Formatierung
        initial_blocks = []
        current_block  = []
        prev_span      = None

        for span in y_spans_sorted:
            split = False

            if prev_span is not None:
                bold_change   = span.bold   != prev_span.bold
                size_change   = abs(span.size - prev_span.size) >= 1.0
                font_change   = bool(span.font and prev_span.font and
                                     span.font != prev_span.font)
                italic_change = span.italic != prev_span.italic
                fmt_change    = bold_change or size_change or font_change or italic_change

                # Spaltenübergang → immer neuer Block
                prev_col = getattr(prev_span, 'column_id', -1)
                curr_col = getattr(span, 'column_id', -1)
                if prev_col != curr_col and prev_col != -1 and curr_col != -1:
                    split = True
                elif span.page != prev_span.page:
                    # Seitenumbruch: nur splitten wenn Formatwechsel
                    if fmt_change:
                        split = True
                else:
                    # Gap mit Seitenzahl gewichtet
                    page_diff = (span.page - prev_span.page) * 10000
                    gap = page_diff + span.y - prev_span.y
                    if gap > self.block_threshold * 1.5:
                        split = True
                    elif gap >= self.block_threshold and fmt_change:
                        split = True

            if split and current_block:
                initial_blocks.append(current_block)
                current_block = []

            current_block.append(span)
            prev_span = span

        if current_block:
            initial_blocks.append(current_block)

        # ── Schritt 4: Fortsetzungs-Merge (Muster-basiert) ───────────────────
        # StructureAnalyzer prüft ob Block B Fortsetzung von Block A ist
        # Regel: nur Fingerprint-Muster, keine Wörter
        try:
            from .structure_analyzer import StructureAnalyzer

            def _to_labeled(block_spans):
                text = ' '.join(s.text for s in block_spans)
                return [(block_spans, text, '')]

            merged_initial = []
            j = 0
            while j < len(initial_blocks):
                block = initial_blocks[j]
                if (j + 1 < len(initial_blocks) and
                        StructureAnalyzer.should_merge_continuation(
                            _to_labeled(block),
                            _to_labeled(initial_blocks[j + 1])
                        )):
                    merged_initial.append(block + initial_blocks[j + 1])
                    j += 2
                else:
                    merged_initial.append(block)
                    j += 1
            initial_blocks = merged_initial
        except Exception:
            pass  # Fallback: original initial_blocks

        # ── Schritt 5: Block-Objekte erstellen ───────────────────────────────
        blocks = []
        for idx, block_spans in enumerate(initial_blocks):
            text       = " ".join([s.text for s in block_spans])
            first_line = block_spans[0].text[:60] if block_spans else ""
            blocks.append(Block(
                index      = idx + 1,
                start_y    = block_spans[0].y,
                end_y      = block_spans[-1].y,
                spans      = block_spans,
                text       = text,
                first_line = first_line,
            ))

        # ── Schritt 6: Projekte gruppieren ───────────────────────────────────
        projects        = []
        current_project = None
        in_experience   = False
        project_starts  = 0

        for block in blocks:

            if not in_experience and self._is_experience_section(block.text):
                in_experience = True
                standalone = Project(index=len(projects) + 1)
                standalone.blocks.append(block)
                projects.append(standalone)
                continue

            if in_experience:
                score = self._project_score(block.text)

                if score >= PROJECT_MIN_SCORE:
                    if current_project:
                        projects.append(current_project)
                    current_project = Project(index=len(projects) + 1)
                    current_project.blocks.append(block)
                    project_starts += 1

                elif current_project is not None:
                    current_project.blocks.append(block)

                else:
                    standalone = Project(index=len(projects) + 1)
                    standalone.blocks.append(block)
                    projects.append(standalone)

            else:
                standalone = Project(index=len(projects) + 1)
                standalone.blocks.append(block)
                projects.append(standalone)

        if current_project:
            projects.append(current_project)

        stats = {
            'total_blocks':    len(blocks),
            'total_projects':  len(projects),
            'project_starts':  project_starts,
            'block_threshold': self.block_threshold,
            'in_experience_found': in_experience,
        }

        return projects, stats


block_detector = BlockDetector()
