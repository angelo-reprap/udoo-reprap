"""Talentfinder „aktuell verfügbar“ → Radar (+ CRM-Verfügbarkeit)."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'Radar Berater: verfügbare Gulp-Profile einlesen '
        '(neu anlegen / bekannt aktualisieren / CRM verfuegbar_ab)'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit', type=int, default=40,
            help='Max. Profile (default 40, max 200)',
        )
        parser.add_argument(
            '--pages', type=int, default=2,
            help='Talentfinder-Seiten (default 2, max 10)',
        )
        parser.add_argument(
            '--page-size', type=int, default=20,
            help='Treffer pro Seite (default 20, max 50)',
        )
        parser.add_argument(
            '--delay', type=float, default=0.35,
            help='Pause zwischen Detail-Requests',
        )
        parser.add_argument(
            '--no-enrich', action='store_true',
            help='Nur Listen-Treffer, kein Detail-GET',
        )

    def handle(self, *args, **options):
        from apps.abpe_shaduler.services import radar_berater_gulp as gulp
        from apps.abpe_shaduler.services import radar_berater_service as rbs

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
            return

        res = rbs.sync_available_from_gulp(
            limit=options['limit'],
            pages=options['pages'],
            page_size=options['page_size'],
            delay_s=options['delay'],
            enrich=not options['no_enrich'],
        )
        self.stdout.write(str(res))
