"""
Rohtext aus PDF/DOCX — wie ResumeParser (pdfminer/docx), ohne Layout/Spans.
Nur für den experimentellen LLM-Pfad.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    suffix = path.suffix.lower()
    if suffix == '.pdf':
        return _from_pdf(path)
    if suffix in ('.docx', '.doc'):
        return _from_docx(path)
    raise ValueError(f'Unsupported format: {suffix}')


def _from_pdf(path: Path) -> str:
    # 1) PyMuPDF wenn vorhanden (schneller, oft schon im Backend)
    try:
        import fitz  # type: ignore
        doc = fitz.open(str(path))
        parts = [page.get_text('text') for page in doc]
        doc.close()
        text = '\n'.join(parts).strip()
        if text:
            return text
    except Exception as e:
        logger.debug('PyMuPDF fallback: %s', e)

    # 2) pdfminer.six
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract
        return (pdfminer_extract(str(path)) or '').strip()
    except Exception:
        pass

    try:
        from pdfminer.converter import TextConverter
        from pdfminer.layout import LAParams
        from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
        from pdfminer.pdfpage import PDFPage

        chunks = []
        with open(path, 'rb') as fh:
            for page in PDFPage.get_pages(fh, caching=True, check_extractable=True):
                rm = PDFResourceManager()
                buf = io.StringIO()
                conv = TextConverter(rm, buf, codec='utf-8', laparams=LAParams())
                PDFPageInterpreter(rm, conv).process_page(page)
                chunks.append(buf.getvalue())
                conv.close()
                buf.close()
        return '\n'.join(chunks).strip()
    except Exception as e:
        raise RuntimeError(f'PDF text extraction failed: {e}') from e


def _from_docx(path: Path) -> str:
    try:
        import docx2txt  # type: ignore
        temp = docx2txt.process(str(path)) or ''
        lines = [ln.replace('\t', ' ') for ln in temp.split('\n') if ln.strip()]
        return '\n'.join(lines).strip()
    except Exception:
        pass
    try:
        from docx import Document  # type: ignore
        doc = Document(str(path))
        return '\n'.join(p.text for p in doc.paragraphs if p.text.strip()).strip()
    except Exception as e:
        raise RuntimeError(f'DOCX text extraction failed: {e}') from e
