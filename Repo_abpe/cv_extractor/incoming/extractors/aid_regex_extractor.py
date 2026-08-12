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
    re.compile(r'AID-[a-z]{2}_\d+'),
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
    (r'Produkte?\s*\|?\s*Standards?(?:\s*\|?\s*Erfahrungen?)?',
                                   'Sonstige Skills',          'ablage'),
    (r'Erfahrungen?\s+im\s+Bereich', 'Sonstige Skills',       'ablage'),
]

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
    r'(?im)^\s*Qualifikationsprofil\s*:\s*AID-[a-z]{2}_[^\n]*$'
)

SECTION_NOISE_NAMES = {
    'zertifizierungen', 'schulungen', 'schulungen / kurse', 'schulungen/kurse',
    'examen', 'examen | prüfungen', 'examen|prüfungen', 'ausbildung',
    'fachbereiche', 'branchen', 'persönliche daten', 'berufliche erfahrungen',
    'programmiersprachen', 'betriebssysteme', 'hardware', 'datenkommunikation',
}


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

    def _is_page_header(self, line: str) -> bool:
        return bool(PAGE_HEADER_RE.match((line or '').strip()))

    def _is_section_noise(self, name: str) -> bool:
        n = (name or '').strip().lower().rstrip(':')
        if not n or len(n) < 2:
            return True
        if self._is_page_header(name):
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

        # 4. Branchen
        branchen = self._extract_branchen(text)
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

        # 7. Skill-Tabellen → skill_ablage
        skill_ablage = self._extract_skill_tables(text)
        if skill_ablage:
            pre_json['extracted_data']['skill_ablage'] = skill_ablage
            filled.append(f'skills({len(skill_ablage)})')

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
        coverage = len(filled) / 8.0
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

        # Geburtsjahr
        m = re.search(r'(?im)^\s*Geburtsjahr\s*:\s*(\d{4})', text)
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
            r'Produkte',
            r'Hardware',
            r'Datenkommunikation',
            r'Schulungen?\s*/\s*Kurse',
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
        # Dedup
        seen, final = set(), []
        for i in out:
            lw = i.lower()
            if lw not in seen and 2 < len(i) < 80:
                seen.add(lw)
                final.append(i)
        return final

    # ── Zertifikate ───────────────────────────────────────────────────────────

    def _extract_zertifikate(self, text: str) -> List[dict]:
        block = self._extract_block(text,
            start_patterns=[r'Zertifizierungen?\s*[\|:]?\s*(?:Schulungen?)?\s*$'],
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
            # Datum am Anfang entfernen: "0/2022 Azure Architekt" → "Azure Architekt"
            line = re.sub(r'^\d{1,2}/\d{4}\s+', '', line)
            line = re.sub(r'^\d{4}\s+', '', line)
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
                certs.append({'name': name, 'issuer': '', 'date_obtained': ''})
        return certs

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
            lw = line.lower()
            if lw in seen:
                continue
            seen.add(lw)
            courses.append({
                'degree': line[:200],
                'institution': '',
                'period': '',
                'description': '',
                'education_type': 'course',
            })
        return courses

    # ── Ausbildung ────────────────────────────────────────────────────────────

    def _extract_ausbildung(self, text: str) -> List[dict]:
        """
        Extrahiert Ausbildung aus 'Ausbildung:' Block.
        Unterstützt:
          - Zeitraum-Range: 1985 - 1989 Studium …
          - Einzeljahr: 1999 Ausbildung zum …
          - Curriculum-Bullets unter dem Eintrag → description (nicht degree)
          - Soft-Wrap ohne Bullet → an degree anhängen
        """
        results = []
        # Block bis nächste Sektion (Fachbereiche / Zertifizierungen / …)
        m = re.search(
            r'(?im)^\s*Ausbildung\s*:\s*(.+?)'
            r'(?=\n\s*(?:Fachbereiche|Zertifizierungen|Examen|Schulungen|'
            r'Branchen|Programmiersprachen|Persönliche\s+Daten|'
            r'Berufliche\s+Erfahrungen?|Betriebssysteme|Hardware)\b|\Z)',
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
                    'description_parts': [],
                })
                continue

            if not entries:
                # Erster Eintrag ohne Jahr (z.B. Nowka)
                entries.append({
                    'degree': clean,
                    'period': '',
                    'description_parts': [],
                })
                continue

            # Bullet unter Ausbildung = Curriculum/Schwerpunkt, nicht Degree
            if had_bullet:
                # Skill-Header-Noise in Ausbildung-Bullets verwerfen
                if re.match(
                    r'(?i)^(programmiersprachen?|betriebssysteme|hardware|'
                    r'datenbanken|netzwerk|fachbereiche)\b',
                    clean,
                ):
                    # "Programmiersprachen Cobol, C/C++" → als description behalten
                    # (Inhalt ist relevant), nur reine Header droppen
                    if re.match(
                        r'(?i)^(programmiersprachen?|betriebssysteme|hardware|'
                        r'datenbanken|netzwerk|fachbereiche)\s*$',
                        clean,
                    ):
                        continue
                entries[-1]['description_parts'].append(clean)
                continue

            # Soft-Wrap: an degree anhängen
            entries[-1]['degree'] = (entries[-1]['degree'] + ' ' + clean).strip()

        for e in entries:
            degree = re.sub(r'\s+', ' ', e['degree']).strip()
            if len(degree) < 3:
                continue
            results.append({
                'degree': degree[:200],
                'institution': '',
                'period': (e['period'] or '')[:100],
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
        Jeder Span hat: text, y, x, sz, bold
        """
        all_skills = []
        seen_lower = set()

        STOP = re.compile(
            r'^(berufliche\s+erfahrungen?|zeitraum\s*:|period\s*:|'
            r'firma\s*/|customer\s*:|projektübersicht)',
            re.IGNORECASE
        )

        # Alle Zeilen aufbauen (y-gruppiert)
        lines = []
        prev_y = -999
        cur_line_spans = []
        for s in sorted(spans, key=lambda x: (x.get('page',1), round(x.get('y',0)/3)*3, x.get('x',0))):
            t = s.get('text','').strip()
            if not t:
                continue
            y = round(s.get('y', 0) / 3) * 3
            if abs(y - prev_y) > 3:
                if cur_line_spans:
                    lines.append(cur_line_spans)
                cur_line_spans = [s]
                prev_y = y
            else:
                cur_line_spans.append(s)
        if cur_line_spans:
            lines.append(cur_line_spans)

        # Header-Mapping
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

    def _extract_skill_tables_UNUSED(self, text: str) -> List[dict]:
        """
        Extrahiert alle Skill-Tabellen (Betriebssysteme, Programmiersprachen, etc.)
        und gibt Liste von Dicts zurück → skill_ablage MIT Kategorie-Info.

        Format: [{"name": "Linux", "category": "Betriebssysteme"}, ...]

        Damit wird der LLM-SkillNormalizer für abcona-Profile BYPASSED —
        die Kategorie kommt direkt aus dem PDF-Layout, nicht vom LLM.
        Linux landet in Betriebssysteme, NICHT in DevOps Tools!
        """
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

        logger.debug(f"[AidRegex] skill_ablage: {len(all_skills)} Skills mit Kategorie")
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

        # Nächste Skill-Sektion oder Berufliche Erfahrungen als Ende
        next_section = re.compile(
            r'(?im)^\s*('
            r'Programmiersprachen?|Betriebssysteme|Datenbanken|Hardware|'
            r'Datenkommunikation|Webserver|Middleware|Methoden|Tools?|'
            r'Netzwerk(?:protokolle)?|Standards?|Verfahren|Entwicklungstools?|'
            r'Softwaretechnologien?|Modellierungstools?|Spezialkenntnisse|'
            r'Application|Produkte|Erfahrungen?\s+im\s+Bereich|'
            r'Berufliche\s+Erfahrungen?|Projektübersicht|Zeitraum\s*:'
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

        return items

    # ── Projekte ──────────────────────────────────────────────────────────────

    def _extract_projekte(self, text: str) -> List[dict]:
        """
        Extrahiert Projekte aus dem 'Berufliche Erfahrungen' Block.

        Unterstützt zwei Hauptformate:
        Format A (tabellarisch):
            Zeitraum:           MM/YYYY – MM/YYYY
            Firma/Institut:     Firma AG
            Projektbeschreibung: Projektname
            Systemumgebung:     Java, Spring, ...
            Position:           Senior Developer

        Format B (Fließtext mit Bold-Header):
            MM/YYYY – MM/YYYY  [bold]
            Firma GmbH         [bold]
            Branche: Energie
            Aufgaben:
            • Tätigkeit 1
        """
        projekte = []

        # Ab 'Berufliche Erfahrungen' suchen
        berufl_m = re.search(
            r'(?im)^\s*Berufliche\s+Erfahrungen?\s*$', text
        )
        if not berufl_m:
            # Fallback: ab erster Zeitraum:-Zeile
            berufl_m = re.search(r'(?im)^\s*Zeitraum\s*:', text)
        if not berufl_m:
            return []

        proj_text = text[berufl_m.start():]

        # Format erkennen
        has_format_a = bool(re.search(r'(?im)^\s*Zeitraum\s*:', proj_text))
        has_format_b = bool(re.search(
            r'(?m)^\s*\d{1,2}[./]\d{4}\s*[-\u2013\u2014]+\s*\d{1,2}[./]\d{4}',
            proj_text
        ))

        if has_format_a:
            projekte = self._extract_projekte_format_a(proj_text)
        if not projekte and has_format_b:
            projekte = self._extract_projekte_format_b(proj_text)

        logger.debug(f"[AidRegex] {len(projekte)} Projekte extrahiert")
        return projekte

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
                projekte.append(proj)

        return projekte

    def _parse_projekt_block_a(self, block: str) -> Optional[dict]:
        """Parst einen einzelnen Projekt-Block im Format A."""
        proj = {}

        # Zeitraum
        m = re.search(r'(?im)^\s*Zeitraum\s*:\s*(.+?)$', block)
        if m:
            proj['period'] = m.group(1).strip()

        # Firma/Institut (verschiedene Schreibweisen)
        m = re.search(r'(?im)^\s*Firma\s*/?\s*Institut\s*:\s*(.+?)$', block)
        if m:
            proj['company'] = m.group(1).strip()
        else:
            # abcona: Kunde / Branche:
            m = re.search(r'(?im)^\s*Kunde\s*/\s*Branche\s*:\s*(.+?)$', block)
            if m:
                proj['company'] = m.group(1).strip()
            else:
                # Fallback: 'Auftraggeber:' oder 'Kunde:'
                m = re.search(r'(?im)^\s*(?:Auftraggeber|Kunde)\s*:\s*(.+?)$', block)
                if m:
                    proj['company'] = m.group(1).strip()

        # Projektbeschreibung → title (ohne Activity-Bullets)
        m = re.search(
            r'(?im)^\s*Projektbeschreibung\s*:\s*(.+?)'
            r'(?=\n\s*(?:Systemumgebung|Position|Rolle|Zeitraum|Firma|Kunde|'
            r'Protokolle|Technologien)\s*:|'
            r'\n\s*[-•\*\u2022\u25aa\uf0b7\uf09f]|$)',
            block, re.DOTALL
        )
        if m:
            title = ' '.join(m.group(1).split())  # Whitespace normalisieren
            proj['title'] = title[:300]

        # Position / Rolle (inkl. abcona Rolle / Position)
        m = re.search(
            r'(?im)^\s*(?:Rolle\s*/\s*Position|Position|Rolle|Projektrolle|Funktion)\s*:\s*(.+?)$',
            block,
        )
        if m:
            proj['role'] = m.group(1).strip()

        # Branche
        m = re.search(r'(?im)^\s*Branche\s*:\s*(.+?)$', block)
        if m:
            proj['industry'] = m.group(1).strip()

        # Systemumgebung / Protokolle/Technologien → technologies[]
        tech_parts = []
        for label in (
            r'Systemumgebung',
            r'Protokolle\s*/\s*Technologien',
            r'Technologien\s*/\s*Umfeld',
            r'Technologien\s*/?\s*Umfeld',
            r'Kenntnisse',
        ):
            m = re.search(
                rf'(?im)^\s*{label}\s*:\s*(.+?)'
                r'(?=\n\s*(?:Position|Rolle|Zeitraum|Firma|Kunde|Systemumgebung|'
                r'Protokolle\s*/|Technologien\s*/|Kenntnisse|Projektbeschreibung)\s*:|\Z)',
                block, re.DOTALL,
            )
            if m:
                tech_parts.append(m.group(1).strip())
        if tech_parts:
            techs = self._parse_tech_list('\n'.join(tech_parts))
            if techs:
                proj['technologies'] = techs

        # activities: Bullet-Liste unter Projektbeschreibung (inkl. Soft-Wraps)
        act_block = ''
        m_act = re.search(
            r'(?is)(?:^|\n)\s*Projektbeschreibung\s*:\s*.*?\n(.*?)'
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

        # Mindest-Validierung: period muss vorhanden sein
        if not proj.get('period'):
            return None

        return proj

    def _extract_projekte_format_b(self, text: str) -> List[dict]:
        """
        Format B: Fließtext mit Zeitraum als standalone Zeile.
        Pattern: MM/YYYY – MM/YYYY am Zeilenanfang
        """
        projekte = []
        DATE_PAT = re.compile(
            r'(?m)^\s*(\d{1,2}[./]\d{4})\s*[-\u2013\u2014]+\s*'
            r'(\d{1,2}[./]\d{4}|heute|dato|aktuell|laufend)\s*$',
            re.IGNORECASE
        )
        positions = [(m.start(), m.group(0).strip()) for m in DATE_PAT.finditer(text)]

        for i, (pos, period_str) in enumerate(positions):
            end   = positions[i+1][0] if i+1 < len(positions) else len(text)
            block = text[pos:end]

            proj = {'period': period_str, 'activities': [], 'technologies': []}

            # abcona-Labels zuerst (zuverlässiger als „erste Zeile = Firma“)
            m = re.search(
                r'(?im)^\s*Kunde\s*/\s*Branche\s*:\s*(.+?)\s*$', block
            )
            if m:
                proj['company'] = m.group(1).strip()
            m = re.search(
                r'(?im)^\s*Rolle\s*/\s*Position\s*:\s*(.+?)\s*$', block
            )
            if m:
                proj['role'] = m.group(1).strip()

            lines = [l.strip() for l in block.splitlines() if l.strip()]
            # Fallback: erste Zeile nach Periode = Firma (wenn kein Kunde-Label)
            if not proj.get('company'):
                for line in lines[1:4]:
                    if re.match(
                        r'(?i)^(kunde\s*/\s*branche|rolle\s*/\s*position|'
                        r'branche|aufgaben?|kenntnisse|system|projektt)',
                        line,
                    ):
                        continue
                    if (not re.match(r'^\d{1,2}[./]', line) and
                            not re.match(r'(?i)^(Branche|Aufgaben?|Kenntnisse|System)', line) and
                            len(line) > 3):
                        proj['company'] = line
                        break

            # Branche (ohne Kunde/)
            if not proj.get('industry'):
                m = re.search(r'(?im)^\s*Branche\s*:\s*(.+?)$', block)
                if m:
                    proj['industry'] = m.group(1).strip()

            # Position/Rolle Fallback
            if not proj.get('role'):
                m = re.search(
                    r'(?im)^\s*(?:Position|Rolle|Projektrolle|Funktion)\s*:\s*(.+?)$',
                    block,
                )
                if m:
                    proj['role'] = m.group(1).strip()

            # Systemumgebung
            m = re.search(r'(?im)^\s*Systemumgebung\s*:\s*(.+?)(?:\n\s*\n|$)', block, re.DOTALL)
            if m:
                proj['technologies'] = self._parse_tech_list(m.group(1))

            # Aufgaben / Bullets
            bullets = re.findall(r'(?m)^[\s]*[-•\*\u2022\u25aa]\s*(.+?)$', block)
            if bullets:
                proj['activities'] = [b.strip() for b in bullets if len(b.strip()) > 5]

            self._append_abschluss_activities(proj, block)
            self._ensure_weiterbildung_content(proj)

            projekte.append(proj)

        return projekte

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

    def _parse_list_items(self, block: str, merge_wraps: bool = False) -> List[str]:
        """Parst Bullet- oder Zeilenliste; optional Soft-Wraps zusammenführen."""
        wrap_tails = {
            'von', 'und', 'oder', 'der', 'die', 'den', 'dem', 'des', 'mit', 'für',
            'zum', 'zur', 'im', 'in', 'am', 'an', 'auf', 'bei', 'sowie', 'inkl',
            'inklusive', 'bzw', 'als', 'nach', 'vor', 'über', 'unter', 'zu',
            'notwendigen', 'verschiedenen', 'diversen', 'neuen', 'eigenen',
        }
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
                # Silbentrennung am Zeilenende
                if prev.endswith('-'):
                    # Compound behalten (Server-Hardware), sonst Soft-Hyphen entfernen
                    if re.match(r'^[A-ZÄÖÜ0-9]', clean):
                        items[-1] = prev + clean
                    else:
                        items[-1] = prev[:-1] + clean
                    continue
                last_word = prev.split()[-1].lower().strip(',;:') if prev.split() else ''
                # Fortsetzung: langer Absatz, Komma, oder typisches Wrap-Wort
                if not re.search(r'[.!;]$', prev) and (
                    len(prev) >= 40
                    or prev.rstrip().endswith(',')
                    or last_word in wrap_tails
                ):
                    items[-1] = (prev + ' ' + clean).strip()
                    continue
            items.append(clean)
        return items

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
        parts = re.split(r'[,;/]', raw)
        techs = []
        seen = set()
        skip = {
            'und', 'oder', 'with', 'and', 'etc', 'u.a.', 'z.b.',
            'protokolle', 'technologien', 'hardware', 'software', 'umfeld',
        }
        for p in parts:
            p = p.strip().rstrip('.,;')
            p = re.sub(r'\s+', ' ', p)
            if self._is_page_header(p) or self._is_section_noise(p):
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
