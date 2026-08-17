"""
services/fl_doc_classifier.py
==============================
Dokument-Classifier für FL-Pipeline.

Phase 0: Regelbasiert (~0ms) — keyword + dateiname + größe
Phase 1: LLM-Fallback (~5s) — nur wenn OTHER oder confidence < 0.4

Doc-Typen (identisch zu pre_json Bereichen):
  CV          → Lebenslauf / Projektliste  → Master Pipeline
  CERTIFICATE → Zertifikat                 → cert_extractor LLM
  REFERENCE   → Referenz / Arbeitszeugnis  → ref_extractor LLM
  COVERLETTER → Anschreiben                → skip
  EDUCATION   → Schulungsnachweis/Zeugnis  → edu_extractor LLM
  OTHER       → Sonstiges                  → skip
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── Schwellwert für LLM-Fallback ─────────────────────────────────────────────
LLM_FALLBACK_CONFIDENCE = 0.4   # unter diesem Wert → LLM anrufen
LLM_FALLBACK_ON_OTHER   = True  # OTHER immer → LLM

# ── Keyword-Listen ────────────────────────────────────────────────────────────

_CERT_KEYWORDS = [
    'has achieved', 'has successfully', 'hereby certifies', 'certificate number',
    'candidate number', 'effective from', 'renew by', 'expiry', 'grant date',
    'certified safe', 'certified scrum', 'pmi-acp', 'prince2', 'pmp',
    'itil', 'cissp', 'cism', 'ccna', 'ccnp', 'aws certified', 'azure certified',
    'google cloud certified', 'has met the requirements',
    'zertifikat', 'zertifizierung', 'bescheinigung', 'nachweis',
    'erfolgreich bestanden', 'gültig bis', 'ausgestellt am',
    'zertifikatsnummer', 'peoplecer', 'scaled agile',
]

_REFERENCE_KEYWORDS = [
    'job reference', 'letter of recommendation', 'reference letter',
    'to whom it may concern', 'worked for', 'employed by',
    'we hereby confirm', 'during his employment', 'during her employment',
    'joined our company', 'left our company', 'was employed',
    'referenzschreiben', 'arbeitszeugnis', 'zeugnis', 'empfehlungsschreiben',
    'war im zeitraum', 'war bei uns', 'war in unserem unternehmen',
    'haben wir herrn', 'haben wir frau', 'mit herrn', 'mit frau',
    'betreff: referenz', 'als mitarbeiter', 'hat herr', 'hat frau',
    'tätig gewesen', 'tätig war',
]

_COVERLETTER_KEYWORDS = [
    'cover letter', 'dear hiring', 'dear hr', 'i am writing to',
    'i would like to apply', 'please find attached', 'my application',
    'sincerely yours', 'kind regards',
    'anschreiben', 'bewerbung', 'sehr geehrte damen', 'sehr geehrter herr',
    'hiermit bewerbe ich', 'mit freundlichen grüßen',
    'ich bewerbe mich', 'meine bewerbung', 'coverletter',
]

_EDUCATION_KEYWORDS = [
    'schulzeugnis', 'abiturzeugnis', 'abschlusszeugnis', 'berufsschule',
    'fachhochschulreife', 'hochschulreife', 'ausbildungszeugnis',
    'abschluss bestätigt', 'schulungsnachweis', 'teilnahmebestätigung',
    'mit auszeichnung bestanden',
    'transcript', 'diploma', 'degree certificate', 'academic record',
    'graduation certificate', 'course completion',
]

_CV_KEYWORDS = [
    'lebenslauf', 'berufserfahrung', 'beruflicher werdegang',
    'projekthistorie', 'projekterfahrung', 'kenntnisse',
    'fachkenntnisse', 'ausbildung', 'studium', 'zur person',
    'curriculum vitae', 'work experience', 'professional experience',
    'project history', 'employment', 'education', 'skills',
    'profile', 'summary', 'objective',
]

_DATE_PATTERN = re.compile(
    r'\b(\d{1,2}[./]\d{4}|\d{4})\s*[-–—]\s*'
    r'(\d{1,2}[./]\d{4}|\d{4}|heute|dato|aktuell|now|present|current)\b',
    re.IGNORECASE
)


# ── Ergebnis-Dataclass ────────────────────────────────────────────────────────

@dataclass
class DocClassifyResult:
    doc_type:    str        = 'OTHER'
    confidence:  float      = 0.0
    signals:     List[str]  = field(default_factory=list)
    skip:        bool       = False
    reason:      str        = ''
    llm_used:    bool       = False   # wurde LLM-Fallback verwendet?
    span_count:  int        = 0
    page_count:  int        = 0
    char_count:  int        = 0
    filename:    str        = ''


# ── Classifier ────────────────────────────────────────────────────────────────

class FLDocClassifier:

    def classify_from_result(self, extract_result) -> DocClassifyResult:
        """Klassifiziert aus WordExtractResult (master_word_extractor)."""
        if not extract_result.ok:
            return DocClassifyResult(
                doc_type='OTHER', confidence=0.0, skip=True,
                reason=f'Extraktion fehlgeschlagen: {extract_result.error}',
                filename=extract_result.filename,
            )
        return self.classify(
            plain_text = extract_result.plain_text,
            first_800  = extract_result.plain_text[:800],
            headings   = extract_result.headings,
            span_count = extract_result.span_count,
            page_count = extract_result.page_count,
            char_count = extract_result.char_count,
            filename   = extract_result.filename,
        )

    def classify_from_spans(self, spans: list, filename: str = '') -> DocClassifyResult:
        """Klassifiziert aus Span-Liste (pdf_extractor Output)."""
        texts = []
        for s in spans:
            t = s.get('text', '') if isinstance(s, dict) else getattr(s, 'text', '')
            if t and t.strip():
                texts.append(t.strip())

        plain_text = '\n'.join(texts)
        page_count = max(
            (s.get('page', 1) if isinstance(s, dict) else getattr(s, 'page', 1))
            for s in spans
        ) if spans else 1

        return self.classify(
            plain_text = plain_text,
            first_800  = plain_text[:800],
            headings   = [],
            span_count = len(spans),
            page_count = page_count,
            char_count = len(plain_text.replace(' ', '').replace('\n', '')),
            filename   = filename,
        )

    def classify(
        self,
        plain_text: str,
        first_800:  str,
        headings:   List[str],
        span_count: int,
        page_count: int,
        char_count: int,
        filename:   str = '',
    ) -> DocClassifyResult:
        """Kern-Klassifikation: regelbasiert + LLM-Fallback."""

        # ── Phase 0: Regelbasiert ─────────────────────────────────────────────
        result = self._classify_rules(
            plain_text, first_800, headings,
            span_count, page_count, char_count, filename,
        )

        # ── Phase 1: LLM-Fallback wenn nötig ─────────────────────────────────
        needs_llm = (
            (LLM_FALLBACK_ON_OTHER   and result.doc_type == 'OTHER') or
            (result.confidence < LLM_FALLBACK_CONFIDENCE)
        )

        if needs_llm:
            logger.info(
                f"[FLDocClassifier] {filename}: "
                f"regelbasiert={result.doc_type} conf={result.confidence:.2f} "
                f"→ LLM-Fallback"
            )
            llm_result = self._classify_llm(
                plain_text, filename, page_count, span_count
            )
            if llm_result:
                # LLM-Ergebnis übernehmen, Signale behalten
                result.doc_type   = llm_result['doc_type']
                result.confidence = llm_result['confidence']
                result.reason     = f"LLM: {llm_result['reason']}"
                result.llm_used   = True
                result.signals.append(f"LLM:{llm_result['doc_type']}({llm_result['confidence']:.2f})")
                result.skip = result.doc_type in ('COVERLETTER', 'OTHER')
                logger.info(
                    f"[FLDocClassifier] {filename}: "
                    f"LLM→{result.doc_type} conf={result.confidence:.2f}"
                )
            else:
                logger.warning(
                    f"[FLDocClassifier] {filename}: LLM-Fallback fehlgeschlagen → OTHER"
                )

        return result

    # ── Regelbasierte Klassifikation ──────────────────────────────────────────

    def _classify_rules(
        self,
        plain_text: str,
        first_800:  str,
        headings:   List[str],
        span_count: int,
        page_count: int,
        char_count: int,
        filename:   str,
    ) -> DocClassifyResult:

        text_lower     = plain_text.lower()
        first_lower    = first_800.lower()
        headings_lower = [h.lower() for h in headings]
        fname_lower    = filename.lower()
        signals: List[str] = []

        fname_type = self._classify_from_filename(fname_lower)

        cert_score  = self._score(text_lower, first_lower, _CERT_KEYWORDS,      signals, 'CERTIFICATE')
        ref_score   = self._score(text_lower, first_lower, _REFERENCE_KEYWORDS,  signals, 'REFERENCE')
        cover_score = self._score(text_lower, first_lower, _COVERLETTER_KEYWORDS, signals, 'COVERLETTER')
        edu_score   = self._score(text_lower, first_lower, _EDUCATION_KEYWORDS,   signals, 'EDUCATION')
        cv_score    = self._score(text_lower, first_lower, _CV_KEYWORDS,          signals, 'CV')

        date_matches = len(_DATE_PATTERN.findall(plain_text))
        if date_matches >= 3:
            cv_score += date_matches * 0.5
            signals.append(f'CV:dates({date_matches})')

        for h in headings_lower:
            if any(kw in h for kw in ['erfahrung', 'experience', 'projekt', 'project']):
                cv_score += 1.0
                signals.append(f'CV:heading({h[:30]})')
            if any(kw in h for kw in ['zertifikat', 'certif', 'lizenz']):
                cert_score += 1.0
                signals.append(f'CERTIFICATE:heading({h[:30]})')

        if span_count <= 15 and page_count == 1:
            cert_score  += 1.5
            cover_score -= 1.0
            cv_score    -= 2.0
            signals.append(f'SIZE:tiny(spans={span_count})')
        elif span_count <= 40 and page_count <= 2:
            signals.append(f'SIZE:small(spans={span_count})')
        else:
            cv_score += 1.0
            signals.append(f'SIZE:normal(spans={span_count})')

        fname_boost = {
            'CERTIFICATE': ('cert_score',  3.0),
            'REFERENCE':   ('ref_score',   3.0),
            'COVERLETTER': ('cover_score', 3.0),
            'CV':          ('cv_score',    3.0),
            'EDUCATION':   ('edu_score',   3.0),
        }
        if fname_type in fname_boost:
            var_name, boost = fname_boost[fname_type]
            locals_map = {
                'cert_score': cert_score, 'ref_score': ref_score,
                'cover_score': cover_score, 'cv_score': cv_score,
                'edu_score': edu_score,
            }
            locals_map[var_name] += boost
            cert_score  = locals_map['cert_score']
            ref_score   = locals_map['ref_score']
            cover_score = locals_map['cover_score']
            cv_score    = locals_map['cv_score']
            edu_score   = locals_map['edu_score']
            signals.append(f'FNAME:{fname_type}({fname_lower[:40]})')

        scores = {
            'CV':          cv_score,
            'CERTIFICATE': cert_score,
            'REFERENCE':   ref_score,
            'COVERLETTER': cover_score,
            'EDUCATION':   edu_score,
        }

        best_type  = max(scores, key=scores.get)
        best_score = scores[best_type]
        total      = sum(max(v, 0) for v in scores.values()) or 1
        confidence = min(best_score / total, 1.0)

        if best_score < 1.0:
            best_type  = 'OTHER'
            confidence = 0.0

        skip   = best_type in ('COVERLETTER', 'OTHER')
        reason = (
            f'{best_type} regelbasiert (score={best_score:.1f}, '
            f'conf={confidence:.2f}) | spans={span_count} pages={page_count}'
        )
        logger.info(f"[FLDocClassifier] {filename}: {reason}")

        return DocClassifyResult(
            doc_type   = best_type,
            confidence = round(confidence, 3),
            signals    = signals,
            skip       = skip,
            reason     = reason,
            llm_used   = False,
            span_count = span_count,
            page_count = page_count,
            char_count = char_count,
            filename   = filename,
        )

    # ── LLM-Fallback ─────────────────────────────────────────────────────────

    def _classify_llm(
        self,
        plain_text: str,
        filename:   str,
        page_count: int,
        span_count: int,
    ) -> Optional[dict]:
        """
        LLM-Fallback via master_document_type_classifier Prompt aus DB.
        Gibt dict {doc_type, confidence, reason} zurück oder None bei Fehler.
        """
        try:
            from apps.cv_extractor.models import PromptTemplate
            pt = PromptTemplate.objects.filter(
                stage='master_document_type_classifier',
                is_active=True,
            ).first()
            if not pt:
                logger.warning('[FLDocClassifier] Prompt master_document_type_classifier nicht gefunden')
                return None
        except Exception as e:
            logger.warning(f'[FLDocClassifier] DB-Fehler beim Prompt-Laden: {e}')
            return None

        # Text kürzen
        first_1000 = plain_text[:1000]
        full_text  = plain_text[:3000]

        prompt = pt.prompt_text.format(
            first_1000 = first_1000,
            full_text  = full_text,
            filename   = filename,
            page_count = page_count,
            span_count = span_count,
        )

        try:
            from apps.cv_extractor.services.deepseek_service import deepseek_service
            res = deepseek_service.extract(prompt)
        except Exception as e:
            logger.warning(f'[FLDocClassifier] DeepSeek-Fehler: {e}')
            return None

        if not res.success or not res.data:
            logger.warning(f'[FLDocClassifier] LLM leere Antwort: {getattr(res, "error", "")}')
            return None

        # Antwort parsen
        data = res.data
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                logger.warning(f'[FLDocClassifier] LLM JSON-Parse-Fehler: {data[:100]}')
                return None

        doc_type   = data.get('doc_type', 'OTHER').upper()
        confidence = float(data.get('confidence', 0.5))
        reason     = data.get('reason', '')

        valid_types = {'CV', 'CERTIFICATE', 'REFERENCE', 'COVERLETTER', 'EDUCATION', 'OTHER'}
        if doc_type not in valid_types:
            logger.warning(f'[FLDocClassifier] LLM unbekannter Typ: {doc_type} → OTHER')
            doc_type = 'OTHER'

        return {
            'doc_type':   doc_type,
            'confidence': confidence,
            'reason':     reason,
        }

    # ── Hilfsmethoden ─────────────────────────────────────────────────────────

    def _score(
        self,
        text_lower:  str,
        first_lower: str,
        keywords:    List[str],
        signals:     List[str],
        label:       str,
    ) -> float:
        score = 0.0
        for kw in keywords:
            in_first = kw in first_lower
            in_full  = kw in text_lower
            if in_first:
                score += 2.0
                signals.append(f'{label}:first:{kw}')
            elif in_full:
                score += 1.0
                signals.append(f'{label}:full:{kw}')
        return score

    def _classify_from_filename(self, fname_lower: str) -> str:
        cert_names  = ['zertifikat','certificate','cert','lizenz','license',
                       'pmi','prince2','itil','cissp','ccna','ccnp','safe',
                       'scrum','aws','azure','google-cloud']
        ref_names   = ['referenz','reference','zeugnis','empfehlung',
                       'arbeitszeugnis','recommendation']
        cover_names = ['anschreiben','coverletter','cover-letter',
                       'cover_letter','motivationsschreiben','bewerbung']
        cv_names    = ['lebenslauf','cv','curriculum','profil','profile',
                       'resume','projektliste','project-history']
        edu_names   = ['abschluss','diplom','bachelor','master','transcript',
                       'schulzeugnis','degree']

        for kw in cert_names:
            if kw in fname_lower: return 'CERTIFICATE'
        for kw in ref_names:
            if kw in fname_lower: return 'REFERENCE'
        for kw in cover_names:
            if kw in fname_lower: return 'COVERLETTER'
        for kw in cv_names:
            if kw in fname_lower: return 'CV'
        for kw in edu_names:
            if kw in fname_lower: return 'EDUCATION'
        return 'UNKNOWN'


# ── Singleton ─────────────────────────────────────────────────────────────────

fl_doc_classifier = FLDocClassifier()
