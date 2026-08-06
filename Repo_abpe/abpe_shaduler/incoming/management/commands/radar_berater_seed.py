"""CRM gulp_id → Radar Vollsync + Soft-Delete + ES-Reindex."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Radar Berater: CRM-Sync (gulp_id) + Soft-Delete + ES-Reindex'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit', type=int, default=0,
            help='Max. CRM-Kontakte (0 = alle)',
        )
        parser.add_argument('--reindex', action='store_true', default=True)
        parser.add_argument('--no-reindex', action='store_true')
        parser.add_argument('--seed', action='store_true', default=True)
        parser.add_argument('--no-seed', action='store_true')

    def handle(self, *args, **options):
        from apps.abpe_shaduler.services import radar_berater_service as rbs
        from apps.abpe_shaduler.services import radar_berater_index as idx

        do_seed = not options.get('no_seed')
        do_reindex = not options.get('no_reindex')
        lim = options['limit']

        if do_seed:
            self.stdout.write('CRM-Sync (gulp_id_c) …')
            res = rbs.sync_crm_index(limit=lim if lim and lim > 0 else 0, reindex=do_reindex)
            self.stdout.write(str(res))
        elif do_reindex:
            self.stdout.write('Reindex ES …')
            re_lim = lim if lim and lim > 0 else 0
            self.stdout.write(str(idx.reindex_all(limit=re_lim, active_only=True)))
