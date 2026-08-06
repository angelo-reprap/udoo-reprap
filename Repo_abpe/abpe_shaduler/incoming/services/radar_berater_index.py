"""
Radar-Berater Elasticsearch-Index (abpe_radar_berater).
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
            'profil_url': {'type': 'keyword', 'index': False},
            'verfuegbar_ab': {'type': 'date'},
            'satz': {'type': 'float'},
            'eingegangen_am': {'type': 'date'},
            'updated_at': {'type': 'date'},
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
    return Elasticsearch(_es_hosts(), verify_certs=False)


def ensure_index(es=None) -> bool:
    es = es or get_es()
    if not es:
        return False
    name = index_name()
    try:
        if not es.indices.exists(index=name):
            es.indices.create(index=name, body=BERATER_INDEX_MAPPING)
            log.info('created berater index %s', name)
        return True
    except Exception as exc:
        log.warning('ensure berater index failed: %s', exc)
        return False


def _iso(val) -> Optional[str]:
    if val is None or val == '':
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    from datetime import date
    if isinstance(val, date):
        return val.isoformat()
    return str(val)


def doc_from_obj(obj) -> dict[str, Any]:
    skills = obj.skills if isinstance(obj.skills, list) else []
    skills = [str(s).strip() for s in skills if str(s).strip()]
    return {
        'name': obj.name or '',
        'beschreibung': obj.beschreibung or '',
        'skills': skills,
        'skills_text': ' '.join(skills),
        'ort': obj.ort or '',
        'gulp_id': obj.gulp_id or '',
        'crm_contact_id': obj.crm_contact_id or '',
        'source': (obj.quelle.name if getattr(obj, 'quelle_id', None) else 'gulp'),
        'status': obj.status or 'neu',
        'match_status': obj.match_status or 'unbekannt',
        'profil_url': obj.profil_url or '',
        'verfuegbar_ab': _iso(obj.verfuegbar_ab),
        'satz': float(obj.satz) if obj.satz is not None else None,
        'eingegangen_am': _iso(obj.eingegangen_am) or _iso(obj.created_at),
        'updated_at': _iso(obj.updated_at),
    }


def index_one(obj) -> bool:
    es = get_es()
    if not es or not ensure_index(es):
        return False
    try:
        es.index(index=index_name(), id=str(obj.pk), document=doc_from_obj(obj))
        return True
    except Exception as exc:
        log.warning('index berater %s: %s', obj.pk, exc)
        return False


def search(
    *,
    q: str = '',
    days: Optional[int] = None,
    source: str = '',
    status: Optional[str] = None,
    match_status: Optional[str] = None,
    sort: str = 'date_desc',
    limit: int = 300,
) -> Optional[dict[str, Any]]:
    es = get_es()
    if not es or not ensure_index(es):
        return None
    filters: list[dict] = []
    if status:
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
        res = es.search(index=index_name(), body=body)
    except Exception as exc:
        log.warning('berater search failed: %s', exc)
        return None
    hits = res.get('hits', {}).get('hits') or []
    ids = [h.get('_id') for h in hits if h.get('_id')]
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
        'ids': ids,
        'total': total_n,
        'by_source': by_source,
        'source': 'elasticsearch',
    }


def reindex_all(*, limit: int = 5000) -> dict[str, Any]:
    from apps.abpe_shaduler.models import RadarConsultantItem
    es = get_es()
    if not es or not ensure_index(es):
        return {'ok': False, 'error': 'ES unavailable'}
    qs = RadarConsultantItem.objects.select_related('quelle').all()[:limit]
    n = 0
    errors = 0
    for obj in qs:
        if index_one(obj):
            n += 1
        else:
            errors += 1
    return {'ok': True, 'indexed': n, 'errors': errors, 'index': index_name()}
