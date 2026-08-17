"""
main_post_processor.py — Post-Prozessor für main_pipeline

Läuft NACH pre_json Extraktion, VOR DB-Import.
Alles im RAM — kein Disk-Zugriff.

Schritte (regelbasiert, schnell):
  1. Rollen bereinigen       — title→role NUR wenn Title wie Rolle aussieht
  2. Technologien bereinigen — Duplikate, Stopwords, zu kurze
  3. Aktivitäten bereinigen  — Soft-Wrap-Fragmente mergen (nichts löschen)
  4. EDV-seit berechnen      — aus ältestem Projekt
  5. Token-Coverage prüfen   — wie viel % vom PDF wurde extrahiert?
  6. Fehlende Tokens LLM     — klassifiziert als skill/product/irrelevant
  7. Fehlende Skills         — in skill_ablage eintragen (dict-sicher)

Singleton: main_post_processor
"""
import copy
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple

logger = logging.getLogger(__name__)

IGNORE_TOKENS = {
    'und', 'oder', 'mit', 'von', 'für', 'auf', 'in', 'an', 'bei',
    'der', 'die', 'das', 'den', 'dem', 'des', 'ein', 'eine', 'einen',
    'ist', 'war', 'wird', 'werden', 'wurde', 'haben', 'hat',
    'seite', 'qualifikationsprofil', 'www', 'abcona', 'de',
    'telefon', 'fax', 'internet', 'stand', 'nach', 'absprache',
    'datum', 'name', 'geburtsjahr', 'staatsangehörigkeit', 'sprachen',
    'verfügbar', 'einsatzort', 'ausbildung', 'berufliche', 'erfahrungen',
    'zeitraum', 'kunde', 'branche', 'rolle', 'position', 'projekttätigkeiten',
    'technologien', 'umfeld', 'weitere', 'projekte', 'nachfrage',
    'aid', 'schwerpunkt', 'consulting', 'agency', 'profil', 'heute',
}

TECH_STOPWORDS = {
    'und', 'and', 'mit', 'with', 'the', 'or', 'oder',
    'etc', 'u.a.', 'z.b.', 'e.g.', 'various', 'verschiedene',
}

_INCOMPLETE_END_RE = re.compile(
    r'(?i)(-|/|\bund|\boder|\beiner|\beines|\beine|\bder|\bdie|\bdas|'
    r'\bden|\bdem|\bdes|\bvon|\bzu[rm]?|\bbei|\bmit|\bfür|\bdurch|'
    r'\binfolge|\baufgrund)$'
)

_ROLE_HINT_RE = re.compile(
    r'(experte|expertin|engineer|administrator|berater|consultant|'
    r'entwickler|architekt|spezialist|analyst|operator|manager|'
    r'lead|senior|junior|programmierer|supporter|dozent)',
    re.IGNORECASE,
)


@dataclass
class PostProcessResult:
    coverage_percent:  float     = 0.0
    original_tokens:   int       = 0
    matched_tokens:    int       = 0
    missing_skills:    List[str] = field(default_factory=list)
    missing_products:  List[str] = field(default_factory=list)
    auto_added_skills: int       = 0
    fixes:             List[str] = field(default_factory=list)
    integrity_ok:      bool      = False


class MainPostProcessor:

    def clean(self, pre_json: dict, pdf_path: str = '') -> dict:
        """
        Hauptmethode — bereinigt pre_json im RAM.
        pdf_path optional — wenn angegeben: Token-Coverage + LLM-Klassifikation.
        """
        result = copy.deepcopy(pre_json)
        ed     = result.setdefault('extracted_data', {})
        exps   = ed.get('experience', [])
        fixes  = []

        logger.info(f"[MainPostProcessor] START: {len(exps)} Projekte")

        # ── 1. Rollen bereinigen ──────────────────────────────────────────
        exps, r1 = self._clean_roles(exps)
        fixes.extend(r1)

        # ── 2. Technologien bereinigen ────────────────────────────────────
        exps, r2 = self._clean_technologies(exps)
        fixes.extend(r2)

        # ── 3. Aktivitäten bereinigen ─────────────────────────────────────
        exps, r3 = self._clean_activities(exps)
        fixes.extend(r3)

        # ── 4. EDV-seit berechnen ─────────────────────────────────────────
        result, r4 = self._fix_edv_since(result)
        fixes.extend(r4)
        ed   = result['extracted_data']
        exps = ed.get('experience', [])

        # ── 5-7. Token-Coverage + LLM (nur wenn pdf_path angegeben) ──────
        pp_result = PostProcessResult(fixes=fixes)
        if pdf_path:
            pp_result = self._token_coverage(result, ed, exps, pdf_path, fixes)

        ed['experience'] = exps
        result['extracted_data'] = ed
        result.setdefault('audit', {})['post_processor'] = {
            'fixes':            fixes,
            'coverage_percent': pp_result.coverage_percent,
            'auto_added_skills':pp_result.auto_added_skills,
            'integrity_ok':     pp_result.integrity_ok,
        }

        logger.info(
            f"[MainPostProcessor] FERTIG: "
            f"coverage={pp_result.coverage_percent:.1f}% | "
            f"fixes={len(fixes)} | "
            f"auto_skills={pp_result.auto_added_skills}"
        )
        return result

    # ── 1. Rollen bereinigen ──────────────────────────────────────────────

    def _clean_roles(self, exps: List[dict]) -> Tuple[List[dict], List[str]]:
        fixes = []
        for exp in exps:
            role  = (exp.get('role',  '') or '').strip()
            title = (exp.get('title', '') or '').strip()
            company = (exp.get('company', '') or '').strip()

            # company sieht aus wie Jobtitel, role leer → tauschen
            if company and not role and _ROLE_HINT_RE.search(company) and len(company) < 80:
                exp['role'] = company
                exp['company'] = ''
                fixes.append(f"ROLLE aus COMPANY: '{company}'")
                role = company
                company = ''

            # role enthält "Kunde / Branche"-Rest und company leer
            if role and not company:
                m = re.match(
                    r'^(?:kunde\s*/\s*branche|kunde|customer)\s*:\s*(.+)$',
                    role, re.IGNORECASE,
                )
                if m:
                    exp['company'] = m.group(1).strip()[:200]
                    exp['role'] = ''
                    fixes.append(f"COMPANY aus ROLE-Label: '{exp['company']}'")
                    role = ''

            # Title → Role NUR wenn Title wie eine Rolle aussieht
            if not role and title and self._title_looks_like_role(title):
                exp['role'] = title[:100]
                fixes.append(f"ROLLE aus TITLE: '{exp['role']}'")
            role = exp.get('role', '') or ''
            if len(role) > 160:
                exp['role'] = role[:160].rsplit(' ', 1)[0]
                fixes.append(f"ROLLE gekuerzt: '{exp['role']}'")
        return exps, fixes

    @staticmethod
    def _title_looks_like_role(title: str) -> bool:
        t = (title or '').strip()
        if not t or len(t) > 80:
            return False
        if t.endswith(':') or t.count(',') >= 2:
            return False
        if re.search(
            r'(?i)(support|administration|erweiterung|migration|'
            r'programmierung|entwicklung|projektbeschreibung)',
            t,
        ):
            return False
        return bool(
            _ROLE_HINT_RE.search(t)
            or re.search(r'(?i)(betreuung|zertifiziert|altersvorsorge)', t)
        )

    # ── 2. Technologien bereinigen ────────────────────────────────────────

    def _clean_technologies(self, exps: List[dict]) -> Tuple[List[dict], List[str]]:
        fixes = []
        for exp in exps:
            techs = exp.get('technologies', [])
            if not techs:
                continue
            seen  = set()
            clean = []
            for t in techs:
                if not isinstance(t, str):
                    continue
                t  = t.strip().rstrip('.,;')
                tl = t.lower()
                if len(t) < 2 or tl in TECH_STOPWORDS or tl in seen:
                    continue
                seen.add(tl)
                clean.append(t)
            if len(clean) != len(techs):
                fixes.append(
                    f"TECH: {len(techs)}→{len(clean)} "
                    f"bei '{exp.get('period', '')}'")
                exp['technologies'] = clean
        return exps, fixes

    # ── 3. Aktivitäten bereinigen ─────────────────────────────────────────

    def _clean_activities(self, exps: List[dict]) -> Tuple[List[dict], List[str]]:
        """Duplikate raus; kurze Soft-Wrap-Fragmente anhängen — Inhalt behalten."""
        fixes = []
        for exp in exps:
            acts = exp.get('activities', [])
            if not acts:
                continue
            merged = []
            for a in acts:
                if not isinstance(a, str):
                    continue
                a = a.strip()
                if not a:
                    continue
                # Nur Soft-Wrap-Fortsetzung anhängen; kurze Keywords (Analyse) behalten
                if merged and _INCOMPLETE_END_RE.search(merged[-1].rstrip()):
                    merged[-1] = f'{merged[-1].rstrip()} {a}'.strip()
                    continue
                merged.append(a)

            seen = set()
            clean = []
            for a in merged:
                key = a.lower()[:60]
                if key in seen:
                    continue
                seen.add(key)
                clean.append(a)

            if clean != [x for x in acts if isinstance(x, str) and x.strip()]:
                fixes.append(
                    f"ACT: {len(acts)}→{len(clean)} "
                    f"bei '{exp.get('period', '')}'")
                exp['activities'] = clean
        return exps, fixes

    # ── 4. EDV-seit berechnen ─────────────────────────────────────────────

    def _fix_edv_since(self, result: dict) -> Tuple[dict, List[str]]:
        fixes = []
        exps  = result.get('extracted_data', {}).get('experience', [])
        years = []
        for e in exps:
            period = e.get('period', '') or ''
            for y in re.findall(r'\b((?:19|20)\d{2})\b', period):
                try:
                    yr = int(y)
                    if 1970 <= yr <= 2030:
                        years.append(yr)
                except Exception:
                    pass
        if years:
            edv_since = min(years)
            personal  = result['extracted_data'].setdefault('personal', {})
            old       = personal.get('edv_experience_since')
            if not old or (isinstance(old, int) and old > edv_since):
                personal['edv_experience_since'] = edv_since
                fixes.append(f"EDV_SEIT: {old}→{edv_since}")
                logger.info(f"  [PostProcessor] EDV seit: {edv_since}")
        return result, fixes

    # ── 5-7. Token-Coverage + LLM ────────────────────────────────────────

    def _token_coverage(self, result: dict, ed: dict,
                        exps: List[dict], pdf_path: str,
                        fixes: List[str]) -> PostProcessResult:

        pp = PostProcessResult(fixes=fixes)

        # Tokens aus PDF
        try:
            pdf_tokens = self._get_pdf_tokens(pdf_path)
            logger.info(f"  [PostProcessor] PDF Tokens: {len(pdf_tokens)}")
        except Exception as e:
            logger.warning(f"  [PostProcessor] PDF-Tokenisierung fehlgeschlagen: {e}")
            return pp

        # Tokens aus pre_json
        extracted_tokens = self._get_extracted_tokens(result)
        logger.info(f"  [PostProcessor] Extrahierte Tokens: {len(extracted_tokens)}")

        matched  = pdf_tokens & extracted_tokens
        missing  = pdf_tokens - extracted_tokens
        coverage = (len(matched) / len(pdf_tokens) * 100) if pdf_tokens else 0

        pp.coverage_percent = coverage
        pp.original_tokens  = len(pdf_tokens)
        pp.matched_tokens   = len(matched)
        pp.integrity_ok     = coverage >= 80

        logger.info(
            f"  [PostProcessor] Coverage: {coverage:.1f}% "
            f"({len(matched)}/{len(pdf_tokens)})"
        )

        # Nur bedeutsame fehlende Tokens
        missing_filtered = [
            t for t in missing
            if len(t) > 3 and not t.isdigit()
        ]
        logger.info(
            f"  [PostProcessor] Fehlende Tokens: {len(missing_filtered)}"
        )

        if not missing_filtered:
            return pp

        # LLM klassifiziert fehlende Tokens
        classified = self._classify_missing(
            missing_filtered,
            result.get('metadata', {}).get('headline', 'IT-Berater')
        )
        pp.missing_skills   = classified.get('skills', [])
        pp.missing_products = classified.get('products', [])

        logger.info(
            f"  [PostProcessor] LLM: "
            f"{len(pp.missing_skills)} Skills, "
            f"{len(pp.missing_products)} Produkte"
        )

        # Fehlende Skills in skill_ablage eintragen (dict-sicher)
        if pp.missing_skills:
            ablage = ed.setdefault('skill_ablage', [])
            existing = set()
            for s in ablage:
                if isinstance(s, dict):
                    existing.add((s.get('name') or '').strip().lower())
                elif isinstance(s, str):
                    existing.add(s.strip().lower())
            added = 0
            for skill in pp.missing_skills:
                name = (skill if isinstance(skill, str) else str(skill or '')).strip()
                if not name or len(name) <= 2 or name.lower() in existing:
                    continue
                ablage.append({'name': name, 'category': 'Sonstige Skills'})
                existing.add(name.lower())
                added += 1
            if added:
                pp.auto_added_skills = added
                fixes.append(f"AUTO_SKILLS: +{added} in skill_ablage")
                logger.info(
                    f"  [PostProcessor] +{added} Skills in skill_ablage"
                )

        return pp

    # ── Hilfsmethoden ─────────────────────────────────────────────────────

    def _tokenize(self, text: str) -> Set[str]:
        tokens = re.findall(
            r'[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß0-9\.\-/]{2,}', text
        )
        return {
            t.lower() for t in tokens
            if t.lower() not in IGNORE_TOKENS
        }

    @staticmethod
    def _as_text_parts(obj) -> List[str]:
        """Dict/List/str → Textteile für Tokenisierung (kein str(dict)-Müll)."""
        if obj is None:
            return []
        if isinstance(obj, str):
            return [obj] if obj.strip() else []
        if isinstance(obj, dict):
            parts = []
            for k in ('name', 'degree', 'institution', 'title', 'content', 'category'):
                v = obj.get(k)
                if isinstance(v, str) and v.strip():
                    parts.append(v)
            return parts
        if isinstance(obj, list):
            out = []
            for x in obj:
                out.extend(MainPostProcessor._as_text_parts(x))
            return out
        return [str(obj)]

    def _get_pdf_tokens(self, pdf_path: str) -> Set[str]:
        if pdf_path.lower().endswith(('.doc', '.docx')):
            from apps.cv_extractor.services.main_word_extractor import MainWordExtractor
            ext    = MainWordExtractor()
            result = ext.extract(pdf_path)
        else:
            from apps.cv_extractor.services.main_pdf_extractor import PDFExtractor
            ext    = PDFExtractor()
            result = ext.extract(pdf_path)
        full_text = ' '.join(s.text for s in result.spans)
        return self._tokenize(full_text)

    def _get_extracted_tokens(self, result: Dict[str, Any]) -> Set[str]:
        parts    = []
        ed       = result.get('extracted_data', {})
        meta     = result.get('metadata', {})

        for v in meta.values():
            parts.extend(self._as_text_parts(v))

        parts.extend(self._as_text_parts(ed.get('personal', {})))

        for proj in ed.get('experience', []):
            if not isinstance(proj, dict):
                continue
            parts.extend([
                proj.get('period', '') or '',
                proj.get('company', '') or '',
                proj.get('role', '') or '',
                proj.get('title', '') or '',
            ])
            parts.extend(self._as_text_parts(proj.get('activities', [])))
            parts.extend(self._as_text_parts(proj.get('technologies', [])))

        parts.extend(self._as_text_parts(ed.get('certifications', [])))
        parts.extend(self._as_text_parts(ed.get('industries', [])))
        parts.extend(self._as_text_parts(ed.get('focus_areas', [])))
        parts.extend(self._as_text_parts(ed.get('focus_experience', [])))
        parts.extend(self._as_text_parts(ed.get('skill_ablage', [])))
        parts.extend(self._as_text_parts(ed.get('education', [])))

        for skill_list in (ed.get('skills') or {}).values():
            parts.extend(self._as_text_parts(skill_list))

        return self._tokenize(' '.join(str(p) for p in parts if p))

    def _classify_missing(self, missing_tokens: List[str],
                          context: str) -> Dict[str, List[str]]:
        if not missing_tokens:
            return {'skills': [], 'products': [], 'irrelevant': []}
        try:
            from apps.cv_extractor.services.deepseek_api import deepseek_api
            from apps.cv_extractor.models import PromptTemplate

            pt = PromptTemplate.objects.filter(
                stage='classify_missing_tokens', is_active=True
            ).first()

            if pt:
                prompt = (pt.prompt_text
                          .replace('{context}', context[:200])
                          .replace('{tokens}',  ', '.join(missing_tokens[:40])))
            else:
                prompt = (
                    f"Klassifiziere diese Begriffe aus einem CV "
                    f"({context[:100]}).\n"
                    f"Begriffe: {', '.join(missing_tokens[:40])}\n"
                    f"- skill: konkrete IT-Technologie\n"
                    f"- product: konkretes Produkt/Standard\n"
                    f"- irrelevant: Überschriften, Formatierung, "
                    f"  Firmennamen, allgemeine Wörter\n"
                    f'Antworte NUR mit JSON: '
                    f'{{"skills": [], "products": [], "irrelevant": []}}'
                )

            r = deepseek_api.extract(prompt, system_prompt='Antworte NUR mit JSON.')
            if r.success and isinstance(r.data, dict):
                return {
                    'skills':     r.data.get('skills',     []),
                    'products':   r.data.get('products',   []),
                    'irrelevant': r.data.get('irrelevant', []),
                }
        except Exception as e:
            logger.warning(f"  [PostProcessor] LLM fehlgeschlagen: {e}")
        return {'skills': [], 'products': [], 'irrelevant': missing_tokens}


main_post_processor = MainPostProcessor()
