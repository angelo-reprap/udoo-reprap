"""
master_translator_to_de.py
Prompt DB-Stage: master_translate_to_de
Uebersetzt alle Projekttexte in profil_pre_json.json auf Deutsch.
Das LLM erkennt die Sprache selbst.
Optimierung: alle Activities eines Projekts in EINEM LLM-Aufruf (JSON Array).
Singleton: master_translator_to_de
"""
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


def _translate_to_de(text: str, context: str = '') -> str:
    """Einzelnen Text ins Deutsche uebersetzen."""
    if not text or not text.strip() or len(text.strip()) < 5:
        return text
    try:
        from apps.cv_extractor.services.deepseek_api import deepseek_api
        prompt = (
            f"Erkenne die Sprache und uebersetze ins Deutsche. "
            f"Bereits Deutsches unveraendert lassen. "
            f"Fachbegriffe, Technologienamen, Firmennamen auf Englisch lassen. "
            f"Kontext: {context}\n\nText:\n{text}"
        )
        res = deepseek_api.extract(
            prompt=prompt,
            system_prompt='Du bist ein Uebersetzer. Antworte NUR mit JSON: {"translation": "..."}'
        )
        if res.success and res.data:
            return res.data.get('translation', text)
        return text
    except Exception as e:
        logger.warning(f"[TranslatorDE] Fehler: {e}")
        return text


def _translate_activities_batch(activities: list, company: str) -> list:
    """Alle Activities eines Projekts in EINEM LLM-Aufruf uebersetzen."""
    if not activities:
        return activities
    try:
        from apps.cv_extractor.services.deepseek_api import deepseek_api
        acts_json = json.dumps(activities, ensure_ascii=False)
        prompt = (
            f"Erkenne die Sprache jedes Eintrags und uebersetze ins Deutsche. "
            f"Bereits Deutsche unveraendert lassen. "
            f"Fachbegriffe, Technologienamen, Firmennamen auf Englisch lassen. "
            f"Kontext: Taetigkeiten bei {company}\n\n"
            f"Eintraege als JSON Array:\n{acts_json}"
        )
        res = deepseek_api.extract(
            prompt=prompt,
            system_prompt='Du bist ein Uebersetzer. Antworte NUR mit JSON: {"translations": ["...", "...", ...]}'
        )
        if res.success and res.data:
            translated = res.data.get('translations', [])
            if isinstance(translated, list) and len(translated) == len(activities):
                return translated
        return activities
    except Exception as e:
        logger.warning(f"[TranslatorDE] Batch Fehler bei {company}: {e}")
        return activities


class MasterTranslatorToDe:

    def translate_pre_json(self, pre_json: dict, max_workers: int = 10) -> dict:
        import copy, datetime
        result = copy.deepcopy(pre_json)
        ed = result['extracted_data']

        # ── Phase 1: Einzelfelder parallel ───────────────────────────────────
        logger.info("[TranslatorDE] Phase 1: Einzelfelder parallel...")

        # Einfache Ersetzungen: Nationalitaet, Verfuegbarkeit, Sprachen
        EN_DE = {
            'German': 'Deutsch', 'Austrian': 'Oesterreichisch',
            'Swiss': 'Schweizer', 'Hungarian': 'Ungarisch',
            '100% available': '100% verfügbar',
            'immediately available': 'sofort verfügbar',
            'upon request': 'nach Absprache',
            'available soon': 'bald verfügbar',
            'not available': 'nicht verfügbar',
            'fluent': 'verhandlungssicher',
            'native': 'Muttersprache',
            'basic': 'Grundkenntnisse',
            'solid knowledge': 'solide Kenntnisse',
            'good knowledge': 'gute Kenntnisse',
        }
        pers = ed.get('personal', {})
        for field in ('nationality', 'availability'):
            val = pers.get(field, '')
            if val:
                for en, de in EN_DE.items():
                    val = val.replace(en, de)
                pers[field] = val
        langs = pers.get('languages', [])
        if langs:
            # Sprachen koennen Dicts {'name':..., 'level':...} oder Strings sein
            new_langs = []
            for l in langs:
                if isinstance(l, dict):
                    new_langs.append(l)  # Dicts unveraendert lassen
                else:
                    for en, de in EN_DE.items():
                        l = l.replace(en, de)
                    new_langs.append(l)
            pers['languages'] = new_langs

        def translate_field(args):
            key, value, context = args
            if isinstance(value, list):
                return key, [_translate_to_de(str(i), context) for i in value]
            elif isinstance(value, str):
                return key, _translate_to_de(value, context)
            return key, value

        field_tasks = []
        meta = result.get('metadata', {})
        if meta.get('headline'):
            field_tasks.append(('headline', meta['headline'], 'Berufsbezeichnung'))
        if ed.get('focus_experience'):
            field_tasks.append(('focus_experience', ed['focus_experience'], 'Schwerpunkt Erfahrung'))
        if ed.get('focus_areas'):
            field_tasks.append(('focus_areas', ed['focus_areas'], 'Fachbereich'))
        if ed.get('industries'):
            field_tasks.append(('industries', ed['industries'], 'Branche'))

        with ThreadPoolExecutor(max_workers=min(len(field_tasks)+1, 4)) as executor:
            futures = {executor.submit(translate_field, t): t[0] for t in field_tasks}
            for future in as_completed(futures):
                key, value = future.result()
                if key == 'headline':
                    meta['headline'] = value
                else:
                    ed[key] = value
        logger.info(f"  {len(field_tasks)} Einzelfelder uebersetzt")

        # ── Phase 2: Projekte parallel (1 Aufruf pro Projekt) ────────────────
        exp = ed.get('experience', [])
        if not exp:
            return result

        logger.info(f"[TranslatorDE] Phase 2: {len(exp)} Projekte parallel (1 API-Aufruf/Projekt)...")

        def translate_project(idx_exp):
            idx, e = idx_exp
            e = dict(e)
            company = e.get('company', '')

            # role/title einzeln
            for field in ('role', 'title'):
                val = e.get(field, '')
                if val and val.strip():
                    e[field] = _translate_to_de(val, f'Projektrolle bei {company}')

            # Activities als Batch (1 Aufruf fuer alle)
            acts = e.get('activities', [])
            if acts:
                e['activities'] = _translate_activities_batch(acts, company)

            return idx, e

        proj_results = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(translate_project, (i, e)): i
                       for i, e in enumerate(ed['experience'])}
            done = 0
            for future in as_completed(futures):
                idx, e = future.result()
                proj_results[idx] = e
                done += 1
                if done % 10 == 0:
                    logger.info(f"  {done}/{len(exp)} Projekte fertig...")

        ed['experience'] = [proj_results[i] for i in sorted(proj_results.keys())]
        logger.info(f"[TranslatorDE] Alle {len(exp)} Projekte uebersetzt")
        result['audit']['translated_to_de_at'] = datetime.datetime.now().isoformat()
        return result

    def translate_and_save(self, pre_json_path: str) -> dict:
        import json as _json
        from pathlib import Path
        path = Path(pre_json_path)
        pre_json = _json.loads(path.read_text(encoding='utf-8'))
        logger.info(f"[TranslatorDE] Starte: {path.name}")
        translated = self.translate_pre_json(pre_json)
        path.write_text(_json.dumps(translated, indent=2, ensure_ascii=False), encoding='utf-8')
        logger.info(f"[TranslatorDE] Gespeichert: {path}")
        return translated


master_translator_to_de = MasterTranslatorToDe()
