"""
aid_regex_extractor.py — Regex-basierter Extraktor für abcona-eigene Qualifikationsprofile

Erkennt abcona-Profile (AID-xx_n.n.n.n + Bornhohl + abcona + Persönliche Daten)
und extrahiert direkt per Regex — OHNE LLM für Struktur/Labeling.

LLM wird nur noch gebraucht für:
  - skill_normalizer (Kategorisierung der Skills)
  - activities-Extraktion aus Projektbeschreibung (optional)
  - AID-Generierung

Einhängepunkt: main_pipeline_controller.run() nach Schritt 1 (Spans), vor Schritt 2 (LLM)

Aufruf:
  from apps.cv_extractor.extractors.aid_regex_extractor import aid_regex_extractor
  result = aid_regex_extractor.extract(text, first_name, last_name)
  # result['is_aid_profile'] → True/False
  # result['pre_json']       → fertig befülltes pre_json (wie labeled_to_prejson Output)

Abdeckung (aus Analyse von 2852 Profilen):
  Personal:        97%  (Name, Geburtsjahr, Sprachen, verfügbar, Ausbildung)
  Fachbereiche:    90%  (Schwerpunkt-Block)
  Branchen:        76%  (Branchen-Block)
  Zertifikate:     54%  (Zertifizierungen-Block)
  Skills-Tabellen: 44-71% (Betriebssysteme, Programmiersprachen, Datenbanken, ...)
  Projekte:        69%  (3/4 Labels: Zeitraum+Firma+Projektbeschreibung+Systemumgebung)
"""
import re
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── abcona-Erkennungs-Signale ────────────────────────────────────────────────
# Mind. 3 von 5 müssen matchen → sicheres abcona-Profil

ABCONA_SIGNALS = [
    re.compile(r'abcona',              re.IGNORECASE),
    re.compile(r'AID-[a-z]{2,4}_\d+'),  # tt_… und kea_/mva_/…
    re.compile(r'Bornhohl',            re.IGNORECASE),
    re.compile(r'office@abcona\.de',   re.IGNORECASE),
    re.compile(r'Pers.nliche\s+Daten', re.IGNORECASE | re.MULTILINE),
]

# ── Skill-Tabellen-Sektionen ─────────────────────────────────────────────────
# Alle bekannten abcona-Skill-Abschnitts-Header mit zugehöriger DB-Kategorie

SKILL_SECTIONS = [
    # (regex_pattern,              category_name,              skill_ablage_or_structured)
    (r'Programmiersprachen?',      'Programmiersprachen',      'structured'),
    (r'Betriebssysteme',           'Betriebssysteme',          'structured'),
    (r'Datenbanken',               'Datenbanken',              'structured'),
    (r'Hardware',                  'Hardware',                 'structured'),
    (r'Datenkommunikation',        'Datenkommunikation',       'structured'),
    (r'Webserver',                 'IT-Infrastruktur',         'structured'),
    (r'Middleware',                'IT-Infrastruktur',         'structured'),
    (r'Methoden',                  'Methoden',                 'structured'),
    (r'Tools?',                    'Sonstige Skills',          'structured'),
    (r'Netzwerk(?:protokolle)?',   'Netzwerkprotokolle',       'structured'),
    (r'Standards?',                'Spezielle Konzepte',       'structured'),
    (r'Verfahren',                 'Methoden',                 'structured'),
    (r'Entwicklungstools?',        'Entwicklungsumgebungen',   'structured'),
    (r'Softwaretechnologien?',     'Frameworks und Bibliotheken', 'structured'),
    (r'Modellierungstools?',       'Dokumentationstools',      'structured'),
    (r'Spezialkenntnisse',         'Sonstige Skills',          'structured'),
    (r'Application',               'Business Software',        'structured'),
    # Produkte|Standards|Erfahrungen → focus_experience (nicht skill_ablage)
    (r'Erfahrungen?\s+im\s+Bereich', 'Sonstige Skills',       'ablage'),
]

# abcona-Block „Produkte | Standards | Erfahrungen“ → FocusExperience
FOCUS_PRODUCTS_HEADER = (
    r'Produkte?\s*\|?\s*Standards?(?:\s*\|?\s*Erfahrungen?)?'
)

# Bekannte Abschnitts-Trennner die eine Skill-Sektion beenden
SECTION_ENDERS = re.compile(
    r'(?im)^\s*('
    r'Berufliche\s+Erfahrungen?|'
    r'Projektübersicht|'
    r'Berufserfahrung|'
    r'Zeitraum\s*:|'
    r'Firma\s*/\s*Institut\s*:|'
    r'Period\s*:|'
    r'Customer\s*:'
    r')\s*$'
)

# PDF-Symbol-Bullets (Wingdings/Symbol) + übliche Aufzählungszeichen
BULLET_PREFIX_RE = re.compile(
    r'^[\-\*\u2022\u25aa\u25cf\u25e6\u00b7•●○■▪▫►➢→'
    r'\uf09f\uf0b7\uf0a7\uf0d8\uf0a0]+\s*',
    re.UNICODE,
)

# Seitenkopf aus abcona-PDFs (leakt sonst in Branchen/Skills/Tech)
PAGE_HEADER_RE = re.compile(
    r'(?im)^\s*Qualifikationsprofil\s*:\s*AID-[a-z]{2,4}_[^\n]*$'
)

SECTION_NOISE_NAMES = {
    'zertifizierungen', 'schulungen', 'schulungen / kurse', 'schulungen/kurse',
    'examen', 'examen | prüfungen', 'examen|prüfungen', 'ausbildung',
    'fachbereiche', 'branchen', 'persönliche daten', 'berufliche erfahrungen',
    'programmiersprachen', 'programmiersprache', 'betriebssysteme', 'betriebsysteme',
    'hardware', 'datenkommunikation', 'datenbanken', 'allgemeine kenntnisse',
    'technische kenntnisse', 'sonstige skills', 'sonstige kenntnisse',
    'produkte | standards | erfahrungen', 'produkte|standards|erfahrungen',
    'sehr gute kenntnisse', 'fortgeschrittene kenntnisse', 'grundkenntnisse',
    'gute kenntnisse', 'netzwerkprotokolle', 'business software',
}

# reine Niveau-Zeilen in Produkte|Standards (kein Produktname)
NIVEAU_ONLY_RE = re.compile(
    r'(?i)^(sehr\s+gute|fortgeschrittene|gute|grund)\s*kenntnisse$'
)

# Deutsche Monatsnamen (bpf: „März 2021 – März 2022“)
DE_MONTHS = {
    'januar': 1, 'jan': 1,
    'februar': 2, 'feb': 2,
    'märz': 3, 'maerz': 3, 'mrz': 3, 'mär': 3,
    'april': 4, 'apr': 4,
    'mai': 5,
    'juni': 6, 'jun': 6,
    'juli': 7, 'jul': 7,
    'august': 8, 'aug': 8,
    'september': 9, 'sep': 9, 'sept': 9,
    'oktober': 10, 'okt': 10,
    'november': 11, 'nov': 11,
    'dezember': 12, 'dez': 12,
}
# Non-capturing: sonst bindet \s+\d{4} nur an die letzte Alternative (Dez)
DE_MONTH_ALT = (
    r'(?:Januar|Februar|M[äa]rz|April|Mai|Juni|Juli|August|'
    r'September|Oktober|November|Dezember|'
    r'Jan|Feb|Mrz|Apr|Jun|Jul|Aug|Sep|Sept|Okt|Nov|Dez)'
)

# Activity-/Satzfragmente die fälschlich als Technologie landen (bpf Soft-Wrap)
TECH_ACTIVITY_NOISE_RE = re.compile(
    r'(?i)(?<!\w)(?:'
    r'analyse|programmierung|migration|entwicklung|weiterentwicklung|'
    r'beratung|erstellung|anpassung|wartung|betreuung|optimierung|'
    r'fusion|redesign|unterstütz|dozent|bearbeitung|fehlerfall|'
    r'funktionalität|testing|programmänder|einsatzvorbereit|'
    r'abstimmung|fachabteilung|zusammenarbeit|deutschlandweit|'
    r'einberufung|kontaktgespräch|daten-?änderungs|software-?paket|'
    r'batchlauf|batchprogramm|online-?programm|kenntnis-?vermittlung|'
    r'sachversicherung|rentenversicherung|privathaftpflicht|'
    r'berufsunfähigkeit|altersvorsorge|hausrat|rechtsschutz|wohngebäude'
    r')'
)
TECH_FRAGMENT_RE = re.compile(
    r'(?i)^(lungen|gespräche|programmen|tungen|den|mit|der|die|das|'
    r'und|von|für|bei|aus|zur|zum|des|einem|eines)\b'
)

# bpf-Footer: nicht in letztes Projekt ziehen
WEITERE_PROJEKTE_RE = re.compile(
    r'(?im)^\s*Weitere\s+Projekte\s+und\s+Auftraggeber\b'
)


class AidRegexExtractor:
    """
    Regex-Extraktor für abcona-eigene Qualifikationsprofile.
    Liefert pre_json-kompatible Struktur ohne LLM.
    """

    def is_aid_profile(self, text: str) -> bool:
        """Prüft ob Text ein abcona-Profil ist (mind. 3 von 5 Signalen)."""
        hits = sum(1 for p in ABCONA_SIGNALS if p.search(text))
        return hits >= 3

    def name_from_dir(self, dir_name: str) -> Tuple[str, str]:
        """
        Extrahiert Vor- und Nachname aus Verzeichnisname.
        Format: nachname_vorname oder nachname_vorname-2
        Beispiele:
          ahmad_mashhood       → ('Mashhood', 'Ahmad')
          mueller_hans_peter   → ('Hans Peter', 'Mueller')  [Bindestrich-Vorname]
          troschke_thomas      → ('Thomas', 'Troschke')
        """
        # Suffix entfernen: -2, -3 etc.
        clean = re.sub(r'-\d+$', '', dir_name.strip())
        parts = clean.split('_')
        if len(parts) >= 2:
            last  = parts[0].capitalize()
            # Mehrsilbige Vornamen: mueller_hans_peter → Hans Peter
            first = ' '.join(p.capitalize() for p in parts[1:])
            # Bindestriche in Vornamen wiederherstellen wenn Original Bindestrich hat
            if '-' in dir_name.split('_', 1)[-1]:
                first = '-'.join(p.capitalize() for p in parts[1:])
            return first, last
        return '', dir_name.capitalize()

    # ── Text-Helpers (allgemein für alle AID-Profile) ─────────────────────────

    def _strip_page_headers(self, text: str) -> str:
        """Entfernt abcona-Seitenköpfe aus dem PDF-Text."""
        return PAGE_HEADER_RE.sub('', text or '')

    def _labeled_value(self, block: str, label_re: str) -> str:
        """
        Wert nach Label-Zeile: zuerst gleiche Zeile nach ':' ,
        sonst die nächste nicht-leere Zeile (solange sie kein neues Label ist).

        Wichtig für Format A mit Zeilenumbruch nach dem Label, z.B.:
          Zeitraum:
           11/2015 – dato
          Firma/Institut:
           Allianz, Zürich
        """
        if not block or not label_re:
            return ''
        m = re.search(rf'(?im)^\s*(?:{label_re})\s*:\s*(.*)$', block)
        if not m:
            return ''
        same = (m.group(1) or '').strip()
        if same:
            # Soft-Wrap: Wert endet mit - / und → nächste Zeile anhängen
            if re.search(r'(?i)(-|/|\bund)$', same):
                for line in block[m.end():].splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    if re.match(r'^[A-Za-zÄÖÜäöü0-9][^:\n]{0,80}:\s*', line):
                        break
                    if re.match(r'^[-•\*\u2022\u25aa]', line):
                        break
                    same = f'{same} {line}'.strip()
                    break
            return same
        for line in block[m.end():].splitlines():
            line = line.strip()
            if not line:
                continue
            # Nächstes Label (Wort…:) → kein Wert unter diesem Label
            if re.match(r'^[A-Za-zÄÖÜäöü0-9][^:\n]{0,80}:\s*', line):
                return ''
            return line
        return ''

    def _is_page_header(self, line: str) -> bool:
        return bool(PAGE_HEADER_RE.match((line or '').strip()))

    def _is_section_noise(self, name: str) -> bool:
        n = (name or '').strip().lower().rstrip(':')
        if not n or len(n) < 2:
            return True
        if self._is_page_header(name):
            return True
        if NIVEAU_ONLY_RE.match(n):
            return True
        if 'produkte' in n and 'standard' in n:
            return True
        return n in SECTION_NOISE_NAMES

    def _strip_bullet(self, line: str) -> Tuple[str, bool]:
        """Entfernt Bullet-Prefix. Returns (clean, had_bullet)."""
        raw = (line or '').strip()
        if not raw:
            return '', False
        m = BULLET_PREFIX_RE.match(raw)
        if m:
            return raw[m.end():].strip(), True
        # Sub-Bullets: "o Text" / "○ Text"
        m2 = re.match(r'^[oO]\s+(.+)$', raw)
        if m2:
            return m2.group(1).strip(), True
        return raw, False

    def _clean_item(self, line: str) -> str:
        clean, _ = self._strip_bullet(line)
        clean = re.sub(r'\s+', ' ', clean).strip()
        if self._is_section_noise(clean):
            return ''
        return clean

    def extract(self, text: str,
                first_name: str = '',
                last_name:  str = '',
                dir_name:   str = '') -> dict:
        """
        Hauptmethode — extrahiert alles per Regex aus dem PDF-Text.

        Returns:
            {
                'is_aid_profile': bool,
                'pre_json':       dict  (None wenn kein abcona-Profil)
                'coverage':       float (0-1, wie viel wurde extrahiert)
            }
        """
        if not self.is_aid_profile(text):
            return {'is_aid_profile': False, 'pre_json': None, 'coverage': 0.0}

        logger.info(f"[AidRegex] abcona-Profil erkannt: {first_name} {last_name}")

        # Seitenköpfe entfernen (leaken sonst in Branchen/Tech/Certs)
        text = self._strip_page_headers(text)

        # Name aus Verzeichnis wenn nicht übergeben
        if dir_name and (not first_name or not last_name):
            first_name, last_name = self.name_from_dir(dir_name)

        # pre_json Skelett aufbauen
        pre_json = self._make_pre_json_skeleton(first_name, last_name)

        # ── Extraktion ─────────────────────────────────────────────────────
        filled = []

        # 1. Personal
        personal = self._extract_personal(text, first_name, last_name)
        pre_json['extracted_data']['personal'] = personal
        if personal:
            filled.append('personal')

        # 2. Headline aus Schwerpunkt-Zeile
        headline = self._extract_headline(text)
        if headline:
            pre_json['metadata']['headline'] = headline
            pre_json['extracted_data']['personal']['headline'] = headline
            filled.append('headline')

        # 3. Fachbereiche (Schwerpunkt-Block)
        fachbereiche = self._extract_fachbereiche(text)
        if fachbereiche:
            pre_json['extracted_data']['focus_areas'] = fachbereiche
            filled.append('fachbereiche')

        # 4. Branchen (+ bpf Branchenkenntnisse aus Allgemeine Kenntnisse)
        branchen = self._extract_branchen(text)
        allg_skills, allg_branchen = self._extract_allgemeine_kenntnisse(text)
        if allg_branchen:
            seen_b = {b.lower() for b in branchen}
            for b in allg_branchen:
                if b.lower() not in seen_b:
                    branchen.append(b)
                    seen_b.add(b.lower())
        if branchen:
            pre_json['extracted_data']['industries'] = branchen
            filled.append('branchen')

        # 5. Zertifikate
        zertifikate = self._extract_zertifikate(text)
        if zertifikate:
            pre_json['extracted_data']['certifications'] = zertifikate
            filled.append('zertifikate')

        # 6. Ausbildung + Schulungen/Kurse
        ausbildung = self._extract_ausbildung(text)
        schulungen = self._extract_schulungen(text)
        education = list(ausbildung) + list(schulungen)
        if education:
            pre_json['extracted_data']['education'] = education
            # Degree-Fallback (nur saubere Ausbildung, nicht Schulung)
            for edu in ausbildung:
                if edu.get('education_type') == 'degree' and edu.get('degree'):
                    if not pre_json['extracted_data']['personal'].get('degree'):
                        pre_json['extracted_data']['personal']['degree'] = edu['degree']
                    break
            filled.append('ausbildung')

        # 7. Skill-Tabellen → skill_ablage (+ bpf Allgemeine Kenntnisse)
        skill_ablage = self._extract_skill_tables(text)
        if allg_skills:
            seen_s = {(s.get('name') or '').lower() for s in skill_ablage}
            for s in allg_skills:
                lw = (s.get('name') or '').lower()
                if lw and lw not in seen_s:
                    skill_ablage.append(s)
                    seen_s.add(lw)
        if skill_ablage:
            pre_json['extracted_data']['skill_ablage'] = skill_ablage
            filled.append(f'skills({len(skill_ablage)})')

        # 7b. Produkte | Standards | Erfahrungen → focus_experience
        focus_exp = self._extract_focus_experience(text)
        if focus_exp:
            pre_json['extracted_data']['focus_experience'] = focus_exp
            filled.append(f'focus_exp({len(focus_exp)})')

        # 8. Projekte
        projekte = self._extract_projekte(text)
        if projekte:
            pre_json['extracted_data']['experience'] = projekte
            filled.append(f'projekte({len(projekte)})')

        # 8b. Format-A ohne Skill-Tabellen: Tech aus Projekten nachziehen
        if not skill_ablage and projekte:
            harvested = self._harvest_skills_from_projects(projekte)
            if harvested:
                pre_json['extracted_data']['skill_ablage'] = harvested
                filled.append(f'skills_from_proj({len(harvested)})')
                skill_ablage = harvested

        # Coverage berechnen
        coverage = len(filled) / 9.0
        pre_json['audit']['regex_extractor'] = {
            'filled':   filled,
            'coverage': round(coverage, 2),
            'method':   'aid_regex',
        }

        logger.info(
            f"[AidRegex] Extraktion: {', '.join(filled)} | "
            f"coverage={coverage:.0%} | "
            f"{len(projekte)} Projekte | "
            f"{len(skill_ablage)} Skills"
        )

        return {
            'is_aid_profile': True,
            'pre_json':       pre_json,
            'coverage':       coverage,
        }

    # ── Persönliche Daten ─────────────────────────────────────────────────────

    def _extract_personal(self, text: str, first_name: str, last_name: str) -> dict:
        p = {}

        # Name aus Verzeichnis hat Vorrang
        if first_name: p['first_name'] = first_name
        if last_name:  p['last_name']  = last_name

        # Geburtsjahr / Jahrgang (Gulp-Stammdaten)
        m = re.search(r'(?im)^\s*(?:Geburtsjahr|Jahrgang)\s*:\s*(\d{4})', text)
        if m:
            p['birth_year'] = int(m.group(1))

        # Staatsangehörigkeit
        m = re.search(r'(?im)^\s*Staatsangeh\w+\s*:\s*(.+?)$', text)
        if m:
            p['nationality'] = m.group(1).strip()

        # Sprachen
        m = re.search(r'(?im)^\s*Sprachen?\s*:\s*(.+?)$', text)
        if m:
            raw = m.group(1).strip()
            langs = [l.strip() for l in re.split(r'[,;/]', raw) if l.strip()]
            p['languages'] = langs

        # Verfügbar
        m = re.search(r'(?im)^\s*Verf.gbar\s*(?:ab)?\s*:\s*(.+?)$', text)
        if m:
            p['availability'] = m.group(1).strip()

        # Einsatzort
        m = re.search(r'(?im)^\s*Einsatzort\s*:\s*(.+?)$', text)
        if m:
            p['location'] = m.group(1).strip()

        # Wohnort (Gulp) — ergänzt location falls Einsatzort leer
        m = re.search(r'(?im)^\s*Wohnort\s*:\s*(.+?)$', text)
        if m:
            wohn = m.group(1).strip()
            if wohn and not p.get('location'):
                p['location'] = wohn

        # Stundensatz (Gulp, optional Meta — nicht in Standard-Personal-Feldern)
        m = re.search(r'(?im)^\s*Stundensatz\s*:\s*(.+?)$', text)
        if m:
            p['hourly_rate'] = m.group(1).strip()

        # EDV Erfahrung seit
        m = re.search(r'(?im)^\s*EDV.Erfahrung\s*(?:seit)?\s*:\s*(.+?)$', text)
        if m:
            val = m.group(1).strip()
            # "31 Jahre" → berechnen, oder direkte Jahreszahl
            yr_m = re.search(r'\b(\d{4})\b', val)
            if yr_m:
                p['edv_experience_since'] = int(yr_m.group(1))
            else:
                jahre_m = re.search(r'(\d+)\s*Jahre?', val, re.IGNORECASE)
                if jahre_m:
                    p['edv_experience_since'] = datetime.now().year - int(jahre_m.group(1))

        return p

    # ── Headline ──────────────────────────────────────────────────────────────

    def _extract_headline(self, text: str) -> str:
        """
        Extrahiert mehrzeiligen Schwerpunkt aus abcona-Profilen.
        """
        # Mehrzeiliger Schwerpunkt bis zur naechsten Leerzeile oder "abcona"
        m = re.search(
            r'(?im)^\s*(?:Fachlicher\s+)?Schwerpunkt\s*:\s*(.+?)(?=\n\s*\n|\n\s*abcona|\Z)',
            text, re.DOTALL
        )
        if m:
            return ' '.join(m.group(1).split()).strip()
        return ''

    # ── Fachbereiche ──────────────────────────────────────────────────────────

    def _extract_fachbereiche(self, text: str) -> List[str]:
        """
        Extrahiert Fachbereiche aus dem Fachbereiche/Schwerpunkt-Block.
        Erkennt Bullet-Listen (•, -, *) und Zeilenblöcke.
        """
        # Block zwischen 'Fachbereiche' und nächster Hauptsektion finden
        block = self._extract_block(text, [
            r'Fachbereiche',
            r'Fachlicher\s+Schwerpunkt',
            r'Schwerpunkt\s*$',
            r'Position\s*$',
        ], stop_patterns=[
            r'Zertifizierungen?(?:\s*[\|/].*)?',
            r'IT.Kompetenzen?',
            r'Qualifikationen?',
            r'Berufliche\s+Erfahrungen?',
            r'Branchen?',
            r'Persönliche\s+St.rken?',
            r'TOP\s+Kenntnisse',
            r'Programmiersprachen?',
            r'Schulungen?\s*/\s*Kurse',
        ])

        if not block:
            return []

        items = self._parse_list_items(block, merge_wraps=True)
        # Fachbereiche: kurze Stichworte ODER 1–2 längere Absätze (Format A)
        return [i for i in items if 3 < len(i) < 400 and not self._is_section_noise(i)]

    # ── Branchen ──────────────────────────────────────────────────────────────

    def _extract_branchen(self, text: str) -> List[str]:
        block = self._extract_block(text, [r'Branchen?\s*$'], stop_patterns=[
            r'Betriebssysteme',
            r'Programmiersprachen?',
            r'Berufliche\s+Erfahrungen?',
            r'Zertifizierungen?(?:\s*[\|/].*)?',
            r'Produkte?\s*\|?\s*Standards?',
            r'Produkte',
            r'Hardware',
            r'Datenkommunikation',
            r'Schulungen?\s*/\s*Kurse',
            r'Allgemeine\s+Kenntnisse',
        ])
        if not block:
            return []
        items = self._parse_list_items(block, merge_wraps=True)
        out = []
        for item in items:
            if self._is_section_noise(item):
                continue
            # Komma-Liste in einer Zeile → einzeln
            if ',' in item and len(item) > 40:
                parts = [p.strip() for p in item.split(',') if p.strip()]
                if len(parts) >= 2 and all(len(p) < 60 for p in parts):
                    out.extend(parts)
                    continue
            out.append(item)
        # Dedup + Noise (Produkte|Standards / Niveau nie als Branche)
        seen, final = set(), []
        for i in out:
            if self._is_section_noise(i):
                continue
            lw = i.lower()
            if lw not in seen and 2 < len(i) < 80:
                seen.add(lw)
                final.append(i)
        return final

    def _extract_allgemeine_kenntnisse(self, text: str):
        """
        bpf „Allgemeine Kenntnisse“ → (skills[], branchen[]).
        Unterblöcke: Betriebssysteme, DB/DC, Programmiersprachen, Methoden,
        Branchenkenntnisse, Sonstige Kenntnisse.
        Span-Text: Header oft same-line mit Inhalt („Betriebssysteme   Mainframe: …“).
        """
        m = re.search(
            r'(?is)Allgemeine\s+Kenntnisse\s*(.*?)'
            r'(?=Durchgef[üu]hrte\s+Projekte|Berufliche\s+Erfahrungen?|\Z)',
            text or '',
        )
        if not m:
            return [], []
        body = m.group(1)
        headers = [
            (r'Betriebssysteme', 'Betriebssysteme'),
            (r'DB/?DC-Systeme', 'Datenbanken'),
            (r'Programmiersprachen?', 'Programmiersprachen'),
            (r'Methoden\s+und\s+Werkzeuge', 'Methoden'),
            (r'Branchenkenntnisse', '_branchen'),
            (r'Sonstige\s+Kenntnisse', 'Sonstige Skills'),
        ]
        # (start, content_start, cat, same_line_rest)
        positions = []
        for pat, cat in headers:
            hm = re.search(rf'(?im)^[ \t]*{pat}\b[ \t]*(.*)$', body)
            if hm:
                positions.append((hm.start(), hm.end(), cat, (hm.group(1) or '').strip()))
        positions.sort(key=lambda x: x[0])

        skills: List[dict] = []
        branchen: List[str] = []
        seen_s: set = set()

        for i, (_start, content_start, cat, same_line) in enumerate(positions):
            block_end = positions[i + 1][0] if i + 1 < len(positions) else len(body)
            block = ((same_line + '\n') if same_line else '') + body[content_start:block_end]
            if cat == '_branchen':
                for line in block.splitlines():
                    line = line.strip().rstrip(',')
                    if not line or self._is_page_header(line) or self._is_section_noise(line):
                        continue
                    # „Bank ca. 14 Jahre, ZV, …“ → Bank
                    bm = re.match(
                        r'^(.+?)\s+ca\.\s*\d+',
                        line, re.IGNORECASE,
                    )
                    name = (bm.group(1) if bm else line).strip().rstrip(',')
                    name = re.split(r'\s*,\s*', name)[0].strip()
                    if 2 < len(name) < 60 and name.lower() not in {b.lower() for b in branchen}:
                        branchen.append(name)
                continue

            for raw in self._parse_allg_skill_lines(block):
                lw = raw.lower()
                if lw in seen_s or self._is_section_noise(raw):
                    continue
                if re.search(r'(?i)weitere\s+projekte|auftraggeber', raw):
                    continue
                seen_s.add(lw)
                skills.append({'name': raw, 'category': cat})

        return skills, branchen

    def _parse_allg_skill_lines(self, block: str) -> List[str]:
        """Zeilen aus Allgemeine-Kenntnisse-Unterblock → Skill-Namen."""
        items: List[str] = []
        for line in (block or '').splitlines():
            line = line.strip().rstrip(',')
            if not line or len(line) < 2:
                continue
            if self._is_page_header(line) or self._is_section_noise(line):
                continue
            # „30 Jahre Erfahrung mit Cobol“ → Cobol
            em = re.match(
                r'(?i)^\d+\s+Jahre?\s+Erfahrung\s+mit\s+(.+)$',
                line,
            )
            if em:
                items.append(em.group(1).strip())
                continue
            # „Mainframe: MVS, z/OS“ → Prefixe behalten oder splitten
            if ':' in line and not line.endswith(':'):
                prefix, rest = line.split(':', 1)
                prefix, rest = prefix.strip(), rest.strip()
                if rest and ',' in rest:
                    for part in rest.split(','):
                        p = part.strip().rstrip('.,;')
                        if p:
                            label = f'{prefix}: {p}' if len(prefix) < 40 else p
                            items.append(label)
                    continue
                if rest:
                    items.append(line if len(line) < 80 else rest)
                    continue
            if ',' in line and len(line.split(',')) >= 2:
                for part in line.split(','):
                    p = part.strip().rstrip('.,;')
                    if not p or len(p) < 2:
                        continue
                    if re.match(r'(?i)^(usw\.?|auch\b)', p):
                        continue
                    items.append(p)
                continue
            # Fließtext / lange Beschreibungen kürzen
            if len(line) > 90:
                continue
            if re.match(r'(?i)^(tätigkeit|erstellung|qualität|modul|datenmigration)\b', line):
                # Methoden-Fließtext als Skill behalten wenn kurz genug
                if len(line) <= 60:
                    items.append(line)
                continue
            items.append(line)
        return items

    # ── Zertifikate ───────────────────────────────────────────────────────────

    def _extract_zertifikate(self, text: str) -> List[dict]:
        block = self._extract_block(text,
            start_patterns=[
                r'Zertifizierungen?\s*[\|:]?\s*(?:Schulungen?)?\s*$',
                r'Zertifikate?\s*[\|/]\s*Schulungen?\s*$',
                r'Zertifikate?\s*$',
            ],
            stop_patterns=[
                r'IT.Kompetenzen?',
                r'Berufliche\s+Erfahrungen?',
                r'Branchen?',
                r'Betriebssysteme',
                r'Programmiersprachen?',
                r'Fachbereiche',
                r'Examen(?:\s*[\|/].*)?',
                r'Schulungen?\s*/\s*Kurse',
                r'Hardware',
                r'Datenkommunikation',
            ]
        )
        if not block:
            return []

        certs = []
        seen = set()
        for line in block.splitlines():
            line = self._clean_item(line)
            if not line or len(line) < 3:
                continue
            # Datum am Anfang behalten (AID-Stil: "01/2015 CCNA …")
            date_obtained = ''
            dm = re.match(r'^(\d{1,2}/\d{4})\s+(.*)$', line)
            if dm:
                mm, yy = dm.group(1).split('/')
                date_obtained = f'{int(mm):02d}/{yy}'
                line = dm.group(2).strip()
            else:
                dm = re.match(r'^(\d{4})\s+(.*)$', line)
                if dm:
                    date_obtained = dm.group(1)
                    line = dm.group(2).strip()
            if self._is_section_noise(line) or len(line) < 3:
                continue
            # Komma-Liste kurzer Cert-Codes: "CCNA, CCDA, CCNP" → einzeln
            parts = [p.strip() for p in line.split(',') if p.strip()]
            if (len(parts) >= 2 and all(len(p) <= 40 for p in parts)
                    and all(re.match(r'^[A-Za-z0-9][A-Za-z0-9 \-+/&.]{1,39}$', p) for p in parts)):
                line_parts = parts
            else:
                line_parts = [line]
            for name in line_parts:
                lw = name.lower()
                if lw in seen or self._is_section_noise(name):
                    continue
                seen.add(lw)
                certs.append({
                    'name': name,
                    'issuer': '',
                    'date_obtained': date_obtained,
                })
        return certs

    def _extract_focus_experience(self, text: str) -> List[dict]:
        """
        Extrahiert „Produkte | Standards | Erfahrungen“ → focus_experience[].
        Gehört nicht in skill_ablage (R3/R7).
        """
        block = self._extract_block(
            text,
            start_patterns=[FOCUS_PRODUCTS_HEADER, r'Produkte\s*/\s*Standards?'],
            stop_patterns=[
                r'Berufliche\s+Erfahrungen?',
                r'Projektübersicht',
                r'Zeitraum\s*:',
                r'Programmiersprachen?',
                r'Betriebssysteme',
                r'Hardware',
                r'Datenkommunikation',
                r'Branchen?',
                r'Zertifizierungen?(?:\s*[\|/].*)?',
                r'Schulungen?\s*/\s*Kurse',
            ],
        )
        if not block:
            # Fallback: gleiche Header-Logik wie Skill-Sektionen
            block = self._extract_skill_section(text, FOCUS_PRODUCTS_HEADER)
        if not block:
            return []

        items = self._parse_skill_items(block)
        out, seen = [], set()
        for name in items:
            clean = (name or '').strip()
            if not clean or len(clean) < 2 or self._is_section_noise(clean):
                continue
            # Header-Reste verwerfen
            if re.match(r'(?i)^produkte?\b', clean) and 'standard' in clean.lower():
                continue
            lw = clean.lower()
            if lw in seen:
                continue
            seen.add(lw)
            if NIVEAU_ONLY_RE.match(clean):
                continue
            out.append({
                'name':       clean[:500],
                'category':   'product_standard',
                'sort_order': len(out),
            })
        return out

    def _extract_schulungen(self, text: str) -> List[dict]:
        """
        Extrahiert 'Schulungen / Kurse' als education_type=course.
        (Getrennt von Zertifizierungen, damit Kurse nicht als Cert landen.)
        """
        # Bevorzugt explizite Sektion "Schulungen / Kurse" (Troschke-Stil).
        # Bare "Schulungen" nur wenn nicht Teil von "Zertifizierungen | Schulungen".
        block = self._extract_block(text,
            start_patterns=[
                r'Schulungen?\s*/\s*Kurse\s*$',
            ],
            stop_patterns=[
                r'Branchen?',
                r'Berufliche\s+Erfahrungen?',
                r'Programmiersprachen?',
                r'Betriebssysteme',
                r'Hardware',
                r'Datenkommunikation',
                r'Zertifizierungen?',
                r'Fachbereiche',
                r'Produkte',
                r'Zeitraum\s*:',
                r'Firma\s*/\s*Institut\s*:',
                r'Netzwerkgrundlagen',
            ]
        )
        if not block:
            # Inline-Unterabschnitt "Schulungen" (z.B. am Profilende vor Projekten)
            m = re.search(
                r'(?im)^\s*Schulungen\s*$',
                text,
            )
            if m:
                # Nicht die kombinierte Zertifizierungen|Schulungen-Zeile
                line_start = text.rfind('\n', 0, m.start()) + 1
                header_line = text[line_start:m.end()]
                if 'zertifizierung' in header_line.lower():
                    block = ''
                else:
                    rest = text[m.end():]
                    stop = re.search(
                        r'(?im)^\s*(?:Zeitraum\s*:|Firma\s*/|Berufliche\s+Erfahrungen?|'
                        r'Programmiersprachen?|Betriebssysteme|Hardware|Branchen?|'
                        r'Netzwerkgrundlagen|Kunde\s*/|Projektbeschreibung\s*:)',
                        rest,
                    )
                    block = rest[:stop.start()] if stop else rest[:500]

        if not block:
            return []
        courses = []
        seen = set()
        for line in block.splitlines():
            line = self._clean_item(line)
            if not line or len(line) < 3 or self._is_section_noise(line):
                continue
            # Projekt-Labels nie als Kurs
            if re.match(
                r'(?i)^(zeitraum|firma|institut|projektbeschreibung|position|'
                r'rolle|systemumgebung|kunde)\b',
                line,
            ):
                break
            period = ''
            dm = re.match(r'^(\d{1,2}/\d{4})\s+(.*)$', line)
            if dm:
                mm, yy = dm.group(1).split('/')
                period = f'{int(mm):02d}/{yy}'
                line = dm.group(2).strip()
            else:
                dm = re.match(r'^(\d{4})\s+(.*)$', line)
                if dm:
                    period = dm.group(1)
                    line = dm.group(2).strip()
            if not line or len(line) < 3 or self._is_section_noise(line):
                continue
            lw = line.lower()
            if lw in seen:
                continue
            seen.add(lw)
            courses.append({
                'degree': line[:200],
                'institution': '',
                'period': period,
                'description': '',
                'education_type': 'course',
            })
        return courses

    # ── Ausbildung ────────────────────────────────────────────────────────────

    # Neuer Abschluss OHNE führendes Jahr (AID-stb u.ä.): nicht Soft-Wrap anhängen
    _NEW_EDU_LINE = re.compile(
        r'(?i)^(weiterbildung|fernstudium|studium\b|ausbildung\b|lehre\b|'
        r'bachelor|master|diplom|zertifikatskurs|'
        r'seit\s+(?:sommer|winter)semester|(?:sommer|winter)semester)\b'
    )

    def _semester_period_from_line(self, line: str) -> Tuple[str, str]:
        """
        Prosa-Zeitraum aus AID-Zeile ziehen, Rest bleibt degree.
        'Seit Sommersemester 2015, Fernstudium … Abschluss Wintersemester 2018/2019'
        → ('2015–2018/2019', 'Fernstudium …')
        """
        clean = re.sub(r'\s+', ' ', (line or '').strip())
        if not clean:
            return '', ''
        m = re.search(
            r'(?i)(?:seit\s+)?(?:sommer|winter)?semester\s+(\d{4})'
            r'.{0,120}?(?:sommer|winter)?semester\s+(\d{4}(?:/\d{2,4})?)',
            clean,
        )
        if not m:
            m2 = re.match(
                r'(?i)^seit\s+(?:sommer|winter)?semester\s+(\d{4})\s*[,:]?\s*(.+)$',
                clean,
            )
            if m2:
                return m2.group(1), m2.group(2).strip()
            return '', clean
        period = f'{m.group(1)}–{m.group(2)}'
        # leading "Seit Sommersemester YYYY," + trailing "voraussichtlicher Abschluss …"
        degree = clean
        degree = re.sub(
            r'(?i)^seit\s+(?:sommer|winter)?semester\s+\d{4}\s*[,:]?\s*',
            '', degree,
        )
        degree = re.sub(
            r'(?i),?\s*voraussichtlicher\s+abschluss\s+'
            r'(?:sommer|winter)?semester\s+\d{4}(?:/\d{2,4})?\s*$',
            '', degree,
        )
        degree = degree.strip(' ,;')
        return period, (degree or clean)

    def _extract_ausbildung(self, text: str) -> List[dict]:
        """
        Extrahiert Ausbildung aus 'Ausbildung:' Block.
        Unterstützt:
          - Zeitraum-Range: 1985 - 1989 Studium …
          - Einzeljahr: 1999 Ausbildung zum …
          - Ohne Jahr: eigene Zeilen (Weiterbildung / Fernstudium / Seit SS …)
          - Curriculum-Bullets unter dem Eintrag → description (nicht degree)
          - Soft-Wrap ohne Bullet → an degree anhängen (nur echte Umbrüche)
        """
        results = []
        # Block bis nächste Sektion (Fachbereiche / Zertifizierungen / …)
        m = re.search(
            r'(?im)^\s*Ausbildung\s*:\s*(.+?)'
            r'(?=\n\s*(?:Fachbereiche|Zertifizierungen|Examen|Schulungen|'
            r'Branchen|Programmiersprachen|Persönliche\s+Daten|'
            r'Berufliche\s+Erfahrungen?|Betriebssysteme|Hardware|'
            r'Allgemeine\s+Kenntnisse|Technische\s+Kenntnisse)\b|\Z)',
            text, re.DOTALL,
        )
        if not m:
            return results
        raw = m.group(1).strip()

        entries = []  # {degree, period, description_parts}
        for line in raw.splitlines():
            line = line.strip()
            if not line or self._is_page_header(line):
                continue
            clean, had_bullet = self._strip_bullet(line)
            if not clean:
                continue
            if self._is_section_noise(clean):
                continue

            # Neuer Eintrag: Jahres-Range oder Einzeljahr am Anfang
            pm = re.match(
                r'^(\d{4}\s*[-–—]\s*(?:\d{4}|heute|dato))\s+(.+)$',
                clean, re.IGNORECASE,
            )
            sm = None if pm else re.match(r'^(\d{4})\s+(.+)$', clean)
            if pm or sm:
                period = re.sub(r'\s+', ' ', (pm or sm).group(1)).strip()
                degree = (pm or sm).group(2).strip()
                entries.append({
                    'degree': degree,
                    'period': period,
                    'institution': '',
                    'description_parts': [],
                })
                continue

            # Neuer Abschluss ohne führendes Kalenderjahr (nicht Soft-Wrap!)
            if (not entries) or self._NEW_EDU_LINE.match(clean):
                period, degree = self._semester_period_from_line(clean)
                if not period:
                    period, degree = '', clean
                entries.append({
                    'degree': degree,
                    'period': period,
                    'institution': '',
                    'description_parts': [],
                })
                continue

            # Bullet unter Ausbildung = Curriculum/Schwerpunkt, nicht Degree
            if had_bullet:
                if re.match(
                    r'(?i)^(programmiersprachen?|betriebssysteme|hardware|'
                    r'datenbanken|netzwerk|fachbereiche)\b',
                    clean,
                ):
                    if re.match(
                        r'(?i)^(programmiersprachen?|betriebssysteme|hardware|'
                        r'datenbanken|netzwerk|fachbereiche)\s*$',
                        clean,
                    ):
                        continue
                entries[-1]['description_parts'].append(clean)
                continue

            # Institution-Zeile (SGZ Bank AG, Frankfurt …) — nicht an Degree kleben
            if (
                not entries[-1].get('institution')
                and re.search(
                    r'(?i)\b(AG|GmbH|e\.?\s*K\.?|KG|Ltd|Inc|Bank|Universität|'
                    r'Hochschule|Schule|Akademie)\b',
                    clean,
                )
                and not re.search(r'(?i)\b(ausbildung|studium|lehre|diplom|bachelor|master)\b', clean)
            ):
                entries[-1]['institution'] = clean[:200]
                continue

            # Soft-Wrap: an degree anhängen (nur echte Zeilenumbrüche mittendrin)
            entries[-1]['degree'] = (entries[-1]['degree'] + ' ' + clean).strip()

        for e in entries:
            degree = re.sub(r'\s+', ' ', e['degree']).strip()
            if len(degree) < 3:
                continue
            period = (e['period'] or '').strip()
            # Soft-Wrap kann "… Abschluss Wintersemester 2018/2019" nachreichen
            if re.search(r'(?i)(?:sommer|winter)semester|\b\d{4}\b', degree):
                probe = degree
                if not re.match(r'(?i)^seit\b', probe):
                    if re.fullmatch(r'\d{4}', period or ''):
                        probe = f'Seit Sommersemester {period}, {degree}'
                    elif not period:
                        probe = degree
                p2, d2 = self._semester_period_from_line(probe)
                if p2:
                    period = p2
                    if d2:
                        degree = d2
            results.append({
                'degree': degree[:200],
                'institution': (e.get('institution') or '')[:200],
                'period': period[:200],
                'description': '; '.join(e['description_parts'])[:300],
                'education_type': 'degree',
            })
        return results

    # ── Skill-Tabellen ────────────────────────────────────────────────────────


    def _extract_skill_tables(self, text: str, spans: list = None) -> list:
        """
        Extrahiert Skill-Tabellen aus abcona-Profilen.

        Strategie:
          1. Spans vorhanden → Y-Abstand-Logik (präzise Block-Grenzen)
          2. Nur Text → Regex-Fallback (bisherige Methode)

        Nach Block-Extraktion:
          - Block-Inhalt gegen TrainingTerm DB matchen
          - Wenn 70%+ matchen → Kategorie sicher
          - Neue unbekannte Terms werden in DB importiert (self-learning)
        """
        if spans:
            return self._extract_skill_tables_by_y(spans)
        else:
            return self._extract_skill_tables_by_regex(text)

    def _extract_skill_tables_by_y(self, spans: list) -> list:
        """
        Y-Abstand-basierte Skill-Extraktion aus Span-Liste.
        Zeilenjoin wie _spans_to_aid_lines: gleiche gerundete Y (+ page/col),
        verschiedene Y nie verkleben (kein abs(diff)>3).
        """
        all_skills = []
        seen_lower = set()

        STOP = re.compile(
            r'^(berufliche\s+erfahrungen?|zeitraum\s*:|period\s*:|'
            r'firma\s*/|customer\s*:|projektübersicht|'
            r'produkte?\s*\|?\s*standards?)',
            re.IGNORECASE
        )

        def _col_key(s):
            c = s.get('column_id', -1)
            try:
                c = int(c)
            except (TypeError, ValueError):
                c = -1
            return c if c >= 0 else 99

        # Zeilen wie Controller-1b: page/col/y exakt (nach /3-Rundung)
        lines = []
        last_y = last_page = last_col = None
        cur_line_spans = []
        sorted_spans = sorted(
            spans or [],
            key=lambda x: (
                _col_key(x),
                int(x.get('page', 1) or 1),
                round(float(x.get('y', 0) or 0) / 3) * 3,
                float(x.get('x', 0) or 0),
            ),
        )
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
                if cur_line_spans:
                    lines.append(cur_line_spans)
                cur_line_spans = [s]
                last_y, last_page, last_col = y, pg, col
            else:
                cur_line_spans.append(s)
        if cur_line_spans:
            lines.append(cur_line_spans)

        # Header-Mapping (Produkte|Standards bewusst nicht — → focus_experience)
        HEADER_TO_CAT = {
            'betriebssysteme':     'Betriebssysteme',
            'betriebsysteme':      'Betriebssysteme',
            'programmiersprachen': 'Programmiersprachen',
            'programmiersprache':  'Programmiersprachen',
            'datenbanken':         'Datenbanken',
            'datenbank':           'Datenbanken',
            'hardware':            'Hardware',
            'datenkommunikation':  'Datenkommunikation',
            'netzwerkprotokolle':  'Netzwerkprotokolle',
            'methoden':            'Methoden',
            'tools':               'Sonstige Skills',
            'technologien':        'Frameworks und Bibliotheken',
            'software':            'Business Software',
            'kenntnisse':          'Sonstige Skills',
            'werkzeuge':           'Entwicklungsumgebungen',
            'dv-umfeld':           'IT-Infrastruktur',
            'entwicklungstools':   'Entwicklungsumgebungen',
            'webserver':           'IT-Infrastruktur',
            'middleware':          'IT-Infrastruktur',
            'frameworks':          'Frameworks und Bibliotheken',
            'spezialkenntnisse':   'Spezielle Konzepte',
        }

        def get_line_text(line_spans):
            return ' '.join(s.get('text','').strip() for s in line_spans).strip()

        def is_header(line_spans):
            t = get_line_text(line_spans).strip().rstrip(':').lower()
            t = re.sub(r'\s*:+\s*$', '', t).strip()
            return HEADER_TO_CAT.get(t)

        def get_y(line_spans):
            return line_spans[0].get('y', 0) if line_spans else 0

        i = 0
        while i < len(lines):
            line = lines[i]
            line_text = get_line_text(line)

            # STOP-Wort → abbrechen
            if STOP.match(line_text):
                break

            cat = is_header(line)
            if cat:
                # Block einlesen per Y-Abstand
                block_items = []
                normal_dy = None
                j = i + 1

                while j < len(lines):
                    curr = lines[j]
                    curr_text = get_line_text(curr)

                    if STOP.match(curr_text):
                        break

                    # Nächster Header → Block Ende
                    if is_header(curr):
                        break

                    dy = get_y(curr) - get_y(lines[j-1])

                    # normal_dy lernen aus Eintrag 1→2
                    if normal_dy is None and j > i + 1 and dy > 2:
                        normal_dy = dy
                    elif normal_dy and dy > normal_dy * 1.5:
                        break  # Block Ende

                    if curr_text.strip():
                        block_items.append(curr_text)
                    j += 1

                # Block gegen TrainingTerm DB validieren + self-learning
                validated_cat = self._validate_and_learn(block_items, cat)

                # Skills extrahieren
                for raw in block_items:
                    for skill in self._parse_skill_items(raw):
                        lw = skill.lower()
                        if lw not in seen_lower and len(skill) >= 2:
                            seen_lower.add(lw)
                            all_skills.append({
                                'name':     skill,
                                'category': validated_cat,
                            })
                i = j
            else:
                i += 1

        return all_skills

    def _validate_and_learn(self, block_items: list, suggested_cat: str) -> str:
        """
        Validiert Block-Kategorie gegen TrainingTerm DB.
        - 70%+ Match → Kategorie bestätigt
        - Neue Terms → in DB importieren (self-learning)
        - Gibt finale Kategorie zurück
        """
        try:
            from apps.cv_extractor.models import TrainingTerm
            from collections import Counter

            # Alle Terms aus Block extrahieren
            all_terms = []
            for raw in block_items:
                for skill in self._parse_skill_items(raw):
                    if skill and len(skill) >= 2:
                        all_terms.append(skill.strip())

            if not all_terms:
                return suggested_cat

            # Gegen DB matchen
            matched_cats = Counter()
            matched_terms = set()
            unmatched = []

            for term in all_terms:
                t = TrainingTerm.objects.filter(term__iexact=term).first()
                if t:
                    matched_cats[t.category] += 1
                    matched_terms.add(term.lower())
                else:
                    unmatched.append(term)

            total = len(all_terms)
            matched = sum(matched_cats.values())
            match_ratio = matched / total if total > 0 else 0

            # Beste Kategorie aus DB
            if matched_cats:
                best_cat = matched_cats.most_common(1)[0][0]
            else:
                best_cat = suggested_cat

            # 70%+ Match → Kategorie aus DB nehmen
            final_cat = best_cat if match_ratio >= 0.7 else suggested_cat

            # Self-learning: neue Terms in DB importieren
            if match_ratio >= 0.7 and unmatched:
                added = 0
                for term in unmatched:
                    if len(term) >= 2 and len(term) <= 100:
                        try:
                            TrainingTerm.objects.get_or_create(
                                term=term,
                                defaults={
                                    'category':   final_cat,
                                    'confidence': 0.75,
                                    'frequency':  1,
                                    'source':     'self_learning',
                                }
                            )
                            added += 1
                        except Exception:
                            pass
                if added:
                    logger.debug(f"[AidRegex] Self-learning: +{added} neue Terms in '{final_cat}'")

            return final_cat

        except Exception as e:
            logger.warning(f"[AidRegex] _validate_and_learn Fehler: {e}")
            return suggested_cat

    def _extract_skill_tables_by_regex(self, text: str) -> list:
        """Fallback: Regex-basierte Skill-Extraktion (alter Code)."""
        all_skills = []
        seen_lower = set()
        for pattern, category, mode in SKILL_SECTIONS:
            block = self._extract_skill_section(text, pattern)
            if not block:
                continue
            items = self._parse_skill_items(block)
            for item in items:
                item_clean = item.strip()
                if not item_clean or len(item_clean) < 2:
                    continue
                lw = item_clean.lower()
                if lw not in seen_lower:
                    seen_lower.add(lw)
                    all_skills.append({
                        'name':     item_clean,
                        'category': category,
                    })
        return all_skills

    def _extract_skill_section(self, text: str, section_pattern: str) -> str:
        """Extrahiert Inhalt einer Skill-Sektion bis zur nächsten Sektion."""
        # Sektion-Header finden
        start_re = re.compile(
            r'(?im)^\s*' + section_pattern + r'\s*$'
        )
        m = start_re.search(text)
        if not m:
            return ''

        start = m.end()
        rest  = text[start:]

        # Nächste Skill-Sektion, Produkte|Standards oder Berufliche Erfahrungen
        next_section = re.compile(
            r'(?im)^\s*('
            r'Programmiersprachen?|Betriebssysteme|Datenbanken|Hardware|'
            r'Datenkommunikation|Webserver|Middleware|Methoden(?:\s+und\s+Werkzeuge)?|Tools?|'
            r'DB/?DC-Systeme|Branchenkenntnisse|Sonstige\s+Kenntnisse|'
            r'Netzwerk(?:protokolle)?|Standards?|Verfahren|Entwicklungstools?|'
            r'Softwaretechnologien?|Modellierungstools?|Spezialkenntnisse|'
            r'Application|'
            + FOCUS_PRODUCTS_HEADER + r'|'
            r'Erfahrungen?\s+im\s+Bereich|'
            r'Berufliche\s+Erfahrungen?|Durchgef[üu]hrte\s+Projekte|'
            r'Projektübersicht|Zeitraum\s*:'
            r')\s*$'
        )
        end_m = next_section.search(rest)
        block = rest[:end_m.start()] if end_m else rest[:2000]
        return block.strip()

    def _parse_skill_items(self, block: str) -> List[str]:
        """
        Parst Skill-Einträge aus einem Block.
        Unterstützt:
        - Einfache Zeilen: "Java\nPython\nC++"
        - Komma-getrennt: "Java, Python, C++"
        - Mit Niveau-Spalte: "Java    Sehr gut    16"  → nur "Java"
        """
        items = []

        for line in block.splitlines():
            line = line.strip()
            if not line or len(line) < 2:
                continue

            # Zeilen mit Niveau-Tabelle: "Java  Sehr gut  16" oder "Java  Gut  3"
            # → ersten Teil nehmen
            niveau_match = re.match(
                r'^(.+?)\s{2,}(?:Sehr gut|Gut|Grundkenntnisse|Experte|'
                r'Expert|Good|Basic|Fortgeschritten)\b',
                line, re.IGNORECASE
            )
            if niveau_match:
                items.append(niveau_match.group(1).strip())
                continue

            # Komma-getrennte Listen
            if ',' in line and len(line.split(',')) >= 2:
                for part in line.split(','):
                    p = part.strip().rstrip('.,;')
                    if p and len(p) >= 2:
                        items.append(p)
                continue

            # Einzelne Zeile
            clean, _ = self._strip_bullet(line)
            if clean and len(clean) >= 2 and not self._is_page_header(clean) and not self._is_section_noise(clean):
                items.append(clean)

        # Kategorie-Header nie als Skill-Name
        return [i for i in items if not self._is_section_noise(i)]

    # ── Projekte ──────────────────────────────────────────────────────────────

    def _normalize_period_token(self, token: str) -> str:
        """'März 2021' / 'Ende 2009' / '03/2021' → '03/2021' bzw. '12/2009'."""
        t = re.sub(r'\s+', ' ', (token or '').strip())
        if not t:
            return ''
        low = t.lower()
        if low in ('heute', 'dato', 'aktuell', 'laufend'):
            return 'dato'
        m = re.match(r'(?i)^ende\s+(\d{4})$', t)
        if m:
            return f'12/{m.group(1)}'
        m = re.match(rf'(?i)^({DE_MONTH_ALT})\s+(\d{{4}})$', t)
        if m:
            key = m.group(1).lower()
            num = DE_MONTHS.get(key)
            if num is None and 'ä' in key:
                num = DE_MONTHS.get(key.replace('ä', 'ae'))
            if num is None and key == 'maerz':
                num = 3
            if num:
                return f'{num:02d}/{m.group(2)}'
        m = re.match(r'^(\d{1,2})[./](\d{4})$', t)
        if m:
            return f'{int(m.group(1)):02d}/{m.group(2)}'
        m = re.match(r'^(\d{4})$', t)
        if m:
            return m.group(1)
        return t

    def _format_period(self, start: str, end: str = '') -> str:
        s = self._normalize_period_token(start)
        e = self._normalize_period_token(end) if end else ''
        if s and e:
            return f'{s} – {e}'
        return s or end

    def _match_period_line(self, line: str):
        """Parst Periodenzeile → (period_norm, company_same_line) oder None."""
        raw = (line or '').strip()
        if not raw:
            return None
        m = re.match(
            r'(?i)^(\d{1,2}[./]\d{4})\s*[-\u2013\u2014]+\s*'
            r'(\d{1,2}[./]\d{4}|heute|dato|aktuell|laufend)\s*(.*)$',
            raw,
        )
        if m:
            return self._format_period(m.group(1), m.group(2)), (m.group(3) or '').strip()
        m = re.match(
            rf'(?i)^({DE_MONTH_ALT}\s+\d{{4}})\s*[-\u2013\u2014]+\s*'
            rf'({DE_MONTH_ALT}\s+\d{{4}}|Ende\s+\d{{4}}|heute|dato)\s*(.*)$',
            raw,
        )
        if m:
            return self._format_period(m.group(1), m.group(2)), (m.group(3) or '').strip()
        m = re.match(
            rf'(?i)^Seit\s+(?:({DE_MONTH_ALT})\s+)?(\d{{4}})'
            rf'(?:\s+parallel)?\s*(.*)$',
            raw,
        )
        if m:
            start = f'{m.group(1)} {m.group(2)}' if m.group(1) else m.group(2)
            return self._format_period(start, 'dato'), (m.group(3) or '').strip()
        # bpf: alleinstehende Periode „12/2004“ (Firma nächste Zeile)
        m = re.match(r'^(\d{1,2}[./]\d{4})\s*$', raw)
        if m:
            return self._format_period(m.group(1)), ''
        m = re.match(r'^(\d{1,2}[./]\d{4})\s{2,}(.+)$', raw)
        if m:
            return self._format_period(m.group(1)), (m.group(2) or '').strip()
        return None

    def _projects_region_start(self, text: str) -> int:
        """Zeichenoffset Start der Projektregion (oder -1)."""
        for pat in (
            r'(?im)^\s*Berufliche\s+Erfahrungen?\s*$',
            r'(?im)^\s*Durchgef[üu]hrte\s+Projekte\s*$',
            r'(?im)^\s*Zeitraum\s*:',
        ):
            m = re.search(pat, text)
            if m:
                return m.start()
        pos = 0
        for line in text.splitlines(keepends=True):
            if self._match_period_line(line.rstrip('\r\n')):
                return pos
            pos += len(line)
        return -1

    def _extract_projekte(self, text: str) -> List[dict]:
        """
        Extrahiert Projekte (Format A oder B/bpf mit DE-Monaten).
        Start: Berufliche Erfahrungen | Durchgeführte Projekte | erste Periode.
        """
        start = self._projects_region_start(text or '')
        if start < 0:
            return []

        proj_text = text[start:]
        footer = ''
        w = WEITERE_PROJEKTE_RE.search(proj_text)
        if w:
            footer = proj_text[w.start():]
            proj_text = proj_text[:w.start()]

        has_format_a = bool(re.search(r'(?im)^\s*Zeitraum\s*:', proj_text))
        has_format_b = any(self._match_period_line(ln) for ln in proj_text.splitlines())

        projekte: List[dict] = []
        if has_format_a:
            projekte = self._extract_projekte_format_a(proj_text)
        if not projekte and has_format_b:
            projekte = self._extract_projekte_format_b(proj_text)
        if footer:
            projekte.extend(self._extract_weitere_projekte(footer))

        logger.debug(f"[AidRegex] {len(projekte)} Projekte extrahiert")
        return projekte

    def _dedupe_title_activity_stub(self, proj: dict) -> None:
        """Erste Activity entfernen wenn sie schon im Title steckt (Soft-Wrap-Rest)."""
        title = re.sub(r'\s+', ' ', (proj.get('title') or '').strip())
        acts = list(proj.get('activities') or [])
        if not title or not acts:
            return
        t = title.rstrip(':').lower()
        while acts:
            a0 = re.sub(r'\s+', ' ', (acts[0] or '').strip()).rstrip(':')
            if not a0:
                acts = acts[1:]
                continue
            al = a0.lower()
            if al in t or t.endswith(al) or (len(al) >= 12 and al[:40] in t):
                acts = acts[1:]
                continue
            break
        proj['activities'] = acts

    def _extract_projekte_format_a(self, text: str) -> List[dict]:
        """
        Format A: Tabellarisch mit 'Zeitraum:' Label.
        Trenner: nächstes 'Zeitraum:' oder Ende
        """
        projekte = []

        # Alle Zeitraum-Positionen finden
        zeitraum_iter = re.finditer(r'(?im)^\s*Zeitraum\s*:', text)
        positions = [m.start() for m in zeitraum_iter]

        for i, pos in enumerate(positions):
            end = positions[i+1] if i+1 < len(positions) else len(text)
            block = text[pos:end]

            proj = self._parse_projekt_block_a(block)
            if proj:
                self._extend_soft_wrapped_role(proj, block)
                self._extend_soft_wrapped_title(proj)
                self._dedupe_title_activity_stub(proj)
                self._projektbeschreibung_to_activities(proj, block)
                projekte.append(proj)

        return projekte

    def _parse_projekt_block_a(self, block: str) -> Optional[dict]:
        """Parst einen einzelnen Projekt-Block im Format A."""
        proj = {}

        # Zeitraum (gleiche Zeile oder nächste Zeile)
        period = self._labeled_value(block, r'Zeitraum|Period')
        if period:
            proj['period'] = period

        # Firma/Institut / Kunde (gleiche Zeile oder nächste Zeile)
        company = (
            self._labeled_value(block, r'Firma\s*/?\s*Institut')
            or self._labeled_value(block, r'Kunde\s*/\s*Branche')
            or self._labeled_value(block, r'Auftraggeber|Kunde|Customer')
        )
        if company:
            proj['company'] = company

        # Projektbeschreibung / Projekttätigkeiten → title (ohne Activity-Bullets)
        # Wichtig: \Z statt $ — bei (?m) würde $ nach der ersten Soft-Wrap-Zeile stoppen
        m = re.search(
            r'(?im)^\s*(?:Projektbeschreibung|Projekttätigkeiten|Projekttatigkeiten)\s*:\s*(.+?)'
            r'(?=\n\s*(?:Systemumgebung|Position|Rolle|Zeitraum|Firma|Kunde|'
            r'Protokolle|Technologien|Eingesetzte)\s*:|'
            r'\n\s*[-•\*\u2022\u25aa\uf0b7\uf09f]|\Z)',
            block, re.DOTALL
        )
        if m:
            title = ' '.join(m.group(1).split())  # Whitespace normalisieren
            if title:
                proj['title'] = title[:300]
        if not proj.get('title'):
            # Label allein, Text beginnt nächste Zeile
            title = self._labeled_value(
                block, r'Projektbeschreibung|Projekttätigkeiten|Projekttatigkeiten'
            )
            if title:
                proj['title'] = title[:300]

        # Position / Rolle (inkl. abcona Rolle / Position)
        role = (
            self._labeled_value(block, r'Rolle\s*/\s*Position')
            or self._labeled_value(block, r'Position|Rolle|Projektrolle|Funktion')
        )
        if role:
            proj['role'] = role

        # Branche
        industry = self._labeled_value(block, r'Branche')
        if industry:
            proj['industry'] = industry

        # Systemumgebung / Produkte / Tools → technologies[]
        tech_parts = []
        for label in (
            r'Systemumgebung',
            r'Eingesetzte\s+Produkte',
            r'Eingesetzte\s+Tools\s*/\s*Software',
            r'Eingesetzte\s+Tools',
            r'Protokolle\s*/\s*Technologien',
            r'Technologien\s*/\s*Umfeld',
            r'Technologien\s*/?\s*Umfeld',
            r'Kenntnisse',
        ):
            m = re.search(
                rf'(?im)^\s*{label}\s*:\s*(.+?)'
                r'(?=\n\s*(?:Position|Rolle|Zeitraum|Firma|Kunde|Systemumgebung|'
                r'Eingesetzte\s+|Protokolle\s*/|Technologien\s*/|Kenntnisse|'
                r'Projektbeschreibung)\s*:|\Z)',
                block, re.DOTALL,
            )
            if m:
                chunk = (m.group(1) or '').strip()
                if chunk:
                    tech_parts.append(chunk)
                else:
                    # leeres Label → Folgetext bis zum nächsten Label
                    val = self._labeled_value(block, label)
                    if val:
                        tech_parts.append(val)
        if tech_parts:
            techs = self._parse_tech_list('\n'.join(tech_parts))
            if techs:
                proj['technologies'] = techs

        # activities: Bullet-Liste unter Projektbeschreibung (inkl. Soft-Wraps)
        act_block = ''
        m_act = re.search(
            r'(?is)(?:^|\n)\s*(?:Projektbeschreibung|Projekttätigkeiten|Projekttatigkeiten)\s*:\s*.*?\n(.*?)'
            r'(?=\n\s*(?:Systemumgebung|Protokolle\s*/\s*Technologien|'
            r'Technologien\s*/|Position|Rolle|Zeitraum|Firma|Kunde)\s*:|\Z)',
            block,
        )
        if m_act:
            act_block = m_act.group(1)
        if act_block:
            acts = self._parse_list_items(act_block, merge_wraps=True)
            acts = [a for a in acts if len(a) > 5]
            if acts:
                proj['activities'] = acts
        else:
            bullets = re.findall(
                r'(?m)^[\s]*[-•\*\u2022\u25aa\uf0b7\uf09f]\s*(.+?)$',
                block,
            )
            if bullets:
                acts = []
                for b in bullets:
                    clean, _ = self._strip_bullet(b.strip())
                    clean = re.sub(r'\s+', ' ', clean).strip()
                    if len(clean) > 5 and not self._is_page_header(clean):
                        acts.append(clean)
                if acts:
                    proj['activities'] = acts

        # Abschluß/Abschluss (häufig bei Weiterbildung) → Activity erzwingen
        self._append_abschluss_activities(proj, block)

        # Weiterbildung ohne Bullets: Titel als Activity behalten (darf nicht wegfallen)
        self._ensure_weiterbildung_content(proj)

        # R1: wie _usable_experience — Firma/Rolle/Acts/Tech ohne period behalten
        if not self._usable_project(proj):
            return None

        return proj

    def _usable_project(self, proj: dict) -> bool:
        """True wenn das Projekt mindestens ein sinnvolles Feld hat."""
        if not isinstance(proj, dict):
            return False
        return bool(
            (proj.get('period') or '').strip()
            or (proj.get('company') or '').strip()
            or (proj.get('role') or '').strip()
            or (proj.get('title') or '').strip()
            or proj.get('activities')
            or proj.get('technologies')
        )

    def _period_block_to_format_a(self, block: str, period_str: str) -> str:
        """Periodenzeile → 'Zeitraum:' damit Format-A-Parser greift (OV)."""
        lines = (block or '').splitlines()
        if lines and self._match_period_line(lines[0]):
            return '\n'.join([f'Zeitraum: {period_str}'] + lines[1:])
        return f'Zeitraum: {period_str}\n{block}'

    def _extend_soft_wrapped_role(self, proj: dict, block: str) -> None:
        """Position/Rolle Soft-Wrap: '... Börseninformations- und\\nHandelssyteme'."""
        role = (proj.get('role') or '').rstrip()
        if not role or not re.search(r'(?i)(-|/|\bund)$', role):
            return
        m = re.search(
            r'(?im)^\s*(?:Rolle\s*/\s*Position|Position|Rolle|Projektrolle|Funktion)\s*:\s*(.*)$',
            block,
        )
        if not m:
            return
        for line in block[m.end():].splitlines():
            line = line.strip()
            if not line:
                continue
            if re.match(r'^[A-Za-zÄÖÜäöü0-9][^:\n]{0,80}:\s*', line):
                break
            if re.match(r'^[-•\*\u2022\u25aa]', line):
                break
            # Fortsetzung der Soft-Wrap-Zeile (kein neuer Satzanfang mit Groß+lang)
            proj['role'] = f'{role} {line}'.strip()
            break

    def _extend_soft_wrapped_title(self, proj: dict) -> None:
        """Title + erste Activity zusammenziehen wenn Soft-Wrap (…Bloomberg- / Trading-Systems:)."""
        title = (proj.get('title') or '').rstrip()
        acts = list(proj.get('activities') or [])
        if not title or not acts:
            return
        if not re.search(r'[-/]$', title):
            return
        a0 = (acts[0] or '').strip()
        if not a0 or len(a0) > 80:
            return
        # typische Fortsetzung: "Trading-Systems:" / "Präsentationen"
        if re.match(r'^[A-Za-zÄÖÜäöü0-9].{0,60}$', a0):
            proj['title'] = f'{title} {a0}'.strip()
            proj['activities'] = acts[1:]


    def _projektbeschreibung_to_activities(self, proj: dict, block: str) -> None:
        """
        Wenn keine Bullets: Projektbeschreibung-Zeilen → activities (nichts weglassen).
        Title behält die erste sinnvolle Zeile / Kurzform.
        """
        if proj.get('activities'):
            return
        m = re.search(
            r'(?is)(?:^|\n)\s*(?:Projektbeschreibung|Projekttätigkeiten|Projekttatigkeiten)\s*:\s*(.*?)'
            r'(?=\n\s*(?:Systemumgebung|Protokolle\s*/\s*Technologien|'
            r'Technologien\s*/|Position|Rolle|Zeitraum|Firma|Kunde)\s*:|\Z)',
            block,
        )
        if not m:
            return
        body = (m.group(1) or '').strip()
        if not body:
            return
        acts = self._parse_list_items(body, merge_wraps=True, strict_wraps=True)
        acts = [
            a.rstrip(':').strip()
            for a in acts
            if len(a) > 5 and not self._is_page_header(a) and not self._looks_like_tech_line(a)
        ]
        if not acts:
            # eine Zeile / ein Absatz → als Activity behalten
            one = ' '.join(body.split())
            if len(one) > 5:
                acts = [one[:500]]
        if acts:
            # Alles in activities; Title = erste Zeile (kein Dedup danach)
            proj['activities'] = acts
            if len(acts) >= 2:
                proj['title'] = acts[0][:300]
                proj['activities'] = acts[1:]
            elif not (proj.get('title') or '').strip():
                proj['title'] = acts[0][:300]

    def _extract_projekte_format_b(self, text: str) -> List[dict]:
        """
        Format B / bpf: Zeitraum am Zeilenanfang (numerisch ODER deutscher Monat).
        """
        projekte = []
        lines_with_pos = []
        pos = 0
        for line in (text or '').splitlines(keepends=True):
            lines_with_pos.append((pos, line.rstrip('\r\n')))
            pos += len(line)

        positions = []
        for off, line in lines_with_pos:
            got = self._match_period_line(line)
            if got:
                period_str, same_company = got
                positions.append((off, period_str, same_company, line))

        for i, (off, period_str, same_company, _hdr) in enumerate(positions):
            end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
            block = text[off:end]
            # OV-Stil: Periode am Zeilenanfang + Firma/Institut / Projektbeschreibung
            # → Format-A-Parser (sonst zerlegt Format B die Beschreibung)
            if re.search(
                r'(?im)^\s*(?:Firma\s*/?\s*Institut|Projektbeschreibung|Projekttätigkeiten|Projekttatigkeiten)\s*:',
                block,
            ):
                a_block = self._period_block_to_format_a(block, period_str)
                a_proj = self._parse_projekt_block_a(a_block)
                if a_proj and self._usable_project(a_proj):
                    self._extend_soft_wrapped_role(a_proj, a_block)
                    self._extend_soft_wrapped_title(a_proj)
                    self._dedupe_title_activity_stub(a_proj)
                    self._projektbeschreibung_to_activities(a_proj, a_block)
                    projekte.append(a_proj)
                    continue

            proj = {'period': period_str, 'activities': [], 'technologies': []}

            if same_company and not self._is_section_noise(same_company) \
                    and not self._is_page_header(same_company):
                company = same_company
                first_lines = [
                    l.strip() for l in block.splitlines()
                    if l.strip() and not self._is_page_header(l.strip())
                ]
                if len(first_lines) >= 2:
                    nxt = first_lines[1]
                    if (
                        not self._match_period_line(nxt)
                        and len(nxt) < 60
                        and re.match(
                            r'(?i)^(dienstleistung|frankfurt|berlin|dortmund|'
                            r'karlsruhe|hannover|nürnberg|nuernberg|kassel|'
                            r'kiel|aachen|schweiz|gmbh|ag\b)',
                            nxt,
                        )
                    ):
                        company = (company + ' ' + nxt).strip()
                proj['company'] = company.rstrip(',')

            m = re.search(r'(?im)^\s*Kunde\s*/\s*Branche\s*:\s*(.+?)\s*$', block)
            if m:
                proj['company'] = m.group(1).strip()
            m = re.search(r'(?im)^\s*Rolle\s*/\s*Position\s*:\s*(.+?)\s*$', block)
            if m:
                proj['role'] = m.group(1).strip()

            lines = [
                l.strip() for l in block.splitlines()
                if l.strip() and not self._is_page_header(l.strip())
            ]
            if not proj.get('company'):
                for line in lines[1:4]:
                    if self._match_period_line(line):
                        break
                    if re.match(
                        r'(?i)^(kunde\s*/|rolle\s*/|branche|aufgaben?|kenntnisse|'
                        r'system|projektt|seither|seite\s+\d|www\.)',
                        line,
                    ):
                        continue
                    if len(line) > 3:
                        proj['company'] = line
                        break

            if not proj.get('industry'):
                m = re.search(r'(?im)^\s*Branche\s*:\s*(.+?)$', block)
                if m:
                    proj['industry'] = m.group(1).strip()

            if not proj.get('role'):
                m = re.search(
                    r'(?im)^\s*(?:Position|Rolle|Projektrolle|Funktion)\s*:\s*(.+?)$',
                    block,
                )
                if m:
                    proj['role'] = m.group(1).strip()

            m = re.search(
                r'(?im)^\s*Systemumgebung\s*:\s*(.+?)(?:\n\s*\n|$)',
                block, re.DOTALL,
            )
            if m:
                proj['technologies'] = self._parse_tech_list(m.group(1))

            if not proj.get('technologies'):
                tech_lines = []
                prev_tech = False
                for line in lines[1:]:
                    if self._match_period_line(line):
                        break
                    if ',' not in line or len(line) >= 120:
                        # Einwort-Fortsetzung unter Tech-Liste (maxenso)
                        if (
                            prev_tech
                            and ' ' not in line
                            and 2 <= len(line) <= 40
                            and not TECH_ACTIVITY_NOISE_RE.search(line)
                        ):
                            tech_lines.append(line)
                            continue
                        prev_tech = False
                        continue
                    if TECH_ACTIVITY_NOISE_RE.search(line):
                        prev_tech = False
                        continue
                    parts = [p.strip() for p in line.split(',') if p.strip()]
                    if not parts or any(self._is_tech_noise(p) for p in parts):
                        clean_parts = [p for p in parts if not self._is_tech_noise(p)]
                        if clean_parts and all(len(p) < 40 for p in clean_parts):
                            tech_lines.append(', '.join(clean_parts))
                            prev_tech = True
                        else:
                            prev_tech = False
                        continue
                    tech_lines.append(line)
                    prev_tech = True
                if tech_lines:
                    proj['technologies'] = self._parse_tech_list('\n'.join(tech_lines))
            elif proj.get('technologies'):
                proj['technologies'] = [
                    t for t in proj['technologies'] if not self._is_tech_noise(t)
                ]

            bullets = re.findall(r'(?m)^[\s]*[-•\*\u2022\u25aa]\s*(.+?)$', block)
            if bullets:
                # Soft-Wraps auch bei Bullet-Listen zusammenziehen
                proj['activities'] = self._parse_list_items(
                    '\n'.join(f'- {b.strip()}' for b in bullets if b.strip()),
                    merge_wraps=True,
                )
                proj['activities'] = [a for a in proj['activities'] if len(a) > 5]
            else:
                act_lines = []
                company_l = (proj.get('company') or '').lower()
                prev_was_tech = False
                for line in lines[1:]:
                    if self._match_period_line(line):
                        break
                    low = line.lower()
                    if company_l and (low == company_l or low in company_l):
                        continue
                    is_tech = self._looks_like_tech_line(line)
                    # Fortsetzungszeile einer Tech-Liste (maxenso unter ADABAS, …)
                    if (
                        not is_tech
                        and prev_was_tech
                        and ' ' not in line
                        and 2 <= len(line) <= 40
                        and not TECH_ACTIVITY_NOISE_RE.search(line)
                    ):
                        is_tech = True
                    if is_tech:
                        prev_was_tech = True
                        continue
                    prev_was_tech = False
                    if re.match(
                        r'(?i)^(kunde\s*/|rolle\s*/|branche|kenntnisse|systemumgebung)\b',
                        line,
                    ):
                        continue
                    if len(line) > 3 and not self._is_section_noise(line):
                        act_lines.append(line)
                if act_lines:
                    acts = self._parse_list_items(
                        '\n'.join(act_lines), merge_wraps=True, strict_wraps=True
                    )
                    acts = [
                        a.rstrip(',').strip()
                        for a in acts
                        if len(a) > 5 and not self._looks_like_tech_line(a)
                    ]
                    if acts:
                        proj['activities'] = acts[:12]
                        # Title nicht = erste Activity (sonst Doppelung in Word/HTML)
                        title = (proj.get('title') or '').strip()
                        if title:
                            a0 = acts[0].lower()
                            tl = title.lower()
                            if a0.startswith(tl[:40]) or tl.startswith(a0[:40]) or tl == a0:
                                proj['title'] = ''

            # „Seit … Zertifizierter …“ → company/title sinnvoll setzen
            if same_company and not proj.get('title'):
                if re.search(r'(?i)zertifiziert|betreuung|reisen', same_company):
                    proj['title'] = same_company[:300]
                    if not proj.get('company') or proj.get('company') == same_company:
                        if re.search(r'(?i)altersvorsorge|versicherung|finanz', same_company):
                            proj['company'] = 'Finanzdienstleistung / Altersvorsorge'
                        elif re.search(r'(?i)betreuung|kunden', same_company):
                            proj['company'] = 'Diverse Kunden'

            self._append_abschluss_activities(proj, block)
            self._ensure_weiterbildung_content(proj)

            if self._usable_project(proj):
                projekte.append(proj)

        return projekte

    def _looks_like_tech_line(self, line: str) -> bool:
        """True wenn Zeile eher Tech-Liste als Activity ist."""
        s = (line or '').strip().rstrip(',')
        if not s:
            return False
        if TECH_ACTIVITY_NOISE_RE.search(s) and ',' in s:
            # „Analyse, Programmierung, Test“ = Activity-Kurzzeile
            parts = [p.strip() for p in s.split(',') if p.strip()]
            if parts and all(
                TECH_ACTIVITY_NOISE_RE.search(p) or len(p.split()) <= 2
                for p in parts
            ):
                return False
        if ',' in s:
            parts = [p.strip() for p in s.split(',') if p.strip()]
            if (
                len(parts) >= 2
                and all(len(p) < 40 and not self._is_tech_noise(p) for p in parts)
                and not TECH_ACTIVITY_NOISE_RE.search(s)
            ):
                return True
        # Einzeltoken-Fortsetzung (maxenso, z/OS) — keine deutschen Kleinwörter (katalogs)
        if ' ' not in s and 2 <= len(s) <= 40 and not TECH_ACTIVITY_NOISE_RE.search(s):
            if re.match(r'^[a-zäöü]{3,}$', s):
                return False
            if re.match(r'^[A-Za-z0-9][\w./+#-]{1,38}$', s):
                return True
        return False

    def _extract_weitere_projekte(self, footer: str) -> List[dict]:
        """Footer „Weitere Projekte und Auftraggeber …“ → Firma/Rolle/Acts/Tech."""
        if not footer:
            return []
        clean_lines = []
        for ln in footer.splitlines():
            s = ln.strip()
            if not s or self._is_page_header(s):
                continue
            if re.match(r'(?i)^(seite\s+\d|www\.|qualifikationsprofil)', s):
                continue
            if WEITERE_PROJEKTE_RE.match(s):
                s = WEITERE_PROJEKTE_RE.sub('', s).strip(' ,;')
                if not s:
                    continue
            clean_lines.append(s)
        blob = '\n'.join(clean_lines)

        firm_pats = [
            (r'Krone\s+AG', 'Krone AG'),
            (r'Cap\s+Gemini(?:\s+Berlin(?:\s+GmbH)?)?', 'Cap Gemini Berlin GmbH'),
            (r'Umweltbundesamt', 'Umweltbundesamt'),
        ]
        positions = []
        for pat, canon in firm_pats:
            for m in re.finditer(rf'(?i)\b({pat})\b', blob):
                positions.append((m.start(), m.end(), canon))
        positions.sort(key=lambda x: x[0])

        out: List[dict] = []
        for i, (start, end, company) in enumerate(positions):
            block_end = positions[i + 1][0] if i + 1 < len(positions) else len(blob)
            block = blob[start:block_end]
            ym = re.search(r'(\d{4})\s*[–\-]\s*(\d{4})', block)
            if not ym:
                continue
            proj: dict = {
                'period': f'{ym.group(1)} – {ym.group(2)}',
                'company': company,
                'title': 'Weitere Projekte / früher',
                'activities': [],
                'technologies': [],
            }
            rm = re.search(
                r'(?i)(Systemanalytiker(?:\s+und\s+Programmierer)?)',
                block,
            )
            if rm:
                proj['role'] = re.sub(r'\s+', ' ', rm.group(1)).strip()

            # Tech-Zeile(n) vor der Jahresangabe (nur echte Tech-Listen)
            head = block[:ym.start()]
            for line in head.splitlines()[1:]:
                if re.match(r'(?i)^(systemanalytiker|programmierer|berlin)\b', line.strip()):
                    continue
                if self._looks_like_tech_line(line) or (
                    ',' in line and re.search(r'(?i)\b(ims|cics|cobol|pl/?i|adabas|dl/?i)\b', line)
                ):
                    techs = [
                        t for t in self._parse_tech_list(line)
                        if not re.match(r'(?i)^(systemanalytiker|programmierer|berlin)$', t)
                    ]
                    if techs:
                        proj['technologies'] = techs
                        break

            # Activities: Text nach Jahresrange (+ Rest der Year-Zeile)
            line_with_year = ''
            for line in block.splitlines():
                if re.search(r'\d{4}\s*[–\-]\s*\d{4}', line):
                    line_with_year = line
                    break
            year_line_rest = ''
            mrest = re.search(r'\d{4}\s*[–\-]\s*\d{4}\s*,?\s*(.*)$', line_with_year)
            if mrest:
                year_line_rest = (mrest.group(1) or '').strip().strip(',').strip()
            after_lines = []
            if year_line_rest and not re.match(r'(?i)^(berlin|systemanalytiker)\b', year_line_rest):
                after_lines.append(year_line_rest)
            # Folgetext nach der Year-Match-Position (ohne Duplikat der Rest-Zeile)
            consumed = False
            for ln in block[ym.end():].splitlines():
                s = ln.strip()
                if not s:
                    continue
                if not consumed and year_line_rest and s == year_line_rest:
                    consumed = True
                    continue
                if re.match(r'(?i)^(systemanalytiker|programmierer|berlin)\b', s):
                    continue
                if self._looks_like_tech_line(s):
                    continue
                after_lines.append(s)
            acts = self._parse_list_items(
                '\n'.join(after_lines), merge_wraps=True, strict_wraps=True
            )
            acts = [
                a.strip(' ,') for a in acts
                if len(a.strip(' ,')) > 12
                and not re.match(r'(?i)^(betreuung|mitarbeit)$', a.strip(' ,'))
            ]
            # Dedup Präfix: kurze „Betreuung“ wenn längere „Betreuung des…“ existiert
            cleaned_acts = []
            for a in acts:
                if any(
                    o != a and o.lower().startswith(a.lower())
                    for o in acts
                ):
                    continue
                cleaned_acts.append(a)
            if cleaned_acts:
                proj['activities'] = cleaned_acts[:8]
                proj['title'] = cleaned_acts[0][:300]

            out.append(proj)

        seen, final = set(), []
        for p in out:
            key = ((p.get('period') or ''), (p.get('company') or '').lower())
            if key in seen:
                continue
            seen.add(key)
            final.append(p)
        return final[:8]

    def _append_abschluss_activities(self, proj: dict, block: str) -> None:
        """Abschluß/Abschluss-Zeilen (z.B. CCVP nach Weiterbildung) → activities."""
        acts = list(proj.get('activities') or [])
        for m in re.finditer(r'(?im)^\s*Abschlu[sß]\s*:\s*(.+?)\s*$', block):
            val = re.sub(r'\s+', ' ', m.group(1)).strip()
            if not val:
                continue
            line = f'Abschluss: {val}'
            if line not in acts and val not in acts:
                acts.append(line)
        if acts:
            proj['activities'] = acts

    def _ensure_weiterbildung_content(self, proj: dict) -> None:
        """
        Weiterbildung-Einträge dürfen nie inhaltsleer werden.
        Ohne Bullets: Titel (Lehrgangstext) als Activity.
        """
        company = (proj.get('company') or '').strip().lower()
        title = (proj.get('title') or '').strip()
        is_wb = (
            'weiterbildung' in company
            or bool(re.search(r'(?i)\b(lehrgang|weiterbildung)\b', title))
        )
        if not is_wb:
            return
        acts = list(proj.get('activities') or [])
        if not acts and title:
            acts = [title]
        if not (proj.get('company') or '').strip():
            proj['company'] = 'Weiterbildung'
        if acts:
            proj['activities'] = acts

    # ── Hilfsmethoden ─────────────────────────────────────────────────────────

    def _extract_block(self, text: str,
                       start_patterns: List[str],
                       stop_patterns:  List[str]) -> str:
        """
        Extrahiert Textblock zwischen start_pattern und erstem stop_pattern.
        Gibt leeren String zurück wenn nicht gefunden.
        """
        # Start finden
        start_re = re.compile(
            r'(?im)^\s*(' + '|'.join(start_patterns) + r')\s*[:\.]?\s*$'
        )
        start_m = start_re.search(text)
        if not start_m:
            # Auch mit Inhalt auf gleicher Zeile versuchen
            start_re2 = re.compile(
                r'(?im)^\s*(' + '|'.join(start_patterns) + r')\s*[:\.]?\s*(.+?)$'
            )
            m2 = start_re2.search(text)
            if m2 and m2.group(2).strip():
                # Inhalt direkt auf der Header-Zeile → als erster Item zurückgeben
                rest_start = m2.end()
                start_content = m2.group(2).strip()
            else:
                return ''
        else:
            rest_start = start_m.end()
            start_content = ''

        rest = text[rest_start:]

        # Stop finden
        stop_re = re.compile(
            r'(?im)^\s*(' + '|'.join(stop_patterns) + r')\s*[:\.]?\s*$'
        )
        stop_m = stop_re.search(rest)
        block = rest[:stop_m.start()] if stop_m else rest[:3000]

        if start_content:
            block = start_content + '\n' + block
        return block.strip()

    def _parse_list_items(self, block: str, merge_wraps: bool = False,
                          strict_wraps: bool = False) -> List[str]:
        """Parst Bullet- oder Zeilenliste; optional Soft-Wraps zusammenführen."""
        wrap_tails = {
            'von', 'und', 'oder', 'der', 'die', 'den', 'dem', 'des', 'mit', 'für',
            'zum', 'zur', 'im', 'in', 'am', 'an', 'auf', 'bei', 'sowie', 'inkl',
            'inklusive', 'bzw', 'als', 'nach', 'vor', 'über', 'unter', 'zu',
            'notwendigen', 'verschiedenen', 'diversen', 'neuen', 'eigenen',
        }
        role_summary = re.compile(
            r'(?i)^(analyse|programmierung|beratung|konzepterstellung|'
            r'systementwicklung|design|test)\b'
        )
        items = []
        for line in block.splitlines():
            raw = line.strip()
            if not raw or self._is_page_header(raw):
                continue
            clean, had_bullet = self._strip_bullet(raw)
            if not clean or len(clean) < 3 or self._is_section_noise(clean):
                continue
            if merge_wraps and items and not had_bullet:
                prev = items[-1]
                # Neue Activity: Rollen-Kurzzeile nie an vorherige hängen
                if role_summary.match(clean) and not prev.rstrip().endswith((',', '-')):
                    items.append(clean)
                    continue
                # Silbentrennung am Zeilenende
                if prev.endswith('-'):
                    if re.match(r'^[A-ZÄÖÜ0-9]', clean):
                        items[-1] = prev + clean
                    else:
                        items[-1] = prev[:-1] + clean
                    continue
                # Fortsetzung mit Artikel/Präposition („Betreuung“ + „des …“)
                if (
                    not re.search(r'[.!;]$', prev)
                    and re.match(
                        r'(?i)^(des|dem|den|der|die|das|mit|von|für|bei|und|oder|'
                        r'sowie|inkl|als|nach|vor|über|unter|zu|im|in|am|an|auf|'
                        r'verschiedener|diverser|weiterer|neuer|eigener)\b',
                        clean,
                    )
                ):
                    items[-1] = (prev + ' ' + clean).strip()
                    continue
                last_word = prev.split()[-1].lower().strip(',;:') if prev.split() else ''
                # Fortsetzung: Komma, Wrap-Wort; len≥40 nur wenn nicht strict
                if not re.search(r'[.!;]$', prev) and (
                    prev.rstrip().endswith(',')
                    or last_word in wrap_tails
                    or (not strict_wraps and len(prev) >= 40)
                ):
                    items[-1] = (prev + ' ' + clean).strip()
                    continue
            items.append(clean)
        return items

    def _is_tech_noise(self, token: str) -> bool:
        """True wenn Token Activity-/Satzfragment statt Technologie ist."""
        t = (token or '').strip()
        if not t or len(t) < 2:
            return True
        if len(t) > 55:
            return True
        if TECH_FRAGMENT_RE.match(t):
            return True
        if TECH_ACTIVITY_NOISE_RE.search(t):
            return True
        # deutsche Satzreste mit Artikel/Präposition (mind. 3 Wörter)
        if (
            re.search(r'(?i)\b(der|die|das|den|dem|des|mit|von|für|und|bei|aus)\b', t)
            and len(t.split()) >= 3
        ):
            return True
        return False

    def _parse_tech_list(self, raw: str) -> List[str]:
        """Parst Technologie-Liste (komma- oder newline-getrennt)."""
        # Label-Prefixe entfernen
        raw = re.sub(
            r'(?i)\b(?:Hardware|Software|Protokolle(?:\s*/\s*Technologien)?|'
            r'Technologien(?:\s*/\s*Umfeld)?|Umfeld)\s*:\s*',
            '', raw or '',
        )
        # Soft-Wrap an Bindestrich am Zeilenende zusammenführen
        raw = re.sub(r'-\s*\n\s*', '', raw)
        raw = raw.replace('\n', ', ')
        parts = re.split(r'[,;]', raw)
        techs = []
        seen = set()
        skip = {
            'und', 'oder', 'with', 'and', 'etc', 'u.a.', 'z.b.',
            'protokolle', 'technologien', 'hardware', 'software', 'umfeld',
            'os',  # zu generisch / Soft-Wrap-Rest von z/OS
        }
        for p in parts:
            p = p.strip().rstrip('.,;')
            p = re.sub(r'\s+', ' ', p)
            if self._is_page_header(p) or self._is_section_noise(p):
                continue
            if self._is_tech_noise(p):
                continue
            if len(p) < 2 or len(p) > 100:
                continue
            if p.lower() in skip:
                continue
            # Abgeschnittene Fragmente wie "WS-" verwerfen
            if re.match(r'^[\w.+#]+\-$', p):
                continue
            lw = p.lower()
            if lw not in seen:
                seen.add(lw)
                techs.append(p)
        return techs

    def _harvest_skills_from_projects(self, projekte: List[dict]) -> List[dict]:
        """
        Wenn keine Skill-Tabellen existieren (Format A): Technologien aus
        Projekten als skill_ablage mit Heuristik-Kategorien ableiten.
        """
        seen = set()
        out = []
        hardware_hint = re.compile(
            r'(?i)\b(juniper|cisco|huawei|forti|checkpoint|nexus|asr|mx\d|'
            r'ptx|srx|catalyst|firewall|switch|router|f5|palo\s*alto)\b'
        )
        proto_hint = re.compile(
            r'(?i)\b(mpls|bgp|isis|ospf|vrf|qos|ipv[46]|tcp/?ip|vpn|vlan|'
            r'ethernet|stp|eigrp|rip|snmp|tacacs|radius)\b'
        )
        for proj in projekte or []:
            for t in proj.get('technologies') or []:
                name = (t or '').strip()
                if not name or len(name) < 2:
                    continue
                if self._is_tech_noise(name):
                    continue
                lw = name.lower()
                if lw in seen:
                    continue
                seen.add(lw)
                if hardware_hint.search(name):
                    cat = 'Hardware'
                elif proto_hint.search(name):
                    cat = 'Netzwerkprotokolle'
                else:
                    cat = 'Sonstige Skills'
                out.append({'name': name, 'category': cat})
        return out

    def _make_pre_json_skeleton(self, first_name: str, last_name: str) -> dict:
        """Erstellt leeres pre_json Skelett — gleiche Struktur wie labeled_to_prejson."""
        return {
            'metadata': {
                'aid':            '',
                'version':        '',
                'consultant_dir': '',
                'first_name':     first_name,
                'last_name':      last_name,
                'headline':       '',
                'pipeline': {
                    'version':   '6.0',
                    'step':      'extraction',
                    'extractor': 'aid_regex_pipeline',
                    'model':     'regex+deepseek',
                },
            },
            'extracted_data': {
                'personal':        {},
                'professional':    {'total_experience_years': 0},
                'skills':          {},  # leer — kommt vom skill_normalizer
                'certifications':  [],
                'experience':      [],
                'industries':      [],
                'focus_areas':     [],
                'focus_experience': [],
                'education':       [],
                'skill_ablage':    [],
                'other':           '',
            },
            'audit': {
                'created_by': 'aid_regex_pipeline',
                'created_at': datetime.now().isoformat(),
                'steps_completed': ['regex_extraction'],
            },
        }


# Singleton
aid_regex_extractor = AidRegexExtractor()
