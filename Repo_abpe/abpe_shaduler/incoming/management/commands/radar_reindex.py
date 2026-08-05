"""
Radar-Anfragen neu in Elasticsearch indexieren.

  python manage.py radar_reindex
  python manage.py radar_reindex --status neu --limit 2000
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Indexiert Radar-Anfragen nach Elasticsearch (abpe_radar_anfragen).'

    def add_arguments(self, parser):
        parser.add_argument('--status', default='', help='nur Status (z.B. neu)')
        parser.add_argument('--limit', type=int, default=5000)

    def handle(self, *args, **options):
        from apps.abpe_shaduler.services import radar_index
        status = (options.get('status') or '').strip() or None
        limit = options.get('limit') or 5000
        self.stdout.write(
            f'Reindex Radar → {radar_index.radar_index_name()} '
            f'(status={status or "*"} limit={limit}) …'
        )
        info = radar_index.reindex_all(status=status, limit=limit)
        style = self.style.SUCCESS if info.get('ok') else self.style.WARNING
        self.stdout.write(style(str(info)))
