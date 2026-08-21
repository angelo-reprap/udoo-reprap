"""
matching_weight_probe.py — gemeinsame Weight-Logik für Pipeline + Wild-Text.

Wiederverwendet die Formel aus main_skill_normalizer (_count_to_weight / _parse_months),
ohne den vollen SkillNormalizer (kein DB-Write, keine Kategorisierung).

Wild-Text: Datums-Anker → Segmente → Skill-Treffer → projects/months/freq → weight.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# ── Zeitraum (angelehnt an main_skill_normalizer._parse_months) ───────────────

_DATE_SPAN_RE = re.compile(
    r'(?:'
    r'(?:\d{4}-\d{2}\s*[–—\-]+\s*(?:\d{4}-\d{2}|heute|dato|aktuell|laufend|present|current|now))'
    r'|(?:\d{1,2}[/.\-]\d{4}\s*[–—\-bis]+\s*(?:\d{1,2}[/.\-]\d{4}|heute|dato|aktuell|laufend|present|current|now))'
    r'|(?:seit\s+\d{1,2}[/.\-]\d{4})'
    r'|(?:\d{4}\s*[–—\-]+\s*(?:\d{4}|heute|dato|aktuell|laufend|present|current|now))'
    r')',
    re.IGNORECASE,
)


def parse_months(period: str) -> int:
    if not period or not str(period).strip():
        return 0
    now = datetime.now()

    def _today_month():
        if now.day <= 15:
            return now.year, now.month
        if now.month == 12:
            return now.year + 1, 1
        return now.year, now.month + 1

    raw = period.strip()
    m = re.search(r'(\d{4})-(\d{2})\s*[–—\-]+\s*(\d{4})-(\d{2})', raw)
    if m:
        from_y, from_m = int(m.group(1)), int(m.group(2))
        to_y, to_m = int(m.group(3)), int(m.group(4))
        return max(1, (to_y * 12 + to_m) - (from_y * 12 + from_m) + 1)

    m = re.search(
        r'(\d{4})-(\d{2})\s*[–—\-]+\s*(heute|dato|aktuell|laufend|present|current|now)',
        raw, re.I,
    )
    if m:
        from_y, from_m = int(m.group(1)), int(m.group(2))
        end_y, end_m = _today_month()
        return max(6, (end_y * 12 + end_m) - (from_y * 12 + from_m) + 1)

    p = raw.replace('–', '-').replace('—', '-').replace('bis', '-')
    p = p.replace('\\', '/').replace('.', '/')
    p = re.sub(r'[*_~`|]', '', p)
    p = re.sub(r'\s*-+\s*', ' - ', p)
    p = re.sub(r'\s+', ' ', p).strip()

    m = re.search(r'(\d{1,2})[/](\d{4})\s*-\s*(\d{1,2})[/](\d{4})', p)
    if m:
        from_m, from_y = int(m.group(1)), int(m.group(2))
        to_m, to_y = int(m.group(3)), int(m.group(4))
        return max(1, (to_y * 12 + to_m) - (from_y * 12 + from_m) + 1)

    m = re.search(
        r'(\d{1,2})[/](\d{4})\s*-\s*(heute|dato|aktuell|laufend|present|current)',
        p, re.I,
    )
    if m:
        from_m, from_y = int(m.group(1)), int(m.group(2))
        end_y, end_m = _today_month()
        return max(6, (end_y * 12 + end_m) - (from_y * 12 + from_m) + 1)

    m = re.search(r'seit\s+(\d{1,2})[/](\d{4})', p, re.I)
    if m:
        from_m, from_y = int(m.group(1)), int(m.group(2))
        end_y, end_m = _today_month()
        return max(6, (end_y * 12 + end_m) - (from_y * 12 + from_m) + 1)

    m = re.search(r'(\d{4})\s*-\s*(\d{4})', p)
    if m:
        return max(12, (int(m.group(2)) - int(m.group(1))) * 12)

    m = re.search(r'(\d{4})\s*-\s*(heute|dato|aktuell|laufend|present|current)', p, re.I)
    if m:
        return 6

    m = re.search(r'(\d{1,2})[/](\d{4})', p)
    if m:
        return 6
    return 0


def get_months(period: str) -> int:
    months = parse_months(period)
    return max(6, months) if months > 0 else 6


def count_to_weight(count: int, project_count: int = 1, total_months: int = 0) -> float:
    """50% Monate / 40% Projekte / 10% Count — identisch zum Enricher."""
    if total_months >= 60:
        month_score = 1.0
    elif total_months >= 36:
        month_score = 0.85
    elif total_months >= 12:
        month_score = 0.70
    elif total_months >= 6:
        month_score = 0.50
    else:
        month_score = 0.30

    if project_count >= 5:
        proj_score = 1.0
    elif project_count >= 3:
        proj_score = 0.75
    elif project_count >= 2:
        proj_score = 0.50
    else:
        proj_score = 0.25

    if count >= 10:
        count_score = 1.0
    elif count >= 5:
        count_score = 0.75
    elif count >= 2:
        count_score = 0.50
    else:
        count_score = 0.25

    weight = (month_score * 0.50) + (proj_score * 0.40) + (count_score * 0.10)
    return round(min(weight, 0.95), 2)


def skill_token_pattern(skill: str) -> re.Pattern:
    """Wortgrenzen, case-insensitive. C++ / .NET etc. escaped."""
    esc = re.escape(skill.strip())
    # erlaube . + # in Tokens
    return re.compile(rf'(?<![\w]){esc}(?![\w])', re.IGNORECASE)


def segment_by_dates(text: str) -> List[Tuple[str, str]]:
    """
    Schneidet Text an Datums-Spans.
    Rückgabe: [(period_label, segment_text), ...]
    period_label = der führende Datums-Match des Segments (oder '').
    """
    if not text or not text.strip():
        return []
    matches = list(_DATE_SPAN_RE.finditer(text))
    if not matches:
        return [('', text)]

    segments: List[Tuple[str, str]] = []
    # Text vor erstem Datum
    if matches[0].start() > 0:
        head = text[: matches[0].start()].strip()
        if head:
            segments.append(('', head))

    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[start:end].strip()
        if chunk:
            segments.append((m.group(0).strip(), chunk))
    return segments


def skill_stats_from_wild_text(
    text: str,
    skills: List[str],
) -> List[Dict]:
    """
    Pro Skill: freq (Treffer gesamt), projects (Segmente mit Treffer),
    months (Summe Perioden der Segmente), weight.
    """
    if not text or not skills:
        return []
    segments = segment_by_dates(text)
    out = []
    for skill in skills:
        if not skill or len(skill.strip()) < 2:
            continue
        pat = skill_token_pattern(skill)
        freq = 0
        project_count = 0
        total_months = 0
        hit_periods = []
        seen_periods = set()
        for period, seg in segments:
            hits = pat.findall(seg)
            if not hits:
                continue
            n = len(hits)
            freq += n
            project_count += 1
            months = get_months(period) if period else 6
            # gleiche Perioden-Labels nicht doppelt zur Laufzeit addieren
            pkey = (period or '').strip().lower()
            if pkey and pkey not in seen_periods:
                seen_periods.add(pkey)
                total_months += months
            elif not pkey:
                total_months += months
            hit_periods.append({'period': period or None, 'hits': n, 'months': months})

        if freq == 0:
            continue
        project_count = max(1, project_count)
        total_months = max(6, total_months)
        # Cap: unrealistische Summen (z.B. 30+ Jahre durch Parsing) begrenzen
        total_months = min(total_months, 240)  # max 20 Jahre
        weight = count_to_weight(freq, project_count, total_months)
        out.append({
            'name': skill.strip(),
            'name_lc': skill.strip().lower(),
            'freq': freq,
            'projects': project_count,
            'months': total_months,
            'years': round(total_months / 12.0, 2),
            'weight': weight,
            'segments': hit_periods[:8],
        })
    out.sort(key=lambda x: (-x['weight'], -x['freq'], x['name_lc']))
    return out


def _safe_skill_key(name: str) -> str:
    """ES object-keys dürfen nicht mit '.' starten/enden und keine Pfad-Konflikte erzeugen.
    Deshalb speichern wir Weights nicht als dynamic object, sondern nur sanitized falls nötig.
    """
    s = (name or '').strip().lower()
    s = re.sub(r'\s+', '_', s)
    s = re.sub(r'[^a-z0-9_+\-#]', '_', s)
    s = s.strip('._')
    if not s or s in ('.', '_'):
        return ''
    # führenden Punkt (z.B. .net) absichern
    if s.startswith('.'):
        s = 'dot_' + s.lstrip('.')
    return s[:80]


def normalize_pipeline_skill_name(name: str) -> str:
    """
    Reinigt Enricher-Labels für Matching:
      'Java: Grundlagen' → 'Java'
      '2003 Server (tiefes Know-How)' → '2003 Server' (danach Filter)
    """
    n = (name or '').strip()
    if not n:
        return ''
    # Level-Suffix in Klammern
    n = re.sub(
        r'\s*\((?:'
        r'(?:tiefes?\s+)?know-?how|grundlagen|basics?|advanced|expert|'
        r'sehr\s+gute?\s+kenntnisse|gute\s+kenntnisse|kenntnisse'
        r')\)\s*$',
        '',
        n,
        flags=re.I,
    )
    # 'Skill: Grundlagen' / 'Skill - gut'
    n = re.sub(
        r'\s*[:\-–—]\s*'
        r'(?:grundlagen|kenntnisse|basics?|advanced|expert|'
        r'tiefes?\s+know-?how|sehr\s+gut|gut|mittel|anfaenger|anfänger)\s*$',
        '',
        n,
        flags=re.I,
    )
    n = re.sub(r'\s+', ' ', n).strip(' :-–—')
    return n


# Tech-Kategorien aus der Skill-DB (SkillCategory / category_name), die für Matching zählen.
# "Sonstige Skills" / Soft Skills absichtlich aus — dort landet der Enricher-Müll.
MATCHING_SKILL_CATEGORIES = frozenset({
    'Programmiersprachen',
    'Frameworks und Bibliotheken',
    'Datenbanken',
    'Cloud-Plattformen',
    'DevOps Tools',
    'CI/CD Tools',
    'Betriebssysteme',
    'IT-Infrastruktur',
    'Netzwerkprotokolle',
    'Virtualisierung',
    'Security Tools',
    'Testing Tools',
    'Versionsverwaltung',
    'Identity Management',
    'Architekturmuster',
    'Datenformate',
    'Datenmanagement',
    'Business Software',
    'Entwicklungsumgebungen',
    'Monitoring Tools',
})

# Zu generisch auch innerhalb erlaubter Kategorien
_GENERIC_SKILL_NAMES = frozenset({
    'server', 'client', 'software', 'hardware', 'tools', 'tool',
    'system', 'systems', 'application', 'applications', 'framework',
    'database', 'cloud', 'network', 'networking', 'os', 'pc',
})


def skill_category_allowed(category_name: str) -> bool:
    cat = (category_name or '').strip()
    if not cat:
        return False
    return cat in MATCHING_SKILL_CATEGORIES


def is_plausible_skill_name(name: str) -> bool:
    """Filtert offensichtlichen Müll aus der Pipeline-Skill-DB für den Probe-Index."""
    n = normalize_pipeline_skill_name(name) if name else ''
    if len(n) < 2 or len(n) > 40:
        return False
    low = n.lower()
    # reine Zahlen / Jahreszahlen / Versionsschrott
    if re.fullmatch(r'\d{1,4}', n):
        return False
    if re.fullmatch(r'(19|20)\d{2}', n):
        return False
    # '2003 Server', '95/98SE/ME', 'Windows 95/98'
    if re.match(r'^(19|20)\d{2}\b', n):
        return False
    if re.match(r'^\d{1,2}\s*/\s*\d{1,2}', n):
        return False
    if re.fullmatch(r'[\d./x]+', low):
        return False
    # abgeschnittene Klammern / Fragmente: 'R6)', '(S)FTP)' ok nur wenn ausgewogen
    if n.endswith(')') and n.count('(') < n.count(')'):
        return False
    if n.startswith('(') and n.count('(') > n.count(')'):
        return False
    # alte OS-/Versionskürzel ohne echten Skill-Wert für Matching
    if re.fullmatch(r'(nt\d*|win\d{0,2}|w2k|w2k3|dos|dr-?dos|os/?2|r\d+)', low):
        return False
    # Satzfragmente / Level-Reste
    junk_parts = (
        'kenntnisse', 'erfahrung', 'grundkenntnisse', 'gute kenntnisse',
        'sehr gute', 'länger her', 'aktuell nicht', 'jahr ', 'jahre',
        'gemacht habe', 'in denen ich', 'alle bis heute', 'alle letzten',
        'tiefes know', 'know-how', 'grundlagen',
    )
    if any(j in low for j in junk_parts):
        return False
    if low.count(' ') > 4:
        return False
    # abgebrochene Tokens / OS-Müll
    if n.endswith(('....)', '…', '...')):
        return False
    if low in ('access', 'approach', 'word', 'excel', 'powerpoint', 'outlook', 'rexx'):
        # zu generisch / Legacy für Tech-Matching
        return False
    if low in _GENERIC_SKILL_NAMES:
        return False
    return True


def skill_stats_from_pipeline(consultant, *, require_category: bool = True) -> List[Dict]:
    """
    Liest ConsultantSkill.weight (+ Name).

    Nutzt die Skill-DB-Kategorie (ConsultantSkill.category_name bzw. Skill.category_name)
    als Allowlist — nicht die rohe Skill-Tabelle (die enthält denselben Müll).
    """
    rows = []
    try:
        qs = consultant.skills.select_related('skill').all()
    except Exception:
        return rows
    for cs in qs:
        raw = getattr(getattr(cs, 'skill', None), 'name', None) or ''
        name = normalize_pipeline_skill_name(raw)
        if not name or not is_plausible_skill_name(name):
            continue
        cat = (
            (getattr(cs, 'category_name', None) or '').strip()
            or (getattr(getattr(cs, 'skill', None), 'category_name', None) or '').strip()
        )
        if require_category and not skill_category_allowed(cat):
            continue
        w = float(getattr(cs, 'weight', 0.5) or 0.5)
        rows.append({
            'name': name,
            'name_lc': name.lower(),
            'raw_name': raw if raw != name else None,
            'category': cat,
            'freq': None,
            'projects': None,
            'months': None,
            'years': None,
            'weight': round(w, 2),
            'segments': [],
            'from_db': True,
        })
    # Dedup by name_lc — highest weight wins
    best = {}
    for r in rows:
        k = r['name_lc']
        if k not in best or r['weight'] > best[k]['weight']:
            best[k] = r
    rows = list(best.values())
    # stabile Sortierung: Gewicht, dann kürzerer Name (weniger Müll-Phrasen oben)
    rows.sort(key=lambda x: (-x['weight'], len(x['name']), x['name_lc']))
    # Fallback: wenn Kategorien leer/falsch gepflegt → Name-Hygiene allein
    if require_category and not rows:
        return skill_stats_from_pipeline(consultant, require_category=False)
    return rows


# CRM-Freitext-Felder für Wild-Gewichtung (SuiteCRM contacts_cstm + contacts.description)
PROFILE_TEXT_FIELDS = (
    'ogo_description_c',
    'gulp_profil_c',
    'freelancermap_profil_c',
    'xing_profile_c',
)


def collect_wild_profile_text(cstm, contact=None) -> Tuple[str, List[str]]:
    """
    Sammelt *_profil / ogo Freitext (+ optional contacts.description).
    Rückgabe: (combined_text, used_field_names).
    Kurze URL-only Werte (< 80 Zeichen und http…) werden übersprungen.
    """
    parts: List[Tuple[str, str]] = []
    used: List[str] = []

    def _usable(raw: str) -> bool:
        t = (raw or '').strip()
        if len(t) < 80:
            return False
        # reine Profil-URL ohne Body
        if t.lower().startswith('http') and len(t) < 200 and '\n' not in t and ' ' not in t.strip():
            return False
        return True

    if cstm is not None:
        for field in PROFILE_TEXT_FIELDS:
            raw = getattr(cstm, field, None) or ''
            if _usable(raw):
                parts.append((field, raw.strip()))
                used.append(field)
    if contact is not None:
        desc = getattr(contact, 'description', None) or ''
        if _usable(desc):
            parts.append(('description', desc.strip()))
            used.append('description')

    if not parts:
        return '', []
    text = '\n\n'.join(f'--- {name} ---\n{body}' for name, body in parts)
    return text, used


def resolve_consultant_for_contact(
    *,
    crm_id: str,
    cstm=None,
    contact=None,
    Consultant=None,
    RadarConsultantItem=None,
    join_index: Optional[Dict] = None,
):
    """
    Join Contact → Consultant (CV-Pipeline), beste verfügbare Brücke zuerst.

    Returns: (consultant_or_None, join_via:str)
      join_via:
        radar_fk          — RadarConsultantItem.consultant für crm_contact_id
        radar_gulp        — Radar-Zeile mit gleichem gulp_id + consultant FK
        gulp_id_dir/aid   — direkter Match auf consultant_dir / aid (selten)
        email             — E-Mail exakt
        name              — eindeutiger Vor+Nachname (nur wenn 1 Person)
        ''                — kein Join
    """
    from django.apps import apps
    from django.db.models import Q

    if Consultant is None:
        try:
            Consultant = apps.get_model('cv_extractor', 'Consultant')
        except LookupError:
            return None, ''
    if RadarConsultantItem is None:
        try:
            RadarConsultantItem = apps.get_model('abpe_shaduler', 'RadarConsultantItem')
        except LookupError:
            RadarConsultantItem = None

    crm_id = str(crm_id or '').strip()
    pool = Consultant.objects.filter(
        status__in=['completed', 'validated', 'profile_ready'],
    ).exclude(aid__endswith='-en')

    gulp_id = ''
    if cstm is not None:
        gulp_id = str(getattr(cstm, 'gulp_id_c', None) or '').strip()

    # ── Schnellpfad über vorbereiteten Index (Bulk-Probe) ──────────────
    if join_index:
        if crm_id and crm_id in join_index.get('by_crm', {}):
            c = join_index['by_crm'][crm_id]
            return c, 'radar_fk'
        if gulp_id and gulp_id in join_index.get('by_gulp', {}):
            c = join_index['by_gulp'][gulp_id]
            return c, 'radar_gulp'

    # 1) Radar: crm_contact_id → consultant FK
    if RadarConsultantItem is not None and crm_id:
        radar = (
            RadarConsultantItem.objects.filter(
                crm_contact_id=crm_id,
                deleted_at__isnull=True,
                consultant_id__isnull=False,
            )
            .select_related('consultant')
            .order_by('-updated_at')
            .first()
        )
        if radar and radar.consultant_id:
            c = radar.consultant
            if c and not str(getattr(c, 'aid', '') or '').endswith('-en'):
                if c.status in ('completed', 'validated', 'profile_ready'):
                    return c, 'radar_fk'

    # 2) Radar: gulp_id → consultant FK (CRM gulp_id_c = Radar.gulp_id)
    if RadarConsultantItem is not None and gulp_id and len(gulp_id) >= 3:
        radar = (
            RadarConsultantItem.objects.filter(
                gulp_id=gulp_id,
                deleted_at__isnull=True,
                consultant_id__isnull=False,
            )
            .select_related('consultant')
            .order_by('-updated_at')
            .first()
        )
        if radar and radar.consultant_id:
            c = radar.consultant
            if (
                c
                and not str(getattr(c, 'aid', '') or '').endswith('-en')
                and c.status in ('completed', 'validated', 'profile_ready')
            ):
                return c, 'radar_gulp'

    # 3) Direkter gulp_id ↔ consultant_dir / aid (selten, aber hart)
    if gulp_id and len(gulp_id) >= 3:
        hit = pool.filter(consultant_dir=gulp_id).order_by('-created_at').first()
        if hit:
            return hit, 'gulp_id_dir'
        hit = pool.filter(aid=gulp_id).order_by('-created_at').first()
        if hit:
            return hit, 'gulp_id_aid'
        # nur ganze Token-Grenze, kein kurzer Zufallstreffer
        if len(gulp_id) >= 5:
            hit = (
                pool.filter(
                    Q(consultant_dir__endswith=gulp_id)
                    | Q(consultant_dir__endswith=f'_{gulp_id}')
                    | Q(consultant_dir__endswith=f'-{gulp_id}')
                )
                .order_by('-created_at')
                .first()
            )
            if hit:
                return hit, 'gulp_id_dir_suffix'

    # 4) E-Mail
    email = ''
    if contact is not None:
        for attr in ('email_address', 'email1', 'email_c', 'email'):
            email = (getattr(contact, attr, None) or '').strip()
            if email:
                break
        # SuiteCRM oft über related emails — optional primary_address_mail?
    if email and '@' in email:
        hit = pool.filter(email__iexact=email).order_by('-created_at').first()
        if hit:
            return hit, 'email'

    # 5) Name — nur wenn eindeutig eine Person (1 consultant_dir)
    first = (getattr(contact, 'first_name', None) or '').strip() if contact else ''
    last = (getattr(contact, 'last_name', None) or '').strip() if contact else ''
    if first and last and len(last) >= 2:
        name_qs = pool.filter(first_name__iexact=first, last_name__iexact=last)
        dirs = list(
            name_qs.values_list('consultant_dir', flat=True).distinct()[:5]
        )
        # leere dirs zählen als eigene Keys
        norm_dirs = {(d or '').lower().strip() for d in dirs}
        if len(norm_dirs) == 1:
            hit = name_qs.order_by('-created_at').first()
            if hit:
                return hit, 'name'
        # mehrere Homonyme → kein Name-Join (zu riskant)

    return None, ''


def build_join_index(Consultant=None, RadarConsultantItem=None) -> Dict:
    """
    Vorberechnete Maps für Bulk-Probe:
      by_crm[crm_contact_id] → Consultant
      by_gulp[gulp_id] → Consultant
    Nur Radar-Zeilen mit gesetztem consultant FK.
    """
    from django.apps import apps

    if Consultant is None:
        Consultant = apps.get_model('cv_extractor', 'Consultant')
    if RadarConsultantItem is None:
        try:
            RadarConsultantItem = apps.get_model('abpe_shaduler', 'RadarConsultantItem')
        except LookupError:
            return {'by_crm': {}, 'by_gulp': {}, 'stats': {'radar_with_consultant': 0}}

    by_crm: Dict = {}
    by_gulp: Dict = {}
    n = 0
    qs = (
        RadarConsultantItem.objects.filter(
            deleted_at__isnull=True,
            consultant_id__isnull=False,
        )
        .select_related('consultant')
        .order_by('-updated_at')
    )
    for r in qs.iterator(chunk_size=500):
        c = r.consultant
        if c is None:
            continue
        if str(getattr(c, 'aid', '') or '').endswith('-en'):
            continue
        if getattr(c, 'status', '') not in ('completed', 'validated', 'profile_ready'):
            continue
        n += 1
        cid = str(r.crm_contact_id or '').strip()
        if cid and cid not in by_crm:
            by_crm[cid] = c
        gid = str(r.gulp_id or '').strip()
        if gid and gid not in by_gulp:
            by_gulp[gid] = c
    return {
        'by_crm': by_crm,
        'by_gulp': by_gulp,
        'stats': {
            'radar_with_consultant': n,
            'unique_crm': len(by_crm),
            'unique_gulp': len(by_gulp),
        },
    }


def weight_for_contact(
    *,
    crm_id: str,
    cstm=None,
    contact=None,
    skills_watch: Optional[List[str]] = None,
    join_index: Optional[Dict] = None,
) -> Dict:
    """
    Prüfschleife pro Contact-ID:
      1) CV-Pipeline-Gewichtung (ConsultantSkill.weight) wenn Join gelingt
      2) sonst Wild-Gewichtung aus ogo / *_profil.c / description

    Rückgabe dict mit weight_source, skill_stats, join_via, profil_fields, …
    """
    skills_watch = skills_watch or []
    consultant, join_via = resolve_consultant_for_contact(
        crm_id=crm_id, cstm=cstm, contact=contact, join_index=join_index,
    )
    first = (getattr(contact, 'first_name', None) or '') if contact else ''
    last = (getattr(contact, 'last_name', None) or '') if contact else ''
    full = f'{first} {last}'.strip()
    gulp_id = str(getattr(cstm, 'gulp_id_c', None) or '') if cstm else ''

    result: Dict = {
        'crm_contact_id': str(crm_id),
        'gulp_id': gulp_id,
        'full_name': full,
        'first_name': first,
        'last_name': last,
        'weight_source': 'none',
        'join_via': join_via or '',
        'aid': '',
        'consultant_dir': '',
        'profil_fields': [],
        'body_text': '',
        'skill_stats': [],
    }

    if consultant is not None:
        stats = skill_stats_from_pipeline(consultant)
        if stats:
            body_parts = [
                getattr(consultant, 'headline', None) or '',
                full,
                getattr(consultant, 'location', None) or '',
                ' '.join(s['name'] for s in stats[:80]),
            ]
            result.update({
                'weight_source': 'pipeline_cv',
                'aid': getattr(consultant, 'aid', None) or '',
                'consultant_dir': getattr(consultant, 'consultant_dir', None) or '',
                'body_text': ' '.join(p for p in body_parts if p),
                'skill_stats': stats[:80],
            })
            return result

    text, used = collect_wild_profile_text(cstm, contact)
    if text:
        stats = skill_stats_from_wild_text(text, skills_watch)
        result.update({
            'weight_source': 'wild_profil',
            'profil_fields': used,
            'body_text': text,
            'skill_stats': stats,
        })
        return result

    return result


def build_matching_doc(
    *,
    doc_id: str,
    source: str,
    full_name: str = '',
    first_name: str = '',
    last_name: str = '',
    body_text: str = '',
    skill_stats: Optional[List[Dict]] = None,
    extra: Optional[Dict] = None,
) -> Dict:
    skill_stats = skill_stats or []
    # KEINE dynamic object keys (asp vs asp.net / .net) — nur nested + keyword list
    names = []
    seen = set()
    for s in skill_stats:
        lc = (s.get('name_lc') or '').strip()
        if not lc or lc in seen:
            continue
        seen.add(lc)
        names.append(lc)
    # flache Gewichtsliste parallel zu skill_stats (suchbar/sortierbar ohne object-keys)
    weight_pairs = [
        {'skill': s['name_lc'], 'weight': s['weight']}
        for s in skill_stats
        if s.get('name_lc') is not None and s.get('weight') is not None
    ]
    doc = {
        'doc_id': doc_id,
        'source': source,  # pipeline | ogo_wild | namazu
        'full_name': full_name,
        'first_name': first_name,
        'last_name': last_name,
        'body_text': (body_text or '')[:80000],
        'skill_names': names,
        'skill_weight_pairs': weight_pairs,
        'skill_stats': skill_stats,
        'indexed_at': datetime.utcnow().isoformat() + 'Z',
        'probe': True,
    }
    if extra:
        doc.update(extra)
    return doc
