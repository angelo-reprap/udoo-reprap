"""
Gulp-Radar vom Server prüfen (ohne Persistenz nötig).

Auf ucs5:
  cd /opt/abpe/backend
  /opt/abpe/venv311/bin/python manage.py radar_test_gulp
  /opt/abpe/venv311/bin/python manage.py radar_test_gulp --days 3 --pages 4
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Test: Gulp REST CSRF + Suche (Radar). Kein DB-Write nötig.'

    def add_arguments(self, parser):
        parser.add_argument('--pages', type=int, default=3)
        parser.add_argument('--page-size', type=int, default=20)
        parser.add_argument('--days', type=int, default=2,
                            help='Fenster heute..(today-days+1)')
        parser.add_argument('--all', action='store_true',
                            help='Kein Datumsfilter')
        parser.add_argument('--json', action='store_true',
                            help='Roh-JSON der ersten Treffer')

    def handle(self, *args, **options):
        from apps.abpe_shaduler.services import radar_fetcher as rf

        pages = max(1, min(10, int(options['pages'] or 3)))
        page_size = max(10, min(30, int(options['page_size'] or 20)))
        days = max(1, min(14, int(options['days'] or 2)))
        today_only = not options['all']

        self.stdout.write(self.style.NOTICE(
            f'Gulp-Test: pages={pages} page_size={page_size} '
            f'today_only={today_only} recent_days={days}'
        ))

        # 1) CSRF
        try:
            opener, jar = rf._gulp_opener()
            token = rf._gulp_csrf_token(opener, jar)
            self.stdout.write(self.style.SUCCESS(
                f'OK CSRF cookie {rf.GULP_CSRF_COOKIE}={token[:8]}…'
            ))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f'CSRF fehlgeschlagen: {exc}'))
            return

        # 2) Fetch
        try:
            items = rf.fetch_gulp_projects(
                pages=pages,
                page_size=page_size,
                today_only=today_only,
                recent_days=days,
            )
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f'Suche fehlgeschlagen: {exc}'))
            return

        by_day = Counter()
        by_type = Counter()
        for it in items:
            by_day[str(it.get('raw_created') or '')[:10] or '?'] += 1
            typ = (it.get('eckdaten') or {}).get('gulp_type') or '?'
            by_type[typ] += 1

        self.stdout.write(self.style.SUCCESS(f'OK Treffer: {len(items)}'))
        self.stdout.write('  nach Tag:  ' + ', '.join(f'{k}={v}' for k, v in sorted(by_day.items(), reverse=True)))
        self.stdout.write('  nach Typ:  ' + ', '.join(f'{k}={v}' for k, v in by_type.most_common()))

        # Fenster-Hinweis
        day = date.today()
        oldest = day - timedelta(days=days - 1)
        self.stdout.write(f'  Fenster:   {oldest.isoformat()} … {day.isoformat()}')

        for it in items[:8]:
            self.stdout.write(
                f"  · [{(it.get('sources') or ['?'])[0]}] "
                f"{(it.get('raw_created') or '')[:16]}  "
                f"{(it.get('headline') or '')[:70]}"
            )
            self.stdout.write(f"      {it.get('external_url') or ''}")

        if options['json'] and items:
            sample = items[0]
            self.stdout.write(json.dumps({
                'id': sample.get('id'),
                'headline': sample.get('headline'),
                'company': sample.get('company'),
                'city': sample.get('city'),
                'raw_created': sample.get('raw_created'),
                'external_url': sample.get('external_url'),
                'eckdaten': sample.get('eckdaten'),
            }, ensure_ascii=False, indent=2))

        if not items and today_only:
            self.stdout.write(self.style.WARNING(
                'Keine Treffer im Fenster. Tipp: --days 3 oder --all'
            ))
