"""
post_processor.py - Intelligenter Post-Processor für CV Extraktion

1. Token-basierter Vergleich (PDF vs extrahierte Daten)
2. LLM klassifiziert fehlende Tokens
3. Automatische Nachsortierung in DB
4. Skill-Normalisierung via normalize_skill_* Prompts
"""

import os
import re
import logging
from typing import Dict, Any, List, Tuple, Set
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

from .services.pdf_extractor import pdf_extractor

logger = logging.getLogger(__name__)


@dataclass
class PostProcessResult:
    coverage_percent:    float     = 0.0
    original_tokens:     int       = 0
    matched_tokens:      int       = 0
    missing_tokens:      List[str] = field(default_factory=list)
    missing_skills:      List[str] = field(default_factory=list)
    missing_products:    List[str] = field(default_factory=list)
    missing_other:       List[str] = field(default_factory=list)
    integrity_ok:        bool      = False
    recommendations:     List[str] = field(default_factory=list)
    auto_added_skills:   int       = 0
    auto_added_products: int       = 0
    normalized_skills:   int       = 0


# Wörter die immer ignoriert werden
IGNORE_TOKENS = {
    'und', 'oder', 'mit', 'von', 'für', 'auf', 'in', 'an', 'bei',
    'der', 'die', 'das', 'den', 'dem', 'des', 'ein', 'eine', 'einen',
    'ist', 'war', 'wird', 'werden', 'wurde', 'haben', 'hat',
    'seite', 'von', 'qualifikationsprofil', 'www', 'abcona', 'de',
    'telefon', 'fax', 'e-mail', 'internet', 'stand', 'nach', 'absprache',
    'datum', 'name', 'geburtsjahr', 'staatsangehörigkeit', 'sprachen',
    'verfügbar', 'einsatzort', 'ausbildung', 'berufliche', 'erfahrungen',
    'zeitraum', 'kunde', 'branche', 'rolle', 'position', 'projekttätigkeiten',
    'technologien', 'umfeld', 'weitere', 'projekte', 'auf', 'nachfrage',
    'aid', 'tt', 'schwerpunkt', 'active', 'business', 'consulting', 'agency',
}


def _get_workers() -> int:
    try:
        import json
        from django.conf import settings
        cfg_path = os.path.join(settings.BASE_DIR, 'settings.json')
        with open(cfg_path) as f:
            cfg = json.load(f)
        return int(cfg.get('pipeline', {}).get('parallel_workers_sections', 10))
    except Exception:
        return 10


class PostProcessor:

    def __init__(self):
        pass

    # ── Token-Extraktion ─────────────────────────────────────────────────────

    def _tokenize(self, text: str) -> Set[str]:
        tokens = re.findall(r'[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß0-9\.\-/]{2,}', text)
        return {t.lower() for t in tokens if t.lower() not in IGNORE_TOKENS}

    def _get_pdf_tokens(self, pdf_path: str) -> Tuple[Set[str], str]:
        if pdf_path.lower().endswith(('.doc', '.docx')):
            from .services.word_extractor import word_extractor
            result = word_extractor.extract(pdf_path)
        else:
            result = pdf_extractor.extract(pdf_path)
        full_text = ' '.join(s.text for s in result.spans)
        return self._tokenize(full_text), full_text

    def _get_extracted_tokens(self, result: Dict[str, Any]) -> Set[str]:
        parts = []
        ed   = result.get('extracted_data', {})
        meta = result.get('metadata', {})

        for v in meta.values():
            if isinstance(v, str): parts.append(v)

        personal = ed.get('personal', {})
        for v in personal.values():
            if isinstance(v, str): parts.append(v)
            elif isinstance(v, list): parts.extend([str(x) for x in v])

        for proj in ed.get('experience', []):
            parts.extend([proj.get('period',''), proj.get('company',''), proj.get('role','')])
            parts.extend(proj.get('activities', []))
            parts.extend(proj.get('technologies', []))

        for cert in ed.get('certifications', []):
            parts.append(cert.get('name',''))

        parts.extend(ed.get('industries', []))
        parts.extend(ed.get('focus_areas', []))
        parts.extend(ed.get('focus_experience', []))

        for edu in ed.get('education', []):
            parts.append(edu.get('degree',''))

        for skill_list in ed.get('skills', {}).values():
            parts.extend(skill_list)

        for s in ed.get('schulungen', []):
            if isinstance(s, dict): parts.append(s.get('name',''))
            else: parts.append(str(s))

        return self._tokenize(' '.join(parts))

    # ── LLM-Klassifikation fehlender Tokens ─────────────────────────────────

    def _classify_missing(self, missing_tokens: List[str],
                          consultant_context: str) -> Dict[str, List[str]]:
        if not missing_tokens:
            return {'skills': [], 'products': [], 'irrelevant': []}
        try:
            from .services.deepseek_api import deepseek_api
            from .models import PromptTemplate

            pt = PromptTemplate.objects.filter(
                stage='classify_missing_tokens', is_active=True
            ).first()

            if pt:
                prompt = pt.prompt_text.replace(
                    '{context}', consultant_context[:200]
                ).replace(
                    '{tokens}', ', '.join(missing_tokens[:40])
                )
            else:
                prompt = f"""Klassifiziere diese Begriffe aus einem CV ({consultant_context[:100]}).
Begriffe: {', '.join(missing_tokens[:40])}
- skill: konkrete IT-Technologie (NICHT Überschriften wie 'betriebssysteme')
- product: konkretes Produkt (NICHT Überschriften wie 'standards')
- irrelevant: Überschriften, Formatierungsfehler, Firmennamen, allgemeine Wörter
Antworte NUR mit JSON: {{"skills": [], "products": [], "irrelevant": []}}"""

            result = deepseek_api.extract(prompt, system_prompt="Antworte NUR mit JSON.")
            if result.success and result.data:
                data = result.data if isinstance(result.data, dict) else {}
                return {
                    'skills':     data.get('skills', []),
                    'products':   data.get('products', []),
                    'irrelevant': data.get('irrelevant', []),
                }
        except Exception as e:
            logger.warning(f"LLM-Klassifikation fehlgeschlagen: {e}")
        return {'skills': [], 'products': [], 'irrelevant': missing_tokens}

    # ── Auto-Nachsortierung ──────────────────────────────────────────────────

    def _auto_add_to_db(self, consultant, classified: Dict) -> Tuple[int, int]:
        from .models import Skill, ConsultantSkill, FocusExperience

        added_skills = 0
        for name in classified.get('skills', []):
            if name and len(name) > 2:
                skill, _ = Skill.objects.get_or_create(
                    name=name[:200],
                    defaults={'category_name': 'Sonstige Skills'}
                )
                _, created = ConsultantSkill.objects.get_or_create(
                    consultant=consultant, skill=skill,
                    defaults={'weight': 0.5}
                )
                if created:
                    added_skills += 1

        added_products = 0
        for name in classified.get('products', []):
            if name and len(name) > 2:
                _, created = FocusExperience.objects.get_or_create(
                    consultant=consultant, name=name[:500],
                    defaults={'category': 'auto_detected'}
                )
                if created:
                    added_products += 1

        return added_skills, added_products

    # ── Skill-Normalisierung ─────────────────────────────────────────────────

    def normalize_skills(self, consultant) -> int:
        """
        Normalisiert Skills eines Consultants via normalize_skill_* Prompts.
        1. Skills aus DB nach Kategorie gruppieren
        2. Pro Kategorie: normalize_skill_<Kategorie> Prompt aufrufen
           → bestätigt: bleibt
           → abgelehnt: Umsortierung versuchen
        3. Abgelehnte: durch alle anderen Kategorien testen
           → passt: neue Kategorie setzen
           → passt nirgendwo: bleibt in alter Kategorie
        Nichts wird gelöscht, nichts wird erfunden.
        Sätze/Satzfragmente (>5 Wörter) bleiben immer.
        Returns: Anzahl umsortierer Skills
        """
        from .models import Skill, ConsultantSkill, PromptTemplate
        from .services.deepseek_api import deepseek_api
        from collections import defaultdict

        logger.info(f"SKILL-NORMALISIERUNG START: {consultant.aid}")

        # Skills aus DB nach Kategorie
        skills_by_cat = defaultdict(list)
        skill_obj_map = {}  # name → Skill-Objekt
        for cs in consultant.skills.all().select_related('skill'):
            cat = cs.skill.category_name or 'LEER'
            skills_by_cat[cat].append(cs.skill.name)
            skill_obj_map[cs.skill.name] = cs.skill

        # Alle normalize_skill_* Prompts laden
        all_prompts = {}
        for pt in PromptTemplate.objects.filter(
            stage__startswith='normalize_skill_', is_active=True
        ):
            cat_name = pt.stage.replace('normalize_skill_', '')
            all_prompts[cat_name] = pt.prompt_text

        def is_satz(text):
            return len(text.split()) > 5

        def check_cat(cat):
            skills = skills_by_cat[cat]
            if cat not in all_prompts:
                return cat, skills, []
            prompt = all_prompts[cat].replace('{text}', ', '.join(skills))
            r = deepseek_api.extract(prompt, system_prompt='Antworte NUR mit JSON.')
            confirmed = []
            rejected  = []
            if r.success and r.data:
                data = r.data if isinstance(r.data, dict) else {}
                conf_list = []
                for v in data.values():
                    if isinstance(v, list):
                        conf_list.extend([str(x).strip().lower() for x in v])
                for s in skills:
                    if is_satz(s):
                        confirmed.append(s)
                    elif s.lower() in conf_list or any(s.lower() in x for x in conf_list):
                        confirmed.append(s)
                    else:
                        rejected.append(s)
            else:
                confirmed = skills
            return cat, confirmed, rejected

        # Schritt 1: Alle Kategorien parallel prüfen
        all_rejected = []
        workers = _get_workers()
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(check_cat, cat): cat
                       for cat in skills_by_cat.keys()}
            for future in as_completed(futures):
                cat, confirmed, rejected = future.result()
                all_rejected.extend([(s, cat) for s in rejected])
                logger.info(f"  {cat}: {len(confirmed)} ok, {len(rejected)} markiert")

        if not all_rejected:
            logger.info("  Keine Skills zum Umsortieren")
            return 0

        logger.info(f"  {len(all_rejected)} Skills markiert → Umsortierung versuchen")

        # Schritt 2: Markierte durch andere Kategorien testen
        def try_reclassify(skill, old_cat):
            if is_satz(skill):
                return skill, old_cat, None
            for try_cat, prompt_text in all_prompts.items():
                if try_cat == old_cat:
                    continue
                prompt = prompt_text.replace('{text}', skill)
                r = deepseek_api.extract(prompt, system_prompt='Antworte NUR mit JSON.')
                if r.success and r.data:
                    data = r.data if isinstance(r.data, dict) else {}
                    for v in data.values():
                        if isinstance(v, list) and any(
                            skill.lower() in str(x).lower() for x in v
                        ):
                            return skill, old_cat, try_cat
            return skill, old_cat, None

        moved = 0
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(try_reclassify, s, c): (s, c)
                       for s, c in all_rejected}
            for future in as_completed(futures):
                skill, old_cat, new_cat = future.result()
                if new_cat:
                    # Kategorie in DB updaten
                    skill_obj = skill_obj_map.get(skill)
                    if skill_obj:
                        skill_obj.category_name = new_cat
                        # Versuche auch FK zu setzen
                        from .models import SkillCategory
                        sc = SkillCategory.objects.filter(name=new_cat).first()
                        if sc:
                            skill_obj.category = sc
                        skill_obj.save(update_fields=['category_name', 'category'])
                        moved += 1
                        logger.info(f"  ✅ {skill}: {old_cat} → {new_cat}")
                else:
                    logger.info(f"  ➡️  {skill}: bleibt in {old_cat}")

        logger.info(f"SKILL-NORMALISIERUNG FERTIG: {moved} Skills umsortiert")
        return moved

    # ── Haupt-Analyse ────────────────────────────────────────────────────────

    def analyze(self, result: Dict[str, Any], pdf_path: str,
                consultant=None) -> PostProcessResult:

        logger.info("POST-PROCESSOR START")

        pdf_tokens, pdf_full_text = self._get_pdf_tokens(pdf_path)
        logger.info(f"  PDF Tokens: {len(pdf_tokens)}")

        extracted_tokens = self._get_extracted_tokens(result)
        logger.info(f"  Extrahierte Tokens: {len(extracted_tokens)}")

        matched  = pdf_tokens & extracted_tokens
        missing  = pdf_tokens - extracted_tokens
        coverage = (len(matched) / len(pdf_tokens) * 100) if pdf_tokens else 0
        logger.info(f"  Coverage: {coverage:.1f}% ({len(matched)}/{len(pdf_tokens)} Tokens)")

        missing_filtered = [t for t in missing if len(t) > 3 and not t.isdigit()]
        logger.info(f"  Fehlende bedeutsame Tokens: {len(missing_filtered)}")

        classified = {'skills': [], 'products': [], 'irrelevant': missing_filtered}
        if missing_filtered and consultant:
            context    = result.get('metadata', {}).get('headline', 'IT-Berater')
            classified = self._classify_missing(missing_filtered, context)
            logger.info(f"  LLM: {len(classified['skills'])} Skills, "
                        f"{len(classified['products'])} Produkte, "
                        f"{len(classified['irrelevant'])} irrelevant")

        added_skills = added_products = 0
        # Produkte nur hinzufügen wenn FOCUS_EXP Block vorhanden war (Mensch hat sortiert)
        has_focus_exp_block = bool(result.get('extracted_data', {}).get('focus_experience', []))
        if not has_focus_exp_block:
            classified['products'] = []
            logger.debug("  Kein FOCUS_EXP Block → Auto-Produkte deaktiviert")
        if consultant and (classified['skills'] or classified['products']):
            added_skills, added_products = self._auto_add_to_db(consultant, classified)
            if added_skills or added_products:
                logger.info(f"  Auto-hinzugefügt: {added_skills} Skills, "
                            f"{added_products} Produkte")

        recommendations = []
        if coverage < 85:
            recommendations.append(
                f"Token-Coverage {coverage:.0f}% — "
                f"{len(missing_filtered)} Begriffe nicht zugeordnet"
            )
        if added_skills:
            recommendations.append(f"{added_skills} Skills automatisch nachgetragen")
        if added_products:
            recommendations.append(f"{added_products} Produkte automatisch nachgetragen")

        return PostProcessResult(
            coverage_percent=coverage,
            original_tokens=len(pdf_tokens),
            matched_tokens=len(matched),
            missing_tokens=missing_filtered[:30],
            missing_skills=classified.get('skills', []),
            missing_products=classified.get('products', []),
            missing_other=classified.get('irrelevant', [])[:20],
            integrity_ok=coverage >= 85,
            recommendations=recommendations,
            auto_added_skills=added_skills,
            auto_added_products=added_products,
        )

    def print_summary(self, result: PostProcessResult):
        bar_len = 20
        filled  = int(result.coverage_percent / 100 * bar_len)
        bar     = '█' * filled + '░' * (bar_len - filled)
        quality = ('✅ Sehr gut' if result.coverage_percent >= 90 else
                   '✅ Gut'      if result.coverage_percent >= 80 else
                   '⚠️ Ausbaufähig')
        logger.info("=" * 50)
        logger.info("POST-PROCESSOR ERGEBNIS")
        logger.info(f"  Coverage: [{bar}] {result.coverage_percent:.1f}%  {quality}")
        logger.info(f"  Tokens:   {result.matched_tokens}/{result.original_tokens} gefunden")
        if result.missing_skills:
            logger.info(f"  → Neue Skills:   {result.missing_skills}")
        if result.missing_products:
            logger.info(f"  → Neue Produkte: {result.missing_products}")
        if result.auto_added_skills:
            logger.info(f"  ✅ Auto Skills hinzugefügt:   {result.auto_added_skills}")
        if result.auto_added_products:
            logger.info(f"  ✅ Auto Produkte hinzugefügt: {result.auto_added_products}")
        if result.normalized_skills:
            logger.info(f"  ✅ Skills normalisiert:       {result.normalized_skills}")
        if result.recommendations:
            for rec in result.recommendations:
                logger.info(f"  📋 {rec}")
        logger.info("=" * 50)


post_processor = PostProcessor()
