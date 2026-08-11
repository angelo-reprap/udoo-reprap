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
        parser.add_argument(
            '--session-info', action='store_true',
            help='Nur Cookie-Quelle anzeigen (settings / CV-Extractor-Datei)',
        )
        parser.add_argument(
            '--probe', action='store_true',
            help='Login-Test wie CV-Extractor (Talentfinder secure API)',
        )

    def handle(self, *args, **options):
        from apps.abpe_shaduler.models import RadarConsultantItem
        from apps.abpe_shaduler.services import radar_berater_service as rbs
        from apps.abpe_shaduler.services import radar_berater_gulp as gulp

        if options.get('probe') or options.get('session_info'):
            info = gulp.probe_session() if options.get('probe') else gulp.gulp_session_info()
            safe = {k: v for k, v in info.items() if k != 'cookie_header'}
            if info.get('cookie_header'):
                safe['cookie_keys'] = [
                    p.split('=', 1)[0] for p in info['cookie_header'].split('; ') if p
                ]
            self.stdout.write(str(safe))
            return

        info = gulp.gulp_session_info()
        if info.get('ok'):
            self.stdout.write(
                f"Gulp-Session: ja (Quelle: {info.get('source')}"
                + (f", Datei: {info.get('path')}" if info.get('path') else '')
                + ')'
            )
        else:
            self.stdout.write('Gulp-Session: NEIN')
            self.stdout.write(info.get('hint') or '')
            if info.get('tried_files'):
                self.stdout.write('Geprüft: ' + ', '.join(info['tried_files']))

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
