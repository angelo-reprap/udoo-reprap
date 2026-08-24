"""
matching_external_recall.py — Gulp + FLM Keyword-Recall für Matching.

- Sucht mit Anfrage-Skills
- Join gegen CRM/Consultant (matching_source_join)
- Bekannt + kontaktierbar → Shortlist-Kandidaten (mit Consultant)
- Sonst → Backoffice-Liste (kein Auto-CV-Update, keine Duplikate)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

DEFAULT_MIN_OVERLAP = 1
DEFAULT_GULP_PAGES = 2
DEFAULT_FLM_PAGES = 2


def _skill_names(project) -> List[str]:
    names: List[str] = []
    for s in (getattr(project, 'required_skills', None) or []):
        if isinstance(s, dict) and s.get('name'):
            names.append(str(s['name']).strip())
        elif isinstance(s, str) and s.strip():
            names.append(s.strip())
    for t in (getattr(project, 'extracted_technologies', None) or []):
        t = str(t).strip()
        if t and t not in names:
            names.append(t)
    # stabil dedupe
    return list(dict.fromkeys(names))


def _overlap(skills_req: List[str], hit: Dict[str, Any]) -> Tuple[int, List[str]]:
    req = [s.lower() for s in skills_req]
    hs = [str(x).lower() for x in (hit.get('skills') or [])]
    blob = ' '.join([
        str(hit.get('name') or ''),
        str(hit.get('beschreibung') or hit.get('description') or '')[:400],
        ' '.join(str(x) for x in (hit.get('skills') or [])[:40]),
        str(hit.get('fm_slug') or ''),
    ]).lower()
    matched = []
    for s in req:
        if any(s in x or x in s for x in hs) or s in blob:
            matched.append(s)
    return len(matched), matched


def _search_term(skills: List[str]) -> str:
    return ' '.join(skills[:6]) if skills else ''


def _hit_display_name(hit: Dict[str, Any], join_display: str = '') -> str:
    """Lesbarer Name: CRM/Join > echter Name > Titel > Skills > Platzhalter."""
    from .matching_source_join import clean_display_name, is_placeholder_name

    for cand in (
        join_display,
        hit.get('name'),
        ' '.join(
            x for x in [hit.get('first_name') or '', hit.get('last_name') or ''] if x
        ).strip(),
    ):
        cleaned = clean_display_name(str(cand or ''))
        if cleaned:
            return cleaned
    title = str(hit.get('title') or hit.get('headline') or '').strip()
    if title and not is_placeholder_name(title) and len(title) < 80:
        return title
    skills = [str(s).strip() for s in (hit.get('skills') or [])[:3] if str(s).strip()]
    gid = hit.get('gulp_id') or hit.get('fm_id') or ''
    src = 'Gulp' if hit.get('gulp_id') else ('FLM' if hit.get('fm_id') else 'Extern')
    if skills:
        return f"{src} {gid} · {', '.join(skills)}" if gid else ', '.join(skills)
    if gid:
        return f'{src} {gid}'
    return 'Unbekannt'


def fetch_gulp_hits(skills: List[str], *, pages: int = DEFAULT_GULP_PAGES) -> List[Dict]:
    try:
        from apps.abpe_shaduler.services import radar_berater_gulp as gulp
    except Exception as exc:
        logger.warning('gulp import: %s', exc)
        return []
    if not gulp.has_gulp_session():
        logger.info('Gulp-Recall skip: keine Session')
        return []
    term = _search_term(skills)
    if not term:
        return []
    out: List[Dict] = []
    seen: Set[str] = set()
    for page in range(max(1, pages)):
        try:
            res = gulp.fetch_experts_list(
                page=page, size=20, available_only=True, search_term=term,
            )
        except TypeError:
            # Live ohne search_term-Kwarg
            res = gulp.fetch_experts_list(page=page, size=20, available_only=True)
        if not res.get('ok'):
            logger.warning('Gulp search fail: %s', res.get('error'))
            break
        for h in res.get('results') or []:
            key = str(h.get('gulp_id') or h.get('mongo_id') or '')
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(h)
    return out


def fetch_flm_hits(skills: List[str], *, pages: int = DEFAULT_FLM_PAGES) -> List[Dict]:
    try:
        from apps.abpe_shaduler.services import radar_berater_fl as fl
    except Exception as exc:
        logger.warning('flm import: %s', exc)
        return []
    term = _search_term(skills)
    if not term:
        return []
    out: List[Dict] = []
    seen: Set[str] = set()
    for page in range(1, max(1, pages) + 1):
        try:
            res = fl.fetch_freelancers_list(
                page=page, available_only=True, query=term,
            )
        except TypeError:
            res = fl.fetch_freelancers_list(page=page, available_only=True)
        if not res.get('ok'):
            logger.warning('FLM search fail: %s', res.get('error'))
            break
        for h in res.get('results') or []:
            key = str(h.get('fm_id') or h.get('fm_slug') or '')
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(h)
    return out


def classify_external_hits(
    project,
    *,
    existing_consultant_ids: Optional[Set[int]] = None,
    min_overlap: int = DEFAULT_MIN_OVERLAP,
    gulp_pages: int = DEFAULT_GULP_PAGES,
    flm_pages: int = DEFAULT_FLM_PAGES,
) -> Dict[str, Any]:
    """
    Returns:
      known_results: list[dict] bereit für Scoring-Merge (mit consultant_cv)
      backoffice: list[dict] für manuelle Bearbeitung
      stats: counts
    """
    from . import matching_source_join as msj

    skills = _skill_names(project)
    existing = set(existing_consultant_ids or [])
    known_results: List[Dict[str, Any]] = []
    backoffice: List[Dict[str, Any]] = []
    seen_consultants: Set[int] = set()
    stats = {
        'skills': skills,
        'gulp_raw': 0,
        'flm_raw': 0,
        'gulp_known': 0,
        'flm_known': 0,
        'backoffice': 0,
        'skipped_dup_db': 0,
        'skipped_low_overlap': 0,
    }

    def _handle(source: str, hit: Dict[str, Any], join):
        ov_n, ov_skills = _overlap(skills, hit)
        if ov_n < min_overlap:
            stats['skipped_low_overlap'] += 1
            return
        jd = join.as_dict()
        display = _hit_display_name(hit, jd.get('display_name') or '')
        base = {
            'match_source': source,
            'match_sources': [source],
            'external_overlap': ov_n,
            'external_overlap_skills': ov_skills,
            'external_hit': {
                'name': display,
                'raw_name': hit.get('name'),
                'title': hit.get('title') or hit.get('headline') or '',
                'gulp_id': hit.get('gulp_id'),
                'mongo_id': hit.get('mongo_id'),
                'fm_id': hit.get('fm_id'),
                'fm_slug': hit.get('fm_slug'),
                'profil_url': hit.get('profil_url') or hit.get('url'),
                'skills': (hit.get('skills') or [])[:20],
                'ort': hit.get('ort') or hit.get('location') or '',
                'satz': hit.get('satz'),
            },
            'crm_link': jd,
            'crm_link_status': jd.get('crm_link_status'),
            'email': jd.get('email') or '',
            'phone': jd.get('phone') or '',
            'profile_refresh_suggested': jd.get('profile_refresh_suggested'),
            'display_name': display,
        }
        cons = join.consultant
        if join.known and cons is not None and jd.get('can_contact'):
            cid = getattr(cons, 'id', None)
            # Duplikate NICHT verwerfen — Engine reichert Quelle an.
            # Hier nur Doppelungen innerhalb Gulp+FLM derselben Person vermeiden.
            if cid in seen_consultants:
                stats['skipped_dup_db'] += 1
                return
            if cid:
                seen_consultants.add(cid)
            # Flag ob schon in ORM-Stage1
            base['already_in_db'] = bool(cid in existing)
            cov = ov_n / max(len(skills), 1)
            known_results.append({
                **base,
                'consultant_cv': cons,
                'overall_score': round(0.35 + 0.55 * cov, 4),
                'skill_score': round(cov, 4),
                'matched_skills': list(ov_skills),
                'missing_skills': [s for s in skills if s.lower() not in ov_skills],
            })
            stats[f'{source}_known'] = stats.get(f'{source}_known', 0) + 1
            if cid in existing:
                stats['skipped_dup_db'] += 1  # informativ: war schon DB
            return

        # Backoffice: unbekannt ODER bekannt ohne Kontakt ODER CRM ohne Consultant-CV
        if join.known and cons is None and jd.get('can_contact'):
            reason = 'known_crm'  # CRM+Kontakt, aber kein CV → manuell
        elif join.known and cons is None:
            reason = 'no_consultant'
        elif join.known and not jd.get('can_contact'):
            reason = 'no_contact'
        else:
            reason = 'unknown'
        backoffice.append({
            **base,
            'reason': reason,
            'join_notes': jd.get('notes') or [],
            'display_name': display,
        })
        stats['backoffice'] += 1
        if join.known:
            stats['backoffice_known'] = stats.get('backoffice_known', 0) + 1

    gulp_hits = fetch_gulp_hits(skills, pages=gulp_pages)
    stats['gulp_raw'] = len(gulp_hits)
    for h in gulp_hits:
        try:
            join = msj.resolve_gulp_hit(h)
        except Exception as exc:
            logger.warning('gulp join: %s', exc)
            join = msj.JoinHit(notes=[str(exc)])
        _handle('gulp', h, join)

    flm_hits = fetch_flm_hits(skills, pages=flm_pages)
    stats['flm_raw'] = len(flm_hits)
    for h in flm_hits:
        try:
            join = msj.resolve_flm_hit(h)
        except Exception as exc:
            logger.warning('flm join: %s', exc)
            join = msj.JoinHit(notes=[str(exc)])
        _handle('flm', h, join)

    # Bekannte CRM-Treffer zuerst, dann nach Overlap
    _prio = {'known_crm': 0, 'no_contact': 1, 'no_consultant': 2, 'unknown': 3}
    backoffice.sort(
        key=lambda b: (
            _prio.get(b.get('reason') or '', 9),
            -(b.get('external_overlap') or 0),
            str(b.get('display_name') or ''),
        )
    )

    return {
        'known_results': known_results,
        'backoffice': backoffice,
        'stats': stats,
        'generated_at': datetime.now(timezone.utc).isoformat(),
    }


def store_backoffice_on_project(project, backoffice: List[Dict], stats: Dict) -> None:
    """
    Speichert Backoffice-Liste am Projekt (extracted_requirements._matching_backoffice).
    Kein Schema-Migration. Andere Keys bleiben erhalten.
    """
    raw = getattr(project, 'extracted_requirements', None)
    meta = dict(raw) if isinstance(raw, dict) else {}
    # Kompakte Serialisierung (kein consultant Objekt)
    slim = []
    for b in backoffice[:100]:
        slim.append({
            'match_source': b.get('match_source'),
            'crm_link_status': b.get('crm_link_status'),
            'reason': b.get('reason'),
            'display_name': b.get('display_name'),
            'email': b.get('email'),
            'phone': b.get('phone'),
            'external_overlap': b.get('external_overlap'),
            'external_overlap_skills': b.get('external_overlap_skills'),
            'external_hit': b.get('external_hit'),
            'join_notes': b.get('join_notes'),
            'profile_refresh_suggested': b.get('profile_refresh_suggested'),
        })
    meta['_matching_backoffice'] = slim
    meta['_matching_external_stats'] = {
        k: v for k, v in (stats or {}).items() if k != 'skills'
    }
    meta['_matching_external_at'] = datetime.now(timezone.utc).isoformat()
    project.extracted_requirements = meta
    try:
        project.save(update_fields=['extracted_requirements'])
    except Exception as exc:
        logger.warning('store_backoffice: %s', exc)
