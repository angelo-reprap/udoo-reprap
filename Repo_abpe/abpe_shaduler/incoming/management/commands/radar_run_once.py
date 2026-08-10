from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Radar Freelancermap + Gulp einmal pollen (Debug).'

    def add_arguments(self, parser):
        parser.add_argument('--pages', type=int, default=1)
        parser.add_argument('--days', type=int, default=2,
                            help='Fenster heute + (days-1) Vortage')
        parser.add_argument('--all-days', action='store_true',
                            help='Nicht auf Datumsfenster beschränken')

    def handle(self, *args, **options):
        from apps.abpe_shaduler.services import radar_fetcher
        pages = options.get('pages') or 1
        today_only = not options.get('all_days')
        days = options.get('days') or 2
        self.stdout.write(
            f'Radar poll pages={pages} today_only={today_only} days={days} …'
        )
        info = radar_fetcher.poll_once(
            pages=pages, today_only=today_only, recent_days=days,
        )
        self.stdout.write(self.style.SUCCESS(str(info)))
