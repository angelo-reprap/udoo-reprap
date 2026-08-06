"""Seed Radar-Berater aus CRM-Kontakten mit gulp_id_c + optional Reindex."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Radar Berater: CRM-Seed (gulp_id) + ES-Reindex'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=500)
        parser.add_argument('--reindex', action='store_true')
        parser.add_argument('--seed', action='store_true', default=True)
        parser.add_argument('--no-seed', action='store_true')

    def handle(self, *args, **options):
        from apps.abpe_shaduler.services import radar_berater_service as rbs
        from apps.abpe_shaduler.services import radar_berater_index as idx

        if not options.get('no_seed'):
            self.stdout.write('Seed aus CRM (gulp_id_c) …')
            res = rbs.seed_from_crm(limit=options['limit'])
            self.stdout.write(str(res))
        if options.get('reindex'):
            self.stdout.write('Reindex ES …')
            self.stdout.write(str(idx.reindex_all(limit=options['limit'])))
