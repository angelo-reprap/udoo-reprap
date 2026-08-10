"""
Radar-Berater Elasticsearch-Index (abpe_radar_berater).

Liste/Suche → ES (leicht). Detail → DB.

Hinweis: ES-Client-API wie Radar-Anfragen (body=), damit ES7 + ES8 funktionieren.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Optional

from django.conf import settings

log = logging.getLogger('abpe_shaduler.radar_berater_index')

BERATER_INDEX_MAPPING = {
    'settings': {
        'number_of_shards': 1,
        'number_of_replicas': 0,
        'analysis': {
            'analyzer': {
                'de_text': {
                    'type': 'custom',
                    'tokenizer': 'standard',
                    'filter': ['lowercase', 'asciifolding'],
                }
            }
        },
    },
    'mappings': {
        'properties': {
            'name': {'type': 'text', 'analyzer': 'de_text',
                     'fields': {'keyword': {'type': 'keyword', 'ignore_above': 320}}},
            'beschreibung': {'type': 'text', 'analyzer': 'de_text'},
            'skills': {'type': 'keyword'},
            'skills_text': {'type': 'text', 'analyzer': 'de_text'},
            'ort': {'type': 'keyword'},
            'gulp_id': {'type': 'keyword'},
            'fm_id': {'type': 'keyword'},
            'fm_slug': {'type': 'keyword'},
            'mongo_id': {'type': 'keyword'},
            'crm_contact_id': {'type': 'keyword'},
            'source': {'type': 'keyword'},
            'status': {'type': 'keyword'},
            'match_status': {'type': 'keyword'},
            'st': {'type': 'keyword'},
            'meta': {'type': 'keyword', 'index': False},
            'note': {'type': 'keyword', 'index': False},
            'profil_url': {'type': 'keyword', 'index': False},
            'kontakt_url': {'type': 'keyword', 'index': False},
            'verfuegbar_ab': {'type': 'date'},
            'satz': {'type': 'float'},
            'eingegangen_am': {'type': 'date'},
            'updated_at': {'type': 'date'},
            'deleted': {'type': 'boolean'},
            'cv_versions': {'type': 'integer'},
        }
    },
}


def _es_hosts() -> list[str]:
    try:
        from .inbox_service import _es_hosts as inbox_hosts
        return inbox_hosts()
    except Exception:
        hosts = getattr(settings, 'ELASTICSEARCH_HOSTS', None) or ['http://localhost:9200']
        if isinstance(hosts, str):
            hosts = [hosts]
        out = []
        for h in hosts:
            h = str(h).strip()
            if h and '://' not in h:
                h = f'http://{h}'
            if h:
                out.append(h)
        return out or ['http://localhost:9200']


def _load_json_settings() -> dict:
    try:
        path = getattr(settings, 'ABPE_SETTINGS_PATH', None) or '/opt/abpe/backend/settings.json'
        import json
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def index_name() -> str:
    cfg = _load_json_settings()
    return (
        (cfg.get('shaduler') or {}).get('es_radar_berater_index')
        or (cfg.get('elasticsearch') or {}).get('radar_berater_index')
        or getattr(settings, 'SHADULER_ES_RADAR_BERATER_INDEX', None)
        or 'abpe_radar_berater'
    )


def get_es():
    try:
        from elasticsearch import Elasticsearch
    except ImportError:
        log.info('elasticsearch-Paket fehlt — Berater-Index Skip')
        return None
    try:
        return Elasticsearch(_es_hosts(), verify_certs=False)
    except TypeError:
        # ältere Client-Version ohne verify_certs
        try:
            return Elasticsearch(_es_hosts())
        except Exception as exc:
            log.warning('ES Client fehlgeschlagen: %s', exc)
            return None
    except Exception as exc:
        log.warning('ES Client fehlgeschlagen: %s', exc)
        return None


def _es_index(es, *, index: str, id: str, doc: dict, refresh: bool = False) -> None:
    """ES7 (body=) und ES8 (document=) kompatibel indexieren."""
    try:
        es.index(index=index, id=id, body=doc, refresh=refresh)
    except TypeError:
        es.index(index=index, id=id, document=doc, refresh=refresh)


def _es_search(es, *, index: str, body: dict):
    """ES8 zuerst (kwargs), ES7-Fallback (body=)."""
    kwargs = {k: v for k, v in body.items() if k in (
        'query', 'size', 'from_', 'from', 'sort', 'aggs', 'aggregations',
        '_source', 'track_total_hits',
    )}
    # 'from' ist Keyword in Python — Client akzeptiert from_
    if 'from' in kwargs and 'from_' not in kwargs:
        kwargs['from_'] = kwargs.pop('from')
    try:
        return es.search(index=index, **kwargs)
    except TypeError:
        return es.search(index=index, body=body)


def _es_create_index(es, name: str) -> None:
    try:
        es.indices.create(index=name, body=BERATER_INDEX_MAPPING)
    except TypeError:
        es.indices.create(
            index=name,
            settings=BERATER_INDEX_MAPPING.get('settings'),
            mappings=BERATER_INDEX_MAPPING.get('mappings'),
        )


def ensure_index(es=None, *, recreate: bool = False) -> bool:
    """
    Index sicherstellen.
    recreate=True legt Mapping neu an — OHNE den Live-Index vorher zu löschen
    (sonst ist die UI minutenlang ohne ES). Stattdessen: temp-Index + Alias-Swap
    erfolgt in reindex_all(); hier nur create-if-missing.
    """
    es = es or get_es()
    if not es:
        return False
    name = index_name()
    try:
        exists = bool(es.indices.exists(index=name))
        if not exists:
            _es_create_index(es, name)
            log.info('created berater index %s', name)
        elif recreate:
            # Mapping-Drift: nur loggen — echter Neuaufbau in reindex_all via temp
            log.info('berater index %s exists — recreate via temp index in reindex_all', name)
        return True
    except Exception as exc:
        try:
            if es.indices.exists(index=name):
                return True
        except Exception:
            pass
        log.warning('ensure berater index failed: %s', exc)
        return False


def _delete_index_quiet(es, name: str) -> None:
    try:
        es.indices.delete(index=name, ignore=[404])
    except TypeError:
        try:
            es.indices.delete(index=name, ignore_unavailable=True)
        except Exception:
            pass
    except Exception:
        pass


def _bulk_index(es, name: str, rows, *, chunk: int = 200) -> tuple[int, int, Optional[str]]:
    """Bulk-index rows → (indexed, errors, sample_error). Progress via log."""
    n = 0
    errors = 0
    sample_err = None
    total = len(rows)
    try:
        from elasticsearch.helpers import bulk
    except ImportError:
        for i, obj in enumerate(rows, 1):
            if index_one(obj, es=es, refresh=False):
                n += 1
            else:
                errors += 1
                if sample_err is None:
                    sample_err = 'index_one failed'
            if i % 500 == 0 or i == total:
                log.info('berater reindex progress %s/%s (single)', i, total)
        return n, errors, sample_err

    actions = []
    for obj in rows:
        actions.append({
            '_op_type': 'index',
            '_index': name,
            '_id': str(obj.pk),
            '_source': doc_from_obj(obj),
        })
    for i in range(0, len(actions), chunk):
        part = actions[i:i + chunk]
        try:
            ok_count, errs = bulk(es, part, raise_on_error=False, refresh=False)
            n += int(ok_count or 0)
            if isinstance(errs, list) and errs:
                errors += len(errs)
                if sample_err is None and errs:
                    sample_err = str(errs[0])[:300]
            elif errs:
                errors += 1
        except Exception as exc:
            log.warning('berater bulk chunk failed: %s — single fallback', exc)
            for action in part:
                try:
                    _es_index(
                        es,
                        index=name,
                        id=action['_id'],
                        doc=action['_source'],
                        refresh=False,
                    )
                    n += 1
                except Exception as exc2:
                    errors += 1
                    if sample_err is None:
                        sample_err = str(exc2)[:300]
        done = min(i + chunk, len(actions))
        if done % 400 == 0 or done == len(actions):
            log.info('berater reindex progress %s/%s', done, total)
            print(f'  … indexed {done}/{total}', flush=True)
    return n, errors, sample_err


def index_stats(es=None, *, sample: bool = True) -> dict[str, Any]:
    """Diagnose: Hosts, Indexname, Doc-Count, optional Sample + Status/Source-Aggs."""
    hosts = _es_hosts()
    name = index_name()
    out: dict[str, Any] = {
        'hosts': hosts,
        'index': name,
        'ok': False,
        'exists': False,
        'count': None,
        'error': None,
        'sample': None,
        'by_status': {},
        'by_source': {},
        'by_deleted': {},
    }
    es = es or get_es()
    if not es:
        out['error'] = 'no_es_client'
        return out
    try:
        out['exists'] = bool(es.indices.exists(index=name))
        if out['exists']:
            res = es.count(index=name)
            out['count'] = res.get('count') if isinstance(res, dict) else getattr(res, 'count', None)
            if sample:
                try:
                    body = {
                        'size': 1,
                        'query': {'match_all': {}},
                        'aggs': {
                            'by_status': {'terms': {'field': 'status', 'size': 20}},
                            'by_source': {'terms': {'field': 'source', 'size': 20}},
                            'by_deleted': {'terms': {'field': 'deleted', 'size': 5}},
                        },
                    }
                    sres = _es_search(es, index=name, body=body)
                    hits = (sres.get('hits') or {}).get('hits') or []
                    if hits:
                        src = dict(hits[0].get('_source') or {})
                        src['_id'] = hits[0].get('_id')
                        # kurz halten
                        if 'beschreibung' in src:
                            src['beschreibung'] = str(src.get('beschreibung') or '')[:120]
                        out['sample'] = src
                    aggs = sres.get('aggregations') or {}
                    for key in ('by_status', 'by_source', 'by_deleted'):
                        buckets = (aggs.get(key) or {}).get('buckets') or []
                        out[key] = {str(b.get('key')): b.get('doc_count') for b in buckets}
                except Exception as exc_s:
                    out['sample_error'] = str(exc_s)[:300]
        out['ok'] = True
    except Exception as exc:
        out['error'] = str(exc)[:400]
    return out


def _iso(val) -> Optional[str]:
    if val is None or val == '':
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    from datetime import date
    if isinstance(val, date):
        return val.isoformat()
    s = str(val).strip()
    if not s:
        return None
    # nur ISO-ähnlich in date-Felder — kaputte Strings → None
    if len(s) >= 10 and s[0:4].isdigit() and s[4] in '-/':
        return s.replace('/', '-')
    return None


def _list_meta(obj) -> str:
    eck = obj.eckdaten or {}
    fm_id = str(eck.get('fm_id') or '').strip()
    id_meta = (
        f'Gulp {obj.gulp_id}' if obj.gulp_id
        else (f'FM {fm_id}' if fm_id else '')
    )
    return ' · '.join(x for x in [
        id_meta,
        obj.ort or '',
        f'ab {obj.verfuegbar_ab.isoformat()}' if obj.verfuegbar_ab else '',
        f'{obj.satz} €' if obj.satz is not None else '',
    ] if x)


def _list_note(obj) -> str:
    if getattr(obj, 'deleted_at', None):
        return 'gelöscht (CRM)'
    eck = obj.eckdaten or {}
    if eck.get('gulp_status') == 'gone':
        return 'nicht mehr in Gulp'
    if obj.match_status == 'bekannt':
        cid = obj.crm_contact_id or ''
        return '✔ CRM ' + (cid[:8] + '…' if cid else '')
    if (obj.name or '').startswith(('Gulp ', 'FM ')):
        return 'Platzhalter — optional in CRM anlegen'
    return 'neu / unbekannt'


def _kontakt_url_for_obj(obj) -> str:
    eck = obj.eckdaten or {}
    mongo = str(eck.get('mongo_id') or '').strip()
    fm_id = str(eck.get('fm_id') or '').strip()
    fm_slug = str(eck.get('fm_slug') or '').strip()
    src = (
        (obj.quelle.name if getattr(obj, 'quelle_id', None) else '') or ''
    ).strip().lower()
    if src == 'freelancermap' or (fm_id and not obj.gulp_id):
        if fm_slug:
            return f'https://www.freelancermap.de/profil/{fm_slug}'
        if fm_id:
            return f'https://www.freelancermap.de/freelancer?id={fm_id}'
        return obj.profil_url or ''
    if re.fullmatch(r'[a-f0-9]{24}', mongo, re.I):
        return f'https://www.gulp.de/talentfinder/app/experten/{mongo}/kontaktieren'
    return ''


def doc_from_obj(obj) -> dict[str, Any]:
    skills = obj.skills if isinstance(obj.skills, list) else []
    skills = [str(s).strip() for s in skills if str(s).strip()]
    st_map = {'bekannt': 'known', 'unsicher': 'maybe', 'unbekannt': 'new'}
    deleted = bool(getattr(obj, 'deleted_at', None)) or obj.status == 'geloescht'
    eck = obj.eckdaten or {}
    fm_id = str(eck.get('fm_id') or '').strip()
    fm_slug = str(eck.get('fm_slug') or '').strip()
    src = (
        (obj.quelle.name if getattr(obj, 'quelle_id', None) else 'gulp') or 'gulp'
    ).strip().lower()
    doc = {
        'name': obj.name or '',
        # Volltext für ES-Suche (Liste lädt beschreibung nicht; Detail kommt aus DB)
        'beschreibung': obj.beschreibung or '',
        'skills': skills,
        'skills_text': ' '.join(skills),
        'ort': obj.ort or '',
        'gulp_id': obj.gulp_id or '',
        'fm_id': fm_id,
        'fm_slug': fm_slug,
        'mongo_id': str(eck.get('mongo_id') or ''),
        'crm_contact_id': obj.crm_contact_id or '',
        'source': src,
        'status': str(obj.status or 'neu').strip().lower() or 'neu',
        'match_status': str(obj.match_status or 'unbekannt').strip().lower() or 'unbekannt',
        'st': st_map.get(obj.match_status, 'new'),
        'meta': _list_meta(obj)[:512],
        'note': _list_note(obj)[:512],
        'profil_url': obj.profil_url or '',
        'kontakt_url': _kontakt_url_for_obj(obj),
        'verfuegbar_ab': _iso(obj.verfuegbar_ab),
        'satz': float(obj.satz) if obj.satz is not None else None,
        'eingegangen_am': _iso(obj.eingegangen_am) or _iso(obj.created_at),
        'updated_at': _iso(obj.updated_at),
        'deleted': bool(deleted),
        'cv_versions': len(obj.cv_versions or []),
    }
    # None-Werte raus — manchen ES-Versionen unangenehm bei date/float
    # (deleted=False und cv_versions=0 bleiben erhalten)
    return {k: v for k, v in doc.items() if v is not None}


def index_one(obj, *, es=None, refresh: bool = False) -> bool:
    es = es or get_es()
    if not es or not ensure_index(es):
        return False
    try:
        _es_index(
            es,
            index=index_name(),
            id=str(obj.pk),
            doc=doc_from_obj(obj),
            refresh=refresh,
        )
        return True
    except Exception as exc:
        log.warning('index berater %s: %s', obj.pk, exc)
        return False


def delete_one(pk) -> bool:
    es = get_es()
    if not es:
        return False
    try:
        try:
            es.delete(index=index_name(), id=str(pk), ignore=[404])
        except TypeError:
            es.delete(index=index_name(), id=str(pk))
        return True
    except Exception as exc:
        log.warning('delete berater ES %s: %s', pk, exc)
        return False


def search(
    *,
    q: str = '',
    days: Optional[int] = None,
    source: str = '',
    status: Optional[str] = None,
    match_status: Optional[str] = None,
    sort: str = 'date_desc',
    limit: int = 5000,
    include_deleted: bool = False,
) -> Optional[dict[str, Any]]:
    es = get_es()
    if not es:
        return None
    name = index_name()
    try:
        if not es.indices.exists(index=name):
            log.info('berater index %s fehlt', name)
            return {
                'hits': [],
                'ids': [],
                'total': 0,
                'by_source': {},
                'source': 'elasticsearch',
                'index_missing': True,
                'error': f'index_missing:{name}',
            }
    except Exception as exc:
        log.warning('berater index exists check failed: %s', exc)
        return None

    filters: list[dict] = []
    if not include_deleted:
        # Nur boolean false — term 0 auf boolean-Feld kann unter ES8 die Query killen
        filters.append({
            'bool': {
                'should': [
                    {'term': {'deleted': False}},
                    {'bool': {'must_not': {'exists': {'field': 'deleted'}}}},
                ],
                'minimum_should_match': 1,
            }
        })
    if status and status != 'all':
        filters.append({'term': {'status': str(status).strip().lower()}})
    if match_status:
        filters.append({'term': {'match_status': str(match_status).strip().lower()}})
    if source:
        filters.append({'term': {'source': source.strip().lower()}})
    if days is not None and int(days) > 0:
        d = max(1, min(365, int(days)))
        filters.append({
            'bool': {
                'should': [
                    {'range': {'eingegangen_am': {'gte': f'now-{d}d/d', 'lte': 'now+1d'}}},
                    {'range': {'updated_at': {'gte': f'now-{d}d/d', 'lte': 'now+1d'}}},
                ],
                'minimum_should_match': 1,
            }
        })
    q = (q or '').strip()
    must: list[dict] = []
    if q:
        must.append({
            'multi_match': {
                'query': q,
                'fields': [
                    'name^3', 'skills_text^2', 'beschreibung', 'ort',
                    'gulp_id^4', 'fm_id^4',
                ],
                'type': 'best_fields',
                'operator': 'and',
            }
        })
    else:
        must.append({'match_all': {}})
    order = 'asc' if sort in ('date_asc', 'asc', 'oldest') else 'desc'
    # ES 8: Sortierung nach _id ist verboten → gulp_id/fm_id als Tiebreaker
    body = {
        'size': max(1, min(10000, int(limit))),
        'track_total_hits': True,
        '_source': [
            'name', 'gulp_id', 'fm_id', 'fm_slug', 'mongo_id', 'ort', 'source',
            'status', 'match_status', 'st', 'meta', 'note', 'verfuegbar_ab',
            'satz', 'crm_contact_id', 'eingegangen_am', 'updated_at',
            'cv_versions', 'deleted', 'skills', 'profil_url', 'kontakt_url',
        ],
        'query': {'bool': {'must': must, 'filter': filters}},
        'sort': [
            {'eingegangen_am': {'order': order, 'unmapped_type': 'date', 'missing': '_last'}},
            {'updated_at': {'order': order, 'unmapped_type': 'date', 'missing': '_last'}},
            {'gulp_id': {'order': 'asc', 'unmapped_type': 'keyword', 'missing': '_last'}},
            {'fm_id': {'order': 'asc', 'unmapped_type': 'keyword', 'missing': '_last'}},
        ],
        'aggs': {
            'by_source': {'terms': {'field': 'source', 'size': 20}},
        },
    }
    try:
        res = _es_search(es, index=name, body=body)
    except Exception as exc:
        log.warning('berater search failed: %s', exc)
        return {
            'hits': [],
            'ids': [],
            'total': 0,
            'by_source': {},
            'source': 'elasticsearch',
            'error': str(exc)[:400],
        }
    hits_raw = res.get('hits', {}).get('hits') or []
    hits = []
    for h in hits_raw:
        src = dict(h.get('_source') or {})
        src['id'] = h.get('_id')
        hits.append(src)
    total = res.get('hits', {}).get('total', {})
    if isinstance(total, dict):
        total_n = total.get('value')
    else:
        total_n = total
    buckets = (
        ((res.get('aggregations') or {}).get('by_source') or {}).get('buckets') or []
    )
    by_source = {b['key']: b['doc_count'] for b in buckets if b.get('key')}
    return {
        'hits': hits,
        'ids': [h['id'] for h in hits if h.get('id')],
        'total': total_n,
        'by_source': by_source,
        'source': 'elasticsearch',
    }


def reindex_all(
    *,
    limit: int = 50000,
    active_only: bool = True,
    recreate: bool = False,
) -> dict[str, Any]:
    """
    Reindex. recreate=True schreibt zuerst in Temp-Index; Live bleibt bis
    der Temp fertig ist, dann kurzer Swap (kein Delete-first).
    """
    from apps.abpe_shaduler.models import RadarConsultantItem
    es = get_es()
    stats_before = index_stats(es, sample=False)
    if not es or not ensure_index(es, recreate=False):
        return {
            'ok': False,
            'error': 'ES unavailable',
            'stats': stats_before,
        }
    qs = (
        RadarConsultantItem.objects
        .select_related('quelle')
        .only(
            'id', 'name', 'beschreibung', 'skills', 'ort', 'gulp_id',
            'crm_contact_id', 'status', 'match_status', 'profil_url',
            'verfuegbar_ab', 'satz', 'eingegangen_am', 'updated_at',
            'created_at', 'deleted_at', 'cv_versions', 'quelle_id',
            'quelle__name',
        )
    )
    if active_only:
        qs = qs.filter(deleted_at__isnull=True).exclude(status='geloescht')
    if limit and limit > 0:
        rows = list(qs[:limit])
    else:
        rows = list(qs.iterator(chunk_size=500))

    live = index_name()
    target = live
    temp = None
    if recreate:
        temp = f'{live}__rebuild'
        _delete_index_quiet(es, temp)
        try:
            _es_create_index(es, temp)
            target = temp
            print(f'  → rebuild into {temp} (live bleibt online)', flush=True)
        except Exception as exc:
            log.warning('temp index create failed (%s) — in-place', exc)
            temp = None
            target = live

    print(f'  → indexing {len(rows)} docs → {target} …', flush=True)
    n, errors, sample_err = _bulk_index(es, target, rows, chunk=200)

    try:
        es.indices.refresh(index=target)
    except Exception as exc:
        log.warning('berater refresh failed: %s', exc)

    if temp and target == temp:
        if n <= 0:
            _delete_index_quiet(es, temp)
            return {
                'ok': False,
                'error': 'temp index empty',
                'indexed': n,
                'errors': errors,
                'sample_error': sample_err,
                'stats_before': stats_before,
            }
        # Kurzer Swap erst wenn Temp voll: Live löschen, Temp→Live per reindex
        print(f'  → swap {temp} → {live} …', flush=True)
        try:
            _delete_index_quiet(es, live)
            _es_create_index(es, live)
            try:
                es.reindex(
                    body={
                        'source': {'index': temp},
                        'dest': {'index': live},
                    },
                    wait_for_completion=True,
                    request_timeout=900,
                )
            except TypeError:
                es.reindex(
                    source={'index': temp},
                    dest={'index': live},
                    wait_for_completion=True,
                )
            try:
                es.indices.refresh(index=live)
            except Exception:
                pass
            _delete_index_quiet(es, temp)
            print('  → swap ok', flush=True)
        except Exception as exc_swap:
            log.warning('swap failed: %s', exc_swap)
            # Temp behalten als Rettung
            return {
                'ok': False,
                'error': f'swap failed: {exc_swap}',
                'indexed': n,
                'errors': errors,
                'temp_index': temp,
                'hint': f'Index liegt in {temp} — manuell: POST /_reindex',
                'sample_error': sample_err,
                'stats_before': stats_before,
                'stats_after': index_stats(es, sample=False),
            }

    stats_after = index_stats(es, sample=True)
    return {
        'ok': errors == 0 and n > 0,
        'indexed': n,
        'errors': errors,
        'scanned': len(rows),
        'index': live,
        'recreate': bool(recreate),
        'sample_error': sample_err,
        'stats_before': stats_before,
        'stats_after': stats_after,
    }
