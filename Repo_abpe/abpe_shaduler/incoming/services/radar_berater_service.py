"""
Radar Berater — Persistenz, CRM-Match (gulp_id), Liste, Paste, CRM-Seed.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from django.db.models import Count, Q
from django.utils import timezone

from . import radar_berater_gulp as gulp
from . import radar_berater_index as berater_index

log = logging.getLogger('abpe_shaduler.radar_berater')

SOURCE_NAME = 'gulp'
BERATER_SOURCES = ('gulp',)


def _ensure_source():
    from apps.abpe_shaduler.models import RadarSource
    src, _ = RadarSource.objects.get_or_create(
        name=SOURCE_NAME,
        ziel=RadarSource.Ziel.BERATER,
        defaults={
            'typ': RadarSource.Typ.HTML_PUBLIC,
            'url': gulp.TF_EXPERTEN,
            'aktiv': True,
            'intervall_min': 30,
        },
    )
    return src


def _dedup(gulp_id: str) -> str:
    return hashlib.sha256(f'gulp:{gulp_id}'.encode('utf-8')).hexdigest()


def _parse_date(val) -> Optional[date]:
    if not val:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    return gulp._parse_date(val)


def _dec(val) -> Optional[Decimal]:
    if val is None or val == '':
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError):
        return None


def find_crm_by_gulp_id(gulp_id: str) -> Optional[dict[str, Any]]:
    """ORM-Lookup SuiteCRM Contact über cstm.gulp_id_c."""
    gid = str(gulp_id or '').strip()
    if not gid:
        return None
    try:
        from apps.abpe_crm.models import CrmContact
    except Exception:
        return None
    try:
        c = (
            CrmContact.objects
            .select_related('cstm')
            .filter(cstm__gulp_id_c=gid)
            .first()
        )
        if not c:
            # manchmal mit Leerzeichen/Prefix
            c = (
                CrmContact.objects
                .select_related('cstm')
                .filter(cstm__gulp_id_c__iexact=gid)
                .first()
            )
        if not c:
            return None
        cstm = getattr(c, 'cstm', None)
        return {
            'crm_id': c.crm_id,
            'first_name': c.first_name or '',
            'last_name': c.last_name or '',
            'full_name': c.full_name or '',
            'gulp_id': getattr(cstm, 'gulp_id_c', '') if cstm else gid,
            'verfuegbar_ab': getattr(cstm, 'verfuegbar_ab_c', None) if cstm else None,
            'konditionen': getattr(cstm, 'konditionen_c', '') if cstm else '',
            'kontakt_status': getattr(cstm, 'kontakt_status_c', '') if cstm else '',
            'city': c.primary_address_city or '',
            'title': c.title or '',
            'description': c.description or '',
        }
    except Exception as exc:
        log.warning('CRM gulp_id lookup failed: %s', exc)
        return None


def _fill_missing_crm(crm_id: str, patch: dict[str, Any], log_rows: list) -> list:
    """Fehlende CRM-Felder nachziehen (leere füllen, Verfügbarkeit aktualisieren)."""
    try:
        from apps.abpe_crm.models import CrmContact
    except Exception:
        return log_rows
    try:
        c = CrmContact.objects.select_related('cstm').filter(crm_id=crm_id).first()
        if not c:
            return log_rows
        cstm = getattr(c, 'cstm', None)
        changed = []
        fn = (c.first_name or '').strip()
        ln = (c.last_name or '').strip()
        new_first = (patch.get('first_name') or '').strip()
        new_last = (patch.get('last_name') or '').strip()
        if new_first and (not fn or fn.lower() == 'gulp' or fn.isdigit()):
            if not re.search(r'(gmbh|ag|experts?|consulting)', new_first, re.I):
                c.first_name = new_first
                changed.append('first_name')
        if new_last and (not ln or ln.lower().startswith('gulp') or ln.isdigit()):
            c.last_name = new_last
            changed.append('last_name')
        if patch.get('city') and not (c.primary_address_city or '').strip():
            c.primary_address_city = patch['city']
            changed.append('city')
        if patch.get('description') and not (c.description or '').strip():
            c.description = patch['description'][:5000]
            changed.append('description')
        if changed:
            c.save()
        if cstm is not None:
            cstm_changed = []
            v_ab = patch.get('verfuegbar_ab')
            if v_ab:
                nd = _parse_date(v_ab)
                cur = getattr(cstm, 'verfuegbar_ab_c', None)
                if nd and cur != nd:
                    cstm.verfuegbar_ab_c = nd
                    cstm_changed.append('verfuegbar_ab_c')
            if patch.get('gulp_id') and not (getattr(cstm, 'gulp_id_c', '') or '').strip():
                cstm.gulp_id_c = str(patch['gulp_id'])[:16]
                cstm_changed.append('gulp_id_c')
            if patch.get('konditionen') and not (getattr(cstm, 'konditionen_c', '') or '').strip():
                cstm.konditionen_c = str(patch['konditionen'])[:255]
                cstm_changed.append('konditionen_c')
            if hasattr(cstm, 'gulp_last_updated_c'):
                from django.utils import timezone as dj_tz
                cstm.gulp_last_updated_c = dj_tz.now()
                cstm_changed.append('gulp_last_updated_c')
            if cstm_changed:
                cstm.save()
                changed.extend(cstm_changed)
        if changed:
            log_rows.append({
                'at': timezone.now().isoformat(),
                'action': 'crm_fill_missing',
                'fields': changed,
            })
    except Exception as exc:
        log.warning('CRM fill failed for %s: %s', crm_id, exc)
        log_rows.append({
            'at': timezone.now().isoformat(),
            'action': 'crm_fill_error',
            'error': str(exc),
        })
    return log_rows


def _append_cv_version(obj, text: str, source: str = 'gulp') -> None:
    text = (text or '').strip()
    if not text:
        return
    h = hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]
    versions = list(obj.cv_versions or [])
    if versions and versions[-1].get('hash') == h:
        return
    versions.append({
        'at': timezone.now().isoformat(),
        'source': source,
        'hash': h,
        'chars': len(text),
        'text': text[:80000],
    })
    obj.cv_versions = versions[-20:]  # keep last 20


def upsert_berater(item: dict[str, Any], *, apply_crm: bool = True) -> Any:
    """Item-Dict → RadarConsultantItem (+ optional CRM update)."""
    from apps.abpe_shaduler.models import RadarConsultantItem

    src = _ensure_source()
    gulp_id = str(item.get('gulp_id') or '').strip()
    if not gulp_id:
        raise ValueError('gulp_id required')
    dedup = _dedup(gulp_id)
    obj = RadarConsultantItem.objects.filter(quelle=src, dedup_hash=dedup).first()
    if not obj:
        obj = RadarConsultantItem.objects.filter(gulp_id=gulp_id).first()

    crm = find_crm_by_gulp_id(gulp_id)
    name = (item.get('name') or '').strip()
    if crm and crm.get('full_name'):
        name = crm['full_name']
    elif not name or name.lower().startswith('gulp '):
        # Platzhalter wenn neu / ohne Profilname
        name = gulp.placeholder_name(gulp_id)

    skills = item.get('skills') if isinstance(item.get('skills'), list) else []
    ort = (item.get('ort') or '').strip()
    if crm and not ort:
        ort = crm.get('city') or ''
    verfuegbar = _parse_date(item.get('verfuegbar_ab'))
    satz = _dec(item.get('satz'))
    beschreibung = (item.get('beschreibung') or '').strip()
    eck = dict(item.get('eckdaten') or {})
    eck.update({
        'gulp_id': gulp_id,
        'mongo_id': item.get('mongo_id') or '',
        'first_name': item.get('first_name') or '',
        'last_name': item.get('last_name') or '',
        'source': item.get('source') or 'gulp',
    })
    if crm:
        eck['crm_status'] = crm.get('kontakt_status') or ''

    log_rows = list((obj.auto_update_log if obj else None) or [])
    created = obj is None
    if created:
        obj = RadarConsultantItem(
            quelle=src,
            dedup_hash=dedup,
            gulp_id=gulp_id,
            status=RadarConsultantItem.Status.NEU,
            eingegangen_am=timezone.now(),
        )

    obj.gulp_id = gulp_id
    obj.profil_url = item.get('profil_url') or gulp.profil_url_for_gulp_id(gulp_id)
    obj.name = name
    if skills:
        obj.skills = skills
    if ort:
        obj.ort = ort
    if verfuegbar:
        obj.verfuegbar_ab = verfuegbar
    if satz is not None:
        obj.satz = satz
    if beschreibung:
        obj.beschreibung = beschreibung
    obj.eckdaten = {**(obj.eckdaten or {}), **eck}
    if not obj.eingegangen_am:
        obj.eingegangen_am = timezone.now()

    if item.get('cv_text'):
        _append_cv_version(obj, item['cv_text'], source=item.get('source') or 'gulp')

    if crm:
        obj.match_status = RadarConsultantItem.MatchStatus.BEKANNT
        obj.crm_contact_id = crm['crm_id']
        obj.match_confidence = 1.0
        if apply_crm:
            log_rows = _fill_missing_crm(crm['crm_id'], {
                'first_name': item.get('first_name') or '',
                'last_name': item.get('last_name') or '',
                'city': ort,
                'description': beschreibung,
                'verfuegbar_ab': verfuegbar.isoformat() if verfuegbar else None,
                'gulp_id': gulp_id,
                'konditionen': str(satz) if satz is not None else '',
            }, log_rows)
    else:
        if not obj.crm_contact_id:
            obj.match_status = RadarConsultantItem.MatchStatus.UNBEKANNT
            obj.match_confidence = 0.0

    log_rows.append({
        'at': timezone.now().isoformat(),
        'action': 'upsert_create' if created else 'upsert_update',
        'gulp_id': gulp_id,
    })
    obj.auto_update_log = log_rows[-50:]
    obj.save()
    try:
        berater_index.index_one(obj)
    except Exception as exc:
        log.warning('berater ES index failed: %s', exc)
    return obj


def serialize_berater(obj) -> dict[str, Any]:
    eck = obj.eckdaten or {}
    st_map = {
        'bekannt': 'known',
        'unsicher': 'maybe',
        'unbekannt': 'new',
    }
    return {
        'id': str(obj.pk),
        'name': obj.name or gulp.placeholder_name(obj.gulp_id),
        'gulp_id': obj.gulp_id or '',
        'src': (obj.quelle.name if obj.quelle_id else 'gulp'),
        'sources': [obj.quelle.name] if obj.quelle_id else ['gulp'],
        'skills': obj.skills or [],
        'ort': obj.ort or '',
        'city': obj.ort or '',
        'verfuegbar_ab': obj.verfuegbar_ab.isoformat() if obj.verfuegbar_ab else None,
        'satz': float(obj.satz) if obj.satz is not None else None,
        'beschreibung': obj.beschreibung or '',
        'profil_url': obj.profil_url or '',
        'match_status': obj.match_status,
        'st': st_map.get(obj.match_status, 'new'),
        'status': obj.status,
        'crm_contact_id': obj.crm_contact_id or '',
        'crm_url': (
            f'/crm/berater/?detail={obj.crm_contact_id}' if obj.crm_contact_id else ''
        ),
        'eingegangen_am': obj.eingegangen_am.isoformat() if obj.eingegangen_am else None,
        'updated_at': obj.updated_at.isoformat() if obj.updated_at else None,
        'cv_versions': len(obj.cv_versions or []),
        'cv_latest_chars': (obj.cv_versions or [{}])[-1].get('chars') if obj.cv_versions else None,
        'meta': ' · '.join(x for x in [
            f'Gulp {obj.gulp_id}' if obj.gulp_id else '',
            obj.ort or '',
            f'ab {obj.verfuegbar_ab.isoformat()}' if obj.verfuegbar_ab else '',
            f'{obj.satz} €' if obj.satz is not None else '',
        ] if x),
        'note': (
            '✔ CRM ' + (obj.crm_contact_id[:8] + '…' if obj.crm_contact_id else '')
            if obj.match_status == 'bekannt'
            else ('Platzhalter — optional in CRM anlegen' if (obj.name or '').startswith('Gulp ')
                  else 'neu / unbekannt')
        ),
        'eckdaten': eck,
    }


def list_berater(
    *,
    q: str = '',
    days: int = 0,
    source: str = '',
    status: str = 'neu',
    match_status: str = '',
    sort: str = 'date_desc',
    limit: int = 300,
    refresh: bool = False,
    available_only: bool = True,
    auto_seed: bool = False,
) -> dict[str, Any]:
    from apps.abpe_shaduler.models import RadarConsultantItem

    fetched = 0
    persist_info: dict[str, Any] = {}
    seed_info: dict[str, Any] = {}

    # Leere Radar-Tabelle → einmal CRM-Seed (z. B. nach frischem Deploy)
    if auto_seed and not RadarConsultantItem.objects.exists():
        seed_info = seed_from_crm(limit=max(limit, 500))
        persist_info['auto_seed'] = seed_info

    if refresh:
        pack = gulp.fetch_experts_list(page=0, size=40, available_only=available_only)
        persist_info['gulp_fetch'] = {
            'ok': pack.get('ok'),
            'error': pack.get('error'),
            'needs_auth': pack.get('needs_auth'),
            'count': len(pack.get('results') or []),
        }
        if pack.get('ok'):
            for it in pack.get('results') or []:
                try:
                    upsert_berater(it, apply_crm=True)
                    fetched += 1
                except Exception as exc:
                    log.warning('upsert berater failed: %s', exc)
        persist_info['fetched'] = fetched

    # ES first
    list_source = 'db'
    results: list[dict] = []
    by_src: dict = {}
    es_total = None
    try:
        es_pack = berater_index.search(
            q=q,
            days=days if days > 0 else None,
            source=source,
            status=status if status != 'all' else None,
            match_status=match_status or None,
            sort=sort,
            limit=limit,
        )
    except Exception as exc:
        log.warning('berater ES search error: %s', exc)
        es_pack = None

    if es_pack and es_pack.get('ids') is not None:
        list_source = 'elasticsearch'
        by_src = es_pack.get('by_source') or {}
        es_total = es_pack.get('total')
        ids = es_pack.get('ids') or []
        if ids:
            import uuid as _uuid
            uuids = []
            for i in ids:
                try:
                    uuids.append(_uuid.UUID(str(i)))
                except Exception:
                    continue
            objs = {
                str(o.pk): o
                for o in RadarConsultantItem.objects.filter(pk__in=uuids).select_related('quelle')
            }
            results = [serialize_berater(objs[str(u)]) for u in uuids if str(u) in objs]
        if not results:
            list_source = 'db'
            by_src = {}
            es_total = None

    if list_source != 'elasticsearch':
        qs = RadarConsultantItem.objects.select_related('quelle').all()
        if status and status != 'all':
            qs = qs.filter(status=status)
        if match_status:
            qs = qs.filter(match_status=match_status)
        if source:
            qs = qs.filter(quelle__name=source)
        else:
            qs = qs.filter(quelle__name__in=BERATER_SOURCES)
        if days and int(days) > 0:
            since = timezone.now() - timedelta(days=int(days))
            qs = qs.filter(Q(eingegangen_am__gte=since) | Q(updated_at__gte=since))
        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(gulp_id__icontains=q)
                | Q(ort__icontains=q)
                | Q(beschreibung__icontains=q)
                | Q(skills__icontains=q)
            )
        if sort in ('date_asc', 'asc', 'oldest'):
            qs = qs.order_by('eingegangen_am', 'updated_at')
        else:
            qs = qs.order_by('-eingegangen_am', '-updated_at')
        rows = list(qs[:limit])
        results = [serialize_berater(o) for o in rows]
        list_source = 'db'
        # by_source
        agg = (
            RadarConsultantItem.objects.filter(quelle__name__in=BERATER_SOURCES)
            .values('quelle__name')
            .annotate(c=Count('id'))
        )
        by_src = {a['quelle__name']: a['c'] for a in agg if a['quelle__name']}

    return {
        'ok': True,
        'demo': False,
        'results': results,
        'count': len(results),
        'by_source': by_src,
        'list_source': list_source,
        'es_total': es_total,
        'fetched': fetched if refresh else None,
        'persist': persist_info,
        'seed': seed_info or None,
        'gulp_session': gulp.has_gulp_session(),
        'available_only': available_only,
    }


def paste_berater(text: str) -> dict[str, Any]:
    gid = gulp.parse_gulp_id(text)
    if not gid:
        return {'ok': False, 'error': 'Keine Gulp-ID in Eingabe erkannt'}
    packed = gulp.fetch_expert_by_gulp_id(gid)
    item = {
        'gulp_id': gid,
        'name': packed.get('name') or gulp.placeholder_name(gid),
        'profil_url': packed.get('profil_url') or gulp.profil_url_for_gulp_id(gid),
        'skills': packed.get('skills') or [],
        'ort': packed.get('ort') or '',
        'verfuegbar_ab': packed.get('verfuegbar_ab'),
        'satz': packed.get('satz'),
        'beschreibung': packed.get('beschreibung') or '',
        'cv_text': packed.get('cv_text') or '',
        'first_name': packed.get('first_name') or ('Gulp' if not packed.get('ok') else ''),
        'last_name': packed.get('last_name') or (gid if not packed.get('ok') else ''),
        'source': 'gulp',
        'mongo_id': packed.get('mongo_id') or '',
    }
    obj = upsert_berater(item, apply_crm=True)
    return {
        'ok': True,
        'item': serialize_berater(obj),
        'fetched': bool(packed.get('ok')),
        'needs_auth': packed.get('needs_auth'),
        'fetch_error': packed.get('error'),
    }


def seed_from_crm(*, limit: int = 500) -> dict[str, Any]:
    """CRM-Kontakte mit gulp_id_c → Radar (bekannt)."""
    try:
        from apps.abpe_crm.models import CrmContact, CrmContactCstm
    except Exception as exc:
        return {'ok': False, 'error': f'CRM nicht verfügbar: {exc}'}

    # Diagnose: wie viele gulp_ids in CRM?
    try:
        crm_with_gulp = (
            CrmContactCstm.objects
            .exclude(gulp_id_c__isnull=True)
            .exclude(gulp_id_c='')
            .exclude(gulp_id_c__regex=r'^\s*$')
            .count()
        )
    except Exception:
        try:
            crm_with_gulp = (
                CrmContactCstm.objects
                .exclude(gulp_id_c__isnull=True)
                .exclude(gulp_id_c='')
                .count()
            )
        except Exception as exc:
            return {'ok': False, 'error': f'CRM cstm query failed: {exc}', 'crm_with_gulp': 0}

    # order_by: Feld heißt crm_date_modified (nicht date_modified)
    try:
        qs = (
            CrmContact.objects
            .select_related('cstm')
            .exclude(cstm__gulp_id_c__isnull=True)
            .exclude(cstm__gulp_id_c='')
            .order_by('-crm_date_modified', '-id')[:limit]
        )
        rows = list(qs)
    except Exception as exc_orm:
        log.warning('seed ORM path failed (%s) — fallback Cstm', exc_orm)
        rows = []
        try:
            cstms = (
                CrmContactCstm.objects
                .select_related('contact')
                .exclude(gulp_id_c__isnull=True)
                .exclude(gulp_id_c='')
                .order_by('-id')[:limit]
            )
            for cstm in cstms:
                c = getattr(cstm, 'contact', None)
                if c is None:
                    continue
                # attach cstm for loop below
                c._seed_cstm = cstm
                rows.append(c)
        except Exception as exc2:
            return {
                'ok': False,
                'error': f'seed failed: {exc_orm} / {exc2}',
                'crm_with_gulp': crm_with_gulp,
            }

    n_ok = n_err = n_skip = 0
    for c in rows:
        cstm = getattr(c, '_seed_cstm', None) or getattr(c, 'cstm', None)
        gid = (getattr(cstm, 'gulp_id_c', '') or '').strip() if cstm else ''
        if not gid:
            n_skip += 1
            continue
        profil = (getattr(cstm, 'gulp_profil_c', None) or '') if cstm else ''
        desc = (c.description or '') or profil
        try:
            upsert_berater({
                'gulp_id': gid,
                'name': c.full_name or gulp.placeholder_name(gid),
                'first_name': c.first_name or '',
                'last_name': c.last_name or '',
                'ort': (
                    c.primary_address_city
                    or (getattr(cstm, 'einsatzort_stadt_c', None) if cstm else '')
                    or ''
                ),
                'verfuegbar_ab': getattr(cstm, 'verfuegbar_ab_c', None) if cstm else None,
                'beschreibung': (desc or '')[:4000],
                'cv_text': (profil or desc or '')[:50000],
                'profil_url': (
                    (getattr(cstm, 'web_profil1_location_c', None) if cstm else None)
                    or gulp.profil_url_for_gulp_id(gid)
                ),
                'source': 'crm_seed',
                'skills': [],
            }, apply_crm=False)
            n_ok += 1
        except Exception as exc:
            log.warning('seed crm %s: %s', gid, exc)
            n_err += 1
    return {
        'ok': True,
        'seeded': n_ok,
        'errors': n_err,
        'skipped': n_skip,
        'crm_with_gulp': crm_with_gulp,
        'scanned': len(rows),
    }


def set_status(pk: str, status: str) -> dict[str, Any]:
    from apps.abpe_shaduler.models import RadarConsultantItem
    import uuid
    obj = RadarConsultantItem.objects.filter(pk=uuid.UUID(str(pk))).first()
    if not obj:
        return {'ok': False, 'error': 'not found'}
    if status not in dict(RadarConsultantItem.Status.choices):
        return {'ok': False, 'error': 'invalid status'}
    obj.status = status
    obj.save(update_fields=['status', 'updated_at'])
    try:
        berater_index.index_one(obj)
    except Exception:
        pass
    return {'ok': True, 'item': serialize_berater(obj)}
