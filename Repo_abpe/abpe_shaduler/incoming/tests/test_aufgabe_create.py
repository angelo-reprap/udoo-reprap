from datetime import date, time
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from apps.abpe_shaduler.models import Aufgabe

User = get_user_model()


class AufgabeCreateApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='aufgabe_neu', password='x', is_staff=True, first_name='Test',
        )
        self.client = Client()
        self.client.force_login(self.user)

    def _post(self, payload):
        return self.client.post(
            '/shaduler/api/aufgaben/create/',
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_titel_required(self):
        r = self._post({'art': 'intern'})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json().get('ok'))

    def test_create_defaults_today(self):
        r = self._post({'titel': 'Rückruf Müller', 'art': 'anruf'})
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()
        self.assertTrue(body.get('ok'))
        created = body['created']
        self.assertEqual(created['titel'], 'Rückruf Müller')
        self.assertEqual(created['art'], 'anruf')
        self.assertEqual(created['faellig_am'], timezone.localdate().isoformat())
        aufgabe = Aufgabe.objects.get(pk=created['id'])
        self.assertEqual(aufgabe.quelle, Aufgabe.Quelle.MANUELL)
        self.assertEqual(aufgabe.zugewiesen_an_id, self.user.id)

    def test_create_honors_due_and_quelle(self):
        r = self._post({
            'titel': 'Radar-Nachzug',
            'art': 'wiedervorlage',
            'beschreibung': 'Gulp prüfen',
            'faellig_am': '2026-09-04',
            'faellig_zeit': '14:30',
            'quelle': 'radar',
        })
        self.assertEqual(r.status_code, 201, r.content)
        created = r.json()['created']
        self.assertEqual(created['faellig_am'], '2026-09-04')
        self.assertEqual(created['faellig_zeit'], '14:30')
        aufgabe = Aufgabe.objects.get(pk=created['id'])
        self.assertEqual(aufgabe.faellig_am, date(2026, 9, 4))
        self.assertEqual(aufgabe.faellig_zeit, time(14, 30))
        self.assertEqual(aufgabe.quelle, Aufgabe.Quelle.RADAR)
        self.assertEqual(aufgabe.beschreibung, 'Gulp prüfen')

    def test_invalid_art_falls_back_to_intern(self):
        r = self._post({'titel': 'Sonstiges', 'art': 'gibtsnicht'})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['created']['art'], Aufgabe.Art.INTERN)
