"""
Radar-Anfragen Elasticsearch-Index.

Alles was per Radar-Fetch persistiert wird, wird zusätzlich indexiert.
Suche: Volltext + Zeitraum + Quelle + Sortierung (Datum).

Index-Name (settings.json / Django):
  shaduler.es_radar_index  |  elasticsearch.radar_index  |  SHADULER_ES_RADAR_INDEX
  Default: abpe_radar_anfragen
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from django.conf import settings

log = logging.getLogger('abpe_shaduler.radar_index')

RADAR_INDEX_MAPPING = {
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
            'headline': {'type': 'text', 'analyzer': 'de_text',
                         'fields': {'keyword': {'type': 'keyword', 'ignore_above': 320}}},
            'beschreibung': {'type': 'text', 'analyzer': 'de_text'},
            'skills': {'type': 'keyword'},
            'skills_text': {'type': 'text', 'analyzer': 'de_text'},
            'company': {'type': 'text', 'analyzer': 'de_text',
                        'fields': {'keyword': {'type': 'keyword', 'ignore_above': 200}}},
            'city': {'type': 'keyword'},
            'contact': {'type': 'text', 'analyzer': 'de_text'},
            'source': {'type': 'keyword'},
            'status': {'type': 'keyword'},
            'external_url': {'type': 'keyword', 'index': False},
            'project_id': {'type': 'keyword'},
            'dedup_hash': {'type': 'keyword'},
            'published_at': {'type': 'date'},
            'eingegangen_am': {'type': 'date'},
            'updated_at': {'type': 'date'},
        }
    },
}


def _es_hosts() -> list[str]:
    """Reuse Inbox-ES-Hosts."""
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
        from .inbox_service import _load_json_settings as _load
        return _load() or {}
    except Exception:
        return {}


def radar_index_name() -> str:
    cfg = _load_json_settings()
    sh = cfg.get('shaduler') or {}
    return (
        sh.get('es_radar_index')
        or (cfg.get('elasticsearch') or {}).get('radar_index')
        or getattr(settings, 'SHADULER_ES_RADAR_INDEX', None)
        or 'abpe_radar_anfragen'
    )


def _client():
    try:
        from elasticsearch import Elasticsearch
    except ImportError:
        log.info('elasticsearch-Paket fehlt — Radar-Index Skip')
        return None
    try:
        return Elasticsearch(_es_hosts())
    except Exception as exc:
        log.warning('ES Client fehlgeschlagen: %s', exc)
        return None


def ensure_index(es=None) -> bool:
    es = es or _client()
    if not es:
        return False
    name = radar_index_name()
    try:
        if es.indices.exists(index=name):
            return True
        es.indices.create(index=name, body=RADAR_INDEX_MAPPING)
        log.info('Radar-Index angelegt: %s', name)
        return True
    except Exception as exc:
        # Race / already exists
        try:
            if es.indices.exists(index=name):
                return True
        except Exception:
            pass
        log.warning('Radar-Index ensure failed: %s', exc)
        return False


def _parse_iso(val) -> Optional[str]:
    if val is None or val == '':
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    s = str(val).strip()
    if not s:
        return None
    return s


def doc_from_radar_item(obj) -> dict[str, Any]:
    """Django RadarItem → ES-Dokument."""
    eck = obj.eckdaten or {}
    source = eck.get('source') or (obj.quelle.name if getattr(obj, 'quelle_id', None) else '')
    skills = obj.skills or []
    if not isinstance(skills, list):
        skills = []
    skills = [str(s).strip() for s in skills if str(s).strip()]
    published = _parse_iso(eck.get('created')) or _parse_iso(getattr(obj, 'eingegangen_am', None))
    return {
        'headline': obj.headline or '',
        'beschreibung': obj.beschreibung or '',
        'skills': skills,
        'skills_text': ' '.join(skills),
        'company': eck.get('company') or '',
        'city': eck.get('city') or '',
        'contact': eck.get('contact') or '',
        'source': source or '',
        'status': obj.status or 'neu',
        'external_url': obj.external_url or eck.get('url') or '',
        'project_id': eck.get('project_id') or '',
        'dedup_hash': obj.dedup_hash or '',
        'published_at': published,
        'eingegangen_am': _parse_iso(getattr(obj, 'eingegangen_am', None)),
        'updated_at': _parse_iso(getattr(obj, 'updated_at', None)),
    }


def index_item(obj, *, es=None) -> bool:
    """Ein RadarItem upserten."""
    es = es or _client()
    if not es or not obj:
        return False
    if not ensure_index(es):
        return False
    doc = doc_from_radar_item(obj)
    try:
        es.index(index=radar_index_name(), id=str(obj.pk), body=doc, refresh=False)
        return True
    except Exception as exc:
        log.warning('Radar index_item %s failed: %s', obj.pk, exc)
        return False


def index_items(objs, *, refresh: bool = False) -> dict:
    """Bulk-Index. Returns {ok, indexed, errors}."""
    es = _client()
    if not es:
        return {'ok': False, 'indexed': 0, 'errors': 1, 'reason': 'no_es'}
    if not ensure_index(es):
        return {'ok': False, 'indexed': 0, 'errors': 1, 'reason': 'no_index'}
    objs = list(objs or [])
    if not objs:
        return {'ok': True, 'indexed': 0, 'errors': 0}
    name = radar_index_name()
    actions = [
        {
            '_op_type': 'index',
            '_index': name,
            '_id': str(obj.pk),
            '_source': doc_from_radar_item(obj),
        }
        for obj in objs
    ]
    try:
        from elasticsearch.helpers import bulk
        ok_count, errors = bulk(es, actions, raise_on_error=False, refresh=refresh)
        err_n = len(errors) if isinstance(errors, list) else (0 if errors is False else 1)
        return {'ok': err_n == 0, 'indexed': ok_count, 'errors': err_n}
    except Exception:
        # Fallback ohne helpers
        indexed = 0
        errors = 0
        for obj in objs:
            if index_item(obj, es=es):
                indexed += 1
            else:
                errors += 1
        if refresh:
            try:
                es.indices.refresh(index=radar_index_name())
            except Exception:
                pass
        return {'ok': errors == 0, 'indexed': indexed, 'errors': errors}


def delete_item(item_id: str) -> bool:
    es = _client()
    if not es:
        return False
    try:
        es.delete(index=radar_index_name(), id=str(item_id), ignore=[404])
        return True
    except Exception as exc:
        log.debug('Radar delete_item: %s', exc)
        return False


def search(
    *,
    q: str = '',
    days: Optional[int] = 2,
    source: str = '',
    status: str = 'neu',
    sort: str = 'date_desc',
    limit: int = 200,
    offset: int = 0,
) -> Optional[dict[str, Any]]:
    """
    ES-Suche. None wenn ES nicht erreichbar.
    → {ids: [...], total, by_source, source: 'elasticsearch'}
    """
    es = _client()
    if not es:
        return None
    name = radar_index_name()
    try:
        if not es.indices.exists(index=name):
            return None
    except Exception:
        return None

    filters: list[dict] = []
    must: list[dict] = []
    if status:
        filters.append({'term': {'status': status}})
    if source:
        filters.append({'term': {'source': source.strip().lower()}})
    if days is not None and int(days) > 0:
        d = max(1, min(365, int(days)))
        filters.append({'range': {'published_at': {'gte': f'now-{d}d/d', 'lte': 'now+1d'}}})
    else:
        filters.append({'range': {'published_at': {'gte': '2000-01-01', 'lte': 'now+1d'}}})

    q = (q or '').strip()
    if q:
        must.append({
            'multi_match': {
                'query': q,
                'fields': [
                    'headline^4', 'company^3', 'skills_text^2',
                    'beschreibung', 'city', 'contact', 'project_id',
                ],
                'type': 'best_fields',
                'operator': 'and',
                'fuzziness': 'AUTO',
            }
        })

    order = 'asc' if (sort or '').lower() in ('date_asc', 'asc', 'oldest') else 'desc'
    body = {
        'from': max(0, int(offset or 0)),
        'size': max(1, min(500, int(limit or 200))),
        'track_total_hits': True,
        'query': {
            'bool': {
                'filter': filters,
                'must': must or [{'match_all': {}}],
            }
        },
        'sort': [
            {'published_at': {'order': order, 'unmapped_type': 'date'}},
            {'_id': 'asc'},
        ],
        'aggs': {
            'by_source': {'terms': {'field': 'source', 'size': 20}},
        },
        '_source': False,
    }
    try:
        res = es.search(index=name, body=body)
    except Exception as exc:
        log.warning('Radar ES search failed: %s', exc)
        return None

    hits = (res.get('hits') or {}).get('hits') or []
    total_raw = (res.get('hits') or {}).get('total') or 0
    if isinstance(total_raw, dict):
        total = int(total_raw.get('value') or 0)
    else:
        total = int(total_raw or 0)
    ids = [str(h.get('_id')) for h in hits if h.get('_id')]
    by_src = {}
    buckets = ((res.get('aggregations') or {}).get('by_source') or {}).get('buckets') or []
    for b in buckets:
        by_src[str(b.get('key') or '')] = int(b.get('doc_count') or 0)
    return {
        'ids': ids,
        'total': total,
        'by_source': by_src,
        'source': 'elasticsearch',
        'index': name,
    }


def reindex_all(*, status: Optional[str] = None, limit: int = 5000) -> dict:
    """Alle RadarItems (Anfragen-Quellen) neu indexieren."""
    from apps.abpe_shaduler.models import RadarItem, RadarSource
    from .radar_fetcher import ANFRAGEN_SOURCES

    src_ids = list(
        RadarSource.objects.filter(name__in=ANFRAGEN_SOURCES).values_list('pk', flat=True)
    )
    qs = RadarItem.objects.select_related('quelle').all()
    if src_ids:
        qs = qs.filter(quelle_id__in=src_ids)
    if status:
        qs = qs.filter(status=status)
    qs = qs.order_by('-eingegangen_am')[: max(1, min(20000, int(limit)))]
    rows = list(qs)
    info = index_items(rows, refresh=True)
    info['scanned'] = len(rows)
    return info
