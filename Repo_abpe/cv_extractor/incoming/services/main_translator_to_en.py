"""
main_translator_to_en.py
Prompt DB-Stage: main_translate_to_en
Uebersetzt alle Projekttexte in profil_pre_json.json auf Englisch.
Optimierung: alle Activities eines Projekts in EINEM LLM-Aufruf.
Singleton: main_translator_to_en
"""
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


def _translate_to_en(text: str, context: str = '') -> str:
    """Einzelnen Text ins Englische uebersetzen."""
    if not text or not text.strip() or len(text.strip()) < 5:
        return text
    try:
        from apps.cv_extractor.services.deepseek_api import deepseek_api
        prompt = (
            f"Detect the language and translate to English. "
            f"If already English, return unchanged. "
            f"Keep technical terms, technology names, company names as-is. "
            f"Context: {context}\n\nText:\n{text}"
        )
        res = deepseek_api.extract(
            prompt=prompt,
            system_prompt='You are a CV translator. Reply ONLY with JSON: {"translation": "..."}'
        )
        if res.success and res.data:
            return res.data.get('translation', text)
        return text
    except Exception as e:
        logger.warning(f"[TranslatorEN] Fehler: {e}")
        return text


def _translate_activities_batch(activities: list, company: str) -> list:
    """Alle Activities eines Projekts in EINEM LLM-Aufruf uebersetzen."""
    if not activities:
        return activities
    try:
        from apps.cv_extractor.services.deepseek_api import deepseek_api
        acts_json = json.dumps(activities, ensure_ascii=False)
        prompt = (
            f"Detect the language of each entry and translate to English. "
            f"If already English, return unchanged. "
            f"Keep technical terms, technology names, company names as-is. "
            f"Context: Activities at {company}\n\n"
            f"Entries as JSON array:\n{acts_json}"
        )
        res = deepseek_api.extract(
            prompt=prompt,
            system_prompt='You are a CV translator. Reply ONLY with JSON: {"translations": ["...", "...", ...]}'
        )
        if res.success and res.data:
            translated = res.data.get('translations', [])
            if isinstance(translated, list) and len(translated) == len(activities):
                return translated
        return activities
    except Exception as e:
        logger.warning(f"[TranslatorEN] Batch Fehler bei {company}: {e}")
        return activities


class MainTranslatorToEn:

    def translate_pre_json(self, pre_json: dict, max_workers: int = 10) -> dict:
        import copy, datetime
        result = copy.deepcopy(pre_json)
        ed = result['extracted_data']

        # ── Phase 1: Einzelfelder parallel ───────────────────────────────────
        logger.info("[TranslatorEN] Phase 1: Einzelfelder parallel...")

        # Einfache Ersetzungen: Nationalitaet, Verfuegbarkeit, Sprachen
        DE_EN = {
            'Deutsch': 'German', 'Oesterreichisch': 'Austrian',
            'Schweizer': 'Swiss', 'Ungarisch': 'Hungarian',
            'Tschechisch': 'Czech', 'Polnisch': 'Polish',
            '100% verfuegbar': '100% available',
            '100% verfügbar': '100% available',
            'sofort verfuegbar': 'immediately available',
            'sofort verfügbar': 'immediately available',
            'nach Absprache': 'upon request',
            'bald verfügbar': 'available soon',
            'nicht verfügbar': 'not available',
            'verhandlungssicher': 'fluent',
            'Muttersprache': 'native',
            'Grundkenntnisse': 'basic',
            'solide Kenntnisse': 'solid knowledge',
            'gute Kenntnisse': 'good knowledge',
            # Sprachnamen
            'Englisch': 'English', 'Franzoesisch': 'French',
            'Französisch': 'French', 'Spanisch': 'Spanish',
            'Italienisch': 'Italian', 'Russisch': 'Russian',
            'Chinesisch': 'Chinese', 'Arabisch': 'Arabic',
            'Tuerkisch': 'Turkish', 'Türkisch': 'Turkish',
            'Japanisch': 'Japanese', 'Koreanisch': 'Korean',
            'Niederlaendisch': 'Dutch', 'Niederländisch': 'Dutch',
            'Portugiesisch': 'Portuguese', 'Polnisch': 'Polish',
            'Ungarisch': 'Hungarian',
        }
        pers = ed.get('personal', {})
        import re
        for field in ('nationality', 'availability'):
            val = pers.get(field, '')
            if val:
                # Erst schnelle Dict-Ersetzung
                matched = False
                for de, en in DE_EN.items():
                    new_val = re.sub(r'\b' + re.escape(de) + r'\b', en, val)
                    if new_val != val:
                        val = new_val
                        matched = True
                # Wenn kein Match → LLM
                if not matched:
                    val = _translate_to_en(val, f'Personal field: {field}')
                pers[field] = val
        langs = pers.get('languages', [])
        if langs:
            # Sprachen koennen Dicts {'name':..., 'level':...} oder Strings sein
            new_langs = []
            for l in langs:
                if isinstance(l, dict):
                    name = l.get('name', '')
                    for de, en in DE_EN.items():
                        name = name.replace(de, en)
                    new_langs.append({'name': name, 'level': l.get('level', '')})
                else:
                    for de, en in DE_EN.items():
                        l = l.replace(de, en)
                    new_langs.append(l)
            pers['languages'] = new_langs

        def translate_field(args):
            key, value, context = args
            if isinstance(value, list):
                processed = []
                for i in value:
                    if isinstance(i, dict) and 'name' in i:
                        # Dictionary: übersetze nur den name, behalte Struktur
                        new_i = i.copy()
                        new_i['name'] = _translate_to_en(new_i['name'], context) if new_i['name'] else new_i['name']
                        processed.append(new_i)
                    elif isinstance(i, str) and i.strip().startswith('{'):
                        # String der wie ein Dictionary aussieht: parsen, name extrahieren, übersetzen
                        try:
                            import ast
                            d = ast.literal_eval(i)
                            if isinstance(d, dict) and 'name' in d:
                                new_d = d.copy()
                                new_d['name'] = _translate_to_en(d['name'], context) if d['name'] else d['name']
                                processed.append(new_d)
                            else:
                                processed.append(_translate_to_en(i, context))
                        except:
                            processed.append(_translate_to_en(i, context))
                    else:
                        processed.append(_translate_to_en(str(i), context))
                return key, processed
            elif isinstance(value, str):
                return key, _translate_to_en(value, context)
            return key, value

        field_tasks = []
        meta = result.get('metadata', {})
        if meta.get('headline'):
            field_tasks.append(('headline', meta['headline'], 'Job title'))
        if ed.get('focus_experience'):
            field_tasks.append(('focus_experience', ed['focus_experience'], 'Focus area'))
        if ed.get('focus_areas'):
            field_tasks.append(('focus_areas', ed['focus_areas'], 'Technical area'))
        if ed.get('industries'):
            field_tasks.append(('industries', ed['industries'], 'Industry'))

        if field_tasks:
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

        logger.info(f"[TranslatorEN] Phase 2: {len(exp)} Projekte parallel...")

        def translate_project(idx_exp):
            idx, e = idx_exp
            e = dict(e)
            company = e.get('company', '')

            for field in ('role', 'title'):
                val = e.get(field, '')
                if val and val.strip():
                    e[field] = _translate_to_en(val, f'Project role at {company}')

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
        logger.info(f"[TranslatorEN] Alle {len(exp)} Projekte uebersetzt")
        
        # Stelle sicher dass audit existiert
        if 'audit' not in result:
            result['audit'] = {}
        result['audit']['translated_to_en_at'] = datetime.datetime.now().isoformat()
        return result

    def translate_and_save(self, pre_json_path: str) -> dict:
        import json as _json
        from pathlib import Path
        path = Path(pre_json_path)
        pre_json = _json.loads(path.read_text(encoding='utf-8'))
        logger.info(f"[TranslatorEN] Start: {path.name}")
        translated = self.translate_pre_json(pre_json)
        path.write_text(_json.dumps(translated, indent=2, ensure_ascii=False), encoding='utf-8')
        logger.info(f"[TranslatorEN] Saved: {path}")
        return translated


main_translator_to_en = MainTranslatorToEn()
