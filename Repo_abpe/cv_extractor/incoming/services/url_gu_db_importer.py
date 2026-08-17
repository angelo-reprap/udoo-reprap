"""
url_gu_db_importer.py — GULP PDF-Parser + DB-Import

Changelog:
  2026-04-28: skill_normalizer nach extracted_to_db.save() hinzugefügt
              search_enricher + self_learning_pipeline hinzugefügt
              _build_tech_counter_from_ram() analog pipeline.py
"""
import copy
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)
BASE_DIR = Path('data/url/gu')

MAIN_SECTIONS = {
    'Einsatzorte', 'Projekte', 'Aus- und Weiterbildung',
    'Position', 'Kompetenzen', 'Branchen', 'Referenzen'
}
PROJECT_LABELS = {
    'Rolle': 'role', 'Kunde': 'company', 'Einsatzort': 'location',
    'Projektinhalte': 'activities', 'Produkte': 'technologies',
    'Kenntnisse': 'technologies',
}
GULP_CLEAN_RE = re.compile(r'[\ue000-\uf8ff]')

DATE_RE      = re.compile(r'^(\d{4}-\d{2})\s*-\s*(\d{4}-\d{2}|heute|dato|aktuell|now)\s*(.+)', re.I)
DURATION_RE  = re.compile(r'^\d+\s*(Jahr|Monat|Woche|Tag)', re.I)
CERT_RE      = re.compile(r'zertifizierung|zertifikat|certified|certificate|abschluss|diploma|diplom', re.I)
COURSE_RE    = re.compile(r'^(lehrgang|kurs|schulung|training|weiterbildung|spezialisierung|fortbildung|umschulung|studium|ausbildung)', re.I)
GULP_CAT_MAP = {
    'Top-Skills': 'special_concept',
    'Programmiersprachen': 'programming_languages',
    'Betriebssysteme': 'operating_system',
    'Hardware': 'hardware',
    'Datenkommunikation': 'network_protocol',
    'Datenbanken': 'database',
    'Produkte / Standards / Erfahrungen / Methoden': 'special_concept',
    'Schwerpunkte': None,
    'Aufgabenbereiche': 'methodology',
    'Design / Entwicklung / Konstruktion': 'framework',
    'Managementerfahrung in Unternehmen': 'methodology',
    'Personalverantwortung': 'soft_skill',
}
ALL_SKILL_CATS = [
    'architecture_pattern','business_software','ci_cd_tool','cloud_platform',
    'communication_tool','database','data_format','data_management',
    'development_environment','devops_tool','documentation_tool','framework',
    'hardware','identity_management','it_infrastructure','methodology',
    'monitoring_tool','network_protocol','operating_system','programming_languages',
    'project_management','security_tool','soft_skill','special_concept',
    'testing_tool','version_control','virtualization'
]


class GULPPdfParser:

    def parse(self, pdf_path: str) -> dict:
        from apps.cv_extractor.services.pdf_extractor import PDFExtractor
        res   = PDFExtractor().extract(str(pdf_path))
        spans = res.spans
        result = {'headline':'','projects':[],'education':[],'certifications':[],'skills':{},'industries':[],'focus':[],'position':''}
        if not spans:
            return result
        sections            = self._split_sections(spans)
        result['headline']  = self._parse_headline(spans)
        if 'Projekte'              in sections: result['projects']       = self._parse_projects(sections['Projekte'])
        if 'Aus- und Weiterbildung' in sections:
            edu, certs = self._parse_education(sections['Aus- und Weiterbildung'])
            result['education'] = edu; result['certifications'] = certs
        if 'Kompetenzen' in sections:
            sk, fo = self._parse_kompetenzen(sections['Kompetenzen'])
            result['skills'] = sk; result['focus'] = fo
        if 'Branchen'  in sections: result['industries'] = self._parse_branchen(sections['Branchen'])
        if 'Position'  in sections: result['position']   = self._parse_position(sections['Position'])
        logger.info(f"[GULPPdfParser] {len(result['projects'])} Proj, {len(result['education'])} Edu, {len(result['certifications'])} Cert, {len(result['industries'])} Branch")
        return result

    def _split_sections(self, spans):
        sections, cur_sec, cur_spans = {}, None, []
        for s in spans:
            if round(s.size,1)==15.0 and s.text.strip() in MAIN_SECTIONS:
                if cur_sec: sections[cur_sec] = cur_spans
                cur_sec, cur_spans = s.text.strip(), []
            elif cur_sec:
                cur_spans.append(s)
        if cur_sec and cur_spans: sections[cur_sec] = cur_spans
        return sections

    def _parse_headline(self, spans):
        parts = []
        for s in spans:
            if s.page==1 and round(s.size,1)==19.5: parts.append(s.text.strip())
            elif s.page>1: break
        return ' '.join(parts).strip()

    def _parse_projects(self, spans):
        projects, current = [], None
        # Alle bekannten Label-Präfixe die GULP zusammenklebt
        ALL_LABELS = [
            'Projektinhalte', 'Produkte', 'Kenntnisse',
            'Rolle', 'Kunde', 'Einsatzort',
        ]
        # Regex zum Auftrennen zusammengeklebter Label+Wert Strings
        # z.B. "ProdukteF5AnsibleOpswat" → label="Produkte", val="F5AnsibleOpswat"
        LABEL_SPLIT_RE = re.compile(
            r'^(' + '|'.join(ALL_LABELS) + r')(.*)', re.DOTALL
        )
        # Datum+Titel zusammengeklebt: "2025-01 - 2025-09Administration F5"
        DATE_TITLE_RE = re.compile(
            r'^(\d{4}-\d{2})\s*[-–]\s*(\d{4}-\d{2}|heute|dato|aktuell|now)\s*(.+)',
            re.I
        )

        def _unsplit(text):
            """
            Trennt zusammengeklebte GULP-Spans auf.
            "ProdukteF5AnsibleOpswat" → [("Produkte","F5AnsibleOpswat")]
            "2025-01 - 2025-09Administration F5" → Datum+Titel
            Gibt Liste von (label_or_none, value) zurück.
            """
            # Datum+Titel zusammengeklebt
            m = DATE_TITLE_RE.match(text)
            if m:
                return [(None, text)]  # Wird von DATE_RE weiterverarbeitet
            # Label+Wert zusammengeklebt
            m = LABEL_SPLIT_RE.match(text)
            if m:
                return [(m.group(1), m.group(2).strip())]
            return [(None, text)]

        for s in spans:
            sz, raw_text = round(s.size, 1), s.text.strip()
            if not raw_text:
                continue
            if DURATION_RE.match(raw_text):
                continue
            if sz == 9.0:
                # Text aufsplitten falls Labels zusammengeklebt
                segments = _unsplit(raw_text)
                for label, text in segments:
                    if not text and not label:
                        continue
                    # Wenn label bekannt → als Label+Wert behandeln
                    if label:
                        text_to_process = label + text
                    else:
                        text_to_process = raw_text

                    m = DATE_RE.match(text_to_process)
                    if m:
                        if current:
                            projects.append(self._fin_proj(current))
                        current = {
                            'period':     f"{m.group(1)} – {m.group(2)}",
                            'title':      m.group(3).strip(),
                            'company':    '', 'role':     '',
                            'location':   '', 'activities': [],
                            'technologies': [], '_tech_raw': [],
                        }
                        continue
                    if current is None:
                        continue
                    matched = False
                    for lbl, field in PROJECT_LABELS.items():
                        if text_to_process.startswith(lbl):
                            val = text_to_process[len(lbl):].strip()
                            if not val:
                                matched = True
                                break
                            if field == 'role' and not current['role']:
                                current['role'] = val
                            elif field == 'company' and not current['company']:
                                current['company'] = val
                            elif field == 'location' and not current['location']:
                                current['location'] = val
                            elif field == 'activities' and val:
                                current['activities'].append(val)
                            elif field == 'technologies' and val:
                                # Val kann mehrere zusammengeklebte Techs sein
                                # z.B. "F5AnsibleOpswat" → aufsplitten
                                current['_tech_raw'].append(val)
                            matched = True
                            break
                    if not matched and current:
                        if current['activities']:
                            current['activities'][-1] += ' ' + text_to_process
                        else:
                            current['activities'].append(text_to_process)
            elif sz == 7.5 and current:
                current['activities'].append(raw_text)
        if current:
            projects.append(self._fin_proj(current))
        return projects

    def _fin_proj(self, p):
        # Bekannte Hersteller-Praefix-Woerter die NICHT gesplittet werden duerfen
        KNOWN_PREFIXES = {
            'forti', 'check', 'cisco', 'palo', 'juniper', 'aruba',
            'netscreen', 'mcafee', 'symantec', 'trend', 'sophos',
            'barracuda', 'sonicwall', 'checkpoint',
        }
        # Bekannte zusammengesetzte Skill-Namen die NICHT gesplittet werden
        PROTECTED = {
            'fortigate', 'fortimanager', 'fortianalyzer', 'fortiauthenticator',
            'fortiswitch', 'fortiap', 'fortios', 'forticlient',
            'checkpoint', 'paloalto',
        }

        def _split_glued(text):
            """
            Splittet zusammengeklebte GULP-PDF Strings.
            Strategie: Wort-Grenzen erkennen an Stellen wo
            Kleinbuchstabe direkt auf Grossbuchstabe folgt
            UND der linke Teil ein bekanntes Wort-Ende bildet.

            Beispiele:
              "F5AnsibleOpswat"        → ["F5", "Ansible", "Opswat"]
              "Network SecurityVPN"    → ["Network Security", "VPN"]
              "FortiAuthenticator"     → ["FortiAuthenticator"]  (geschuetzt)
              "CheckPoint Firewall"    → ["CheckPoint Firewall"] (geschuetzt)
              "Palo Alto FirewallF5 VE"→ ["Palo Alto Firewall", "F5 VE"]
            """
            # Geschuetzte Namen → nicht splitten
            if text.lower().replace(' ', '') in PROTECTED:
                return [text]
            # Erstes Wort ist bekanntes Praefix → nicht splitten
            first_word = text.split()[0].lower() if text.split() else ''
            if first_word in KNOWN_PREFIXES:
                return [text]

            # Splitten an: Kleinbuchstabe + Grossbuchstabe (direkt, kein Leerzeichen)
            # z.B. "securityVPN" → split vor V
            # z.B. "FirewallF5"  → split vor F
            parts = re.split(r'(?<=[a-z])(?=[A-Z])', text)
            if len(parts) == 1:
                return [text]

            # Teile zusammenfuehren wenn sie zu kurz sind (< 2 Zeichen)
            merged = []
            current = parts[0]
            for part in parts[1:]:
                # Wenn aktueller Teil mit Leerzeichen endet und naechster
                # Teil kurz ist → zusammenhalten
                combined = current + part
                # Neuer Teil beginnt mit bekanntem Praefix → neues Token
                first = part.split()[0].lower() if part.split() else ''
                if first in KNOWN_PREFIXES or len(part.strip()) >= 2:
                    merged.append(current.strip())
                    current = part
                else:
                    current = combined
            if current.strip():
                merged.append(current.strip())

            # Nur zurueckgeben wenn alle Teile >= 2 Zeichen
            merged = [m for m in merged if len(m) >= 2]
            return merged if len(merged) > 1 else [text]

        def _split_raw(raw):
            """
            Haupt-Split-Funktion fuer rohe Tech-Strings.
            Reihenfolge:
              1. Klammern extrahieren
              2. Komma/Semikolon/Slash splitten
              3. Zusammengeklebte Tokens aufsplitten
            """
            result = []

            # Schritt 1: Klammern extrahieren
            extras = []
            for m in re.finditer(r'\(([^)]+)\)', raw):
                for x in m.group(1).split(','):
                    x = x.strip()
                    if x and len(x) >= 2:
                        extras.append(x)
            cleaned = re.sub(r'\s*\([^)]*\)', '', raw).strip()

            # Schritt 2: Komma/Semikolon/Slash splitten
            parts = re.split(r',|;(?=\s*[A-Z0-9])|/(?=\s*[A-Z0-9])', cleaned)

            # Schritt 3: Jeden Teil auf zusammengeklebte Tokens pruefen
            for part in parts:
                part = part.strip()
                if not part or len(part) < 2:
                    continue
                result.extend(_split_glued(part))

            result.extend(extras)
            return result

        techs = []
        for raw in p.get('_tech_raw', []):
            techs.extend(_split_raw(raw))

        # Duplikate entfernen, Reihenfolge behalten
        seen, deduped = set(), []
        for t in techs:
            if t.lower() not in seen:
                seen.add(t.lower())
                deduped.append(t)

        return {
            'period':       p.get('period', ''),
            'title':        p.get('title', ''),
            'company':      p.get('company', ''),
            'industry':     '',
            'role':         p.get('role', ''),
            'location':     p.get('location', ''),
            'activities':   [a for a in p.get('activities', []) if a.strip()],
            'technologies': deduped,
        }

    def _parse_education(self, spans):
        edu, certs = [], []
        lines = [(round(s.size,1), s.text.strip()) for s in spans if s.text.strip() and round(s.size,1) in (9.0,7.5)]
        i, current_entry, in_cert, cur_date = 0, None, False, ''
        while i < len(lines):
            sz, text = lines[i]; tl = text.lower().strip()
            if re.match(r'^zertifizierungen?:?\s*$',tl) or re.match(r'^zertifizierungen?/\s*schulungen?\s*:?\s*$',tl):
                in_cert=True; cur_date=''; i+=1; continue
            m = DATE_RE.match(text)
            if m and sz==9.0:
                if current_entry: self._add_edu(current_entry, edu, certs, in_cert)
                current_entry={'title':m.group(3).strip(),'period':f"{m.group(1)} – {m.group(2)}",'degree':'','institution':'','description':''}
                i+=1; continue
            if text.startswith('Abschluss') and sz==9.0:
                if current_entry: current_entry['degree']=text[len('Abschluss'):].strip()
                i+=1; continue
            if (text.startswith('Institution, Ort') or text.startswith('Institution:')) and sz==9.0:
                val=re.sub(r'^Institution,?\s*(Ort)?:?\s*','',text).strip()
                if current_entry: current_entry['institution']=val
                i+=1; continue
            if text.startswith('Schwerpunkt') and sz==9.0: i+=1; continue
            ym=re.match(r'^(\d{4})\s*[-–/]\s*(\d{4}):?\s*$',text)
            if ym and sz==9.0: cur_date=f"{ym.group(1)} – {ym.group(2)}"; i+=1; continue
            ym2=re.match(r'^(\d{2}/\d{4}):?\s*$',text)
            if ym2 and sz==9.0: cur_date=ym2.group(1); i+=1; continue
            ym3=re.match(r'^(\d{4}):?\s*$',text)
            if ym3 and sz==9.0: cur_date=ym3.group(1); i+=1; continue
            if DURATION_RE.match(text): i+=1; continue
            if sz==7.5 or (in_cert and sz==9.0 and not current_entry):
                if COURSE_RE.match(text):
                    edu.append({'degree':re.sub(r'^(lehrgang|kurs|schulung|training)\s+','',text,flags=re.I).strip(),'institution':'','period':cur_date,'description':'','education_type':'course','issuer':''})
                else:
                    certs.append({'name':text,'issuer':'','date_obtained':cur_date,'expiry_date':''})
                cur_date=''; i+=1; continue
            if cur_date and sz==9.0:
                if CERT_RE.search(text) or in_cert:
                    certs.append({'name':text,'issuer':'','date_obtained':cur_date,'expiry_date':''})
                elif COURSE_RE.match(text):
                    edu.append({'degree':text,'institution':'','period':cur_date,'description':'','education_type':'course','issuer':''})
                else:
                    edu.append({'degree':text,'institution':'','period':cur_date,'description':'','education_type':'degree','issuer':''})
                cur_date=''; i+=1; continue
            if current_entry and sz==9.0:
                if not current_entry.get('institution') and len(text)<100: current_entry['institution']=text
                else: current_entry['description']+=' '+text
            i+=1
        if current_entry: self._add_edu(current_entry, edu, certs, in_cert)
        return edu, certs

    def _add_edu(self, entry, edu, certs, in_cert):
        degree = entry.get('degree','') or entry.get('title','')
        if not degree: return
        if in_cert or CERT_RE.search(degree):
            certs.append({'name':degree,'issuer':entry.get('institution',''),'date_obtained':entry.get('period',''),'expiry_date':''})
        elif COURSE_RE.match(degree):
            edu.append({'degree':degree,'institution':entry.get('institution',''),'period':entry.get('period',''),'description':entry.get('description','').strip(),'education_type':'course','issuer':''})
        else:
            edu.append({'degree':degree,'institution':entry.get('institution',''),'period':entry.get('period',''),'description':entry.get('description','').strip(),'education_type':'degree','issuer':''})

    def _parse_kompetenzen(self, spans):
        skills = {k:[] for k in ALL_SKILL_CATS}
        focus, cur_cat, is_focus = [], None, False
        for s in spans:
            sz, text = round(s.size,1), s.text.strip()
            if not text: continue
            if sz==12.0:
                if text in GULP_CAT_MAP:
                    mapped=GULP_CAT_MAP[text]
                    if mapped is None: is_focus=True; cur_cat=None
                    else: is_focus=False; cur_cat=mapped
                else: cur_cat=None; is_focus=False
                continue
            # sz=9.0 ignorieren: GULP klebt mehrere Felder zusammen (13/14 Profile betroffen)
            # Primaere Skill-Quelle: profil_pre_json.json (API-Daten)
            # Sekundaere Quelle: sz=7.5 Bullet-Liste (sauber)
            if sz == 9.0:
                continue
            if sz == 7.5 and (cur_cat or is_focus):
                items = self._split_skills(text, sz)
                if is_focus: focus.extend(items)
                elif cur_cat:
                    for item in items:
                        if item not in skills[cur_cat]: skills[cur_cat].append(item)
        skills = {k:v for k,v in skills.items() if v}
        return skills, focus

    def _split_skills(self, text, sz):
        """
        Splittet einen Skill-String in einzelne Skill-Namen.
        sz=7.5: Komma-getrennte Liste (sauber)
        sz=9.0: Zusammengeklebte Tokens (GULP PDF Problem)
                z.B. "FortigateCheck PointPalo Alto Firewall"
                z.B. "CISCO IOS (11.xx, 15.xx)FortiOS (5.x)"
        """
        text = GULP_CLEAN_RE.sub('', text).strip()
        if not text:
            return []

        # sz=7.5: sauber, nur Komma-Split
        if sz == 7.5:
            return [p.strip() for p in text.split(',')
                    if p.strip() and len(p.strip()) > 1]

        # sz=9.0: zusammengeklebt — komplexes Parsing nötig
        # Strategie:
        #   1. Klammer-Gruppen als Einheit behandeln
        #   2. Auf Kleinbuchstabe→Grossbuchstabe splitten (ohne Leerzeichen)
        #   3. Bekannte Präfixe schützen

        KNOWN_PREFIXES = {
            'forti', 'check', 'cisco', 'palo', 'juniper', 'aruba',
            'netscreen', 'mcafee', 'symantec', 'trend', 'sophos',
            'barracuda', 'sonicwall', 'checkpoint',
        }

        def _expand_brackets(s):
            """
            Expandiert Klammer-Gruppen zu einzelnen Tokens.
            "CISCO IOS (11.xx, 15.xx)FortiOS" →
              ["CISCO IOS 11.xx", "CISCO IOS 15.xx", "FortiOS"]
            "Unix (Linux (RedHat,SuSE))" →
              ["Unix Linux RedHat", "Unix Linux SuSE"]
            """
            # Finde erste Klammer-Gruppe
            m = re.search(r'^(.*?)\(([^()]+)\)(.*)', s, re.DOTALL)
            if not m:
                return [s]
            prefix  = m.group(1).strip()
            content = m.group(2).strip()
            suffix  = m.group(3).strip()
            # Items in Klammer
            items = [x.strip() for x in content.split(',') if x.strip()]
            result = []
            for item in items:
                combined = f"{prefix} {item}".strip() if prefix else item
                # Suffix rekursiv verarbeiten
                if suffix:
                    for sub in _expand_brackets(suffix):
                        result.append(combined)
                    # Suffix als eigene Tokens
                else:
                    result.append(combined)
            if suffix:
                result.extend(_expand_brackets(suffix))
            return result if result else [s]

        def _split_glued(s):
            """Splittet zusammengeklebte Tokens an Kleinbuchstabe→Grossbuchstabe."""
            # Geschützte Präfixe → nicht splitten
            first_word = s.split()[0].lower() if s.split() else ''
            if first_word in KNOWN_PREFIXES:
                return [s]
            # Split an: Kleinbuchstabe direkt vor Grossbuchstabe
            parts = re.split(r'(?<=[a-z])(?=[A-Z])', s)
            if len(parts) == 1:
                return [s]
            merged = []
            current = parts[0]
            for part in parts[1:]:
                first = part.split()[0].lower() if part.split() else ''
                if len(part.strip()) >= 2:
                    merged.append(current.strip())
                    current = part
                else:
                    current += part
            if current.strip():
                merged.append(current.strip())
            merged = [m for m in merged if len(m) >= 2]
            return merged if len(merged) > 1 else [s]

        # Hauptlogik: Erst Klammern expandieren, dann splitten
        # Schritt 1: Auf Komma ausserhalb von Klammern splitten
        # (Komma in Klammern gehört zum Klammer-Inhalt)
        depth = 0
        parts = []
        current = ''
        for ch in text:
            if ch == '(':
                depth += 1
                current += ch
            elif ch == ')':
                depth -= 1
                current += ch
            elif ch == ',' and depth == 0:
                if current.strip():
                    parts.append(current.strip())
                current = ''
            else:
                current += ch
        if current.strip():
            parts.append(current.strip())

        # Schritt 2: Jeden Teil expandieren (Klammern) und dann splitten
        result = []
        for part in parts:
            if '(' in part:
                expanded = _expand_brackets(part)
                for e in expanded:
                    result.extend(_split_glued(e))
            else:
                result.extend(_split_glued(part))

        # Bereinigen
        final = []
        seen = set()
        for item in result:
            item = item.strip()
            if item and len(item) >= 2 and item.lower() not in seen:
                seen.add(item.lower())
                final.append(item)
        return final

    def _parse_branchen(self, spans):
        branchen = []
        for s in spans:
            if round(s.size,1) in (7.5,9.0) and s.text.strip():
                for b in s.text.split(','):
                    b=GULP_CLEAN_RE.sub('',b).strip()
                    if b and len(b)>2: branchen.append(b)
        return list(dict.fromkeys(branchen))

    def _parse_position(self, spans):
        return ' '.join(s.text.strip() for s in spans if round(s.size,1)==9.0 and s.text.strip()).strip()


class GULPDbImporter:

    def __init__(self):
        self.pdf_parser = GULPPdfParser()

    def import_all(self, dry_run=False):
        """Alle GULP-Profile parallel importieren (max 10 Worker)."""
        import os
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = {'ok':[], 'error':[]}
        dirs = sorted([d for d in BASE_DIR.iterdir() if d.is_dir()])
        logger.info(f"[GULPDbImporter] {len(dirs)} Profile")

        # Worker-Anzahl aus settings.json
        try:
            from django.conf import settings as dj_settings
            cfg_path = os.path.join(dj_settings.BASE_DIR, 'settings.json')
            with open(cfg_path) as f:
                cfg = json.load(f)
            workers = int(cfg.get('pipeline', {}).get('parallel_workers_projects', 10))
        except Exception:
            workers = 10

        def _import_one_safe(d):
            try:
                r = self.import_one(d.name, dry_run=dry_run)
                return d.name, r
            except Exception as e:
                return d.name, {'success': False, 'error': str(e)}

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_import_one_safe, d): d for d in dirs}
            for future in as_completed(futures):
                dir_name, r = future.result()
                if r.get('success'):
                    results['ok'].append({'dir': dir_name, 'aid': r.get('aid'), 'name': r.get('name')})
                    logger.info(f"  ✅ {dir_name} → {r.get('aid')}")
                else:
                    results['error'].append({'dir': dir_name, 'error': r.get('error')})
                    logger.warning(f"  ❌ {dir_name}: {r.get('error')}")

        logger.info(f"[GULPDbImporter] {len(results['ok'])} OK, {len(results['error'])} Fehler")
        return results

    def import_one(self, dir_name, dry_run=False, first_name_override=None, last_name_override=None):
        base = BASE_DIR / dir_name
        pre_json_path = base / 'profil_pre_json.json'
        if not pre_json_path.exists():
            return {'success':False,'error':f'profil_pre_json.json fehlt'}

        pre_json = json.loads(pre_json_path.read_text(encoding='utf-8'))
        meta  = pre_json.get('metadata',{})
        first = first_name_override or meta.get('first_name','')
        last  = last_name_override  or meta.get('last_name','')
        if not first or not last:
            parts = dir_name.replace('-','_').split('_')
            if len(parts) >= 2:
                last  = parts[0].capitalize()
                first = parts[1].capitalize()
            else:
                first = 'Unbekannt'
                last  = dir_name

        # PDF parsen — nur wenn pre_json keine Projekte hat
        # (pre_json wurde bereits von url_gu_importer mit PDF-Daten gebaut)
        pdf_path = base / 'download' / '01_profil.pdf'
        pdf_data = {}
        has_projects = bool(pre_json.get('extracted_data', {}).get('experience', []))
        if pdf_path.exists() and not has_projects:
            try: pdf_data = self.pdf_parser.parse(str(pdf_path))
            except Exception as e: logger.warning(f"  PDF Fehler: {e}")
        elif pdf_path.exists() and has_projects:
            # Nur Bildung + Zertifikate + Skills aus PDF ergaenzen
            # Projekte NICHT nochmal parsen (bereits in pre_json)
            try:
                pdf_data = self.pdf_parser.parse(str(pdf_path))
                pdf_data['projects'] = []  # Projekte aus PDF ignorieren
            except Exception as e: logger.warning(f"  PDF Fehler: {e}")

        # Mergen
        merged = self._merge(pre_json, pdf_data)

        if dry_run:
            return {'success':True,'dry_run':True,'name':f"{first} {last}",
                    'projects':len(merged['extracted_data']['experience']),
                    'skills':sum(len(v) for v in merged['extracted_data']['skills'].values())}

        # UploadedPDF anlegen (status=processing → Signal feuert NICHT)
        from apps.cv_extractor.models import UploadedPDF
        upload = UploadedPDF.objects.create(
            filename    = f"GULP:{dir_name}",
            first_name  = first,
            last_name   = last,
            action_type = 'url_import',
            status      = 'processing',
        )

        # AID generieren
        from apps.cv_extractor.services.aid_generator import aid_generator
        from apps.cv_extractor.services.versioning import version_manager
        version_info   = version_manager.get_next_version(first, last, target_directory=dir_name, action_type='new_version')
        consultant_dir = version_info['consultant_dir']
        aid_info = aid_generator.generate_from_cv(merged['extracted_data'], first, last, target_directory=consultant_dir, action_type='new_version')
        if not aid_info:
            upload.status='failed'; upload.save(update_fields=['status'])
            return {'success':False,'error':'AID-Generierung fehlgeschlagen'}
        aid = aid_info['aid']
        merged['metadata']['aid']            = aid
        merged['metadata']['version']        = aid_info['version_string']
        merged['metadata']['consultant_dir'] = consultant_dir

        # Consultant + DB
        from apps.cv_extractor.models import Consultant
        from apps.cv_extractor.enricher.extracted_to_db import extracted_to_db
        consultant, created = Consultant.objects.get_or_create(aid=aid)
        personal = merged['extracted_data'].get('personal',{})
        consultant.version=aid_info['version_string']; consultant.consultant_dir=consultant_dir
        consultant.first_name=first; consultant.last_name=last; consultant.source_type='url_import'
        consultant.headline=merged['metadata'].get('headline','')
        consultant.birth_year=personal.get('birth_year'); consultant.nationality=personal.get('nationality','')
        consultant.email=personal.get('email',''); consultant.phone=personal.get('phone','')
        consultant.location=personal.get('location',''); consultant.availability=personal.get('availability','')
        consultant.edv_experience_since=personal.get('edv_experience_since'); consultant.degree=personal.get('degree','')
        consultant.website=personal.get('website','') or ''; consultant.summary=personal.get('summary','') or ''
        consultant.extracted_json_export={'metadata':merged['metadata'],'extracted_data':merged['extracted_data'],'raw_text':''}
        consultant.status='processing'; consultant.save()
        consultant = extracted_to_db.save(consultant, consultant.extracted_json_export)

        # ── Schritt 10 analog pipeline.py: Skill-Normalisierung ──────────────
        try:
            tech_counter, experience_map = self._build_tech_counter_from_ram(
                merged['extracted_data']['experience'], consultant
            )
            if tech_counter:
                from apps.cv_extractor.services.skill_normalizer import skill_normalizer
                headline = merged['metadata'].get('headline', '')
                normalized = skill_normalizer.normalize(tech_counter, headline=headline)
                stats = skill_normalizer.save_to_db(consultant, normalized, experience_map)
                logger.info(f"  SkillNormalizer: +{stats['added']} Skills, {stats['updated']} aktualisiert")
            else:
                logger.info(f"  Keine Technologien in Projekten gefunden")
        except Exception as e:
            logger.warning(f"  SkillNormalizer Fehler: {e}")

        # Status + HTML
        consultant.status='profile_ready'; consultant.save(update_fields=['status','updated_at'])
        try:
            from apps.cv_extractor.generator.html.html_generator import HTMLGenerator
            gen=HTMLGenerator(); gen.generate('aid-profile',consultant); gen.generate('aid-short',consultant)
            logger.info(f"  HTML: {aid}")
        except Exception as e: logger.warning(f"  HTML Fehler: {e}")

        # ── SearchEnricher (analog pipeline.py Stufe 1) ───────────────────────
        try:
            from apps.cv_extractor.enricher.search_enricher import search_enricher
            master_json = consultant.extracted_json_export or {}
            master_json = search_enricher.enrich(consultant, master_json)
            consultant.extracted_json_export = master_json
            consultant.save(update_fields=['extracted_json_export', 'updated_at'])
            logger.info(f"  SearchEnricher: {aid}")
        except Exception as e:
            logger.warning(f"  SearchEnricher Fehler: {e}")

        # ── SelfLearning (analog pipeline.py Stufe 1) ─────────────────────────
        try:
            from apps.cv_extractor.enricher.self_learning_pipeline import self_learning_pipeline
            stats = self_learning_pipeline.process(consultant, consultant.extracted_json_export or {})
            logger.info(f"  SelfLearning: {stats}")
        except Exception as e:
            logger.warning(f"  SelfLearning Fehler: {e}")

        # UploadedPDF aktualisieren → erscheint in Liste mit Editor-Button
        UploadedPDF.objects.filter(pk=upload.pk).update(
            status='completed', aid=aid,
            version=aid_info['version_string'],
            consultant_dir=consultant_dir,
            consultant_id=consultant.id,
        )

        # Stufe 2 (Celery): DBEnricher + SkillGraphBuilder
        try:
            from apps.cv_extractor.tasks import enrich_consultant_task
            enrich_consultant_task.delay(consultant.id)
        except Exception as e: logger.warning(f"  Stufe 2: {e}")

        return {
            'success':    True,
            'aid':        aid,
            'name':       f"{first} {last}",
            'consultant': consultant.id,
            'created':    created,
            'editor_url': f'/cv-extractor/editor/{aid}/',
        }

    def _build_tech_counter_from_ram(self, experience_list: list,
                                      consultant) -> tuple:
        """
        Baut Tech-Counter aus experience_list (RAM, noch Dicts).
        Gibt (tech_counter, experience_map) zurück.

        experience_map: {skill_name: [Experience-DB-Objekt, ...]}
        Analog zu pipeline.py _build_tech_counter_from_ram().
        """
        tech_counter   = Counter()
        experience_map = defaultdict(list)

        # Experience-DB-Objekte laden (von extracted_to_db gerade geschrieben)
        exp_db_list = list(consultant.experience.all().order_by('sort_order'))

        for idx, exp_data in enumerate(experience_list):
            techs = exp_data.get('technologies', [])
            if not techs:
                continue
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

    def _merge(self, pre_json, pdf_data):
        merged = copy.deepcopy(pre_json)
        ed = merged.get('extracted_data',{})
        if not pdf_data: return merged
        if pdf_data.get('headline') and not merged['metadata'].get('headline'):
            merged['metadata']['headline']=pdf_data['headline']
        if pdf_data.get('position') and not merged['metadata'].get('headline'):
            merged['metadata']['headline']=pdf_data['position']
            ed['personal']['headline']=pdf_data['position']
        if not ed.get('experience') and pdf_data.get('projects'):
            ed['experience']=pdf_data['projects']
        elif ed.get('experience') and pdf_data.get('projects'):
            # PDF-Technologies nur ergaenzen wenn API-Projekt KEINE Technologies hat
            # API-Daten sind immer sauberer als PDF-Extraktion
            api_p, pdf_p = ed['experience'], pdf_data['projects']
            if len(api_p)==len(pdf_p):
                for i,(ap,pp) in enumerate(zip(api_p,pdf_p)):
                    api_techs = ap.get('technologies', [])
                    if api_techs:
                        # API hat bereits Technologies → PDF ignorieren
                        continue
                    # API hat keine Technologies → PDF-Technologies uebernehmen
                    # aber nur saubere (max 60 Zeichen, kein reiner Buchstaben-Blob)
                    ex = set()
                    for t in pp.get('technologies', []):
                        t = t.strip()
                        if not t or len(t) < 2 or len(t) > 60:
                            continue
                        if t.lower() not in ex:
                            api_p[i].setdefault('technologies', []).append(t)
                            ex.add(t.lower())
        ex_deg={e.get('degree','').lower() for e in ed.get('education',[])}
        for edu in pdf_data.get('education',[]):
            d=edu.get('degree','').lower()
            if d and d not in ex_deg: ed.setdefault('education',[]).append(edu); ex_deg.add(d)
        ex_cert={c.get('name','').lower() for c in ed.get('certifications',[])}
        for cert in pdf_data.get('certifications',[]):
            n=cert.get('name','').lower()
            if n and n not in ex_cert: ed.setdefault('certifications',[]).append(cert); ex_cert.add(n)
        api_sk=ed.get('skills',{})
        for cat,items in pdf_data.get('skills',{}).items():
            if cat not in api_sk: api_sk[cat]=[]
            ex={s.lower() for s in api_sk[cat]}
            for item in items:
                if item.lower() not in ex: api_sk[cat].append(item); ex.add(item.lower())
        ed['skills']=api_sk
        # industries: HTML-String → Python-Liste (alter pre_json)
        ind_raw = ed.get('industries', [])
        if isinstance(ind_raw, str):
            from apps.cv_extractor.services.url_gu_importer import GULPImporter
            ed['industries'] = GULPImporter()._parse_industries(ind_raw)
        # PUA-Clean auf industries
        PUA_RE = re.compile(r'[\ue000-\uf8ff\u25a1\u2610\u2611\u2612]')
        ed['industries'] = [
            PUA_RE.sub('', ind).strip()
            for ind in ed.get('industries', [])
            if ind and PUA_RE.sub('', ind).strip()
        ]
        ex_ind={i.lower() for i in ed.get('industries',[])}
        for ind in pdf_data.get('industries',[]):
            ind_clean = PUA_RE.sub('', ind).strip()
            if ind_clean and ind_clean.lower() not in ex_ind:
                ed.setdefault('industries',[]).append(ind_clean)
                ex_ind.add(ind_clean.lower())
        ex_f={f.lower() for f in ed.get('focus_experience',[])}
        for f in pdf_data.get('focus',[]):
            if f.lower() not in ex_f: ed.setdefault('focus_experience',[]).append(f); ex_f.add(f.lower())
        # Post-Processing: Technologies in allen Projekten bereinigen
        # Klammern splitten: "F5 BigIP (LTM" + "GTM)" → "F5 BigIP", "LTM", "GTM"
        # Semikolon splitten: "Nexus 3xxx; 5xxx; 7xxxx" → "Nexus 3xxx", "5xxx", "7xxxx"
        for exp in ed.get('experience', []):
            techs = exp.get('technologies', [])
            if not techs:
                continue
            cleaned = []
            for t in techs:
                t = t.strip()
                if not t:
                    continue
                # Semikolon splitten
                if ';' in t:
                    for part in t.split(';'):
                        part = part.strip()
                        if part and len(part) >= 2:
                            cleaned.append(part)
                    continue
                # Klammer-Fragment bereinigen: endet mit "(" oder beginnt mit ")"
                # z.B. "F5 BigIP Loadbalancer (LTM" → "F5 BigIP Loadbalancer", "LTM"
                # z.B. "GTM)" → "GTM"
                if '(' in t:
                    # Alles vor Klammer + Klammer-Inhalt als separate Tokens
                    before = re.sub(r'\s*\(.*', '', t).strip()
                    inside = re.search(r'\(([^)]*)', t)
                    if before and len(before) >= 2:
                        cleaned.append(before)
                    if inside:
                        for x in inside.group(1).split(','):
                            x = x.strip()
                            if x and len(x) >= 2:
                                cleaned.append(x)
                    continue
                if t.endswith(')'):
                    # Fragment wie "GTM)" → "GTM"
                    t = t.rstrip(')').strip()
                    if t and len(t) >= 2:
                        cleaned.append(t)
                    continue
                cleaned.append(t)
            # Deduplizieren
            seen, deduped = set(), []
            for t in cleaned:
                if t.lower() not in seen:
                    seen.add(t.lower())
                    deduped.append(t)
            exp['technologies'] = deduped

        merged['extracted_data']=ed
        return merged


gulp_db_importer = GULPDbImporter()
