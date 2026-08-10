# -*- coding: utf-8 -*-
"""Verfügbare Freelancer von Freelancermap (public Search-Ajax) → Radar Berater."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'Radar Berater: verfügbare Freelancermap-Profile einlesen '
        '(neu anlegen / bekannt aktualisieren / CRM verfuegbar_ab)'
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

        res = rbs.sync_available_from_fl(
            limit=options['limit'],
            pages=options['pages'],
            delay_s=options['delay'],
        )
        self.stdout.write(str(res))
