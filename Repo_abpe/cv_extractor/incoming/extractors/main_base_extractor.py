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


def _labeled_value_from_text(text: str, label_re: str) -> str:
    """Label-Wert: gleiche Zeile nach ':', sonst nächste nicht-leere Nicht-Label-Zeile."""
    if not text or not label_re:
        return ''
    m = re.search(rf'(?im)^\s*(?:{label_re})\s*:\s*(.*)$', text)
    if not m:
        return ''
    same = (m.group(1) or '').strip()
    if same:
        return same
    for line in text[m.end():].splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r'^[A-Za-zÄÖÜäöü0-9][^:\n]{0,80}:\s*', line):
            return ''
        return line
    return ''


def _regex_fill_experience_from_text(text: str, data: dict) -> dict:
    """
    Regex-Overlay auf LLM-Projekt-JSON (allgemein, Label-basiert).
    Füllt period/company/role aus AID-Labels (auch wenn Wert in der nächsten Zeile steht).
    LLM-Werte behalten Vorrang wenn bereits sinnvoll gesetzt.
    """
    if not isinstance(data, dict) or not text:
        return data
    out = dict(data)
    role_hint = re.compile(
        r'(experte|expertin|engineer|administrator|berater|consultant|'
        r'entwickler|architekt|spezialist|analyst|operator)',
        re.IGNORECASE,
    )

    if not (out.get('period') or '').strip():
        period = _labeled_value_from_text(text, r'Zeitraum|Period')
        if period:
            out['period'] = period[:80]

    company = (
        _labeled_value_from_text(text, r'Kunde\s*/\s*Branche')
        or _labeled_value_from_text(text, r'Firma\s*/?\s*Institut')
        or _labeled_value_from_text(text, r'Auftraggeber|Kunde|Customer')
    )
    if company:
        cur = (out.get('company') or '').strip()
        if not cur or role_hint.search(cur):
            out['company'] = company[:200]

    role = (
        _labeled_value_from_text(text, r'Rolle\s*/\s*Position')
        or _labeled_value_from_text(text, r'Position|Rolle|Projektrolle|Funktion')
    )
    if role and not (out.get('role') or '').strip():
        out['role'] = role[:200]

    return out


def _usable_experience(exp) -> bool:
    """True wenn das Projekt mindestens ein sinnvolles Feld hat."""
    if not isinstance(exp, dict):
        return False
    return bool(
        (exp.get('period') or '').strip()
        or (exp.get('company') or '').strip()
        or (exp.get('role') or '').strip()
        or (exp.get('title') or '').strip()
        or exp.get('activities')
        or exp.get('technologies')
    )


def _aid_regex_project_fallback(text: str, exp: dict) -> dict:
    """Format-A/B Regex füllt fehlende Felder nach (Zeitraum gleiche/nächste Zeile)."""
    out = dict(exp) if isinstance(exp, dict) else {}
    if not (text or '').strip():
        return out
    regex_proj = None
    try:
        aid_ex = None
        try:
            from apps.cv_extractor.extractors.aid_regex_extractor import aid_regex_extractor as aid_ex
        except Exception:
            import importlib.util
            from pathlib import Path
            p = Path(__file__).resolve().parent / 'aid_regex_extractor.py'
            spec = importlib.util.spec_from_file_location('_aid_regex_fb', p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            aid_ex = mod.aid_regex_extractor
        regex_proj = aid_ex._parse_projekt_block_a(text)
        if not isinstance(regex_proj, dict) or not _usable_experience(regex_proj):
            # bpf / Format B: MM/YYYY – MM/YYYY Firma auf einer Zeile
            b_list = aid_ex._extract_projekte_format_b(text)
            if b_list:
                regex_proj = b_list[0]
    except Exception:
        regex_proj = None
    if not isinstance(regex_proj, dict):
        return out
    for key, val in regex_proj.items():
        if not val:
            continue
        cur = out.get(key)
        if cur in (None, '', [], {}):
            out[key] = val
    return out


def _normalize_project_fill(text: str, data) -> tuple:
    """
    LLM-Ergebnis → Liste nutzbarer Experience-Dicts.
    Immer Regex-Overlay; wenn leer → reiner Format-A/B-Fallback.
    Returns: (experiences: list[dict], used_regex_fallback: bool)
    """
    if not isinstance(data, dict):
        data = {}
    candidates = []
    if isinstance(data.get('experience'), dict):
        candidates = [data['experience']]
    elif isinstance(data.get('experience'), list):
        candidates = [e for e in data['experience'] if isinstance(e, dict)]
    elif any(
        (data.get(k) not in (None, '', [], {}))
        for k in ('period', 'company', 'role', 'title', 'activities', 'technologies')
    ):
        candidates = [data]

    filled = []
    for e in candidates:
        e2 = _regex_fill_experience_from_text(text, e)
        e2 = _aid_regex_project_fallback(text, e2)
        if _usable_experience(e2):
            filled.append(e2)

    used_fb = False
    if not filled:
        fb = _aid_regex_project_fallback(
            text, _regex_fill_experience_from_text(text, {})
        )
        if _usable_experience(fb):
            filled = [fb]
            used_fb = True
    return filled, used_fb


def _match_seed_for_group_text(text: str, seeded: list) -> dict:
    """Wenn Fill leer: Seed-Projekt anhand Zeitraum/Firma im Gruppentext."""
    if not (text or '').strip() or not seeded:
        return {}
    text_l = text.lower()
    best, best_score = None, 0
    for e in seeded:
        if not _usable_experience(e):
            continue
        score = 0
        period = e.get('period') or ''
        for d in re.findall(r'\d{1,2}[./]\d{4}', period):
            variants = {d, d.replace('.', '/'), d.replace('/', '.')}
            if any(v in text for v in variants):
                score += 2
        co = (e.get('company') or '').strip()
        if len(co) >= 4 and co.lower()[:16] in text_l:
            score += 3
        role = (e.get('role') or '').strip()
        if len(role) >= 4 and role.lower()[:16] in text_l:
            score += 1
        if score > best_score:
            best_score = score
            best = e
    if best_score >= 2 and best is not None:
        return dict(best)
    return {}


def _period_date_key(exp) -> str:
    """Nur Start(+Ende) ohne Firma — für Merge-Vergleiche."""
    if not isinstance(exp, dict):
        return ''
    p = (exp.get('period') or '').strip().lower()
    p = p.replace('—', '–').replace('-', '–')
    dates = re.findall(r'(\d{1,2})[./](\d{4})', p)
    if dates:
        parts = [f"{int(d[0]):02d}/{d[1]}" for d in dates[:2]]
        if re.search(r'(heute|dato|aktuell|laufend)', p):
            parts.append('dato')
        return '–'.join(parts)
    years = re.findall(r'(?<!\d)(\d{4})(?!\d)', p)
    if len(years) >= 2:
        return f'{years[0]}–{years[1]}'
    if years:
        base = years[0]
        if re.search(r'(heute|dato|aktuell|laufend|parallel)', p):
            base += '–dato'
        return base
    return re.sub(r'\s+', ' ', p)


def _company_norm(company: str) -> str:
    """Firma für Dedup: erster Segment vor Komma, lower, gekürzt."""
    c = re.sub(r'\s+', ' ', (company or '').strip().lower())
    c = c.split(',')[0].strip()
    return c[:48]


def _activity_fingerprint(exp) -> str:
    acts = exp.get('activities') if isinstance(exp, dict) else None
    a0 = (acts[0] if acts else '') or ((exp.get('title') or '') if isinstance(exp, dict) else '')
    return re.sub(r'\s+', ' ', (a0 or '').strip().lower())[:60]


def _acts_similar(a: str, b: str) -> bool:
    """True wenn Activities zusammengehören (kein zweites Parallel-Projekt).

    Leere Fingerprints: gleicher Slot (LLM-Hülle vs. Seed) → mergen, nicht
    als zweites Projekt werten. Beide leer = gleiches leeres Projekt.
    """
    a, b = (a or '').strip().lower(), (b or '').strip().lower()
    if not a and not b:
        return True
    if not a or not b:
        return True
    return a[:28] in b or b[:28] in a


def _experience_richness(exp) -> int:
    """Grober Score: ob Seed/LLM mehr Inhalt hat (Fill-Merge)."""
    if not isinstance(exp, dict):
        return 0
    score = 0
    for k in ('period', 'company', 'role', 'title', 'industry', 'location'):
        if (exp.get(k) or '').strip():
            score += 1
    acts = exp.get('activities') or []
    techs = exp.get('technologies') or []
    if isinstance(acts, list):
        score += min(4, len([a for a in acts if (a or '').strip()]))
        score += min(8, sum(len(str(a)) for a in acts if (a or '').strip()) // 40)
    if isinstance(techs, list):
        score += min(3, len([t for t in techs if (t or '').strip()]))
    return score


def _norm_list_item(s: str) -> str:
    return re.sub(r'\s+', ' ', (s or '').strip().lower())


def _list_items_similar(a: str, b: str) -> bool:
    """True wenn gleicher Activity/Tech-Slot (inkl. abgeschnittener Seed-Zeile)."""
    ca, cb = _norm_list_item(a), _norm_list_item(b)
    if not ca or not cb:
        return False
    if ca == cb or ca[:28] in cb or cb[:28] in ca:
        return True
    short, long = (ca, cb) if len(ca) <= len(cb) else (cb, ca)
    core = short.rstrip(':.,; ').strip()
    return len(core) >= 12 and core in long


def _merge_string_lists_prefer_richer(base_list, donor_list) -> list:
    """Vereinigt Listen: ähnliche Einträge → längere Formulierung behalten, neue anhängen."""
    merged = []
    for x in list(base_list or []) + list(donor_list or []):
        s = re.sub(r'\s+', ' ', str(x).strip()) if x is not None else ''
        if not s:
            continue
        replaced = False
        for i, cur in enumerate(merged):
            if not _list_items_similar(s, cur):
                continue
            if len(s) > len(str(cur).strip()) + 5:
                merged[i] = s
            replaced = True
            break
        if not replaced:
            merged.append(s)
    return merged


def _merge_experience_fields(base: dict, donor: dict) -> dict:
    """Füllt/ergänzt base aus donor — Activities/Techs werden vereinigt (nichts weglassen)."""
    if not isinstance(base, dict):
        base = {}
    out = dict(base)
    if not isinstance(donor, dict):
        return _clean_experience_technologies(out)
    for key, val in donor.items():
        if val in (None, '', [], {}):
            continue
        cur = out.get(key)
        if cur in (None, '', [], {}):
            out[key] = val
            continue
        if key in ('activities', 'technologies') and isinstance(cur, list) and isinstance(val, list):
            out[key] = _merge_string_lists_prefer_richer(cur, val)
        elif key in ('company', 'role', 'title', 'period', 'industry', 'location') and isinstance(cur, str) and isinstance(val, str):
            # Längere/informativere Formulierung behalten
            if len(val.strip()) > len(cur.strip()) + 8:
                out[key] = val
    return _clean_experience_technologies(out)


def _period_key(exp) -> str:
    """
    Normalisierter Zeitraum für Dedup.
    MM/YYYY: Datum+Firma+Activity-Fingerprint (zwei Fortinet 03/2024).
    Freitext „2005 – dato“: Datum+Firma.
    """
    if not isinstance(exp, dict):
        return ''
    date = _period_date_key(exp)
    if not date:
        return ''
    co = _company_norm(exp.get('company') or '')
    fp = _activity_fingerprint(exp)
    p = (exp.get('period') or '')
    if not re.search(r'\d{1,2}[./]\d{4}', p):
        return f'{date}|{co}' if co else date
    parts = [date]
    if co:
        parts.append(co)
    if fp:
        parts.append(fp[:40])
    return '|'.join(parts)


def _period_sort_key(exp) -> tuple:
    m = re.search(r'(\d{1,2})[./](\d{4})', (exp.get('period') or '') if isinstance(exp, dict) else '')
    if not m:
        years = re.findall(r'(?<!\d)(\d{4})(?!\d)', (exp.get('period') or '') if isinstance(exp, dict) else '')
        if years:
            return (int(years[0]), 0)
        return (0, 0)
    return (int(m.group(2)), int(m.group(1)))


_FOOTER_FIRMS = ('krone', 'cap gemini', 'umweltbundesamt')

_TECH_NOISE_RE = re.compile(
    r'(?i)(?<!\w)(?:'
    r'analyse|programmierung|migration|entwicklung|weiterentwicklung|'
    r'beratung|erstellung|anpassung|wartung|betreuung|optimierung|'
    r'fusion|redesign|unterstütz|dozent|bearbeitung|fehlerfall|'
    r'funktionalität|testing|programmänder|einsatzvorbereit|'
    r'abstimmung|fachabteilung|zusammenarbeit|deutschlandweit|'
    r'einberufung|kontaktgespräch|daten-?änderungs|software-?paket|'
    r'batchlauf|sachversicherung|rentenversicherung|privathaftpflicht|'
    r'lungen|gespräche|programmen'
    r')'
)


def _clean_experience_technologies(exp: dict) -> dict:
    """Activity-Fragmente aus technologies[] entfernen (LLM+Seed)."""
    if not isinstance(exp, dict):
        return exp
    techs = exp.get('technologies')
    if not techs:
        return exp
    cleaned = []
    seen = set()
    for t in techs:
        name = re.sub(r'\s+', ' ', (t or '').strip())
        if not name or len(name) > 55:
            continue
        if _TECH_NOISE_RE.search(name):
            continue
        if (
            re.search(r'(?i)\b(der|die|das|den|dem|mit|von|für|und|bei)\b', name)
            and len(name.split()) >= 3
        ):
            continue
        lw = name.lower()
        if lw in seen:
            continue
        seen.add(lw)
        cleaned.append(name)
    out = dict(exp)
    out['technologies'] = cleaned
    return out


def _company_soft_match(a: str, b: str) -> bool:
    """Firma grob gleich (LLM kürzt/erweitert oft den Kundennamen)."""
    na, nb = _company_norm(a), _company_norm(b)
    if not na or not nb:
        return True
    if na == nb:
        return True
    short = min(len(na), len(nb), 16)
    if short < 4:
        return na == nb
    return na[:short] in nb or nb[:short] in na


def _merge_experience(seed, llm) -> list:
    """
    Regex-Seed ist kanonisch (AID Fast-Path); LLM reichert nur an.

    - Seed vorhanden: Parallel-Projekte (zwei Fortinet) nur aus Seed.
      LLM-Treffer ohne Seed-Match werden verworfen (Label-Overcount).
    - Seed leer: LLM-only mit Dedup (Nicht-AID).
    - Jahresrange-Footer (Krone/Cap/UBA): Seed gewinnt.
    """
    seed = [e for e in (seed or []) if _usable_experience(e)]
    llm = [e for e in (llm or []) if _usable_experience(e)]

    footer_by_date = {}
    for e in seed:
        period = e.get('period') or ''
        if re.search(r'\d{1,2}[./]\d{4}', period):
            continue
        co = (e.get('company') or '').lower()
        if not any(f in co for f in _FOOTER_FIRMS):
            continue
        dk = _period_date_key(e)
        if dk:
            footer_by_date[dk] = e

    out = []
    seen_groups = {}

    def _group_key(e) -> str:
        return f"{_period_date_key(e)}|{_company_norm(e.get('company') or '')}"

    def _add_canonical(e) -> None:
        """Seed (oder LLM-only): gleiche date|firma + ähnliche Acts → mergen, sonst parallel."""
        gk = _group_key(e)
        fp = _activity_fingerprint(e)
        existing = seen_groups.get(gk)
        if existing is None:
            seen_groups[gk] = [fp]
            out.append(_clean_experience_technologies(e))
            return
        for i, item in enumerate(out):
            if _group_key(item) != gk:
                continue
            if not _acts_similar(fp, _activity_fingerprint(item)):
                continue
            out[i] = _merge_experience_fields(item, e)
            new_fp = _activity_fingerprint(out[i])
            if new_fp and new_fp not in existing:
                existing.append(new_fp)
            return
        existing.append(fp)
        out.append(_clean_experience_technologies(e))

    def _find_seed_target(e):
        """Index in out für LLM-Enrich; None = verwerfen."""
        dk = _period_date_key(e)
        if not dk:
            return None
        period = e.get('period') or ''
        if dk in footer_by_date and not re.search(r'\d{1,2}[./]\d{4}', period):
            return None
        candidates = []
        for i, item in enumerate(out):
            if _period_date_key(item) != dk:
                continue
            if not _company_soft_match(e.get('company') or '', item.get('company') or ''):
                continue
            candidates.append(i)
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        fp = _activity_fingerprint(e)
        if not fp:
            # Leere LLM-Hülle bei Parallel-Slots: nicht raten
            return None
        best_i, best = candidates[0], -1
        for i in candidates:
            ifp = _activity_fingerprint(out[i])
            score = 0
            if _acts_similar(fp, ifp):
                score = 2
            if ifp and (fp[:24] in ifp or ifp[:24] in fp):
                score = 3
            if score > best:
                best, best_i = score, i
        return best_i if best > 0 else candidates[0]

    if seed:
        for e in seed:
            _add_canonical(e)
        for dk, e in footer_by_date.items():
            gk = _group_key(e)
            if gk not in seen_groups:
                seen_groups[gk] = [_activity_fingerprint(e)]
                out.append(_clean_experience_technologies(e))
        for e in llm:
            idx = _find_seed_target(e)
            if idx is None:
                continue
            out[idx] = _merge_experience_fields(out[idx], e)
        out.sort(key=_period_sort_key, reverse=True)
        return out

    # Kein Seed → LLM-only Dedup
    for e in llm:
        period = e.get('period') or ''
        dk = _period_date_key(e)
        if dk in footer_by_date and not re.search(r'\d{1,2}[./]\d{4}', period):
            continue
        _add_canonical(e)
    out.sort(key=_period_sort_key, reverse=True)
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
    n = (name or '').strip().lower().rstrip(':')
    if not n or len(n) < 3:
        return True
    if re.match(r'(?i)^qualifikationsprofil\s*:\s*aid-', n):
        return True
    if re.match(r'(?i)^(sehr\s+gute|fortgeschrittene|gute|grund)\s*kenntnisse$', n):
        return True
    if 'produkte' in n and 'standard' in n:
        return True
    noise = (
        'zertifizierungen', 'schulungen', 'schulungen / kurse', 'schulungen/kurse',
        'examen', 'examen | prüfungen', 'examen|prüfungen', 'ausbildung',
        'fachbereiche', 'branchen', 'persönliche daten',
        'programmiersprachen', 'programmiersprache', 'betriebssysteme',
        'allgemeine kenntnisse', 'technische kenntnisse', 'sonstige skills',
        'datenbanken', 'hardware', 'datenkommunikation',
    )
    return n in noise


def _merge_str_lists(seed, llm) -> list:
    """P3: Regex-Seed behalten, LLM-Einträge ergänzen (keine LLM-Sperre)."""
    out = []
    seen = set()
    for item in list(seed or []) + list(llm or []):
        if not isinstance(item, str):
            continue
        name = item.strip()
        if not name or _is_section_noise_name(name):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def _merge_personal(seed, llm) -> dict:
    """R0/P3: Regex-Personal behalten, LLM füllt Lücken (kein Seed-Wipe)."""
    out = dict(seed or {}) if isinstance(seed, dict) else {}
    llm = llm if isinstance(llm, dict) else {}
    for k, v in llm.items():
        if k == 'education':
            continue  # education separat gemerged
        if v in (None, '', [], {}):
            continue
        if k == 'languages':
            merged_langs, seen = [], set()
            for src in (out.get('languages') or [], v if isinstance(v, list) else []):
                for lang in src:
                    if isinstance(lang, dict):
                        name = (lang.get('name') or '').strip()
                        item = {
                            'name': name,
                            'level': (lang.get('level') or ''),
                        }
                    elif isinstance(lang, str) and lang.strip():
                        name = lang.strip()
                        item = {'name': name, 'level': ''}
                    else:
                        continue
                    if not name:
                        continue
                    key = name.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    merged_langs.append(item)
            if merged_langs:
                out['languages'] = merged_langs
            continue
        cur = out.get(k)
        if cur in (None, '', [], {}):
            out[k] = v
        # sonst Seed behalten (AID-Regex ist für Geburtsjahr etc. zuverlässig)
    return out


def _norm_focus_experience(items) -> list:
    """focus_experience → [{name, category, sort_order}, ...]."""
    norm = []
    for idx, item in enumerate(items or []):
        if isinstance(item, dict):
            name = (item.get('name') or '').strip()
            if not name or _is_section_noise_name(name):
                continue
            norm.append({
                'name':       name,
                'category':   (item.get('category') or 'product_standard'),
                'sort_order': item.get('sort_order', idx),
            })
        elif isinstance(item, str) and item.strip():
            name = item.strip()
            if _is_section_noise_name(name):
                continue
            norm.append({
                'name':       name,
                'category':   'product_standard',
                'sort_order': idx,
            })
    for i, fe in enumerate(norm):
        fe['sort_order'] = i
    return norm


def _merge_named_dicts(seed, llm) -> list:
    """P3: Zertifikate u.ä. — Seed + LLM nach name mergen."""
    out = []
    seen = set()
    for c in list(seed or []) + list(llm or []):
        if isinstance(c, str):
            name = c.strip()
            item = {'name': name}
        elif isinstance(c, dict):
            item = dict(c)
            name = (item.get('name') or '').strip()
        else:
            continue
        if not name or _is_section_noise_name(name):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        item['name'] = name
        out.append(item)
    return out


def _norm_edu_period(period: str) -> str:
    """'1985 - 1989' / '1985–1989' → '1985-1989'."""
    p = (period or '').strip().lower()
    p = p.replace('–', '-').replace('—', '-')
    p = re.sub(r'\s+', '', p)
    return p


_EDU_STOP = {
    'zum', 'zur', 'und', 'oder', 'der', 'die', 'das', 'den', 'dem', 'des',
    'bei', 'von', 'vom', 'für', 'mit', 'aus', 'als', 'the', 'and', 'for',
    'germany', 'deutschland', 'studium', 'ausbildung', 'fernstudium',
}


def _edu_sig_tokens(text: str) -> set:
    """Signifikante Tokens für Education-Overlap (allgemein)."""
    raw = re.findall(r'[A-Za-zÄÖÜäöüß0-9]{3,}', (text or '').lower())
    return {t for t in raw if t not in _EDU_STOP}


def _edu_full_text(e: dict) -> str:
    parts = [
        (e.get('degree') or '').strip(),
        (e.get('institution') or '').strip(),
        (e.get('description') or '').strip(),
    ]
    return ' '.join(p for p in parts if p)


def _edu_is_same_degree(a: dict, b: dict) -> bool:
    """
    True wenn a/b denselben Ausbildungsabschluss beschreiben.
    Deckt u.a. LLM-Kurzform 'Programmierer'+Institution vs.
    Regex-Langform 'Fernstudium Programmierer ILS Hamburg, Germany'.
    """
    da = (a.get('degree') or '').strip().lower()
    db = (b.get('degree') or '').strip().lower()
    if not da or not db:
        return False
    if da == db:
        return True
    if da in db or db in da:
        return True

    ia = (a.get('institution') or '').strip().lower()
    ib = (b.get('institution') or '').strip().lower()
    full_a = f'{da} {ia}'.strip()
    full_b = f'{db} {ib}'.strip()
    if full_a and full_b and (full_a in full_b or full_b in full_a):
        return True

    # Institution der einen Seite steckt in Degree der anderen + Token-Overlap
    if ia and len(ia) >= 3 and ia in db:
        ta, tb = _edu_sig_tokens(da), _edu_sig_tokens(db)
        if ta and tb and (ta <= tb or tb <= ta or len(ta & tb) >= max(1, min(len(ta), len(tb)))):
            return True
    if ib and len(ib) >= 3 and ib in da:
        ta, tb = _edu_sig_tokens(da), _edu_sig_tokens(db)
        if ta and tb and (ta <= tb or tb <= ta or len(ta & tb) >= max(1, min(len(ta), len(tb)))):
            return True

    ta, tb = _edu_sig_tokens(full_a), _edu_sig_tokens(full_b)
    if not ta or not tb:
        return False
    inter = ta & tb
    # starker Overlap: kürzere Tokenmenge fast ganz in längerer
    shorter, longer = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if len(shorter) >= 1 and shorter <= longer:
        return True
    if len(shorter) >= 2 and len(inter) >= max(2, int(0.7 * len(shorter))):
        return True
    return False


def _edu_prefer_richer(keep: dict, other: dict) -> dict:
    """Reicht keep mit Feldern aus other an; längerer degree gewinnt."""
    out = dict(keep)
    kd = (out.get('degree') or '').strip()
    od = (other.get('degree') or '').strip()
    if len(od) > len(kd):
        out['degree'] = od
        kd = od
    if other.get('period') and not (out.get('period') or '').strip():
        out['period'] = other.get('period')
    # Institution nur wenn nicht schon im Degree-Text
    inst = (other.get('institution') or out.get('institution') or '').strip()
    if inst and inst.lower() not in kd.lower():
        out['institution'] = inst
    else:
        # Institution redundant → leeren (verhindert "Degree @ Institution"-Doppelung)
        cur_inst = (out.get('institution') or '').strip()
        if cur_inst and cur_inst.lower() in (out.get('degree') or '').lower():
            out['institution'] = ''
    odsc = (other.get('description') or '').strip()
    kdsc = (out.get('description') or '').strip()
    if odsc and odsc.lower() not in kdsc.lower():
        out['description'] = (kdsc + '; ' + odsc).strip('; ') if kdsc else odsc
    return out


def _merge_education(existing, incoming):
    """
    Dedup merge education lists.
    - gleicher degree+type → skip/anreichern
    - gleiche Periode + type=degree → behalte längere Beschreibung
    - semantischer Overlap (Kurzform+Institution vs. Langform) → anreichern
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
            if et == 'degree' and _edu_is_same_degree(e, m):
                return i
            mper = _norm_edu_period(m.get('period'))
            if et == 'degree' and per and mper and per == mper:
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
        # Institution im Degree → nicht separat halten
        inst = (e.get('institution') or '').strip()
        if inst and inst.lower() in degree.lower():
            e['institution'] = ''
        idx = _find_dup(e)
        if idx is None:
            merged.append(e)
            added += 1
            continue
        merged[idx] = _edu_prefer_richer(merged[idx], e)
    return merged, added


def _finalize_education(items):
    """Abschluss-Dedup: Periode, semantischer Overlap, redundante Institution."""
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
        # Institution redundant zum Degree entfernen
        inst = (e.get('institution') or '').strip()
        if inst and inst.lower() in deg.lower():
            e['institution'] = ''
        if not per:
            no_period.append(e)
            continue
        prev = by_period.get(per)
        if not prev:
            by_period[per] = e
        else:
            by_period[per] = _edu_prefer_richer(prev, e)

    # no_period: drop/merge if same as period-entry OR other no_period
    kept_np = []
    period_entries = list(by_period.values())
    for e in no_period:
        # gegen Perioden-Einträge
        hit = None
        for i, p in enumerate(period_entries):
            if _edu_is_same_degree(e, p):
                hit = ('period', i)
                break
        if hit:
            period_entries[hit[1]] = _edu_prefer_richer(period_entries[hit[1]], e)
            # sync back into by_period
            per = _norm_edu_period(period_entries[hit[1]].get('period'))
            if per:
                by_period[per] = period_entries[hit[1]]
            continue
        # gegen bereits behaltene no_period
        merged_into = False
        for i, k in enumerate(kept_np):
            if _edu_is_same_degree(e, k):
                # längeren Degree behalten
                if len((e.get('degree') or '')) >= len((k.get('degree') or '')):
                    kept_np[i] = _edu_prefer_richer(e, k)
                else:
                    kept_np[i] = _edu_prefer_richer(k, e)
                merged_into = True
                break
        if not merged_into:
            kept_np.append(e)

    # courses exact dedup
    seen_c, courses_out = set(), []
    for e in courses:
        k = (e.get('degree') or '').strip().lower()
        if not k or k in seen_c:
            continue
        seen_c.add(k)
        courses_out.append(e)

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
        if aid_extracted.get('personal'):
            pre_json['extracted_data']['personal'] = _merge_personal(
                {}, aid_extracted['personal']
            )
        if aid_extracted.get('headline'):
            pre_json['metadata']['headline'] = aid_extracted['headline']
            pre_json['extracted_data'].setdefault('personal', {})['headline'] = aid_extracted['headline']
        if aid_extracted.get('certifications'):
            cleaned = []
            for c in aid_extracted['certifications']:
                name = (c.get('name') if isinstance(c, dict) else str(c) or '').strip()
                if name and not _is_section_noise_name(name):
                    cleaned.append(c if isinstance(c, dict) else {'name': name})
            pre_json['extracted_data']['certifications'] = cleaned
        if aid_extracted.get('industries'):
            pre_json['extracted_data']['industries'] = [
                i for i in aid_extracted['industries']
                if isinstance(i, str) and not _is_section_noise_name(i)
            ]
        if aid_extracted.get('focus_areas'):
            pre_json['extracted_data']['focus_areas'] = [
                f for f in aid_extracted['focus_areas']
                if isinstance(f, str) and not _is_section_noise_name(f) and len(f) > 3
            ]
        if aid_extracted.get('focus_experience'):
            pre_json['extracted_data']['focus_experience'] = _norm_focus_experience(
                aid_extracted['focus_experience']
            )
        if aid_extracted.get('experience'):
            # Regex-Projekte vorbelegen — LLM ergänzt, fehlende Perioden bleiben (bpf)
            pre_json['extracted_data']['experience'] = [
                e for e in aid_extracted['experience'] if _usable_experience(e)
            ]
        if aid_extracted.get('education'):
            # Regex-Ausbildung vorbelegen (LLM/PERSONAL darf später ergänzen, nicht löschen)
            pre_json['extracted_data']['education'] = _norm_education_items(
                aid_extracted['education'], default_type='degree'
            )
        if aid_extracted.get('skill_ablage'):
            pre_json['extracted_data']['skill_ablage'] = [
                s for s in aid_extracted['skill_ablage']
                if isinstance(s, dict) and (s.get('name') or '').strip()
            ]

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
        seeded_p = pre_json['extracted_data'].get('personal') or {}
        merged_p = _merge_personal(seeded_p, results['PERSONAL'])
        pre_json['extracted_data']['personal'] = merged_p
        if seeded_p:
            print(
                f"    personal gemerged: seed_keys={len(seeded_p)} → {len(merged_p)}"
            )
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
        # personal.languages sicher als [{name, level}]
        raw_langs = merged_p.get('languages', [])
        norm_langs = []
        for lang in raw_langs:
            if isinstance(lang, dict):
                name = (lang.get("name") or "").strip()
                if name:
                    norm_langs.append({"name": name, "level": lang.get("level", "")})
            elif isinstance(lang, str) and lang.strip():
                norm_langs.append({"name": lang.strip(), "level": ""})
        if norm_langs:
            pre_json['extracted_data']['personal']['languages'] = norm_langs
            print(f"    languages normalisiert: {len(norm_langs)} Einträge")

    if results.get('FACHBEREICHE'):
        llm_fa = results['FACHBEREICHE'].get('focus_areas', []) or []
        seeded = pre_json['extracted_data'].get('focus_areas') or []
        merged_fa = _merge_str_lists(seeded, llm_fa)
        pre_json['extracted_data']['focus_areas'] = merged_fa
        if seeded and llm_fa:
            print(f"    fachbereiche gemerged: seed={len(seeded)} + llm → {len(merged_fa)}")

    if results.get('ZERTIFIKATE'):
        raw_certs = results['ZERTIFIKATE'].get('certifications', []) or []
        seeded_c = pre_json['extracted_data'].get('certifications') or []
        merged_c = _merge_named_dicts(seeded_c, raw_certs)
        pre_json['extracted_data']['certifications'] = merged_c
        if seeded_c and raw_certs:
            print(f"    zertifikate gemerged: seed={len(seeded_c)} + llm → {len(merged_c)}")

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

    if results.get('BRANCHEN'):
        llm_ind = results['BRANCHEN'].get('industries', []) or []
        seeded_i = pre_json['extracted_data'].get('industries') or []
        merged_i = _merge_str_lists(seeded_i, llm_ind)
        pre_json['extracted_data']['industries'] = merged_i
        if seeded_i and llm_ind:
            print(f"    branchen gemerged: seed={len(seeded_i)} + llm → {len(merged_i)}")

    if results.get('FOCUS_EXP'):
        llm_focus = _norm_focus_experience(
            results['FOCUS_EXP'].get('focus_experience', [])
        )
        seeded_fe = pre_json['extracted_data'].get('focus_experience') or []
        merged_fe = _merge_named_dicts(seeded_fe, llm_focus)
        # sort_order neu nummerieren; Kategorie default
        for i, fe in enumerate(merged_fe):
            fe.setdefault('category', 'product_standard')
            fe['sort_order'] = i
        pre_json['extracted_data']['focus_experience'] = merged_fe
        print(
            f"    focus_experience gemerged: seed={len(seeded_fe)} + llm={len(llm_focus)} "
            f"→ {len(merged_fe)}"
        )
    elif pre_json['extracted_data'].get('focus_experience'):
        print(
            f"    focus_experience aus Regex-Seed: "
            f"{len(pre_json['extracted_data']['focus_experience'])} Einträge"
        )

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
        seeded_exp = [
            e for e in (pre_json['extracted_data'].get('experience') or [])
            if _usable_experience(e)
        ]

        def _run_proj(lg):
            g = gruppen_by_idx.get(lg['index'])
            if not g:
                return lg['index'], [], False
            text = gruppe_to_volltext(g, block_by_nr)
            if not text.strip():
                return lg['index'], [], False
            data = MasterBaseExtractor(
                'main_extract_experience', consultant_type
            ).extract(text)
            filled, used_fb = _normalize_project_fill(text, data)
            if not filled:
                # Letzter Versuch: Seed anhand Zeitraum/Firma im Gruppentext
                seed_hit = _match_seed_for_group_text(text, seeded_exp)
                if _usable_experience(seed_hit):
                    filled = [seed_hit]
                    used_fb = True
            return lg['index'], filled, used_fb

        all_exp  = []
        proj_map = {}
        with ThreadPoolExecutor(max_workers=10) as ex:
            futs = {ex.submit(_run_proj, lg): lg['index'] for lg in proj_gruppen}
            for f in as_completed(futs):
                idx, filled, used_fb = f.result()
                proj_map[idx] = filled
                ok = bool(filled) and any(_usable_experience(e) for e in filled)
                tag = ' ✅' if ok else ' ❌'
                if ok and used_fb:
                    tag += ' (regex/seed-fallback)'
                print(f"    Projekt {idx}:{tag}")

        for lg in proj_gruppen:
            filled = proj_map.get(lg['index']) or []
            if not filled:
                g = gruppen_by_idx.get(lg['index'])
                if not g:
                    continue
                text = gruppe_to_volltext(g, block_by_nr)
                fb_list, _ = _normalize_project_fill(text, {})
                if not fb_list:
                    seed_hit = _match_seed_for_group_text(text, seeded_exp)
                    if _usable_experience(seed_hit):
                        fb_list = [seed_hit]
                filled = fb_list
            all_exp.extend(e for e in filled if _usable_experience(e))

        merged_exp = _merge_experience(seeded_exp, all_exp)
        pre_json['extracted_data']['experience'] = merged_exp
        print(
            f"  {len(merged_exp)} Projekte extrahiert "
            f"(seed={len(seeded_exp)}, fill={len(all_exp)})"
        )
    elif pre_json['extracted_data'].get('experience'):
        # Keine PROJECT-Labels — Regex-Seed behalten (bpf ohne Group-Treffer)
        seeded_exp = [
            e for e in pre_json['extracted_data']['experience'] if _usable_experience(e)
        ]
        seeded_exp.sort(key=_period_sort_key, reverse=True)
        pre_json['extracted_data']['experience'] = seeded_exp
        print(f"  {len(seeded_exp)} Projekte aus Regex-Seed (keine PROJECT-Labels)")

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
