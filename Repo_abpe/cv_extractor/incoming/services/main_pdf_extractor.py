"""
services/pdf_extractor.py
PDF-Extraktion mit X+Y-Sortierung und Zeilen-Zusammenfuehrung.

Debug-Steuerung via settings.json:
  "debug": { "pdf_extractor": true }
  → speichert extrahierten Text nach data/extracted/{dir}/{aid}_{ver}.txt

OCR-Fallback:
  Wenn kein Text-Layer gefunden (Vektorpfade, gescannte PDFs):
  → Seiten rastern (2x = ~150 DPI)
  → pytesseract.image_to_data()
  → ExtractedSpan aus Bounding-Boxes
  → size aus Zeilenhöhe, bold aus Großbuchstaben
"""

import hashlib
import io
import logging
import os
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF

try:
    import pytesseract
    from PIL import Image as PILImage
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

logger = logging.getLogger(__name__)


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class ExtractedSpan:
    text:     str
    x:        int
    y:        int
    size:     float
    bold:     bool
    italic:   bool
    font:     str
    page:     int
    x0:        float = 0.0
    y0:        float = 0.0
    x1:        float = 0.0
    y1:        float = 0.0
    origin_x:  float = 0.0
    origin_y:  float = 0.0
    column_id: int   = -1


@dataclass
class ExtractionResult:
    text:              str
    spans:             List[ExtractedSpan]
    pages:             List[str]
    page_count:        int
    metadata:          Dict[str, Any]
    has_text_layer:    bool
    requires_ocr:      bool
    processing_time:   float
    header_y:          Optional[int] = None
    footer_y:          Optional[int] = None
    error:             Optional[str] = None
    original_text:     str = ""
    original_checksum: str = ""
    removed_text:      str = ""
    removed_checksum:  str = ""
    removed_span_count: int = 0

    @property
    def sorted_text(self) -> str:
        if not self.spans:
            return self.text
        return "\n".join(
            s.text for s in sorted(self.spans, key=lambda s: (s.page, s.y, s.x))
        )

    def verify_integrity(self, tolerance: int = 3) -> Tuple[bool, str]:
        if not self.original_text:
            return False, "Kein Originaltext vorhanden"
        current = hashlib.md5(self.original_text.encode()).hexdigest()
        if current != self.original_checksum:
            return False, "Original-Checksum mismatch"
        diff = abs(len(self.original_text) - (len(self.text) + len(self.removed_text)))
        if diff <= tolerance:
            return True,  f"Integritaet OK (Differenz: {diff} Zeichen)"
        return False, f"Integritaet NICHT OK (Differenz: {diff} Zeichen)"


# ── PDFExtractor ──────────────────────────────────────────────────────────────

class PDFExtractor:

    def __init__(self, config: Optional[Dict] = None):
        self.config = {
            'language':                 'deu+eng',
            'start_page':               1,
            'end_page':                 None,
            'header_footer_threshold':  0.7,
            'ocr_scale':                2.0,    # Raster-Skalierung (2.0 = ~150 DPI)
            'ocr_min_conf':             30,     # Mindest-Konfidenz für OCR-Wörter
            **(config or {}),
        }

    # ── Interne Hilfsmethoden ────────────────────────────────────────────────

    def _merge_spans_on_same_line(self,
                                  spans: List[ExtractedSpan]) -> List[ExtractedSpan]:
        if not spans:
            return []

        spans_sorted = sorted(spans, key=lambda s: (s.page, s.y, s.x))
        merged, current_line, current_y, current_page = [], [], None, None

        def flush():
            if not current_line:
                return
            text  = " ".join(s.text for s in current_line)
            first = current_line[0]
            merged.append(ExtractedSpan(
                text=text, x=first.x, y=current_y,
                size=first.size, bold=first.bold, italic=first.italic,
                font=first.font, page=first.page,
                x0=first.x0, y0=first.y0,
                x1=current_line[-1].x1, y1=first.y1,
                origin_x=first.origin_x, origin_y=first.origin_y,
            ))

        for span in spans_sorted:
            new_line = (current_page != span.page or
                        (current_y is not None and abs(span.y - current_y) > 5))
            if new_line:
                flush()
                current_line = [span]
                current_y    = span.y
                current_page = span.page
            else:
                if current_line:
                    last = current_line[-1]
                    if span.x - last.x1 > 30:
                        current_line.append(ExtractedSpan(
                            text=" ", x=last.x1, y=current_y,
                            size=last.size, bold=False, italic=False,
                            font=last.font, page=current_page,
                        ))
                current_line.append(span)

        flush()
        return merged



    def _detect_columns_and_merge(self, spans: List[ExtractedSpan]) -> List[ExtractedSpan]:
        """
        Erkennt N-spaltige PDFs, trennt Spalten und merged jede Spalte separat.
        Alle signifikanten X-Luecken (>= 100px) werden als Spaltengrenze erkannt.
        Unterstuetzt 2, 3, 4+ Spalten universell.
        """
        if not spans:
            return spans

        from collections import Counter
        x_rounded = [round(getattr(s, 'x', 0) / 20) * 20 for s in spans]
        counter   = Counter(x_rounded)
        clusters  = sorted(counter.keys())

        # Alle signifikanten Luecken >= 100px finden
        split_points = []
        if len(clusters) >= 2:
            for i in range(1, len(clusters)):
                gap = clusters[i] - clusters[i-1]
                if gap >= 100:
                    split_x = (clusters[i-1] + clusters[i]) // 2
                    split_points.append(split_x)

        if not split_points:
            # Einspaltig: normal mergen
            return self._merge_spans_on_same_line(spans)

        # N+1 Spalten bilden
        n_cols = len(split_points) + 1
        col_spans = [[] for _ in range(n_cols)]

        for s in spans:
            x = getattr(s, 'x', 0)
            col = 0
            for sp in split_points:
                if x >= sp:
                    col += 1
                else:
                    break
            col_spans[col].append(s)

        # Jede Spalte separat sortieren und mergen
        result = []
        for col_id, col_list in enumerate(col_spans):
            if not col_list:
                continue
            col_sorted = sorted(col_list, key=lambda s: (s.page, s.y, s.x))
            merged = self._merge_spans_on_same_line(col_sorted)
            for s in merged:
                s.column_id = col_id
            result.extend(merged)

        logger.info(
            f"[PDF] {n_cols}spaltig erkannt: splits={split_points} | "
            f"{[len(c) for c in col_spans]} Spans pro Spalte"
        )
        return result

    def _detect_columns(self, spans: List[ExtractedSpan]) -> List[ExtractedSpan]:
        """
        Erkennt zweispaltige PDFs und sortiert Spans:
        erst linke Spalte (komplett), dann rechte Spalte.
        Erkennung: groesste X-Luecke zwischen Clustern.
        """
        if not spans:
            return spans

        # X-Cluster finden (20px Rasterung)
        from collections import Counter
        x_rounded = [round(getattr(s, 'x', 0) / 20) * 20 for s in spans]
        counter = Counter(x_rounded)
        clusters = sorted(counter.keys())

        if len(clusters) < 2:
            return spans

        # Groesste Luecke finden
        gaps = [(clusters[i] - clusters[i-1], i) for i in range(1, len(clusters))]
        max_gap, max_idx = max(gaps, key=lambda g: g[0])

        # Nur bei signifikanter Luecke (> 100px) zweispaltig behandeln
        if max_gap < 100:
            return spans

        # Spaltengrenze = Mitte der groessten Luecke
        split_x = (clusters[max_idx - 1] + clusters[max_idx]) // 2

        left  = [s for s in spans if getattr(s, 'x', 0) < split_x]
        right = [s for s in spans if getattr(s, 'x', 0) >= split_x]

        if not left or not right:
            return spans

        # Links und rechts jeweils nach Y sortieren, dann zusammenfuehren
        left_sorted  = sorted(left,  key=lambda s: (s.page, s.y))
        right_sorted = sorted(right, key=lambda s: (s.page, s.y))

        logger.info(f"[PDF] Zweispaltig erkannt: split_x={split_x} | links={len(left)} rechts={len(right)} spans")

        return left_sorted + right_sorted

    def _detect_and_remove_headers_footers(self, result: ExtractionResult):
        if not result.spans:
            return

        pages_dict: Dict[int, List] = {}
        for span in result.spans:
            pages_dict.setdefault(span.page, []).append(span)

        num_pages = len(pages_dict)
        threshold = num_pages * self.config['header_footer_threshold']

        y_counter = Counter(
            s.y for spans in pages_dict.values() for s in spans
        )

        first_page_spans = pages_dict.get(1, [])
        last_page_spans  = pages_dict.get(num_pages, [])
        first_y = min((s.y for s in first_page_spans), default=None)
        last_y  = max((s.y for s in last_page_spans),  default=None)

        for y, count in y_counter.most_common():
            if count >= threshold and y == first_y:
                result.header_y = y
                break

        for y, count in y_counter.most_common():
            if count >= threshold and y == last_y and y != result.header_y:
                result.footer_y = y
                break

        cleaned, removed = [], []
        for span in result.spans:
            (removed if span.y in (result.header_y, result.footer_y) else cleaned).append(span)

        result.spans              = cleaned
        result.text               = "\n".join(s.text for s in cleaned)
        result.removed_text       = "\n".join(s.text for s in removed)
        result.removed_checksum   = hashlib.md5(result.removed_text.encode()).hexdigest()
        result.removed_span_count = len(removed)

    # ── OCR-Fallback ─────────────────────────────────────────────────────────

    def _ocr_fallback(self, doc) -> List[ExtractedSpan]:
        """
        OCR-Fallback fuer PDFs ohne Text-Layer.
        Vektorpfade / gescannte Seiten → rastern → pytesseract → ExtractedSpan.

        Schriftgroesse:  aus Zeilenhoehe geschaetzt (h * 0.75)
        Bold:            True wenn Text GROSSBUCHSTABEN oder size >= 13
        Italic:          immer False (nicht erkennbar via OCR)
        Font:            'OCR' als Marker
        """
        if not OCR_AVAILABLE:
            logger.warning("[OCR] pytesseract/Pillow nicht installiert – kein Fallback moeglich")
            return []

        all_spans  = []
        scale      = self.config['ocr_scale']
        min_conf   = self.config['ocr_min_conf']
        lang       = self.config['language']

        for pnum in range(len(doc)):
            page = doc[pnum]

            # Seite rastern
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat)
            img = PILImage.open(io.BytesIO(pix.tobytes("png")))

            try:
                data = pytesseract.image_to_data(
                    img, lang=lang,
                    output_type=pytesseract.Output.DICT
                )
            except Exception as e:
                logger.warning(f"[OCR] Seite {pnum+1} fehlgeschlagen: {e}")
                continue

            # Zeilen aus Wort-Bounding-Boxes rekonstruieren
            line_map: Dict[tuple, Dict] = {}
            for i in range(len(data['text'])):
                word = data['text'][i].strip()
                if not word:
                    continue
                try:
                    conf = int(data['conf'][i])
                except (ValueError, TypeError):
                    conf = 0
                if conf < min_conf:
                    continue

                key = (data['block_num'][i], data['par_num'][i], data['line_num'][i])
                if key not in line_map:
                    line_map[key] = {
                        'words': [],
                        'x':     data['left'][i],
                        'y':     data['top'][i],
                        'h':     data['height'][i],
                    }
                line_map[key]['words'].append(word)

            # ExtractedSpan pro Zeile bauen
            for key in sorted(line_map.keys()):
                ln   = line_map[key]
                text = ' '.join(ln['words']).strip()
                if not text:
                    continue

                # Koordinaten auf Original-Seitenkoordinaten skalieren
                x = round(ln['x'] / scale)
                y = round(ln['y'] / scale)
                h = ln['h'] / scale

                # Schriftgroesse aus Zeilenhoehe schaetzen
                size = round(h * 0.75, 1)
                size = max(6.0, min(size, 48.0))

                # Bold heuristisch
                t    = text.strip()
                bold = (t.isupper() and len(t) > 2) or size >= 13.0

                all_spans.append(ExtractedSpan(
                    text=text,
                    x=x, y=y,
                    size=size,
                    bold=bold,
                    italic=False,
                    font='OCR',
                    page=pnum + 1,
                    x0=float(x),
                    y0=float(y),
                    x1=float(x + round(ln['h'] / scale)),
                    y1=float(y + round(h)),
                    origin_x=float(x),
                    origin_y=float(y),
                ))

        logger.info(f"[OCR] {len(all_spans)} Spans aus {len(doc)} Seiten extrahiert")
        return all_spans

    # ── Oeffentliche Methoden ────────────────────────────────────────────────

    def extract(self, pdf_path: str) -> ExtractionResult:
        start = time.time()

        if not os.path.exists(pdf_path):
            return ExtractionResult(
                text="", spans=[], pages=[], page_count=0, metadata={},
                has_text_layer=False, requires_ocr=False, processing_time=0,
                error=f"Datei nicht gefunden: {pdf_path}",
            )

        try:
            doc        = fitz.open(pdf_path)
            all_spans  = []
            pages_text = []
            metadata   = {k: doc.metadata.get(k, '')
                          for k in ('title', 'author', 'subject', 'creator', 'producer')}

            page_count = len(doc)
            pg_start   = max(0, self.config['start_page'] - 1)
            pg_end     = self.config['end_page'] or page_count

            for pnum in range(pg_start, min(pg_end, page_count)):
                page = doc[pnum]
                pages_text.append(page.get_text())
                data = page.get_text("dict")

                for block in data['blocks']:
                    for line in block.get('lines', []):
                        for span in line['spans']:
                            text = span['text'].strip()
                            if not text:
                                continue
                            # Seitenzahlen herausfiltern
                            if text.lower().startswith('seite ') and 'von' in text.lower():
                                continue

                            bbox   = span['bbox']
                            origin = span['origin']
                            flags  = span['flags']

                            all_spans.append(ExtractedSpan(
                                text=text,
                                x=round(origin[0]),
                                y=round(origin[1]),
                                size=round(span['size'], 1),
                                bold=bool(flags & 16),
                                italic=bool(flags & 2),
                                font=span['font'],
                                page=pnum + 1,
                                x0=round(bbox[0], 1), y0=round(bbox[1], 1),
                                x1=round(bbox[2], 1), y1=round(bbox[3], 1),
                                origin_x=round(origin[0], 1),
                                origin_y=round(origin[1], 1),
                            ))

            all_spans = self._detect_columns_and_merge(all_spans)
            # KEIN sort hier — _detect_columns_and_merge liefert bereits
            # korrekte Reihenfolge: erst alle col=0, dann alle col=1

            # ── OCR-Fallback wenn kein Text-Layer ────────────────────────────
            if not all_spans:
                logger.info(f"[OCR] Kein Text-Layer in {pdf_path} – starte OCR-Fallback")
                ocr_spans = self._ocr_fallback(doc)
                if ocr_spans:
                    full_text = "\n".join(s.text for s in ocr_spans)
                    result = ExtractionResult(
                        text=full_text,
                        spans=ocr_spans,
                        pages=pages_text,
                        page_count=page_count,
                        metadata=metadata,
                        has_text_layer=False,
                        requires_ocr=True,
                        processing_time=0,
                    )
                    result.original_text     = full_text
                    result.original_checksum = hashlib.md5(full_text.encode()).hexdigest()
                    # Header/Footer-Erkennung auch fuer OCR
                    self._detect_and_remove_headers_footers(result)
                    result.processing_time = time.time() - start
                    logger.info(f"[OCR] Fertig: {len(ocr_spans)} Spans, "
                                f"{result.processing_time:.1f}s")
                    return result
                else:
                    logger.warning(f"[OCR] Kein Text extrahierbar: {pdf_path}")
                    return ExtractionResult(
                        text="", spans=[], pages=pages_text,
                        page_count=page_count, metadata=metadata,
                        has_text_layer=False, requires_ocr=True,
                        processing_time=time.time() - start,
                        error="Kein Text-Layer und OCR lieferte keine Ergebnisse",
                    )

            # ── Normaler Pfad ─────────────────────────────────────────────────
            full_text = "\n".join(s.text for s in all_spans)

            result = ExtractionResult(
                text=full_text, spans=all_spans, pages=pages_text,
                page_count=page_count, metadata=metadata,
                has_text_layer=True, requires_ocr=False, processing_time=0,
            )
            result.original_text     = result.text
            result.original_checksum = hashlib.md5(result.original_text.encode()).hexdigest()
            self._detect_and_remove_headers_footers(result)
            result.processing_time   = time.time() - start
            return result

        except Exception as e:
            logger.exception(f"Fehler bei PDF-Extraktion: {e}")
            return ExtractionResult(
                text="", spans=[], pages=[], page_count=0, metadata={},
                has_text_layer=False, requires_ocr=False,
                processing_time=time.time() - start, error=str(e),
            )

    def save_extracted_text(self, text: str, consultant_dir: str,
                            aid: str, version: str) -> Optional[str]:
        """
        Speichert extrahierten Text als .txt Datei.
        Nur bei debug.pdf_extractor=true oder debug.global=true.
        Pfad: data/extracted/{consultant_dir}/{aid}_{version}.txt
        """
        if not self._debug_enabled('pdf_extractor'):
            return None

        from django.conf import settings
        base = os.path.join(settings.BASE_DIR, 'data', 'extracted', consultant_dir)
        os.makedirs(base, exist_ok=True)

        filepath = os.path.join(base, f"{aid}_{version}.txt")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text)

        logger.info(f"[DEBUG] TXT gespeichert: {filepath}")
        return filepath

    @staticmethod
    def _debug_enabled(module: str) -> bool:
        """Liest debug-Schalter aus settings.json."""
        try:
            import json
            from django.conf import settings
            cfg_path = os.path.join(settings.BASE_DIR, 'settings.json')
            with open(cfg_path) as f:
                cfg = json.load(f)
            debug = cfg.get('debug', {})
            if debug.get('global', False):
                return True
            return debug.get(module, False)
        except Exception:
            return False


pdf_extractor = PDFExtractor()
