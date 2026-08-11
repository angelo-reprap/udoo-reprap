"""
Radar Berater — Persistenz, CRM-Match (gulp_id), Liste, Paste, CRM-Seed,
Gulp-Aktualisieren (Existenz + Verfügbarkeit).
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from django.db.models import Count, Q
from django.utils import timezone

from . import radar_berater_gulp as gulp
from . import radar_berater_fl as fl
from . import radar_berater_index as berater_index

log = logging.getLogger('abpe_shaduler.radar_berater')

SOURCE_NAME = 'gulp'
SOURCE_NAME_FL = 'freelancermap'
BERATER_SOURCES = ('gulp', 'freelancermap')


def _ensure_source(name: str = SOURCE_NAME):
    """RadarSource für Berater — robust gegen Duplikate (name+ziel)."""
    from django.db.models import Count

    from apps.abpe_shaduler.models import RadarSource

    url = gulp.TF_EXPERTEN if name == SOURCE_NAME else fl.FM_LIST
    typ = RadarSource.Typ.HTML_PUBLIC
    ziel = RadarSource.Ziel.BERATER
    qs = RadarSource.objects.filter(name=name, ziel=ziel)
    src = (
        qs.annotate(_n=Count('consultant_items', distinct=True))
        .order_by('-aktiv', '-_n', 'created_at')
        .first()
    )
    if src is None:
        src = RadarSource.objects.create(
            name=name,
            ziel=ziel,
            typ=typ,
            url=url,
            aktiv=True,
            intervall_min=30,
        )
    else:
        dup_ids = list(qs.exclude(pk=src.pk).values_list('pk', flat=True))
        if dup_ids:
            RadarSource.objects.filter(pk__in=dup_ids).update(
                aktiv=False,
                letzter_status='duplikat-deaktiviert',
            )
        updates = []
        if url and src.url != url:
            src.url = url
            updates.append('url')
        if not src.aktiv:
            src.aktiv = True
            updates.append('aktiv')
        if updates:
            src.save(update_fields=updates)
    return src


def _dedup(gulp_id: str) -> str:
    return hashlib.sha256(f'gulp:{gulp_id}'.encode('utf-8')).hexdigest()


def _dedup_fm(fm_id: str) -> str:
    return hashlib.sha256(f'fm:{fm_id}'.encode('utf-8')).hexdigest()


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


def find_crm_by_fm(fm_id: str = '', slug: str = '', profil_url: str = '') -> Optional[dict[str, Any]]:
    """CRM-Lookup über freelancermap_profil_c (URL/Slug/ID)."""
    fid = str(fm_id or '').strip()
    slug = str(slug or '').strip().strip('/')
    profil_url = str(profil_url or '').strip()
    needles = []
    if profil_url:
        needles.append(profil_url)
    if slug:
        needles.append(f'/profil/{slug}')
        needles.append(slug)
    if fid:
        needles.append(fid)
    if not needles:
        return None
    try:
        from apps.abpe_crm.models import CrmContact
    except Exception:
        return None
    try:
        c = None
        for n in needles:
            c = (
                CrmContact.objects
                .select_related('cstm')
                .filter(cstm__freelancermap_profil_c__icontains=n)
                .first()
            )
            if c:
                break
        if not c:
            return None
        cstm = getattr(c, 'cstm', None)
        return {
            'crm_id': c.crm_id,
            'first_name': c.first_name or '',
            'last_name': c.last_name or '',
            'full_name': c.full_name or '',
            'gulp_id': getattr(cstm, 'gulp_id_c', '') if cstm else '',
            'freelancermap_profil': getattr(cstm, 'freelancermap_profil_c', '') if cstm else '',
            'verfuegbar_ab': getattr(cstm, 'verfuegbar_ab_c', None) if cstm else None,
            'konditionen': getattr(cstm, 'konditionen_c', '') if cstm else '',
            'kontakt_status': getattr(cstm, 'kontakt_status_c', '') if cstm else '',
            'city': c.primary_address_city or '',
            'title': c.title or '',
            'description': c.description or '',
        }
    except Exception as exc:
        log.warning('CRM FM lookup failed: %s', exc)
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
            if patch.get('freelancermap_profil') and hasattr(cstm, 'freelancermap_profil_c'):
                cur_fm = (getattr(cstm, 'freelancermap_profil_c', '') or '').strip()
                new_fm = str(patch['freelancermap_profil']).strip()
                if new_fm and not cur_fm:
                    cstm.freelancermap_profil_c = new_fm[:255]
                    cstm_changed.append('freelancermap_profil_c')
            if hasattr(cstm, 'freelancermap_last_updated_c') and patch.get('freelancermap_touch'):
                from django.utils import timezone as dj_tz
                cstm.freelancermap_last_updated_c = dj_tz.now()
                cstm_changed.append('freelancermap_last_updated_c')
            if patch.get('konditionen') and not (getattr(cstm, 'konditionen_c', '') or '').strip():
                cstm.konditionen_c = str(patch['konditionen'])[:255]
                cstm_changed.append('konditionen_c')
            if hasattr(cstm, 'gulp_last_updated_c') and patch.get('gulp_id'):
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
    """Item-Dict → RadarConsultantItem (+ optional CRM update). Gulp- oder FM-ID."""
    from apps.abpe_shaduler.models import RadarConsultantItem

    gulp_id = str(item.get('gulp_id') or '').strip()
    fm_id = str(item.get('fm_id') or '').strip()
    fm_slug = str(item.get('fm_slug') or '').strip()
    source_name = str(
        item.get('source_name')
        or (SOURCE_NAME_FL if (fm_id and not gulp_id) else SOURCE_NAME)
    ).strip() or SOURCE_NAME
    src = _ensure_source(source_name)

    if not gulp_id and not fm_id:
        raise ValueError('gulp_id oder fm_id required')

    if gulp_id:
        dedup = _dedup(gulp_id)
        obj = RadarConsultantItem.objects.filter(quelle=src, dedup_hash=dedup).first()
        if not obj:
            obj = RadarConsultantItem.objects.filter(gulp_id=gulp_id).first()
        crm = find_crm_by_gulp_id(gulp_id)
    else:
        dedup = _dedup_fm(fm_id)
        obj = RadarConsultantItem.objects.filter(quelle=src, dedup_hash=dedup).first()
        if not obj:
            # Fallback: eckdaten.fm_id
            obj = (
                RadarConsultantItem.objects
                .filter(quelle=src, eckdaten__fm_id=fm_id)
                .first()
            )
        crm = find_crm_by_fm(
            fm_id=fm_id,
            slug=fm_slug,
            profil_url=item.get('profil_url') or '',
        )

    name = (item.get('name') or '').strip()
    if crm and crm.get('full_name'):
        name = crm['full_name']
    elif not name or name.lower().startswith('gulp ') or name.lower().startswith('fm '):
        # Headline aus Beschreibung / title
        title = (item.get('title') or '').strip()
        desc0 = (item.get('beschreibung') or '').strip()
        first_line = desc0.split('\n')[0].strip() if desc0 else ''
        if title and len(title) > 3:
            name = title[:120]
        elif first_line and len(first_line) > 8 and not first_line.lower().startswith('projekte'):
            name = first_line[:120]
        else:
            name = (
                gulp.placeholder_name(gulp_id) if gulp_id
                else (f'FM {fm_id}' if fm_id else 'Berater')
            )

    skills = item.get('skills') if isinstance(item.get('skills'), list) else []
    ort = (item.get('ort') or '').strip()
    if crm and not ort:
        ort = crm.get('city') or ''
    verfuegbar = _parse_date(item.get('verfuegbar_ab'))
    satz = _dec(item.get('satz'))
    beschreibung = (item.get('beschreibung') or '').strip()
    eck = dict(item.get('eckdaten') or {})
    eck.update({
        'source': item.get('source') or source_name,
        'first_name': item.get('first_name') or '',
        'last_name': item.get('last_name') or '',
    })
    if gulp_id:
        eck['gulp_id'] = gulp_id
        eck['mongo_id'] = item.get('mongo_id') or eck.get('mongo_id') or ''
    if fm_id:
        eck['fm_id'] = fm_id
        eck['fm_slug'] = fm_slug
        eck['fm_user_id'] = item.get('fm_user_id') or ''
    if crm:
        eck['crm_status'] = crm.get('kontakt_status') or ''

    log_rows = list((obj.auto_update_log if obj else None) or [])
    created = obj is None
    if created:
        obj = RadarConsultantItem(
            quelle=src,
            dedup_hash=dedup,
            gulp_id=gulp_id or '',
            status=RadarConsultantItem.Status.NEU,
            eingegangen_am=timezone.now(),
        )

    if gulp_id:
        obj.gulp_id = gulp_id
    # Profil-URL
    if item.get('profil_url'):
        obj.profil_url = item['profil_url']
    elif gulp_id:
        obj.profil_url = gulp.profil_url_for_gulp_id(gulp_id)
    elif fm_id:
        obj.profil_url = fl.profil_url_for(slug=fm_slug, fm_id=fm_id)

    obj.name = name
    if getattr(obj, 'deleted_at', None) or obj.status == RadarConsultantItem.Status.GELOESCHT:
        obj.deleted_at = None
        if obj.status == RadarConsultantItem.Status.GELOESCHT:
            obj.status = RadarConsultantItem.Status.NEU
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

    # „Datum: neueste“ = Wann zuletzt in FM/Gulp-Aktuellste gesehen (Listenrang),
    # nicht Verfügbar-ab und nicht einmalige Importzeit.
    list_rank = item.get('list_rank')
    bump = item.get('bump_eingegangen') or item.get('from_available_sync')
    if list_rank is not None:
        try:
            rank_i = max(0, int(list_rank))
        except (TypeError, ValueError):
            rank_i = 0
        # Erster Treffer der Aktuellste-Liste = jetzt, folgende je 1s älter
        obj.eingegangen_am = timezone.now() - timedelta(seconds=rank_i)
    elif bump:
        obj.eingegangen_am = timezone.now()
    elif not obj.eingegangen_am:
        obj.eingegangen_am = timezone.now()

    if item.get('cv_text'):
        _append_cv_version(obj, item['cv_text'], source=item.get('source') or source_name)

    if crm:
        obj.match_status = RadarConsultantItem.MatchStatus.BEKANNT
        obj.crm_contact_id = crm['crm_id']
        obj.match_confidence = 1.0
        if apply_crm:
            patch = {
                'first_name': item.get('first_name') or '',
                'last_name': item.get('last_name') or '',
                'city': ort,
                'description': beschreibung,
                'verfuegbar_ab': verfuegbar.isoformat() if verfuegbar else None,
                'konditionen': str(satz) if satz is not None else '',
            }
            if gulp_id:
                patch['gulp_id'] = gulp_id
            if fm_id:
                patch['freelancermap_profil'] = (
                    item.get('profil_url') or fl.profil_url_for(slug=fm_slug, fm_id=fm_id)
                )
                patch['freelancermap_touch'] = True
            log_rows = _fill_missing_crm(crm['crm_id'], patch, log_rows)
    else:
        if not obj.crm_contact_id:
            obj.match_status = RadarConsultantItem.MatchStatus.UNBEKANNT
            obj.match_confidence = 0.0

    log_rows.append({
        'at': timezone.now().isoformat(),
        'action': 'upsert_create' if created else 'upsert_update',
        'gulp_id': gulp_id or '',
        'fm_id': fm_id or '',
    })
    obj.auto_update_log = log_rows[-50:]
    obj.save()
    try:
        berater_index.index_one(obj)
    except Exception as exc:
        log.warning('berater ES index failed: %s', exc)
    return obj


def serialize_berater(obj, *, detail: bool = False, preview_chars: int = 4000) -> dict[str, Any]:
    eck = obj.eckdaten or {}
    st_map = {
        'bekannt': 'known',
        'unsicher': 'maybe',
        'unbekannt': 'new',
    }
    body = obj.beschreibung or ''
    if detail:
        body = body[: max(0, int(preview_chars or 4000))]
    else:
        body = ''  # Liste ohne Volltext
    mongo = str(eck.get('mongo_id') or '').strip()
    fm_id = str(eck.get('fm_id') or '').strip()
    fm_slug = str(eck.get('fm_slug') or '').strip()
    src_name = (obj.quelle.name if obj.quelle_id else '') or (
        SOURCE_NAME_FL if fm_id and not obj.gulp_id else SOURCE_NAME
    )
    is_fm = src_name == SOURCE_NAME_FL or bool(fm_id and not obj.gulp_id)
    profil = ''
    kontakt = ''
    if is_fm:
        profil = obj.profil_url or fl.profil_url_for(slug=fm_slug, fm_id=fm_id)
        kontakt = fl.kontakt_url_for(slug=fm_slug, fm_id=fm_id)
    elif mongo and re.fullmatch(r'[a-f0-9]{24}', mongo, re.I):
        profil = f'https://www.gulp.de/talentfinder/app/experten/{mongo}'
        kontakt = gulp.kontakt_url_for(gulp_id=obj.gulp_id or '', mongo_id=mongo)
    elif obj.gulp_id:
        profil = gulp.profil_url_for_gulp_id(obj.gulp_id)
        kontakt = gulp.kontakt_url_for(gulp_id=obj.gulp_id or '', mongo_id=mongo)
    else:
        profil = obj.profil_url or ''
        kontakt = gulp.kontakt_url_for(gulp_id=obj.gulp_id or '', mongo_id=mongo)
    # Listen-Titel: erste Zeile der Beschreibung, wenn Name nur Platzhalter
    display_name = obj.name or (
        gulp.placeholder_name(obj.gulp_id) if obj.gulp_id
        else (f'FM {fm_id}' if fm_id else 'Berater')
    )
    if (
        (display_name or '').startswith('Gulp ') or (display_name or '').startswith('FM ')
    ) and (obj.beschreibung or '').strip():
        first_line = (obj.beschreibung or '').strip().split('\n')[0].strip()
        if first_line and len(first_line) > 8:
            display_name = first_line[:120]
    id_meta = (
        f'FM {fm_id}' if is_fm and fm_id
        else (f'Gulp {obj.gulp_id}' if obj.gulp_id else '')
    )
    return {
        'id': str(obj.pk),
        'name': display_name,
        'gulp_id': obj.gulp_id or '',
        'fm_id': fm_id,
        'fm_slug': fm_slug,
        'mongo_id': mongo,
        'src': src_name,
        'sources': [src_name],
        'skills': obj.skills or [],
        'ort': obj.ort or '',
        'city': obj.ort or '',
        'verfuegbar_ab': obj.verfuegbar_ab.isoformat() if obj.verfuegbar_ab else None,
        'satz': float(obj.satz) if obj.satz is not None else None,
        'beschreibung': body,
        'profil_url': profil,
        'kontakt_url': kontakt,
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
        'deleted': bool(getattr(obj, 'deleted_at', None)),
        'meta': ' · '.join(x for x in [
            id_meta,
            obj.ort or '',
            f'ab {obj.verfuegbar_ab.isoformat()}' if obj.verfuegbar_ab else '',
            f'{obj.satz} €' if obj.satz is not None else '',
        ] if x),
        'note': (
            'gelöscht (CRM)' if getattr(obj, 'deleted_at', None)
            else (
                'nicht mehr in Gulp'
                if (eck.get('gulp_status') == 'gone')
                else (
                    '✔ CRM ' + (obj.crm_contact_id[:8] + '…' if obj.crm_contact_id else '')
                    if obj.match_status == 'bekannt'
                    else (
                        'Platzhalter — optional in CRM anlegen'
                        if (obj.name or '').startswith(('Gulp ', 'FM '))
                        else 'neu / unbekannt'
                    )
                )
            )
        ),
        'gulp_status': eck.get('gulp_status') or 'ok',
        'eckdaten': eck if detail else {},
    }


def serialize_list_hit(hit: dict[str, Any]) -> dict[str, Any]:
    """Leichter Listeneintrag aus ES-_source (ohne beschreibung)."""
    cid = hit.get('crm_contact_id') or ''
    note = hit.get('note') or ''
    mongo = str(hit.get('mongo_id') or '').strip()
    gid = hit.get('gulp_id') or ''
    fm_id = str(hit.get('fm_id') or '').strip()
    fm_slug = str(hit.get('fm_slug') or '').strip()
    src = (hit.get('source') or ('freelancermap' if fm_id and not gid else 'gulp')).strip().lower()
    is_fm = src == SOURCE_NAME_FL or bool(fm_id and not gid)
    kontakt = hit.get('kontakt_url') or ''
    profil = hit.get('profil_url') or ''
    if is_fm:
        if not profil:
            profil = fl.profil_url_for(slug=fm_slug, fm_id=fm_id)
        if not kontakt:
            kontakt = fl.kontakt_url_for(slug=fm_slug, fm_id=fm_id)
    else:
        kontakt = kontakt or gulp.kontakt_url_for(gulp_id=gid, mongo_id=mongo)
        if not profil:
            if mongo and re.fullmatch(r'[a-f0-9]{24}', mongo, re.I):
                profil = f'https://www.gulp.de/talentfinder/app/experten/{mongo}'
            elif gid:
                profil = gulp.profil_url_for_gulp_id(gid)
    return {
        'id': str(hit.get('id') or ''),
        'name': hit.get('name') or (
            gulp.placeholder_name(gid) if gid else (f'FM {fm_id}' if fm_id else 'Berater')
        ),
        'gulp_id': gid,
        'fm_id': fm_id,
        'fm_slug': fm_slug,
        'mongo_id': mongo,
        'src': src,
        'sources': [src],
        'skills': hit.get('skills') or [],
        'ort': hit.get('ort') or '',
        'city': hit.get('ort') or '',
        'verfuegbar_ab': hit.get('verfuegbar_ab'),
        'satz': hit.get('satz'),
        'beschreibung': '',
        'profil_url': profil,
        'kontakt_url': kontakt,
        'match_status': hit.get('match_status') or 'unbekannt',
        'st': hit.get('st') or 'new',
        'status': hit.get('status') or 'neu',
        'crm_contact_id': cid,
        'crm_url': f'/crm/berater/?detail={cid}' if cid else '',
        'eingegangen_am': hit.get('eingegangen_am'),
        'updated_at': hit.get('updated_at'),
        'cv_versions': hit.get('cv_versions') or 0,
        'deleted': bool(hit.get('deleted')),
        'meta': hit.get('meta') or '',
        'note': note,
        'gulp_status': 'gone' if 'nicht mehr in Gulp' in str(note) else 'ok',
        'eckdaten': {},
    }


def get_berater_detail(pk: str, *, preview_chars: int = 4000) -> dict[str, Any]:
    from apps.abpe_shaduler.models import RadarConsultantItem
    import uuid
    try:
        uid = uuid.UUID(str(pk))
    except Exception:
        return {'ok': False, 'error': 'invalid id'}
    obj = RadarConsultantItem.objects.select_related('quelle').filter(pk=uid).first()
    if not obj:
        return {'ok': False, 'error': 'not found'}
    return {'ok': True, 'item': serialize_berater(obj, detail=True, preview_chars=preview_chars)}


def list_berater(
    *,
    q: str = '',
    days: int = 0,
    source: str = '',
    status: str = 'neu',
    match_status: str = '',
    sort: str = 'date_desc',
    limit: int = 5000,
    refresh: bool = False,
    available_only: bool = True,
    auto_seed: bool = False,
) -> dict[str, Any]:
    from apps.abpe_shaduler.models import RadarConsultantItem

    fetched = 0
    persist_info: dict[str, Any] = {}
    seed_info: dict[str, Any] = {}

    # Leere Radar-Tabelle → einmal CRM-Seed (z. B. nach frischem Deploy)
    if auto_seed and not RadarConsultantItem.objects.filter(deleted_at__isnull=True).exists():
        seed_info = sync_crm_index(limit=0, reindex=True)
        persist_info['auto_seed'] = seed_info

    if refresh:
        # Manueller Refresh = CRM→Radar→ES Sync (nicht Gulp-Login-Liste)
        persist_info['crm_sync'] = sync_crm_index(limit=0, reindex=True)

    # ES first — Liste direkt aus Hits (ohne DB-Hydrate)
    # verfügbar/neu → status=neu; alle sichtbaren → status=all
    if available_only and (not status or status == 'neu'):
        status = 'neu'
    elif not available_only and status == 'neu':
        status = 'all'

    list_source = 'db'
    results: list[dict] = []
    by_src: dict = {}
    es_total = None
    es_info: dict[str, Any] = {}
    try:
        es_info = berater_index.index_stats(sample=False)
    except Exception:
        es_info = {}
    try:
        es_pack = berater_index.search(
            q=q,
            days=days if days > 0 else None,
            source=source,
            status=status if status != 'all' else None,
            match_status=match_status or None,
            sort=sort,
            limit=limit,
            include_deleted=False,
        )
    except Exception as exc:
        log.warning('berater ES search error: %s', exc)
        es_pack = None
        es_info['search_error'] = str(exc)[:400]

    es_doc_count = es_info.get('count')
    if not isinstance(es_doc_count, int):
        es_doc_count = None

    if es_pack is not None and es_pack.get('hits') is not None and not es_pack.get('error'):
        hits = es_pack.get('hits') or []
        list_source = 'elasticsearch'
        by_src = es_pack.get('by_source') or {}
        es_total = es_pack.get('total')
        results = [serialize_list_hit(h) for h in hits]
        index_empty = (
            es_pack.get('index_missing')
            or (es_doc_count == 0)
            or (
                not results
                and not q
                and (es_total is None or es_total == 0)
                and (es_doc_count is None or es_doc_count == 0)
            )
        )
        # Index hat Docs, Filter (status/source) trifft 0 → DB-Fallback
        # (verhindert leere Liste bei Mapping-/Feld-Mismatch)
        filter_miss = (
            not results
            and not q
            and (es_total == 0 or es_total is None)
            and isinstance(es_doc_count, int)
            and es_doc_count > 0
        )
        if index_empty and not q:
            if RadarConsultantItem.objects.filter(deleted_at__isnull=True).exists():
                list_source = 'db'
                by_src = {}
                es_total = es_doc_count
                es_info['fallback'] = 'empty_index'
        elif filter_miss:
            list_source = 'db'
            by_src = {}
            es_info['fallback'] = 'filter_miss'
            es_info['es_filter_total'] = es_total
            es_total = es_doc_count
    else:
        if es_pack and es_pack.get('error'):
            es_info['search_error'] = es_pack.get('error')
            es_info['fallback'] = 'search_error'
        elif es_pack is None:
            es_info['fallback'] = 'es_unavailable'

    if list_source != 'elasticsearch':
        qs = (
            RadarConsultantItem.objects
            .select_related('quelle')
            .filter(deleted_at__isnull=True)
            .exclude(status='geloescht')
        )
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
        results = [serialize_berater(o, detail=False) for o in rows]
        list_source = 'db'
        agg = (
            RadarConsultantItem.objects
            .filter(quelle__name__in=BERATER_SOURCES, deleted_at__isnull=True)
            .exclude(status='geloescht')
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
        'es_info': es_info,
        'fetched': fetched if refresh else None,
        'persist': persist_info,
        'seed': seed_info or None,
        'gulp_session': gulp.has_gulp_session(),
        'fl_session': fl.has_fl_session(),
        'available_only': available_only,
    }


def paste_berater(text: str) -> dict[str, Any]:
    """Gulp-ID/URL oder Freelancermap-Profil-URL/Slug/ID → Radar (+ CRM-Match)."""
    s = (text or '').strip()
    if not s:
        return {'ok': False, 'error': 'Keine Gulp- oder Freelancermap-URL/ID erkannt'}

    # Freelancermap zuerst, wenn URL/Slug klar FM ist (sonst Gulp-Zahlen-ID)
    fm_ref = fl.parse_fm_ref(s)
    looks_fm = bool(
        fm_ref
        and (
            'freelancermap' in s.lower()
            or '/profil/' in s.lower()
            or fm_ref.get('fm_slug')
        )
    )
    gid = gulp.parse_gulp_id(s)

    if looks_fm or (fm_ref and not gid):
        packed = fl.fetch_profile(
            slug=fm_ref.get('fm_slug') or '',
            fm_id=fm_ref.get('fm_id') or '',
        )
        hit = packed.get('item') if isinstance(packed.get('item'), dict) else {}
        fid = str(hit.get('fm_id') or fm_ref.get('fm_id') or '').strip()
        slug = str(hit.get('fm_slug') or fm_ref.get('fm_slug') or '').strip()
        if not fid and not slug:
            return {
                'ok': False,
                'error': packed.get('error') or 'Keine Freelancermap-ID erkannt',
                'fl_session': fl.has_fl_session(),
                'needs_auth': packed.get('needs_auth'),
            }
        item = {
            'fm_id': fid,
            'fm_slug': slug,
            'gulp_id': '',
            'name': hit.get('name') or (f'FM {fid}' if fid else 'Freelancermap'),
            'profil_url': hit.get('profil_url') or fl.profil_url_for(slug=slug, fm_id=fid),
            'kontakt_url': hit.get('kontakt_url') or fl.kontakt_url_for(slug=slug, fm_id=fid),
            'skills': hit.get('skills') or [],
            'ort': hit.get('ort') or '',
            'verfuegbar_ab': hit.get('verfuegbar_ab'),
            'satz': hit.get('satz'),
            'beschreibung': hit.get('beschreibung') or '',
            'cv_text': hit.get('cv_text') or '',
            'first_name': hit.get('first_name') or '',
            'last_name': hit.get('last_name') or '',
            'title': hit.get('title') or '',
            'source': SOURCE_NAME_FL,
            'source_name': SOURCE_NAME_FL,
            'eckdaten': {
                'availability_percent': hit.get('availability_percent'),
                'availability_code': hit.get('availability_code'),
                'anonym': hit.get('anonym'),
                'from_paste': True,
                'checked_at': timezone.now().isoformat(),
            },
        }
        obj = upsert_berater(item, apply_crm=True)
        return {
            'ok': True,
            'item': serialize_berater(obj),
            'fetched': bool(packed.get('ok')),
            'needs_auth': packed.get('needs_auth'),
            'fetch_error': packed.get('error') if not packed.get('ok') else None,
            'fl_session': fl.has_fl_session(),
            'source': SOURCE_NAME_FL,
        }

    if not gid:
        return {
            'ok': False,
            'error': 'Keine Gulp- oder Freelancermap-URL/ID erkannt',
        }
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
        'gulp_session': gulp.has_gulp_session(),
        'source': 'gulp',
    }


def _mark_gulp_gone(obj) -> dict[str, Any]:
    """Profil nicht mehr in Gulp — markieren, nicht CRM-löschen."""
    eck = dict(obj.eckdaten or {})
    eck['gulp_status'] = 'gone'
    eck['gulp_checked_at'] = timezone.now().isoformat()
    obj.eckdaten = eck
    log_rows = list(obj.auto_update_log or [])
    log_rows.append({
        'at': timezone.now().isoformat(),
        'action': 'gulp_gone',
        'gulp_id': obj.gulp_id,
    })
    obj.auto_update_log = log_rows[-50:]
    obj.save(update_fields=['eckdaten', 'auto_update_log', 'updated_at'])
    try:
        berater_index.index_one(obj)
    except Exception as exc:
        log.warning('ES index after gulp_gone: %s', exc)
    return {'action': 'gone', 'gulp_id': obj.gulp_id, 'id': str(obj.pk)}


def _mark_gulp_ok(obj, packed: dict) -> dict[str, Any]:
    """Profil gefunden → Verfügbarkeit/Satz/Ort updaten, gone-Flag löschen."""
    before = {
        'verfuegbar_ab': obj.verfuegbar_ab.isoformat() if obj.verfuegbar_ab else None,
        'satz': float(obj.satz) if obj.satz is not None else None,
        'ort': obj.ort or '',
        'gulp_status': (obj.eckdaten or {}).get('gulp_status'),
    }
    item = {
        'gulp_id': obj.gulp_id,
        'name': packed.get('name') or obj.name,
        'profil_url': packed.get('profil_url') or gulp.profil_url_for_gulp_id(obj.gulp_id),
        'skills': packed.get('skills') or [],
        'ort': packed.get('ort') or '',
        'verfuegbar_ab': packed.get('verfuegbar_ab'),
        'satz': packed.get('satz'),
        'beschreibung': packed.get('beschreibung') or '',
        'cv_text': packed.get('cv_text') or '',
        'first_name': packed.get('first_name') or '',
        'last_name': packed.get('last_name') or '',
        'source': 'gulp_refresh',
        'mongo_id': packed.get('mongo_id') or '',
    }
    obj = upsert_berater(item, apply_crm=False)
    eck = dict(obj.eckdaten or {})
    eck['gulp_status'] = 'ok'
    eck['gulp_checked_at'] = timezone.now().isoformat()
    changed = []
    after_v = obj.verfuegbar_ab.isoformat() if obj.verfuegbar_ab else None
    after_s = float(obj.satz) if obj.satz is not None else None
    if before['verfuegbar_ab'] != after_v:
        changed.append('verfuegbar_ab')
    if before['satz'] != after_s:
        changed.append('satz')
    if before['ort'] != (obj.ort or '') and (packed.get('ort') or ''):
        changed.append('ort')
    if before['gulp_status'] == 'gone':
        changed.append('gulp_status')
    eck['gulp_last_changes'] = changed
    obj.eckdaten = eck
    log_rows = list(obj.auto_update_log or [])
    log_rows.append({
        'at': timezone.now().isoformat(),
        'action': 'gulp_refresh',
        'gulp_id': obj.gulp_id,
        'changed': changed,
        'verfuegbar_ab': after_v,
        'satz': after_s,
    })
    obj.auto_update_log = log_rows[-50:]
    obj.save(update_fields=['eckdaten', 'auto_update_log', 'updated_at'])
    try:
        berater_index.index_one(obj)
    except Exception as exc:
        log.warning('ES index after gulp_refresh: %s', exc)
    return {
        'action': 'updated' if changed else 'unchanged',
        'gulp_id': obj.gulp_id,
        'id': str(obj.pk),
        'changed': changed,
        'verfuegbar_ab': after_v,
        'satz': after_s,
    }


def refresh_one_from_gulp(obj) -> dict[str, Any]:
    """Eine RadarConsultantItem-Zeile gegen Gulp prüfen."""
    gid = (obj.gulp_id or '').strip()
    if not gid:
        return {'action': 'skip', 'error': 'keine gulp_id', 'id': str(obj.pk)}
    eck = obj.eckdaten or {}
    mongo = str(eck.get('mongo_id') or eck.get('profileId') or '').strip()
    packed = gulp.fetch_expert_by_gulp_id(gid, mongo_id=mongo)
    if packed.get('needs_auth'):
        return {
            'action': 'auth',
            'error': packed.get('error') or 'Gulp-Session fehlt',
            'needs_auth': True,
            'gulp_id': gid,
            'id': str(obj.pk),
            'probe': packed.get('probe'),
        }
    if packed.get('not_found'):
        return _mark_gulp_gone(obj)
    if not packed.get('ok'):
        return {
            'action': 'error',
            'error': packed.get('error') or 'fetch failed',
            'gulp_id': gid,
            'id': str(obj.pk),
            'steps': packed.get('steps'),
        }
    # Mongo-ID merken für nächste Runde
    if packed.get('mongo_id'):
        eck = dict(obj.eckdaten or {})
        eck['mongo_id'] = packed['mongo_id']
        obj.eckdaten = eck
        obj.save(update_fields=['eckdaten', 'updated_at'])
    return _mark_gulp_ok(obj, packed)


def refresh_from_gulp(
    *,
    limit: int = 50,
    ids: Optional[list] = None,
    delay_s: float = 0.35,
) -> dict[str, Any]:
    """
    Batch: Existenz + Verfügbarkeit/Satz aus Gulp.
    Default limit=50 (Gulp nicht hammern). ids= optional UUID-Liste.
    """
    from apps.abpe_shaduler.models import RadarConsultantItem
    import uuid as _uuid

    if not gulp.has_gulp_session():
        return {
            'ok': False,
            'error': (
                'Gulp-Session fehlt — CV-Extractor Session erneuern '
                '(data/url/gu/.session_cookies.json) oder settings.json → '
                'shaduler.gulp_talentfinder'
            ),
            'needs_auth': True,
            'session': gulp.gulp_session_info(),
        }

    qs = (
        RadarConsultantItem.objects
        .filter(deleted_at__isnull=True)
        .exclude(status='geloescht')
        .exclude(gulp_id='')
        .order_by('-updated_at')
    )
    if ids:
        uuids = []
        for x in ids:
            try:
                uuids.append(_uuid.UUID(str(x)))
            except Exception:
                continue
        qs = qs.filter(pk__in=uuids)
    take = max(1, min(500, int(limit or 50)))
    rows = list(qs[:take])

    stats = {
        'ok': True,
        'scanned': 0,
        'updated': 0,
        'unchanged': 0,
        'gone': 0,
        'errors': 0,
        'auth_stop': False,
        'results': [],
        'limit': take,
        'gulp_session': True,
    }
    for i, obj in enumerate(rows):
        stats['scanned'] += 1
        try:
            res = refresh_one_from_gulp(obj)
        except Exception as exc:
            log.warning('gulp refresh %s: %s', obj.gulp_id, exc)
            res = {'action': 'error', 'error': str(exc)[:200], 'gulp_id': obj.gulp_id, 'id': str(obj.pk)}
        action = res.get('action')
        if action == 'auth':
            stats['auth_stop'] = True
            stats['needs_auth'] = True
            stats['ok'] = False
            stats['error'] = res.get('error')
            stats['results'].append(res)
            break
        if action == 'gone':
            stats['gone'] += 1
        elif action == 'updated':
            stats['updated'] += 1
        elif action == 'unchanged':
            stats['unchanged'] += 1
        else:
            stats['errors'] += 1
        if len(stats['results']) < 30:
            stats['results'].append(res)
        if delay_s and i + 1 < len(rows):
            time.sleep(max(0.0, float(delay_s)))

    return stats


def sync_available_from_gulp(
    *,
    limit: int = 40,
    pages: int = 2,
    page_size: int = 20,
    delay_s: float = 0.35,
    enrich: bool = True,
) -> dict[str, Any]:
    """
    Talentfinder „aktuell verfügbar“ einlesen.

    - bekannte Gulp-ID (Radar/CRM): Verfügbarkeit/Satz/Skills aktualisieren;
      CRM verfuegbar_ab_c mitziehen
    - unbekannte: neuer Radar-Eintrag mit möglichst reichem Profil
    """
    from apps.abpe_shaduler.models import RadarConsultantItem

    if not gulp.has_gulp_session():
        return {
            'ok': False,
            'error': (
                'Gulp-Session fehlt — CV-Extractor Session erneuern '
                '(data/url/gu/.session_cookies.json)'
            ),
            'needs_auth': True,
            'session': gulp.gulp_session_info(),
        }

    take = max(1, min(200, int(limit or 40)))
    pages = max(1, min(10, int(pages or 2)))
    page_size = max(5, min(50, int(page_size or 20)))

    stats = {
        'ok': True,
        'scanned': 0,
        'created': 0,
        'updated': 0,
        'crm_updated': 0,
        'skipped': 0,
        'errors': 0,
        'auth_stop': False,
        'results': [],
        'limit': take,
        'pages': pages,
        'tf_total': None,
        'gulp_session': True,
    }

    seen: set[str] = set()
    for page in range(pages):
        if stats['scanned'] >= take:
            break
        listed = gulp.fetch_experts_list(
            page=page,
            size=page_size,
            available_only=True,
        )
        if listed.get('needs_auth'):
            stats['ok'] = False
            stats['auth_stop'] = True
            stats['needs_auth'] = True
            stats['error'] = listed.get('error') or 'Gulp-Session ungültig'
            break
        if not listed.get('ok'):
            stats['ok'] = False
            stats['error'] = listed.get('error') or 'Suche fehlgeschlagen'
            stats['errors'] += 1
            break
        if stats['tf_total'] is None and listed.get('total') is not None:
            stats['tf_total'] = listed.get('total')

        hits = listed.get('results') or []
        if not hits:
            break

        for hit in hits:
            if stats['scanned'] >= take:
                break
            gid = str(hit.get('gulp_id') or '').strip()
            mid = str(hit.get('mongo_id') or '').strip()
            if gid and gid in seen:
                stats['skipped'] += 1
                continue

            packed = dict(hit)
            if enrich and (mid or gid):
                if delay_s:
                    time.sleep(max(0.0, float(delay_s)))
                detail = gulp.fetch_expert_by_gulp_id(gid or mid, mongo_id=mid)
                if detail.get('needs_auth'):
                    stats['ok'] = False
                    stats['auth_stop'] = True
                    stats['needs_auth'] = True
                    stats['error'] = detail.get('error') or 'Gulp-Session ungültig'
                    stats['results'].append({
                        'action': 'auth',
                        'gulp_id': gid,
                        'error': stats['error'],
                    })
                    return stats
                if detail.get('ok'):
                    for k, v in hit.items():
                        if k == 'raw':
                            continue
                        if detail.get(k) in (None, '', [], {}):
                            detail[k] = v
                    packed = detail
                    gid = str(packed.get('gulp_id') or gid or '').strip()
                    mid = str(packed.get('mongo_id') or mid or '').strip()

            if not gid:
                stats['skipped'] += 1
                continue
            if gid in seen:
                stats['skipped'] += 1
                continue
            seen.add(gid)

            stats['scanned'] += 1
            existed = (
                RadarConsultantItem.objects
                .filter(gulp_id=gid)
                .exists()
            )
            crm_before = find_crm_by_gulp_id(gid)
            before_v = None
            if crm_before and crm_before.get('verfuegbar_ab'):
                bv = crm_before['verfuegbar_ab']
                before_v = bv.isoformat() if hasattr(bv, 'isoformat') else str(bv)

            try:
                obj = upsert_berater({
                    'gulp_id': gid,
                    'name': packed.get('name') or gulp.placeholder_name(gid),
                    'profil_url': packed.get('profil_url') or gulp.profil_url_for_gulp_id(gid),
                    'skills': packed.get('skills') or [],
                    'ort': packed.get('ort') or '',
                    'verfuegbar_ab': packed.get('verfuegbar_ab'),
                    'satz': packed.get('satz'),
                    'beschreibung': packed.get('beschreibung') or '',
                    'cv_text': packed.get('cv_text') or '',
                    'first_name': packed.get('first_name') or '',
                    'last_name': packed.get('last_name') or '',
                    'source': 'gulp_available',
                    'mongo_id': mid or packed.get('mongo_id') or '',
                    'list_rank': stats['scanned'] - 1,
                    'from_available_sync': True,
                    'eckdaten': {
                        'availability_percent': packed.get('availability_percent'),
                        'remote': packed.get('remote'),
                        'gulp_status': 'ok',
                        'gulp_checked_at': timezone.now().isoformat(),
                        'from_available_sync': True,
                        'list_rank': stats['scanned'] - 1,
                    },
                }, apply_crm=True)
            except Exception as exc:
                log.warning('available sync %s: %s', gid, exc)
                stats['errors'] += 1
                if len(stats['results']) < 40:
                    stats['results'].append({
                        'action': 'error',
                        'gulp_id': gid,
                        'error': str(exc)[:200],
                    })
                continue

            action = 'created' if not existed else 'updated'
            if action == 'created':
                stats['created'] += 1
            else:
                stats['updated'] += 1

            crm_touched = False
            if obj.crm_contact_id and packed.get('verfuegbar_ab'):
                crm_after = find_crm_by_gulp_id(gid)
                after_v = None
                if crm_after and crm_after.get('verfuegbar_ab'):
                    av = crm_after['verfuegbar_ab']
                    after_v = av.isoformat() if hasattr(av, 'isoformat') else str(av)
                if after_v and after_v != before_v:
                    stats['crm_updated'] += 1
                    crm_touched = True
                elif after_v and not before_v:
                    stats['crm_updated'] += 1
                    crm_touched = True

            if len(stats['results']) < 40:
                stats['results'].append({
                    'action': action,
                    'gulp_id': gid,
                    'id': str(obj.pk),
                    'crm': bool(obj.crm_contact_id),
                    'crm_availability': crm_touched,
                    'verfuegbar_ab': packed.get('verfuegbar_ab'),
                    'satz': packed.get('satz'),
                    'name': (obj.name or '')[:80],
                    'skills_n': len(obj.skills or []),
                })

    return stats


def sync_available_from_fl(
    *,
    limit: int = 36,
    pages: int = 2,
    delay_s: float = 0.15,
) -> dict[str, Any]:
    """
    Freelancermap „verfügbare Freelancer“ einlesen (öffentliche Suche, Aktuellste).

    - bekannt (Radar/CRM via freelancermap_profil_c): aktualisieren
    - neu: Radar-Eintrag mit Titel/Skills/Projekten
    - list_rank setzt eingegangen_am → „Datum: neueste“ = FM-Listenreihenfolge
    """
    from apps.abpe_shaduler.models import RadarConsultantItem

    take = max(1, min(200, int(limit or 36)))
    pages = max(1, min(10, int(pages or 2)))

    sess = fl.fl_session_info()
    stats = {
        'ok': True,
        'scanned': 0,
        'created': 0,
        'updated': 0,
        'crm_updated': 0,
        'skipped': 0,
        'errors': 0,
        'results': [],
        'limit': take,
        'pages': pages,
        'fm_total': None,
        'source': 'freelancermap',
        'sort': 'aktuellste',
        'fl_session': bool(sess.get('ok')),
        'fl_session_info': {
            'ok': sess.get('ok'),
            'source': sess.get('source'),
            'path': sess.get('path'),
            'hint': sess.get('hint'),
            'cookie_names': sess.get('cookie_names') or [],
            'cookies_n': sess.get('cookies_n') or 0,
        },
        'rates_with_value': 0,
    }

    seen: set[str] = set()
    for page in range(1, pages + 1):
        if stats['scanned'] >= take:
            break
        listed = fl.fetch_freelancers_list(
            page=page, available_only=True, most_recent=True,
        )
        if not listed.get('ok'):
            stats['ok'] = False
            stats['error'] = listed.get('error') or 'FM Suche fehlgeschlagen'
            stats['errors'] += 1
            break
        if stats['fm_total'] is None and listed.get('total') is not None:
            stats['fm_total'] = listed.get('total')

        hits = listed.get('results') or []
        if not hits:
            break

        for hit in hits:
            if stats['scanned'] >= take:
                break
            fid = str(hit.get('fm_id') or '').strip()
            if not fid:
                stats['skipped'] += 1
                continue
            if fid in seen:
                stats['skipped'] += 1
                continue
            seen.add(fid)

            stats['scanned'] += 1
            existed = (
                RadarConsultantItem.objects
                .filter(dedup_hash=_dedup_fm(fid))
                .exists()
            )
            crm_before = find_crm_by_fm(
                fm_id=fid,
                slug=hit.get('fm_slug') or '',
                profil_url=hit.get('profil_url') or '',
            )
            before_v = None
            if crm_before and crm_before.get('verfuegbar_ab'):
                bv = crm_before['verfuegbar_ab']
                before_v = bv.isoformat() if hasattr(bv, 'isoformat') else str(bv)

            try:
                obj = upsert_berater({
                    **hit,
                    'source': 'freelancermap_available',
                    'source_name': SOURCE_NAME_FL,
                    'list_rank': stats['scanned'] - 1,
                    'from_available_sync': True,
                    'eckdaten': {
                        'availability_percent': hit.get('availability_percent'),
                        'availability_code': hit.get('availability_code'),
                        'anonym': hit.get('anonym'),
                        'from_available_sync': True,
                        'list_rank': stats['scanned'] - 1,
                        'checked_at': timezone.now().isoformat(),
                    },
                }, apply_crm=True)
            except Exception as exc:
                log.warning('FM available sync %s: %s', fid, exc)
                stats['errors'] += 1
                if len(stats['results']) < 40:
                    stats['results'].append({
                        'action': 'error',
                        'fm_id': fid,
                        'error': str(exc)[:200],
                    })
                continue

            action = 'created' if not existed else 'updated'
            if action == 'created':
                stats['created'] += 1
            else:
                stats['updated'] += 1

            crm_touched = False
            if obj.crm_contact_id:
                if not crm_before:
                    stats['crm_updated'] += 1
                    crm_touched = True
                elif hit.get('verfuegbar_ab'):
                    crm_after = find_crm_by_fm(
                        fm_id=fid,
                        slug=hit.get('fm_slug') or '',
                        profil_url=hit.get('profil_url') or '',
                    )
                    after_v = None
                    if crm_after and crm_after.get('verfuegbar_ab'):
                        av = crm_after['verfuegbar_ab']
                        after_v = av.isoformat() if hasattr(av, 'isoformat') else str(av)
                    if after_v and after_v != before_v:
                        stats['crm_updated'] += 1
                        crm_touched = True

            if delay_s:
                time.sleep(max(0.0, float(delay_s)))

            if hit.get('satz') is not None:
                stats['rates_with_value'] += 1

            if len(stats['results']) < 40:
                stats['results'].append({
                    'action': action,
                    'fm_id': fid,
                    'id': str(obj.pk),
                    'crm': bool(obj.crm_contact_id),
                    'crm_availability': crm_touched,
                    'verfuegbar_ab': hit.get('verfuegbar_ab'),
                    'satz': hit.get('satz'),
                    'name': (obj.name or '')[:80],
                    'skills_n': len(obj.skills or []),
                    'profil_url': hit.get('profil_url') or '',
                })

    if not stats.get('fl_session'):
        stats['hint'] = (
            (sess.get('hint') or '')
            + ' Ohne Session sind Stundensätze in der Suche oft leer.'
        ).strip()

    return stats


def seed_from_crm(*, limit: int = 0) -> dict[str, Any]:
    """Alias: CRM gulp_id → Radar + Soft-Delete fehlender + ES."""
    return sync_crm_index(limit=limit, reindex=True)


def sync_crm_index(
    *,
    limit: int = 0,
    reindex: bool = True,
    recreate_index: bool = False,
) -> dict[str, Any]:
    """
    Vollsync: alle CRM-Kontakte mit gulp_id_c → Radar.
    Fehlende gulp_ids in Radar → soft-delete (deleted_at + status geloescht).
    Optional ES-Reindex aktiver Einträge.
    """
    from apps.abpe_shaduler.models import RadarConsultantItem

    try:
        from apps.abpe_crm.models import CrmContact, CrmContactCstm
    except Exception as exc:
        return {'ok': False, 'error': f'CRM nicht verfügbar: {exc}'}

    try:
        crm_with_gulp = (
            CrmContactCstm.objects
            .exclude(gulp_id_c__isnull=True)
            .exclude(gulp_id_c='')
            .count()
        )
    except Exception as exc:
        return {'ok': False, 'error': f'CRM cstm query failed: {exc}', 'crm_with_gulp': 0}

    take = int(limit or 0)
    seen_gids: set[str] = set()
    try:
        qs = (
            CrmContact.objects
            .select_related('cstm')
            .exclude(cstm__gulp_id_c__isnull=True)
            .exclude(cstm__gulp_id_c='')
            .order_by('-crm_date_modified', '-id')
        )
        rows = list(qs[:take] if take > 0 else qs)
    except Exception as exc_orm:
        log.warning('sync ORM path failed (%s) — fallback Cstm', exc_orm)
        rows = []
        try:
            cstms = (
                CrmContactCstm.objects
                .select_related('contact')
                .exclude(gulp_id_c__isnull=True)
                .exclude(gulp_id_c='')
                .order_by('-id')
            )
            if take > 0:
                cstms = cstms[:take]
            for cstm in cstms:
                c = getattr(cstm, 'contact', None)
                if c is None:
                    continue
                c._seed_cstm = cstm
                rows.append(c)
        except Exception as exc2:
            return {
                'ok': False,
                'error': f'sync failed: {exc_orm} / {exc2}',
                'crm_with_gulp': crm_with_gulp,
            }

    n_ok = n_err = n_skip = 0
    for c in rows:
        cstm = getattr(c, '_seed_cstm', None) or getattr(c, 'cstm', None)
        gid = (getattr(cstm, 'gulp_id_c', '') or '').strip() if cstm else ''
        if not gid:
            n_skip += 1
            continue
        seen_gids.add(gid)
        profil = (getattr(cstm, 'gulp_profil_c', None) or '') if cstm else ''
        desc = (c.description or '') or profil
        kond = (getattr(cstm, 'konditionen_c', None) or '') if cstm else ''
        satz = None
        if kond:
            m = re.search(r'(\d+(?:[.,]\d+)?)', str(kond))
            if m:
                try:
                    satz = float(m.group(1).replace(',', '.'))
                except ValueError:
                    satz = None
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
                'satz': satz,
                'beschreibung': (desc or '')[:80000],
                'cv_text': (profil or desc or '')[:80000],
                'profil_url': gulp.profil_url_for_gulp_id(gid),
                'source': 'crm_sync',
                'skills': [],
            }, apply_crm=False)
            n_ok += 1
        except Exception as exc:
            log.warning('sync crm %s: %s', gid, exc)
            n_err += 1

    # Soft-Delete nur bei Vollsync (limit=0): gulp_id nicht mehr in CRM
    n_del = 0
    if take <= 0:
        active = (
            RadarConsultantItem.objects
            .filter(deleted_at__isnull=True)
            .exclude(gulp_id='')
            .exclude(status='geloescht')
        )
        for obj in active.iterator(chunk_size=500):
            gid = (obj.gulp_id or '').strip()
            if not gid or gid in seen_gids:
                continue
            obj.deleted_at = timezone.now()
            obj.status = RadarConsultantItem.Status.GELOESCHT
            log_rows = list(obj.auto_update_log or [])
            log_rows.append({
                'at': timezone.now().isoformat(),
                'action': 'crm_soft_delete',
                'gulp_id': gid,
            })
            obj.auto_update_log = log_rows[-50:]
            obj.save(update_fields=['deleted_at', 'status', 'auto_update_log', 'updated_at'])
            try:
                berater_index.index_one(obj)
            except Exception:
                berater_index.delete_one(obj.pk)
            n_del += 1

    reindex_info = None
    if reindex:
        reindex_info = berater_index.reindex_all(
            limit=0 if take <= 0 else max(take, n_ok + 100),
            active_only=True,
            recreate=recreate_index,
        )

    return {
        'ok': True,
        'seeded': n_ok,
        'errors': n_err,
        'skipped': n_skip,
        'deleted': n_del,
        'crm_with_gulp': crm_with_gulp,
        'scanned': len(rows),
        'limit': take,
        'reindex': reindex_info,
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
    return {'ok': True, 'item': serialize_berater(obj, detail=False)}
