"""
main_pipeline_controller.py — Universeller CV-Pipeline Controller

Orchestriert den kompletten Ablauf vollständig im RAM:
  PDF/DOCX → Spans → Gruppen → Labels → pre_json → PostProcessor → DB → HTML + TXT

Einzige Disk-Outputs:
  data/extracted/<dir>/<AID>.txt   (lesbares Profil)
  data/html_out/<dir>/<AID>.html   (HTML Qualifikationsprofil)

Verwendung:
  from apps.cv_extractor.services.main_pipeline_controller import main_pipeline_controller
  result = main_pipeline_controller.run(
      pdf_path   = 'data/url/fl/akbulut_akin/download/01_Akin-Akbulut.pdf',
      first_name = 'Akin',
      last_name  = 'Akbulut',
      dir_name   = 'akbulut_akin',
  )
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _span_get(span, key, default=None):
    """PDF liefert ExtractedSpan (Attribute), Word liefert dict — beides lesen."""
    if isinstance(span, dict):
        return span.get(key, default)
    return getattr(span, key, default)


def _normalize_spans(raw_spans) -> list:
    """Einheitliches Span-Dict für Detector/Labeler/Fill."""
    spans = []
    for s in raw_spans or []:
        text = _span_get(s, 'text', '') or ''
        if not str(text).strip():
            continue
        x0 = float(_span_get(s, 'x0', 0.0) or 0.0)
        x1 = float(_span_get(s, 'x1', 0.0) or 0.0)
        width = float(_span_get(s, 'width', 0.0) or 0.0)
        if width <= 0 and x1 > x0:
            width = x1 - x0
        size = float(_span_get(s, 'size', 12.0) or 12.0)
        spans.append({
            'page':      int(_span_get(s, 'page', 1) or 1),
            'y':         float(_span_get(s, 'y', 0) or 0),
            'x':         float(_span_get(s, 'x', 0) or 0),
            'size':      size,
            'sz':        size,
            'bold':      bool(_span_get(s, 'bold', False)),
            'italic':    bool(_span_get(s, 'italic', False)),
            'font':      str(_span_get(s, 'font', '') or ''),
            'text':      str(text),
            'width':     width,
            'column_id': int(_span_get(s, 'column_id', -1) if _span_get(s, 'column_id', -1) is not None else -1),
            'x0':        x0,
            'y0':        0.0,
            'x1':        x1,
            'y1':        0.0,
        })
    return spans


def _spans_to_aid_lines(spans) -> list:
    """
    Spans → Zeilen für AID-Regex (Schritt 1b).

    P0: gleiche gerundete Y = eine Zeile; verschiedene Y nie verkleben
        (vorher abs(diff)>3 merge bei Diff==3).
    P1: column_id in Sortierung und Zeilentrennung (Mehrspalter).
    """
    def _col_key(s):
        c = s.get('column_id', -1)
        try:
            c = int(c)
        except (TypeError, ValueError):
            c = -1
        # unbekannte Spalte nach bekannten, Lesereihenfolge col0→col1
        return c if c >= 0 else 99

    sorted_spans = sorted(
        spans or [],
        key=lambda s: (
            _col_key(s),
            int(s.get('page', 1) or 1),
            round(float(s.get('y', 0) or 0) / 3) * 3,
            float(s.get('x', 0) or 0),
        ),
    )
    lines_text = []
    last_y = None
    last_page = None
    last_col = None
    cur_line = []
    for s in sorted_spans:
        t = (s.get('text') or '').strip()
        if not t:
            continue
        pg = int(s.get('page', 1) or 1)
        y = round(float(s.get('y', 0) or 0) / 3) * 3
        col = _col_key(s)
        new_line = (
            last_page is None
            or pg != last_page
            or col != last_col
            or y != last_y
        )
        if new_line:
            if cur_line:
                lines_text.append(' '.join(cur_line))
            cur_line = [t]
            last_y = y
            last_page = pg
            last_col = col
        else:
            cur_line.append(t)
    if cur_line:
        lines_text.append(' '.join(cur_line))
    return lines_text


class MainPipelineController:

    def run(self, pdf_path: str, first_name: str, last_name: str,
            dir_name: str = None, consultant_type: str = "IT-Freelancer") -> dict:
        """
        Kompletter Pipeline-Durchlauf im RAM.
        Einzige Disk-Outputs: TXT in data/extracted/, HTML in data/html_out/
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            return {'success': False, 'error': f'Datei nicht gefunden: {pdf_path}'}

        if not dir_name:
            dir_name = f"{last_name.lower()}_{first_name.lower()}"

        logger.info(f"[MainPipeline] START: {first_name} {last_name} — {pdf_path.name}")

        # ── Schritt 1: PDF → Spans ─────────────────────────────────────────
        try:
            logger.info(f"[MainPipeline] Schritt 1: PDF → Spans")
            suffix = pdf_path.suffix.lower()
            if suffix == '.pdf':
                from apps.cv_extractor.services.main_pdf_extractor import PDFExtractor
                result = PDFExtractor().extract(str(pdf_path))
            elif suffix in ('.docx', '.doc'):
                from apps.cv_extractor.services.main_word_extractor import WordExtractor
                result = WordExtractor().extract(str(pdf_path))
            else:
                return {'success': False, 'error': f'Unbekanntes Format: {suffix}'}

            if not result.spans:
                return {'success': False, 'error': 'Keine Spans extrahiert'}

            spans = _normalize_spans(result.spans)
            if not spans:
                return {'success': False, 'error': 'Keine Spans extrahiert'}
            logger.info(f"[MainPipeline] Spans: {len(spans)}")
        except Exception as e:
            return {'success': False, 'error': f'Span-Extraktion: {e}'}

        # ── Schritt 1b: abcona Regex-Extraktor ────────────────────────────
        # Für abcona-Profile: Skills direkt aus PDF-Struktur mit korrekter
        # Kategorie extrahieren — Normalizer-LLM wird für Skills bypassed
        aid_skill_categories = {}  # {skill_name: category} aus PDF-Layout
        aid_extracted = {}         # {headline, focus_areas, industries, certifications, education}
        try:
            lines_text = _spans_to_aid_lines(spans)
            full_text = '\n'.join(lines_text)
            from apps.cv_extractor.extractors.aid_regex_extractor import (
                aid_regex_extractor,
                ABCONA_SIGNALS,
            )
            signal_hits = sum(1 for p in ABCONA_SIGNALS if p.search(full_text))
            is_aid = signal_hits >= 3
            logger.info(
                f"[MainPipeline] Schritt 1b: lines={len(lines_text)} chars={len(full_text)} "
                f"aid_signals={signal_hits}/5 is_aid={is_aid}"
            )
            if is_aid:
                logger.info(f"[MainPipeline] Schritt 1b: abcona-Profil erkannt → Fast-Path")
                # P2: erst Header strippen, dann Skills/Sektionen
                full_text_clean = aid_regex_extractor._strip_page_headers(full_text)
                skill_ablage = aid_regex_extractor._extract_skill_tables(full_text_clean)
                dup_skills = 0
                for item in skill_ablage:
                    if not (isinstance(item, dict) and item.get('name') and item.get('category')):
                        continue
                    name = item['name']
                    cat = item['category']
                    if name in aid_skill_categories and aid_skill_categories[name] != cat:
                        dup_skills += 1
                        logger.info(
                            f"[MainPipeline] Schritt 1b: Skill-Duplikat '{name}': "
                            f"{aid_skill_categories[name]} → {cat}"
                        )
                    aid_skill_categories[name] = cat
                logger.info(
                    f"[MainPipeline] Schritt 1b: {len(aid_skill_categories)} Skills vorkategorisiert"
                    + (f" ({dup_skills} Duplikat-Überschreibungen)" if dup_skills else "")
                )
                aid_extracted['headline']       = aid_regex_extractor._extract_headline(full_text_clean)
                aid_extracted['focus_areas']    = aid_regex_extractor._extract_fachbereiche(full_text_clean)
                aid_extracted['industries']     = aid_regex_extractor._extract_branchen(full_text_clean)
                aid_extracted['certifications'] = aid_regex_extractor._extract_zertifikate(full_text_clean)
                aid_extracted['education']      = (
                    list(aid_regex_extractor._extract_ausbildung(full_text_clean) or [])
                    + list(aid_regex_extractor._extract_schulungen(full_text_clean) or [])
                )
                # Format-A: Skills aus Projekten nachziehen wenn Tabellen fehlen
                if not aid_skill_categories:
                    projekte = aid_regex_extractor._extract_projekte(full_text_clean)
                    harvested = aid_regex_extractor._harvest_skills_from_projects(projekte)
                    for item in harvested:
                        if item.get('name') and item.get('category'):
                            aid_skill_categories[item['name']] = item['category']
                    if harvested:
                        logger.info(
                            f"[MainPipeline] Schritt 1b: {len(harvested)} Skills aus Projekten geerntet"
                        )
                logger.info(
                    f"[MainPipeline] Schritt 1b: headline={bool(aid_extracted.get('headline'))} | "
                    f"fachbereiche={len(aid_extracted.get('focus_areas') or [])} | "
                    f"branchen={len(aid_extracted.get('industries') or [])} | "
                    f"zertifikate={len(aid_extracted.get('certifications') or [])} | "
                    f"ausbildung={len(aid_extracted.get('education') or [])}"
                )
            else:
                logger.info(f"[MainPipeline] Schritt 1b: kein abcona-Profil → normale Pipeline")
        except Exception as e:
            # P4: kein halber Fast-Path in Group/Label/Fill
            aid_skill_categories = {}
            aid_extracted = {}
            logger.warning(f"[MainPipeline] Schritt 1b Fehler (nicht kritisch, Fast-Path verworfen): {e}")

        # ── Schritt 2: Spans → Gruppen ─────────────────────────────────────
        try:
            logger.info(f"[MainPipeline] Schritt 2: Spans → Gruppen")
            from apps.cv_extractor.services.main_pipeline_detector import MasterDetector
            det = MasterDetector()

            lines = []
            for s in spans:
                lines.append({
                    'page':      int(s.get('page', 1)),
                    'y':         float(s.get('y', 0)),
                    'x':         float(s.get('x', 0)),
                    'sz':        float(s.get('sz', 12.0)),
                    'bold':      bool(s.get('bold', False)),
                    'italic':    bool(s.get('italic', False)),
                    'font':      str(s.get('font', '')),
                    'text':      str(s.get('text', '')),
                    'width':     float(s.get('width', 0)),
                    'column_id': int(s.get('column_id', -1)),
                    'x0': 0.0, 'y0': 0.0, 'x1': 0.0, 'y1': 0.0, 'ox': 0.0, 'oy': 0.0,
                })

            lines.sort(key=lambda l: (
                l['column_id'] if l['column_id'] >= 0 else 99,
                l['page'], l['y']
            ))

            blocks  = det.format_blocks(det.split_blocks(lines))
            cv_info = det.detect_section_headers(blocks)
            gruppen = det.group_blocks(blocks, cv_info=cv_info)
            gruppen = det.split_by_format(gruppen, blocks)
            gruppen = det.quality_check(gruppen, blocks)
            gruppen = det.relabel_from_content(gruppen, blocks)

            logger.info(f"[MainPipeline] Gruppen: {len(gruppen)}, Blöcke: {len(blocks)}")
        except Exception as e:
            import traceback
            return {'success': False, 'error': f'Gruppierung: {e}\n{traceback.format_exc()}'}

        # ── Schritt 3: Gruppen → Labels ────────────────────────────────────
        try:
            logger.info(f"[MainPipeline] Schritt 3: Labels")
            from apps.cv_extractor.services.main_labeler import main_labeler
            labeled = main_labeler.label(gruppen, blocks)
            n_proj  = len([l for l in labeled if l['label'] == 'PROJECT'])
            n_skill = len([l for l in labeled if l['label'] == 'SKILLS'])
            logger.info(f"[MainPipeline] {n_proj} Projekte, {n_skill} Skill-Blöcke")
        except Exception as e:
            import traceback
            return {'success': False, 'error': f'Labeling: {e}\n{traceback.format_exc()}'}

        # ── Schritt 4: Labels → pre_json ───────────────────────────────────
        try:
            logger.info(f"[MainPipeline] Schritt 4: pre_json")
            from apps.cv_extractor.extractors.main_base_extractor import labeled_to_prejson
            block_by_nr = {b['index']: b for b in blocks}
            pre_json = labeled_to_prejson(labeled, gruppen, block_by_nr, consultant_type, aid_extracted=aid_extracted)
            pre_json['metadata']['first_name'] = first_name
            pre_json['metadata']['last_name']  = last_name

            n_exp    = len(pre_json.get('extracted_data', {}).get('experience', []))
            n_ablage = len(pre_json.get('extracted_data', {}).get('skill_ablage', []))
            logger.info(f"[MainPipeline] pre_json: {n_exp} Projekte, {n_ablage} skill_ablage")
        except Exception as e:
            import traceback
            return {'success': False, 'error': f'Extraktion: {e}\n{traceback.format_exc()}'}

        # ── Schritt 4b: Post-Processor ─────────────────────────────────────
        try:
            logger.info(f"[MainPipeline] Schritt 4b: Post-Processor")
            from apps.cv_extractor.services.main_post_processor import main_post_processor
            pre_json = main_post_processor.clean(pre_json, str(pdf_path))
            audit    = pre_json.get('audit', {}).get('post_processor', {})
            logger.info(
                f"[MainPipeline] Post-Processor: "
                f"coverage={audit.get('coverage_percent', 0):.1f}% | "
                f"fixes={len(audit.get('fixes', []))} | "
                f"auto_skills={audit.get('auto_added_skills', 0)}"
            )
            # skill_ablage nach Post-Processor aktualisieren
            n_ablage = len(pre_json.get('extracted_data', {}).get('skill_ablage', []))
            logger.info(f"[MainPipeline] skill_ablage nach PostProcessor: {n_ablage}")
        except Exception as e:
            logger.warning(f"[MainPipeline] Post-Processor Fehler (nicht kritisch): {e}")

        # ── Schritt 5: pre_json → DB ───────────────────────────────────────
        try:
            logger.info(f"[MainPipeline] Schritt 5: DB-Import")
            from apps.cv_extractor.services.main_db_importer import main_db_importer
            result = main_db_importer.import_from_prejson(
                pre_json            = pre_json,
                dir_name            = dir_name,
                first_name_override = first_name,
                last_name_override  = last_name,
                aid_skill_categories = aid_skill_categories,
                source_filename     = pdf_path.name,
            )
            if not result.get('success'):
                return {'success': False, 'error': result.get('error', 'DB-Import fehlgeschlagen')}

            logger.info(f"[MainPipeline] FERTIG: {result['aid']}")
            return result

        except Exception as e:
            import traceback
            return {'success': False, 'error': f'DB-Import: {e}\n{traceback.format_exc()}'}


main_pipeline_controller = MainPipelineController()
