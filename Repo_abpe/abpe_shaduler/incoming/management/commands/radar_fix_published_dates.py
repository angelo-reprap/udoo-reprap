"""
eingegangen_am aus eckdaten.created nachziehen (Publikationsdatum).

Behebt „Datum: neueste“ verkehrt nach Batch-Import (auto_now_add = Importzeit).

  cd /opt/abpe/backend
  /opt/abpe/venv311/bin/python manage.py radar_fix_published_dates
  /opt/abpe/venv311/bin/python manage.py radar_fix_published_dates --apply
"""
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'RadarItem.eingegangen_am aus eckdaten.created korrigieren.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--limit', type=int, default=5000)

    def handle(self, *args, **options):
        from apps.abpe_shaduler.models import RadarItem
        from apps.abpe_shaduler.services.radar_fetcher import _parse_dt, ANFRAGEN_SOURCES

        apply = options['apply']
        limit = max(1, min(20000, int(options['limit'])))
        qs = (
            RadarItem.objects.filter(quelle__name__in=ANFRAGEN_SOURCES)
            .exclude(eckdaten={})
            .order_by('-updated_at')[:limit]
        )
        fixed = 0
        scanned = 0
        for obj in qs:
            scanned += 1
            eck = obj.eckdaten or {}
            pub = _parse_dt(eck.get('created'))
            if not pub:
                continue
            if timezone.is_naive(pub):
                try:
                    pub = timezone.make_aware(pub, timezone.get_current_timezone())
                except Exception:
                    pub = timezone.make_aware(pub, timezone.utc)
            if obj.eingegangen_am and abs((obj.eingegangen_am - pub).total_seconds()) <= 60:
                continue
            fixed += 1
            self.stdout.write(
                f"  {obj.pk}  {obj.eingegangen_am} → {pub}  {(obj.headline or '')[:50]}"
            )
            if apply:
                RadarItem.objects.filter(pk=obj.pk).update(eingegangen_am=pub)

        self.stdout.write(f"gescannt={scanned} zu_korrigieren={fixed}")
        if not apply and fixed:
            self.stdout.write(self.style.WARNING('dry-run — mit --apply schreiben'))
        elif apply:
            self.stdout.write(self.style.SUCCESS(f'OK — {fixed} Datumsangaben korrigiert'))
