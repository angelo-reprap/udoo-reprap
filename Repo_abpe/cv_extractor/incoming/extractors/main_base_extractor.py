"""
main_base_extractor.py - Universeller Extraktor fuer main_pipeline

- Kein Zeichenlimit
- Placeholder: {text}, {consultant_type}
- Prompt aus DB per stage-Name
- Gibt immer Dict zurueck

Changelog:
  2026-05-11: Schritt 4 SKILLS → skill_ablage mit Kategorie aus skill_cat
              Kein LLM mehr für SKILLS wenn skill_cat bekannt (Regex-Parsing)
              Keine Stopwords — Kontext bestimmt was ein Skill ist
              skill_ablage = [{"name": "Assembler", "category": "Programmiersprachen"}]
"""
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from datetime import datetime
import re

# Mapping: snake_case (intern) → Deutsche DB-Kategorienamen
SKILL_CAT_TO_DB = {
    'programming_languages':   'Programmiersprachen',
    'operating_system':        'Betriebssysteme',
    'database':                'Datenbanken',
    'hardware':                'Hardware',
    'datenkommunikation':      'Datenkommunikation',  # abcona-PDF-Header 1:1
    'network_protocol':        'Netzwerkprotokolle',
    'it_infrastructure':       'IT-Infrastruktur',
    'methodology':             'Methoden',
    'framework':               'Frameworks und Bibliotheken',
    'cloud_platform':          'Cloud-Plattformen',
    'security_tool':           'Security Tools',
    'devops_tool':             'DevOps Tools',
    'development_environment': 'Entwicklungsumgebungen',
    'documentation_tool':      'Dokumentationstools',
    'monitoring_tool':         'Monitoring Tools',
    'version_control':         'Versionsverwaltung',
    'testing_tool':            'Testing Tools',
    'data_format':             'Datenformate',
    'data_management':         'Datenmanagement',
    'business_software':       'Business Software',
    'special_concept':         'Spezielle Konzepte',
    'soft_skill':              'Soft Skills',
    'virtualization':          'Virtualisierung',
    'ci_cd_tool':              'CI/CD Tools',
    'identity_management':     'Identity Management',
    'communication_tool':      'Kommunikationstools',
    'project_management':      'Projektmanagement Tools',
    'architecture_pattern':    'Architekturmuster',
    'special_skill':           'Sonstige Skills',
}

# Header-Zeilen die keine Skills sind — werden beim Parsing übersprungen
HEADER_PATTERNS = re.compile(
    r'^(programmiersprachen?|betriebssysteme?|datenbanken?|hardware|'
    r'datenkommunikation|netzwerkprotokolle?|netzwerk|methoden|tools?|'
    r'entwicklungstools?|softwaretechnologien?|modellierungstools?|'
    r'spezialkenntnisse|application|technologien|frameworks?|cloud|'
    r'virtualisierung|sicherheit|security|monitoring|versionsverwaltung|'
    r'testing|datenformate|datenmanagement|produkte?\s*\|.*|'
    r'erfahrungen?\s+im\s+bereich)\s*$',
    re.IGNORECASE
)


class MasterBaseExtractor:
    """Laedt Prompt aus DB per stage, sendet an LLM, gibt Dict zurueck."""

    def __init__(self, stage: str, consultant_type: str = "IT-Freelancer"):
        self.stage           = stage
        self.consultant_type = consultant_type
        self._prompt_text    = None

    def _load_prompt(self) -> Optional[str]:
        if self._prompt_text is not None:
            return self._prompt_text
        try:
            from apps.cv_extractor.models import PromptTemplate
            pt = PromptTemplate.objects.get(stage=self.stage, is_active=True)
            self._prompt_text = pt.prompt_text
            return self._prompt_text
        except Exception as e:
            print(f"⚠️ Prompt nicht gefunden: {self.stage} → {e}")
            return None

    def extract(self, text: str) -> Dict[str, Any]:
        """Sendet Text an LLM und gibt JSON-Dict zurueck."""
        if not text or len(text.strip()) < 5:
            return {}
        prompt_text = self._load_prompt()
        if not prompt_text:
            return {}
        prompt = prompt_text
        prompt = prompt.replace("{text}",            text)
        prompt = prompt.replace("{consultant_type}", self.consultant_type)
        prompt = prompt.replace('{{', '{').replace('}}', '}')
        from apps.cv_extractor.services.deepseek_api_label import deepseek_label_api
        res = deepseek_label_api.extract(
            prompt,
            system_prompt="Du bist ein praeziser CV-Analyst. Antworte nur mit JSON."
        )
        if res.success and res.data:
            if isinstance(res.data, dict):
                return res.data
            if isinstance(res.data, list) and res.data:
                return res.data[0] if isinstance(res.data[0], dict) else {}
        print(f"❌ {self.stage}: {getattr(res,'error','leer')} | raw={getattr(res,'raw_response','')[:80]}")
        return {}


def _regex_fill_experience_from_text(text: str, data: dict) -> dict:
    """
    Regex-Overlay auf LLM-Projekt-JSON (allgemein, Label-basiert).
    Füllt company/role wenn im Quelltext 'Kunde / Branche:' bzw.
    'Rolle / Position:' stehen — LLM-Ergebnis hat Vorrang nur wenn schon gesetzt
    und nicht wie eine Rolle aussieht.
    """
    if not isinstance(data, dict) or not text:
        return data
    out = dict(data)
    role_hint = re.compile(
        r'(experte|expertin|engineer|administrator|berater|consultant|'
        r'entwickler|architekt|spezialist|analyst|operator)',
        re.IGNORECASE,
    )

    m = re.search(r'(?im)^\s*Kunde\s*/\s*Branche\s*:\s*(.+?)\s*$', text)
    if m:
        company = m.group(1).strip()
        cur = (out.get('company') or '').strip()
        if company and (not cur or role_hint.search(cur)):
            out['company'] = company[:200]

    m = re.search(r'(?im)^\s*Rolle\s*/\s*Position\s*:\s*(.+?)\s*$', text)
    if m:
        role = m.group(1).strip()
        if role:
            out['role'] = role[:200]

    m = re.search(
        r'(?im)^\s*(?:Position|Rolle|Projektrolle|Funktion)\s*:\s*(.+?)\s*$',
        text,
    )
    if m and not (out.get('role') or '').strip():
        out['role'] = m.group(1).strip()[:200]

    return out


def gruppe_to_volltext(gruppe: dict, block_by_nr: dict) -> str:
    """Gibt den vollstaendigen Text einer Gruppe zurueck."""
    lines = []
    for nr in gruppe.get('blocks', []):
        b = block_by_nr.get(nr)
        if b:
            lines.extend(b['lines'])
    return '\n'.join(l for l in lines if l.strip())


def _parse_skill_items_from_text(text: str) -> List[str]:
    """
    Parst Skill-Einträge aus einem Textblock per Regex.
    Keine Stopwords — der Kontext (Kategorie) bestimmt was ein Skill ist.

    Unterstützt:
    - Zeilenweise:         "Java\nPython\nC++"
    - Komma-getrennt:      "Java, Python, C++"
    - Mit Niveau-Spalte:   "Java  Sehr gut  16" → "Java"
    - Bullet-Listen:       "• Java\n• Python"
    - Header-Zeilen:       "Programmiersprachen" → wird übersprungen
    """
    items = []
    seen  = set()

    for line in text.splitlines():
        line = line.strip()
        if not line or len(line) < 1:
            continue

        # Header-Zeilen überspringen (Kategorie-Name selbst ist kein Skill)
        if HEADER_PATTERNS.match(line):
            continue

        # Bullet entfernen
        line = re.sub(r'^[-•\*\u2022\u25aa]\s*', '', line).strip()
        if not line:
            continue

        # Niveau-Spalte entfernen: "Java  Sehr gut  16"
        niveau_m = re.match(
            r'^(.+?)\s{2,}(?:Sehr gut|Gut|Grundkenntnisse|Experte|'
            r'Expert|Good|Fortgeschritten)\b',
            line, re.IGNORECASE
        )
        if niveau_m:
            line = niveau_m.group(1).strip()

        # Komma-getrennte Liste
        if ',' in line and len(line.split(',')) >= 2:
            for part in line.split(','):
                p = part.strip().rstrip('.,;')
                if p and len(p) >= 2:
                    lw = p.lower()
                    if lw not in seen:
                        seen.add(lw)
                        items.append(p)
            continue

        # Einzelne Zeile
        clean = line.rstrip('.,;:')
        if clean and len(clean) >= 1:
            lw = clean.lower()
            if lw not in seen:
                seen.add(lw)
                items.append(clean)

    return items


def _norm_education_items(items, default_type='degree'):
    """Strings/Dicts → education_type degree|course; degree-Feld setzen."""
    out = []
    for edu in items or []:
        if isinstance(edu, str):
            edu = {'degree': edu.strip(), 'education_type': default_type}
        elif isinstance(edu, dict):
            edu = dict(edu)
        else:
            continue
        degree = (edu.get('degree') or edu.get('name') or '').strip()
        if not degree:
            degree = (edu.get('description') or '').strip()
        if not degree:
            continue
        edu['degree'] = degree
        et = (edu.get('education_type') or default_type or 'degree').strip().lower()
        if et in ('schulung', 'schulungen', 'course', 'training', 'kurs'):
            et = 'course'
        elif et not in ('degree', 'course', 'certification'):
            et = default_type
        edu['education_type'] = et
        out.append(edu)
    return out


def _is_section_noise_name(name: str) -> bool:
    n = (name or '').strip().lower()
    if not n or len(n) < 3:
        return True
    noise = (
        'zertifizierungen', 'schulungen', 'schulungen / kurse', 'schulungen/kurse',
        'examen', 'examen | prüfungen', 'examen|prüfungen', 'ausbildung',
        'fachbereiche', 'branchen', 'persönliche daten',
    )
    return n in noise or n.rstrip(':') in noise


def _norm_edu_period(period: str) -> str:
    """'1985 - 1989' / '1985–1989' → '1985-1989'."""
    p = (period or '').strip().lower()
    p = p.replace('–', '-').replace('—', '-')
    p = re.sub(r'\s+', '', p)
    return p


def _merge_education(existing, incoming):
    """
    Dedup merge education lists.
    - gleicher degree+type → skip
    - gleiche Periode + type=degree → behalte längere Beschreibung
      (z.B. LLM 'Dipl.-Ing. …' vs Regex 'Studium zum Dipl.-Ing. …')
    """
    merged = [dict(e) for e in (existing or []) if isinstance(e, dict)]
    added = 0

    def _find_dup(e):
        degree = (e.get('degree') or '').strip()
        if not degree:
            return None
        et = e.get('education_type') or 'degree'
        deg_l = degree.lower()
        per = _norm_edu_period(e.get('period'))
        for i, m in enumerate(merged):
            if (m.get('education_type') or 'degree') != et:
                continue
            mdeg = (m.get('degree') or '').strip().lower()
            if not mdeg:
                continue
            if mdeg == deg_l:
                return i
            mper = _norm_edu_period(m.get('period'))
            if et == 'degree' and per and mper and per == mper:
                # gleiche Periode: Substring / kürzere Variante
                if deg_l in mdeg or mdeg in deg_l:
                    return i
        return None

    for e in incoming or []:
        if not isinstance(e, dict):
            continue
        e = dict(e)
        degree = (e.get('degree') or '').strip()
        if not degree:
            continue
        idx = _find_dup(e)
        if idx is None:
            merged.append(e)
            added += 1
            continue
        # Reicherer Eintrag gewinnt (längerer degree-Text; Periode nachziehen)
        old = merged[idx]
        old_deg = (old.get('degree') or '').strip()
        if len(degree) > len(old_deg):
            old['degree'] = degree
        if e.get('period') and not (old.get('period') or '').strip():
            old['period'] = e.get('period')
        if e.get('institution') and not (old.get('institution') or '').strip():
            old['institution'] = e.get('institution')
    return merged, added


def _finalize_education(items):
    """Abschluss-Dedup: degrees nach Periode kollabieren, courses nach Name."""
    degrees, courses = [], []
    for e in items or []:
        if not isinstance(e, dict):
            continue
        e = dict(e)
        if (e.get('education_type') or 'degree') == 'course':
            courses.append(e)
        else:
            degrees.append(e)

    by_period = {}
    no_period = []
    for e in degrees:
        per = _norm_edu_period(e.get('period'))
        deg = (e.get('degree') or '').strip()
        if not deg:
            continue
        if not per:
            no_period.append(e)
            continue
        prev = by_period.get(per)
        if not prev or len(deg) > len((prev.get('degree') or '').strip()):
            by_period[per] = e

    # no_period: drop if substring of a period-entry degree
    kept_np = []
    period_degs = [(p.get('degree') or '').strip().lower() for p in by_period.values()]
    for e in no_period:
        deg_l = (e.get('degree') or '').strip().lower()
        if any(deg_l in pd or pd in deg_l for pd in period_degs if pd):
            continue
        kept_np.append(e)

    # courses exact dedup
    seen_c, courses_out = set(), []
    for e in courses:
        k = (e.get('degree') or '').strip().lower()
        if not k or k in seen_c:
            continue
        seen_c.add(k)
        courses_out.append(e)

    # stabile Reihenfolge: degrees mit Periode (Jahr aufsteigend), dann Rest, dann courses
    def _year_key(e):
        m = re.search(r'(\d{4})', e.get('period') or '')
        return int(m.group(1)) if m else 9999

    deg_out = sorted(by_period.values(), key=_year_key) + kept_np
    return deg_out + courses_out


def labeled_to_prejson(labeled: list, gruppen: list, block_by_nr: dict,
                        consultant_type: str = "IT-Freelancer",
                        aid_extracted: dict = None) -> dict:
    """
    Konvertiert gelabelte Gruppen in pre_json Struktur.

    Ablauf:
      1. PERSONAL/FACHBEREICHE/ZERTIFIKATE/SCHULUNGEN/BRANCHEN/FOCUS_EXP/OTHER
         → parallel LLM
      2. PROJECT → einzeln pro Projekt parallel LLM
      3. HEADER  → Name + Headline extrahieren LLM
      4. SKILLS  → Regex-Parsing mit skill_cat aus Labeler (kein LLM!)
                   → skill_ablage = [{"name": "Java", "category": "Programmiersprachen"}]
                   → LLM nur Fallback für Gruppen ohne skill_cat
    """
    # ── pre_json Skelett ──────────────────────────────────────────────────────
    pre_json = {
        "metadata": {
            "aid":            "",
            "version":        "",
            "consultant_dir": "",
            "first_name":     "",
            "last_name":      "",
            "headline":       "",
            "source": {
                "type":        "main_pipeline",
                "filename":    "",
                "filesize":    0,
                "import_id":   "",
                "import_date": datetime.now().isoformat(),
            },
            "pipeline": {
                "version":       "6.0",
                "step":          "extraction",
                "extractor":     "main_pipeline",
                "model":         "deepseek-chat",
                "self_learning": True,
            },
            "duplicate_check": {
                "exists":  False,
                "message": "",
            },
            "statistics": {
                "total_categories": 0,
                "has_personal":     False,
                "has_skills":       False,
                "has_experience":   False,
            },
        },
        "extracted_data": {
            "personal":  {},
            "skills": {
                "architecture_pattern":    [],
                "business_software":       [],
                "ci_cd_tool":              [],
                "cloud_platform":          [],
                "communication_tool":      [],
                "database":                [],
                "data_format":             [],
                "data_management":         [],
                "development_environment": [],
                "devops_tool":             [],
                "documentation_tool":      [],
                "framework":               [],
                "hardware":                [],
                "identity_management":     [],
                "it_infrastructure":       [],
                "methodology":             [],
                "monitoring_tool":         [],
                "network_protocol":        [],
                "operating_system":        [],
                "programming_languages":   [],
                "project_management":      [],
                "security_tool":           [],
                "soft_skill":              [],
                "special_concept":         [],
                "special_skill":           [],
                "testing_tool":            [],
                "version_control":         [],
                "virtualization":          [],
            },
            "certifications":   [],
            "experience":       [],
            "industries":       [],
            "focus_areas":      [],
            "focus_experience": [],
            "education":        [],
            "other":            [],
            "skill_ablage":     [],
        },
        "audit": {
            "created_by":      "main_pipeline",
            "created_at":      datetime.now().isoformat(),
            "source_file":     "",
            "steps_completed": [],
        },
    }

    # ── Schritt 0: Regex-Werte vorbelegen (aid_extracted) ───────────────────────
    if aid_extracted:
        if aid_extracted.get('headline'):
            pre_json['metadata']['headline'] = aid_extracted['headline']
            pre_json['extracted_data'].setdefault('personal', {})['headline'] = aid_extracted['headline']
        if aid_extracted.get('focus_areas'):
            pre_json['extracted_data']['focus_areas'] = aid_extracted['focus_areas']
        if aid_extracted.get('industries'):
            pre_json['extracted_data']['industries'] = aid_extracted['industries']
        if aid_extracted.get('certifications'):
            _noise = {
                'zertifizierungen', 'schulungen', 'schulungen / kurse', 'schulungen/kurse',
                'examen', 'examen | prüfungen', 'examen|prüfungen',
            }
            cleaned = []
            for c in aid_extracted['certifications']:
                name = (c.get('name') if isinstance(c, dict) else str(c) or '').strip()
                if name and name.lower().rstrip(':') not in _noise:
                    cleaned.append(c if isinstance(c, dict) else {'name': name})
            pre_json['extracted_data']['certifications'] = cleaned
        if aid_extracted.get('education'):
            # Regex-Ausbildung vorbelegen (LLM/PERSONAL darf später ergänzen, nicht löschen)
            pre_json['extracted_data']['education'] = _norm_education_items(
                aid_extracted['education'], default_type='degree'
            )

    # ── Gruppen-Indizes aufbauen ──────────────────────────────────────────────
    label_gruppen  = defaultdict(list)
    gruppen_by_idx = {i + 1: g for i, g in enumerate(gruppen)}

    for lg in labeled:
        label_gruppen[lg['label']].append(lg)

    # ── Schritt 1: Parallele LLM-Extraktionen ────────────────────────────────
    STAGE_MAP = {
        'PERSONAL':     'main_extract_personal',
        'FACHBEREICHE': 'main_extract_fachbereiche',
        'ZERTIFIKATE':  'main_extract_zertifikate',
        'SCHULUNGEN':   'main_extract_schulungen',
        'BRANCHEN':     'main_extract_branchen',
        'FOCUS_EXP':    'main_extract_focus_exp',
        'OTHER':        'main_extract_sonstiges',
    }

    tasks = []
    for label, stage in STAGE_MAP.items():
        grps = label_gruppen.get(label, [])
        if not grps:
            continue
        full_text = ''
        for lg in grps:
            g = gruppen_by_idx.get(lg['index'])
            if g:
                full_text += gruppe_to_volltext(g, block_by_nr) + '\n\n'
        if full_text.strip():
            tasks.append((label, stage, full_text.strip()))

    print(f"  LLM: {len(tasks)} Extraktionen parallel...")

    def _run(task):
        label, stage, text = task
        return label, MasterBaseExtractor(stage, consultant_type).extract(text)

    results = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_run, t): t[0] for t in tasks}
        for future in as_completed(futures):
            label, data = future.result()
            results[label] = data
            print(f"    {label}: ✅" if data else f"    {label}: ❌ leer")

    # ── Ergebnisse einfügen ───────────────────────────────────────────────────
    if results.get('PERSONAL'):
        pre_json['extracted_data']['personal'] = results['PERSONAL']
        # personal.education mergen (Regex-Ausbildung aus Schritt 0 behalten)
        personal_edu = _norm_education_items(
            results['PERSONAL'].get('education', []), default_type='degree'
        )
        if personal_edu:
            merged, added = _merge_education(
                pre_json['extracted_data'].get('education'), personal_edu
            )
            pre_json['extracted_data']['education'] = merged
            print(f"    education aus personal gemerged: +{added} (gesamt {len(merged)})")
        # personal.languages normalisieren: Strings → [{name, level}]
        raw_langs = results['PERSONAL'].get('languages', [])
        norm_langs = []
        for lang in raw_langs:
            if isinstance(lang, dict):
                norm_langs.append({"name": lang.get("name", "").strip(), "level": lang.get("level", "")})
            elif isinstance(lang, str) and lang.strip():
                norm_langs.append({"name": lang.strip(), "level": ""})
        if norm_langs:
            pre_json['extracted_data']['personal']['languages'] = norm_langs
            print(f"    languages normalisiert: {len(norm_langs)} Einträge")

    if results.get('FACHBEREICHE') and not pre_json['extracted_data']['focus_areas']:
        pre_json['extracted_data']['focus_areas'] = \
            results['FACHBEREICHE'].get('focus_areas', [])

    if results.get('ZERTIFIKATE') and not pre_json['extracted_data']['certifications']:
        raw_certs = results['ZERTIFIKATE'].get('certifications', []) or []
        clean_certs = []
        for c in raw_certs:
            if isinstance(c, str):
                name = c.strip()
                item = {'name': name}
            elif isinstance(c, dict):
                item = dict(c)
                name = (item.get('name') or '').strip()
            else:
                continue
            if name and not _is_section_noise_name(name):
                item['name'] = name
                clean_certs.append(item)
        pre_json['extracted_data']['certifications'] = clean_certs

    if results.get('SCHULUNGEN'):
        # WICHTIG: nicht überschreiben — Ausbildung (degree) behalten
        d = results['SCHULUNGEN']
        courses = _norm_education_items(
            d.get('education', d.get('schulungen', [])), default_type='course'
        )
        for c in courses:
            c['education_type'] = 'course'
        existing = list(pre_json['extracted_data'].get('education') or [])
        merged, added = _merge_education(existing, courses)
        pre_json['extracted_data']['education'] = merged
        print(f"    schulungen gemerged: +{added} courses (education gesamt {len(merged)})")

    # Ausbildung final dedup (gleiche Periode → eine Zeile)
    before = len(pre_json['extracted_data'].get('education') or [])
    pre_json['extracted_data']['education'] = _finalize_education(
        pre_json['extracted_data'].get('education')
    )
    after = len(pre_json['extracted_data']['education'])
    if before != after:
        print(f"    education finalized: {before} → {after}")

    if results.get('BRANCHEN') and not pre_json['extracted_data']['industries']:
        pre_json['extracted_data']['industries'] = \
            results['BRANCHEN'].get('industries', [])

    if results.get('FOCUS_EXP'):
        raw_focus = results['FOCUS_EXP'].get('focus_experience', [])
        norm_focus = []
        for idx, item in enumerate(raw_focus):
            if isinstance(item, dict):
                norm_focus.append({
                    "name":       item.get("name", "").strip(),
                    "category":   item.get("category", "product_standard"),
                    "sort_order": item.get("sort_order", idx),
                })
            elif isinstance(item, str) and item.strip():
                norm_focus.append({
                    "name":       item.strip(),
                    "category":   "product_standard",
                    "sort_order": idx,
                })
        pre_json['extracted_data']['focus_experience'] = norm_focus
        print(f"    focus_experience normalisiert: {len(norm_focus)} Einträge")

    if results.get('OTHER'):
        other_raw = results['OTHER']
        if isinstance(other_raw, list):
            pre_json['extracted_data']['other'] = other_raw
        elif isinstance(other_raw, dict):
            items = other_raw.get('other', other_raw.get('items', []))
            if isinstance(items, list):
                pre_json['extracted_data']['other'] = items
            elif isinstance(items, str) and items.strip():
                pre_json['extracted_data']['other'] = [{"content": items.strip(), "content_type": "text", "source": "pre_json", "sort_order": 0}]
        elif isinstance(other_raw, str) and other_raw.strip():
            pre_json['extracted_data']['other'] = [{"content": other_raw.strip(), "content_type": "text", "source": "pre_json", "sort_order": 0}]

    # ── Schritt 2: Projekte einzeln parallel ─────────────────────────────────
    proj_gruppen = [lg for lg in labeled if lg['label'] in ('PROJECT', 'EXPERIENCE')]
    if proj_gruppen:
        print(f"  PROJEKTE: {len(proj_gruppen)} einzeln parallel...")

        def _run_proj(lg):
            g = gruppen_by_idx.get(lg['index'])
            if not g:
                return lg['index'], {}
            text = gruppe_to_volltext(g, block_by_nr)
            if not text.strip():
                return lg['index'], {}
            data = MasterBaseExtractor(
                'main_extract_experience', consultant_type
            ).extract(text)
            # Regex-Overlay: abcona-Labels Kunde/Rolle nachziehen
            if isinstance(data, dict):
                if 'experience' in data and isinstance(data['experience'], dict):
                    data['experience'] = _regex_fill_experience_from_text(
                        text, data['experience']
                    )
                elif data.get('period') or data.get('company') or data.get('role'):
                    data = _regex_fill_experience_from_text(text, data)
                elif isinstance(data.get('experience'), list):
                    data['experience'] = [
                        _regex_fill_experience_from_text(text, e)
                        if isinstance(e, dict) else e
                        for e in data['experience']
                    ]
            return lg['index'], data

        all_exp  = []
        proj_map = {}
        with ThreadPoolExecutor(max_workers=10) as ex:
            futs = {ex.submit(_run_proj, lg): lg['index'] for lg in proj_gruppen}
            for f in as_completed(futs):
                idx, data = f.result()
                proj_map[idx] = data
                print(f"    Projekt {idx}: {'✅' if data else '❌'}")

        for lg in proj_gruppen:
            data = proj_map.get(lg['index'], {})
            if not data:
                continue
            if isinstance(data, list):
                all_exp.extend(data)
            elif isinstance(data, dict):
                exp = data.get('experience', data)
                if isinstance(exp, list):
                    all_exp.extend(exp)
                elif isinstance(exp, dict) and exp.get('period'):
                    all_exp.append(exp)

        pre_json['extracted_data']['experience'] = all_exp
        print(f"  {len(all_exp)} Projekte extrahiert")

    # ── Schritt 3: HEADER → Name + Headline ──────────────────────────────────
    header_gruppen = [lg for lg in labeled if lg['label'] == 'HEADER']
    if header_gruppen:
        header_text = ''
        for lg in header_gruppen:
            g = gruppen_by_idx.get(lg['index'])
            if g:
                header_text += gruppe_to_volltext(g, block_by_nr) + '\n'
        if header_text.strip():
            data = MasterBaseExtractor(
                'main_extract_header', consultant_type
            ).extract(header_text)
            if data:
                hl = data.get('headline', '')
                fn = data.get('first_name', '')
                ln = data.get('last_name', '')
                if hl and not pre_json['metadata']['headline']:
                    pre_json['metadata']['headline'] = hl
                if hl and not pre_json['extracted_data']['personal'].get('headline'):
                    pre_json['extracted_data']['personal']['headline'] = hl
                if fn and not pre_json['metadata']['first_name']:
                    pre_json['metadata']['first_name'] = fn
                if ln and not pre_json['metadata']['last_name']:
                    pre_json['metadata']['last_name'] = ln
                print(f"    HEADER: {fn} {ln} | {hl}")

    # ── Schritt 4: SKILLS → skill_ablage MIT Kategorie ───────────────────────
    # skill_cat aus Labeler direkt nutzen → kein LLM nötig!
    # skill_ablage = [{"name": "Java", "category": "Programmiersprachen"}, ...]
    skill_gruppen = [lg for lg in labeled if lg['label'] == 'SKILLS']
    if skill_gruppen:
        print(f"  SKILLS: {len(skill_gruppen)} Gruppe(n) → skill_ablage...")
        skill_ablage = []
        seen_skills  = set()
        llm_fallback = []

        for lg in skill_gruppen:
            g = gruppen_by_idx.get(lg['index'])
            if not g:
                continue

            text      = gruppe_to_volltext(g, block_by_nr)
            skill_cat = lg.get('skill_cat')

            if skill_cat and skill_cat in SKILL_CAT_TO_DB:
                # Kategorie bekannt → Regex-Parsing, kein LLM
                db_cat = SKILL_CAT_TO_DB[skill_cat]
                items  = _parse_skill_items_from_text(text)
                added  = 0
                for item in items:
                    lw = item.lower()
                    if lw not in seen_skills:
                        seen_skills.add(lw)
                        skill_ablage.append({
                            'name':     item,
                            'category': db_cat,
                        })
                        added += 1
                if added:
                    print(f"    {db_cat}: {added} Skills (Regex)")
            else:
                # Kategorie unbekannt → LLM Fallback
                llm_fallback.append((lg, text))

        # LLM-Fallback für Gruppen ohne skill_cat
        if llm_fallback:
            print(f"    {len(llm_fallback)} Gruppen ohne Kategorie → LLM Fallback")
            fallback_text = '\n\n'.join(text for _, text in llm_fallback)
            data = MasterBaseExtractor(
                'main_extract_skill_list', consultant_type
            ).extract(fallback_text)
            if data:
                items = data.get('skills', data.get('items', []))
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, str) and item.strip():
                            lw = item.strip().lower()
                            if lw not in seen_skills:
                                seen_skills.add(lw)
                                skill_ablage.append({
                                    'name':     item.strip(),
                                    'category': 'Sonstige Skills',
                                })
                        elif isinstance(item, dict) and item.get('name'):
                            lw = item['name'].lower()
                            if lw not in seen_skills:
                                seen_skills.add(lw)
                                skill_ablage.append(item)

        if skill_ablage:
            pre_json['extracted_data']['skill_ablage'] = skill_ablage
            print(f"    {len(skill_ablage)} Skills → skill_ablage (mit Kategorie)")
        else:
            print(f"    SKILLS: skill_ablage leer")

    # ── Schritt 5: skill_ablage → skills Dict übertragen ────────────────────
    # Umgekehrtes Mapping: Deutsch → snake_case
    DB_TO_SKILL_CAT = {v: k for k, v in SKILL_CAT_TO_DB.items()}
    nicht_gemappt = []
    for entry in pre_json['extracted_data'].get('skill_ablage', []):
        name    = entry.get('name', '').strip() if isinstance(entry, dict) else ''
        cat_de  = entry.get('category', '')     if isinstance(entry, dict) else ''
        cat_key = DB_TO_SKILL_CAT.get(cat_de)
        if cat_key and cat_key in pre_json['extracted_data']['skills']:
            if name and name not in pre_json['extracted_data']['skills'][cat_key]:
                pre_json['extracted_data']['skills'][cat_key].append(name)
            # gemappt → nicht mehr in skill_ablage behalten
        else:
            # Kategorie unbekannt → in skill_ablage lassen
            nicht_gemappt.append(entry)
    pre_json['extracted_data']['skill_ablage'] = nicht_gemappt
    filled = {k: v for k, v in pre_json['extracted_data']['skills'].items() if v}
    print(f"    skills befüllt: {len(filled)} Kategorien, skill_ablage Rest: {len(nicht_gemappt)}")

    pre_json['audit']['steps_completed'] = \
        list(results.keys()) + ['PROJECT', 'HEADER', 'SKILLS']
    return pre_json
