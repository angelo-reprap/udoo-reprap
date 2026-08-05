from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Radar Freelancermap einmal pollens (Debug).'

    def add_arguments(self, parser):
        parser.add_argument('--pages', type=int, default=1)
        parser.add_argument('--all-days', action='store_true',
                            help='Nicht auf heutige Einträge beschränken')

    def handle(self, *args, **options):
        from apps.abpe_shaduler.services import radar_fetcher
        pages = options.get('pages') or 1
        today_only = not options.get('all_days')
        self.stdout.write(f'Radar poll pages={pages} today_only={today_only} …')
        info = radar_fetcher.poll_once(pages=pages, today_only=today_only)
        self.stdout.write(self.style.SUCCESS(str(info)))
