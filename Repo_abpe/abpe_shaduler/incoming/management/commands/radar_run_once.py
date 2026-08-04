from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Radar manuell einmal anstoßen (Debug).'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('radar_run_once: Stub — V2.'))
