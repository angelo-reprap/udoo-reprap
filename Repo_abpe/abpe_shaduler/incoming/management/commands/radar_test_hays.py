"""
Hays-Radar vom Server prüfen (ohne Persistenz nötig).

  python manage.py radar_test_hays
  python manage.py radar_test_hays --days 3 --pages 2
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Test: Hays IT/Contracting HTML + JSON-LD (Radar). Kein DB-Write nötig.'

    def add_arguments(self, parser):
        parser.add_argument('--pages', type=int, default=2)
        parser.add_argument('--days', type=int, default=2)
        parser.add_argument('--all', action='store_true', help='Kein Datumsfilter')
        parser.add_argument('--no-detail', action='store_true', help='Nur Listen-Karten')
        parser.add_argument('--json', action='store_true')

    def handle(self, *args, **options):
        from apps.abpe_shaduler.services import radar_fetcher as rf

        pages = max(1, min(8, int(options['pages'] or 2)))
        days = max(1, min(14, int(options['days'] or 2)))
        today_only = not options['all']
        enrich = not options['no_detail']

        self.stdout.write(self.style.NOTICE(
            f'Hays-Test: pages={pages} today_only={today_only} '
            f'recent_days={days} enrich={enrich}'
        ))
        self.stdout.write(f'URL: {rf._hays_list_url(1)}')

        try:
            items = rf.fetch_hays_projects(
                pages=pages,
                today_only=today_only,
                recent_days=days,
                enrich_details=enrich,
            )
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f'Fetch fehlgeschlagen: {exc}'))
            return

        by_day = Counter()
        for it in items:
            by_day[str(it.get('raw_created') or '')[:10] or '?'] += 1

        self.stdout.write(self.style.SUCCESS(f'OK Treffer: {len(items)}'))
        self.stdout.write(
            '  nach Tag:  ' + ', '.join(
                f'{k}={v}' for k, v in sorted(by_day.items(), reverse=True)
            )
        )
        day = date.today()
        oldest = day - timedelta(days=days - 1)
        self.stdout.write(f'  Fenster: {oldest.isoformat()} … {day.isoformat()}')

        for it in items[:8]:
            self.stdout.write(
                f"  · {str(it.get('raw_created') or '')[:16]}  "
                f"{(it.get('headline') or '')[:70]}  "
                f"[{it.get('city') or ''}]  {it.get('external_id') or ''}"
            )

        if options['json']:
            import json
            self.stdout.write(json.dumps(items[:3], ensure_ascii=False, indent=2)[:4000])
