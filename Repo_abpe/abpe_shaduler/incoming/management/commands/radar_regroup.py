"""
Radar-Anfragen neu clustern (Cross-Source-Dedup).

  python manage.py radar_regroup
  python manage.py radar_regroup --days 14 --status neu --limit 800
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Clustert Radar-Anfragen zu RadarItemGroup (Titel/Skills/Stadt, ohne LLM).'

    def add_arguments(self, parser):
        parser.add_argument('--status', default='neu')
        parser.add_argument('--days', type=int, default=14)
        parser.add_argument('--limit', type=int, default=800)

    def handle(self, *args, **options):
        from apps.abpe_shaduler.services import radar_grouper
        status = (options.get('status') or '').strip() or None
        days = options.get('days') or 14
        limit = options.get('limit') or 800
        self.stdout.write(
            f'Regroup Radar (status={status or "*"} days={days} limit={limit}) …'
        )
        info = radar_grouper.regroup_recent(status=status, days=days, limit=limit)
        style = self.style.SUCCESS if info.get('ok') else self.style.WARNING
        self.stdout.write(style(str(info)))
