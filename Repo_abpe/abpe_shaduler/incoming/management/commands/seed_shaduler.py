from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Lädt Shaduler-Fixtures (ErgebnisTypen, Default-Regeln) und prüft Defaults.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('seed_shaduler: Stub — Fixtures folgen.'))
