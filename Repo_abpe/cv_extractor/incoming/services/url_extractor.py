"""
services/url_extractor.py
URL → JSON/HTML → SimpleSpan Liste

Strategie:
  1. JSON-First: React/Next.js Apps liefern oft JSON in <script> Tags
     → direkt parsen, kein HTML-Parsing nötig
     → Unterstützt: freelancermap.de (ProfileShow), generisch

  2. HTML-Fallback: get_text(separator='\n') mit Tag-Formatierung
     → für normale HTML-Seiten

Schnittstelle identisch zu pdf_extractor/word_extractor:
  result = url_extractor.extract(url)
  result.spans   → List[SimpleSpan]
  result.text    → str
  result.error   → Optional[str]
"""

import logging
import re
import time
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

REQUESTS_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

IGNORE_NAV_CLASSES = [
    'nav', 'menu', 'footer', 'header', 'cookie', 'banner',
    'advertisement', 'sidebar', 'breadcrumb', 'pagination',
    'social', 'share', 'login', 'signup', 'newsletter',
    'no-style', 'kontaktanfrage',
]


@dataclass
class UrlExtractionResult:
    text:            str
    spans:           List
    page_count:      int
    processing_time: float
    url:             str
    title:           str           = ''
    error:           Optional[str] = None
    requires_ocr:    bool          = False
    has_text_layer:  bool          = True
    source_type:     str           = 'html'  # 'json' oder 'html'


class URLExtractor:

    def extract(self, url: str, timeout: int = 30,
                session=None) -> UrlExtractionResult:
        start = time.time()

        try:
            import requests as _requests
            from bs4 import BeautifulSoup
            from .block_detector import SimpleSpan
        except ImportError as e:
            return UrlExtractionResult(
                text='', spans=[], page_count=0,
                processing_time=0, url=url,
                error=f"Import fehlgeschlagen: {e}"
            )

        # ── HTTP-Request ──────────────────────────────────────────────────────
        try:
            s    = session or _requests.Session()
            resp = s.get(url, headers=REQUESTS_HEADERS,
                         timeout=timeout, verify=False,
                         allow_redirects=True)
            resp.encoding = resp.apparent_encoding or 'utf-8'
            html = resp.text
            logger.info(f"[URL] {url} → {resp.status_code} ({len(html)} Bytes)")
        except Exception as e:
            return UrlExtractionResult(
                text='', spans=[], page_count=0,
                processing_time=time.time()-start,
                url=url, error=f"HTTP-Fehler: {e}"
            )

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
        except Exception as e:
            return UrlExtractionResult(
                text='', spans=[], page_count=0,
                processing_time=time.time()-start,
                url=url, error=f"Parse-Fehler: {e}"
            )

        title = soup.title.get_text(strip=True) if soup.title else ''

        # ── Strategie 1: React JSON (ProfileShow) ─────────────────────────────
        script = soup.find('script', {'data-component-name': 'ProfileShow'})
        if script and script.string:
            try:
                import json
                data    = json.loads(script.string)
                profile = data.get('profile', {})
                if profile:
                    from .block_detector import SimpleSpan
                    spans = self._spans_from_freelancermap_json(profile, SimpleSpan)
                    if spans:
                        full_text = '\n'.join(s.text for s in spans)
                        logger.info(f"[URL-JSON] {len(spans)} Spans aus ProfileShow JSON")
                        return UrlExtractionResult(
                            text            = full_text,
                            spans           = spans,
                            page_count      = max(s.page for s in spans),
                            processing_time = round(time.time()-start, 2),
                            url             = url,
                            title           = title,
                            source_type     = 'json',
                        )
            except Exception as e:
                logger.warning(f"[URL-JSON] JSON-Parsing fehlgeschlagen: {e}")

        # ── Strategie 2: HTML-Fallback ────────────────────────────────────────
        from .block_detector import SimpleSpan
        spans = self._spans_from_html(soup, SimpleSpan)
        full_text = '\n'.join(s.text for s in spans)
        logger.info(f"[URL-HTML] {len(spans)} Spans aus HTML")

        return UrlExtractionResult(
            text            = full_text,
            spans           = spans,
            page_count      = max((s.page for s in spans), default=1),
            processing_time = round(time.time()-start, 2),
            url             = url,
            title           = title,
            source_type     = 'html',
        )

    # ── freelancermap JSON → Spans ────────────────────────────────────────────

    def _spans_from_freelancermap_json(self, profile: dict, SimpleSpan) -> List:
        """Baut SimpleSpans aus freelancermap ProfileShow JSON."""
        spans = []
        y     = 0
        page  = 1

        def add(text, size, bold, x=0, italic=False):
            nonlocal y, page
            text = self._clean(text)
            if not text or len(text) < 2:
                return
            if y > page * 840:
                page += 1
                y = page * 1000
            y += 14
            spans.append(SimpleSpan(
                page=page, y=y, x=x,
                size=size, bold=bold, italic=italic,
                font='URL', text=text
            ))

        def add_html(html_text, base_size=10.0):
            """HTML-Inhalt aus Projekt-Beschreibung parsen."""
            if not html_text:
                return
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_text, 'html.parser')
                for tag in soup.find_all(['strong', 'b']):
                    add(tag.get_text(' ', strip=True), base_size, True, 0)
                    tag.decompose()
                for tag in soup.find_all(['em', 'i']):
                    add(tag.get_text(' ', strip=True), base_size, False, 0, italic=True)
                    tag.decompose()
                for tag in soup.find_all('li'):
                    add(tag.get_text(' ', strip=True), base_size, False, 20)
                    tag.decompose()
                # Restlicher Text
                for line in soup.get_text('\n', strip=True).split('\n'):
                    add(line, base_size, False, 0)
            except Exception as e:
                logger.debug(f"add_html Fehler: {e}")

        # ── HEADER: Name + Titel ──────────────────────────────────────────────
        user    = profile.get('user', {})
        if isinstance(user, dict):
            u = user.get('user', {})
            if isinstance(u, dict):
                fn = u.get('firstName', '')
                ln = u.get('lastName', '')
                if fn or ln:
                    add(f"{fn} {ln}".strip(), 20.0, True, 0)

        title = profile.get('title', '')
        if title:
            add(title, 14.0, True, 0)

        # ── PERSONAL: Über mich ───────────────────────────────────────────────
        add('Über mich', 17.0, True, 0)
        about = profile.get('aboutMe', '')
        if about:
            add(about, 10.0, False, 0)

        # Abschluss
        grad = profile.get('graduation', '')
        if grad:
            add(grad, 10.0, False, 0)

        # Verfügbarkeit
        avail = profile.get('availability')
        avail_map = {1: 'sofort verfügbar', 2: 'bald verfügbar',
                     3: '100% verfügbar', 4: 'nicht verfügbar'}
        if avail:
            add(avail_map.get(avail, str(avail)), 10.0, False, 0)

        # ── SPRACHEN ─────────────────────────────────────────────────────────
        langs = profile.get('languageSkills', [])
        if langs:
            add('Sprachen', 17.0, True, 0)
            level_map = {1: 'Grundkenntnisse', 2: 'gut',
                         3: 'verhandlungssicher', 4: 'Muttersprache'}
            for l in langs:
                name  = l.get('languageName', '')
                level = level_map.get(l.get('level', 0), '')
                add(f"{name}: {level}", 10.0, False, 0)

        # ── SKILLS ───────────────────────────────────────────────────────────
        skills_html = profile.get('skills', '')
        if skills_html:
            add('Skills / Kerntechnologien', 17.0, True, 0)
            add_html(skills_html, 10.0)

        # ── PROJEKTHISTORIE ───────────────────────────────────────────────────
        references = profile.get('references', [])
        if references:
            add('Projekthistorie', 17.0, True, 0)
            for ref in references:
                # Datum
                start_raw = ref.get('startDate', '')
                end_raw   = ref.get('endDate', '')
                at_now    = ref.get('atNow', False)

                def fmt_date(d):
                    try:
                        return datetime.fromisoformat(d.replace('Z', '+00:00')).strftime('%m/%Y')
                    except Exception:
                        return ''

                start_fmt = fmt_date(start_raw)
                end_fmt   = 'heute' if at_now else fmt_date(end_raw)
                period    = f"{start_fmt} – {end_fmt}" if start_fmt else ''

                company   = ref.get('company', '')
                position  = ref.get('position', '')
                branche   = ref.get('companyBranche', '').replace('_', ' ')
                members   = ref.get('companyMembers', '')

                if period:
                    add(period, 11.0, True, 0)
                if company:
                    add(company, 11.0, True, 0)
                if position:
                    add(position, 11.0, False, 0)
                if branche:
                    add(f"Branche: {branche}", 10.0, False, 0)
                if members:
                    add(f"Mitarbeiter: {members}", 10.0, False, 0)

                desc = ref.get('description', '')
                if desc:
                    add_html(desc, 10.0)

        # ── ZERTIFIKATE ───────────────────────────────────────────────────────
        certs = profile.get('certificates', [])
        if certs:
            add('Zertifikate', 17.0, True, 0)
            for cert in certs:
                name   = cert.get('name', '')
                issuer = cert.get('issuingOffice', '')
                year   = cert.get('certificationDate', '')
                add(f"{name} – {issuer} {year}".strip(' –'), 10.0, False, 0)

        logger.info(f"[URL-JSON] freelancermap: {len(spans)} Spans | "
                    f"{len(references)} Projekte | {len(certs)} Zertifikate")
        return spans

    # ── HTML-Fallback → Spans ─────────────────────────────────────────────────

    def _spans_from_html(self, soup, SimpleSpan) -> List:
        """HTML-Fallback: Tag-basierte Span-Generierung."""
        spans = []
        y     = 0
        page  = 1
        seen  = set()

        for tag in soup.find_all(['script','style','nav','footer',
                                   'header','noscript','iframe',
                                   'button','form','meta','link']):
            tag.decompose()

        for tag in soup.find_all(True):
            try:
                classes = ' '.join(tag.get('class', []) or []).lower()
                if any(p in classes for p in IGNORE_NAV_CLASSES):
                    tag.decompose()
            except Exception:
                pass

        main = soup.find('main') or soup.body or soup

        def add(text, size, bold, x=0):
            nonlocal y, page
            text = self._clean(text)
            if not text or len(text) < 2:
                return
            key = text.lower()[:50]
            if key in seen:
                return
            seen.add(key)
            if y > page * 840:
                page += 1
                y = page * 1000
            y += 14
            spans.append(SimpleSpan(
                page=page, y=y, x=x,
                size=size, bold=bold, italic=False,
                font='HTML', text=text
            ))

        # Zeilen aus main
        raw = main.get_text(separator='\n', strip=True)
        for line in raw.split('\n'):
            add(line, 10.0, False, 0)

        return spans

    def _clean(self, text: str) -> str:
        if not text:
            return ''
        text = re.sub(r'\s+', ' ', str(text))
        text = text.replace('\xa0', ' ').replace('&amp;', '&') \
                   .replace('&lt;', '<').replace('&gt;', '>') \
                   .replace('&quot;', '"').replace('&#39;', "'")
        return text.strip()


url_extractor = URLExtractor()
