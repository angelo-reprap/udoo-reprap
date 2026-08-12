"""
self_learning_pipeline.py

Zwei Aufgaben:

1. process() — synchron, kein LLM
   - TrainingTerm Frequenzen erhoehen
   - Industry + FocusArea Frequenzen erhoehen
   - PromptTemplate Beispiele aktualisieren

2. process_unknown_skills() — async (Celery), LLM (DeepSeek)
   - Key parsen: "OSPF.AID-mm_1.2.3.1.exp_42&45.Mustermann.Max"
   - Experience Objekte aus DB holen (warten bis verfuegbar)
   - Kontext-String aufbauen (bereits im Key-Dict enthalten)
   - LLM: Skill + Projekt-Kontext → Kategorie (1 der 28 Kategorien)
   - TrainingTerm anlegen (source='self_learning_llm', confidence=0.80)
   - Skill.category_name aktualisieren (nur wenn 'Sonstige Skills')
   - ConsultantSkill.category_name + weight aktualisieren
   - HTML DE + EN neu generieren
   LLM-Slots: max parallel_workers_projects (aus settings.json, alle durch llm_rate_limiter)
   Bei 429: exponential backoff 2s, 4s, 8s
   1s Pause zwischen Calls
"""

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional

from django.db import transaction
from django.db.models import F

logger = logging.getLogger(__name__)

CATEGORY_DISPLAY = {
    'architecture_pattern':    'Architekturmuster',
    'business_software':       'Business Software',
    'ci_cd_tool':              'CI/CD Tools',
    'cloud_platform':          'Cloud-Plattformen',
    'communication_tool':      'Kommunikationstools',
    'database':                'Datenbanken',
    'data_format':             'Datenformate',
    'data_management':         'Datenmanagement',
    'development_environment': 'Entwicklungsumgebungen',
    'devops_tool':             'DevOps Tools',
    'documentation_tool':      'Dokumentationstools',
    'framework':               'Frameworks und Bibliotheken',
    'hardware':                'Hardware',
    'identity_management':     'Identity Management',
    'it_infrastructure':       'IT-Infrastruktur',
    'methodology':             'Methoden',
    'monitoring_tool':         'Monitoring Tools',
    'network_protocol':        'Netzwerkprotokolle',
    'operating_system':        'Betriebssysteme',
    'programming_languages':   'Programmiersprachen',
    'project_management':      'Projektmanagement Tools',
    'security_tool':           'Security Tools',
    'soft_skill':              'Soft Skills',
    'special_concept':         'Spezielle Konzepte',
    'testing_tool':            'Testing Tools',
    'version_control':         'Versionsverwaltung',
    'virtualization':          'Virtualisierung',
    'special_skill':           'Sonstige Skills',
}

MIN_FREQ_FOR_PROMPT  = 3
MIN_CONF_FOR_PROMPT  = 0.7
MAX_EXAMPLES_PER_CAT = 10
MAX_WAIT_FOR_DB      = 30   # Sekunden warten auf Experience in DB
DB_CHECK_INTERVAL    =  2   # Sekunden zwischen DB-Pruefungen
CALL_PAUSE           =  1   # Sekunden Pause zwischen LLM-Calls
MAX_RETRIES          =  3   # Max Retries bei 429


def _get_llm_workers() -> int:
    """Liest parallel_workers_projects aus settings.json."""
    import json, os
    try:
        from django.conf import settings
        cfg_path = os.path.join(settings.BASE_DIR, 'settings.json')
        with open(cfg_path) as f:
            cfg = json.load(f)
        workers = int(cfg.get('pipeline', {}).get('parallel_workers_projects', 10))
        return max(1, workers)
    except Exception:
        return 10


def _parse_unknown_skill_key(key: str) -> Optional[Dict]:
    """
    Parst den strukturierten Key:
    "OSPF.AID-mm_1.2.3.1.exp_42&45.Mustermann.Max"

    Gibt zurueck:
    {
      'skill':      'OSPF',
      'aid':        'AID-mm_1.2.3.1',
      'exp_ids':    [42, 45],
      'last_name':  'Mustermann',
      'first_name': 'Max',
    }
    """
    try:
        # Split: erst Skill-Name via | abtrennen, dann Rest via .
        if '|' in key:
            skill_name, rest = key.split('|', 1)
            parts = [skill_name] + rest.split('.')
        else:
            # Legacy-Format (Punkt als Trenner)
            parts = key.split('.')
        if len(parts) < 3:
            return None

        skill_name = parts[0]  # bereits korrekt gesetzt (| oder legacy .)

        # AID: zweiter Teil — kann Punkte enthalten (AID-mm_1.2.3.1)
        # exp_ Teil finden
        exp_idx = None
        for i, p in enumerate(parts):
            if p.startswith('exp_'):
                exp_idx = i
                break

        if exp_idx is None:
            return None

        aid       = '.'.join(parts[1:exp_idx])
        exp_part  = parts[exp_idx]           # "exp_42&45"
        last_name  = parts[exp_idx + 1] if len(parts) > exp_idx + 1 else ''
        first_name = parts[exp_idx + 2] if len(parts) > exp_idx + 2 else ''

        # exp_ids parsen
        exp_str = exp_part.replace('exp_', '')
        exp_ids = []
        for eid in exp_str.split('&'):
            try:
                exp_ids.append(int(eid))
            except ValueError:
                pass

        return {
            'skill':      skill_name,
            'aid':        aid,
            'exp_ids':    exp_ids,
            'last_name':  last_name,
            'first_name': first_name,
        }
    except Exception as e:
        logger.warning(f"Key parsen fehlgeschlagen '{key}': {e}")
        return None


def _wait_for_experiences(exp_ids: List[int]) -> List:
    """
    Wartet bis Experience-Objekte in DB verfuegbar sind.
    Gibt Liste der Experience-Objekte zurueck.
    Max MAX_WAIT_FOR_DB Sekunden warten.
    """
    from apps.cv_extractor.models import Experience

    if not exp_ids:
        return []

    waited = 0
    while waited < MAX_WAIT_FOR_DB:
        exps = list(Experience.objects.filter(id__in=exp_ids))
        if len(exps) == len(exp_ids):
            return exps
        if waited == 0:
            logger.info(
                f"Warte auf Experience-Objekte {exp_ids} in DB "
                f"(gefunden: {len(exps)}/{len(exp_ids)})..."
            )
        time.sleep(DB_CHECK_INTERVAL)
        waited += DB_CHECK_INTERVAL

    # Teilweise verfuegbar → mit vorhandenen fortfahren
    exps = list(Experience.objects.filter(id__in=exp_ids))
    logger.warning(
        f"Experience-Objekte nur teilweise verfuegbar: "
        f"{len(exps)}/{len(exp_ids)} nach {waited}s"
    )
    return exps


def _build_llm_prompt(skill_name: str, context_str: str,
                       last_name: str, first_name: str) -> str:
    """
    Baut den LLM-Prompt fuer einen unbekannten Skill.
    Kategorien dynamisch aus SkillCategory DB.
    """
    from apps.cv_extractor.models import SkillCategory

    categories = SkillCategory.objects.filter(
        is_active=True
    ).order_by('sort_order', 'name')

    cat_lines = []
    for cat in categories:
        desc = (cat.description or '').strip()
        if desc:
            cat_lines.append(f"- {cat.name}: {desc}")
        else:
            cat_lines.append(f"- {cat.name}")

    berater = f"{first_name} {last_name}".strip()
    context_block = f"\nProjekt-Kontext:\n{context_str}\n" if context_str else ""

    prompt = (
        f"Du bist ein IT-Skill-Kategorisierungs-Experte.\n\n"
        f"Berater: {berater}\n"
        f"Skill: {skill_name}\n"
        f"{context_block}\n"
        f"Ordne den Skill GENAU EINER der folgenden Kategorien zu.\n"
        f"Antworte NUR mit einem JSON-Objekt: "
        f'{{\"category\": \"Kategoriename\"}}\n\n'
        f"KATEGORIEN:\n"
        f"{chr(10).join(cat_lines)}\n\n"
        f"REGELN:\n"
        f"- Nutze den Projekt-Kontext um die beste Kategorie zu bestimmen\n"
        f"- Wenn unsicher: 'Sonstige Skills'\n"
        f"- Antworte NUR mit JSON, keine Erklaerungen"
    )
    return prompt


def _call_llm_with_retry(prompt: str, skill_name: str) -> Optional[str]:
    """
    DeepSeek API Call mit exponential backoff bei 429.
    Gibt Kategorie-String zurueck oder None bei Fehler.
    """
    from apps.cv_extractor.services.deepseek_api import deepseek_api
    from apps.cv_extractor.services.llm_rate_limiter import llm_slot

    wait = 2
    for attempt in range(MAX_RETRIES):
        try:
            with llm_slot(label=f'self_learning:{skill_name}'):
                result = deepseek_api.extract(
                    prompt,
                    system_prompt=(
                        'Antworte NUR mit einem JSON-Objekt. '
                        'Keine Erklaerungen. Kein Markdown.'
                    )
                )

            if result.success and result.data:
                data = result.data
                if isinstance(data, dict):
                    cat = data.get('category', '').strip()
                    if cat:
                        return cat
                elif isinstance(data, str):
                    import json as _json
                    try:
                        d = _json.loads(data)
                        cat = d.get('category', '').strip()
                        if cat:
                            return cat
                    except Exception:
                        pass

            logger.warning(f"LLM leere Antwort fuer '{skill_name}' (Versuch {attempt+1})")

        except Exception as e:
            err_str = str(e)
            if '429' in err_str:
                logger.warning(
                    f"LLM 429 fuer '{skill_name}' — "
                    f"warte {wait}s (Versuch {attempt+1}/{MAX_RETRIES})"
                )
                time.sleep(wait)
                wait *= 2
                continue
            else:
                logger.error(f"LLM Fehler fuer '{skill_name}': {e}")
                break

    return None


def _process_single_unknown_skill(unknown: Dict) -> Dict:
    """
    Verarbeitet einen unbekannten Skill komplett:
    1. Experience aus DB holen
    2. LLM aufrufen
    3. DB aktualisieren (TrainingTerm, Skill, ConsultantSkill)

    Gibt Status-Dict zurueck.
    """
    key        = unknown.get('key', '')
    skill_name = unknown.get('skill', '')
    context    = unknown.get('context', '')
    exp_ids    = unknown.get('exp_ids', [])

    parsed = _parse_unknown_skill_key(key)
    if not parsed:
        return {'key': key, 'success': False, 'error': 'Key nicht parsebar'}

    last_name  = parsed['last_name']
    first_name = parsed['first_name']
    aid        = parsed['aid']

    # Experience aus DB holen (warten bis verfuegbar)
    exps = _wait_for_experiences(exp_ids)

    # Kontext aus DB neu aufbauen wenn kein Kontext im Key
    if not context and exps:
        from apps.cv_extractor.services.main_skill_normalizer import (
            _select_projects_for_context
        )
        _, context = _select_projects_for_context(exps)

    # LLM aufrufen
    prompt   = _build_llm_prompt(skill_name, context, last_name, first_name)
    category = _call_llm_with_retry(prompt, skill_name)

    if not category or category == 'Sonstige Skills':
        logger.info(f"  Self-Learning: '{skill_name}' → bleibt 'Sonstige Skills'")
        return {
            'key':      key,
            'skill':    skill_name,
            'success':  False,
            'category': 'Sonstige Skills',
        }

    # Pause zwischen Calls
    time.sleep(CALL_PAUSE)

    # DB aktualisieren
    try:
        _update_db_for_skill(skill_name, category, aid, exps)
        logger.info(f"  Self-Learning: '{skill_name}' → '{category}' ✅")
        return {
            'key':      key,
            'skill':    skill_name,
            'success':  True,
            'category': category,
        }
    except Exception as e:
        logger.error(f"  Self-Learning DB-Update fehlgeschlagen '{skill_name}': {e}")
        return {
            'key':     key,
            'skill':   skill_name,
            'success': False,
            'error':   str(e),
        }


@transaction.atomic
def _update_db_for_skill(skill_name: str, category: str,
                          aid: str, exps: list):
    """
    Aktualisiert DB nach LLM-Kategorisierung:
    - TrainingTerm anlegen/aktualisieren
    - Skill.category_name aktualisieren (nur wenn 'Sonstige Skills')
    - ConsultantSkill.category_name + weight aktualisieren
    """
    from apps.cv_extractor.models import (
        TrainingTerm, Skill, ConsultantSkill, SkillCategory, Consultant
    )
    from apps.cv_extractor.services.main_skill_normalizer import (
        _count_to_weight, _get_months
    )
    from concurrent.futures import ThreadPoolExecutor

    # 1. TrainingTerm anlegen oder aktualisieren
    tt, created = TrainingTerm.objects.get_or_create(
        term=skill_name[:200],
        defaults={
            'category':   category,
            'confidence': 0.80,
            'frequency':  1,
            'source':     'self_learning_llm',
        }
    )
    if not created:
        tt.frequency  += 1
        tt.confidence  = min(0.99, tt.confidence + 0.05)
        if tt.category == 'Sonstige Skills':
            tt.category = category
            tt.source   = 'self_learning_llm'
        tt.save(update_fields=['frequency', 'confidence', 'category', 'source'])

    # 2. Skill.category_name aktualisieren (nur wenn Sonstige Skills)
    cat_obj = SkillCategory.objects.filter(name=category).first()
    Skill.objects.filter(
        name=skill_name,
        category_name='Sonstige Skills'
    ).update(
        category_name=category,
        category=cat_obj,
    )

    # 3. ConsultantSkill aktualisieren
    # Consultant via AID finden
    try:
        consultant = Consultant.objects.get(aid=aid)
    except Consultant.DoesNotExist:
        logger.warning(f"Consultant {aid} nicht gefunden")
        return

    skill_obj = Skill.objects.filter(name=skill_name).first()
    if not skill_obj:
        return

    cs = ConsultantSkill.objects.filter(
        consultant=consultant,
        skill=skill_obj,
    ).first()

    if not cs:
        return

    # Gewichtung neu berechnen mit korrekter Kategorie
    count         = cs.weight  # Naeherung — echten Count haben wir nicht mehr
    project_count = len(exps)
    periods       = [getattr(exp, 'period', '') or '' for exp in exps]

    with ThreadPoolExecutor(max_workers=4) as executor:
        months_list = list(executor.map(_get_months, periods))
    total_months = sum(months_list)

    project_count = max(1, project_count)
    total_months  = max(6, total_months)

    # count aus ConsultantSkill.weight rueckrechnen — Naeherung
    # Besser: direkt 1 nehmen als Basis
    new_weight = _count_to_weight(1, project_count, total_months)

    cs.category_name = category
    cs.weight        = max(cs.weight, new_weight)
    cs.save(update_fields=['category_name', 'weight'])


class SelfLearningPipeline:

    def __init__(self):
        logger.info("SelfLearningPipeline initialisiert")

    @transaction.atomic
    def process(self, consultant, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Stufe 1 — synchron, kein LLM.
        TrainingTerm + Industry + FocusArea Frequenzen erhoehen.
        PromptTemplate Beispiele aktualisieren.
        """
        logger.info(f"Self-Learning (sync) fuer {consultant.aid}")

        extracted = extracted_data.get('extracted_data', {})
        stats = {'terms_updated': 0, 'terms_created': 0, 'prompts_updated': 0}

        # ── 1. Skills aus ConsultantSkill DB ─────────────────────────────
        skill_count = 0
        for cs in consultant.skills.select_related('skill').all():
            skill_name    = cs.skill.name
            category_name = (cs.category_name or
                             cs.skill.category_name or
                             'Sonstige Skills')
            if skill_name and len(skill_name) > 1:
                created = self._update_training_term(skill_name, category_name)
                if created:
                    stats['terms_created'] += 1
                else:
                    stats['terms_updated'] += 1
                skill_count += 1

        # Fallback: aus extracted_data.skills{}
        if skill_count == 0:
            skills_data = extracted.get('skills', {})
            for cat_key, skill_list in skills_data.items():
                if not skill_list:
                    continue
                category_name = CATEGORY_DISPLAY.get(cat_key, cat_key)
                for skill_name in skill_list:
                    if skill_name and isinstance(skill_name, str) and len(skill_name) > 1:
                        created = self._update_training_term(skill_name, category_name)
                        if created:
                            stats['terms_created'] += 1
                        else:
                            stats['terms_updated'] += 1

        # ── 2. Industries ─────────────────────────────────────────────────
        for industry_name in extracted.get('industries', []):
            if industry_name:
                self._update_frequency('Industry', industry_name)

        # ── 3. FocusAreas ─────────────────────────────────────────────────
        for focus_name in extracted.get('focus_areas', []):
            if focus_name:
                self._update_frequency('FocusArea', focus_name)

        # ── 4. PromptTemplate Beispiele ───────────────────────────────────
        stats['prompts_updated'] = self._update_prompt_examples()

        logger.info(
            f"Self-Learning (sync) abgeschlossen: "
            f"{stats['terms_created']} neu, "
            f"{stats['terms_updated']} aktualisiert, "
            f"{stats['prompts_updated']} Prompts"
        )
        return stats

    def process_unknown_skills(self, unknown_skills: List[Dict]) -> Dict[str, Any]:
        """
        Stufe 2 — async (Celery), LLM (DeepSeek).
        Verarbeitet unbekannte Skills parallel (max parallel_workers_projects aus settings.json).

        unknown_skills: Liste von Dicts aus main_skill_normalizer.normalize():
          [{'key': 'OSPF.AID-mm_1.2.3.1.exp_42&45.Mustermann.Max',
            'skill': 'OSPF',
            'context': 'Projekt: ...',
            'exp_ids': [42, 45],
            'count': 3}, ...]

        Gibt Stats-Dict zurueck.
        """
        if not unknown_skills:
            return {'processed': 0, 'categorized': 0, 'failed': 0}

        workers = _get_llm_workers()
        logger.info(
            f"Self-Learning (async LLM) Start: "
            f"{len(unknown_skills)} Skills, {workers} parallele Slots"
        )

        stats = {'processed': 0, 'categorized': 0, 'failed': 0}
        html_aids = set()  # AIDs fuer HTML-Regenerierung

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_process_single_unknown_skill, u): u
                for u in unknown_skills
            }
            for future in as_completed(futures):
                result = future.result()
                stats['processed'] += 1
                if result.get('success'):
                    stats['categorized'] += 1
                    # AID fuer HTML-Regenerierung merken
                    parsed = _parse_unknown_skill_key(result.get('key', ''))
                    if parsed:
                        html_aids.add(parsed['aid'])
                else:
                    stats['failed'] += 1

        # HTML neu generieren fuer betroffene Consultants
        for aid in html_aids:
            self._regenerate_html(aid)

        logger.info(
            f"Self-Learning (async LLM) abgeschlossen: "
            f"{stats['categorized']}/{stats['processed']} kategorisiert, "
            f"{stats['failed']} fehlgeschlagen"
        )
        return stats

    def _regenerate_html(self, aid: str):
        """Regeneriert DE-HTML (und EN falls vorhanden) fuer einen Consultant."""
        try:
            from apps.cv_extractor.models import Consultant
            from apps.cv_extractor.generator.html.html_generator import HTMLGenerator

            consultant = Consultant.objects.filter(aid=aid).first()
            if not consultant:
                return

            gen = HTMLGenerator()
            gen.generate('aid-profile', consultant)
            gen.generate('aid-short',   consultant)
            logger.info(f"  HTML DE regeneriert: {aid}")

            # EN-Version regenerieren falls vorhanden
            en_consultant = Consultant.objects.filter(
                aid_base=aid, language='en'
            ).first()
            if en_consultant:
                gen.generate('aid-profile', en_consultant)
                gen.generate('aid-short',   en_consultant)
                logger.info(f"  HTML EN regeneriert: {en_consultant.aid}")

        except Exception as e:
            logger.warning(f"HTML Regenerierung fehlgeschlagen fuer {aid}: {e}")

    def _update_training_term(self, term: str, category: str) -> bool:
        """Aktualisiert oder erstellt einen TrainingTerm."""
        from apps.cv_extractor.models import TrainingTerm

        term_clean = term.strip()[:200]
        if not term_clean:
            return False

        obj, created = TrainingTerm.objects.get_or_create(
            term=term_clean,
            defaults={
                'category':   category,
                'frequency':  1,
                'confidence': 0.5,
                'source':     'self_learning',
            }
        )
        if not created:
            obj.frequency  += 1
            obj.confidence  = min(0.99, obj.confidence + 0.02)
            obj.save(update_fields=['frequency', 'confidence'])

        try:
            from apps.cv_extractor.models import Skill
            Skill.objects.filter(name=term_clean).update(
                frequency=F('frequency') + 1
            )
        except Exception:
            pass

        return created

    def _update_frequency(self, model_name: str, name: str):
        """Erhoeht Frequenz fuer Industry oder FocusArea."""
        try:
            if model_name == 'Industry':
                from apps.cv_extractor.models import Industry
                Industry.objects.filter(name=name[:200]).update(
                    frequency=F('frequency') + 1
                )
            elif model_name == 'FocusArea':
                from apps.cv_extractor.models import FocusArea
                FocusArea.objects.filter(name=name[:200]).update(
                    frequency=F('frequency') + 1
                )
        except Exception as e:
            logger.warning(f"_update_frequency {model_name}: {e}")

    def _update_prompt_examples(self) -> int:
        """Aktualisiert PromptTemplate Beispiele fuer Skill-Kategorien."""
        from apps.cv_extractor.models import TrainingTerm, PromptTemplate

        updated = 0
        candidates = TrainingTerm.objects.filter(
            frequency__gte=MIN_FREQ_FOR_PROMPT,
            confidence__gte=MIN_CONF_FOR_PROMPT,
            in_prompt=False,
        ).order_by('-frequency')

        by_category: Dict[str, list] = {}
        for term in candidates:
            cat_key = self._display_to_key(term.category)
            if cat_key:
                by_category.setdefault(cat_key, []).append(term)

        for cat_key, terms in by_category.items():
            stage = f"extract_skill_{cat_key}"
            pt    = PromptTemplate.objects.filter(stage=stage, is_active=True).first()
            if not pt or pt.updated_by == 'manual':
                continue

            current_examples = self._extract_examples_from_prompt(pt.prompt_text, cat_key)
            new_terms = [
                t for t in terms if t.term not in current_examples
            ][:MAX_EXAMPLES_PER_CAT - len(current_examples)]

            if not new_terms:
                continue

            all_examples = current_examples + [t.term for t in new_terms]
            new_prompt   = self._update_examples_in_prompt(
                pt.prompt_text, cat_key, all_examples
            )

            if new_prompt != pt.prompt_text:
                new_version         = self._increment_version(pt.version)
                pt.prompt_text      = new_prompt
                pt.version          = new_version
                pt.updated_by       = 'self_learning'
                pt.trained_on_count = pt.trained_on_count + len(new_terms)
                pt.save(update_fields=[
                    'prompt_text', 'version', 'updated_by',
                    'trained_on_count', 'updated_at'
                ])
                TrainingTerm.objects.filter(
                    id__in=[t.id for t in new_terms]
                ).update(in_prompt=True)
                updated += 1
                logger.info(f"Prompt {stage} v{new_version}: +{len(new_terms)} Beispiele")

        return updated

    def _display_to_key(self, display_name: str) -> str:
        reverse = {v: k for k, v in CATEGORY_DISPLAY.items()}
        return reverse.get(display_name, '')

    def _extract_examples_from_prompt(self, prompt_text: str, cat_key: str) -> list:
        pattern = rf'"{cat_key}":\s*\[([^\]]+)\]'
        match   = re.search(pattern, prompt_text)
        if not match:
            return []
        return re.findall(r'"([^"]+)"', match.group(1))

    def _update_examples_in_prompt(self, prompt_text: str,
                                    cat_key: str, examples: list) -> str:
        examples_str = ', '.join(f'"{e}"' for e in examples[:MAX_EXAMPLES_PER_CAT])
        new_line     = f'{{"{cat_key}": [{examples_str}]}}'
        pattern      = rf'{{"{cat_key}":\s*\[[^\]]*\]}}'
        return re.sub(pattern, new_line, prompt_text)

    @staticmethod
    def _increment_version(version: str) -> str:
        try:
            parts = version.split('.')
            if len(parts) >= 2:
                parts[-1] = str(int(parts[-1]) + 1)
                return '.'.join(parts)
        except Exception:
            pass
        return version + '.1'


self_learning_pipeline = SelfLearningPipeline()
