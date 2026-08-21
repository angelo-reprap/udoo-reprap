"""
probe_matching_unified_index — Test: ein Matching-Index für Pipeline + Wild-Ogo.

Default: DRY (nur JSON-Report). Schreiben: --execute
Index: abpe_matching_profiles_probe (kein Prod-Index).

ucs5:
  python manage.py probe_matching_unified_index --dry-run --pipeline 5 --wild 5
  python manage.py probe_matching_unified_index --execute --pipeline 20 --wild 20
  python manage.py probe_matching_unified_index --execute --pipeline 20 --wild 20 \\
      --skills java,python,django --search
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db.models import Q


DEFAULT_INDEX = 'abpe_matching_profiles_probe'
DEFAULT_SKILLS = [
    'Java', 'Python', 'Perl', 'Django', 'Spring', 'Kubernetes', 'Docker',
    'AWS', 'Azure', 'SAP', 'SQL', 'PostgreSQL', 'Oracle', 'Linux', 'React',
]


class Command(BaseCommand):
    help = 'Probe: unified matching index (pipeline skills + wild ogo date/weight)'

    def add_arguments(self, parser):
        parser.add_argument('--pipeline', type=int, default=5, help='Anzahl Consultant (DE)')
        parser.add_argument('--wild', type=int, default=5, help='Anzahl Contacts mit ogo_description')
        parser.add_argument('--skills', default=','.join(DEFAULT_SKILLS))
        parser.add_argument('--index', default=DEFAULT_INDEX)
        parser.add_argument('--execute', action='store_true')
        parser.add_argument('--dry-run', action='store_true', default=False)
        parser.add_argument('--search', action='store_true', help='Nach Index kurze Skill-Suche')
        parser.add_argument('--out', default='')

    def handle(self, *args, **options):
        from apps.abpe_shaduler.services import matching_weight_probe as mwp

        n_pipe = max(0, int(options['pipeline']))
        n_wild = max(0, int(options['wild']))
        skills = [s.strip() for s in (options['skills'] or '').split(',') if s.strip()]
        index = options['index']
        execute = bool(options['execute']) and not bool(options['dry_run'])
        do_search = bool(options['search'])
        out_dir = Path(options['out'] or f"/tmp/matching-unified-probe-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
        out_dir.mkdir(parents=True, exist_ok=True)

        docs = []
        report = {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'execute': execute,
            'index': index,
            'skills_watch': skills,
            'pipeline': [],
            'wild': [],
        }

        # ── Pipeline ────────────────────────────────────────────────────
        Consultant = apps.get_model('cv_extractor', 'Consultant')
        qs = (
            Consultant.objects.filter(status__in=['completed', 'validated', 'profile_ready'])
            .exclude(aid__endswith='-en')
            .prefetch_related('skills__skill')
            .order_by('-created_at')
        )
        seen_dirs = set()
        for c in qs.iterator(chunk_size=50):
            if len(report['pipeline']) >= n_pipe:
                break
            key = (c.consultant_dir or c.aid or str(c.id)).lower()
            if key in seen_dirs:
                continue
            seen_dirs.add(key)
            stats = mwp.skill_stats_from_pipeline(c)
            body_parts = [
                c.headline or '',
                f'{c.first_name or ""} {c.last_name or ""}'.strip(),
                c.location or '',
                ' '.join(s['name'] for s in stats[:80]),
            ]
            doc = mwp.build_matching_doc(
                doc_id=f'pipeline:{c.aid or c.id}',
                source='pipeline',
                full_name=f'{c.first_name or ""} {c.last_name or ""}'.strip(),
                first_name=c.first_name or '',
                last_name=c.last_name or '',
                body_text=' '.join(p for p in body_parts if p),
                skill_stats=stats[:60],
                extra={
                    'aid': c.aid,
                    'consultant_dir': c.consultant_dir,
                    'status': c.status,
                },
            )
            docs.append(doc)
            report['pipeline'].append({
                'aid': c.aid,
                'name': doc['full_name'],
                'skills': len(stats),
                'top': stats[:5],
            })

        # ── Wild Ogo ────────────────────────────────────────────────────
        wild_rows = []
        try:
            Cstm = apps.get_model('abpe_crm', 'CrmContactCstm')
        except LookupError:
            Cstm = None
            report['wild_error'] = 'CrmContactCstm not found'

        if Cstm is not None:
            cstm_qs = (
                Cstm.objects.exclude(Q(ogo_description_c__isnull=True) | Q(ogo_description_c=''))
                .select_related('contact')
                .order_by('-id')
            )
            for cstm in cstm_qs.iterator(chunk_size=50):
                if len(wild_rows) >= n_wild:
                    break
                text = (cstm.ogo_description_c or '').strip()
                if len(text) < 80:
                    continue
                for attr in ('gulp_profil_c', 'freelancermap_profil_c'):
                    extra = getattr(cstm, attr, None) or ''
                    if extra and len(extra) > 40:
                        text = text + '\n\n' + extra
                contact = getattr(cstm, 'contact', None)
                first = (getattr(contact, 'first_name', None) or '') if contact else ''
                last = (getattr(contact, 'last_name', None) or '') if contact else ''
                full = f'{first} {last}'.strip()
                crm_id = getattr(contact, 'crm_id', None) or getattr(cstm, 'crm_id_c', None) or str(cstm.pk)
                gulp_id = getattr(cstm, 'gulp_id_c', None) or ''
                stats = mwp.skill_stats_from_wild_text(text, skills)
                doc = mwp.build_matching_doc(
                    doc_id=f'ogo:{crm_id}',
                    source='ogo_wild',
                    full_name=full,
                    first_name=first,
                    last_name=last,
                    body_text=text,
                    skill_stats=stats,
                    extra={
                        'crm_contact_id': str(crm_id),
                        'gulp_id': gulp_id,
                        'body_len': len(text),
                    },
                )
                docs.append(doc)
                wild_rows.append({
                    'crm_id': str(crm_id),
                    'gulp_id': gulp_id,
                    'name': full,
                    'body_len': len(text),
                    'skills_hit': len(stats),
                    'top': stats[:5],
                    'segments_sample': (stats[0]['segments'] if stats else []),
                })
            report['wild'] = wild_rows

        (out_dir / 'report.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str) + '\n',
            encoding='utf-8',
        )
        (out_dir / 'docs_sample.json').write_text(
            json.dumps(docs[:10], ensure_ascii=False, indent=2, default=str) + '\n',
            encoding='utf-8',
        )
        self.stdout.write(f'pipeline={len(report["pipeline"])} wild={len(report["wild"])} docs={len(docs)}')
        self.stdout.write(f'report → {out_dir}/report.json')

        if not execute:
            self.stdout.write(self.style.WARNING('DRY — nichts nach ES. --execute zum Schreiben.'))
            # show one wild example
            for w in report['wild'][:2]:
                self.stdout.write(f"  wild {w.get('name')}: hits={w.get('skills_hit')} top={w.get('top')}")
            for p in report['pipeline'][:2]:
                self.stdout.write(f"  pipe {p.get('name')}: skills={p.get('skills')} top={p.get('top')}")
            return

        # ── ES write ────────────────────────────────────────────────────
        from elasticsearch import Elasticsearch, helpers

        cfg = {}
        try:
            cfg = json.load(open('/opt/abpe/backend/settings.json'))
        except Exception:
            pass
        hosts = (cfg.get('elasticsearch') or {}).get('hosts') or ['http://localhost:9200']
        es = Elasticsearch(hosts, verify_certs=False, request_timeout=120)
        if not es.ping():
            self.stderr.write('ES ping failed')
            return

        if not es.indices.exists(index=index):
            es.indices.create(
                index=index,
                body={
                    'settings': {'number_of_shards': 1, 'number_of_replicas': 0},
                    'mappings': {
                        'properties': {
                            'doc_id': {'type': 'keyword'},
                            'source': {'type': 'keyword'},
                            'full_name': {'type': 'text'},
                            'first_name': {'type': 'text'},
                            'last_name': {'type': 'text'},
                            'body_text': {'type': 'text'},
                            'skill_names': {'type': 'keyword'},
                            'skill_weights': {'type': 'object', 'enabled': True},
                            'skill_stats': {'type': 'nested'},
                            'aid': {'type': 'keyword'},
                            'crm_contact_id': {'type': 'keyword'},
                            'indexed_at': {'type': 'date'},
                            'probe': {'type': 'boolean'},
                        }
                    },
                },
            )
            self.stdout.write(f'created index {index}')

        actions = (
            {'_index': index, '_id': d['doc_id'], '_source': d}
            for d in docs
        )
        helpers.bulk(es, actions, chunk_size=50, request_timeout=120)
        es.indices.refresh(index=index)
        count = es.count(index=index)['count']
        self.stdout.write(self.style.SUCCESS(f'indexed docs={len(docs)} es_count={count}'))

        if do_search and skills:
            q_skills = skills[:4]
            should = [{'match': {'body_text': s}} for s in q_skills]
            should += [{'term': {'skill_names': s.lower()}} for s in q_skills]
            res = es.search(
                index=index,
                size=15,
                query={'bool': {'should': should, 'minimum_should_match': 1}},
            )
            hits = res.get('hits', {}).get('hits', [])
            self.stdout.write(f'\nSearch {q_skills} → {len(hits)} hits:')
            ranked = []
            for h in hits:
                src = h.get('_source') or {}
                wmap = src.get('skill_weights') or {}
                score_boost = sum(float(wmap.get(s.lower(), 0) or 0) for s in q_skills)
                ranked.append((score_boost, h.get('_score') or 0, src))
            ranked.sort(key=lambda x: (-x[0], -x[1]))
            for boost, es_score, src in ranked:
                self.stdout.write(
                    f"  boost={boost:.2f} es={es_score:.2f} "
                    f"[{src.get('source')}] {src.get('full_name')} "
                    f"weights={{{', '.join(f'{k}:{v}' for k,v in list((src.get('skill_weights') or {}).items())[:5])}}}"
                )
