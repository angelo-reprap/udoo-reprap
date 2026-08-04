from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from apps.abpe_shaduler.models import ErgebnisTyp, ProzessRegel, ProzessSchritt
from apps.abpe_shaduler.services import aufgaben_service
from apps.abpe_shaduler.services.seed_data import ERGEBNIS_TYPEN, PROZESS_REGELN

User = get_user_model()


class Command(BaseCommand):
    help = 'Lädt ErgebnisTypen + Default-Regeln; optional Demo-Aufgaben für einen User.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--demo-tasks', action='store_true',
            help='Beispiel-Aufgaben für --user anlegen (nur wenn noch keine offenen existieren)',
        )
        parser.add_argument(
            '--user', type=str, default='',
            help='Username für Demo-Aufgaben (Default: erster Superuser)',
        )
        parser.add_argument(
            '--force-demo', action='store_true',
            help='Demo-Aufgaben auch anlegen wenn schon offene existieren',
        )

    def handle(self, *args, **options):
        n_et = self._seed_ergebnis_typen()
        n_reg = self._seed_regeln()
        self.stdout.write(self.style.SUCCESS(
            f'seed_shaduler: {n_et} ErgebnisTypen, {n_reg} Regeln OK'
        ))
        if options['demo_tasks']:
            user = self._resolve_user(options['user'])
            if not user:
                self.stdout.write(self.style.ERROR('Kein User für Demo-Aufgaben'))
                return
            created = self._seed_demo_tasks(user, force=options['force_demo'])
            self.stdout.write(self.style.SUCCESS(
                f'Demo-Aufgaben für {user.username}: {created} neu'
            ))

    def _seed_ergebnis_typen(self) -> int:
        n = 0
        for row in ERGEBNIS_TYPEN:
            _, created = ErgebnisTyp.objects.update_or_create(
                code=row['code'],
                defaults={
                    'label': row['label'],
                    'label_i18n_key': row.get('label_i18n_key', ''),
                    'kontext': row['kontext'],
                    'wirkung_status': row.get('wirkung_status', ''),
                    'eingabefelder': row.get('eingabefelder') or [],
                    'zeigt_dialog': row.get('zeigt_dialog', False),
                    'schliesst_vorgang': row.get('schliesst_vorgang', True),
                    'sort_order': row.get('sort_order', 100),
                    'aktiv': True,
                },
            )
            if created:
                n += 1
        # wirkung_regel nach Regeln setzen
        return n

    def _seed_regeln(self) -> int:
        n = 0
        for spec in PROZESS_REGELN:
            regel, created = ProzessRegel.objects.update_or_create(
                name=spec['name'],
                defaults={
                    'beschreibung': spec.get('beschreibung', ''),
                    'aktiv': True,
                    'ausloeser_typ': spec['ausloeser_typ'],
                    'ausloeser_wert': spec['ausloeser_wert'],
                    'bedingung': {},
                    'erstellt_von': 'user',
                },
            )
            if created:
                n += 1
            for step in spec.get('schritte') or []:
                ProzessSchritt.objects.update_or_create(
                    regel=regel,
                    reihenfolge=step['reihenfolge'],
                    defaults={
                        'aktion_art': step['aktion_art'],
                        'parameter': step.get('parameter') or {},
                        'frist_offset': step.get('frist_offset', ''),
                        'abbruch_bei': '',
                    },
                )
            # ErgebnisTyp.wirkung_regel verknüpfen
            if spec['ausloeser_typ'] == 'ergebnis':
                ErgebnisTyp.objects.filter(code=spec['ausloeser_wert']).update(wirkung_regel=regel)
        return n

    def _resolve_user(self, username: str):
        if username:
            return User.objects.filter(username=username).first()
        return (
            User.objects.filter(is_superuser=True).order_by('id').first()
            or User.objects.order_by('id').first()
        )

    def _seed_demo_tasks(self, user, force: bool = False) -> int:
        from apps.abpe_shaduler.models import Aufgabe
        if not force and Aufgabe.objects.filter(zugewiesen_an=user, status=Aufgabe.Status.OFFEN).exists():
            self.stdout.write('Offene Aufgaben vorhanden — überspringe Demo (--force-demo zum Erzwingen)')
            return 0
        today = timezone.localdate()
        samples = [
            {
                'art': Aufgabe.Art.ANRUF,
                'titel': 'Nachfassen: Angebot #2481 — Hays',
                'beschreibung': 'Angebot mit 3 Profilen gesendet. Kunde anrufen.',
                'faellig_am': today - timedelta(days=2),
                'ref_type': 'anfrage',
                'ref_id': '2481',
                'prioritaet': 1,
            },
            {
                'art': Aufgabe.Art.SMS_MESSENGER,
                'titel': 'Termin-Erinnerung an T. Lorenz',
                'beschreibung': 'Interview morgen 10:00 bei Bechtle.',
                'faellig_am': today,
                'ref_type': 'berater',
                'ref_id': 'lorenz',
                'prioritaet': 2,
                'kanal': 'whatsapp',
            },
            {
                'art': Aufgabe.Art.WIEDERVORLAGE,
                'titel': 'Vertragseingang R. Simon prüfen',
                'beschreibung': 'Vertrag am 28.07. per Post gesendet.',
                'faellig_am': today,
                'ref_type': 'berater',
                'ref_id': 'simon',
                'prioritaet': 3,
            },
            {
                'art': Aufgabe.Art.EMAIL,
                'titel': 'Absagen: 2 Berater (#2440)',
                'beschreibung': 'Massenaktion Absage Berater.',
                'faellig_am': today + timedelta(days=1),
                'ref_type': 'anfrage',
                'ref_id': '2440',
                'prioritaet': 3,
            },
        ]
        n = 0
        for s in samples:
            aufgaben_service.erstellen(zugewiesen_an=user, user=user, quelle=Aufgabe.Quelle.MANUELL, **s)
            n += 1
        return n
