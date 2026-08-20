"""
url_fl_db_importer.py — freelancermap DB-Import

Importiert profil_pre_json.json aus data/url/fl/<dir>/
in die ABpE Datenbank.

Analog zu url_gu_db_importer.py aber ohne PDF-Parser
(FL PDFs sind individuell formatiert → normale Pipeline).
"""
import copy
import json
import logging
from pathlib import Path
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)
BASE_DIR = Path('data/url/fl')


class FLDbImporter:

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

        # master_merger: PDF-pre_jsons + reine API-Daten zusammenfuehren
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
                logger.info(f"[FLDBImporter] master_merger: "
                            f"{len(pdf_pre_jsons)} PDFs + API")

                # profil_raw fuer FL-API languageSkills + paymentInformation
                profil_raw = None
                try:
                    profil_raw = json.loads(
                        (base / 'profil.json').read_text(encoding='utf-8'))
                except Exception as e:
                    logger.warning(f"  profil.json lesen fehlgeschlagen: {e}")

                # Fix 2: Reine FL-API-Projekte als Anker verwenden,
                # nicht den bereits gemergten profil_pre_json.
                # profil_pre_json enthaelt den Output eines frueheren Merger-Laufs
                # mit potenziell duplizierten Projekten — das wuerde den Merger
                # gegen seinen eigenen fehlerhaften Output matchen lassen.
                api_only_pre_json = None
                if profil_raw:
                    try:
                        from apps.cv_extractor.services.url_fl_importer import url_importer
                        # Name aus vorhandenem pre_json oder dir_name ableiten
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
                        n_api = len(api_only_pre_json.get(
                            'extracted_data', {}).get('experience', []))
                        logger.info(f"  API-only pre_json: {n_api} Projekte als Anker")
                    except Exception as e:
                        logger.warning(f"  api_only_pre_json Fehler: {e}")
                        api_only_pre_json = None

                # Fallback: falls profil.json fehlt oder _build_pre_json scheitert,
                # nehmen wir pre_json wie bisher — besser als gar keine Anker
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
                    json.dumps(pre_json, indent=2, ensure_ascii=False),
                    encoding='utf-8'
                )
            else:
                logger.info(f"[FLDBImporter] Keine PDFs -> nur API-Daten")

        except Exception as e:
            logger.warning(f"[FLDBImporter] master_merger Fehler: {e}")

        # Post-Clean: Duplikate, Perioden, Firmennamen bereinigen
        try:
            from apps.cv_extractor.services.master_post_clean import master_post_cleaner
            pre_json = master_post_cleaner.clean(pre_json)
            n_proj = len(pre_json.get('extracted_data', {}).get('experience', []))
            logger.info(f"[FLDBImporter] post_clean: {n_proj} Projekte")
        except Exception as e:
            logger.warning(f"[FLDBImporter] post_clean Fehler: {e}")

        # Uebersetzung auf Deutsch (vor DB-Import)
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

        # UploadedPDF anlegen
        from apps.cv_extractor.models import UploadedPDF
        upload = UploadedPDF.objects.create(
            filename    = f"FL:{dir_name}",
            first_name  = first,
            last_name   = last,
            action_type = 'url_import',
            status      = 'processing',
        )

        # AID generieren
        from apps.cv_extractor.services.aid_generator import aid_generator
        from apps.cv_extractor.services.versioning    import version_manager
        version_info   = version_manager.get_next_version(
            first, last, target_directory=dir_name, action_type='new_version'
        )
        consultant_dir = version_info['consultant_dir']
        aid_info = aid_generator.generate_from_cv(
            pre_json['extracted_data'], first, last,
            target_directory=consultant_dir, action_type='new_version'
        )
        if not aid_info:
            upload.status = 'failed'
            upload.save(update_fields=['status'])
            return {'success': False, 'error': 'AID-Generierung fehlgeschlagen'}

        aid = aid_info['aid']
        pre_json['metadata']['aid']            = aid
        pre_json['metadata']['version']        = aid_info['version_string']
        pre_json['metadata']['consultant_dir'] = consultant_dir

        # Consultant + DB speichern
        from apps.cv_extractor.models import Consultant
        from apps.cv_extractor.enricher.extracted_to_db import extracted_to_db
        consultant, created = Consultant.objects.get_or_create(aid=aid)
        personal = pre_json['extracted_data'].get('personal', {})

        consultant.version              = aid_info['version_string']
        consultant.consultant_dir       = consultant_dir
        consultant.first_name           = first
        consultant.last_name            = last
        consultant.source_type          = 'url_import'
        consultant.headline             = meta.get('headline', '')
        consultant.birth_year           = personal.get('birth_year')
        consultant.nationality          = personal.get('nationality', '')
        consultant.email                = personal.get('email', '')
        consultant.phone                = personal.get('phone', '')
        consultant.location             = personal.get('location', '')
        consultant.availability         = personal.get('availability', '')
        # EDV seit: IMMER aus aeltestem Projekt berechnen
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

        # hourly_rate aus FL-API paymentInformation (Cents -> EUR)
        # Prioritaet: hourlyRateInCents -> dailyRateInCents / 8 -> None
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
        consultant = extracted_to_db.save(consultant, consultant.extracted_json_export)

        # Skill-Normalisierung
        try:
            tech_counter, experience_map = self._build_tech_counter_from_ram(
                pre_json['extracted_data'].get('experience', []), consultant
            )
            if tech_counter:
                from apps.cv_extractor.services.skill_normalizer import skill_normalizer
                normalized = skill_normalizer.normalize(
                    tech_counter, headline=meta.get('headline', '')
                )
                stats = skill_normalizer.save_to_db(consultant, normalized, experience_map)
                logger.info(f"  SkillNormalizer: +{stats['added']} Skills, "
                            f"{stats['updated']} aktualisiert")
            else:
                logger.info(f"  Keine Technologien — überspringe SkillNormalizer")
        except Exception as e:
            logger.warning(f"  SkillNormalizer Fehler: {e}")

        # HTML generieren
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

        # Extracted TXT speichern
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
            lines.extend(ed.get('focus_areas', []))
            lines.append("")
            lines.append("BRANCHEN:")
            lines.extend(ed.get('industries', []))
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
                    lines.append(f"    Technologien: {', '.join(techs[:10])}")
            lines.append("")
            lines.append("SKILLS:")
            for cat, items in ed.get('skills', {}).items():
                if items:
                    lines.append(f"  {cat}: {', '.join(items[:5])}")
            txt_content = '\n'.join(lines)
            txt_path.write_text(txt_content, encoding='utf-8')
            consultant.raw_text = txt_content
            consultant.save(update_fields=['raw_text', 'updated_at'])
            logger.info(f"  TXT: {txt_path}")
        except Exception as e:
            logger.warning(f"  TXT Fehler: {e}")

        # SearchEnricher
        try:
            from apps.cv_extractor.enricher.search_enricher import search_enricher
            master_json = consultant.extracted_json_export or {}
            master_json = search_enricher.enrich(consultant, master_json)
            consultant.extracted_json_export = master_json
            consultant.save(update_fields=['extracted_json_export', 'updated_at'])
            logger.info(f"  SearchEnricher: {aid}")
        except Exception as e:
            logger.warning(f"  SearchEnricher Fehler: {e}")

        # SelfLearning
        try:
            from apps.cv_extractor.enricher.self_learning_pipeline import self_learning_pipeline
            stats = self_learning_pipeline.process(
                consultant, consultant.extracted_json_export or {})
            logger.info(f"  SelfLearning: {stats}")
        except Exception as e:
            logger.warning(f"  SelfLearning Fehler: {e}")

        # UploadedPDF aktualisieren
        UploadedPDF.objects.filter(pk=upload.pk).update(
            status         = 'completed',
            aid            = aid,
            version        = aid_info['version_string'],
            consultant_dir = consultant_dir,
            consultant_id  = consultant.id,
        )

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

    def _build_tech_counter_from_ram(self, experience_list, consultant):
        """Tech-Counter aus experience_list."""
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

        logger.info(f"  Tech-Counter: {len(tech_counter)} einzigartige Technologien")
        return tech_counter, dict(experience_map)


fl_db_importer = FLDbImporter()
