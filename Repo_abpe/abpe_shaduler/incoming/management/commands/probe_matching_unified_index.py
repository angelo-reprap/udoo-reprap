"""
probe_matching_unified_index — Contact-zentrierter Matching-Gewichtungs-Probe.

Prüfschleife pro CRM-Contact-ID:
  1) CV-Pipeline-Gewichtung (ConsultantSkill.weight), wenn Join gelingt
  2) sonst Wild-Gewichtung aus ogo_description_c / gulp_profil_c /
     freelancermap_profil_c / xing_profile_c (+ description)

Ein ES-Dokument pro Contact: contact:{crm_id}
Index: abpe_matching_profiles_probe (kein Prod-Index).

ucs5:
  python manage.py probe_matching_unified_index --dry-run --contacts 10
  python manage.py probe_matching_unified_index --contact-id <CRM_UUID> --dry-run
  python manage.py probe_matching_unified_index --execute --contacts 40 --search
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
    help = 'Probe: 1 Matching-Doc pro CRM-Contact (Pipeline-CV-Weights oder Wild-Profil)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--contacts', type=int, default=20,
            help='Anzahl Contacts für die Stichprobe (ignoriert bei --contact-id)',
        )
        parser.add_argument(
            '--contact-id', default='',
            help='Einzelne CRM-Contact-ID (Prüfschleife für genau einen Kontakt)',
        )
        parser.add_argument('--skills', default=','.join(DEFAULT_SKILLS))
        parser.add_argument('--index', default=DEFAULT_INDEX)
        parser.add_argument('--execute', action='store_true')
        parser.add_argument('--dry-run', action='store_true', default=False)
        parser.add_argument('--search', action='store_true', help='Nach Index kurze Skill-Suche')
        parser.add_argument('--out', default='')
        parser.add_argument('--recreate', action='store_true', help='Probe-Index vorher löschen')
        # Legacy-Flags (ignoriert, Warnung) — alte dual-stream Probe
        parser.add_argument('--pipeline', type=int, default=None, help='(legacy, ignoriert)')
        parser.add_argument('--wild', type=int, default=None, help='(legacy, ignoriert)')

    def handle(self, *args, **options):
        from apps.abpe_shaduler.services import matching_weight_probe as mwp

        if options.get('pipeline') is not None or options.get('wild') is not None:
            self.stdout.write(self.style.WARNING(
                'Hinweis: --pipeline/--wild sind legacy. Nutze --contacts / --contact-id '
                '(1 Doc pro Contact: CV-Weight oder Wild-Profil).'
            ))

        n_contacts = max(0, int(options['contacts']))
        only_id = (options.get('contact_id') or '').strip()
        skills = [s.strip() for s in (options['skills'] or '').split(',') if s.strip()]
        index = options['index']
        execute = bool(options['execute']) and not bool(options['dry_run'])
        do_search = bool(options['search'])
        recreate = bool(options.get('recreate'))
        out_dir = Path(
            options['out']
            or f"/tmp/matching-contact-probe-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
        out_dir.mkdir(parents=True, exist_ok=True)

        try:
            Contact = apps.get_model('abpe_crm', 'CrmContact')
            Cstm = apps.get_model('abpe_crm', 'CrmContactCstm')
        except LookupError as exc:
            self.stderr.write(f'CRM models missing: {exc}')
            return

        rows_meta = []
        docs = []
        counts = {
            'pipeline_cv': 0,
            'wild_profil': 0,
            'none': 0,
            'join_via': {},
        }

        if only_id:
            targets = self._load_one(Contact, Cstm, only_id)
        else:
            targets = self._sample_contacts(Contact, Cstm, n_contacts)

        for contact, cstm in targets:
            crm_id = getattr(contact, 'crm_id', None) or (
                getattr(cstm, 'contact_id', None) if cstm else None
            ) or ''
            crm_id = str(crm_id)
            weighed = mwp.weight_for_contact(
                crm_id=crm_id,
                cstm=cstm,
                contact=contact,
                skills_watch=skills,
            )
            src = weighed['weight_source']
            counts[src] = counts.get(src, 0) + 1
            jv = weighed.get('join_via') or ''
            if jv:
                counts['join_via'][jv] = counts['join_via'].get(jv, 0) + 1

            if src == 'none':
                rows_meta.append({
                    'crm_id': crm_id,
                    'name': weighed.get('full_name') or '',
                    'weight_source': 'none',
                    'join_via': jv,
                    'skills': 0,
                    'skip': 'no_pipeline_weights_and_no_profil_text',
                })
                continue

            es_source = 'pipeline_cv' if src == 'pipeline_cv' else 'wild_profil'
            doc = mwp.build_matching_doc(
                doc_id=f'contact:{crm_id}',
                source=es_source,
                full_name=weighed.get('full_name') or '',
                first_name=weighed.get('first_name') or '',
                last_name=weighed.get('last_name') or '',
                body_text=weighed.get('body_text') or '',
                skill_stats=weighed.get('skill_stats') or [],
                extra={
                    'crm_contact_id': crm_id,
                    'gulp_id': weighed.get('gulp_id') or '',
                    'weight_source': src,
                    'join_via': jv,
                    'aid': weighed.get('aid') or '',
                    'consultant_dir': weighed.get('consultant_dir') or '',
                    'profil_fields': weighed.get('profil_fields') or [],
                    'body_len': len(weighed.get('body_text') or ''),
                },
            )
            docs.append(doc)
            top = (weighed.get('skill_stats') or [])[:5]
            rows_meta.append({
                'crm_id': crm_id,
                'name': weighed.get('full_name') or '',
                'weight_source': src,
                'join_via': jv,
                'aid': weighed.get('aid') or '',
                'gulp_id': weighed.get('gulp_id') or '',
                'profil_fields': weighed.get('profil_fields') or [],
                'skills': len(weighed.get('skill_stats') or []),
                'top': [
                    {'name': t.get('name'), 'weight': t.get('weight')}
                    for t in top
                ],
            })

        report = {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'mode': 'contact_centric',
            'execute': execute,
            'index': index,
            'skills_watch': skills,
            'contact_id_filter': only_id or None,
            'sampled': len(targets),
            'docs': len(docs),
            'counts': counts,
            'contacts': rows_meta,
        }
        (out_dir / 'report.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str) + '\n',
            encoding='utf-8',
        )
        (out_dir / 'docs_sample.json').write_text(
            json.dumps(docs[:10], ensure_ascii=False, indent=2, default=str) + '\n',
            encoding='utf-8',
        )

        self.stdout.write(
            f"contacts={len(targets)} docs={len(docs)} "
            f"pipeline_cv={counts['pipeline_cv']} "
            f"wild_profil={counts['wild_profil']} "
            f"none={counts['none']}"
        )
        self.stdout.write(f"join_via={counts['join_via']}")
        self.stdout.write(f'report → {out_dir}/report.json')

        for row in rows_meta[:8]:
            self.stdout.write(
                f"  [{row.get('weight_source')}] {row.get('name') or '?'} "
                f"crm={str(row.get('crm_id') or '')[:8]}… "
                f"join={row.get('join_via') or '-'} "
                f"skills={row.get('skills')} top={row.get('top')}"
            )

        if not execute:
            self.stdout.write(self.style.WARNING(
                'DRY — nichts nach ES. --execute zum Schreiben (1 Doc pro Contact).'
            ))
            return

        self._write_es(index, docs, recreate, do_search, skills)

    def _load_one(self, Contact, Cstm, crm_id: str):
        contact = Contact.objects.filter(crm_id=crm_id).first()
        if not contact:
            self.stderr.write(f'Contact nicht gefunden: {crm_id}')
            return []
        cstm = (
            Cstm.objects.filter(contact_id=crm_id).select_related('contact').first()
            or getattr(contact, 'cstm', None)
        )
        return [(contact, cstm)]

    def _sample_contacts(self, Contact, Cstm, n: int):
        """Contacts mit Profil-Text und/oder gulp_id (Join-Kandidaten)."""
        if n <= 0:
            return []
        qs = (
            Cstm.objects.filter(
                Q(ogo_description_c__isnull=False) & ~Q(ogo_description_c='')
                | Q(gulp_profil_c__isnull=False) & ~Q(gulp_profil_c='')
                | Q(freelancermap_profil_c__isnull=False) & ~Q(freelancermap_profil_c='')
                | Q(xing_profile_c__isnull=False) & ~Q(xing_profile_c='')
                | Q(gulp_id_c__isnull=False) & ~Q(gulp_id_c='')
            )
            .select_related('contact')
            .order_by('-id')
        )
        out = []
        seen = set()
        for cstm in qs.iterator(chunk_size=80):
            if len(out) >= n:
                break
            contact = getattr(cstm, 'contact', None)
            if contact is None:
                cid = getattr(cstm, 'contact_id', None)
                if cid:
                    contact = Contact.objects.filter(crm_id=cid).first()
            if contact is None:
                continue
            crm_id = str(getattr(contact, 'crm_id', '') or '')
            if not crm_id or crm_id in seen:
                continue
            seen.add(crm_id)
            out.append((contact, cstm))
        return out

    def _write_es(self, index, docs, recreate, do_search, skills):
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

        if recreate and es.indices.exists(index=index):
            es.indices.delete(index=index)
            self.stdout.write(f'deleted index {index}')

        if not es.indices.exists(index=index):
            es.indices.create(
                index=index,
                body={
                    'settings': {'number_of_shards': 1, 'number_of_replicas': 0},
                    'mappings': {
                        'properties': {
                            'doc_id': {'type': 'keyword'},
                            'source': {'type': 'keyword'},
                            'weight_source': {'type': 'keyword'},
                            'join_via': {'type': 'keyword'},
                            'full_name': {'type': 'text'},
                            'first_name': {'type': 'text'},
                            'last_name': {'type': 'text'},
                            'body_text': {'type': 'text'},
                            'skill_names': {'type': 'keyword'},
                            'skill_weight_pairs': {
                                'type': 'nested',
                                'properties': {
                                    'skill': {'type': 'keyword'},
                                    'weight': {'type': 'float'},
                                },
                            },
                            'skill_stats': {
                                'type': 'nested',
                                'properties': {
                                    'name': {'type': 'keyword'},
                                    'name_lc': {'type': 'keyword'},
                                    'freq': {'type': 'integer'},
                                    'projects': {'type': 'integer'},
                                    'months': {'type': 'integer'},
                                    'years': {'type': 'float'},
                                    'weight': {'type': 'float'},
                                    'from_db': {'type': 'boolean'},
                                },
                            },
                            'aid': {'type': 'keyword'},
                            'consultant_dir': {'type': 'keyword'},
                            'crm_contact_id': {'type': 'keyword'},
                            'gulp_id': {'type': 'keyword'},
                            'profil_fields': {'type': 'keyword'},
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
        ok_n, errors = helpers.bulk(
            es, actions, chunk_size=50, request_timeout=120, raise_on_error=False,
        )
        if errors:
            self.stderr.write(f'bulk warnings: {len(errors)} failed (erste: {errors[0]})')
        es.indices.refresh(index=index)
        count = es.count(index=index)['count']
        self.stdout.write(self.style.SUCCESS(f'indexed ok≈{ok_n} es_count={count}'))

        if do_search and skills:
            q_skills = [s.lower() for s in skills[:4]]
            should = [{'match': {'body_text': s}} for s in q_skills]
            should += [{'term': {'skill_names': s}} for s in q_skills]
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
                pairs = src.get('skill_weight_pairs') or []
                wmap = {
                    p.get('skill'): float(p.get('weight') or 0)
                    for p in pairs if p.get('skill')
                }
                score_boost = sum(wmap.get(s, 0) for s in q_skills)
                ranked.append((score_boost, h.get('_score') or 0, src))
            ranked.sort(key=lambda x: (-x[0], -x[1]))
            for boost, es_score, src in ranked:
                top_w = ', '.join(
                    f"{p.get('skill')}:{p.get('weight')}"
                    for p in (src.get('skill_weight_pairs') or [])[:5]
                )
                self.stdout.write(
                    f"  boost={boost:.2f} es={es_score:.2f} "
                    f"[{src.get('weight_source')}|join={src.get('join_via') or '-'}] "
                    f"{src.get('full_name')} "
                    f"crm={str(src.get('crm_contact_id') or '')[:8]}… "
                    f"weights={{{top_w}}}"
                )
