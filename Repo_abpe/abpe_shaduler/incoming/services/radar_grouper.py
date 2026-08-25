"""
Radar-Dedup / Clustering (günstig, ohne LLM).

Gleiche Ausschreibung über Börsen (FM + Gulp …) → RadarItemGroup.
Merkmale: normalisierter Titel + Skills-Overlap (+ Stadt soft).

Architektur: RadarItem.gruppe → RadarItemGroup (merkmal_hash, titel_norm, anbieter_anzahl).
DeepSeek/Embeddings später optional — V1 = difflib + Jaccard.
"""
from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Iterable, Optional

log = logging.getLogger('abpe_shaduler.radar_grouper')

# Schwellwerte (bewusst konservativ — lieber zwei Zeilen als Falsch-Merge)
TITLE_MIN = 0.82
TITLE_STRONG = 0.92
SKILL_JACCARD_MIN = 0.30
SKILL_INTERSECT_MIN = 2

_GENDER = re.compile(
    r'\(?\s*m\s*/\s*w\s*/\s*[dDxX*+]?\s*\)?|\(m/w/divers\)|\(all genders\)|'
    r'\b[mwWdD]\s*/\s*[mwWdD]\s*/\s*[dDxX*+]\b',
    re.I,
)
_NOISE = re.compile(
    r'\b(gesucht|gesucht!|dringend|asap|sofort|ab sofort|'
    r'freelance(?:r)?|freelancer|m\s*w\s*d)\b',
    re.I,
)
_NON_ALNUM = re.compile(r'[^\w\s]', re.UNICODE)
_WS = re.compile(r'\s+')
_CITY_PREFIX = re.compile(r'^(raum|region|gebiet|nähe|nahe|area)\s+', re.I)


def ping() -> bool:
    return True


def normalize_title(title: str) -> str:
    s = unicodedata.normalize('NFKC', (title or '').strip()).lower()
    if not s:
        return ''
    s = _GENDER.sub(' ', s)
    s = s.replace('–', ' ').replace('—', ' ').replace('-', ' ')
    s = _NON_ALNUM.sub(' ', s)
    s = _NOISE.sub(' ', s)
    s = _WS.sub(' ', s).strip()
    return s[:250]


def normalize_city(city: str) -> str:
    s = unicodedata.normalize('NFKC', (city or '').strip()).lower()
    if not s:
        return ''
    s = _CITY_PREFIX.sub('', s)
    s = _NON_ALNUM.sub(' ', s)
    s = _WS.sub(' ', s).strip()
    # nur erster Ortsteil
    if '/' in s:
        s = s.split('/')[0].strip()
    if ',' in s:
        s = s.split(',')[0].strip()
    return s[:80]


def normalize_skills(skills: Iterable[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in skills or []:
        s = unicodedata.normalize('NFKC', str(raw or '').strip()).lower()
        s = _NON_ALNUM.sub(' ', s)
        s = _WS.sub(' ', s).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    out.sort()
    return out


def merkmal_hash(titel_norm: str, skills: list[str], city_norm: str = '') -> str:
    """Exakter Cluster-Key (schneller Pfad)."""
    sk = '|'.join(skills[:10])
    raw = f'{titel_norm}#{sk}#{city_norm}'
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _skill_score(a: list[str], b: list[str]) -> tuple[float, int]:
    if not a or not b:
        return 0.0, 0
    sa, sb = set(a), set(b)
    inter = len(sa & sb)
    union = len(sa | sb) or 1
    return inter / union, inter


def _city_ok(a: str, b: str) -> bool:
    if not a or not b:
        return True
    if a == b:
        return True
    return a in b or b in a


def similarity(
    *,
    titel_a: str,
    titel_b: str,
    skills_a: list[str],
    skills_b: list[str],
    city_a: str = '',
    city_b: str = '',
) -> float:
    """0..1 Similarity; 0 = kein Match."""
    ta = titel_a or ''
    tb = titel_b or ''
    if not ta or not tb:
        return 0.0
    if ta == tb:
        title_r = 1.0
    else:
        title_r = SequenceMatcher(None, ta, tb).ratio()
    if title_r < TITLE_MIN:
        return 0.0

    jacc, inter = _skill_score(skills_a, skills_b)
    if skills_a and skills_b:
        if jacc < SKILL_JACCARD_MIN and inter < SKILL_INTERSECT_MIN and title_r < TITLE_STRONG:
            return 0.0
    elif title_r < TITLE_STRONG:
        # ohne Skills nur bei fast identischem Titel
        return 0.0

    if not _city_ok(city_a, city_b) and title_r < 0.94:
        return 0.0

    # gewichteter Score
    if skills_a and skills_b:
        score = title_r * 0.72 + jacc * 0.28
    else:
        score = title_r
    return score if score >= 0.80 else 0.0


def features_from_item(obj) -> dict[str, Any]:
    eck = getattr(obj, 'eckdaten', None) or {}
    titel = normalize_title(getattr(obj, 'headline', '') or '')
    skills = normalize_skills(getattr(obj, 'skills', None) or [])
    city = normalize_city(eck.get('city') or '')
    return {
        'titel_norm': titel,
        'skills': skills,
        'city_norm': city,
        'merkmal_hash': merkmal_hash(titel, skills, city),
        'company_norm': '',  # absichtlich nicht im Key — Agenturen differieren
    }


def _union_find_parent(parent: dict, x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def _union(parent: dict, a, b):
    ra, rb = _union_find_parent(parent, a), _union_find_parent(parent, b)
    if ra != rb:
        parent[rb] = ra


def regroup_queryset(objs: list, *, min_score: float = 0.80) -> dict:
    """
    Cluster Liste von RadarItem → setzt gruppe FK, aktualisiert anbieter_anzahl.
    Returns {groups, linked, scanned}.
    """
    from apps.abpe_shaduler.models import RadarItemGroup

    objs = [o for o in (objs or []) if o is not None]
    if not objs:
        return {'ok': True, 'groups': 0, 'linked': 0, 'scanned': 0}

    feats = {str(o.pk): features_from_item(o) for o in objs}
    ids = [str(o.pk) for o in objs]
    parent = {i: i for i in ids}

    # 1) Exact hash buckets
    by_hash: dict[str, list[str]] = {}
    for i in ids:
        h = feats[i]['merkmal_hash']
        if feats[i]['titel_norm']:
            by_hash.setdefault(h, []).append(i)
    for bucket in by_hash.values():
        for j in range(1, len(bucket)):
            _union(parent, bucket[0], bucket[j])

    # 2) Fuzzy zwischen Repräsentanten unterschiedlicher Hashes
    #    (nur wenn Titel-Prefix grob ähnlich — O(n²) ok bis ~500)
    reps = []
    for i in ids:
        f = feats[i]
        if not f['titel_norm']:
            continue
        reps.append(i)
    n = len(reps)
    for a_idx in range(n):
        ia = reps[a_idx]
        fa = feats[ia]
        for b_idx in range(a_idx + 1, n):
            ib = reps[b_idx]
            if _union_find_parent(parent, ia) == _union_find_parent(parent, ib):
                continue
            fb = feats[ib]
            # schnelle Ablehnung
            if fa['titel_norm'][0] != fb['titel_norm'][0] and len(fa['titel_norm']) > 4:
                # erster Buchstabe oft gleich bei gleichem Thema — soft skip only if very different length
                if abs(len(fa['titel_norm']) - len(fb['titel_norm'])) > 25:
                    continue
            sc = similarity(
                titel_a=fa['titel_norm'],
                titel_b=fb['titel_norm'],
                skills_a=fa['skills'],
                skills_b=fb['skills'],
                city_a=fa['city_norm'],
                city_b=fb['city_norm'],
            )
            if sc >= min_score:
                _union(parent, ia, ib)

    # Cluster → Group rows
    clusters: dict[str, list] = {}
    obj_by_id = {str(o.pk): o for o in objs}
    for i in ids:
        root = _union_find_parent(parent, i)
        clusters.setdefault(root, []).append(obj_by_id[i])

    groups_n = 0
    linked = 0
    for members in clusters.values():
        if not members:
            continue
        # Repräsentant: längste Beschreibung / neueste
        members.sort(
            key=lambda o: (
                len(o.beschreibung or ''),
                o.eingegangen_am.timestamp() if getattr(o, 'eingegangen_am', None) else 0,
            ),
            reverse=True,
        )
        primary = members[0]
        f0 = feats[str(primary.pk)]
        titel_norm = f0['titel_norm'] or normalize_title(primary.headline) or primary.headline[:250]
        mhash = f0['merkmal_hash']

        # bestehende Gruppe wiederverwenden wenn eines schon verknüpft
        grp = None
        for m in members:
            if m.gruppe_id:
                grp = m.gruppe
                break
        if grp is None:
            # Hash-Match auf existierende Gruppe
            grp = RadarItemGroup.objects.filter(merkmal_hash=mhash).first()
        if grp is None:
            grp = RadarItemGroup.objects.create(
                merkmal_hash=mhash,
                titel_norm=titel_norm[:250],
                anbieter_anzahl=len(members),
            )
            groups_n += 1
        else:
            grp.merkmal_hash = mhash
            grp.titel_norm = titel_norm[:250]
            grp.anbieter_anzahl = len(members)
            grp.save(update_fields=['merkmal_hash', 'titel_norm', 'anbieter_anzahl'])

        for m in members:
            if m.gruppe_id != grp.pk:
                m.gruppe = grp
                m.save(update_fields=['gruppe', 'updated_at'] if hasattr(m, 'updated_at') else ['gruppe'])
                linked += 1
            elif m.gruppe_id == grp.pk:
                pass

    return {
        'ok': True,
        'groups': groups_n,
        'linked': linked,
        'scanned': len(objs),
        'clusters': len(clusters),
    }


def regroup_recent(*, status: str = 'neu', days: int = 14, limit: int = 800) -> dict:
    """Neu-Items der letzten Tage neu clustern."""
    from datetime import timedelta
    from django.utils import timezone
    from apps.abpe_shaduler.models import RadarItem, RadarSource
    from .radar_fetcher import ANFRAGEN_SOURCES

    src_ids = list(
        RadarSource.objects.filter(name__in=ANFRAGEN_SOURCES).values_list('pk', flat=True)
    )
    qs = RadarItem.objects.select_related('quelle', 'gruppe').all()
    if src_ids:
        qs = qs.filter(quelle_id__in=src_ids)
    if status:
        qs = qs.filter(status=status)
    if days and days > 0:
        since = timezone.now() - timedelta(days=max(1, min(365, int(days))))
        qs = qs.filter(eingegangen_am__gte=since)
    qs = qs.order_by('-eingegangen_am')[: max(1, min(5000, int(limit)))]
    rows = list(qs)
    return regroup_queryset(rows)


def regroup_touched(objs: list) -> dict:
    """
    Nach Persist: Touched + Kandidaten mit ähnlichem Titel-Prefix aus DB laden,
    dann clustern (damit Cross-Source-Treffer gefunden werden).
    """
    from datetime import timedelta
    from django.db.models import Q
    from django.utils import timezone
    from apps.abpe_shaduler.models import RadarItem

    objs = list(objs or [])
    if not objs:
        return {'ok': True, 'groups': 0, 'linked': 0, 'scanned': 0}

    prefixes = set()
    for o in objs:
        t = normalize_title(o.headline or '')
        if len(t) >= 4:
            prefixes.add(t[:12])

    since = timezone.now() - timedelta(days=14)
    q = Q(pk__in=[o.pk for o in objs])
    for p in list(prefixes)[:40]:
        q |= Q(headline__icontains=p[:8])
    candidates = list(
        RadarItem.objects.filter(status=RadarItem.Status.NEU, eingegangen_am__gte=since)
        .filter(q)
        .select_related('quelle', 'gruppe')[:500]
    )
    # Touched immer dabei
    by_id = {str(c.pk): c for c in candidates}
    for o in objs:
        by_id[str(o.pk)] = o
    return regroup_queryset(list(by_id.values()))


def split_group(group_id) -> dict:
    """Gruppe auflösen — jedes Item wird eigenständig."""
    from apps.abpe_shaduler.models import RadarItem, RadarItemGroup
    import uuid as _uuid

    try:
        gid = _uuid.UUID(str(group_id))
    except Exception:
        return {'ok': False, 'error': 'ungültige gruppen-id'}
    grp = RadarItemGroup.objects.filter(pk=gid).first()
    if not grp:
        return {'ok': False, 'error': 'gruppe nicht gefunden'}
    n = RadarItem.objects.filter(gruppe=grp).update(gruppe=None)
    grp.delete()
    return {'ok': True, 'ungrouped': n}


def merge_items(item_ids: list[str], *, group_id: Optional[str] = None) -> dict:
    """Items manuell in eine Gruppe legen."""
    from apps.abpe_shaduler.models import RadarItem, RadarItemGroup
    import uuid as _uuid

    uuids = []
    for i in item_ids or []:
        try:
            uuids.append(_uuid.UUID(str(i)))
        except Exception:
            continue
    if len(uuids) < 2 and not group_id:
        return {'ok': False, 'error': 'mindestens 2 items nötig'}
    objs = list(RadarItem.objects.filter(pk__in=uuids).select_related('gruppe'))
    if not objs:
        return {'ok': False, 'error': 'items nicht gefunden'}

    grp = None
    if group_id:
        try:
            grp = RadarItemGroup.objects.filter(pk=_uuid.UUID(str(group_id))).first()
        except Exception:
            grp = None
    if grp is None:
        for o in objs:
            if o.gruppe_id:
                grp = o.gruppe
                break
    f0 = features_from_item(objs[0])
    if grp is None:
        grp = RadarItemGroup.objects.create(
            merkmal_hash=f0['merkmal_hash'],
            titel_norm=f0['titel_norm'] or objs[0].headline[:250],
            anbieter_anzahl=len(objs),
        )
    for o in objs:
        o.gruppe = grp
        o.save(update_fields=['gruppe'])
    # Zähler inkl. bereits verknüpfter Geschwister
    total = RadarItem.objects.filter(gruppe=grp).count()
    grp.anbieter_anzahl = total
    grp.titel_norm = f0['titel_norm'] or grp.titel_norm
    grp.merkmal_hash = f0['merkmal_hash']
    grp.save(update_fields=['anbieter_anzahl', 'titel_norm', 'merkmal_hash'])
    return {'ok': True, 'gruppe_id': str(grp.pk), 'anbieter_anzahl': total}


def collapse_serialized(
    results: list[dict],
    *,
    source_filter: str = '',
) -> list[dict]:
    """
    Liste serialisierter Items → eine Zeile pro Gruppe.
    sources[] = alle Börsen; grp = Anzahl; group_links = Links zu Geschwistern.
    """
    if not results:
        return []

    from apps.abpe_shaduler.models import RadarItem
    import uuid as _uuid

    # Geschwister nachladen
    gids = []
    for r in results:
        gid = r.get('gruppe_id')
        if gid:
            try:
                gids.append(_uuid.UUID(str(gid)))
            except Exception:
                pass
    siblings: dict[str, list] = {}
    if gids:
        for o in RadarItem.objects.filter(
            gruppe_id__in=gids, status=RadarItem.Status.NEU,
        ).select_related('quelle', 'gruppe'):
            siblings.setdefault(str(o.gruppe_id), []).append(o)

    by_group: dict[str, list[dict]] = {}
    singles: list[dict] = []
    order: list[tuple[str, str]] = []  # ('g', gid) | ('s', index)

    for r in results:
        gid = r.get('gruppe_id') or ''
        if not gid:
            singles.append(r)
            order.append(('s', str(len(singles) - 1)))
            continue
        if gid not in by_group:
            by_group[gid] = []
            order.append(('g', gid))
        by_group[gid].append(r)

    # Serialisierte Geschwister ergänzen (andere Quelle, nicht in ES-Hit)
    from .radar_fetcher import serialize_db_item

    for gid, members in list(by_group.items()):
        have = {m.get('id') for m in members}
        for o in siblings.get(gid) or []:
            sid = str(o.pk)
            if sid not in have:
                members.append(serialize_db_item(o))
                have.add(sid)

    out_list: list[dict] = []
    src_f = (source_filter or '').strip().lower()

    def _primary_for_group(gid: str) -> Optional[dict]:
        members = by_group.get(gid) or []
        if not members:
            return None
        if src_f:
            if not any(
                src_f == ((m.get('sources') or [''])[0] or '').lower()
                for m in members
            ):
                return None
        members = list(members)
        members.sort(
            key=lambda m: len(m.get('beschreibung') or ''),
            reverse=True,
        )
        if src_f:
            preferred = [
                m for m in members
                if src_f == ((m.get('sources') or [''])[0] or '').lower()
            ]
            primary = preferred[0] if preferred else members[0]
        else:
            primary = dict(members[0])

        sources = []
        links = []
        seen_src = set()
        for m in members:
            s = ((m.get('sources') or [''])[0] or '').strip()
            url = m.get('external_url') or ''
            if s and s.lower() not in seen_src:
                seen_src.add(s.lower())
                sources.append(s)
            links.append({
                'id': m.get('id'),
                'source': s,
                'url': url,
                'headline': m.get('headline') or '',
                'company': m.get('company') or '',
            })

        primary = dict(primary)
        primary['sources'] = sources or primary.get('sources') or []
        primary['grp'] = max(1, len(members))
        primary['gruppe_id'] = gid
        primary['group_links'] = links
        primary['anbieter_anzahl'] = len(members)
        return primary

    for kind, key in order:
        if kind == 'g':
            primary = _primary_for_group(key)
            if primary:
                out_list.append(primary)
        else:
            try:
                r = singles[int(key)]
            except Exception:
                continue
            if src_f:
                s0 = ((r.get('sources') or [''])[0] or '').lower()
                if s0 != src_f:
                    continue
            rr = dict(r)
            rr['grp'] = 1
            rr.setdefault('group_links', [{
                'id': rr.get('id'),
                'source': ((rr.get('sources') or [''])[0] or ''),
                'url': rr.get('external_url') or '',
                'headline': rr.get('headline') or '',
                'company': rr.get('company') or '',
            }])
            out_list.append(rr)

    return out_list
