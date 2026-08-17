"""
services/fl_doc_extractor.py
==============================
Spezialist-Extraktoren für fl_doc_classifier.py Pipeline.

Wird aufgerufen NACH fl_doc_classifier — kennt den doc_type bereits.
Gibt strukturierte RAM-Daten zurück die direkt ins profil_pre_json.json
eingesortiert werden.

Routing nach doc_type:
  CV          → NICHT hier — geht in bestehende Master Pipeline
  CERTIFICATE → _extract_certifications() → extracted_data.certifications[]
  REFERENCE   → _extract_reference()      → extracted_data.experience[]
  EDUCATION   → _extract_education()      → extracted_data.education[]
  OTHER       → _extract_other()          → extracted_data.other (string)
  COVERLETTER → skip (None)

LLM-Auswahl:
  deepseek_label_api  → Array-Antworten  (certifications, education)
  deepseek_service    → Dict-Antworten   (reference, other)

Verwendung:
  from apps.cv_extractor.services.fl_doc_extractor import fl_doc_extractor

  result = fl_doc_extractor.extract(
      doc_type   = 'CERTIFICATE',   # aus fl_doc_classifier
      plain_text = '...',
      filename   = '01_e-cert.pdf',
  )
  # result.ok       → True/False
  # result.target   → 'certifications'
  # result.data     → [{name, issuer, date_obtained, ...}]
  # result.duration → float Sekunden
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# Maximale Textlänge an LLM (Tokens sparen)
MAX_TEXT_CHARS = 4000


# ── Ergebnis-Dataclass ────────────────────────────────────────────────────────

@dataclass
class DocExtractResult:
    """
    RAM-Ergebnis eines Spezialist-Extraktors.
    .data wird direkt in profil_pre_json.json eingesortiert.
    """
    ok:        bool          = False
    error:     Optional[str] = None
    doc_type:  str           = ''     # CERTIFICATE | REFERENCE | EDUCATION | OTHER
    target:    str           = ''     # certifications | experience | education | other
    data:      Any           = None   # List oder String je nach target
    filename:  str           = ''
    duration:  float         = 0.0
    llm_used:  bool          = False
    raw:       str           = ''     # LLM-Rohantwort für Debugging


# ── Haupt-Extraktionsklasse ───────────────────────────────────────────────────

class FLDocExtractor:
    """
    Spezialist-Extraktor für klassifizierte Nicht-CV-Dokumente.
    Kein Routing für CV — das bleibt in der bestehenden Master Pipeline.
    """

    def extract(
        self,
        doc_type:   str,
        plain_text: str,
        filename:   str = '',
    ) -> Optional[DocExtractResult]:
        """
        Hauptmethode: doc_type + plain_text → strukturierte Daten im RAM.

        Returns:
            DocExtractResult oder None wenn doc_type skip ist (CV, COVERLETTER)
        """
        doc_type = doc_type.upper()

        if doc_type == 'CV':
            # CV geht in Master Pipeline — hier nichts tun
            return None

        if doc_type == 'COVERLETTER':
            # Kein Mehrwert — skip
            logger.info(f"[FLDocExtractor] {filename}: COVERLETTER → skip")
            return None

        start = time.time()

        if doc_type == 'CERTIFICATE':
            result = self._extract_certifications(plain_text, filename)
        elif doc_type == 'REFERENCE':
            result = self._extract_reference(plain_text, filename)
        elif doc_type == 'EDUCATION':
            result = self._extract_education(plain_text, filename)
        elif doc_type == 'OTHER':
            result = self._extract_other(plain_text, filename)
        else:
            logger.warning(f"[FLDocExtractor] {filename}: unbekannter doc_type={doc_type}")
            result = self._extract_other(plain_text, filename)

        result.duration = round(time.time() - start, 2)
        result.filename  = filename
        result.doc_type  = doc_type

        if result.ok:
            logger.info(
                f"[FLDocExtractor] {filename}: {doc_type} → {result.target} "
                f"({result.duration}s)"
            )
        else:
            logger.warning(
                f"[FLDocExtractor] {filename}: {doc_type} Extraktion fehlgeschlagen: "
                f"{result.error}"
            )

        return result

    # ── CERTIFICATE ───────────────────────────────────────────────────────────

    def _extract_certifications(
        self, plain_text: str, filename: str
    ) -> DocExtractResult:
        """
        Extrahiert Zertifikatsdaten → Liste für certifications[].
        Verwendet deepseek_label_api (Array-Parser).
        """
        prompt_text = self._load_prompt('master_classifier_certifications')
        if not prompt_text:
            return DocExtractResult(
                ok=False, error='Prompt master_classifier_certifications nicht gefunden',
                target='certifications',
            )

        prompt = prompt_text.format(
            full_text = plain_text[:MAX_TEXT_CHARS],
            filename  = filename,
        )

        try:
            from apps.cv_extractor.services.deepseek_api_label import deepseek_label_api
            res = deepseek_label_api.extract(
                prompt,
                system_prompt='Antworte NUR mit JSON-Array.',
            )
        except Exception as e:
            return DocExtractResult(
                ok=False, error=f'deepseek_label_api Fehler: {e}',
                target='certifications',
            )

        if not res.success or not res.data:
            return DocExtractResult(
                ok=False,
                error=f'LLM fehlgeschlagen: {getattr(res, "error", "")}',
                target='certifications',
                raw=getattr(res, 'raw_response', ''),
            )

        # Normalisieren: immer Liste
        data = res.data
        if isinstance(data, dict):
            # LLM hat {certifications: [...]} zurückgegeben
            data = data.get('certifications', data.get('items', [data]))
        if not isinstance(data, list):
            data = [data]

        # Felder sichern
        clean = []
        for item in data:
            if not isinstance(item, dict):
                continue
            clean.append({
                'name':               str(item.get('name', '')).strip(),
                'issuer':             str(item.get('issuer', '')).strip(),
                'date_obtained':      str(item.get('date_obtained', '')).strip(),
                'expiry_date':        str(item.get('expiry_date', '')).strip(),
                'certificate_number': str(item.get('certificate_number', '')).strip(),
            })

        return DocExtractResult(
            ok      = bool(clean),
            error   = None if clean else 'Keine Zertifikate extrahiert',
            target  = 'certifications',
            data    = clean,
            llm_used= True,
            raw     = getattr(res, 'raw_response', ''),
        )

    # ── REFERENCE ─────────────────────────────────────────────────────────────

    def _extract_reference(
        self, plain_text: str, filename: str
    ) -> DocExtractResult:
        """
        Extrahiert Referenz/Zeugnis-Daten → Dict für experience[].
        Verwendet deepseek_service (Dict-Parser).
        """
        prompt_text = self._load_prompt('master_classifier_reference')
        if not prompt_text:
            return DocExtractResult(
                ok=False, error='Prompt master_classifier_reference nicht gefunden',
                target='experience',
            )

        prompt = prompt_text.format(
            full_text = plain_text[:MAX_TEXT_CHARS],
            filename  = filename,
        )

        try:
            from apps.cv_extractor.services.deepseek_service import deepseek_service
            res = deepseek_service.extract(
                prompt,
                system_prompt='Antworte NUR mit JSON-Objekt.',
            )
        except Exception as e:
            return DocExtractResult(
                ok=False, error=f'deepseek_service Fehler: {e}',
                target='experience',
            )

        if not res.success or not res.data:
            return DocExtractResult(
                ok=False,
                error=f'LLM fehlgeschlagen: {getattr(res, "error", "")}',
                target='experience',
                raw=getattr(res, 'raw_response', ''),
            )

        data = res.data
        if isinstance(data, list) and data:
            data = data[0]

        if not isinstance(data, dict):
            return DocExtractResult(
                ok=False, error='Kein Dict in LLM-Antwort',
                target='experience',
                raw=getattr(res, 'raw_response', ''),
            )

        # In experience-Format bringen (kompatibel mit pre_json)
        exp = {
            'period':       str(data.get('period', '')).strip(),
            'title':        str(data.get('role', '')).strip(),
            'company':      str(data.get('company', '')).strip(),
            'industry':     '',
            'role':         str(data.get('role', '')).strip(),
            'location':     '',
            'activities':   data.get('activities', []) if isinstance(data.get('activities'), list) else [],
            'technologies': data.get('technologies', []) if isinstance(data.get('technologies'), list) else [],
            # Referenz-spezifische Felder
            '_source':         'reference',
            '_reference_type': str(data.get('reference_type', 'referenz')).strip(),
            '_summary':        str(data.get('summary', '')).strip(),
        }

        return DocExtractResult(
            ok      = bool(exp['company'] or exp['period']),
            error   = None if (exp['company'] or exp['period']) else 'Keine Firmendaten extrahiert',
            target  = 'experience',
            data    = exp,
            llm_used= True,
            raw     = getattr(res, 'raw_response', ''),
        )

    # ── EDUCATION ─────────────────────────────────────────────────────────────

    def _extract_education(
        self, plain_text: str, filename: str
    ) -> DocExtractResult:
        """
        Extrahiert Bildungsdaten → Liste für education[].
        Verwendet deepseek_label_api (Array-Parser).
        """
        prompt_text = self._load_prompt('master_classifier_education')
        if not prompt_text:
            return DocExtractResult(
                ok=False, error='Prompt master_classifier_education nicht gefunden',
                target='education',
            )

        prompt = prompt_text.format(
            full_text = plain_text[:MAX_TEXT_CHARS],
            filename  = filename,
        )

        try:
            from apps.cv_extractor.services.deepseek_api_label import deepseek_label_api
            res = deepseek_label_api.extract(
                prompt,
                system_prompt='Antworte NUR mit JSON-Array.',
            )
        except Exception as e:
            return DocExtractResult(
                ok=False, error=f'deepseek_label_api Fehler: {e}',
                target='education',
            )

        if not res.success or not res.data:
            return DocExtractResult(
                ok=False,
                error=f'LLM fehlgeschlagen: {getattr(res, "error", "")}',
                target='education',
                raw=getattr(res, 'raw_response', ''),
            )

        data = res.data
        if isinstance(data, dict):
            data = data.get('education', data.get('items', [data]))
        if not isinstance(data, list):
            data = [data]

        clean = []
        for item in data:
            if not isinstance(item, dict):
                continue
            clean.append({
                'degree':         str(item.get('degree', '')).strip(),
                'institution':    str(item.get('institution', '')).strip(),
                'period':         str(item.get('period', '')).strip(),
                'description':    str(item.get('description', '')).strip(),
                'education_type': str(item.get('education_type', 'degree')).strip(),
                'issuer':         str(item.get('issuer', '')).strip(),
            })

        return DocExtractResult(
            ok      = bool(clean),
            error   = None if clean else 'Keine Bildungsdaten extrahiert',
            target  = 'education',
            data    = clean,
            llm_used= True,
            raw     = getattr(res, 'raw_response', ''),
        )

    # ── OTHER ─────────────────────────────────────────────────────────────────

    def _extract_other(
        self, plain_text: str, filename: str
    ) -> DocExtractResult:
        """
        Extrahiert Zusammenfassung → String für other.
        Verwendet deepseek_service (Dict-Parser).
        """
        prompt_text = self._load_prompt('master_classifier_other')
        if not prompt_text:
            # Fallback: plain_text direkt als other speichern
            summary = plain_text[:500].strip()
            return DocExtractResult(
                ok     = bool(summary),
                target = 'other',
                data   = f'[{filename}] {summary}',
            )

        prompt = prompt_text.format(
            full_text = plain_text[:MAX_TEXT_CHARS],
            filename  = filename,
        )

        try:
            from apps.cv_extractor.services.deepseek_service import deepseek_service
            res = deepseek_service.extract(
                prompt,
                system_prompt='Antworte NUR mit JSON-Objekt.',
            )
        except Exception as e:
            # Fallback: plain_text direkt
            return DocExtractResult(
                ok     = True,
                target = 'other',
                data   = f'[{filename}] {plain_text[:300]}',
                error  = f'LLM-Fehler (Fallback): {e}',
            )

        if not res.success or not res.data:
            # Fallback
            return DocExtractResult(
                ok     = True,
                target = 'other',
                data   = f'[{filename}] {plain_text[:300]}',
                error  = f'LLM fehlgeschlagen (Fallback)',
                raw    = getattr(res, 'raw_response', ''),
            )

        data = res.data
        summary  = str(data.get('summary',  '')).strip()
        doc_hint = str(data.get('doc_hint', '')).strip()
        keywords = data.get('relevant_keywords', [])

        # Als lesbaren String zusammenbauen
        parts = []
        if doc_hint:
            parts.append(f'[{doc_hint}]')
        if summary:
            parts.append(summary)
        if keywords:
            parts.append(f'Keywords: {", ".join(keywords)}')
        other_text = f'[{filename}] ' + ' | '.join(parts) if parts else f'[{filename}] {plain_text[:200]}'

        return DocExtractResult(
            ok      = True,
            target  = 'other',
            data    = other_text,
            llm_used= True,
            raw     = getattr(res, 'raw_response', ''),
        )

    # ── Prompt laden ─────────────────────────────────────────────────────────

    def _load_prompt(self, stage: str) -> Optional[str]:
        """Lädt Prompt-Text aus DB."""
        try:
            from apps.cv_extractor.models import PromptTemplate
            pt = PromptTemplate.objects.filter(
                stage=stage, is_active=True
            ).first()
            if pt:
                return pt.prompt_text
            logger.warning(f'[FLDocExtractor] Prompt {stage} nicht in DB')
        except Exception as e:
            logger.warning(f'[FLDocExtractor] DB-Fehler bei {stage}: {e}')
        return None


# ── Singleton ─────────────────────────────────────────────────────────────────

fl_doc_extractor = FLDocExtractor()
