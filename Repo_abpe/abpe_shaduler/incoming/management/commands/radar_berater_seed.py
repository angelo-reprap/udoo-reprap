"""Seed Radar-Berater aus CRM-Kontakten mit gulp_id_c + optional Reindex."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Radar Berater: CRM-Seed (gulp_id) + ES-Reindex'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=10000,
                            help='Max. CRM-Kontakte mit gulp_id (0 = alle)')
        parser.add_argument('--reindex', action='store_true')
        parser.add_argument('--seed', action='store_true', default=True)
        parser.add_argument('--no-seed', action='store_true')

    def handle(self, *args, **options):
        from apps.abpe_shaduler.services import radar_berater_service as rbs
        from apps.abpe_shaduler.services import radar_berater_index as idx

        if not options.get('no_seed'):
            self.stdout.write('Seed aus CRM (gulp_id_c) …')
            lim = options['limit']
            res = rbs.seed_from_crm(limit=lim if lim and lim > 0 else 0)
            self.stdout.write(str(res))
        if options.get('reindex'):
            self.stdout.write('Reindex ES …')
            lim = options['limit']
            re_lim = lim if lim and lim > 0 else 50000
            self.stdout.write(str(idx.reindex_all(limit=re_lim)))
