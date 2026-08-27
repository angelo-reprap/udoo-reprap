from datetime import date
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from apps.abpe_shaduler.models import Aufgabe
from apps.abpe_shaduler.services import aufgaben_service

User = get_user_model()


class AufgabeDelegationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='admin_del', password='x', is_staff=True, first_name='Admin',
        )
        self.verena = User.objects.create_user(
            username='verena', password='x', is_staff=True, first_name='Verena',
        )
        self.annett = User.objects.create_user(
            username='annett', password='x', is_staff=True, first_name='Annett',
        )
        self.aufgabe = aufgaben_service.erstellen(
            art=Aufgabe.Art.WIEDERVORLAGE,
            titel='Gulp-Nachbearbeitung — Testdeleg',
            zugewiesen_an=self.owner,
            user=self.owner,
            beschreibung='Arbeitsliste',
        )
        self.client = Client()

    def test_owner_keeps_task_after_share(self):
        aufgaben_service.set_delegates(
            self.aufgabe, [self.verena, self.annett], user=self.owner,
        )
        mine = aufgaben_service.liste(user=self.owner)
        hers = aufgaben_service.liste(user=self.verena)
        ids_mine = {str(t.pk) for t in mine}
        ids_hers = {str(t.pk) for t in hers}
        self.assertIn(str(self.aufgabe.pk), ids_mine)
        self.assertIn(str(self.aufgabe.pk), ids_hers)
        self.assertEqual(self.aufgabe.zugewiesen_an_id, self.owner.id)

    def test_serialize_lists_delegates(self):
        aufgaben_service.set_delegates(self.aufgabe, [self.verena], user=self.owner)
        payload = aufgaben_service.serialize(self.aufgabe, viewer=self.owner)
        self.assertTrue(payload['kann_delegieren'])
        self.assertEqual(payload['delegiert_an_label'], 'Verena')
        as_verena = aufgaben_service.serialize(self.aufgabe, viewer=self.verena)
        self.assertFalse(as_verena['kann_delegieren'])
        self.assertTrue(as_verena['ist_delegiert_an_mich'])

    def test_api_share_and_team(self):
        self.client.force_login(self.owner)
        r = self.client.get('/shaduler/api/team/')
        self.assertEqual(r.status_code, 200)
        names = {u['username'] for u in r.json()['users']}
        self.assertIn('verena', names)
        self.assertIn('annett', names)

        r = self.client.post(
            f'/shaduler/api/aufgaben/{self.aufgabe.pk}/delegieren/',
            data=json.dumps({'user_ids': [self.verena.id, self.annett.id]}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertTrue(body.get('ok'))
        label = body['aufgabe']['delegiert_an_label']
        self.assertIn('Verena', label)
        self.assertIn('Annett', label)

        self.client.force_login(self.verena)
        r = self.client.get(f'/shaduler/api/aufgaben/{self.aufgabe.pk}/')
        self.assertEqual(r.status_code, 200)
        r = self.client.post(
            f'/shaduler/api/aufgaben/{self.aufgabe.pk}/delegieren/',
            data=json.dumps({'user_ids': []}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 403)

    def test_stats_include_delegated(self):
        self.aufgabe.faellig_am = date.today()
        self.aufgabe.save(update_fields=['faellig_am'])
        aufgaben_service.set_delegates(self.aufgabe, [self.verena], user=self.owner)
        st = aufgaben_service.stats(self.verena)
        self.assertGreaterEqual(st['heute'] + st['ueberfaellig'] + st['geplant'], 1)
