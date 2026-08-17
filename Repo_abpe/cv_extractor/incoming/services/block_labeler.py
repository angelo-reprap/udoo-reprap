"""
services/block_labeler.py

3-stufiger Block-Labeler fuer CV-Extraktion:

Stufe 1: LLM klassifiziert alle Gruppen (ein Call, Prompt: extract_block_label)
         Input: erste 3 Zeilen + Formatierung (kompakt, schnell)
         Labels: HEADER, PERSONAL, FACHBEREICHE, ZERTIFIKATE, SCHULUNGEN,
                 BRANCHEN, SKILLS, FOCUS_EXP, EXPERIENCE, PROJECT, OTHER

Stufe 2: LLM sortiert SKILLS in 27 Kategorien (Prompt: extract_skill_label)
         Nur SKILLS-Bloecke, kein FOCUS_EXP

Stufe 3: LLM merged PROJECT-Bloecke (Prompt: extract_project_label)
         Erkennt zusammengehoerige Bloecke (Seitenumbruch, geteilte Projekte)

Regel: Nur SKILLS darf skill_cat haben — alle anderen Labels bekommen None
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

MAIN_LABELS = [
    'HEADER', 'PERSONAL', 'FACHBEREICHE', 'ZERTIFIKATE', 'SCHULUNGEN',
    'BRANCHEN', 'SKILLS', 'FOCUS_EXP', 'EXPERIENCE', 'PROJECT', 'OTHER',
]

SKILL_CATEGORIES = [
    'architecture_pattern', 'business_software', 'ci_cd_tool', 'cloud_platform',
    'communication_tool', 'database', 'data_format', 'data_management',
    'development_environment', 'devops_tool', 'documentation_tool', 'framework',
    'hardware', 'identity_management', 'it_infrastructure', 'methodology',
    'monitoring_tool', 'network_protocol', 'operating_system', 'programming_languages',
    'project_management', 'security_tool', 'soft_skill', 'special_concept',
    'testing_tool', 'version_control', 'virtualization', 'special_skill',
]


@dataclass
class LabeledGroup:
    index:       int
    label:       str
    skill_cat:   Optional[str] = None
    text:        str = ''
    first_line:  str = ''
    spans:       List = field(default_factory=list)
    project_nr:  Optional[int] = None


class BlockLabeler:

    def __init__(self):
        from .deepseek_api_label import deepseek_label_api as deepseek_api
        self.api = deepseek_api
        logger.info("BlockLabeler initialisiert")

    def label(self, groups) -> List[LabeledGroup]:
        """Hauptmethode: alle 3 Stufen ausfuehren."""
        logger.info(f"BlockLabeler: {len(groups)} Gruppen")

        label_map   = self._stage1_classify(groups)
        skill_map   = self._stage2_skills(groups, label_map)
        project_map = self._stage3_projects(groups, label_map)

        result = []
        for g in groups:
            all_spans = [s for b in g.blocks for s in b.spans]
            result.append(LabeledGroup(
                index      = g.index,
                label      = label_map.get(g.index, 'OTHER'),
                skill_cat  = skill_map.get(g.index),
                text       = g.text,
                first_line = g.first_line,
                spans      = all_spans,
                project_nr = project_map.get(g.index),
            ))

        # Nur SKILLS darf skill_cat haben
        for lg in result:
            if lg.label != 'SKILLS':
                lg.skill_cat = None

        n_proj  = len(set(x.project_nr for x in result if x.project_nr))
        n_skill = len([x for x in result if x.label in ('SKILLS', 'FOCUS_EXP')])
        logger.info(f"BlockLabeler: {n_proj} Projekte, {n_skill} Skill-Bloecke")
        return result

    # ── Stufe 1 ───────────────────────────────────────────────────────────────

    def _stage1_classify(self, groups) -> Dict[int, str]:
        logger.info("Stufe 1: Hauptgruppen klassifizieren...")
        from apps.cv_extractor.models import PromptTemplate

        pt = PromptTemplate.objects.filter(
            stage='extract_block_label', is_active=True
        ).first()
        if not pt:
            logger.warning("Kein extract_block_label Prompt – Fallback")
            return {g.index: self._fallback_label(g, {}) for g in groups}

        # Kompakte Darstellung: erste 3 Zeilen + Formatierung
        # OCR-Modus: CAPS-Zeilen als [ÜBERSCHRIFT] markieren + size+2
        import re as _re
        def _is_caps(text):
            t = text.strip()
            if len(t) < 3: return False
            letters = [c for c in t if c.isalpha()]
            if not letters: return False
            return sum(1 for c in letters if c.isupper()) / len(letters) >= 0.7

        def _is_ocr_group(g):
            for b in g.blocks:
                for s in b.spans:
                    if getattr(s, 'font', '') == 'OCR':
                        return True
            return False

        rows = []
        for g in groups:
            s0   = g.blocks[0].spans[0] if g.blocks and g.blocks[0].spans else None
            pg   = s0.page if s0 else 0
            bold = 'B' if (s0 and s0.bold) else '.'
            sz   = round(s0.size) if s0 else 0
            lines = [l.strip() for l in g.text.split('  ') if l.strip()][:3]
            first3 = ' | '.join(lines)

            # OCR-Marker: CAPS-Zeile → [ÜBERSCHRIFT] + size+2
            if _is_ocr_group(g) and _is_caps(g.first_line):
                bold  = 'B'
                sz    = sz + 2
                first3 = f"[ÜBERSCHRIFT]{first3}"

            # block_type Marker aus OCR-Detector (stats nicht verfügbar hier
            # → direkt aus Spans lesen ob OCR + block_type)
            # Block-Typ Marker zusätzlich zum ÜBERSCHRIFT-Marker
            BLOCK_TYPE_MARKERS = {
                'BULLET_LIST':  '[BULLET_LIST]',
                'PROJECT':      '[PROJEKT]',
                'EDUCATION':    '[AUSBILDUNG]',
                'SKILLS_LABEL': '[SKILLS]',
                'CONTACT':      '[KONTAKT]',
                'PROSE':        '[FLIESSTEXT]',
                'HEADING':      '[ÜBERSCHRIFT]',
                'MIXED':        '',
            }
            # block_type aus erstem Block lesen (OCRBlockDetector setzt es)
            if _is_ocr_group(g):
                bt = getattr(g.blocks[0], 'block_type', '') if g.blocks else ''
                marker = BLOCK_TYPE_MARKERS.get(bt, '')
                # ÜBERSCHRIFT-Marker nur wenn nicht schon gesetzt
                if marker and not first3.startswith('['):
                    first3 = f"{marker}{first3}"

            rows.append(f"G{g.index:02d}|p{pg}|sz={sz}|{bold}|{first3[:120]}")

        prompt = pt.prompt_text.format(blocks="\n".join(rows))

        r = self.api.extract(
            prompt,
            system_prompt="Antworte NUR mit JSON-Array."
        )

        label_map = {}
        if r.success and r.data:
            data = r.data if isinstance(r.data, list) else json.loads(r.data)
            label_map = {
                item['group']: item['label']
                for item in data
                if item.get('label') in MAIN_LABELS
            }
            from collections import Counter
            dist = Counter(label_map.values())
            for k, v in sorted(dist.items()):
                logger.info(f"  {k}: {v}")
        else:
            logger.warning("  Stufe 1 LLM fehlgeschlagen")

        # Fallback fuer nicht klassifizierte
        for g in groups:
            if g.index not in label_map:
                label_map[g.index] = self._fallback_label(g, label_map)

        return label_map

    def _fallback_label(self, g, existing: Dict) -> str:
        s0 = g.blocks[0].spans[0] if g.blocks and g.blocks[0].spans else None
        if s0 and s0.page == 1:
            return 'HEADER'
        prev = existing.get(g.index - 1, '')
        if prev in ('SKILLS', 'FOCUS_EXP'):
            return 'FOCUS_EXP'
        if prev == 'PROJECT':
            return 'PROJECT'
        return 'OTHER'

    # ── Stufe 2 ───────────────────────────────────────────────────────────────

    def _stage2_skills(self, groups, label_map: Dict) -> Dict[int, str]:
        logger.info("Stufe 2: Skills in 27 Kategorien sortieren...")
        from apps.cv_extractor.models import PromptTemplate

        skill_groups = [g for g in groups
                        if label_map.get(g.index) == 'SKILLS']
        if not skill_groups:
            return {}

        pt = PromptTemplate.objects.filter(
            stage='extract_skill_label', is_active=True
        ).first()
        if not pt:
            logger.warning("Kein extract_skill_label Prompt")
            return {}

        blocks_text = "\n".join(
            f"G{g.index:02d}: {g.text[:150]}"
            for g in skill_groups
        )
        prompt = pt.prompt_text.format(blocks=blocks_text)

        r = self.api.extract(prompt, system_prompt="Antworte NUR mit JSON-Array.")

        skill_map = {}
        if r.success and r.data:
            data = r.data if isinstance(r.data, list) else json.loads(r.data)
            skill_map = {
                item['group']: item['category']
                for item in data
                if item.get('category') in SKILL_CATEGORIES
            }
            logger.info(f"  {len(skill_map)} Skill-Bloecke kategorisiert")
        else:
            logger.warning("  Stufe 2 LLM fehlgeschlagen – Fallback")

        # Fallback: Ueberschrift auswerten
        heading_map = {
            'programmiersprachen': 'programming_languages',
            'betriebssysteme':     'operating_system',
            'hardware':            'hardware',
            'datenkommunikation':  'network_protocol',
            'virtualisierung':     'virtualization',
            'datenbanken':         'database',
            'netzwerk':            'network_protocol',
            'sicherheit':          'security_tool',
        }
        for g in skill_groups:
            if g.index not in skill_map:
                h = g.first_line.lower()
                skill_map[g.index] = next(
                    (v for k, v in heading_map.items() if k in h),
                    'it_infrastructure'
                )

        # Ueberschrift-Regel: Einzeiler bold+sz>=13 uebertraegt skill_cat auf naechsten Block
        prev_cat = None
        prev_is_heading = False
        for g in skill_groups:
            spans = [s for b in g.blocks for s in b.spans]
            is_heading = len(spans) == 1 and spans[0].bold and spans[0].size >= 13.0
            if prev_is_heading and g.index in skill_map:
                skill_map[g.index] = prev_cat
                logger.info(f"  G{g.index:02d} erbt skill_cat={prev_cat} von Ueberschrift")
            prev_cat = skill_map.get(g.index)
            prev_is_heading = is_heading

        return skill_map

    # ── Stufe 3 ───────────────────────────────────────────────────────────────

    def _stage3_projects(self, groups, label_map: Dict) -> Dict[int, Optional[int]]:
        logger.info("Stufe 3: Projekt-Bloecke zusammenfuehren...")
        from apps.cv_extractor.models import PromptTemplate

        proj_groups = [g for g in groups
                       if label_map.get(g.index) in ('PROJECT', 'EXPERIENCE')]
        if not proj_groups:
            return {}

        pt = PromptTemplate.objects.filter(
            stage='extract_project_label', is_active=True
        ).first()
        if not pt:
            logger.warning("Kein extract_project_label Prompt – Fallback")
            return self._fallback_projects(proj_groups, label_map)

        rows = []
        for g in proj_groups:
            s0  = g.blocks[0].spans[0] if g.blocks and g.blocks[0].spans else None
            pg  = s0.page if s0 else 0
            tl  = g.text.lower()
            d   = 'D' if re.search(r'\d{1,2}/\d{4}|\d{4}', g.text) else '.'
            k   = 'K' if any(x in tl for x in ['kunde','firma','institut','branche']) else '.'
            p   = 'P' if any(x in tl for x in ['projekttät','tätigkei','tätigkeit']) else '.'
            t   = 'T' if any(x in tl for x in ['technolog','umfeld','systemumg','methoden','tools:','stack:','frameworks','technician']) else '.'
            rows.append(f"G{g.index:02d}|p{pg}|{d}{k}{p}{t}|{g.text[:120]}")

        prompt = pt.prompt_text.format(blocks="\n".join(rows))
        r = self.api.extract(prompt, system_prompt="Antworte NUR mit JSON-Array.")

        project_map = {}
        if r.success and r.data:
            data = r.data if isinstance(r.data, list) else json.loads(r.data)
            project_map = {
                item['group']: item.get('project_nr')
                for item in data
            }
            n = len(set(v for v in project_map.values() if v))
            logger.info(f"  {n} Projekte zusammengefuehrt")
        else:
            logger.warning("  Stufe 3 LLM fehlgeschlagen – Fallback")
            project_map = self._fallback_projects(proj_groups, label_map)

        return project_map

    def _fallback_projects(self, proj_groups, label_map) -> Dict[int, Optional[int]]:
        pnr = 0
        result = {}
        for g in proj_groups:
            if label_map.get(g.index) == 'EXPERIENCE':
                result[g.index] = None
            elif re.search(r'\d{1,2}/\d{4}', g.text):
                pnr += 1
                result[g.index] = pnr
            else:
                result[g.index] = pnr or None
        return result

    # ── Hilfsmethoden ─────────────────────────────────────────────────────────

    def get_skills_by_category(self, labeled: List[LabeledGroup]) -> Dict[str, List[str]]:
        skills: Dict[str, List[str]] = {}
        for lg in labeled:
            if lg.label not in ('SKILLS', 'FOCUS_EXP') or not lg.skill_cat:
                continue
            cat = lg.skill_cat
            for i, span in enumerate(lg.spans):
                if i == 0 and span.bold and span.size >= 13.0:
                    continue
                for part in span.text.split(','):
                    part = part.strip()
                    if part and len(part) > 1:
                        skills.setdefault(cat, []).append(part)
        return {k: list(dict.fromkeys(v)) for k, v in skills.items()}

    def get_projects(self, labeled: List[LabeledGroup]) -> List[Dict]:
        proj_dict: Dict[int, List[LabeledGroup]] = {}
        for lg in labeled:
            if lg.project_nr is None:
                continue
            proj_dict.setdefault(lg.project_nr, []).append(lg)
        result = []
        for pnr in sorted(proj_dict.keys()):
            grps = proj_dict[pnr]
            all_spans = [s for lg in grps for s in lg.spans]
            result.append({
                'project_nr': pnr,
                'groups':     [lg.index for lg in grps],
                'text':       ' '.join(lg.text for lg in grps),
                'spans':      all_spans,
            })
        return result

    def get_labeled_text(self, labeled: List[LabeledGroup]) -> str:
        lines = ["="*70, "GELABELTE BLOECKE", "="*70, ""]
        lines.append("LABEL-UEBERSICHT:")
        for lg in labeled:
            extra = f" skill.{lg.skill_cat}" if lg.skill_cat else ""
            extra += f" PROJECT_{lg.project_nr:02d}" if lg.project_nr else ""
            lines.append(f"  G{lg.index:02d} [{lg.label:15s}]{extra} | {lg.first_line[:50]}")
        lines.append("")
        for lg in labeled:
            plbl = lg.label
            if lg.project_nr:
                plbl = f"PROJECT_{lg.project_nr:02d}"
            elif lg.skill_cat:
                plbl = f"SKILL.{lg.skill_cat}"
            lines.append("="*60)
            lines.append(f"GRUPPE #{lg.index} [{plbl}]")
            lines.append(f"  Text: {lg.text[:120]}")
            for span in lg.spans:
                lines.append(
                    f"    p{span.page} y={span.y:4} x={span.x:4} "
                    f"sz={span.size:4.1f} "
                    f"{'B' if span.bold else '.'}{'I' if span.italic else '.'} | "
                    f"{span.text[:65]}"
                )
            lines.append("")
        return "\n".join(lines)


block_labeler = BlockLabeler()
