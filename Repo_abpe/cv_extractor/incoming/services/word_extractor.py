"""
services/word_extractor.py
DOCX-Extraktion mit Paragraph-basierter Span-Erzeugung.
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class WordExtractionResult:
    text:            str
    spans:           List
    page_count:      int
    processing_time: float
    error:           Optional[str] = None


class WordExtractor:

    HEADING_SIZE_THRESHOLD = 13.0
    DEFAULT_SIZE = 12.0
    Y_STEP = 20
    Y_PAGE_OFFSET = 1000

    def extract(self, docx_path: str) -> WordExtractionResult:
        start = time.time()
        if not os.path.exists(docx_path):
            return WordExtractionResult(text='', spans=[], page_count=0,
                processing_time=0, error=f'Datei nicht gefunden: {docx_path}')
        try:
            from docx import Document
            from apps.cv_extractor.services.block_detector import SimpleSpan

            doc = Document(docx_path)
            spans = []
            page = 1
            y = 0

            def _style_size(style) -> float:
                try:
                    if style and style.font and style.font.size:
                        return round(style.font.size.pt, 1)
                    if style and style.base_style:
                        return _style_size(style.base_style)
                except Exception:
                    pass
                return self.DEFAULT_SIZE

            def _style_bold(style) -> bool:
                try:
                    if style and style.font and style.font.bold is not None:
                        return style.font.bold
                    if style and style.base_style:
                        return _style_bold(style.base_style)
                except Exception:
                    pass
                return False

            def _style_font(style) -> str:
                try:
                    if style and style.font and style.font.name:
                        return style.font.name
                    if style and style.base_style:
                        return _style_font(style.base_style)
                except Exception:
                    pass
                return 'Arial'

            def _is_heading_style(style) -> bool:
                if not style:
                    return False
                name = (style.name or '').lower()
                return name.startswith('heading') or name.startswith('ueberschrift') or name.startswith('überschrift')

            def _para_to_span(para, page: int, y: int):
                text = para.text.strip()
                if not text:
                    return None
                try:
                    indent = para.paragraph_format.left_indent
                    x = round(indent.pt) if indent else 0
                except Exception:
                    x = 0

                # Tabs als x-Tiefe wenn kein indent (1 Tab=1, 2 Tabs=2)
                if x == 0:
                    raw_text_for_tabs = para.text
                    tab_count = len(raw_text_for_tabs) - len(raw_text_for_tabs.lstrip('\t'))
                    if tab_count:
                        x = tab_count

                style      = para.style
                style_size = _style_size(style)
                style_bold = _style_bold(style) or _is_heading_style(style)
                style_font = _style_font(style)
                bold   = style_bold
                italic = False
                size   = style_size
                font   = style_font

                for run in para.runs:
                    if not run.text.strip():
                        continue
                    if run.bold is not None:
                        bold = run.bold
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

                if _is_heading_style(style) and size < self.HEADING_SIZE_THRESHOLD:
                    size = self.HEADING_SIZE_THRESHOLD
                    bold = True

                return SimpleSpan(page=page, y=y, x=x, size=size,
                                  bold=bold, italic=italic, font=font, text=text)

            def _has_page_break(para) -> bool:
                try:
                    if 'w:type="page"' in para._p.xml:
                        return True
                except Exception:
                    pass
                try:
                    if para.paragraph_format.page_break_before:
                        return True
                except Exception:
                    pass
                return False

            for block in doc.element.body:
                tag = block.tag.split('}')[-1] if '}' in block.tag else block.tag

                if tag == 'p':
                    from docx.text.paragraph import Paragraph as P
                    para = P(block, doc)
                    if _has_page_break(para):
                        page += 1
                        y = page * self.Y_PAGE_OFFSET
                    y += self.Y_STEP
                    span = _para_to_span(para, page, y)
                    if span:
                        spans.append(span)

                elif tag == 'tbl':
                    from docx.table import Table as T
                    table = T(block, doc)
                    for row in table.rows:
                        cells = row.cells
                        if len(cells) >= 2:
                            label = cells[0].text.strip()
                            value = cells[1].text.strip()
                            if label or value:
                                y += self.Y_STEP
                                # Label-Zelle (x=0, bold)
                                if label:
                                    spans.append(SimpleSpan(
                                        page=page, y=y, x=0,
                                        size=self.DEFAULT_SIZE, bold=True, italic=False,
                                        font='Arial', text=label
                                    ))
                                # Wert-Zelle (x=200, normal) - als eigener Span
                                if value:
                                    # Mehrzeilige Werte aufteilen
                                    for line in value.split('\n'):
                                        line = line.strip()
                                        if line:
                                            spans.append(SimpleSpan(
                                                page=page, y=y, x=200,
                                                size=self.DEFAULT_SIZE, bold=False, italic=False,
                                                font='Arial', text=line
                                            ))
                                            y += self.Y_STEP
                        elif len(cells) == 1:
                            text = cells[0].text.strip()
                            if text:
                                y += self.Y_STEP
                                spans.append(SimpleSpan(
                                    page=page, y=y, x=0,
                                    size=self.DEFAULT_SIZE, bold=False, italic=False,
                                    font='Arial', text=text
                                ))

            full_text = '\n'.join(s.text for s in spans)
            logger.info(f"WordExtractor: {len(spans)} Spans, {page} Seite(n), {len(full_text)} Zeichen")

            return WordExtractionResult(text=full_text, spans=spans,
                page_count=page, processing_time=round(time.time() - start, 3))

        except Exception as e:
            logger.exception(f"WordExtractor Fehler: {e}")
            return WordExtractionResult(text='', spans=[], page_count=0,
                processing_time=round(time.time() - start, 3), error=str(e))

    def save_spans_txt(self, result: WordExtractionResult, output_path: str) -> str:
        lines = []
        for s in result.spans:
            b = 'B' if s.bold else '.'
            i = 'I' if s.italic else '.'
            lines.append(f"p{s.page:02d}|y={s.y:5}|x={s.x:4}|sz={s.size:4.1f}|{b}{i} |{s.text}")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        logger.info(f"Spans TXT gespeichert: {output_path}")
        return output_path


word_extractor = WordExtractor()
