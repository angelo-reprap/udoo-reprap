#!/usr/bin/env python3
"""
index_namazu_profiles — HTML unter /var/www/namazu/index → ES abpe_namazu_profiles.

Usage (ucs5):
  python manage.py index_namazu_profiles --dry-run --limit 20
  python manage.py index_namazu_profiles --incremental --since-hours 168
  python manage.py index_namazu_profiles --full          # Catch-up nach langer Pause

Inkrementell: nur Dateien mit mtime innerhalb since_hours (Default 168).
Full: alle HTML-Dateien (kann bei ~23k einige Minuten dauern).
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from pathlib import Path

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

DEFAULT_DIR = Path('/var/www/namazu/index')
DEFAULT_INDEX = 'abpe_namazu_profiles'

# nachname__vorname__uuid.html  (Inventur-Muster)
NAME_FILE_RE = re.compile(
    r'^(?P<last>[^_]+)__(?P<first>[^_]+)__(?P<uid>[a-f0-9-]{8,})\.html$',
    re.I,
)
GULP_RE = re.compile(r'gulp[_-]?id["\s:=]+([A-Za-z0-9_-]+)', re.I)
EMAIL_RE = re.compile(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', re.I)
PHONE_RE = re.compile(r'(?:\+?\d[\d\s/()-]{6,}\d)')
META_RE = re.compile(
    r'(verfügbar(?:\s*ab)?|funktion|status)\s*[:\-]\s*([^\n<]{2,80})',
    re.I,
)


class _StripHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        if data and data.strip():
            self.parts.append(data)

    def text(self):
        return re.sub(r'\s+', ' ', ' '.join(self.parts)).strip()


def _strip_html(raw: str) -> str:
    p = _StripHTML()
    try:
        p.feed(raw)
        p.close()
        return p.text()
    except Exception:
        return re.sub(r'<[^>]+>', ' ', raw)


def _parse_file(path: Path) -> dict:
    raw = path.read_text(encoding='utf-8', errors='replace')
    body = _strip_html(raw)[:50000]
    fname = path.name
    m = NAME_FILE_RE.match(fname)
    first = last = uid = ''
    if m:
        first = m.group('first').replace('-', ' ').strip()
        last = m.group('last').replace('-', ' ').strip()
        uid = m.group('uid')

    gulp = ''
    gm = GULP_RE.search(raw) or GULP_RE.search(body)
    if gm:
        gulp = gm.group(1)

    email = ''
    em = EMAIL_RE.search(body)
    if em:
        email = em.group(0)

    telefon = ''
    # skip emails mistaken as phone — take first plausible
    for pm in PHONE_RE.finditer(body[:2000]):
        cand = re.sub(r'\s+', ' ', pm.group(0)).strip()
        if '@' in cand:
            continue
        digits = re.sub(r'\D', '', cand)
        if 7 <= len(digits) <= 15:
            telefon = cand
            break

    funktion = status = verfuegbar = ''
    for mm in META_RE.finditer(body[:3000]):
        key = mm.group(1).lower()
        val = mm.group(2).strip()
        if 'verfügbar' in key:
            verfuegbar = val[:120]
        elif 'funktion' in key:
            funktion = val[:120]
        elif 'status' in key:
            status = val[:80]

    full_name = f'{first} {last}'.strip()
    return {
        'filename': fname,
        'first_name': first,
        'last_name': last,
        'full_name': full_name,
        'gulp_id': gulp or uid or '',
        'email': email,
        'telefon': telefon,
        'funktion': funktion,
        'status': status,
        'verfuegbar_ab': verfuegbar,
        'profile_url': f'/namazu/{fname}' if fname else '',
        'body_text': body,
        'indexed_at': datetime.now(timezone.utc).isoformat(),
        'source': 'index_namazu_profiles',
    }


def _es_client():
    from elasticsearch import Elasticsearch

    cfg = {}
    try:
        cfg = json.load(open('/opt/abpe/backend/settings.json'))
    except Exception:
        pass
    hosts = (cfg.get('elasticsearch') or {}).get('hosts') or ['http://localhost:9200']
    return Elasticsearch(hosts, verify_certs=False, request_timeout=120)


def _ensure_index(es, index: str):
    if es.indices.exists(index=index):
        return
    es.indices.create(
        index=index,
        body={
            'settings': {'number_of_shards': 1, 'number_of_replicas': 0},
            'mappings': {
                'properties': {
                    'filename': {'type': 'keyword'},
                    'first_name': {'type': 'text', 'fields': {'keyword': {'type': 'keyword'}}},
                    'last_name': {'type': 'text', 'fields': {'keyword': {'type': 'keyword'}}},
                    'full_name': {'type': 'text'},
                    'gulp_id': {'type': 'keyword'},
                    'email': {'type': 'keyword'},
                    'telefon': {'type': 'keyword'},
                    'funktion': {'type': 'text'},
                    'status': {'type': 'keyword'},
                    'verfuegbar_ab': {'type': 'keyword'},
                    'profile_url': {'type': 'keyword'},
                    'body_text': {'type': 'text'},
                    'indexed_at': {'type': 'date'},
                    'source': {'type': 'keyword'},
                }
            },
        },
    )


class Command(BaseCommand):
    help = 'Namazu HTML → Elasticsearch abpe_namazu_profiles (inkrementell oder full)'

    def add_arguments(self, parser):
        parser.add_argument('--dir', default=str(DEFAULT_DIR))
        parser.add_argument('--index', default=DEFAULT_INDEX)
        parser.add_argument('--incremental', action='store_true', default=False)
        parser.add_argument('--full', action='store_true', default=False)
        parser.add_argument('--since-hours', type=int, default=168)
        parser.add_argument('--limit', type=int, default=0)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--batch-size', type=int, default=200)

    def handle(self, *args, **options):
        root = Path(options['dir'])
        index = options['index']
        incremental = bool(options['incremental']) and not bool(options['full'])
        since_hours = max(1, int(options['since_hours'] or 168))
        limit = int(options['limit'] or 0)
        dry = bool(options['dry_run'])
        batch = max(20, int(options['batch_size'] or 200))

        if not root.is_dir():
            self.stderr.write(self.style.ERROR(f'DIR fehlt: {root}'))
            return

        cutoff = None
        if incremental:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)

        files = sorted(root.glob('*.html'))
        selected = []
        for p in files:
            if cutoff is not None:
                mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
                if mtime < cutoff:
                    continue
            selected.append(p)
            if limit and len(selected) >= limit:
                break

        self.stdout.write(
            f'namazu_profiles: dir={root} index={index} '
            f'html_total={len(files)} selected={len(selected)} '
            f'incremental={incremental} since_hours={since_hours} dry={dry}'
        )

        if not selected:
            self.stdout.write('Nichts zu indexieren.')
            return

        if dry:
            for p in selected[:10]:
                doc = _parse_file(p)
                self.stdout.write(
                    f"  DRY {p.name} name={doc['full_name']!r} "
                    f"gulp={doc['gulp_id']!r} body_len={len(doc['body_text'])}"
                )
            if len(selected) > 10:
                self.stdout.write(f'  … +{len(selected) - 10} weitere')
            return

        from elasticsearch import helpers

        es = _es_client()
        if not es.ping():
            self.stderr.write(self.style.ERROR('ES nicht erreichbar'))
            return
        _ensure_index(es, index)

        ok = fail = 0

        def actions():
            nonlocal ok, fail
            for p in selected:
                try:
                    doc = _parse_file(p)
                    doc_id = doc.get('gulp_id') or p.stem
                    yield {
                        '_index': index,
                        '_id': doc_id,
                        '_source': doc,
                    }
                    ok += 1
                except Exception as exc:
                    fail += 1
                    logger.warning('parse/index skip %s: %s', p.name, exc)

        helpers.bulk(es, actions(), chunk_size=batch, request_timeout=120)
        try:
            es.indices.refresh(index=index)
        except Exception:
            pass
        count = es.count(index=index)['count']
        self.stdout.write(
            self.style.SUCCESS(
                f'DONE selected={len(selected)} ok≈{ok} fail={fail} es_count={count}'
            )
        )
