"""
main_labeler.py
===============
Labeler fuer main_pipeline Gruppen (dict-basiert).

Stufe 1: LLM klassifiziert alle Gruppen     → main_block_label
Stufe 2: LLM kategorisiert SKILLS-Bloecke   → main_extract_skill_label
Stufe 3: LLM gruppiert PROJECT-Bloecke      → main_extract_project_label

Input:  gruppen = [{'blocks': [1,2,3], 'label': '...'}]
        blocks  = [{'index': 1, 'lines': [...], 'sz': 9.1, 'bold': True, ...}]
Output: labeled = [{'index': 1, 'label': 'PROJECT', 'skill_cat': None,
                    'text': '...', 'blocks': [1,2,3], 'project_nr': 1}]
"""
import json
import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

MAIN_LABELS = [
    'HEADER', 'PERSONAL', 'FACHBEREICHE', 'ZERTIFIKATE', 'SCHULUNGEN',
    'BRANCHEN', 'SKILLS', 'FOCUS_EXP', 'EXPERIENCE', 'PROJECT', 'OTHER',
]

# ── Regelbasierte Erkennung anhand erstem Wort der Gruppe ──────────────────
# Basis + Gulp-v1.3 Section-Keywords (section_label_keywords.py)
from .section_label_keywords import (  # noqa: E402
    FIRST_WORD_TO_LABEL as _GULP_FIRST_WORD_TO_LABEL,
    label_from_heading,
    merged_first_word_map,
)

_BASE_FIRST_WORD_TO_LABEL = {
    # → SKILLS (Hauptlabel)
    'programmiersprachen':   'SKILLS',
    'programmiersprache':    'SKILLS',
    'betriebssysteme':       'SKILLS',
    'betriebssystem':        'SKILLS',
    'datenbanken':           'SKILLS',
    'datenbank':             'SKILLS',
    'hardware':              'SKILLS',
    'datenkommunikation':    'SKILLS',
    'netzwerk':              'SKILLS',
    'netzwerkprotokolle':    'SKILLS',
    'webserver':             'SKILLS',
    'middleware':            'SKILLS',
    'methoden':              'SKILLS',
    'tools':                 'SKILLS',
    'tool':                  'SKILLS',
    'entwicklungstools':     'SKILLS',
    'softwaretechnologien':  'SKILLS',
    'modellierungstools':    'SKILLS',
    'spezialkenntnisse':     'SKILLS',
    'application':           'SKILLS',
    'technologien':          'SKILLS',
    'frameworks':            'SKILLS',
    'framework':             'SKILLS',
    'cloud':                 'SKILLS',
    'virtualisierung':       'SKILLS',
    'sicherheit':            'SKILLS',
    'security':              'SKILLS',
    'monitoring':            'SKILLS',
    'versionsverwaltung':    'SKILLS',
    'testing':               'SKILLS',
    'datenformate':          'SKILLS',
    'datenmanagement':       'SKILLS',
    # → PERSONAL
    'persönliche':           'PERSONAL',
    'personal':              'PERSONAL',
    'name':                  'PERSONAL',
    'geburtsjahr':           'PERSONAL',
    # → FACHBEREICHE
    'fachbereiche':          'FACHBEREICHE',
    'fachbereich':           'FACHBEREICHE',
    'schwerpunkt':           'FACHBEREICHE',
    'schwerpunkte':          'FACHBEREICHE',
    'fachlicher':            'FACHBEREICHE',
    # → BRANCHEN
    'branchen':              'BRANCHEN',
    'branche':               'BRANCHEN',
    # → ZERTIFIKATE
    'zertifizierungen':      'ZERTIFIKATE',
    'zertifizierung':        'ZERTIFIKATE',
    'zertifikate':           'ZERTIFIKATE',
    'zertifikat':            'ZERTIFIKATE',
    'qualifikationen':       'ZERTIFIKATE',
    # → SCHULUNGEN
    'ausbildung':            'SCHULUNGEN',
    'schulungen':            'SCHULUNGEN',
    'schulung':              'SCHULUNGEN',
    'weiterbildung':         'SCHULUNGEN',
    'training':              'SCHULUNGEN',
    # → PROJECT (Zeitraum-Marker)
    'zeitraum':              'PROJECT',
    'period':                'PROJECT',
    # → FOCUS_EXP
    'produkte':              'FOCUS_EXP',
    'erfahrungen':           'FOCUS_EXP',
}

FIRST_WORD_TO_LABEL = merged_first_word_map(_BASE_FIRST_WORD_TO_LABEL)

# Skill-Kategorie direkt aus erstem Wort der Gruppe
FIRST_WORD_TO_SKILL_CAT = {
    'programmiersprachen':   'programming_languages',
    'programmiersprache':    'programming_languages',
    'betriebssysteme':       'operating_system',
    'betriebssystem':        'operating_system',
    'datenbanken':           'database',
    'datenbank':             'database',
    'hardware':              'hardware',
    'datenkommunikation':    'datenkommunikation',  # Anzeige: Datenkommunikation
    'netzwerk':              'network_protocol',
    'netzwerkprotokolle':    'network_protocol',
    'webserver':             'it_infrastructure',
    'middleware':            'it_infrastructure',
    'methoden':              'methodology',
    'tools':                 'special_skill',
    'tool':                  'special_skill',
    'entwicklungstools':     'development_environment',
    'softwaretechnologien':  'framework',
    'modellierungstools':    'documentation_tool',
    'spezialkenntnisse':     'special_concept',
    'application':           'business_software',
    'produkte':              'special_skill',
    'erfahrungen':           'special_skill',
    'technologien':          'special_skill',
    'frameworks':            'framework',
    'framework':             'framework',
    'cloud':                 'cloud_platform',
    'virtualisierung':       'virtualization',
    'sicherheit':            'security_tool',
    'security':              'security_tool',
    'monitoring':            'monitoring_tool',
    'versionsverwaltung':    'version_control',
    'testing':               'testing_tool',
    'datenformate':          'data_format',
    'datenmanagement':       'data_management',
}

SKILL_CATEGORIES = [
    'architecture_pattern', 'business_software', 'ci_cd_tool', 'cloud_platform',
    'communication_tool', 'database', 'data_format', 'data_management',
    'datenkommunikation',
    'development_environment', 'devops_tool', 'documentation_tool', 'framework',
    'hardware', 'identity_management', 'it_infrastructure', 'methodology',
    'monitoring_tool', 'network_protocol', 'operating_system', 'programming_languages',
    'project_management', 'security_tool', 'soft_skill', 'special_concept',
    'testing_tool', 'version_control', 'virtualization', 'special_skill',
]


def _get_prompt(stage: str) -> Optional[str]:
    try:
        from apps.cv_extractor.models import PromptTemplate
        pt = PromptTemplate.objects.filter(stage=stage, is_active=True).first()
        return pt.prompt_text if pt else None
    except Exception as e:
        logger.warning(f"[MainLabeler] Prompt '{stage}': {e}")
        return None


def _llm(prompt: str):
    try:
        from apps.cv_extractor.services.deepseek_api_label import deepseek_label_api
        return deepseek_label_api.extract(
            prompt, system_prompt="Antworte NUR mit JSON-Array."
        )
    except Exception as e:
        logger.warning(f"[MainLabeler] LLM: {e}")
        return None


class MainLabeler:

    def label(self, gruppen: list, blocks: list) -> list:
        """
        Hauptmethode.
        gruppen: [{'blocks': [1,2,3], 'label': '...'}]
        blocks:  [{'index': 1, 'lines': [...], 'sz': 9.1, 'bold': True, ...}]
        Gibt labeled zurueck.
        """
        block_by_nr = {b['index']: b for b in blocks}

        normalized = []
        for i, g in enumerate(gruppen, 1):
            nrs   = g.get('blocks', [])
            lines = []
            for nr in nrs:
                b = block_by_nr.get(nr)
                if b:
                    lines.extend(b.get('lines', []))
            text       = ' '.join(l.strip() for l in lines if l.strip())
            first_line = lines[0].strip() if lines else ''
            first_b    = block_by_nr.get(nrs[0]) if nrs else {}
            normalized.append({
                'index':      i,
                'blocks':     nrs,
                'text':       text,
                'first_line': first_line,
                'sz':         first_b.get('sz', 0),
                'bold':       first_b.get('bold', False),
                'page':       first_b.get('page', 1),
                'font':       first_b.get('font', ''),
            })

        logger.info(f"[MainLabeler] {len(normalized)} Gruppen")

        label_map   = self._stage1_classify(normalized)
        skill_map   = self._stage2_skills(normalized, label_map, block_by_nr)
        project_map = self._stage3_projects(normalized, label_map)

        result = []
        for g in normalized:
            idx   = g['index']
            label = label_map.get(idx, 'OTHER')
            scat  = skill_map.get(idx) if label == 'SKILLS' else None
            result.append({
                'index':      idx,
                'label':      label,
                'skill_cat':  scat,
                'text':       g['text'],
                'first_line': g['first_line'],
                'blocks':     g['blocks'],
                'project_nr': project_map.get(idx),
                'page':       g['page'],
            })

        n_proj  = len(set(x['project_nr'] for x in result if x['project_nr']))
        n_skill = len([x for x in result if x['label'] == 'SKILLS'])
        logger.info(f"[MainLabeler] {n_proj} Projekte, {n_skill} Skill-Bloecke")
        return result

    def _stage1_classify(self, normalized: list) -> Dict[int, str]:
        logger.info("  Stufe 1: Hauptlabels...")

        # ── Schritt 1a: Regelbasiert (kein LLM) ──────────────────────────
        label_map   = {}
        llm_needed  = []

        for g in normalized:
            first = g['first_line'].strip().lower()
            # Erstes Wort extrahieren
            first_word = re.split(r'[\s:,|]', first)[0] if first else ''

            # Zeitraum-Marker → direkt PROJECT
            if re.match(r'\d{1,2}/\d{4}', first) or first_word == 'zeitraum':
                label_map[g['index']] = 'PROJECT'
                continue

            # Phrase / Gulp-Heading (Fachlicher Schwerpunkt, Top-Skills, …)
            phrase_lab = label_from_heading(g['first_line'])
            if phrase_lab and phrase_lab in MAIN_LABELS:
                label_map[g['index']] = phrase_lab
                continue

            # Bekanntes erstes Wort → direkt labeln
            if first_word in FIRST_WORD_TO_LABEL:
                label_map[g['index']] = FIRST_WORD_TO_LABEL[first_word]
                continue

            # Unbekannt → LLM
            llm_needed.append(g)

        regel_count = len(label_map)
        logger.info(f"  Regelbasiert: {regel_count} Gruppen direkt gelabelt")

        # ── Schritt 1b: LLM nur für unbekannte Gruppen ───────────────────
        if llm_needed:
            pt = _get_prompt('main_block_label')
            if pt:
                rows = []
                for g in llm_needed:
                    rows.append(
                        f"G{g['index']:02d}|p{g['page']}|sz={round(g['sz'])}|"
                        f"{'B' if g['bold'] else '.'}|"
                        f"{g['text'][:150].replace(chr(10), ' ')}"
                    )
                r = _llm(pt.format(blocks="\n".join(rows)))
                if r and r.success and r.data:
                    data = r.data if isinstance(r.data, list) else json.loads(str(r.data))
                    llm_needed_idx = {g['index'] for g in llm_needed}
                    for item in data:
                        if isinstance(item, dict) and item.get('label') in MAIN_LABELS:
                            grp = item['group']
                            if grp in llm_needed_idx:  # nur LLM-Gruppen überschreiben
                                label_map[grp] = item['label']
                    logger.info(f"  LLM: {len(llm_needed)} Gruppen nachklassifiziert")
            # Fallback
            for g in llm_needed:
                if g['index'] not in label_map:
                    label_map[g['index']] = 'PROJECT' if g['page'] > 1 else 'OTHER'

        from collections import Counter
        logger.info(f"  Labels: {dict(Counter(label_map.values()))}")
        return label_map

    def _stage2_skills(self, normalized: list, label_map: Dict,
                       block_by_nr: Dict) -> Dict[int, str]:
        logger.info("  Stufe 2: Skills kategorisieren...")
        skill_groups = [g for g in normalized if label_map.get(g['index']) == 'SKILLS']
        if not skill_groups:
            return {}

        # ── Schritt 2a: Regelbasiert aus erstem Wort ─────────────────────
        skill_map  = {}
        llm_needed = []

        for g in skill_groups:
            first      = g['first_line'].strip().lower()
            first_word = re.split(r'[\s:,|]', first)[0] if first else ''

            if first_word in FIRST_WORD_TO_SKILL_CAT:
                skill_map[g['index']] = FIRST_WORD_TO_SKILL_CAT[first_word]
            else:
                llm_needed.append(g)

        regel_count = len(skill_map)
        logger.info(f"  Regelbasiert: {regel_count} Skill-Kategorien direkt erkannt")

        # ── Schritt 2b: LLM nur für unbekannte Skill-Blöcke ─────────────
        if llm_needed:
            pt = _get_prompt('main_extract_skill_label')
            if pt:
                rows = "\n".join(
                    f"G{g['index']:02d}: {g['text'][:150]}" for g in llm_needed
                )
                r = _llm(pt.format(blocks=rows))
                if r and r.success and r.data:
                    data = r.data if isinstance(r.data, list) else json.loads(str(r.data))
                    for item in data:
                        if isinstance(item, dict) and item.get('category') in SKILL_CATEGORIES:
                            skill_map[item['group']] = item['category']
                    logger.info(f"  LLM: {len(llm_needed)} Skill-Blöcke nachkategorisiert")

            for g in llm_needed:
                if g['index'] not in skill_map:
                    skill_map[g['index']] = 'special_skill'

        logger.info(f"  {len(skill_map)} Skill-Bloecke kategorisiert")
        return skill_map

    def _stage3_projects(self, normalized: list, label_map: Dict) -> Dict[int, Optional[int]]:
        logger.info("  Stufe 3: Projekte zusammenfuehren...")
        proj_groups = [
            g for g in normalized
            if label_map.get(g['index']) in ('PROJECT', 'EXPERIENCE')
        ]
        if not proj_groups:
            return {}

        pt = _get_prompt('main_extract_project_label')
        if not pt:
            return self._fallback_projects(proj_groups)

        rows = []
        for g in proj_groups:
            tl = g['text'].lower()
            d  = 'D' if re.search(r'\d{1,2}/\d{4}|\d{4}', g['text']) else '.'
            k  = 'K' if any(x in tl for x in ['gmbh','ag','kg','ltd','inc','se']) else '.'
            rows.append(f"G{g['index']:02d}|p{g['page']}|{d}{k}|{g['text'][:120]}")

        r = _llm(pt.format(blocks="\n".join(rows)))

        project_map = {}
        if r and r.success and r.data:
            data = r.data if isinstance(r.data, list) else json.loads(str(r.data))
            for item in data:
                if isinstance(item, dict):
                    project_map[item['group']] = item.get('project_nr')
            logger.info(f"  {len(set(v for v in project_map.values() if v))} Projekte")
        else:
            logger.warning("  Stufe 3 fehlgeschlagen")
            project_map = self._fallback_projects(proj_groups)

        return project_map

    def _fallback_projects(self, proj_groups: list) -> Dict[int, Optional[int]]:
        pnr    = 0
        result = {}
        for g in proj_groups:
            if re.search(r'\d{1,2}/\d{4}', g['text']):
                pnr += 1
                result[g['index']] = pnr
            else:
                result[g['index']] = pnr or None
        return result


main_labeler = MainLabeler()
