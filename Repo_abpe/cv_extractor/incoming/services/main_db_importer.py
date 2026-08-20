"""
main_db_importer.py — main_pipeline DB-Import

Zwei Methoden:
  import_one()         — FL-Pipeline (liest profil_pre_json.json von Disk)
  import_from_prejson() — main_pipeline (alles im RAM, kein Disk-Lesen)

Einzige Disk-Outputs (import_from_prejson):
  data/extracted/<dir>/<AID>.txt
  data/html_out/<dir>/<AID>.html
"""
import copy
import json
import logging
from pathlib import Path
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)
BASE_DIR = Path('data/url/fl')


class MainDbImporter:

    @staticmethod
    def _as_name(item) -> str:
        """str | dict{name/skill/technology} → Anzeigename."""
        if isinstance(item, dict):
            return (
                item.get('name') or item.get('skill') or item.get('technology') or ''
            ).strip()
        if isinstance(item, str):
            return item.strip()
        return str(item).strip() if item is not None else ''

    @classmethod
    def _join_names(cls, items, limit=None) -> str:
        names = []
        for it in (items or []):
            n = cls._as_name(it)
            if n:
                names.append(n)
            if limit is not None and len(names) >= limit:
                break
        return ', '.join(names)

    @staticmethod
    def _years_from_periods(experience_list) -> list:
        """Volle Jahre (19xx/20xx) aus Projekt-Perioden — nicht nur (19|20)-Captures."""
        import re as _re
        years = []
        for e in experience_list or []:
            period = (e.get('period') if isinstance(e, dict) else '') or ''
            for y in _re.findall(r'\b((?:19|20)\d{2})\b', period):
                try:
                    yr = int(y)
                except Exception:
                    continue
                if 1970 <= yr <= 2030:
                    years.append(yr)
        return years

    def import_all(self, dry_run=False):
        """Alle FL-Profile sequenziell importieren."""
        results = {'ok': [], 'error': []}
        dirs = sorted([d for d in BASE_DIR.iterdir() if d.is_dir()])
        logger.info(f"[FLDbImporter] {len(dirs)} Profile gefunden")
        for d in dirs:
            try:
                r = self.import_one(d.name, dry_run=dry_run)
                if r.get('success'):
                    results['ok'].append({'dir': d.name, 'aid': r.get('aid'), 'name': r.get('name')})
                    logger.info(f"  ✅ {d.name} → {r.get('aid')}")
                else:
                    results['error'].append({'dir': d.name, 'error': r.get('error')})
                    logger.warning(f"  ❌ {d.name}: {r.get('error')}")
            except Exception as e:
                results['error'].append({'dir': d.name, 'error': str(e)})
                logger.error(f"  ❌ {d.name}: {e}")
        logger.info(f"[FLDbImporter] {len(results['ok'])} OK, {len(results['error'])} Fehler")
        return results

    def import_one(self, dir_name, dry_run=False,
                   first_name_override=None, last_name_override=None):

        base          = BASE_DIR / dir_name
        pre_json_path = base / 'profil_pre_json.json'
        if not pre_json_path.exists():
            profil_path = base / 'profil.json'
            if profil_path.exists():
                logger.info(f"[FLDBImporter] profil_pre_json.json fehlt → starte Pipeline für {dir_name}")
                try:
                    import json as _json
                    from apps.cv_extractor.services.url_fl_importer import url_importer
                    profil = _json.loads(profil_path.read_text(encoding='utf-8'))
                    url_importer._run_freelancermap(
                        url     = profil.get('url', ''),
                        profil  = profil.get('profile', {}),
                        person  = profil.get('person', {}),
                        address = profil.get('address', {}),
                        base    = base,
                        dl_dir  = base / 'download',
                        ex_dir  = base / 'extract',
                    )
                except Exception as e:
                    logger.warning(f"[FLDBImporter] Pipeline Fehler: {e}")
                    return {'success': False, 'error': f'Pipeline Fehler: {e}'}
            if not pre_json_path.exists():
                return {'success': False, 'error': 'profil_pre_json.json fehlt'}

        pre_json = json.loads(pre_json_path.read_text(encoding='utf-8'))

        try:
            from apps.cv_extractor.services.master_merger import master_merger
            pdf_pre_jsons = []
            for i in range(1, 20):
                p = base / f'pdf_pre_json_{i}.json'
                if not p.exists():
                    break
                try:
                    pj = json.loads(p.read_text(encoding='utf-8'))
                    n  = len(pj.get('extracted_data', {}).get('experience', []))
                    logger.info(f"  pdf_pre_json_{i}.json: {n} Projekte")
                    pdf_pre_jsons.append(pj)
                except Exception as e:
                    logger.warning(f"  pdf_pre_json_{i}.json Fehler: {e}")

            extra_certifications = []
            extra_experience     = []
            extra_education      = []
            classifier_path = base / 'analysis' / 'classifier.json'
            if classifier_path.exists():
                try:
                    clf = json.loads(classifier_path.read_text(encoding='utf-8'))
                    extra_certifications = clf.get('certifications', [])
                    extra_experience     = clf.get('experience', [])
                    extra_education      = clf.get('education', [])
                    logger.info(f"  classifier.json: "
                                f"{len(extra_certifications)} certs, "
                                f"{len(extra_experience)} refs, "
                                f"{len(extra_education)} edu")
                except Exception as e:
                    logger.warning(f"  classifier.json Fehler: {e}")

            if pdf_pre_jsons:
                logger.info(f"[FLDBImporter] master_merger: {len(pdf_pre_jsons)} PDFs + API")
                profil_raw = None
                try:
                    profil_raw = json.loads((base / 'profil.json').read_text(encoding='utf-8'))
                except Exception as e:
                    logger.warning(f"  profil.json lesen fehlgeschlagen: {e}")

                api_only_pre_json = None
                if profil_raw:
                    try:
                        from apps.cv_extractor.services.url_fl_importer import url_importer
                        meta      = pre_json.get('metadata', {})
                        fn        = first_name_override or meta.get('first_name', '')
                        ln        = last_name_override  or meta.get('last_name',  '')
                        if not fn or not ln:
                            parts = dir_name.replace('-', '_').split('_')
                            ln = parts[0].capitalize() if len(parts) >= 2 else dir_name
                            fn = parts[1].capitalize() if len(parts) >= 2 else 'Unbekannt'
                        api_only_pre_json = url_importer._build_pre_json(
                            profil_raw.get('profile', {}),
                            profil_raw.get('person',  {}),
                            profil_raw.get('address', {}),
                            profil_raw.get('url', ''),
                            fn, ln,
                        )
                        n_api = len(api_only_pre_json.get('extracted_data', {}).get('experience', []))
                        logger.info(f"  API-only pre_json: {n_api} Projekte als Anker")
                    except Exception as e:
                        logger.warning(f"  api_only_pre_json Fehler: {e}")
                        api_only_pre_json = None

                if api_only_pre_json is None:
                    logger.warning("  Fallback: profil_pre_json als Anker (api_only nicht verfuegbar)")
                    api_only_pre_json = pre_json

                pre_json = master_merger.merge(
                    pdf_pre_jsons        = pdf_pre_jsons,
                    api_pre_json         = api_only_pre_json,
                    extra_certifications = extra_certifications,
                    extra_experience     = extra_experience,
                    extra_education      = extra_education,
                    profil_raw           = profil_raw,
                )
                n_proj = len(pre_json.get('extracted_data', {}).get('experience', []))
                logger.info(f"[FLDBImporter] master_merger: {n_proj} Projekte")
                pre_json_path.write_text(
                    json.dumps(pre_json, indent=2, ensure_ascii=False), encoding='utf-8'
                )
            else:
                logger.info(f"[FLDBImporter] Keine PDFs -> nur API-Daten")
        except Exception as e:
            logger.warning(f"[FLDBImporter] master_merger Fehler: {e}")

        try:
            from apps.cv_extractor.services.master_post_clean import master_post_cleaner
            pre_json = master_post_cleaner.clean(pre_json)
            n_proj = len(pre_json.get('extracted_data', {}).get('experience', []))
            logger.info(f"[FLDBImporter] post_clean: {n_proj} Projekte")
        except Exception as e:
            logger.warning(f"[FLDBImporter] post_clean Fehler: {e}")

        try:
            from apps.cv_extractor.services.master_translator_to_de import master_translator_to_de
            logger.info(f"[FLDBImporter] Übersetze auf Deutsch...")
            pre_json = master_translator_to_de.translate_pre_json(pre_json)
            pre_json_path.write_text(
                json.dumps(pre_json, indent=2, ensure_ascii=False), encoding='utf-8'
            )
            logger.info(f"[FLDBImporter] Übersetzung abgeschlossen")
        except Exception as e:
            logger.warning(f"[FLDBImporter] Übersetzung fehlgeschlagen: {e}")

        meta  = pre_json.get('metadata', {})
        first = first_name_override or meta.get('first_name', '')
        last  = last_name_override  or meta.get('last_name',  '')
        if not first or not last:
            parts = dir_name.replace('-', '_').split('_')
            if len(parts) >= 2:
                last  = parts[0].capitalize()
                first = parts[1].capitalize()
            else:
                first = 'Unbekannt'
                last  = dir_name

        if dry_run:
            ed = pre_json.get('extracted_data', {})
            return {
                'success':  True,
                'dry_run':  True,
                'name':     f"{first} {last}",
                'projects': len(ed.get('experience', [])),
                'skills':   sum(len(v) for v in ed.get('skills', {}).values()),
            }

        from apps.cv_extractor.models import UploadedPDF
        upload = UploadedPDF.objects.create(
            filename    = f"FL:{dir_name}",
            first_name  = first,
            last_name   = last,
            action_type = 'url_import',
            status      = 'processing',
        )

        from apps.cv_extractor.services.aid_generator import aid_generator
        from apps.cv_extractor.services.versioning    import version_manager
        version_info   = version_manager.get_next_version(
            first, last, target_directory=dir_name, action_type='new_version'
        )
        consultant_dir = version_info['consultant_dir']
        aid_info = aid_generator.generate_from_cv(
            pre_json['extracted_data'], first, last,
            target_directory=consultant_dir, action_type='new_version',
            version_info=version_info
        )
        if not aid_info:
            upload.status = 'failed'
            upload.save(update_fields=['status'])
            return {'success': False, 'error': 'AID-Generierung fehlgeschlagen'}

        aid = aid_info['aid']
        pre_json['metadata']['aid']            = aid
        pre_json['metadata']['version']        = aid_info['version_string']
        pre_json['metadata']['consultant_dir'] = consultant_dir

        from apps.cv_extractor.models import Consultant
        from apps.cv_extractor.enricher.main_extracted_to_db import main_extracted_to_db
        consultant, created = Consultant.objects.get_or_create(aid=aid)
        personal = pre_json['extracted_data'].get('personal', {})

        consultant.version              = aid_info['version_string']
        consultant.consultant_dir       = consultant_dir
        consultant.first_name           = first
        consultant.last_name            = last
        consultant.source_type          = 'url_import'
        try:
            version_manager.bind_real_aid(
                consultant_dir, aid_info['version_string'], aid
            )
        except Exception as _e:
            logger.warning(f"  ConsultantVersion AID-Bind fehlgeschlagen: {_e}")
        consultant.headline             = meta.get('headline', '')
        consultant.birth_year           = personal.get('birth_year')
        consultant.nationality          = personal.get('nationality', '')
        consultant.email                = personal.get('email', '')
        consultant.phone                = personal.get('phone', '')
        consultant.location             = personal.get('location', '')
        consultant.availability         = personal.get('availability', '')
        try:
            from apps.cv_extractor.services.master_merger import _normalize_period
            _exps = pre_json['extracted_data'].get('experience', [])
            _years = []
            for _e in _exps:
                _sy, _sm, _ey, _em = _normalize_period(_e.get('period', ''))
                if _sy and _sy > 1900:
                    _years.append(_sy)
            _edv = min(_years) if _years else personal.get('edv_experience_since')
        except Exception:
            _edv = personal.get('edv_experience_since')
        consultant.edv_experience_since = _edv
        consultant.degree               = personal.get('degree') or ''
        consultant.website              = personal.get('website', '') or ''
        consultant.summary              = personal.get('summary', '') or ''

        try:
            _profil_raw   = json.loads((base / 'profil.json').read_text(encoding='utf-8'))
            _payment      = _profil_raw.get('profile', {}).get('paymentInformation', {})
            _hourly_cents = _payment.get('hourlyRateInCents') or 0
            _daily_cents  = _payment.get('dailyRateInCents')  or 0
            if _hourly_cents and isinstance(_hourly_cents, int) and _hourly_cents > 0:
                consultant.hourly_rate = _hourly_cents // 100
            elif _daily_cents and isinstance(_daily_cents, int) and _daily_cents > 0:
                consultant.hourly_rate = (_daily_cents // 8) // 100
        except Exception as _e:
            logger.debug(f"  hourly_rate nicht gesetzt: {_e}")

        consultant.extracted_json_export = {
            'metadata':       pre_json['metadata'],
            'extracted_data': pre_json['extracted_data'],
            'raw_text':       '',
        }
        consultant.status = 'processing'
        consultant.save()
        consultant = main_extracted_to_db.save(consultant, consultant.extracted_json_export)

        try:
            tech_counter, experience_map = self._build_tech_counter_from_ram(
                pre_json['extracted_data'].get('experience', []), consultant,
                pre_json=pre_json
            )
            if tech_counter:
                from apps.cv_extractor.services.main_skill_normalizer import main_skill_normalizer
                normalized, unknown_skills = main_skill_normalizer.normalize(
                    tech_counter,
                    headline=meta.get('headline', ''),
                    experience_map=experience_map,
                    consultant=consultant,
                )
                stats = main_skill_normalizer.save_to_db(consultant, normalized, experience_map)
                logger.info(f"  SkillNormalizer: +{stats['added']} Skills, {stats['updated']} aktualisiert")
                if unknown_skills:
                    logger.info(f"  {len(unknown_skills)} unbekannte Skills → Self-Learning Task")
                    try:
                        from apps.cv_extractor.tasks import process_unknown_skills_task
                        process_unknown_skills_task.delay(consultant.id, unknown_skills)
                    except Exception as _e:
                        logger.warning(f"  process_unknown_skills_task Start fehlgeschlagen: {_e}")
            else:
                logger.info(f"  Keine Technologien — überspringe SkillNormalizer")
        except Exception as e:
            logger.warning(f"  SkillNormalizer Fehler: {e}")

        consultant.status = 'profile_ready'
        consultant.save(update_fields=['status', 'updated_at'])
        try:
            from apps.cv_extractor.generator.html.html_generator import HTMLGenerator
            gen = HTMLGenerator()
            gen.generate('aid-profile', consultant)
            gen.generate('aid-short',   consultant)
            logger.info(f"  HTML: {aid}")
        except Exception as e:
            logger.warning(f"  HTML Fehler: {e}")

        try:
            extracted_dir = Path('data/extracted') / consultant_dir
            extracted_dir.mkdir(parents=True, exist_ok=True)
            txt_path = extracted_dir / f'{aid}.txt'
            ed = pre_json['extracted_data']
            p  = ed.get('personal', {})
            lines = []
            lines.append(f"AID: {aid}")
            lines.append(f"Name: {first} {last}")
            lines.append(f"Headline: {meta.get('headline','')}")
            lines.append(f"Ort: {p.get('location','')}")
            if p.get('wohnort'):
                lines.append(f"Wohnort: {p.get('wohnort')}")
            if p.get('birth_year'):
                lines.append(f"Jahrgang: {p.get('birth_year')}")
            lines.append(f"Verfügbar: {p.get('availability','')}")
            lines.append(f"EDV seit: {p.get('edv_experience_since','')}")
            langs = p.get('languages', [])
            lang_str = ', '.join(
                l.get('name','') if isinstance(l, dict) else str(l)
                for l in langs if l
            )
            lines.append(f"Sprachen: {lang_str}")
            lines.append("")
            lines.append("ZUSAMMENFASSUNG:")
            lines.append(p.get('summary',''))
            lines.append("")
            lines.append("FACHBEREICHE:")
            lines.extend(
                self._as_name(x) for x in (ed.get('focus_areas') or []) if self._as_name(x)
            )
            lines.append("")
            lines.append("BRANCHEN:")
            lines.extend(
                self._as_name(x) for x in (ed.get('industries') or []) if self._as_name(x)
            )
            lines.append("")
            lines.append("PROJEKTE:")
            for exp in ed.get('experience', []):
                lines.append(
                    f"  {exp.get('period','')} | "
                    f"{exp.get('company','')} | "
                    f"{exp.get('role', exp.get('title',''))}")
                for act in exp.get('activities', [])[:3]:
                    lines.append(f"    - {act}")
                techs = exp.get('technologies', [])
                if techs:
                    joined = self._join_names(techs, limit=10)
                    if joined:
                        lines.append(f"    Technologien: {joined}")
            lines.append("")
            lines.append("SKILLS:")
            for cat, items in ed.get('skills', {}).items():
                if items:
                    lines.append(f"  {cat}: {self._join_names(items, limit=5)}")
            # skill_ablage dict-sicher (wie import_from_prejson)
            ablage = ed.get('skill_ablage') or []
            if ablage:
                lines.append("")
                lines.append(f"SKILL-ABLAGE: {self._join_names(ablage)}")
            txt_content = '\n'.join(str(x) for x in lines)
            txt_path.write_text(txt_content, encoding='utf-8')
            consultant.raw_text = txt_content
            consultant.save(update_fields=['raw_text', 'updated_at'])
            logger.info(f"  TXT: {txt_path}")
        except Exception as e:
            logger.warning(f"  TXT Fehler: {e}")

        try:
            from apps.cv_extractor.enricher.search_enricher import search_enricher
            master_json = consultant.extracted_json_export or {}
            master_json = search_enricher.enrich(consultant, master_json)
            consultant.extracted_json_export = master_json
            consultant.save(update_fields=['extracted_json_export', 'updated_at'])
            logger.info(f"  SearchEnricher: {aid}")
        except Exception as e:
            logger.warning(f"  SearchEnricher Fehler: {e}")

        try:
            from apps.cv_extractor.enricher.self_learning_pipeline import self_learning_pipeline
            stats = self_learning_pipeline.process(consultant, consultant.extracted_json_export or {})
            logger.info(f"  SelfLearning: {stats}")
        except Exception as e:
            logger.warning(f"  SelfLearning Fehler: {e}")

        UploadedPDF.objects.filter(pk=upload.pk).update(
            status         = 'completed',
            aid            = aid,
            version        = aid_info['version_string'],
            consultant_dir = consultant_dir,
            consultant_id  = consultant.id,
        )

        try:
            from apps.cv_extractor.tasks import enrich_consultant_task
            enrich_consultant_task.delay(consultant.id)
        except Exception as e:
            logger.warning(f"  Stufe 2: {e}")

        return {
            'success':    True,
            'aid':        aid,
            'name':       f"{first} {last}",
            'consultant': consultant.id,
            'created':    created,
            'editor_url': f'/cv-extractor/editor/{aid}/',
        }

    def import_from_prejson(self, pre_json, dir_name,
                             first_name_override=None, last_name_override=None,
                             aid_skill_categories=None, source_filename=None):
        """
        aid_skill_categories: {skill_name: category} aus abcona PDF-Layout
        Wenn vorhanden → diese Skills BYPASSEN den LLM-Normalizer
        """
        """
        Importiert direkt aus pre_json (RAM) — kein Disk-Lesen.
        Einzige Disk-Outputs: TXT + HTML
        """
        from apps.cv_extractor.models import Consultant
        from apps.cv_extractor.enricher.main_extracted_to_db import main_extracted_to_db
        from apps.cv_extractor.services.aid_generator import aid_generator
        from apps.cv_extractor.services.versioning import version_manager
        from apps.cv_extractor.services.main_skill_normalizer import main_skill_normalizer

        meta  = pre_json.get('metadata', {})
        first = first_name_override or meta.get('first_name', '')
        last  = last_name_override  or meta.get('last_name',  '')
        if not first or not last:
            parts = dir_name.replace('-', '_').split('_')
            last  = parts[0].capitalize() if len(parts) >= 2 else dir_name
            first = parts[1].capitalize() if len(parts) >= 2 else 'Unbekannt'

        logger.info(f"[MainDbImporter] import_from_prejson: {first} {last}")
        n_exp    = len(pre_json.get('extracted_data', {}).get('experience', []))
        n_ablage = len(pre_json.get('extracted_data', {}).get('skill_ablage', []))
        logger.info(f"  Projekte: {n_exp} | skill_ablage: {n_ablage}")

        version_info   = version_manager.get_next_version(
            first, last, target_directory=dir_name, action_type='new_version'
        )
        consultant_dir = version_info['consultant_dir']
        aid_info = aid_generator.generate_from_cv(
            pre_json['extracted_data'], first, last,
            target_directory=consultant_dir, action_type='new_version',
            version_info=version_info
        )
        if not aid_info:
            return {'success': False, 'error': 'AID-Generierung fehlgeschlagen'}

        aid = aid_info['aid']
        pre_json['metadata']['aid']            = aid
        pre_json['metadata']['version']        = aid_info['version_string']
        pre_json['metadata']['consultant_dir'] = consultant_dir
        pre_json['metadata']['first_name']     = first
        pre_json['metadata']['last_name']      = last

        consultant, created = Consultant.objects.get_or_create(aid=aid)
        personal = pre_json['extracted_data'].get('personal', {})

        consultant.version              = aid_info['version_string']
        consultant.consultant_dir       = consultant_dir
        consultant.first_name           = first
        consultant.last_name            = last
        consultant.source_type          = 'main_pipeline'
        # Platzhalter-AID in ConsultantVersion → echte AID (sonst bleiben
        # Kollisions-Anfälligere AID-tmp/AID-tb_*_* Einträge liegen)
        try:
            version_manager.bind_real_aid(
                consultant_dir, aid_info['version_string'], aid
            )
        except Exception as _e:
            logger.warning(f"  ConsultantVersion AID-Bind fehlgeschlagen: {_e}")
        if source_filename:
            consultant.source_filename = source_filename
        consultant.headline             = (meta.get('headline', '') or
                                           personal.get('headline', ''))
        consultant.birth_year           = personal.get('birth_year')
        consultant.nationality          = personal.get('nationality', '')
        consultant.email                = personal.get('email', '')
        consultant.phone                = personal.get('phone', '')
        consultant.location             = personal.get('location', '')
        consultant.availability         = personal.get('availability', '')
        consultant.degree               = personal.get('degree') or ''
        consultant.website              = personal.get('website', '') or ''
        consultant.summary              = personal.get('summary', '') or ''

        # EDV seit: Seed/Personal hat Vorrang; sonst ältestes volles Jahr aus Perioden
        try:
            seeded_edv = personal.get('edv_experience_since')
            if isinstance(seeded_edv, int) and 1970 <= seeded_edv <= 2030:
                consultant.edv_experience_since = seeded_edv
            else:
                _years = self._years_from_periods(
                    pre_json['extracted_data'].get('experience', [])
                )
                consultant.edv_experience_since = min(_years) if _years else seeded_edv
        except Exception:
            consultant.edv_experience_since = personal.get('edv_experience_since')

        consultant.extracted_json_export = {
            'metadata':       pre_json['metadata'],
            'extracted_data': pre_json['extracted_data'],
            'raw_text':       '',
        }
        consultant.status = 'processing'
        consultant.save()

        # DB speichern via main_extracted_to_db
        consultant = main_extracted_to_db.save(consultant, consultant.extracted_json_export)

        # Felder sichern die main_extracted_to_db überschreiben könnte
        if first_name_override:
            consultant.first_name = first_name_override
        if last_name_override:
            consultant.last_name = last_name_override
        if not consultant.headline:
            fas = pre_json.get('extracted_data', {}).get('focus_areas', [])
            if fas and isinstance(fas[0], str):
                consultant.headline = fas[0]
        consultant.save(update_fields=['first_name', 'last_name', 'headline', 'updated_at'])

        # Skill-Normalisierung: Projekte + skill_ablage
        try:
            tech_counter, experience_map = self._build_tech_counter_from_ram(
                pre_json['extracted_data'].get('experience', []), consultant,
                pre_json=pre_json
            )
            if tech_counter:
                # aid_skill_categories: aus PDF-Layout vorkategorisiert (kein LLM nötig)
                pre_categorized = aid_skill_categories or {}

                if pre_categorized:
                    logger.info(f"  {len(pre_categorized)} Skills aus PDF-Layout vorkategorisiert")
                    # Vorkategorisierte direkt als normalized
                    pre_normalized = {
                        name: {'category': cat, 'count': tech_counter.get(name, 1)}
                        for name, cat in pre_categorized.items()
                        if name in tech_counter
                    }
                    # Restliche (aus Projekten, nicht aus Skill-Tabellen) via LLM
                    remaining_counter = Counter({
                        k: v for k, v in tech_counter.items()
                        if k not in pre_categorized
                    })
                    if remaining_counter:
                        logger.info(f"  {len(remaining_counter)} Projekt-Skills via Normalizer")
                        llm_normalized, unknown_skills = main_skill_normalizer.normalize(
                            remaining_counter,
                            headline=meta.get('headline', ''),
                            experience_map=experience_map,
                            consultant=consultant,
                        )
                    else:
                        llm_normalized = {}
                        unknown_skills = []
                    # Zusammenführen: PDF-Layout hat Vorrang
                    normalized = {**llm_normalized, **pre_normalized}
                    logger.info(f"  Gesamt: {len(normalized)} Skills "
                                f"({len(pre_normalized)} aus PDF, "
                                f"{len(llm_normalized)} via Normalizer)")
                else:
                    normalized, unknown_skills = main_skill_normalizer.normalize(
                        tech_counter,
                        headline=meta.get('headline', ''),
                        experience_map=experience_map,
                        consultant=consultant,
                    )
                stats = main_skill_normalizer.save_to_db(
                    consultant, normalized, experience_map
                )
                logger.info(f"  SkillNormalizer: +{stats['added']} Skills, "
                            f"{stats['updated']} aktualisiert")
                if unknown_skills:
                    logger.info(f"  {len(unknown_skills)} unbekannte Skills → Self-Learning Task")
                    try:
                        from apps.cv_extractor.tasks import process_unknown_skills_task
                        process_unknown_skills_task.delay(consultant.id, unknown_skills)
                    except Exception as _e:
                        logger.warning(f"  process_unknown_skills_task Start fehlgeschlagen: {_e}")
            else:
                logger.info(f"  Keine Technologien — überspringe SkillNormalizer")
        except Exception as e:
            logger.warning(f"  SkillNormalizer Fehler: {e}")

        # HTML generieren (Disk-Output 1)
        consultant.status = 'profile_ready'
        consultant.save(update_fields=['status', 'updated_at'])
        try:
            from apps.cv_extractor.generator.html.html_generator import HTMLGenerator
            gen = HTMLGenerator()
            gen.generate('aid-profile', consultant)
            gen.generate('aid-short',   consultant)
            logger.info(f"  HTML: {aid}")
        except Exception as e:
            logger.warning(f"  HTML Fehler: {e}")

        # TXT speichern (Disk-Output 2)
        try:
            extracted_dir = Path('data/extracted') / consultant_dir
            extracted_dir.mkdir(parents=True, exist_ok=True)
            txt_path = extracted_dir / f'{aid}.txt'
            ed = pre_json['extracted_data']
            p  = ed.get('personal', {})
            lines = [
                f"AID: {aid}",
                f"Name: {first} {last}",
                f"Headline: {meta.get('headline', '') or p.get('headline', '')}",
                f"Ort: {p.get('location', '')}",
            ]
            if p.get('wohnort'):
                lines.append(f"Wohnort: {p.get('wohnort')}")
            by = p.get('birth_year') or consultant.birth_year
            if by:
                lines.append(f"Jahrgang: {by}")
            lines += [
                f"Verfügbar: {p.get('availability', '')}",
                f"EDV seit: {consultant.edv_experience_since or ''}",
                f"Sprachen: {', '.join(l.get('name','') if isinstance(l,dict) else str(l) for l in p.get('languages',[]) if l)}",
                "",
                "FACHBEREICHE:",
            ]
            lines.extend(
                self._as_name(x) for x in (ed.get('focus_areas') or []) if self._as_name(x)
            )
            lines += ["", "BRANCHEN:"]
            lines.extend(
                self._as_name(x) for x in (ed.get('industries') or []) if self._as_name(x)
            )
            lines += ["", "PROJEKTE:"]
            for exp in ed.get('experience', []):
                lines.append(
                    f"  {exp.get('period','')} | "
                    f"{exp.get('company','')} | "
                    f"{exp.get('role', exp.get('title',''))}"
                )
                for act in exp.get('activities', [])[:3]:
                    if act:
                        lines.append(f"    - {act if isinstance(act, str) else self._as_name(act)}")
                techs = exp.get('technologies', [])
                if techs:
                    joined = self._join_names(techs, limit=10)
                    if joined:
                        lines.append(f"    Techs: {joined}")
            lines += [
                "",
                "SKILL-ABLAGE:",
                self._join_names(ed.get('skill_ablage', [])),
            ]
            txt_content = '\n'.join(str(x) for x in lines)
            txt_path.write_text(txt_content, encoding='utf-8')
            consultant.raw_text = txt_content
            consultant.save(update_fields=['raw_text', 'updated_at'])
            logger.info(f"  TXT: {txt_path}")
        except Exception as e:
            logger.warning(f"  TXT Fehler: {e}")

        # SearchEnricher
        try:
            from apps.cv_extractor.enricher.search_enricher import search_enricher
            master_json = search_enricher.enrich(consultant, consultant.extracted_json_export or {})
            consultant.extracted_json_export = master_json
            consultant.save(update_fields=['extracted_json_export', 'updated_at'])
        except Exception as e:
            logger.warning(f"  SearchEnricher Fehler: {e}")

        # SelfLearning
        try:
            from apps.cv_extractor.enricher.self_learning_pipeline import self_learning_pipeline
            self_learning_pipeline.process(consultant, consultant.extracted_json_export or {})
        except Exception as e:
            logger.warning(f"  SelfLearning Fehler: {e}")

        # Stufe 2 (Celery)
        try:
            from apps.cv_extractor.tasks import enrich_consultant_task
            enrich_consultant_task.delay(consultant.id)
        except Exception as e:
            logger.warning(f"  Stufe 2: {e}")

        return {
            'success':    True,
            'aid':        aid,
            'name':       f"{first} {last}",
            'consultant': consultant.id,
            'created':    created,
            'editor_url': f'/cv-extractor/editor/{aid}/',
        }

    def _build_tech_counter_from_ram(self, experience_list, consultant,
                                      pre_json=None):
        """Tech-Counter aus experience_list + skill_ablage."""
        tech_counter   = Counter()
        experience_map = defaultdict(list)
        exp_db_list    = list(consultant.experience.all().order_by('sort_order'))

        for idx, exp_data in enumerate(experience_list):
            techs  = exp_data.get('technologies', [])
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

        logger.info(f"  Tech-Counter Projekte: {len(tech_counter)} Technologien")

        # Müll-Filter: Header-Namen und generische Wörter entfernen
        SKILL_STOPWORDS = {
            'betriebssysteme', 'datenkommunikation', 'programmiersprachen',
            'datenbanken', 'hardware', 'netzwerkprotokolle', 'methoden',
            'tools', 'technologien', 'software', 'kenntnisse', 'werkzeuge',
            'dv-umfeld', 'entwicklungstools', 'webserver', 'middleware',
            'frameworks', 'spezialkenntnisse', 'application', 'produkte',
            'telekommunikation', 'projekt', 'daten', 'internet', 'laufwerke',
            'serversysteme', 'servermigration', 'mcse', 'e-mail',
        }
        for sw in list(tech_counter.keys()):
            if sw.lower() in SKILL_STOPWORDS or len(sw) < 2:
                del tech_counter[sw]

        if pre_json:
            skill_ablage = pre_json.get('extracted_data', {}).get('skill_ablage', [])
            added = 0
            for skill in skill_ablage:
                # Neues Format: {"name": "Linux", "category": "Betriebssysteme"}
                if isinstance(skill, dict):
                    name     = skill.get('name', '').strip()
                    category = skill.get('category', '')
                elif isinstance(skill, str):
                    name     = skill.strip()
                    category = ''
                else:
                    continue
                if name and len(name) > 1:
                    if name not in tech_counter:
                        tech_counter[name] = 1
                        added += 1
                    # Kategorie merken für direkten Bypass des SkillNormalizers
                    if category:
                        if not hasattr(tech_counter, '_categories'):
                            tech_counter._categories = {}
                        tech_counter._categories[name] = category
            if added:
                logger.info(f"  skill_ablage: +{added} Zusatz-Skills")

        logger.info(f"  Tech-Counter gesamt: {len(tech_counter)} einzigartige Technologien")
        return tech_counter, dict(experience_map)


main_db_importer = MainDbImporter()
