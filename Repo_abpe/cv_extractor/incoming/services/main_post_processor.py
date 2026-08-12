"""
main_post_processor.py — Post-Prozessor für main_pipeline

Läuft NACH pre_json Extraktion, VOR DB-Import.
Alles im RAM — kein Disk-Zugriff.

Schritte (regelbasiert, schnell):
  1. Rollen bereinigen       — role aus title wenn leer, zu lange kürzen
  2. Technologien bereinigen — Duplikate, Stopwords, zu kurze
  3. Aktivitäten bereinigen  — Duplikate, zu kurze
  4. EDV-seit berechnen      — aus ältestem Projekt
  5. Token-Coverage prüfen   — wie viel % vom PDF wurde extrahiert?
  6. Fehlende Tokens LLM     — klassifiziert als skill/product/irrelevant
  7. Fehlende Skills         — in skill_ablage eintragen (nicht überschreiben)

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
            if not role and title:
                exp['role'] = title
                fixes.append(f"ROLLE aus TITLE: '{title}'")
            role = exp.get('role', '') or ''
            if len(role) > 100:
                exp['role'] = role[:100].rsplit(' ', 1)[0]
                fixes.append(f"ROLLE gekuerzt: '{exp['role']}'")
        return exps, fixes

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
        fixes = []
        for exp in exps:
            acts = exp.get('activities', [])
            if not acts:
                continue
            seen  = set()
            clean = []
            for a in acts:
                if not isinstance(a, str):
                    continue
                a = a.strip()
                if len(a) < 10:
                    continue
                key = a.lower()[:60]
                if key in seen:
                    continue
                seen.add(key)
                clean.append(a)
            if len(clean) != len(acts):
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
            period = e.get('period', '')
            if not period:
                continue
            found = re.findall(r'\b(19|20)\d{2}\b', period)
            for y in found:
                try:
                    yr = int(y + period[period.find(y)+4:period.find(y)+6]
                             if False else y)
                    if 1970 <= yr <= 2030:
                        years.append(yr)
                except Exception:
                    pass
        if years:
            edv_since = min(years)
            personal  = result['extracted_data'].setdefault('personal', {})
            old       = personal.get('edv_experience_since')
            if not old or old > edv_since:
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

        # Fehlende Skills in skill_ablage eintragen
        if pp.missing_skills:
            existing_ablage = set(
                s.lower() for s in ed.get('skill_ablage', [])
            )
            added = 0
            for skill in pp.missing_skills:
                if (skill and len(skill) > 2 and
                        skill.lower() not in existing_ablage):
                    ed.setdefault('skill_ablage', []).append(skill)
                    existing_ablage.add(skill.lower())
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
            if isinstance(v, str):
                parts.append(v)

        personal = ed.get('personal', {})
        for v in personal.values():
            if isinstance(v, str):
                parts.append(v)
            elif isinstance(v, list):
                parts.extend([str(x) for x in v])

        for proj in ed.get('experience', []):
            parts.extend([
                proj.get('period', ''),
                proj.get('company', ''),
                proj.get('role', ''),
            ])
            parts.extend(proj.get('activities', []))
            parts.extend(proj.get('technologies', []))

        for cert in ed.get('certifications', []):
            parts.append(cert.get('name', ''))

        parts.extend(ed.get('industries', []))
        parts.extend(ed.get('focus_areas', []))
        parts.extend(ed.get('focus_experience', []))
        parts.extend(ed.get('skill_ablage', []))

        for edu in ed.get('education', []):
            parts.append(edu.get('degree', ''))

        for skill_list in ed.get('skills', {}).values():
            parts.extend(skill_list)

        return self._tokenize(' '.join(str(p) for p in parts))

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
