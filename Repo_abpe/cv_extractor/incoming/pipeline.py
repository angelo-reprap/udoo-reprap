"""
pipeline.py - CV Extraktions-Pipeline (Block-Labeler Version)

Schritt 0:  PDF -> Spans -> BlockDetector -> Gruppen
Schritt 1:  BlockLabeler -> Labels
Schritt 2-6: PERSONAL, FACHBEREICHE, ZERTIFIKATE, SCHULUNGEN, BRANCHEN, HEADER -> parallel
Schritt 7:  SKILLS + FOCUS_EXP -> direkt aus Bloecken (kein LLM)
Schritt 8:  PROJEKTE -> extract_experience parallel
            technologies bleiben im RAM!
Schritt 9:  Post-Processor (Token-Coverage)
Schritt 10: skill_normalizer:
            - technologies aus RAM sammeln → Counter
            - Duplikate entfernen
            - sequenziell durch NORMALIZE_ORDER kategorisieren
            - ConsultantSkill + ExperienceTechnology in DB schreiben
Schritt 11: normalize_skills() → Skills aus Bloecken (Schritt 7) normalisieren
            -> HTML generieren
"""
import json
import logging
import os
import re
import shutil
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.conf import settings

from .enricher.extracted_to_db import extracted_to_db
from .extractors.base_extractor import UniversalExtractor
from .models import Consultant, SkillCategory
from .post_processor import post_processor
from .services.aid_generator import aid_generator
from .services.block_detector import BlockDetector, SimpleSpan
from .services.block_labeler import block_labeler, LabeledGroup
from .services.pdf_extractor import pdf_extractor
from .services.skill_normalizer import skill_normalizer

logger = logging.getLogger(__name__)


def _get_workers(key: str, default: int) -> int:
    try:
        cfg_path = os.path.join(settings.BASE_DIR, 'settings.json')
        with open(cfg_path) as f:
            cfg = json.load(f)
        return int(cfg.get('pipeline', {}).get(key, default))
    except Exception:
        return default


def _debug(module: str) -> bool:
    try:
        cfg_path = os.path.join(settings.BASE_DIR, 'settings.json')
        with open(cfg_path) as f:
            cfg = json.load(f)
        d = cfg.get('debug', {})
        return d.get('global', False) or d.get(module, False)
    except Exception:
        return False


@dataclass
class ExtractionContext:
    labeled:     List[LabeledGroup] = field(default_factory=list)
    result:      Dict[str, Any]     = field(default_factory=dict)
    total_chars: int                = 0


class CvExtractionPipeline:

    def __init__(self):
        self.extractors       = {}
        self.skill_categories = list(
            SkillCategory.objects.exclude(name='special_skill')
                                 .values_list('name', flat=True)
        )
        logger.info(f"Pipeline initialisiert mit {len(self.skill_categories)} Skill-Kategorien")

    def _get_extractor(self, stage: str) -> UniversalExtractor:
        if stage not in self.extractors:
            self.extractors[stage] = UniversalExtractor(stage)
        return self.extractors[stage]

    def _groups_text(self, groups: List[LabeledGroup]) -> str:
        return "\n".join(span.text for lg in groups for span in lg.spans)

    def _write_tmp_txt(self, text: str,
                       first_name: str, last_name: str) -> Optional[str]:
        if not _debug('pdf_extractor'):
            return None
        consultant_dir = f"{last_name.lower()}_{first_name.lower()}"
        txt_dir = os.path.join(settings.BASE_DIR, 'data', 'extracted', consultant_dir)
        os.makedirs(txt_dir, exist_ok=True)
        tmp_path = os.path.join(txt_dir, f"tmp_{int(time.time())}.txt")
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write(text)
        logger.info(f"[DEBUG] Temporaere TXT: {tmp_path}")
        return tmp_path

    def _skills_from_blocks(self,
                             labeled: List[LabeledGroup]) -> Dict[str, List[str]]:
        skills: Dict[str, List[str]] = {}
        for lg in labeled:
            if lg.label != 'SKILLS' or not lg.skill_cat:
                continue
            for i, span in enumerate(lg.spans):
                if i == 0 and span.bold and span.size >= 13.0:
                    continue
                for part in span.text.split(','):
                    part = part.strip()
                    if part and len(part) > 1:
                        skills.setdefault(lg.skill_cat, []).append(part)
        return {k: list(dict.fromkeys(v)) for k, v in skills.items() if v}

    def _focus_exp_from_blocks(self,
                                labeled: List[LabeledGroup]) -> List[str]:
        items = []
        for lg in labeled:
            if lg.label != 'FOCUS_EXP':
                continue
            for i, span in enumerate(lg.spans):
                if i == 0 and span.bold and span.size >= 13.0:
                    continue
                text = span.text.strip()
                if not text or len(text) <= 1:
                    continue
                # Fliesstext-Erkennung: langer Text, Satzendezeichen,
                # Doppelpunkt ohne Komma, mehrere Punkte
                is_fliesstext = (
                    len(text) > 60
                    or text.endswith('.')
                    or (':' in text and ',' not in text)
                    or text.count('.') > 1
                    or (len(text) > 30 and text.count(',') == 0)
                )
                if is_fliesstext:
                    items.append(text)
                else:
                    for part in text.split(','):
                        part = part.strip()
                        if part and len(part) > 1:
                            items.append(part)
        return list(dict.fromkeys(items))

    def _extract_projects(self,
                           labeled: List[LabeledGroup]) -> List[Dict]:
        proj_dict: Dict[int, List[LabeledGroup]] = {}
        for lg in labeled:
            if lg.project_nr is None:
                if lg.label == 'EXPERIENCE' and re.search(r'\d{1,2}/\d{4}', lg.text):
                    proj_dict.setdefault(-lg.index, []).append(lg)
                continue
            proj_dict.setdefault(lg.project_nr, []).append(lg)

        extractor = self._get_extractor("extract_experience")
        total_projects = len(proj_dict)
        logger.info(f"  {total_projects} Projekte parallel verarbeiten...")

        def _extract_one(pnr_grps):
            pnr, grps = pnr_grps
            text = self._groups_text(grps)
            if not text.strip():
                return pnr, []
            data = extractor.extract(text)
            if not data:
                return pnr, []
            exp = data if isinstance(data, list) else data.get('experience', data)
            result = []
            if isinstance(exp, list):
                for p in exp:
                    if any([p.get('period'), p.get('company'),
                            p.get('role'),   p.get('activities')]):
                        result.append(p)
            elif isinstance(exp, dict):
                if any([exp.get('period'), exp.get('company'),
                        exp.get('role'),   exp.get('activities')]):
                    result.append(exp)
            return pnr, result

        items = [(pnr, proj_dict[pnr]) for pnr in sorted(proj_dict.keys())]
        results_map = {}
        done = 0
        with ThreadPoolExecutor(max_workers=_get_workers("parallel_workers_projects", 10)) as executor:
            futures = {executor.submit(_extract_one, item): item[0] for item in items}
            for future in as_completed(futures):
                pnr, projs = future.result()
                results_map[pnr] = projs
                done += 1
                logger.info(f"  Projekt {done}/{total_projects} fertig")

        projects = []
        for pnr in sorted(results_map.keys()):
            projects.extend(results_map[pnr])
        return projects

    def _save_artifacts(self, consultant, extracted_data,
                        pdf_path, raw_text, tmp_txt_path=None):
        aid            = consultant.aid
        version        = consultant.version
        consultant_dir = (consultant.consultant_dir or
                          f"{consultant.last_name.lower()}_{consultant.first_name.lower()}")
        data_root = os.path.join(settings.BASE_DIR, 'data')

        if pdf_path and os.path.exists(pdf_path) and pdf_path.lower().endswith('.pdf'):
            pdf_dir    = os.path.join(data_root, 'pdf')
            os.makedirs(pdf_dir, exist_ok=True)
            pdf_target = os.path.join(pdf_dir, f"{aid}.pdf")
            shutil.copy2(pdf_path, pdf_target)
            logger.info(f"PDF abgelegt: {pdf_target}")

        if _debug('pdf_extractor'):
            txt_dir  = os.path.join(data_root, 'extracted', consultant_dir)
            os.makedirs(txt_dir, exist_ok=True)
            txt_path = os.path.join(txt_dir, f"{aid}.txt")
            if tmp_txt_path and os.path.exists(tmp_txt_path):
                os.rename(tmp_txt_path, txt_path)
                logger.info(f"[DEBUG] TXT umbenannt: {txt_path}")
            else:
                with open(txt_path, 'w', encoding='utf-8') as f:
                    f.write(raw_text)
        else:
            if tmp_txt_path and os.path.exists(tmp_txt_path):
                os.remove(tmp_txt_path)

        if _debug('enricher'):
            enriched_dir = os.path.join(data_root, 'enriched', consultant_dir)
            os.makedirs(enriched_dir, exist_ok=True)
            with open(os.path.join(enriched_dir,
                                   f"{aid}_{version}_master.json"), 'w',
                      encoding='utf-8') as f:
                json.dump(consultant.extracted_json_export, f,
                          indent=2, ensure_ascii=False)

        os.makedirs(os.path.join(data_root, 'html_out', consultant_dir),
                    exist_ok=True)

    def _save_to_database(self, result, pdf_path="", raw_text="",
                          first_name="", last_name="",
                          tmp_txt_path=None,
                          target_directory="",
                          action_type="new_version") -> Optional[Consultant]:
        if not first_name:
            first_name = (result.get('extracted_data', {})
                               .get('personal', {})
                               .get('first_name', ''))
        if not last_name:
            last_name  = (result.get('extracted_data', {})
                               .get('personal', {})
                               .get('last_name', ''))
        if not first_name or not last_name:
            logger.warning("Keine Namen - DB-Speicherung uebersprungen")
            return None

        aid_info = self._generate_aid(
            {**result.get('extracted_data', {}),
             'headline': result.get('metadata', {}).get('headline', '')},
            first_name, last_name,
            target_directory=target_directory,
            action_type=action_type
        )
        if not aid_info:
            return None

        aid = aid_info['aid']
        consultant, created = Consultant.objects.get_or_create(aid=aid)

        consultant.version        = aid_info['version_string']
        consultant.consultant_dir = aid_info.get(
            'consultant_dir',
            f"{last_name.lower()}_{first_name.lower()}"
        )
        consultant.first_name = first_name
        consultant.last_name  = last_name
        consultant.raw_text   = raw_text

        personal = result.get('extracted_data', {}).get('personal', {})
        metadata = result.get('metadata', {})
        consultant.headline             = metadata.get('headline', '')
        consultant.birth_year           = personal.get('birth_year')
        consultant.nationality          = personal.get('nationality', '')
        consultant.email                = personal.get('email', '')
        consultant.phone                = personal.get('phone', '')
        consultant.location             = personal.get('location', '')
        consultant.availability         = personal.get('availability', '')
        consultant.edv_experience_since = personal.get('edv_experience_since')
        consultant.degree               = personal.get('degree', '')
        consultant.company = metadata.get('company', '')
        consultant.address = metadata.get('address', '')
        consultant.website = metadata.get('website', '')
        consultant.stand   = metadata.get('stand', '')

        consultant.extracted_json_export = {
            "metadata": {
                **metadata,
                "aid":            aid,
                "version":        consultant.version,
                "consultant_dir": consultant.consultant_dir,
                "generated_by":   "cv_extractor_pipeline_v2",
            },
            "extracted_data": result.get('extracted_data', {}),
            "raw_text":       raw_text,
        }
        consultant.save()

        from apps.cv_extractor.services.versioning import version_manager
        version_manager.bind_real_aid(
            consultant.consultant_dir, consultant.version, aid
        )

        consultant = extracted_to_db.save(consultant,
                                          consultant.extracted_json_export)
        self._save_artifacts(consultant, consultant.extracted_json_export,
                             pdf_path, raw_text, tmp_txt_path)

        logger.info(f"DB gespeichert: {consultant.aid} "
                    f"({'neu' if created else 'aktualisiert'})")
        logger.info(f"  Version:    {consultant.version}")
        logger.info(f"  Verzeichnis:{consultant.consultant_dir}")
        logger.info(f"  Degree:     {consultant.degree}")
        return consultant

    def _generate_aid(self, extracted_data, first_name, last_name,
                      target_directory="", action_type="new_version"):
        try:
            result = aid_generator.generate_from_cv(
                extracted_data, first_name, last_name,
                target_directory=target_directory,
                action_type=action_type
            )
            if result:
                logger.info(f"AID generiert: {result['aid']}")
                return result
        except Exception as e:
            logger.error(f"AID-Generierung fehlgeschlagen: {e}")
        return None

    def _generate_html(self, consultant: Consultant):
        try:
            from .generator.html.html_generator import HTMLGenerator
            gen = HTMLGenerator()
            r1  = gen.generate('aid-profile', consultant)
            r2  = gen.generate('aid-short',   consultant)
            logger.info(f"HTML Profil:   {r1['url']}")
            logger.info(f"HTML Kurzprofil: {r2['url']}")
            # Publish nach /mnt/public/.../neu/cv/ läuft in HTMLGenerator (aid-profile)
            return r1['url']
        except Exception as e:
            logger.error(f"HTML-Generierung fehlgeschlagen: {e}")
            return None

    def _build_tech_counter_from_ram(self, experience_list: List[Dict],
                                      consultant) -> tuple:
        """
        Baut Counter aus technologies im RAM (ctx.result).
        Gibt (tech_counter, experience_map) zurueck.

        tech_counter:   {skill_name: count}
        experience_map: {skill_name: [Experience-DB-Objekt, ...]}
        """
        tech_counter   = Counter()
        experience_map = defaultdict(list)

        # Experience-Objekte aus DB holen (wurden von extracted_to_db gespeichert)
        exp_db_list = list(consultant.experience.all().order_by('sort_order'))

        for idx, exp_data in enumerate(experience_list):
            techs = exp_data.get('technologies', [])
            if not techs:
                continue
            # Passendes DB-Objekt finden (per Index)
            exp_db = exp_db_list[idx] if idx < len(exp_db_list) else None
            for tech in techs:
                if isinstance(tech, dict):
                    name = (tech.get('name') or tech.get('skill') or
                            tech.get('technology') or '').strip()
                elif isinstance(tech, str):
                    name = tech.strip()
                else:
                    continue
                if name and len(name) > 1:
                    tech_counter[name] += 1
                    if exp_db:
                        experience_map[name].append(exp_db)

        logger.info(f"  Tech-Counter aus RAM: {len(tech_counter)} einzigartige Technologien")
        return tech_counter, dict(experience_map)

    # ── Haupt-Pipeline ────────────────────────────────────────────────────────

    def run(self, pdf_path: str,
            save_to_db: bool = True,
            first_name: str = "",
            last_name:  str = "",
            target_directory: str = "",
            action_type: str = "new_version") -> Dict[str, Any]:

        _pipeline_start = time.time()
        logger.info("=" * 60)
        logger.info("CV EXTRACTION PIPELINE START")
        logger.info("=" * 60)

        # ── Schritt 0: PDF/DOCX → Spans → Bloecke ────────────────────────────
        logger.info("SCHRITT 0: Dokument extrahieren + Bloecke erkennen")
        is_docx = pdf_path.lower().endswith('.docx')

        if is_docx:
            from .services.word_extractor import word_extractor
            res      = word_extractor.extract(pdf_path)
            raw_text = res.text
            spans    = res.spans
            logger.info(f"  DOCX: {len(spans)} Spans, {res.page_count} Seiten")
        else:
            res      = pdf_extractor.extract(pdf_path)
            raw_text = res.text
            spans    = [
                SimpleSpan(page=s.page, y=s.y, x=s.x, size=s.size,
                           bold=s.bold, italic=s.italic, font=s.font, text=s.text)
                for s in res.spans
            ]

        groups, stats = BlockDetector().detect(spans)
        total_chars   = sum(len(s.text) for s in spans)
        logger.info(f"  {len(spans)} Spans, "
                    f"{stats['total_projects']} Gruppen, "
                    f"{total_chars} Zeichen")

        tmp_txt_path = self._write_tmp_txt(raw_text, first_name, last_name)

        ctx = ExtractionContext(
            total_chars=total_chars,
            result={
                "metadata": {},
                "extracted_data": {
                    "personal": {
                        "first_name": "", "last_name": "",
                        "birth_year": None, "nationality": "",
                        "languages": [], "email": "", "phone": "",
                        "location": "", "availability": "",
                        "degree": "", "edv_experience_since": None,
                        "headline": "", "summary": "",
                    },
                    "skills":           {},
                    "certifications":   [],
                    "experience":       [],
                    "industries":       [],
                    "focus_areas":      [],
                    "focus_experience": [],
                    "education":        [],
                    "other":            "",
                },
                "audit": {
                    "steps_completed":   [],
                    "total_chars_input": total_chars,
                    "extracted_at":      datetime.now().isoformat(),
                },
            },
        )

        # ── Schritt 1: Block-Labeler ──────────────────────────────────────────
        logger.info("SCHRITT 1: Block-Labeler")
        _t_label    = time.time()
        labeled     = block_labeler.label(groups)
        ctx.labeled = labeled
        dist = Counter(lg.label for lg in labeled)
        for k, v in sorted(dist.items()):
            logger.info(f"  {k}: {v}")
        ctx.result['audit']['steps_completed'].append('block_labeler')
        logger.info(f"  Block-Labeler: {time.time()-_t_label:.0f}s")

        def get_blocks(label: str) -> List[LabeledGroup]:
            return [lg for lg in labeled if lg.label == label]

        # ── Schritte 2-6: Parallel extrahieren ───────────────────────────────
        logger.info("SCHRITTE 2-6: Parallel extrahieren...")
        _t_parallel = time.time()

        def _run_personal():
            pb = get_blocks('PERSONAL')
            if not pb: return 'personal', {}
            return 'personal', self._get_extractor("extract_personal").extract(
                self._groups_text(pb))

        def _run_focus():
            fb = get_blocks('FACHBEREICHE')
            if not fb: return 'focus_areas', {}
            return 'focus_areas', self._get_extractor("extract_focus_areas").extract(
                self._groups_text(fb))

        def _run_cert():
            zb = get_blocks('ZERTIFIKATE')
            if not zb: return 'certifications', {}
            return 'certifications', self._get_extractor("extract_certifications").extract(
                self._groups_text(zb))

        def _run_schulungen():
            sb = get_blocks('SCHULUNGEN')
            if not sb: return 'schulungen', {}
            return 'schulungen', self._get_extractor("extract_schulungen").extract(
                self._groups_text(sb))

        def _run_industries():
            bb = get_blocks('BRANCHEN')
            if not bb: return 'industries', {}
            return 'industries', self._get_extractor("extract_industries").extract(
                self._groups_text(bb))

        def _run_kopf():
            hb = get_blocks('HEADER')
            if not hb: return 'kopf', {}
            return 'kopf', self._get_extractor("extract_kopf").extract(
                self._groups_text(hb))

        _par = {}
        with ThreadPoolExecutor(max_workers=_get_workers("parallel_workers_sections", 6)) as executor:
            _futs = [
                executor.submit(_run_personal),
                executor.submit(_run_focus),
                executor.submit(_run_cert),
                executor.submit(_run_schulungen),
                executor.submit(_run_industries),
                executor.submit(_run_kopf),
            ]
            for fut in as_completed(_futs):
                key, data = fut.result()
                _par[key] = data

        logger.info(f"  Parallel-Extraktion: {time.time()-_t_parallel:.0f}s")

        # Schritt 2: Personal
        data = _par.get('personal', {})
        if data:
            for key in ['first_name', 'last_name', 'birth_year',
                        'nationality', 'languages', 'email', 'phone',
                        'location', 'availability',
                        'edv_experience_since', 'degree']:
                if key in data:
                    ctx.result['extracted_data']['personal'][key] = data[key]
            if 'education' in data:
                for edu in data['education']:
                    edu.setdefault('education_type', 'degree')
                ctx.result['extracted_data']['education'] = data['education']
            if not first_name:
                first_name = data.get('first_name', '')
            if not last_name:
                last_name  = data.get('last_name', '')
            logger.info(f"  Personal: {first_name} {last_name}, "
                        f"Degree: {data.get('degree', '-')}")
        ctx.result['audit']['steps_completed'].append('personal')

        # Schritt 3: Fachbereiche
        data = _par.get('focus_areas', {})
        if data and 'focus_areas' in data:
            ctx.result['extracted_data']['focus_areas'] = data['focus_areas']
            logger.info(f"  Fachbereiche: {len(data['focus_areas'])}")
        ctx.result['audit']['steps_completed'].append('focus_areas')

        # Schritt 4a: Zertifikate
        data = _par.get('certifications', {})
        if data and 'certifications' in data:
            ctx.result['extracted_data']['certifications'] = data['certifications']
            logger.info(f"  Zertifikate: {len(data['certifications'])}")

        # Schritt 4b: Schulungen
        data = _par.get('schulungen', {})
        if data:
            schulungen = data if isinstance(data, list) else \
                data.get('schulungen', data.get('courses', []))
            ctx.result['extracted_data']['schulungen'] = schulungen
            logger.info(f"  Schulungen: {len(schulungen)}")
        ctx.result['audit']['steps_completed'].append('certifications')

        # Schritt 5: Branchen
        data = _par.get('industries', {})
        if data and 'industries' in data:
            ctx.result['extracted_data']['industries'] = data['industries']
            logger.info(f"  Branchen: {len(data['industries'])}")
        ctx.result['audit']['steps_completed'].append('industries')

        # Schritt 6: Kopf
        data = _par.get('kopf', {})
        if data:
            ctx.result['metadata'] = data
            logger.info(f"  Headline: {data.get('headline', '-')[:60]}")
        ctx.result['audit']['steps_completed'].append('kopf')

        # ── Schritt 7: Skills + FOCUS_EXP direkt aus Bloecken ─────────────────
        logger.info("SCHRITT 7: Skills + FOCUS_EXP (direkt aus Bloecken)")
        skills = self._skills_from_blocks(labeled)
        ctx.result['extracted_data']['skills'] = skills
        total_sk = sum(len(v) for v in skills.values())
        logger.info(f"  {len(skills)} Kategorien, {total_sk} Skills")

        focus_exp = self._focus_exp_from_blocks(labeled)
        ctx.result['extracted_data']['focus_experience'] = focus_exp
        logger.info(f"  FOCUS_EXP: {len(focus_exp)} Eintraege")
        ctx.result['audit']['steps_completed'].append('skills_blocks')

        # ── Schritt 8: Projekte parallel ──────────────────────────────────────
        # technologies bleiben im RAM → ctx.result['extracted_data']['experience']
        logger.info("SCHRITT 8: Projekte (parallel)")
        _t_proj  = time.time()
        projects = self._extract_projects(labeled)
        ctx.result['extracted_data']['experience'] = projects
        logger.info(f"  {len(projects)} Projekte in {time.time()-_t_proj:.0f}s")
        ctx.result['audit']['steps_completed'].append('experience')

        # Branchen aus Projekten nachfuellen wenn kein BRANCHEN-Block
        if not ctx.result['extracted_data']['industries']:
            branchen = set()
            for p in projects:
                ind = p.get('industry', '').strip()
                if ind and len(ind) > 2:
                    for b in re.split(r'[|,]', ind):
                        b = b.strip()
                        if b and len(b) > 2:
                            branchen.add(b)
            if branchen:
                ctx.result['extracted_data']['industries'] = sorted(branchen)
                logger.info(f"  Branchen aus Projekten: {sorted(branchen)}")

        # ── Schritt 9: Post-Processor (Token-Coverage) ────────────────────────
        logger.info("SCHRITT 9: Post-Processor")
        try:
            pp = post_processor.analyze(ctx.result, pdf_path)
            ctx.result['audit']['post_processor'] = {
                'coverage_percent': pp.coverage_percent,
                'integrity_ok':     pp.integrity_ok,
            }
            logger.info(f"  Token-Coverage: {pp.coverage_percent:.1f}%  "
                       f"({'✅' if pp.coverage_percent >= 85 else '⚠️'})")
        except Exception as e:
            logger.warning(f"  Post-Processor fehlgeschlagen: {e}")
        ctx.result['audit']['steps_completed'].append('post_processor')
        ctx.result['audit']['integrity_ok'] = True

        # ── Abschluss-Log ──────────────────────────────────────────────────────
        skills_all = ctx.result['extracted_data']['skills']
        _duration  = time.time() - _pipeline_start
        logger.info("=" * 60)
        logger.info("PIPELINE ABGESCHLOSSEN")
        logger.info(f"  Projekte:      {len(ctx.result['extracted_data']['experience'])}")
        logger.info(f"  Zertifikate:   {len(ctx.result['extracted_data']['certifications'])}")
        logger.info(f"  Fachbereiche:  {len(ctx.result['extracted_data']['focus_areas'])}")
        logger.info(f"  Branchen:      {len(ctx.result['extracted_data']['industries'])}")
        logger.info(f"  Skills:        {len([k for k, v in skills_all.items() if v])} Kategorien")
        logger.info(f"  FOCUS_EXP:     {len(ctx.result['extracted_data']['focus_experience'])}")
        logger.info(f"  Degree:        {ctx.result['extracted_data']['personal'].get('degree', '-')}")
        logger.info(f"  Gesamtdauer:   {_duration:.0f}s ({_duration/60:.1f} min)")
        logger.info("=" * 60)

        # ── DB + HTML ──────────────────────────────────────────────────────────
        if save_to_db:
            consultant = self._save_to_database(
                ctx.result, pdf_path, raw_text,
                first_name, last_name, tmp_txt_path,
                target_directory=target_directory,
                action_type=action_type
            )
            if consultant:
                ctx.result.setdefault('metadata', {})['aid'] = consultant.aid
                ctx.result['metadata']['version']        = consultant.version
                ctx.result['metadata']['consultant_dir'] = consultant.consultant_dir

                try:
                    pp2 = post_processor.analyze(ctx.result, pdf_path, consultant)
                    post_processor.print_summary(pp2)
                    if pp2.auto_added_skills or pp2.auto_added_products:
                        logger.info(f"  Auto-Nachsortierung: "
                                   f"+{pp2.auto_added_skills} Skills, "
                                   f"+{pp2.auto_added_products} Produkte")
                except Exception as e:
                    logger.warning(f"Post-Prozessor Auto-Sort fehlgeschlagen: {e}")

                # ── Schritt 10: Skill-Normalisierung aus Projekt-Technologien ──
                logger.info("SCHRITT 10: Skill-Normalisierung aus Projekten")
                try:
                    experience_list = ctx.result['extracted_data']['experience']
                    tech_counter, experience_map = self._build_tech_counter_from_ram(
                        experience_list, consultant
                    )
                    if tech_counter:
                        headline = ctx.result.get("metadata", {}).get("headline", "")
                        normalized = skill_normalizer.normalize(tech_counter, headline=headline)
                        stats = skill_normalizer.save_to_db(
                            consultant, normalized, experience_map
                        )
                        logger.info(f"  +{stats['added']} Skills, "
                                   f"{stats['updated']} Gewichtungen aktualisiert")
                    else:
                        logger.info("  Keine Technologien in Projekten gefunden")
                except Exception as e:
                    logger.warning(f"  Skill-Normalisierung Schritt 10 fehlgeschlagen: {e}")

                # DEAKTIVIERT: # ── Schritt 11: normalize_skills() → Skills aus Bloecken ───────
                # DEAKTIVIERT: logger.info("SCHRITT 11: Skill-Normalisierung (Bloecke)")
                # DEAKTIVIERT: try:
                # DEAKTIVIERT: moved = post_processor.normalize_skills(consultant)
                # DEAKTIVIERT: logger.info(f"  {moved} Skills normalisiert")
                # DEAKTIVIERT: except Exception as e:
                # DEAKTIVIERT: logger.warning(f"  Skill-Normalisierung fehlgeschlagen: {e}")

                self._generate_html(consultant)
        else:
            if tmp_txt_path and os.path.exists(tmp_txt_path):
                os.remove(tmp_txt_path)

        return ctx.result


pipeline = CvExtractionPipeline()
