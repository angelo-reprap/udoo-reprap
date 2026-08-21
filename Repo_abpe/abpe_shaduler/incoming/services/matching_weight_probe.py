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
        for period, seg in segments:
            hits = pat.findall(seg)
            if not hits:
                continue
            n = len(hits)
            freq += n
            project_count += 1
            months = get_months(period) if period else 6
            total_months += months
            hit_periods.append({'period': period or None, 'hits': n, 'months': months})

        if freq == 0:
            continue
        project_count = max(1, project_count)
        total_months = max(6, total_months)
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


def skill_stats_from_pipeline(consultant) -> List[Dict]:
    """Liest ConsultantSkill.weight (+ Name) — schon vom Enricher berechnet."""
    rows = []
    try:
        qs = consultant.skills.select_related('skill').all()
    except Exception:
        return rows
    for cs in qs:
        name = getattr(getattr(cs, 'skill', None), 'name', None) or ''
        if not name:
            continue
        w = float(getattr(cs, 'weight', 0.5) or 0.5)
        rows.append({
            'name': name,
            'name_lc': name.lower(),
            'freq': None,
            'projects': None,
            'months': None,
            'years': None,
            'weight': round(w, 2),
            'segments': [],
            'from_db': True,
        })
    rows.sort(key=lambda x: (-x['weight'], x['name_lc']))
    return rows


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
    weights = {s['name_lc']: s['weight'] for s in skill_stats if s.get('name_lc')}
    names = [s['name_lc'] for s in skill_stats]
    doc = {
        'doc_id': doc_id,
        'source': source,  # pipeline | ogo_wild | namazu
        'full_name': full_name,
        'first_name': first_name,
        'last_name': last_name,
        'body_text': (body_text or '')[:80000],
        'skill_names': names,
        'skill_weights': weights,
        'skill_stats': skill_stats,
        'indexed_at': datetime.utcnow().isoformat() + 'Z',
        'probe': True,
    }
    if extra:
        doc.update(extra)
    return doc
