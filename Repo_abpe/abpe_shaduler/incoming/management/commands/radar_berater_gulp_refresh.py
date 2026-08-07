"""Gulp aktualisieren: Existenz + Verfügbarkeit für Radar-Berater."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Radar Berater: Gulp-Existenz/Verfügbarkeit prüfen (Batch)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit', type=int, default=50,
            help='Max. Profile (default 50, max 500)',
        )
        parser.add_argument(
            '--delay', type=float, default=0.35,
            help='Pause zwischen Requests in Sekunden',
        )
        parser.add_argument(
            '--gulp-id', type=str, default='',
            help='Nur diese eine Gulp-ID prüfen',
        )

    def handle(self, *args, **options):
        from apps.abpe_shaduler.models import RadarConsultantItem
        from apps.abpe_shaduler.services import radar_berater_service as rbs
        from apps.abpe_shaduler.services import radar_berater_gulp as gulp

        self.stdout.write(
            'Gulp-Session: ' + ('ja' if gulp.has_gulp_session() else 'NEIN — Cookies setzen!')
        )
        gid = (options.get('gulp_id') or '').strip()
        if gid:
            obj = (
                RadarConsultantItem.objects
                .filter(gulp_id=gid, deleted_at__isnull=True)
                .exclude(status='geloescht')
                .first()
            )
            if not obj:
                self.stderr.write(f'Kein Radar-Eintrag für gulp_id={gid}')
                return
            self.stdout.write(str(rbs.refresh_one_from_gulp(obj)))
            return

        res = rbs.refresh_from_gulp(
            limit=options['limit'],
            delay_s=options['delay'],
        )
        self.stdout.write(str(res))
