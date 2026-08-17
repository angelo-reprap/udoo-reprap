"""
block_detector_ocr.py - OCR-spezifische Block-Erkennung

Wird von block_detector.py aufgerufen wenn alle Spans font=OCR haben.

Block-Typ Erkennung aus OCR-Signalen (kein Bold/Font/Size verwertbar):
  Position:   x (Einrückung), y (Zeile), page
  Text-Muster: CAPS, Bullets, Datum, Abschluss, Institution, Firma, Rolle
  Größe:      sz aus Zeilenhöhe (grob)

Block-Typen:
  HEADING      → CAPS ≥70%, allein oder kurz
  BULLET_LIST  → >50% Zeilen beginnen mit Bullet-Zeichen
  PROJECT      → Datum + Rolle/Firma (x<80)
  EDUCATION    → Datum + Abschluss/Institution
  SKILLS_LABEL → "Sprachen:" "Tools:" "Kenntnisse:" etc.
  CONTACT      → Email/Tel/Web
  PROSE        → langer Fließtext ohne Bullets
  MIXED        → Gemischt / nicht eindeutig

stats['block_types'] = {group_index: block_type, ...}
→ block_labeler.py liest das aus und baut Marker in LLM-Input

Schnittstelle identisch zu BlockDetector.detect():
  groups, stats = OCRBlockDetector().detect(spans)
  → List[Project], dict
"""

import re
import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional

logger = logging.getLogger(__name__)

# ── Patterns ──────────────────────────────────────────────────────────────────

PERIOD_PATTERNS = [
    re.compile(r'\b\d{1,2}/\d{4}\b'),
    re.compile(r'\b\d{4}\s*[-–—]\s*(\d{4}|dato|heute|present|current)\b', re.I),
    re.compile(r'\b\d{2}/\d{4}\s*[-–]\s*(heute|\d{2}/\d{4})\b', re.I),
    re.compile(r'\b\d{4}\s*-\s*\d{4}\b'),
    re.compile(r'\b\d{4}\s*-\s*heute\b', re.I),
]

BULLET_CHARS = re.compile(
    r'^\s*[•·▪▸\*\-–—©«►➢→❯›\+]\s+\w', re.MULTILINE
)

DEGREE_PATTERNS = re.compile(
    r'\b(m\.sc|b\.sc|b\.a|m\.a|dipl\.|bachelor|master|'
    r'diplom|dr\.|phd|mba|staatsexamen|abitur|ausbildung)\b', re.I
)

INSTITUTION_PATTERNS = re.compile(
    r'\b(universität|hochschule|fachhochschule|akademie|'
    r'schule|institut|college|university|school)\b', re.I
)

COMPANY_PATTERNS = [
    re.compile(r'\b(gmbh|ag|kg|inc|ltd|llc|corp|se\b|ug\b|b\.v\.)\b', re.I),
    re.compile(r'\b(bank|versicherung|ministerium|rechenzentrum|konzern)\b', re.I),
]

ROLE_PATTERNS = re.compile(
    r'\b(engineer|architekt|architect|developer|entwickler|'
    r'consultant|berater|manager|administrator|experte|'
    r'spezialist|analyst|lead|senior|junior|director|'
    r'managerin|beraterin|dozentin|freelancer)\b', re.I
)

SKILLS_LABEL_PATTERNS = re.compile(
    r'^(sprachen|languages|tools|skills|kenntnisse|kompetenzen|'
    r'fachkenntnisse|it-kenntnisse|software|technologien|'
    r'zertifikate|zertifizierungen|certifications)\s*[:\-]?', re.I
)

CONTACT_PATTERNS = re.compile(
    r'(e-mail|email|tel\.|telefon|phone|mobil|mobile|'
    r'www\.|http|linkedin|xing|adresse|address)\s*[:\.]?', re.I
)

EXPERIENCE_SECTION_KEYWORDS = [
    'berufliche erfahrungen', 'berufserfahrung', 'berufliche tätigkeiten',
    'berufstätigkeit', 'beruflicher werdegang', 'werdegang',
    'projekthistorie', 'projekterfahrung', 'projektübersicht',
    'projekttätigkeiten', 'berufliche stationen',
    'relevante erfahrung', 'berufspraxis',
    'work experience', 'professional experience', 'employment history',
    'career history', 'project experience', 'work history',
]

PROJECT_MIN_SCORE = 3


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class Block:
    index:      int
    start_y:    int
    end_y:      int
    spans:      List
    text:       str
    first_line: str
    block_type: str = 'MIXED'   # NEU: vom OCR-Detector gesetzt


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

    @property
    def block_type(self) -> str:
        """Block-Typ der ersten Block-Gruppe."""
        return self.blocks[0].block_type if self.blocks else 'MIXED'


# ── OCRBlockDetector ──────────────────────────────────────────────────────────

class OCRBlockDetector:

    def detect(self, spans: List) -> Tuple[List[Project], dict]:
        if not spans:
            return [], {
                'total_blocks': 0, 'total_projects': 0,
                'project_starts': 0, 'block_threshold': 0,
                'in_experience_found': False, 'ocr_mode': True,
                'block_types': {},
            }

        spans_sorted = sorted(spans, key=lambda s: (s.page, s.y, s.x))

        # ── Schritt 1: Y-Abstände → threshold ────────────────────────────────
        y_gaps = []
        for i in range(1, len(spans_sorted)):
            if spans_sorted[i].page == spans_sorted[i-1].page:
                gap = spans_sorted[i].y - spans_sorted[i-1].y
                if 0 < gap < 80:
                    y_gaps.append(gap)

        if y_gaps:
            gap_counter = Counter(y_gaps)
            normal_gap  = gap_counter.most_common(1)[0][0]
            threshold   = max(normal_gap * 3.0, 18)
        else:
            normal_gap = 12
            threshold  = 18

        logger.info(f"[OCR-Detector] {len(spans)} Spans | "
                    f"normal_gap={normal_gap} | threshold={threshold:.0f}")

        # ── Schritt 2: Spans → initiale Blöcke ───────────────────────────────
        raw_blocks: List[List] = []
        current:    List       = []
        prev                   = spans_sorted[0]
        current.append(prev)

        for span in spans_sorted[1:]:
            split  = False

            if span.page != prev.page:
                split = True
            elif self._is_caps_heading(span.text):
                split = True
            elif self._is_caps_heading(prev.text):
                split = True
            elif self._has_date(span.text) and span.x < 80:
                split = True
            elif (span.y - prev.y) > threshold:
                split = True
            elif prev.x > 100 and span.x < 80:
                split = True

            if split:
                if current:
                    raw_blocks.append(current)
                current = [span]
            else:
                current.append(span)

            prev = span

        if current:
            raw_blocks.append(current)

        logger.info(f"[OCR-Detector] {len(raw_blocks)} initiale Blöcke")

        # ── Schritt 3: Block-Objekte bauen + block_type ermitteln ─────────────
        blocks: List[Block] = []
        for idx, block_spans in enumerate(raw_blocks):
            text       = " ".join(s.text for s in block_spans)
            first_line = block_spans[0].text[:60] if block_spans else ""
            btype      = self._classify_block(block_spans, text)
            blocks.append(Block(
                index      = idx + 1,
                start_y    = block_spans[0].y,
                end_y      = block_spans[-1].y,
                spans      = block_spans,
                text       = text,
                first_line = first_line,
                block_type = btype,
            ))
            logger.debug(f"[OCR] Block {idx+1}: {btype:15s} | {first_line[:50]}")

        # ── Schritt 4: Continuation-Merge ────────────────────────────────────
        try:
            from .structure_analyzer import StructureAnalyzer

            def _to_labeled(block_spans):
                text = ' '.join(s.text for s in block_spans)
                return [(block_spans, text, '')]

            merged = []
            j = 0
            while j < len(blocks):
                b = blocks[j]
                if (j + 1 < len(blocks) and
                        StructureAnalyzer.should_merge_continuation(
                            _to_labeled(b.spans),
                            _to_labeled(blocks[j+1].spans)
                        )):
                    combined   = b.spans + blocks[j+1].spans
                    text       = " ".join(s.text for s in combined)
                    # Block-Typ nach Merge neu bestimmen
                    btype      = self._classify_block(combined, text)
                    merged.append(Block(
                        index      = b.index,
                        start_y    = b.start_y,
                        end_y      = blocks[j+1].end_y,
                        spans      = combined,
                        text       = text,
                        first_line = b.first_line,
                        block_type = btype,
                    ))
                    j += 2
                else:
                    merged.append(b)
                    j += 1
            blocks = merged
            logger.info(f"[OCR-Detector] nach Merge: {len(blocks)} Blöcke")
        except Exception as e:
            logger.debug(f"[OCR-Detector] StructureAnalyzer skip: {e}")

        # ── Schritt 5: Projekte gruppieren ───────────────────────────────────
        projects, project_starts, in_experience = self._group_projects(blocks)

        # block_types map für block_labeler
        block_types = {}
        for g in projects:
            for b in g.blocks:
                block_types[g.index] = b.block_type

        stats = {
            'total_blocks':        len(blocks),
            'total_projects':      len(projects),
            'project_starts':      project_starts,
            'block_threshold':     threshold,
            'in_experience_found': in_experience,
            'ocr_mode':            True,
            'normal_gap':          normal_gap,
            'block_types':         block_types,
        }

        logger.info(f"[OCR-Detector] {len(projects)} Gruppen | "
                    f"in_experience={in_experience}")
        return projects, stats

    # ── Block-Typ Erkennung ───────────────────────────────────────────────────

    def _classify_block(self, spans: List, text: str) -> str:
        """
        Ermittelt den Block-Typ aus OCR-Signalen.

        Priorität:
          1. HEADING      → CAPS-Zeile allein oder kurz
          2. CONTACT      → Email/Tel/Web
          3. SKILLS_LABEL → "Sprachen:" "Tools:" etc.
          4. EDUCATION    → Datum + Abschluss/Institution
          5. PROJECT      → Datum + Rolle/Firma
          6. BULLET_LIST  → >50% Bullet-Zeilen
          7. PROSE        → langer Fließtext
          8. MIXED        → alles andere
        """
        if not spans:
            return 'MIXED'

        first_line = spans[0].text.strip()
        n_spans    = len(spans)
        lines      = [s.text.strip() for s in spans if s.text.strip()]

        # 1. HEADING
        if self._is_caps_heading(first_line):
            return 'HEADING'

        # 2. CONTACT
        if CONTACT_PATTERNS.search(text):
            # nur wenn kurz und keine Projekte
            if n_spans <= 3 and not self._has_date(text):
                return 'CONTACT'

        # 3. SKILLS_LABEL
        if SKILLS_LABEL_PATTERNS.match(first_line):
            return 'SKILLS_LABEL'

        # 4. EDUCATION
        if self._has_date(text):
            if DEGREE_PATTERNS.search(text) or INSTITUTION_PATTERNS.search(text):
                return 'EDUCATION'

        # 5. PROJECT
        if self._has_date(text) and spans[0].x < 80:
            if (ROLE_PATTERNS.search(text) or
                    any(p.search(text) for p in COMPANY_PATTERNS)):
                return 'PROJECT'
            # Datum allein reicht auch
            if self._project_score(text) >= PROJECT_MIN_SCORE:
                return 'PROJECT'

        # 6. BULLET_LIST
        bullet_count = sum(1 for l in lines if BULLET_CHARS.match(l))
        if lines and (bullet_count / len(lines)) >= 0.4:
            return 'BULLET_LIST'

        # 7. PROSE
        long_lines = sum(1 for l in lines if len(l) > 60)
        if lines and (long_lines / len(lines)) >= 0.5:
            return 'PROSE'

        return 'MIXED'

    # ── Gruppierung ───────────────────────────────────────────────────────────

    def _group_projects(self,
                        blocks: List[Block]) -> Tuple[List[Project], int, bool]:
        projects        = []
        current_project = None
        in_experience   = False
        project_starts  = 0

        for block in blocks:
            is_caps = self._is_caps_heading(block.first_line)

            # ── CAPS-Überschrift ──────────────────────────────────────────────
            if is_caps:
                if self._is_experience_section(block.text):
                    if current_project:
                        projects.append(current_project)
                        current_project = None
                    in_experience = True
                    standalone = Project(index=len(projects) + 1)
                    standalone.blocks.append(block)
                    projects.append(standalone)
                    continue

                if in_experience:
                    if current_project:
                        projects.append(current_project)
                        current_project = None
                    in_experience = False

                standalone = Project(index=len(projects) + 1)
                standalone.blocks.append(block)
                projects.append(standalone)
                continue

            # ── Im Erfahrungs-Abschnitt ───────────────────────────────────────
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

        return projects, project_starts, in_experience

    # ── Hilfsmethoden ─────────────────────────────────────────────────────────

    def _is_caps_heading(self, text: str) -> bool:
        t = text.strip()
        if len(t) < 3:
            return False
        letters = [c for c in t if c.isalpha()]
        if not letters:
            return False
        upper = sum(1 for c in letters if c.isupper())
        return (upper / len(letters)) >= 0.7

    def _has_date(self, text: str) -> bool:
        return any(p.search(text) for p in PERIOD_PATTERNS)

    def _project_score(self, text: str) -> int:
        if not self._has_date(text):
            return 0
        score = 3
        if any(p.search(text) for p in COMPANY_PATTERNS):  score += 1
        if ROLE_PATTERNS.search(text):                       score += 1
        if BULLET_CHARS.search(text):                        score += 1
        return score

    def _is_experience_section(self, text: str) -> bool:
        text_lower = text.lower().strip()
        return any(kw in text_lower for kw in EXPERIENCE_SECTION_KEYWORDS)
