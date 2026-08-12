"""
services/url_importer.py
URL → strukturiertes Verzeichnis → profil_pre_json.json

Pipeline:
  1. fetch()      → profil.json
  2. download()   → download/*.pdf|doc|docx
  3. extract()    → extract/*_yx.txt
  4. keywords()   → analysis/keywords.json
  5. match()      → analysis/matches.json
  6. checksum()   → analysis/checksum.json
  7. pre_json()   → profil_pre_json.json

NEU (Schritt 7b):
  fl_doc_classifier → doc_type pro Datei
  fl_doc_extractor  → Spezialist-LLM pro Nicht-CV-Datei
  Ergebnis wird ins profil_pre_json.json eingemergt
"""

import os, json, re, time, logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PLATFORM_MAP = {
    'freelancermap.de': 'fl',
    'xing.com':         'xi',
    'linkedin.com':     'li',
    'gulp.de':          'gu',
}

BASE_DIR = Path('data/url')


class URLImporter:

    def __init__(self):
        self.log_entries = []

    def run(self, url: str, cookies: dict = None, **kwargs) -> dict:
        start = time.time()
        self._log(f"START: {url}")
        platform = self._detect_platform(url)
        self._log(f"Plattform: {platform}")
        if platform == 'fl':
            result = self._run_freelancermap(url, cookies, **kwargs)
        else:
            result = {'error': f'Plattform {platform} noch nicht implementiert'}
        result['duration'] = round(time.time() - start, 2)
        self._log(f"DONE in {result['duration']}s")
        return result

    def _run_freelancermap(self, url: str, cookies: dict = None, **kwargs) -> dict:
        import requests
        from bs4 import BeautifulSoup
        import warnings
        warnings.filterwarnings('ignore')

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'de-DE,de;q=0.9',
        }

        # ── 0. COOKIES laden ─────────────────────────────────────────────────
        if not cookies:
            cookie_file = Path('data/url/fl/.session_cookies.json')
            if cookie_file.exists():
                try:
                    saved = json.loads(cookie_file.read_text())
                    cookies = {c['name']: c['value']
                               for c in saved.get('cookies', [])}
                    self._log(f"Session-Cookies geladen: {list(cookies.keys())}")
                except Exception as e:
                    self._log(f"Cookie-Datei Fehler: {e}")

        session = requests.Session()
        session.verify = False
        if cookies:
            for k, v in cookies.items():
                session.cookies.set(k, v, domain='www.freelancermap.de')

        # ── 1. FETCH ─────────────────────────────────────────────────────────
        self._log("FETCH profil.json...")
        resp = session.get(url, headers=headers, timeout=30)
        soup = BeautifulSoup(resp.text, 'html.parser')

        script = soup.find('script', {'data-component-name': 'ProfileShow'})
        if not script:
            return {'error': 'ProfileShow JSON nicht gefunden'}

        profile = json.loads(script.string).get('profile', {})

        person = {}
        address = {}
        for s in soup.find_all('script', type='application/ld+json'):
            try:
                d = json.loads(s.string)
                if d.get('@type') == 'Person':          person  = d
                elif d.get('@type') == 'PostalAddress': address = d
            except: pass

        first_name = person.get('givenName', '')
        last_name  = person.get('familyName', '')

        force_dir   = kwargs.get('force_dir',  '') or ''
        force_first = kwargs.get('first_name', '') or ''
        force_last  = kwargs.get('last_name',  '') or ''

        fl_id = ''
        try:
            sc = soup.find('script', {'data-component-name': 'ProfileShow'})
            if sc:
                fl_id = str(json.loads(sc.string).get('profile', {}).get('id', ''))
        except: pass

        if force_first and force_last:
            first_name, last_name = force_first, force_last
        elif not first_name or not last_name:
            if force_dir:
                first_name = f'FL-{fl_id}' if fl_id else 'FL'
                last_name  = force_dir
            else:
                provisional_dir = f'fl-{fl_id}' if fl_id else 'fl-anonym'
                return {
                    'name_missing':    True,
                    'fl_id':           fl_id,
                    'provisional_dir': provisional_dir,
                    'url':             url,
                }

        dir_name = force_dir if force_dir else f"{last_name.lower()}_{first_name.lower()}"
        base     = BASE_DIR / 'fl' / dir_name
        dl_dir   = base / 'download'
        ex_dir   = base / 'extract'
        an_dir   = base / 'analysis'
        for d in [base, dl_dir, ex_dir, an_dir]:
            d.mkdir(parents=True, exist_ok=True)

        profile_path = base / 'profil.json'
        with open(profile_path, 'w', encoding='utf-8') as f:
            json.dump({
                'url':        url,
                'fetched_at': datetime.now().isoformat(),
                'person':     person,
                'address':    address,
                'profile':    profile,
            }, f, indent=2, ensure_ascii=False)
        self._log(f"profil.json gespeichert: {profile_path}")

        # ── 2. DOWNLOAD PDFs ─────────────────────────────────────────────────
        self._log("DOWNLOAD PDFs...")
        downloaded = []
        attachments = profile.get('attachments', [])

        if not cookies:
            cookie_file = Path('data/url/fl/.session_cookies.json')
            if cookie_file.exists():
                try:
                    saved = json.loads(cookie_file.read_text())
                    cookies = {c['name']: c['value']
                               for c in saved.get('cookies', [])}
                except Exception as e:
                    self._log(f"Cookie-Datei Fehler: {e}")

        if attachments and cookies:
            session = requests.Session()
            session.verify = False
            for k, v in cookies.items():
                session.cookies.set(k, v, domain='www.freelancermap.de')

            for i, att in enumerate(attachments, 1):
                suffix = (att.get('suffix') or '').lower()
                if suffix not in ('pdf', 'doc', 'docx'):
                    continue
                dl_url   = 'https://www.freelancermap.de' + att.get('downloadUrl', '')
                filename = f"{i:02d}_{att.get('keyName','unknown')}.{suffix}"
                path     = dl_dir / filename
                try:
                    r  = session.get(dl_url, headers=headers, timeout=60)
                    ct = r.headers.get('Content-Type', '')
                    if len(r.content) > 1000 and 'html' not in ct.lower():
                        with open(path, 'wb') as f:
                            f.write(r.content)
                        downloaded.append({
                            'filename': filename,
                            'path':     str(path),
                            'size':     len(r.content),
                            'desc':     att.get('description', ''),
                        })
                        self._log(f"  ✅ {filename} ({len(r.content)//1024} KB)")
                    else:
                        self._log(f"  ❌ {filename}: Login nötig ({ct})")
                except Exception as e:
                    self._log(f"  ❌ {filename}: {e}")
        elif attachments:
            self._log(f"  ⚠️  {len(attachments)} Attachments gefunden aber kein Cookie")

        # ── 3. EXTRACT ───────────────────────────────────────────────────────
        self._log("EXTRACT yx.txt...")
        extracted = []

        from apps.cv_extractor.services.pdf_extractor  import PDFExtractor
        from apps.cv_extractor.services.word_extractor import WordExtractor

        pdf_extractor_svc  = PDFExtractor()
        word_extractor_svc = WordExtractor()

        for dl in downloaded:
            path   = Path(dl['path'])
            suffix = path.suffix.lower()
            yx_name = path.stem + '_yx.txt'
            yx_path = ex_dir / yx_name
            try:
                if suffix == '.pdf':
                    res = pdf_extractor_svc.extract(str(path))
                elif suffix in ('.doc', '.docx'):
                    res = word_extractor_svc.extract(str(path))
                else:
                    continue

                if res.spans:
                    with open(yx_path, 'w', encoding='utf-8') as f:
                        for s in res.spans:
                            b    = 'B' if s.bold   else '.'
                            i    = 'I' if s.italic else '.'
                            font = (getattr(s, 'font', '') or '').replace('|', '_')[:30]
                            f.write(
                                f"p{s.page:02d}"
                                f"|y={s.y:5}|x={s.x:4}"
                                f"|sz={s.size:5.1f}"
                                f"|{b}{i}"
                                f"|fn={font}"
                                f"|x0={getattr(s,'x0',0.0):7.1f}|y0={getattr(s,'y0',0.0):7.1f}"
                                f"|x1={getattr(s,'x1',0.0):7.1f}|y1={getattr(s,'y1',0.0):7.1f}"
                                f"|ox={getattr(s,'origin_x',0.0):7.1f}|oy={getattr(s,'origin_y',0.0):7.1f}"
                                f"|{s.text}\n"
                            )
                    char_count = sum(len(s.text) for s in res.spans)
                    extracted.append({
                        'source':     dl['filename'],
                        'yx_file':    yx_name,
                        'spans':      len(res.spans),
                        'pages':      res.page_count,
                        'char_count': char_count,
                    })
                    self._log(f"  ✅ {yx_name}: {len(res.spans)} Spans, {char_count} Zeichen")
                else:
                    self._log(f"  ⚠️  {yx_name}: 0 Spans (OCR nötig?)")
            except Exception as e:
                self._log(f"  ❌ {path.name}: {e}")

        # ── 4. KEYWORDS ──────────────────────────────────────────────────────
        self._log("KEYWORDS extrahieren...")
        keywords = self._extract_keywords_from_profile(profile, soup)
        with open(an_dir / 'keywords.json', 'w', encoding='utf-8') as f:
            json.dump({'count': len(keywords), 'keywords': sorted(keywords)},
                      f, indent=2, ensure_ascii=False)
        self._log(f"  {len(keywords)} Keywords")

        # ── 5. MATCH ─────────────────────────────────────────────────────────
        self._log("MATCH Keywords gegen yx.txt...")
        matches_all = {}
        for ext in extracted:
            yx_path = ex_dir / ext['yx_file']
            if not yx_path.exists():
                continue
            lines     = open(yx_path, encoding='utf-8').readlines()
            matched   = {}
            unmatched = []
            for kw in sorted(keywords):
                kw_lower = kw.lower()
                hits = []
                for line in lines:
                    parts = line.split('|')
                    if len(parts) >= 6:
                        text = '|'.join(parts[5:]).strip().lower()
                        if kw_lower in text:
                            hits.append(parts[0])
                if hits:
                    matched[kw] = hits[:3]
                else:
                    unmatched.append(kw)
            matches_all[ext['source']] = {
                'matched':          len(matched),
                'unmatched':        len(unmatched),
                'total':            len(keywords),
                'coverage_percent': round(len(matched) / max(len(keywords), 1) * 100, 1),
                'matched_keywords': matched,
                'unmatched':        unmatched,
            }
            self._log(f"  {ext['source']}: {len(matched)}/{len(keywords)} Keywords "
                      f"({matches_all[ext['source']]['coverage_percent']}%)")
        with open(an_dir / 'matches.json', 'w', encoding='utf-8') as f:
            json.dump(matches_all, f, indent=2, ensure_ascii=False)

        # ── 6. CHECKSUM ──────────────────────────────────────────────────────
        checksum = {
            'fetched_at':  datetime.now().isoformat(),
            'url':         url,
            'name':        f"{first_name} {last_name}",
            'attachments': len(attachments),
            'downloaded':  len(downloaded),
            'extracted':   len(extracted),
            'keywords':    len(keywords),
            'files':       extracted,
            'coverage':    {k: v['coverage_percent'] for k, v in matches_all.items()},
        }
        with open(an_dir / 'checksum.json', 'w', encoding='utf-8') as f:
            json.dump(checksum, f, indent=2, ensure_ascii=False)

        # ── 7. PRE_JSON aus profil.json (API) ────────────────────────────────
        self._log("PRE_JSON bauen (aus API)...")
        profil_pre_json = self._build_pre_json(
            profile, person, address, url, first_name, last_name
        )

        # ── 7b. DOKUMENT-CLASSIFIER + SPEZIALIST-EXTRAKTOREN ─────────────────
        # NEU: ersetzt den alten 20%-Coverage-Filter
        # Jede Datei wird klassifiziert:
        #   CV          → Master Pipeline (wie bisher)
        #   CERTIFICATE → cert_extractor → certifications[]
        #   REFERENCE   → ref_extractor  → experience[]
        #   EDUCATION   → edu_extractor  → education[]
        #   OTHER       → other_extractor→ other (string)
        #   COVERLETTER → skip
        self._log("DOKUMENT-CLASSIFIER starten...")

        pdf_pre_json        = None   # aus CV-Dateien via Master Pipeline
        classifier_results  = {}     # doc_type pro Dateiname
        extra_certifications = []    # aus CERTIFICATE-Dateien
        extra_experience     = []    # aus REFERENCE-Dateien
        extra_education      = []    # aus EDUCATION-Dateien
        extra_other_parts    = []    # aus OTHER-Dateien

        try:
            from apps.cv_extractor.services.fl_doc_classifier import fl_doc_classifier
            from apps.cv_extractor.services.fl_doc_extractor  import fl_doc_extractor
        except ImportError as e:
            self._log(f"  ⚠️  fl_doc_classifier/extractor Import fehlgeschlagen: {e}")
            fl_doc_classifier = None
            fl_doc_extractor  = None

        all_files = sorted(dl_dir.glob('*.pdf')) + \
                    sorted(dl_dir.glob('*.docx')) + \
                    sorted(dl_dir.glob('*.doc'))

        cv_files = []   # nur CV-Dateien für Master Pipeline

        for file_path in all_files:
            fname = file_path.name
            suffix = file_path.suffix.lower()
            self._log(f"  Klassifiziere: {fname}")

            # Spans laden (aus yx.txt wenn vorhanden, sonst neu extrahieren)
            plain_text = ''
            spans_list = []
            yx_path    = ex_dir / (file_path.stem + '_yx.txt')

            if yx_path.exists():
                # yx.txt → plain_text (schnell, kein LLM)
                try:
                    lines = yx_path.read_text(encoding='utf-8').splitlines()
                    texts = []
                    for line in lines:
                        if line.startswith('#') or not line.strip():
                            continue
                        parts = line.split('|')
                        # yx.txt Format: p|y|x|sz|bi|fn|x0|y0|x1|y1|ox|oy|text
                        if len(parts) >= 13:
                            texts.append(parts[12].strip())
                        elif len(parts) >= 6:
                            texts.append(parts[-1].strip())
                    plain_text = '\n'.join(t for t in texts if t)
                except Exception as e:
                    self._log(f"    yx.txt lesen fehlgeschlagen: {e}")

            if not plain_text:
                # Direkt extrahieren (kein yx.txt vorhanden)
                try:
                    if suffix == '.pdf':
                        res = pdf_extractor_svc.extract(str(file_path))
                        spans_list = res.spans or []
                    elif suffix in ('.docx', '.doc'):
                        from apps.cv_extractor.services.master_word_extractor \
                            import master_word_extractor
                        res = master_word_extractor.extract(str(file_path))
                        if res.ok:
                            plain_text = res.plain_text
                    if spans_list:
                        plain_text = '\n'.join(
                            (s.text or '').strip()
                            for s in spans_list if s.text
                        )
                except Exception as e:
                    self._log(f"    Extraktion fehlgeschlagen: {e}")

            if not plain_text:
                self._log(f"    ⚠️  {fname}: kein Text → skip")
                continue

            # Klassifizieren
            if fl_doc_classifier:
                try:
                    cls_result = fl_doc_classifier.classify(
                        plain_text = plain_text,
                        first_800  = plain_text[:800],
                        headings   = [],
                        span_count = len(plain_text.splitlines()),
                        page_count = 1,
                        char_count = len(plain_text),
                        filename   = fname,
                    )
                    doc_type = cls_result.doc_type
                    classifier_results[fname] = {
                        'doc_type':   doc_type,
                        'confidence': cls_result.confidence,
                        'skip':       cls_result.skip,
                        'llm_used':   cls_result.llm_used,
                    }
                    self._log(
                        f"    → {doc_type} "
                        f"(conf={cls_result.confidence:.2f}"
                        f"{', LLM' if cls_result.llm_used else ''})"
                    )
                except Exception as e:
                    self._log(f"    Classifier Fehler: {e}")
                    doc_type = 'CV'   # Fallback: als CV behandeln
            else:
                doc_type = 'CV'

            # Routing nach doc_type
            if doc_type == 'CV':
                cv_files.append(file_path)

            elif doc_type == 'COVERLETTER':
                self._log(f"    → skip (Anschreiben)")

            elif doc_type in ('CERTIFICATE', 'REFERENCE', 'EDUCATION', 'OTHER') \
                    and fl_doc_extractor:
                try:
                    ext_result = fl_doc_extractor.extract(
                        doc_type   = doc_type,
                        plain_text = plain_text,
                        filename   = fname,
                    )
                    if ext_result and ext_result.ok:
                        if doc_type == 'CERTIFICATE':
                            data = ext_result.data
                            if isinstance(data, list):
                                extra_certifications.extend(data)
                            elif isinstance(data, dict):
                                extra_certifications.append(data)
                            self._log(
                                f"    ✅ {len(extra_certifications)} Zertifikat(e) extrahiert"
                            )
                        elif doc_type == 'REFERENCE':
                            data = ext_result.data
                            if isinstance(data, dict):
                                extra_experience.append(data)
                            elif isinstance(data, list):
                                extra_experience.extend(data)
                            self._log(
                                f"    ✅ Referenz extrahiert: {data.get('company','?') if isinstance(data,dict) else ''}"
                            )
                        elif doc_type == 'EDUCATION':
                            data = ext_result.data
                            if isinstance(data, list):
                                extra_education.extend(data)
                            elif isinstance(data, dict):
                                extra_education.append(data)
                            self._log(
                                f"    ✅ {len(extra_education)} Bildungseintrag/einträge extrahiert"
                            )
                        elif doc_type == 'OTHER':
                            if ext_result.data:
                                extra_other_parts.append(str(ext_result.data))
                            self._log(f"    ✅ OTHER gespeichert")
                    else:
                        self._log(
                            f"    ⚠️  Extraktion fehlgeschlagen: "
                            f"{ext_result.error if ext_result else 'None'}"
                        )
                except Exception as e:
                    self._log(f"    Extractor Fehler ({doc_type}): {e}")

        # Classifier-Ergebnis speichern
        with open(an_dir / 'classifier.json', 'w', encoding='utf-8') as f:
            json.dump(classifier_results, f, indent=2, ensure_ascii=False)
        self._log(
            f"Classifier: {len(cv_files)} CV | "
            f"{len(extra_certifications)} Zertifikate | "
            f"{len(extra_experience)} Referenzen | "
            f"{len(extra_education)} Bildung | "
            f"{len(extra_other_parts)} Sonstiges"
        )

        # ── 7c. MASTER PIPELINE nur für CV-Dateien ───────────────────────────
        if cv_files:
            self._log(f"Master Pipeline starten ({len(cv_files)} CV-Datei(en))...")
            try:
                import copy as _copy

                all_pre = []
                for file_path in cv_files:
                    suffix = file_path.suffix.lower()
                    if suffix == '.pdf':
                        res = pdf_extractor_svc.extract(str(file_path))
                    elif suffix in ('.doc', '.docx'):
                        res = word_extractor_svc.extract(str(file_path))
                    else:
                        continue

                    if not res.spans:
                        self._log(f"  ⚠️ {file_path.name}: 0 Spans")
                        continue

                    spans = [
                        {
                            'page':      s.page,
                            'y':         int(s.y),
                            'x':         int(s.x),
                            'size':      s.size,
                            'bold':      s.bold,
                            'italic':    s.italic,
                            'font':      getattr(s, 'font', ''),
                            'text':      s.text,
                            'width':     float(getattr(s, 'x1', 0) or 0)
                                         - float(getattr(s, 'x0', 0) or 0),
                            'column_id': getattr(s, 'column_id', -1),
                        }
                        for s in res.spans if s.text and s.text.strip()
                    ]
                    self._log(f"  {file_path.name}: {len(spans)} Spans im RAM")
                    pj = run_master_pipeline_from_spans(spans, first_name, last_name)
                    all_pre.append(pj)

                # ── Multi-CV Merge: jedes CV einzeln speichern + intelligent mergen ──
                for i, pj in enumerate(all_pre, 1):
                    out = base / f'pdf_pre_json_{i}.json'
                    with open(out, 'w', encoding='utf-8') as f:
                        json.dump(pj, f, indent=2, ensure_ascii=False)
                    self._log(f"  pdf_pre_json_{i}.json gespeichert ({len(pj['extracted_data']['experience'])} Projekte)")

                if all_pre:
                    # Alle Projekte aus allen PDFs zusammenwerfen (kein Merge, kein Dedup)
                    # Der echte Merge laeuft in url_fl_db_importer mit allen pdf_pre_json_*.json
                    import copy
                    pdf_pre_json = copy.deepcopy(all_pre[0])
                    all_exps = []
                    for pj in all_pre:
                        all_exps.extend(pj.get('extracted_data', {}).get('experience', []))
                    pdf_pre_json['extracted_data']['experience'] = all_exps

                if pdf_pre_json:
                    self._log(
                        f"Master Pipeline: "
                        f"{len(pdf_pre_json['extracted_data']['experience'])} Projekte"
                    )
                    pdf_pre_json_path = base / 'pdf_pre_json.json'
                    with open(pdf_pre_json_path, 'w', encoding='utf-8') as f:
                        json.dump(pdf_pre_json, f, indent=2, ensure_ascii=False)
                    self._log(f"pdf_pre_json.json gespeichert")

            except Exception as e:
                self._log(f"Master Pipeline Fehler: {e}")
                logger.warning(f"[URLImporter] Master Pipeline Fehler: {e}")
                import traceback; traceback.print_exc()

        # ── 7d. MERGE + NORMALIZE ─────────────────────────────────────────────
        if pdf_pre_json:
            self._log("Merge profil.json + PDF...")
            merged = merge_profil_and_pdf(profil_pre_json, pdf_pre_json)
            self._log("Normalize...")
            final_pre_json = normalize_pre_json(merged)
            self._log(f"Final: {len(final_pre_json['extracted_data']['experience'])} Projekte")
        else:
            self._log("Kein CV-PDF → nur API pre_json")
            final_pre_json = profil_pre_json

        # ── 7e. CLASSIFIER-ERGEBNISSE EINSORTIEREN ────────────────────────────
        # Zertifikate aus Zertifikat-PDFs → certifications[]
        if extra_certifications:
            existing_certs = final_pre_json['extracted_data'].get('certifications', [])
            seen = {c.get('name', '').lower() for c in existing_certs}
            added = 0
            for cert in extra_certifications:
                name = cert.get('name', '').lower()
                if name and name not in seen:
                    existing_certs.append(cert)
                    seen.add(name)
                    added += 1
            final_pre_json['extracted_data']['certifications'] = existing_certs
            self._log(f"  +{added} Zertifikate aus PDF-Dokumenten")

        # Referenzen aus Arbeitszeugnis-PDFs → experience[]
        if extra_experience:
            existing_exp = final_pre_json['extracted_data'].get('experience', [])
            seen_periods = {e.get('period', '') for e in existing_exp}
            added = 0
            for exp in extra_experience:
                period = exp.get('period', '')
                if period and period in seen_periods:
                    # Zeitraum bereits vorhanden → technologies ergänzen
                    for ex in existing_exp:
                        if ex.get('period') == period:
                            ref_techs = exp.get('technologies', [])
                            if ref_techs and not ex.get('technologies'):
                                ex['technologies'] = ref_techs
                            break
                else:
                    existing_exp.append(exp)
                    seen_periods.add(period)
                    added += 1
            final_pre_json['extracted_data']['experience'] = existing_exp
            self._log(f"  +{added} Referenz-Einträge aus PDF-Dokumenten")

        # Bildung aus Schulungsnachweisen → education[]
        if extra_education:
            existing_edu = final_pre_json['extracted_data'].get('education', [])
            seen_degrees = {e.get('degree', '').lower() for e in existing_edu}
            added = 0
            for edu in extra_education:
                degree = edu.get('degree', '').lower()
                if degree and degree not in seen_degrees:
                    existing_edu.append(edu)
                    seen_degrees.add(degree)
                    added += 1
            final_pre_json['extracted_data']['education'] = existing_edu
            self._log(f"  +{added} Bildungseinträge aus PDF-Dokumenten")

        # Sonstiges → other (string, angehängt)
        if extra_other_parts:
            existing_other = final_pre_json['extracted_data'].get('other', '') or ''
            new_parts = '\n'.join(extra_other_parts)
            if existing_other:
                final_pre_json['extracted_data']['other'] = (
                    existing_other + '\n' + new_parts
                )
            else:
                final_pre_json['extracted_data']['other'] = new_parts
            self._log(f"  +{len(extra_other_parts)} Sonstiges-Einträge")

        # Audit ergänzen
        final_pre_json['audit']['classifier'] = classifier_results
        final_pre_json['audit']['classifier_at'] = datetime.now().isoformat()

        # ── 8. SPEICHERN ──────────────────────────────────────────────────────
        pre_json_path = base / 'profil_pre_json.json'
        with open(pre_json_path, 'w', encoding='utf-8') as f:
            json.dump(final_pre_json, f, indent=2, ensure_ascii=False)

        n_proj  = len(final_pre_json['extracted_data']['experience'])
        n_cert  = len(final_pre_json['extracted_data']['certifications'])
        n_edu   = len(final_pre_json['extracted_data']['education'])
        self._log(
            f"profil_pre_json.json gespeichert "
            f"({n_proj} Projekte, {n_cert} Zertifikate, {n_edu} Bildung)"
        )

        with open(base / 'import.log', 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.log_entries))

        return {
            'status':        'ok',
            'name':          f"{first_name} {last_name}",
            'dir':           str(base),
            'downloaded':    len(downloaded),
            'extracted':     len(extracted),
            'keywords':      len(keywords),
            'coverage':      checksum['coverage'],
            'pre_json_path': str(pre_json_path),
            'classifier':    classifier_results,
        }

    def _extract_keywords_from_profile(self, profile: dict, soup) -> set:
        from bs4 import BeautifulSoup as BS
        keywords = set()
        STOPWORDS = {
            'und','die','der','das','mit','von','für','bei','aus','ist',
            'eine','einen','einer','auch','sich','auf','nicht','aber',
            'oder','über','nach','unter','sowie','durch','werden','haben',
            'wird','kann','dass','dies','beim','dem','den','des','ein',
        }
        def add(text):
            if text and len(text.strip()) > 2:
                keywords.add(text.strip())
        for c in profile.get('sortedSubCategories', []):
            add(c.get('name', ''))
        skills_html = profile.get('skills', '') or ''
        if skills_html:
            s2 = BS(skills_html, 'html.parser')
            for li in s2.find_all('li'):
                add(li.get_text(' ', strip=True))
            for strong in s2.find_all('strong'):
                add(strong.get_text(' ', strip=True))
        for ref in profile.get('references', []):
            add(ref.get('position', ''))
            add(ref.get('company', ''))
            desc = BS(ref.get('description', '') or '', 'html.parser')
            for li in desc.find_all('li'):
                add(li.get_text(' ', strip=True))
        for cert in profile.get('certificates', []):
            add(cert.get('name', ''))
            add(cert.get('issuingOffice', ''))
        about = profile.get('aboutMe', '') or ''
        for w in re.findall(r'\b[A-ZÄÖÜa-zäöü][a-zäöüA-ZÄÖÜ]{4,}\b', about):
            if w.lower() not in STOPWORDS:
                keywords.add(w)
        return keywords

    def _build_pre_json(self, profile, person, address, url,
                        first_name, last_name) -> dict:
        from bs4 import BeautifulSoup as BS

        def fmt_date(d):
            try:
                from datetime import datetime as DT
                return DT.fromisoformat(
                    d.replace('Z', '+00:00')).strftime('%m/%Y')
            except: return ''

        def html_to_list(html):
            if not html: return []
            s = BS(html, 'html.parser')
            items = []
            for li in s.find_all('li'):
                t = li.get_text(' ', strip=True)
                if t and len(t) > 1: items.append(t)
            if not items:
                for tag in s.find_all(['em', 'strong', 'p']):
                    t = tag.get_text(' ', strip=True)
                    if t and len(t) > 2: items.append(t)
            return list(dict.fromkeys(items))

        BRANCHE = {
            'consumer_goods_and_retail':           'Konsumgüter und Handel',
            'industry_and_mechanical_engineering': 'Industrie und Maschinenbau',
            'banking_and_finance':                 'Banken und Finanzen',
            'it_and_software':                     'IT und Software',
            'healthcare':                          'Gesundheitswesen',
            'automotive':                          'Automotive',
            'energy':                              'Energie',
            'insurance':                           'Versicherungen',
            'telecommunications':                  'Telekommunikation',
            'public_sector':                       'Öffentlicher Dienst',
            'logistics':                           'Logistik',
            'transport_and_logistics':             'Transport und Logistik',
        }
        LEVEL = {1:'Grundkenntnisse',2:'gut',3:'verhandlungssicher',4:'Muttersprache'}
        AVAIL = {1:'sofort verfügbar',2:'bald verfügbar',
                 3:'100% verfügbar',4:'nicht verfügbar'}

        # Location: Einsatzort aus travelConfiguration + Stadt
        _city  = address.get('addressLocality', '').strip()
        _tc    = profile.get('travelConfiguration', {}) or {}
        _rad   = _tc.get('radius')
        _noRes = _tc.get('noRestrictions', False)
        _remOt = _tc.get('remoteOnly', False)
        _isRes = _tc.get('isResidence', False)
        if _noRes:
            location = 'Weltweit'
        elif _remOt and _isRes and _city and _rad:
            location = f'Remote, {_city} +{_rad} km'
        elif _remOt:
            location = 'Remote'
        elif _isRes and _city and _rad:
            location = f'{_city} +{_rad} km'
        elif _city:
            location = _city
        else:
            location = 'nach Absprache'
        company  = person.get('worksFor', {})
        if isinstance(company, dict): company = company.get('name', '')
        else: company = ''

        languages = []
        for l in profile.get('languageSkills', []):
            name  = l.get('languageName', '')
            level = LEVEL.get(l.get('level', 0), '')
            if name: languages.append(f"{name} ({level})" if level else name)

        experience = []
        industries = []
        for ref in profile.get('references', []):
            start  = fmt_date(ref.get('startDate', ''))
            end    = 'heute' if ref.get('atNow') else fmt_date(ref.get('endDate', ''))
            period = f"{start} – {end}" if start else ''
            branche = BRANCHE.get(ref.get('companyBranche', ''),
                      (ref.get('companyBranche') or '').replace('_', ' ').title())
            if branche and branche not in industries:
                industries.append(branche)
            experience.append({
                'period':       period,
                'title':        ref.get('position', ''),
                'company':      ref.get('company', ''),
                'industry':     branche,
                'role':         ref.get('position', ''),
                'location':     '',
                'activities':   html_to_list(ref.get('description', '')),
                'technologies': [],
            })

        certifications = [{
            'name':          c.get('name', ''),
            'issuer':        (c.get('issuingOffice', '') or '').strip(),
            'date_obtained': str(c.get('certificationDate', '')),
            'expiry_date':   '',
        } for c in profile.get('certificates', [])]

        graduation = profile.get('graduation', '')
        education  = []
        if graduation:
            education.append({
                'degree': graduation, 'institution': '',
                'period': '', 'description': '',
                'education_type': 'degree', 'issuer': '',
            })

        focus_experience = html_to_list(profile.get('skills', ''))
        focus_areas      = [c.get('name', '') for c in
                            profile.get('sortedSubCategories', [])[:15]
                            if c.get('name')]
        attachments_info = [{
            'name': a.get('description', ''),
            'url':  'https://www.freelancermap.de' + a.get('downloadUrl', ''),
            'type': a.get('suffix', ''),
        } for a in profile.get('attachments', [])]

        now = datetime.now().isoformat()
        return {
            '_comment':     f'freelancermap Import {url} am {now[:10]}',
            '_attachments': attachments_info,
            'metadata': {
                'aid':            '',
                'version':        '1.0.0.0',
                'consultant_dir': f"{last_name.lower()}_{first_name.lower()}",
                'first_name':     first_name,
                'last_name':      last_name,
                'headline':       profile.get('title', ''),
                'source': {
                    'type':        'url_import',
                    'filename':    url,
                    'filesize':    0,
                    'import_id':   str(profile.get('id', '')),
                    'import_date': now,
                },
                'pipeline': {
                    'version':       '5.0',
                    'step':          'url_import',
                    'extractor':     'url_importer',
                    'model':         'direct_json',
                    'self_learning': True,
                },
                'duplicate_check': {'exists': False, 'message': ''},
                'statistics': {
                    'total_categories': 0,
                    'has_personal':     bool(first_name),
                    'has_skills':       bool(focus_experience),
                    'has_experience':   bool(experience),
                },
            },
            'extracted_data': {
                'personal': {
                    'first_name':           first_name,
                    'last_name':            last_name,
                    'birth_year':           None,
                    'nationality':          '',
                    'languages':            languages,
                    'email':                '',
                    'phone':                '',
                    'location':             location,
                    'availability':         AVAIL.get(profile.get('availability'), 'nach Absprache'),
                    'degree':               graduation,
                    'edv_experience_since': profile.get('freelancerSinceYear'),
                    'headline':             profile.get('title', ''),
                    'summary':              profile.get('aboutMe', ''),
                    'company':              company,
                    'website':              profile.get('socialMedia', {}).get('website', ''),
                },
                'professional':   {'total_experience_years': 0},
                'skills':         {k: [] for k in [
                    'architecture_pattern','business_software','ci_cd_tool',
                    'cloud_platform','communication_tool','database','data_format',
                    'data_management','development_environment','devops_tool',
                    'documentation_tool','framework','hardware','identity_management',
                    'it_infrastructure','methodology','monitoring_tool','network_protocol',
                    'operating_system','programming_languages','project_management',
                    'security_tool','soft_skill','special_concept','testing_tool',
                    'version_control','virtualization',
                ]},
                'certifications':   certifications,
                'experience':       experience,
                'industries':       industries,
                'focus_areas':      focus_areas,
                'focus_experience': focus_experience,
                'education':        education,
                'other':            '',
            },
            'audit': {
                'created_by':      'url_importer',
                'created_at':      now,
                'source_file':     url,
                'steps_completed': ['url_fetch', 'json_parse', 'mapping'],
            },
        }

    def _detect_platform(self, url: str) -> str:
        for domain, code in PLATFORM_MAP.items():
            if domain in url:
                return code
        return 'other'

    def _log(self, msg: str):
        entry = f"{datetime.now().strftime('%H:%M:%S')} {msg}"
        self.log_entries.append(entry)
        logger.info(f"[URLImporter] {msg}")


url_importer = URLImporter()


# ══════════════════════════════════════════════════════════════════════════════
# MASTER PIPELINE INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════

def run_master_pipeline_for_yx(yx_path: str, first_name: str = '',
                                last_name: str = '') -> dict:
    spans = _parse_yx_to_spans(yx_path)
    return run_master_pipeline_from_spans(spans, first_name, last_name)


def _parse_yx_to_spans(yx_path: str) -> list:
    from pathlib import Path as _P
    spans = []
    for line in _P(yx_path).read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line: continue
        parts = line.split('|')
        if len(parts) < 6: continue
        try:
            page   = int(parts[0].replace('p','').strip())
            y      = int(parts[1].split('=')[1].strip())
            x      = int(parts[2].split('=')[1].strip())
            sz     = float(parts[3].split('=')[1].strip())
            bold   = len(parts[4]) >= 1 and parts[4][0].upper() == 'B'
            italic = len(parts[4]) >= 2 and parts[4][1].upper() == 'I'
            text   = '|'.join(parts[5:]).strip()
            if text:
                spans.append({'page':page,'y':y,'x':x,'size':sz,
                              'bold':bold,'italic':italic,'text':text})
        except: continue
    return spans


def run_master_pipeline_from_spans(spans: list, first_name: str = '',
                                    last_name: str = '') -> dict:
    import re
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from dataclasses import dataclass, field
    from typing import List
    from collections import defaultdict
    from datetime import datetime

    logger.info(f"[MasterPipeline] START: {len(spans)} Spans, {first_name} {last_name}")

    from apps.cv_extractor.services.master_detector import master_detector
    result      = master_detector.detect_from_spans(spans, debug_dir=None)
    gruppen     = result['gruppen']
    grouped_txt = result['text']
    logger.info(f"[MasterPipeline] {len(gruppen)} Gruppen erkannt")

    parts = re.split(r'={60} Gruppe (\d+) \| (.+)', grouped_txt)
    parsed_gruppen = []
    i = 1
    while i < len(parts) - 2:
        nr    = int(parts[i])
        label = parts[i+1].strip()
        body  = parts[i+2]
        lines, blks, cur = [], [], None
        for line in body.split('\n'):
            if line.startswith('##'):
                if cur: blks.append(cur)
                m = re.search(r'Block (\d+) \| p(\d+) \| sz=([\d.]+) \| (\S+) \| fn=(\S+)', line)
                cur = {'index':int(m.group(1)),'page':int(m.group(2)),'sz':float(m.group(3)),
                       'bold':'B' in m.group(4),'italic':'I' in m.group(4),
                       'font':m.group(5),'lines':[]} if m else None
            elif line.startswith('  ') and cur:
                cur['lines'].append(line.strip())
                lines.append(line.strip())
        if cur: blks.append(cur)
        parsed_gruppen.append({'nr':nr,'label':label,
                               'text':'\n'.join(l for l in lines if l),
                               'lines':lines,'blocks':blks})
        i += 3

    gruppen_map = {g['nr']: g for g in parsed_gruppen}

    @dataclass
    class SS:
        page:int=0;y:float=0;x:float=0;size:float=12.0
        bold:bool=False;italic:bool=False;font:str='';text:str=''
    @dataclass
    class SB:
        spans:List=field(default_factory=list)
    @dataclass
    class SG:
        index:int;blocks:List=field(default_factory=list)
        text:str='';first_line:str=''

    def to_sg(gruppen):
        return [SG(index=g['nr'],
                   blocks=[SB(spans=[SS(page=b['page'],size=b['sz'],bold=b['bold'],
                                        italic=b['italic'],font=b['font'],text=l)
                                     for l in b['lines']]) for b in g['blocks']],
                   text=g['text'],
                   first_line=g['lines'][0] if g['lines'] else '')
                for g in gruppen]

    from apps.cv_extractor.services.master_labeler import BlockLabeler
    labeled = BlockLabeler().label(to_sg(parsed_gruppen))
    logger.info(f"[MasterPipeline] {len(labeled)} Labels vergeben")

    SKILL_CATS = [
        'architecture_pattern','business_software','ci_cd_tool','cloud_platform',
        'communication_tool','database','data_format','data_management',
        'development_environment','devops_tool','documentation_tool','framework',
        'hardware','identity_management','it_infrastructure','methodology',
        'monitoring_tool','network_protocol','operating_system','programming_languages',
        'project_management','security_tool','soft_skill','special_concept',
        'testing_tool','version_control','virtualization'
    ]
    pre_json = {
        "metadata": {
            "aid":"","version":"","consultant_dir":"",
            "first_name":first_name,"last_name":last_name,"headline":"",
            "pipeline":{"version":"6.0","step":"master_extraction",
                        "extractor":"master_pipeline","model":"deepseek-chat"}
        },
        "extracted_data": {
            "personal":{},"professional":{"total_experience_years":0},
            "skills":{c:[] for c in SKILL_CATS},
            "certifications":[],"experience":[],"industries":[],
            "focus_areas":[],"focus_experience":[],"education":[],"other":""
        },
        "audit":{"created_by":"master_pipeline",
                 "created_at":datetime.now().isoformat(),"steps_completed":[]}
    }

    for lg in labeled:
        if lg.label != 'SKILLS' or not lg.skill_cat: continue
        g = gruppen_map.get(lg.index)
        if not g or lg.skill_cat not in pre_json['extracted_data']['skills']: continue
        items, skip = [], True
        for line in g['text'].split('\n'):
            line = line.strip().lstrip('•·▪►').strip()
            if not line: continue
            if skip and line.endswith(':'): skip=False; continue
            skip = False
            for p in line.split(','):
                p = p.strip()
                if p and len(p) > 1: items.append(p)
        pre_json['extracted_data']['skills'][lg.skill_cat] = list(dict.fromkeys(items))

    from apps.cv_extractor.extractors.master_base_extractor import MasterBaseExtractor

    # consultant_type aus HEADER-Gruppe ableiten
    _consultant_type = 'IT-Freelancer'
    for _lg in labeled:
        if _lg.label == 'HEADER':
            _g = gruppen_map.get(_lg.index)
            if _g and _g.get('text'):
                _consultant_type = _g['text'][:80]
            break

    STAGE_MAP = {
        'HEADER':      'fl_extract_kopf',
        'PERSONAL':    'fl_extract_personal',
        'FACHBEREICHE':'fl_extract_fachbereiche',
        'ZERTIFIKATE': 'fl_extract_zertifikate',
        'SCHULUNGEN':  'fl_extract_schulungen',
        'BRANCHEN':    'fl_extract_branchen',
        'FOCUS_EXP':   'fl_extract_focus_exp',
        'OTHER':       'fl_extract_sonstiges',
    }

    label_texts = defaultdict(str)
    proj_tasks  = []
    for lg in labeled:
        g = gruppen_map.get(lg.index)
        if not g: continue
        if lg.label == 'PROJECT' and lg.project_nr:
            proj_tasks.append((lg.project_nr, g['text']))
        elif lg.label in STAGE_MAP and g['text'].strip():
            label_texts[lg.label] += g['text'] + '\n\n---\n\n'

    tasks = [(lbl, STAGE_MAP[lbl], txt.strip())
             for lbl, txt in label_texts.items() if txt.strip()]

    def run_sec(task):
        lbl, stage, txt = task
        return lbl, MasterBaseExtractor(stage, _consultant_type).extract(txt)

    def run_proj(pt):
        pnr, txt = pt
        return pnr, MasterBaseExtractor('fl_extract_experience', _consultant_type).extract(txt)

    llm_res, proj_res = {}, {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        fs = {ex.submit(run_sec, t):('s',t[0]) for t in tasks}
        fs.update({ex.submit(run_proj,pt):('p',pt[0]) for pt in proj_tasks})
        for f in as_completed(fs):
            typ, key = fs[f]
            if typ == 's':
                lbl, data = f.result()
                llm_res[lbl] = data
            else:
                pnr, data = f.result()
                proj_res[pnr] = data

    logger.info(f"[MasterPipeline] LLM: {len(llm_res)} Sektionen, {len(proj_res)} Projekte")

    if llm_res.get('HEADER'):
        h = llm_res['HEADER']
        pre_json['metadata']['headline'] = h.get('headline','')
        pre_json['metadata']['company']  = h.get('company','')
    if llm_res.get('PERSONAL'):
        pre_json['extracted_data']['personal'] = llm_res['PERSONAL']
    if llm_res.get('FACHBEREICHE'):
        pre_json['extracted_data']['focus_areas'] = llm_res['FACHBEREICHE'].get('focus_areas',[])
    if llm_res.get('ZERTIFIKATE'):
        pre_json['extracted_data']['certifications'] = llm_res['ZERTIFIKATE'].get('certifications',[])
    if llm_res.get('SCHULUNGEN'):
        s = llm_res['SCHULUNGEN']
        pre_json['extracted_data']['education'] = s.get('education',s.get('schulungen',[]))
    if llm_res.get('BRANCHEN'):
        pre_json['extracted_data']['industries'] = llm_res['BRANCHEN'].get('industries',[])
    if llm_res.get('FOCUS_EXP'):
        pre_json['extracted_data']['focus_experience'] = llm_res['FOCUS_EXP'].get('focus_experience',[])
    if llm_res.get('OTHER'):
        pre_json['extracted_data']['other'] = str(llm_res['OTHER'])

    exp = []
    for pnr in sorted(proj_res.keys()):
        d = proj_res[pnr]
        if not d: continue
        if isinstance(d, list): exp.extend(d)
        elif isinstance(d, dict):
            e = d.get('experience', d)
            if isinstance(e, list): exp.extend(e)
            elif isinstance(e, dict): exp.append(e)
    pre_json['extracted_data']['experience'] = exp
    pre_json['audit']['steps_completed'] = list(llm_res.keys()) + ['SKILLS','PROJECT']

    logger.info(f"[MasterPipeline] FERTIG: {len(exp)} Projekte")
    return pre_json


def merge_profil_and_pdf(profil_pre_json: dict, pdf_pre_json: dict) -> dict:
    import copy
    merged = copy.deepcopy(profil_pre_json)
    pdf_ed = pdf_pre_json.get('extracted_data', {})
    api_ed = profil_pre_json.get('extracted_data', {})

    api_p    = api_ed.get('personal', {})
    pdf_p    = pdf_ed.get('personal', {})
    merged_p = merged['extracted_data']['personal']

    for f in ['first_name','last_name','headline','summary','availability',
              'location','nationality']:
        if api_p.get(f): merged_p[f] = api_p[f]

    for f in ['email','phone']:
        if pdf_p.get(f):   merged_p[f] = pdf_p[f]
        elif api_p.get(f): merged_p[f] = api_p[f]

    api_langs = api_p.get('languages', [])
    pdf_langs = pdf_p.get('languages', [])
    seen_lang = {}
    for lang in api_langs + pdf_langs:
        name = lang.split('(')[0].strip().lower()
        if name not in seen_lang or len(lang) > len(seen_lang[name]):
            seen_lang[name] = lang
    merged_p['languages'] = list(seen_lang.values())

    for f in ['birth_year','edv_experience_since','degree','nationality']:
        if not merged_p.get(f) and pdf_p.get(f):
            merged_p[f] = pdf_p[f]

    if profil_pre_json.get('metadata',{}).get('headline'):
        merged['metadata']['headline'] = profil_pre_json['metadata']['headline']

    api_exp    = api_ed.get('experience', [])
    pdf_exp    = pdf_ed.get('experience', [])
    pdf_periods = {e.get('period','').strip() for e in pdf_exp}

    if len(pdf_exp) >= len(api_exp):
        extra_from_api = []
        for a_e in api_exp:
            a_period      = a_e.get('period','').strip()
            a_period_norm = a_period.replace('heute','aktuell').replace('dato','aktuell')
            found = False
            for p_period in pdf_periods:
                p_norm = p_period.replace('heute','aktuell').replace('dato','aktuell')
                if a_period_norm and (a_period_norm in p_norm or p_norm in a_period_norm):
                    found = True; break
            if not found and a_period:
                extra_from_api.append(a_e)
        merged['extracted_data']['experience'] = extra_from_api + pdf_exp
    else:
        for i, a_e in enumerate(api_exp):
            for p_e in pdf_exp:
                if a_e.get('period','') == p_e.get('period',''):
                    if not a_e.get('technologies') and p_e.get('technologies'):
                        api_exp[i]['technologies'] = p_e['technologies']
                    if p_e.get('activities') and len(p_e['activities']) > len(a_e.get('activities',[])):
                        api_exp[i]['activities'] = p_e['activities']
                    break
        merged['extracted_data']['experience'] = api_exp

    pdf_skills = pdf_ed.get('skills', {})
    if any(pdf_skills.values()):
        merged['extracted_data']['skills'] = pdf_skills

    if pdf_ed.get('focus_experience'):
        merged['extracted_data']['focus_experience'] = pdf_ed['focus_experience']

    api_fa = api_ed.get('focus_areas', [])
    pdf_fa = pdf_ed.get('focus_areas', [])
    seen_fa, merged_fa = set(), []
    for fa in api_fa + pdf_fa:
        if fa and fa.lower() not in seen_fa:
            seen_fa.add(fa.lower()); merged_fa.append(fa)
    merged['extracted_data']['focus_areas'] = merged_fa

    merged['extracted_data']['industries'] = list(
        dict.fromkeys(api_ed.get('industries',[]) + pdf_ed.get('industries',[])))[:20]

    api_edu = api_ed.get('education', [])
    pdf_edu = pdf_ed.get('education', [])
    seen = {e.get('degree','').lower() for e in api_edu}
    for e in pdf_edu:
        if e.get('degree','').lower() not in seen:
            api_edu.append(e)
    merged['extracted_data']['education'] = api_edu

    api_certs = api_ed.get('certifications', [])
    pdf_certs = pdf_ed.get('certifications', [])
    seen = {c.get('name','').lower() for c in api_certs}
    for c in pdf_certs:
        if c.get('name','').lower() not in seen:
            api_certs.append(c)
    merged['extracted_data']['certifications'] = api_certs

    def _to_str(v):
        if not v: return ''
        if isinstance(v, dict): return v.get('other', str(v))
        return str(v)
    api_other = _to_str(api_ed.get('other', ''))
    pdf_other = _to_str(pdf_ed.get('other', ''))
    if pdf_other and pdf_other not in api_other:
        merged['extracted_data']['other'] = (api_other + '\n' + pdf_other).strip()
    elif api_other:
        merged['extracted_data']['other'] = api_other

    ed = merged['extracted_data']
    merged['metadata']['statistics'] = {
        'total_categories': len([c for c in ed['skills'].values() if c]),
        'has_personal':     bool(ed['personal'].get('birth_year') or ed['personal'].get('location')),
        'has_skills':       any(ed['skills'].values()),
        'has_experience':   len(ed['experience']) > 0,
        'project_count':    len(ed['experience']),
        'skill_count':      sum(len(v) for v in ed['skills'].values()),
    }
    merged['audit']['merged_at']     = datetime.now().isoformat()
    merged['audit']['merge_source']  = 'profil_json + master_pipeline'
    return merged


def normalize_pre_json(merged: dict) -> dict:
    import copy
    import json as _json
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from apps.cv_extractor.services.deepseek_service import deepseek_service
    from apps.cv_extractor.services.deepseek_api_label import deepseek_label_api
    from apps.cv_extractor.models import PromptTemplate

    result = copy.deepcopy(merged)
    ed     = result['extracted_data']

    def get_prompt(stage):
        try:
            return PromptTemplate.objects.get(stage=stage, is_active=True).prompt_text
        except Exception as e:
            logger.warning(f"[Normalizer] Prompt {stage} nicht gefunden: {e}")
            return None

    def run_section(stage, data, use_array=False):
        if (isinstance(data, list) and not data) or \
           (isinstance(data, dict) and not any(data.values())):
            return stage, None
        pt = get_prompt(stage)
        if not pt: return stage, None
        prompt = pt.format(data=_json.dumps(data, ensure_ascii=False, indent=2))
        api = deepseek_label_api if use_array else deepseek_service
        res = api.extract(prompt)
        if res.success and res.data:
            return stage, res.data
        logger.warning(f"[Normalizer] {stage} fehlgeschlagen: {getattr(res,'error','')}")
        return stage, None

    def get_result(results, stage):
        d = results.get(stage)
        if not d: return None
        if isinstance(d, dict): return d.get('result', d)
        if isinstance(d, list): return d
        return None

    section_tasks = [
        ('fl_normalize_industries',       ed.get('industries',       []), False),
        ('fl_normalize_focus_areas',      ed.get('focus_areas',      []), False),
        ('fl_normalize_focus_experience', ed.get('focus_experience', []), False),
        ('fl_normalize_languages',        ed.get('personal', {}).get('languages', []), False),
        ('fl_normalize_education',        ed.get('education',        []), True),
        ('fl_normalize_certifications',   ed.get('certifications',   []), True),
        ('fl_normalize_skills',           ed.get('skills',           {}), False),
        ('fl_normalize_personal',         ed.get('personal',         {}), False),
    ]

    logger.info(f"[Normalizer] Phase 1: {len(section_tasks)} Bereiche parallel...")
    sec_results = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(run_section, s, d, a): s
                   for s, d, a in section_tasks}
        for future in as_completed(futures):
            stage, data = future.result()
            sec_results[stage] = data
            logger.info(f"  {stage}: {'OK' if data else 'leer/fehler'}")

    if get_result(sec_results, 'fl_normalize_industries'):
        ed['industries'] = get_result(sec_results, 'fl_normalize_industries')
    if get_result(sec_results, 'fl_normalize_focus_areas'):
        ed['focus_areas'] = get_result(sec_results, 'fl_normalize_focus_areas')
    if get_result(sec_results, 'fl_normalize_focus_experience'):
        ed['focus_experience'] = get_result(sec_results, 'fl_normalize_focus_experience')
    if get_result(sec_results, 'fl_normalize_languages'):
        ed['personal']['languages'] = get_result(sec_results, 'fl_normalize_languages')
    r = get_result(sec_results, 'fl_normalize_education')
    if isinstance(r, list): ed['education'] = r
    r = get_result(sec_results, 'fl_normalize_certifications')
    if isinstance(r, list): ed['certifications'] = r
    r = sec_results.get('fl_normalize_skills')
    if isinstance(r, dict) and 'architecture_pattern' in r: ed['skills'] = r
    r = get_result(sec_results, 'fl_normalize_personal')
    if isinstance(r, dict):
        for k, v in r.items():
            if v and v != '' and v != [] and v != 0:
                ed['personal'][k] = v

    exp_list = ed.get('experience', [])
    if exp_list:
        pt = get_prompt('fl_normalize_experience')
        if pt:
            logger.info(f"[Normalizer] Phase 2: {len(exp_list)} Projekte parallel...")

            def normalize_one(idx_exp):
                idx, exp = idx_exp
                try:
                    prompt = pt.format(data=_json.dumps(exp, ensure_ascii=False, indent=2))
                    res = deepseek_service.extract(prompt)
                    if res.success and res.data:
                        r = res.data
                        r = r.get('result', r) if isinstance(r, dict) else r
                        if isinstance(r, dict) and r.get('period'): return idx, r
                        if isinstance(r, list) and r: return idx, r[0]
                    return idx, exp
                except Exception as e:
                    logger.warning(f"  Projekt {idx}: {e}")
                    return idx, exp

            proj_results = {}
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(normalize_one, (i, exp)): i
                           for i, exp in enumerate(exp_list)}
                done = 0
                for future in as_completed(futures):
                    idx, exp = future.result()
                    proj_results[idx] = exp
                    done += 1

            normalized_exp = [proj_results[i] for i in sorted(proj_results.keys())]
            seen, deduped = set(), []
            for exp in normalized_exp:
                p = exp.get('period', '')
                if p and p in seen: continue
                if p: seen.add(p)
                deduped.append(exp)
            ed['experience'] = deduped
            logger.info(f"[Normalizer] Projekte: {len(deduped)}")

    result['audit']['normalized_at'] = datetime.now().isoformat()
    result['audit']['steps_completed'].append('normalize')
    return result
