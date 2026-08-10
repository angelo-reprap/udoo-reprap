"""
Doppelte RadarSource-Zeilen bereinigen (gleicher name+ziel).

Live-Symptom:
  MultipleObjectsReturned: get() returned more than one RadarSource

Usage (ucs5):
  cd /opt/abpe/backend
  /opt/abpe/venv311/bin/python manage.py radar_dedupe_sources
  /opt/abpe/venv311/bin/python manage.py radar_dedupe_sources --apply
"""
from django.core.management.base import BaseCommand
from django.db.models import Count


class Command(BaseCommand):
    help = 'Doppelte RadarSource (name+ziel) zusammenführen / deaktivieren.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Schreiben: Items umhängen + Duplikate deaktivieren/löschen',
        )
        parser.add_argument(
            '--delete', action='store_true',
            help='Mit --apply: Duplikate löschen statt nur deaktivieren',
        )

    def handle(self, *args, **options):
        from apps.abpe_shaduler.models import RadarItem, RadarConsultantItem, RadarSource

        apply = options['apply']
        do_delete = options['delete']
        groups = (
            RadarSource.objects.values('name', 'ziel')
            .annotate(n=Count('id'))
            .filter(n__gt=1)
            .order_by('name', 'ziel')
        )
        if not groups:
            self.stdout.write(self.style.SUCCESS('OK — keine Duplikate'))
            return

        for g in groups:
            name, ziel, n = g['name'], g['ziel'], g['n']
            qs = RadarSource.objects.filter(name=name, ziel=ziel)
            if ziel == RadarSource.Ziel.BERATER:
                ranked = list(
                    qs.annotate(_n=Count('consultant_items', distinct=True))
                    .order_by('-aktiv', '-_n', 'created_at')
                )
            else:
                ranked = list(
                    qs.annotate(_n=Count('items', distinct=True))
                    .order_by('-aktiv', '-_n', 'created_at')
                )
            keep = ranked[0]
            dups = ranked[1:]
            self.stdout.write(
                f"→ {name}/{ziel}: {n} Stück — behalte {keep.pk} "
                f"(items={getattr(keep, '_n', '?')}, aktiv={keep.aktiv})"
            )
            for d in dups:
                item_n = RadarItem.objects.filter(quelle=d).count()
                ber_n = RadarConsultantItem.objects.filter(quelle=d).count()
                self.stdout.write(
                    f"   dup {d.pk} items={item_n} berater={ber_n} aktiv={d.aktiv}"
                )
                if not apply:
                    continue
                if item_n:
                    RadarItem.objects.filter(quelle=d).update(quelle=keep)
                if ber_n:
                    RadarConsultantItem.objects.filter(quelle=d).update(quelle=keep)
                if do_delete:
                    d.delete()
                    self.stdout.write(self.style.WARNING(f'   gelöscht {d.pk}'))
                else:
                    d.aktiv = False
                    d.letzter_status = 'duplikat-deaktiviert'
                    d.save(update_fields=['aktiv', 'letzter_status'])
                    self.stdout.write(f'   deaktiviert {d.pk}')

        if not apply:
            self.stdout.write(self.style.WARNING('dry-run — mit --apply schreiben'))
        else:
            self.stdout.write(self.style.SUCCESS('OK — Duplikate bereinigt'))
