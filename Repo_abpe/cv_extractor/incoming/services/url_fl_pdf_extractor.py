"""
services/url_fl_pdf_extractor.py  v2 — 2-Stufen-Architektur

Phase 0: Regex-Vorlabeling (~0s)
  Spans -> Zeilen -> RawBlocks
  Format kompakt: B01|p1|sz=24|B|regex:PERSONAL|ANGELIKA SZEWCZYK

Phase 1: Dirigent-Call (1 LLM, ~10-15s)
  Prompt: fl_classify_cv (in DB)
  Erkennt: consultant_type + consultant_level
  Weist jeden Block zu: 1=KOPF 2=PERSONAL 3=BRANCHEN 4=FACHBEREICHE
  5=SCHULUNGEN 6=ZERTIFIKATE 7=FOCUS_EXP 8=EXPERIENCE 9=SONSTIGES

Phase 2: 9 parallele Spezialisten (~25s)
  Dict-API fuer { }: kopf, personal, branchen, fachbereiche, focus_exp, sonstiges
  Array-API fuer [ ]: schulungen, zertifikate, experience
  Prompts aus DB: fl_extract_*

Phase 3: Merge mit FL-API pre_json
  technologies aus LLM in API-experience einpflegen
  headline/languages/availability aus FL-API bevorzugen
"""

import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Regex-Vorlabeling Keywords ────────────────────────────────────────────────

REGEX_LABELS = {
    'PERSONAL': [
        'stammdaten', 'persoenliche daten', 'persönliche daten', 'kontakt',
        'ueber mich', 'über mich', 'about me', 'kurzprofil', 'kurzvorstellung',
        'lebenslauf', 'curriculum vitae',
    ],
    'EXPERIENCE': [
        'beruflicher werdegang', 'berufserfahrung', 'berufliche erfahrung',
        'projekthistorie', 'projekterfahrung', 'projektubersicht',
        'projektübersicht', 'work experience', 'professional experience',
        'referenzen', 'references', 'taetigkeiten', 'tätigkeiten',
        'stationen', 'community engagement', 'open-source',
    ],
    'SKILLS': [
        'it-kenntnisse', 'fachkenntnisse', 'technische kenntnisse',
        'kompetenzen', 'faehigkeiten', 'fähigkeiten', 'technologien',
        'programmiersprachen', 'betriebssysteme', 'datenbanken',
    ],
    'EDUCATION': [
        'ausbildung', 'bildung', 'studium', 'schule',
        'education', 'university', 'hochschule', 'abschluss',
    ],
    'CERTIFICATIONS': [
        'zertifikate', 'zertifizierungen', 'zertifizierung',
        'certifications', 'certificates', 'lizenzen',
    ],
    'SCHULUNGEN': [
        'schulungen', 'kurse', 'weiterbildung', 'trainings', 'seminare',
    ],
    'BRANCHEN': [
        'branchen', 'branchenkenntnisse', 'branchenerfahrung',
    ],
    'FOCUS_EXP': [
        'produkte', 'standards', 'tools', 'werkzeuge',
        'allgemeine kenntnisse',
    ],
}

DATE_PATTERN = re.compile(
    r'\b(\d{1,2}[./]\d{4}|\d{4})\s*[-\u2013\u2014]\s*'
    r'(\d{1,2}[./]\d{4}|\d{4}|heute|dato|aktuell|now)\b',
    re.IGNORECASE
)

SKILL_CATEGORIES = [
    'architecture_pattern', 'business_software', 'ci_cd_tool', 'cloud_platform',
    'communication_tool', 'database', 'data_format', 'data_management',
    'development_environment', 'devops_tool', 'documentation_tool', 'framework',
    'hardware', 'identity_management', 'it_infrastructure', 'methodology',
    'monitoring_tool', 'network_protocol', 'operating_system', 'programming_languages',
    'project_management', 'security_tool', 'soft_skill', 'special_concept',
    'testing_tool', 'version_control', 'virtualization',
]

AREA_MAP = {
    1: 'kopf', 2: 'personal', 3: 'branchen', 4: 'fachbereiche',
    5: 'schulungen', 6: 'zertifikate', 7: 'focus_exp',
    8: 'experience', 9: 'sonstiges',
}

# ── pre_json Template ─────────────────────────────────────────────────────────

def _empty_pre_json() -> dict:
    return {
        'metadata': {
            'aid': '', 'version': '1.0.0.0', 'consultant_dir': '',
            'first_name': '', 'last_name': '', 'headline': '',
            'source': {
                'type': 'url_import', 'filename': '', 'filesize': 0,
                'import_id': '', 'import_date': '',
            },
            'pipeline': {
                'version': '5.0', 'step': 'fl_pdf_extraction',
                'extractor': 'url_fl_pdf_extractor_v2',
                'model': 'deepseek-chat', 'self_learning': True,
            },
            'duplicate_check': {'exists': False, 'message': ''},
            'statistics': {
                'total_categories': 0,
                'has_personal': False, 'has_skills': False, 'has_experience': False,
            },
        },
        'extracted_data': {
            'personal': {
                'first_name': '', 'last_name': '', 'birth_year': None,
                'nationality': '', 'languages': [], 'email': '', 'phone': '',
                'location': '', 'availability': '', 'degree': '',
                'edv_experience_since': None, 'headline': '', 'summary': '',
            },
            'professional': {'total_experience_years': 0},
            'skills':           {k: [] for k in SKILL_CATEGORIES},
            'certifications':   [],
            'experience':       [],
            'industries':       [],
            'focus_areas':      [],
            'focus_experience': [],
            'education':        [],
            'schulungen':       [],
            'other':            '',
        },
        'audit': {
            'created_by': 'url_fl_pdf_extractor_v2',
            'created_at': '', 'source_file': '', 'steps_completed': [],
        },
    }

# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class YxSpan:
    page:   int
    y:      int
    x:      int
    size:   float
    bold:   bool
    italic: bool = False
    text:   str = ''
    source: str = ''

@dataclass
class RawBlock:
    index:       int
    first_span:  YxSpan
    lines:       List[Tuple[YxSpan, str]]
    text:        str
    first_line:  str
    regex_label: str
    has_date:    bool

# ── FLPdfExtractor ────────────────────────────────────────────────────────────

class FLPdfExtractor:

    def __init__(self, api_key: Optional[str] = None):
        self._api_key   = api_key
        self._api       = None
        self._label_api = None
        self._lock      = threading.Lock()

    def _get_api(self):
        if self._api:
            return self._api
        with self._lock:
            if self._api:
                return self._api
            try:
                from apps.cv_extractor.services.deepseek_api import deepseek_api
                self._api = deepseek_api
            except ImportError:
                self._api = self._make_api(array_first=False)
        return self._api

    def _get_label_api(self):
        if self._label_api:
            return self._label_api
        with self._lock:
            if self._label_api:
                return self._label_api
            try:
                from apps.cv_extractor.services.deepseek_api_label import deepseek_label_api
                self._label_api = deepseek_label_api
            except ImportError:
                self._label_api = self._make_api(array_first=True)
        return self._label_api

    def _make_api(self, array_first: bool):
        import requests as _req
        import urllib3
        urllib3.disable_warnings()
        key = self._api_key or self._load_api_key()

        class _Api:
            def __init__(self, k, af):
                self.k, self.af = k, af

            def extract(self, prompt, system_prompt='Antworte NUR mit JSON.', **_):
                try:
                    r = _req.post(
                        'https://api.deepseek.com/v1/chat/completions',
                        headers={'Authorization': f'Bearer {self.k}',
                                 'Content-Type': 'application/json'},
                        json={'model': 'deepseek-chat', 'temperature': 0.1,
                              'max_tokens': 4096,
                              'messages': [
                                  {'role': 'system', 'content': system_prompt},
                                  {'role': 'user',   'content': prompt},
                              ]},
                        timeout=90, verify=False,
                    )
                    r.raise_for_status()
                    content = r.json()['choices'][0]['message']['content']
                    content = re.sub(r'^```(?:json)?\s*', '', content.strip())
                    content = re.sub(r'\s*```$', '', content)
                    pats = ([r'\[[\s\S]*\]', r'\{[\s\S]*\}'] if self.af
                            else [r'\{[\s\S]*\}', r'\[[\s\S]*\]'])
                    for pat in pats:
                        m = re.search(pat, content)
                        if m:
                            try:
                                data = json.loads(m.group())
                                return type('R', (), {
                                    'success': True, 'data': data, 'raw': content})()
                            except Exception:
                                pass
                    return type('R', (), {
                        'success': False, 'data': None, 'raw': content,
                        'error': 'Kein JSON'})()
                except Exception as e:
                    return type('R', (), {
                        'success': False, 'data': None, 'raw': '', 'error': str(e)})()

        return _Api(key, array_first)

    @staticmethod
    def _load_api_key() -> str:
        """DeepSeek-Key nur aus settings.json — kein Hardcode-Fallback."""
        candidates = (
            Path('/opt/abpe/backend/settings.json'),
            Path('settings.json'),
        )
        for settings_path in candidates:
            try:
                if not settings_path.is_file():
                    continue
                cfg = json.loads(settings_path.read_text(encoding='utf-8'))
                key = (
                    (cfg.get('ai_models') or {}).get('deepseek') or {}
                ).get('api_key') or (cfg.get('api_keys') or {}).get('deepseek')
                if key:
                    return str(key).strip()
            except Exception as e:
                logger.debug('DeepSeek-Key aus %s nicht lesbar: %s', settings_path, e)
        logger.error(
            'DeepSeek API-Key fehlt in settings.json '
            '(ai_models.deepseek.api_key / api_keys.deepseek) — kein Hardcode-Fallback'
        )
        return ''

    def _get_prompt(self, stage: str) -> Optional[str]:
        try:
            from apps.cv_extractor.models import PromptTemplate
            pt = PromptTemplate.objects.filter(stage=stage, is_active=True).first()
            return pt.prompt_text if pt else None
        except Exception:
            return None

    # ── yx.txt parsen ─────────────────────────────────────────────────────────

    def _parse_yx_txt(self, yx_path: Path) -> List[YxSpan]:
        spans = []
        fname = yx_path.name
        for line in yx_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split('|')
            if len(parts) < 6:
                continue
            try:
                page = int(parts[0].replace('p', '').strip())
                y    = int(parts[1].split('=')[1].strip())
                x    = int(parts[2].split('=')[1].strip())
                sz   = float(parts[3].split('=')[1].strip())
                # FL-PDF: p|y|x|sz|B|Text     5.Feld = 'B' oder '.'
                # Word:   p|y|x|sz|BI |Text   5.Feld = 'BI','B.','I.','..'+Leerzeichen
                flag_field = parts[4]
                bold   = len(flag_field) >= 1 and flag_field[0].upper() == 'B'
                italic = len(flag_field) >= 2 and flag_field[1].upper() == 'I'
                text   = '|'.join(parts[5:]).strip()
                if text:
                    spans.append(YxSpan(page=page, y=y, x=x,
                                        size=sz, bold=bold, italic=italic,
                                        text=text, source=fname))
            except (ValueError, IndexError):
                continue
        return spans

    @staticmethod
    def _normalize_spans(spans) -> List[YxSpan]:
        result = []
        for s in spans:
            text = str(getattr(s, 'text', '')).strip()
            if text:
                result.append(YxSpan(
                    page=int(getattr(s, 'page', 1)),
                    y=int(getattr(s, 'y', 0)),
                    x=int(getattr(s, 'x', 0)),
                    size=float(getattr(s, 'size', 11.0)),
                    bold=bool(getattr(s, 'bold', False)),
                    italic=bool(getattr(s, 'italic', False)),
                    text=text, source='direct',
                ))
        return result

    # ── Phase 0: Regex-Vorlabeling ────────────────────────────────────────────

    def _build_raw_blocks(self, spans: List[YxSpan]) -> List[RawBlock]:
        if not spans:
            return []

        lines: List[Tuple[YxSpan, str]] = []
        sorted_spans = sorted(spans, key=lambda s: (s.source, s.page, s.y, s.x))
        cur_y = cur_page = cur_src = None
        cur_grp: List[YxSpan] = []

        def _flush(grp):
            if grp:
                lines.append((grp[0], ' '.join(s.text for s in grp)))

        for span in sorted_spans:
            new_line = (cur_src != span.source or cur_page != span.page
                        or cur_y is None or abs(span.y - cur_y) > 8)
            if new_line:
                _flush(cur_grp)
                cur_grp  = [span]
                cur_y    = span.y
                cur_page = span.page
                cur_src  = span.source
            else:
                cur_grp.append(span)
        _flush(cur_grp)

        sizes     = sorted(s.size for s in spans)
        median_sz = sizes[len(sizes) // 2] if sizes else 11.0
        h_thresh  = median_sz + 1.0

        def _is_heading(text: str, size: float, bold: bool,
                        italic: bool = False) -> bool:
            t = text.strip()
            if not t or len(t) < 2:
                return False
            # Italic-only Zeilen sind NIE Ueberschriften (Zitate, Fussnoten)
            if italic and not bold:
                return False
            if size >= h_thresh:
                return True
            if bold and len(t) < 70:
                return True
            letters = [c for c in t if c.isalpha()]
            if letters and len(t) >= 4:
                if sum(1 for c in letters if c.isupper()) / len(letters) >= 0.70:
                    return True
            return False

        def _regex_label(text: str) -> str:
            t = text.lower().strip()
            for label, keywords in REGEX_LABELS.items():
                for kw in keywords:
                    if kw in t:
                        return label
            return ''

        raw_blocks: List[RawBlock] = []
        cur_block_lines: List[Tuple[YxSpan, str]] = []
        block_idx = 0

        def _save_block(block_lines):
            nonlocal block_idx
            if not block_lines:
                return
            block_idx += 1
            text       = '\n'.join(lt for _, lt in block_lines)
            first_line = block_lines[0][1][:80]
            first_span = block_lines[0][0]
            rl         = _regex_label(first_line)
            has_date   = bool(DATE_PATTERN.search(text))
            raw_blocks.append(RawBlock(
                index=block_idx, first_span=first_span,
                lines=list(block_lines), text=text,
                first_line=first_line, regex_label=rl, has_date=has_date,
            ))

        for first_span, line_text in lines:
            is_head = _is_heading(line_text, first_span.size, first_span.bold, first_span.italic)
            split = False
            if is_head:
                stripped = line_text.strip()
                if not (stripped.endswith(':') and len(stripped) < 30):
                    split = True
            if split and cur_block_lines:
                _save_block(cur_block_lines)
                cur_block_lines = []
            cur_block_lines.append((first_span, line_text))

        _save_block(cur_block_lines)
        logger.info(f"[FLPdfExtractor] Phase 0: {len(raw_blocks)} Bloecke aus {len(spans)} Spans")
        return raw_blocks

    def _build_block_overview(self, raw_blocks: List[RawBlock]) -> str:
        rows = []
        for b in raw_blocks:
            sz   = round(b.first_span.size)
            bi   = ('B' if b.first_span.bold else '.') + \
                   ('I' if b.first_span.italic else '.')
            page = b.first_span.page
            rl   = f"regex:{b.regex_label}" if b.regex_label else (
                   "regex:DATE" if b.has_date else "regex:?")
            preview = b.first_line[:100]
            if len(b.lines) > 1:
                second = b.lines[1][1][:60].strip()
                if second:
                    preview += f" | {second}"
            rows.append(f"B{b.index:02d}|p{page}|sz={sz}|{bi}|{rl}|{preview}")
        return '\n'.join(rows)

    # ── Phase 1: Dirigent ─────────────────────────────────────────────────────

    def _phase1_classify(self, raw_blocks: List[RawBlock]) -> dict:
        prompt_tpl = self._get_prompt('fl_classify_cv')
        if not prompt_tpl:
            logger.warning("[FLPdfExtractor] fl_classify_cv nicht gefunden -> Fallback")
            return self._phase1_fallback(raw_blocks)

        overview = self._build_block_overview(raw_blocks)
        prompt   = prompt_tpl.format(blocks=overview)
        logger.info("[FLPdfExtractor] Phase 1: Dirigent-Call...")
        r = self._get_api().extract(prompt, system_prompt='Antworte NUR mit JSON.')

        if r.success and isinstance(r.data, dict):
            consultant_type  = r.data.get('consultant_type', 'IT-Experte')
            consultant_level = r.data.get('consultant_level', 'Senior')
            assignments_raw  = r.data.get('assignments', [])
            assignments = {}
            for item in assignments_raw:
                if isinstance(item, dict):
                    b    = item.get('block')
                    area = item.get('area')
                    if b is not None and area is not None:
                        try:
                            assignments[int(b)] = int(area)
                        except (ValueError, TypeError):
                            pass
            logger.info(f"  Typ: {consultant_type} | Level: {consultant_level}")
            logger.info(f"  {len(assignments)} Bloecke zugewiesen")
            from collections import Counter
            for area_nr, count in sorted(Counter(assignments.values()).items()):
                logger.info(f"    Bereich {area_nr} ({AREA_MAP.get(area_nr,'?')}): {count} Bloecke")
            return {'consultant_type': consultant_type,
                    'consultant_level': consultant_level,
                    'assignments': assignments}

        logger.warning("[FLPdfExtractor] Phase 1 fehlgeschlagen -> Fallback")
        return self._phase1_fallback(raw_blocks)

    def _phase1_fallback(self, raw_blocks: List[RawBlock]) -> dict:
        REGEX_TO_AREA = {
            'PERSONAL': 2, 'EXPERIENCE': 8, 'SKILLS': 7, 'EDUCATION': 2,
            'CERTIFICATIONS': 6, 'SCHULUNGEN': 5, 'BRANCHEN': 3, 'FOCUS_EXP': 7,
        }
        assignments = {}
        for b in raw_blocks:
            # Rein-italic Bloecke (Zitate, Fussnoten) → immer SONSTIGES
            if b.first_span.italic and not b.first_span.bold:
                assignments[b.index] = 9
            elif b.regex_label:
                assignments[b.index] = REGEX_TO_AREA.get(b.regex_label, 9)
            elif b.has_date:
                assignments[b.index] = 8
            elif b.index <= 2:
                assignments[b.index] = 1
            else:
                assignments[b.index] = 9
        return {'consultant_type': 'IT-Experte', 'consultant_level': 'Senior',
                'assignments': assignments}

    # ── Phase 2: Spezialisten ─────────────────────────────────────────────────

    def _collect_texts_by_area(self, raw_blocks: List[RawBlock],
                                assignments: dict) -> Dict[str, str]:
        area_texts: Dict[int, List[str]] = {}
        for b in raw_blocks:
            area_nr = assignments.get(b.index, 9)
            area_texts.setdefault(area_nr, []).append(b.text)
        return {
            AREA_MAP[nr]: '\n\n'.join(texts)
            for nr, texts in area_texts.items() if nr in AREA_MAP
        }

    def _run_specialist(self, stage: str, text: str,
                        consultant_type: str, use_label_api: bool) -> object:
        prompt_tpl = self._get_prompt(stage)
        if not prompt_tpl:
            logger.warning(f"[FLPdfExtractor] Prompt {stage} nicht gefunden")
            return None
        max_chars = {'fl_extract_experience': 40000,
                     'fl_extract_focus_exp':   6000,
                     'fl_extract_personal':   3000}.get(stage, 2500)
        prompt = prompt_tpl.format(text=text[:max_chars],
                                   consultant_type=consultant_type)
        api = self._get_label_api() if use_label_api else self._get_api()
        return api.extract(prompt, system_prompt='Antworte NUR mit JSON.')

    def _phase2_specialists(self, area_texts: Dict[str, str],
                             consultant_type: str) -> dict:
        SPECIALISTS = {
            'fl_extract_kopf':         ('kopf',         False),
            'fl_extract_personal':     ('personal',     False),
            'fl_extract_branchen':     ('branchen',     False),
            'fl_extract_fachbereiche': ('fachbereiche', False),
            'fl_extract_schulungen':   ('schulungen',   True),
            'fl_extract_zertifikate':  ('zertifikate',  True),
            'fl_extract_focus_exp':    ('focus_exp',    False),
            'fl_extract_experience':   ('experience',   True),
            'fl_extract_sonstiges':    ('sonstiges',    False),
        }
        logger.info("[FLPdfExtractor] Phase 2: 9 Spezialisten parallel...")
        results = {}
        tasks   = {}

        with ThreadPoolExecutor(max_workers=9) as pool:
            for stage, (area_name, use_label) in SPECIALISTS.items():
                text = area_texts.get(area_name, '')
                if not text.strip():
                    logger.info(f"  ⏭  {stage}: kein Text")
                    continue
                tasks[stage] = pool.submit(
                    self._run_specialist, stage, text, consultant_type, use_label)

            for stage, future in tasks.items():
                try:
                    r = future.result(timeout=90)
                    if r and r.success and r.data:
                        results[stage] = r.data
                        logger.info(f"  ✅ {stage}")
                    else:
                        logger.warning(f"  ❌ {stage}: {getattr(r,'error','') if r else 'None'}")
                        results[stage] = None
                except Exception as e:
                    logger.warning(f"  ❌ {stage}: {e}")
                    results[stage] = None
        return results

    def _build_pre_json(self, specialist_results: dict,
                         first_name: str, last_name: str,
                         dir_name: str, source_url: str,
                         consultant_type: str, now: str) -> dict:
        pj = _empty_pre_json()
        pj['metadata']['first_name']            = first_name
        pj['metadata']['last_name']             = last_name
        pj['metadata']['consultant_dir']        = dir_name
        pj['metadata']['source']['filename']    = source_url or dir_name
        pj['metadata']['source']['import_date'] = now
        pj['metadata']['pipeline']['extractor'] = f'url_fl_pdf_extractor_v2 ({consultant_type})'

        kopf = specialist_results.get('fl_extract_kopf') or {}
        if isinstance(kopf, dict) and kopf.get('headline'):
            pj['metadata']['headline'] = kopf['headline']

        personal = specialist_results.get('fl_extract_personal') or {}
        if isinstance(personal, dict) and personal:
            ed_p = pj['extracted_data']['personal']
            for k in ed_p:
                v = personal.get(k)
                if v is not None and v != '' and v != [] and v != 0:
                    ed_p[k] = v
            if first_name: ed_p['first_name'] = first_name
            if last_name:  ed_p['last_name']  = last_name
            if personal.get('headline') and not pj['metadata'].get('headline'):
                pj['metadata']['headline'] = personal['headline']
            edu_from_personal = personal.get('education', [])
            if isinstance(edu_from_personal, list) and edu_from_personal:
                pj['extracted_data']['education'] = edu_from_personal

        branchen = specialist_results.get('fl_extract_branchen') or {}
        if isinstance(branchen, dict):
            inds = branchen.get('industries', [])
            if isinstance(inds, list):
                pj['extracted_data']['industries'] = inds

        fach = specialist_results.get('fl_extract_fachbereiche') or {}
        if isinstance(fach, dict):
            fas = fach.get('focus_areas', [])
            if isinstance(fas, list):
                pj['extracted_data']['focus_areas'] = fas

        schulungen_raw = specialist_results.get('fl_extract_schulungen')
        if isinstance(schulungen_raw, list):
            pj['extracted_data']['schulungen'] = [
                {'name': s['name'] if isinstance(s, dict) else str(s)}
                for s in schulungen_raw
                if (isinstance(s, dict) and s.get('name')) or
                   (isinstance(s, str) and s.strip())
            ]
        elif isinstance(schulungen_raw, dict):
            pj['extracted_data']['schulungen'] = [
                {'name': s.get('name', '')}
                for s in schulungen_raw.get('schulungen', []) if s.get('name')
            ]

        certs_raw = specialist_results.get('fl_extract_zertifikate')
        if isinstance(certs_raw, list):
            pj['extracted_data']['certifications'] = certs_raw
        elif isinstance(certs_raw, dict):
            pj['extracted_data']['certifications'] = certs_raw.get('certifications', [])

        focus_exp_raw = specialist_results.get('fl_extract_focus_exp') or {}
        if isinstance(focus_exp_raw, dict):
            fex = focus_exp_raw.get('focus_experience', [])
            if isinstance(fex, list):
                pj['extracted_data']['focus_experience'] = fex
        elif isinstance(focus_exp_raw, list):
            pj['extracted_data']['focus_experience'] = focus_exp_raw

        exp_raw = specialist_results.get('fl_extract_experience')
        if isinstance(exp_raw, list):
            pj['extracted_data']['experience'] = exp_raw
        elif isinstance(exp_raw, dict):
            pj['extracted_data']['experience'] = exp_raw.get('experience', [])

        sonstiges = specialist_results.get('fl_extract_sonstiges') or {}
        if isinstance(sonstiges, dict) and sonstiges.get('other'):
            existing = pj['extracted_data'].get('other', '')
            pj['extracted_data']['other'] = (
                existing + '\n' + sonstiges['other'] if existing else sonstiges['other']
            )

        pj['metadata']['statistics'] = {
            'total_categories': sum(
                1 for v in pj['extracted_data']['skills'].values() if v),
            'has_personal':   bool(personal),
            'has_skills':     bool(pj['extracted_data']['focus_experience']),
            'has_experience': bool(pj['extracted_data']['experience']),
        }
        pj['audit']['created_at']  = now
        pj['audit']['source_file'] = source_url or dir_name
        pj['audit']['steps_completed'] = [
            s for s in ['kopf', 'personal', 'branchen', 'fachbereiche',
                        'schulungen', 'zertifikate', 'focus_exp', 'experience', 'sonstiges']
            if specialist_results.get(f'fl_extract_{s}') is not None
        ]
        return pj

    # ── Merge mit FL-API pre_json ─────────────────────────────────────────────

    def _merge_with_existing(self, new: dict, existing: dict) -> dict:
        import copy
        merged  = copy.deepcopy(new)
        ex_data = existing.get('extracted_data', {})

        ex_hl = existing.get('metadata', {}).get('headline', '')
        if ex_hl:
            merged['metadata']['headline'] = ex_hl
            merged['extracted_data']['personal']['headline'] = ex_hl

        ex_p  = ex_data.get('personal', {})
        new_p = merged['extracted_data']['personal']
        for f in ('availability', 'edv_experience_since', 'nationality', 'location'):
            if ex_p.get(f) and not new_p.get(f):
                new_p[f] = ex_p[f]

        ex_langs = ex_p.get('languages', [])
        if ex_langs:
            merged['extracted_data']['personal']['languages'] = ex_langs

        api_exp = ex_data.get('experience', [])
        llm_exp = merged['extracted_data']['experience']

        if api_exp and llm_exp:
            if len(api_exp) == len(llm_exp):
                for i, (a_e, l_e) in enumerate(zip(api_exp, llm_exp)):
                    a_techs = a_e.get('technologies', [])
                    l_techs = l_e.get('technologies', [])
                    if not a_techs and l_techs:
                        api_exp[i]['technologies'] = [
                            t for t in l_techs if t and 2 <= len(t.strip()) <= 60]
                    elif a_techs and l_techs:
                        seen = {t.lower() for t in a_techs}
                        for t in l_techs:
                            if t and t.lower() not in seen:
                                api_exp[i]['technologies'].append(t)
                                seen.add(t.lower())
                    l_acts = l_e.get('activities', [])
                    a_acts = a_e.get('activities', [])
                    if l_acts and len(l_acts) > len(a_acts):
                        api_exp[i]['activities'] = l_acts
                merged['extracted_data']['experience'] = api_exp
            else:
                logger.info(f"  Merge: API {len(api_exp)} vs LLM {len(llm_exp)} -> LLM")
        elif api_exp and not llm_exp:
            merged['extracted_data']['experience'] = api_exp

        ex_certs  = ex_data.get('certifications', [])
        new_certs = merged['extracted_data']['certifications']
        if ex_certs and not new_certs:
            merged['extracted_data']['certifications'] = ex_certs
        elif ex_certs and new_certs:
            seen = {c.get('name', '').lower() for c in new_certs}
            for c in ex_certs:
                if c.get('name', '').lower() not in seen:
                    new_certs.append(c)

        ex_focus = ex_data.get('focus_areas', [])
        if ex_focus:
            merged['extracted_data']['focus_areas'] = ex_focus

        ex_ind  = ex_data.get('industries', [])
        new_ind = merged['extracted_data']['industries']
        merged['extracted_data']['industries'] = list(
            dict.fromkeys(new_ind + ex_ind))[:15]

        ex_edu  = ex_data.get('education', [])
        new_edu = merged['extracted_data']['education']
        if ex_edu and not new_edu:
            merged['extracted_data']['education'] = ex_edu
        elif ex_edu and new_edu:
            seen = {e.get('degree', '').lower() for e in new_edu}
            for e in ex_edu:
                if e.get('degree', '').lower() not in seen:
                    new_edu.append(e)

        ex_id = existing.get('metadata', {}).get('source', {}).get('import_id', '')
        if ex_id:
            merged['metadata']['source']['import_id'] = ex_id

        return merged

    # ── Haupt-Pipeline ────────────────────────────────────────────────────────

    def extract_from_spans(self, spans, first_name='', last_name='',
                           dir_name='', source_url='') -> dict:
        return self._run_extraction(
            self._normalize_spans(spans),
            first_name, last_name, dir_name, source_url)

    def extract_from_dir(self, dir_path: str,
                         first_name='', last_name='', source_url='') -> dict:
        base   = Path(dir_path)
        ex_dir = base / 'extract'
        if not ex_dir.exists():
            return {'success': False, 'error': f'extract/ fehlt: {ex_dir}'}

        pj_path = base / 'profil.json'
        if pj_path.exists() and (not first_name or not last_name):
            try:
                person     = json.loads(pj_path.read_text(encoding='utf-8')).get('person', {})
                first_name = first_name or person.get('givenName', '')
                last_name  = last_name  or person.get('familyName', '')
            except Exception:
                pass

        if not first_name or not last_name:
            parts = base.name.replace('-', '_').split('_')
            if len(parts) >= 2:
                last_name  = last_name  or parts[0].capitalize()
                first_name = first_name or parts[1].capitalize()

        yx_files = sorted(ex_dir.glob('*_yx.txt'))
        if not yx_files:
            return {'success': False, 'error': 'Keine *_yx.txt gefunden'}

        all_spans: List[YxSpan] = []
        for p in yx_files:
            s = self._parse_yx_txt(p)
            logger.info(f"[FLPdfExtractor] {p.name}: {len(s)} Spans")
            all_spans.extend(s)

        logger.info(f"[FLPdfExtractor] {len(all_spans)} Spans gesamt")
        return self._run_extraction(all_spans, first_name, last_name,
                                    base.name, source_url)

    def _run_extraction(self, spans: List[YxSpan],
                        first_name: str, last_name: str,
                        dir_name: str, source_url: str) -> dict:
        start = time.time()
        now   = datetime.now().isoformat()
        logger.info(f"[FLPdfExtractor] START {first_name} {last_name} ({len(spans)} Spans)")

        raw_blocks = self._build_raw_blocks(spans)
        if not raw_blocks:
            return {'success': False, 'error': 'Keine Bloecke erkannt'}

        phase1          = self._phase1_classify(raw_blocks)
        consultant_type = phase1['consultant_type']
        assignments     = phase1['assignments']

        for b in raw_blocks:
            if b.index not in assignments:
                assignments[b.index] = 9

        area_texts         = self._collect_texts_by_area(raw_blocks, assignments)
        specialist_results = self._phase2_specialists(area_texts, consultant_type)

        pj = self._build_pre_json(
            specialist_results, first_name, last_name,
            dir_name, source_url, consultant_type, now)

        duration = round(time.time() - start, 1)
        n_exp = len(pj['extracted_data']['experience'])
        n_fe  = len(pj['extracted_data']['focus_experience'])
        logger.info(f"[FLPdfExtractor] FERTIG {duration}s | "
                    f"Typ: {consultant_type} | {n_exp} Projekte | {n_fe} Focus-Exp")

        return {
            'success':         True,
            'pre_json':        pj,
            'blocks':          len(raw_blocks),
            'consultant_type': consultant_type,
            'llm_calls':       1 + len([v for v in specialist_results.values()
                                         if v is not None]),
            'duration':        duration,
            'first_name':      first_name,
            'last_name':       last_name,
        }

    # ── extract_and_save ──────────────────────────────────────────────────────

    def extract_and_save(self, dir_path: str, overwrite: bool = False) -> dict:
        base          = Path(dir_path)
        pre_json_path = base / 'profil_pre_json.json'

        if pre_json_path.exists() and not overwrite:
            try:
                existing = json.loads(pre_json_path.read_text(encoding='utf-8'))
                steps    = existing.get('audit', {}).get('steps_completed', [])
                if 'experience' in steps or 'focus_exp' in steps:
                    logger.info(f"[FLPdfExtractor] {base.name}: bereits extrahiert")
                    return {'success': True, 'skipped': True, 'dir': str(base)}
            except Exception:
                pass

        result = self.extract_from_dir(str(base))
        if not result.get('success'):
            return result

        pj = result['pre_json']
        if pre_json_path.exists():
            try:
                existing = json.loads(pre_json_path.read_text(encoding='utf-8'))
                pj = self._merge_with_existing(pj, existing)
            except Exception as e:
                logger.warning(f"[FLPdfExtractor] Merge-Fehler: {e}")

        pre_json_path.write_text(
            json.dumps(pj, indent=2, ensure_ascii=False), encoding='utf-8')
        logger.info(f"[FLPdfExtractor] Gespeichert: {pre_json_path}")
        result['pre_json_path'] = str(pre_json_path)
        return result

    # ── Batch ─────────────────────────────────────────────────────────────────

    def extract_all_pending(self, fl_base: str = 'data/url/fl',
                             dry_run: bool = False) -> dict:
        base    = Path(fl_base)
        results = {'ok': [], 'error': [], 'skipped': []}
        dirs    = sorted([d for d in base.iterdir()
                          if d.is_dir() and not d.name.startswith('.')])
        logger.info(f"[FLPdfExtractor] {len(dirs)} Verzeichnisse")

        for d in dirs:
            ex_dir   = d / 'extract'
            yx_files = list(ex_dir.glob('*_yx.txt')) if ex_dir.exists() else []

            if not yx_files:
                results['skipped'].append({'dir': d.name, 'reason': 'keine yx.txt'})
                logger.info(f"  ⏭  {d.name}: keine yx.txt")
                continue

            if dry_run:
                results['ok'].append({'dir': d.name, 'dry_run': True})
                logger.info(f"  [DRY] {d.name}: {len(yx_files)} yx.txt")
                continue

            try:
                r = self.extract_and_save(str(d), overwrite=False)
                if r.get('skipped'):
                    results['skipped'].append({'dir': d.name, 'reason': 'bereits extrahiert'})
                    logger.info(f"  ⏭  {d.name}: bereits extrahiert")
                elif r.get('success'):
                    n = len(r.get('pre_json', {}).get('extracted_data', {})
                             .get('experience', []))
                    results['ok'].append({
                        'dir': d.name, 'duration': r.get('duration'),
                        'projects': n, 'consultant_type': r.get('consultant_type', ''),
                    })
                    logger.info(f"  ✅ {d.name} ({r.get('duration')}s, "
                                f"{n} Projekte, {r.get('consultant_type','')})")
                else:
                    results['error'].append({'dir': d.name, 'error': r.get('error')})
                    logger.warning(f"  ❌ {d.name}: {r.get('error')}")
            except Exception as e:
                results['error'].append({'dir': d.name, 'error': str(e)})
                logger.error(f"  ❌ {d.name}: {e}")

        logger.info(f"[FLPdfExtractor] OK={len(results['ok'])} "
                    f"ERR={len(results['error'])} SKIP={len(results['skipped'])}")
        return results


# ── Singleton ─────────────────────────────────────────────────────────────────
fl_pdf_extractor = FLPdfExtractor()
