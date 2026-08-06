"""
Radar-Berater Elasticsearch-Index (abpe_radar_berater).

Liste/Suche → ES (leicht). Detail → DB.

Hinweis: ES-Client-API wie Radar-Anfragen (body=), damit ES7 + ES8 funktionieren.
"""
from __future__ import annotations

import logging
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
            'crm_contact_id': {'type': 'keyword'},
            'source': {'type': 'keyword'},
            'status': {'type': 'keyword'},
            'match_status': {'type': 'keyword'},
            'st': {'type': 'keyword'},
            'meta': {'type': 'keyword', 'index': False},
            'note': {'type': 'keyword', 'index': False},
            'profil_url': {'type': 'keyword', 'index': False},
            'verfuegbar_ab': {'type': 'date', 'ignore_malformed': True},
            'satz': {'type': 'float', 'ignore_malformed': True},
            'eingegangen_am': {'type': 'date', 'ignore_malformed': True},
            'updated_at': {'type': 'date', 'ignore_malformed': True},
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
    try:
        return es.search(index=index, body=body)
    except TypeError:
        # ES8: body aufgelöst in query/size/…
        kwargs = {k: v for k, v in body.items() if k in (
            'query', 'size', 'from', 'sort', 'aggs', 'aggregations', '_source',
            'track_total_hits',
        )}
        return es.search(index=index, **kwargs)


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
    es = es or get_es()
    if not es:
        return False
    name = index_name()
    try:
        exists = es.indices.exists(index=name)
        if exists and recreate:
            try:
                es.indices.delete(index=name, ignore=[404])
            except TypeError:
                es.indices.delete(index=name, ignore_unavailable=True)
            exists = False
        if not exists:
            _es_create_index(es, name)
            log.info('created berater index %s', name)
        return True
    except Exception as exc:
        try:
            if es.indices.exists(index=name):
                return True
        except Exception:
            pass
        log.warning('ensure berater index failed: %s', exc)
        return False


def index_stats(es=None) -> dict[str, Any]:
    """Diagnose: Hosts, Indexname, Doc-Count."""
    hosts = _es_hosts()
    name = index_name()
    out: dict[str, Any] = {
        'hosts': hosts,
        'index': name,
        'ok': False,
        'exists': False,
        'count': None,
        'error': None,
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
    return ' · '.join(x for x in [
        f'Gulp {obj.gulp_id}' if obj.gulp_id else '',
        obj.ort or '',
        f'ab {obj.verfuegbar_ab.isoformat()}' if obj.verfuegbar_ab else '',
        f'{obj.satz} €' if obj.satz is not None else '',
    ] if x)


def _list_note(obj) -> str:
    if getattr(obj, 'deleted_at', None):
        return 'gelöscht (CRM)'
    if obj.match_status == 'bekannt':
        cid = obj.crm_contact_id or ''
        return '✔ CRM ' + (cid[:8] + '…' if cid else '')
    if (obj.name or '').startswith('Gulp '):
        return 'Platzhalter — optional in CRM anlegen'
    return 'neu / unbekannt'


def doc_from_obj(obj) -> dict[str, Any]:
    skills = obj.skills if isinstance(obj.skills, list) else []
    skills = [str(s).strip() for s in skills if str(s).strip()]
    st_map = {'bekannt': 'known', 'unsicher': 'maybe', 'unbekannt': 'new'}
    deleted = bool(getattr(obj, 'deleted_at', None)) or obj.status == 'geloescht'
    doc = {
        'name': obj.name or '',
        # Volltext für Suche (gekürzt), nicht für Listen-Payload nötig
        'beschreibung': (obj.beschreibung or '')[:12000],
        'skills': skills,
        'skills_text': ' '.join(skills),
        'ort': obj.ort or '',
        'gulp_id': obj.gulp_id or '',
        'crm_contact_id': obj.crm_contact_id or '',
        'source': (obj.quelle.name if getattr(obj, 'quelle_id', None) else 'gulp'),
        'status': obj.status or 'neu',
        'match_status': obj.match_status or 'unbekannt',
        'st': st_map.get(obj.match_status, 'new'),
        'meta': _list_meta(obj)[:512],
        'note': _list_note(obj)[:512],
        'profil_url': obj.profil_url or '',
        'verfuegbar_ab': _iso(obj.verfuegbar_ab),
        'satz': float(obj.satz) if obj.satz is not None else None,
        'eingegangen_am': _iso(obj.eingegangen_am) or _iso(obj.created_at),
        'updated_at': _iso(obj.updated_at),
        'deleted': deleted,
        'cv_versions': len(obj.cv_versions or []),
    }
    # None-Werte raus — manchen ES-Versionen unangenehm bei date/float
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
        filters.append({'term': {'status': status}})
    if match_status:
        filters.append({'term': {'match_status': match_status}})
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
                'fields': ['name^3', 'skills_text^2', 'beschreibung', 'ort', 'gulp_id^4'],
                'type': 'best_fields',
                'operator': 'and',
            }
        })
    else:
        must.append({'match_all': {}})
    order = 'asc' if sort in ('date_asc', 'asc', 'oldest') else 'desc'
    body = {
        'size': max(1, min(10000, int(limit))),
        'track_total_hits': True,
        '_source': [
            'name', 'gulp_id', 'ort', 'source', 'status', 'match_status', 'st',
            'meta', 'note', 'verfuegbar_ab', 'satz', 'crm_contact_id',
            'eingegangen_am', 'updated_at', 'cv_versions', 'deleted', 'skills',
        ],
        'query': {'bool': {'must': must, 'filter': filters}},
        'sort': [
            {'eingegangen_am': {'order': order, 'unmapped_type': 'date', 'missing': '_last'}},
            {'updated_at': {'order': order, 'unmapped_type': 'date', 'missing': '_last'}},
            {'_id': 'asc'},
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
    from apps.abpe_shaduler.models import RadarConsultantItem
    es = get_es()
    stats_before = index_stats(es)
    if not es or not ensure_index(es, recreate=recreate):
        return {
            'ok': False,
            'error': 'ES unavailable',
            'stats': stats_before,
        }
    qs = RadarConsultantItem.objects.select_related('quelle').all()
    if active_only:
        qs = qs.filter(deleted_at__isnull=True).exclude(status='geloescht')
    if limit and limit > 0:
        rows = list(qs[:limit])
    else:
        rows = list(qs.iterator(chunk_size=500))

    name = index_name()
    n = 0
    errors = 0
    sample_err = None

    # Bulk wenn helpers verfügbar
    try:
        from elasticsearch.helpers import bulk
        actions = [
            {
                '_op_type': 'index',
                '_index': name,
                '_id': str(obj.pk),
                '_source': doc_from_obj(obj),
            }
            for obj in rows
        ]
        # chunked
        chunk = 400
        for i in range(0, len(actions), chunk):
            part = actions[i:i + chunk]
            ok_count, errs = bulk(es, part, raise_on_error=False, refresh=False)
            n += int(ok_count or 0)
            if isinstance(errs, list) and errs:
                errors += len(errs)
                if sample_err is None and errs:
                    sample_err = str(errs[0])[:300]
            elif errs:
                errors += 1
    except Exception as exc_bulk:
        log.warning('berater bulk failed (%s) — fallback single', exc_bulk)
        n = 0
        errors = 0
        for obj in rows:
            if index_one(obj, es=es, refresh=False):
                n += 1
            else:
                errors += 1
                if sample_err is None:
                    sample_err = 'index_one failed'

    try:
        es.indices.refresh(index=name)
    except Exception as exc:
        log.warning('berater refresh failed: %s', exc)

    stats_after = index_stats(es)
    return {
        'ok': errors == 0 and n > 0,
        'indexed': n,
        'errors': errors,
        'scanned': len(rows),
        'index': name,
        'sample_error': sample_err,
        'stats_before': stats_before,
        'stats_after': stats_after,
    }
