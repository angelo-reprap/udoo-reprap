"""
services/main_word_extractor.py
==================================
Universeller DOCX/DOC-Extractor fuer die main_pipeline.

Unterstützte Formate:
  .docx  → direkt via python-docx (im RAM)
  .doc   → LibreOffice → tmp PDF → main_pdf_extractor → Spans im RAM
            Temp-PDF wird nach Extraktion sofort gelöscht.

RAM-Struktur (WordExtractResult):
  .ok            bool
  .error         str|None
  .filename      str
  .source_format str            'docx' oder 'doc'
  .page_count    int
  .span_count    int
  .char_count    int
  .plain_text    str
  .first_500     str
  .spans         List[dict]     kompatibel mit main_pdf_extractor
  .tables        List[dict]
  .headings      List[str]
  .meta          dict
"""

import logging
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

DEFAULT_SIZE         = 12.0
HEADING_SIZE_MIN     = 13.0
Y_STEP               = 20
Y_PAGE_OFFSET        = 1000
MAX_PLAIN_TEXT_CHARS = 50_000


@dataclass
class WordExtractResult:
    ok:            bool           = False
    error:         Optional[str]  = None
    filename:      str            = ''
    source_format: str            = ''
    page_count:    int            = 0
    span_count:    int            = 0
    char_count:    int            = 0
    plain_text:    str            = ''
    first_500:     str            = ''
    spans:         List[dict]     = field(default_factory=list)
    tables:        List[dict]     = field(default_factory=list)
    headings:      List[str]      = field(default_factory=list)
    meta:          Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.plain_text and not self.first_500:
            self.first_500 = self.plain_text[:500]


def _resolve_size(style) -> float:
    try:
        if style and style.font and style.font.size:
            return round(style.font.size.pt, 1)
        if style and style.base_style:
            return _resolve_size(style.base_style)
    except Exception:
        pass
    return DEFAULT_SIZE


def _resolve_bold(style) -> bool:
    try:
        if style and style.font and style.font.bold is not None:
            return bool(style.font.bold)
        if style and style.base_style:
            return _resolve_bold(style.base_style)
    except Exception:
        pass
    return False


def _resolve_font(style) -> str:
    try:
        if style and style.font and style.font.name:
            return style.font.name
        if style and style.base_style:
            return _resolve_font(style.base_style)
    except Exception:
        pass
    return 'Arial'


def _is_heading_style(style) -> bool:
    if not style:
        return False
    name = (style.name or '').lower()
    return (name.startswith('heading') or
            name.startswith('ueberschrift') or
            name.startswith('überschrift') or
            name.startswith('title'))


def _has_page_break_from_element(para_element) -> bool:
    try:
        xml = para_element.xml if hasattr(para_element, 'xml') else ''
        if 'w:type="page"' in xml:
            return True
    except Exception:
        pass
    return False


def _get_indent_x(para) -> int:
    try:
        indent = para.paragraph_format.left_indent
        if indent:
            return round(indent.pt)
    except Exception:
        pass
    raw  = para.text
    tabs = len(raw) - len(raw.lstrip('\t'))
    return tabs * 20 if tabs else 0


class WordExtractor:

    def extract(self, doc_path: str) -> WordExtractResult:
        path_obj = Path(doc_path)
        if not path_obj.exists():
            return WordExtractResult(
                ok=False,
                error=f'Datei nicht gefunden: {doc_path}',
                filename=path_obj.name,
            )
        suffix = path_obj.suffix.lower()
        if suffix == '.docx':
            return self._extract_docx(path_obj)
        elif suffix == '.doc':
            return self._extract_doc_via_libreoffice(path_obj)
        else:
            return WordExtractResult(
                ok=False,
                error=f'Format nicht unterstützt: {suffix}',
                filename=path_obj.name,
            )

    def _extract_docx(self, path_obj: Path) -> WordExtractResult:
        start = time.time()
        try:
            from docx import Document
        except ImportError:
            return WordExtractResult(ok=False, error='python-docx nicht installiert',
                                     filename=path_obj.name)
        try:
            doc = Document(str(path_obj))
        except Exception as e:
            return WordExtractResult(ok=False, error=f'DOCX Fehler: {e}',
                                     filename=path_obj.name)

        spans:    List[dict] = []
        tables:   List[dict] = []
        headings: List[str]  = []
        page = 1
        y    = 0

        for block in doc.element.body:
            tag = block.tag.split('}')[-1] if '}' in block.tag else block.tag
            if tag == 'p':
                if _has_page_break_from_element(block):
                    page += 1
                    y = page * Y_PAGE_OFFSET
                y += Y_STEP
                span_dict, is_heading = self._para_to_span(block, doc, page, y)
                if span_dict:
                    spans.append(span_dict)
                    if is_heading:
                        headings.append(span_dict['text'])
            elif tag == 'tbl':
                table_data = self._table_to_dict(block, doc, page, y)
                if table_data:
                    tables.append(table_data)
                    for row_spans in table_data.get('row_spans', []):
                        for s in row_spans:
                            s['y'] = y
                            s['page'] = page
                            spans.append(s)
                            y += Y_STEP

        return self._build_result(spans, tables, headings, page,
                                  path_obj.name, 'docx',
                                  round(time.time() - start, 3))

    def _extract_doc_via_libreoffice(self, path_obj: Path) -> WordExtractResult:
        start = time.time()
        with tempfile.TemporaryDirectory(prefix='abpe_doc_') as tmp_dir:
            tmp_path = Path(tmp_dir)
            lo_result = subprocess.run(
                ['libreoffice', '--headless', '--nofirststartwizard',
                 '--norestore', '--convert-to', 'pdf',
                 str(path_obj), '--outdir', str(tmp_path)],
                capture_output=True, text=True, timeout=120,
            )
            if lo_result.returncode != 0:
                return WordExtractResult(
                    ok=False,
                    error=f'LibreOffice Exit {lo_result.returncode}: {lo_result.stderr[:300]}',
                    filename=path_obj.name, source_format='doc',
                )
            pdf_name = path_obj.stem + '.pdf'
            pdf_path = tmp_path / pdf_name
            if not pdf_path.exists():
                pdfs = list(tmp_path.glob('*.pdf'))
                if not pdfs:
                    return WordExtractResult(ok=False, error='LibreOffice: kein PDF erzeugt',
                                             filename=path_obj.name, source_format='doc')
                pdf_path = pdfs[0]

            lo_duration = round(time.time() - start, 2)
            logger.info(f"[WordExtractor] DOC→PDF: {path_obj.name} → {pdf_path.name} in {lo_duration}s")

            # ── main_pdf_extractor verwenden (nicht alten pdf_extractor) ──
            try:
                from apps.cv_extractor.services.main_pdf_extractor import PDFExtractor
                pdf_result = PDFExtractor().extract(str(pdf_path))
            except Exception as e:
                return WordExtractResult(ok=False,
                    error=f'main_pdf_extractor nach DOC-Konvertierung: {e}',
                    filename=path_obj.name, source_format='doc')

            spans:    List[dict] = []
            headings: List[str]  = []
            for s in (pdf_result.spans or []):
                text = (s.text or '').strip()
                if not text:
                    continue
                bold   = bool(getattr(s, 'bold',   False))
                size   = float(getattr(s, 'size',  DEFAULT_SIZE))
                is_hdg = bold and size >= HEADING_SIZE_MIN
                span = {
                    'page':      int(getattr(s, 'page', 1)),
                    'y':         int(getattr(s, 'y',    0)),
                    'x':         int(getattr(s, 'x',    0)),
                    'size':      size,
                    'bold':      bold,
                    'italic':    bool(getattr(s, 'italic', False)),
                    'font':      str(getattr(s, 'font',   'Arial')),
                    'text':      text,
                    'width':     float(getattr(s, 'x1', 0) or 0)
                                  - float(getattr(s, 'x0', 0) or 0),
                    'column_id': int(getattr(s, 'column_id', -1)),
                }
                spans.append(span)
                if is_hdg:
                    headings.append(text)

            total_duration = round(time.time() - start, 3)
            result = self._build_result(
                spans, [], headings,
                getattr(pdf_result, 'page_count', 1),
                path_obj.name, 'doc', total_duration,
            )
            result.meta['lo_duration_s'] = lo_duration
            result.meta['lo_stderr']     = lo_result.stderr[:200] if lo_result.stderr else ''
            return result

    def _para_to_span(self, para_element, doc, page: int, y: int):
        try:
            from docx.text.paragraph import Paragraph as DocxParagraph
            para = DocxParagraph(para_element, doc)
        except Exception:
            return None, False
        text = para.text.strip()
        if not text:
            return None, False
        x      = _get_indent_x(para)
        style  = para.style
        size   = _resolve_size(style)
        bold   = _resolve_bold(style) or _is_heading_style(style)
        italic = False
        font   = _resolve_font(style)
        for run in para.runs:
            if not run.text.strip():
                continue
            if run.bold is not None:
                bold = bool(run.bold)
            if run.italic:
                italic = True
            try:
                if run.font.size:
                    size = round(run.font.size.pt, 1)
            except Exception:
                pass
            try:
                if run.font.name:
                    font = run.font.name
            except Exception:
                pass
            break
        if _is_heading_style(style) and size < HEADING_SIZE_MIN:
            size = HEADING_SIZE_MIN
            bold = True
        is_heading = bold and size >= HEADING_SIZE_MIN
        return {
            'page': page, 'y': y, 'x': x,
            'size': size, 'bold': bold, 'italic': italic,
            'font': font, 'text': text, 'width': 0.0,
            'column_id': -1,
        }, is_heading

    def _table_to_dict(self, tbl_element, doc, page: int, y: int) -> Optional[dict]:
        try:
            from docx.table import Table as DocxTable
            table = DocxTable(tbl_element, doc)
        except Exception:
            return None
        all_rows:  List[List[str]]  = []
        row_spans: List[List[dict]] = []
        raw_lines: List[str]        = []
        for row in table.rows:
            row_texts:     List[str]  = []
            row_span_list: List[dict] = []
            for col_idx, cell in enumerate(row.cells):
                cell_text = cell.text.strip()
                if not cell_text:
                    continue
                row_texts.append(cell_text)
                raw_lines.append(cell_text)
                row_span_list.append({
                    'page': page, 'y': y, 'x': col_idx * 100,
                    'size': DEFAULT_SIZE, 'bold': False, 'italic': False,
                    'font': 'Arial', 'text': cell_text, 'width': 0.0,
                    'column_id': -1,
                })
            if row_texts:
                all_rows.append(row_texts)
                row_spans.append(row_span_list)
        if not all_rows:
            return None
        return {
            'headers':   all_rows[0],
            'rows':      all_rows[1:] if len(all_rows) > 1 else [],
            'row_spans': row_spans,
            'raw_text':  '\n'.join(raw_lines),
        }

    def _build_result(self, spans, tables, headings, page_count,
                      filename, source_format, duration) -> WordExtractResult:
        plain_text = '\n'.join(s['text'] for s in spans if s.get('text', '').strip())
        if len(plain_text) > MAX_PLAIN_TEXT_CHARS:
            plain_text = plain_text[:MAX_PLAIN_TEXT_CHARS]
        char_count = len(plain_text.replace(' ', '').replace('\n', ''))
        logger.info(f"[WordExtractor] {filename} ({source_format}): "
                    f"{len(spans)} Spans | {page_count} Seite(n) | "
                    f"{char_count} Zeichen | {duration}s")
        return WordExtractResult(
            ok=True, filename=filename, source_format=source_format,
            page_count=page_count, span_count=len(spans),
            char_count=char_count, plain_text=plain_text,
            first_500=plain_text[:500], spans=spans,
            tables=tables, headings=headings,
            meta={'duration_s': duration, 'suffix': '.' + source_format},
        )


# Singleton — main_pipeline_controller importiert WordExtractor direkt
word_extractor = WordExtractor()
