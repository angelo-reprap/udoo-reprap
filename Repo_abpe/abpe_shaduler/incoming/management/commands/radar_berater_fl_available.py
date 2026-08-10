# -*- coding: utf-8 -*-
"""Verfügbare Freelancer von Freelancermap → Radar Berater.

Session (optional, für Stundensätze):
  settings.json → shaduler.freelancermap  ODER  data/url/fl/.session_cookies.json

Immer aus dem Backend-Root ausführen:
  cd /opt/abpe/backend
  /opt/abpe/venv311/bin/python manage.py radar_berater_fl_available --limit 20 --pages 1
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'Radar Berater: verfügbare Freelancermap-Profile einlesen '
        '(neu anlegen / bekannt aktualisieren / CRM verfuegbar_ab; '
        'Session → Stundensätze)'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit', type=int, default=36,
            help='Max. Profile (default 36, max 200)',
        )
        parser.add_argument(
            '--pages', type=int, default=2,
            help='FM-Suchseiten (default 2, max 10)',
        )
        parser.add_argument(
            '--delay', type=float, default=0.15,
            help='Pause zwischen Upserts',
        )

    def handle(self, *args, **options):
        from apps.abpe_shaduler.services import radar_berater_service as rbs
        from apps.abpe_shaduler.services import radar_berater_fl as fl

        info = fl.fl_session_info()
        if info.get('ok'):
            self.stdout.write(
                self.style.SUCCESS(
                    f"FM-Session: {info.get('source')} {info.get('path') or ''}".strip()
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    info.get('hint')
                    or 'Keine FM-Session — Sätze in der Suche oft leer.'
                )
            )

        res = rbs.sync_available_from_fl(
            limit=options['limit'],
            pages=options['pages'],
            delay_s=options['delay'],
        )
        rates = res.get('rates_with_value')
        if rates is not None:
            self.stdout.write(f"rates_with_value={rates} fl_session={res.get('fl_session')}")
        if res.get('hint'):
            self.stdout.write(self.style.WARNING(str(res['hint'])))
        self.stdout.write(str(res))
