"""Tests für Matching KI-Anfragen-Wizard (matching_anfrage)."""
from django.test import TestCase

from apps.abpe_ki_wiz.prompt_defaults import WIZARD_PROMPT_DEFAULTS
from apps.abpe_ki_wiz.providers.matching_anfrage import (
    PROMPT_KEY,
    MatchingAnfrageWizardProvider,
    map_extract_to_form_fields,
)
from apps.abpe_ki_wiz.registry import get_provider, list_wizard_ids
from apps.abpe_ki_wiz.services.matching_anfrage_extract import build_user_email_payload
from apps.abpe_ki_wiz.services.orchestrator import _prompt_key


class MatchingAnfrageProviderTests(TestCase):
    def test_provider_registered(self):
        self.assertIn('matching_anfrage', list_wizard_ids())
        p = get_provider('matching_anfrage')
        self.assertEqual(p.wizard_id, 'matching_anfrage')
        self.assertEqual(p.get_catalog().get('prompt_key'), PROMPT_KEY)

    def test_no_clarify_questions(self):
        p = MatchingAnfrageWizardProvider()
        self.assertEqual(p.resolve_questions('irgendein langer briefing text hier'), [])

    def test_prompt_default_present(self):
        keys = [r['key'] for r in WIZARD_PROMPT_DEFAULTS]
        self.assertIn(PROMPT_KEY, keys)
        row = next(r for r in WIZARD_PROMPT_DEFAULTS if r['key'] == PROMPT_KEY)
        self.assertEqual(row['wizard_id'], 'matching_anfrage')
        self.assertIn('Weiterleitungen', row['system'])
        self.assertIn('[[BRIEFING]]', row['user_template'])

    def test_orchestrator_prompt_key(self):
        self.assertEqual(
            _prompt_key('matching_anfrage', 'generate'),
            PROMPT_KEY,
        )


class MatchingAnfrageMapTests(TestCase):
    def test_map_hays_style(self):
        extract = {
            'kunde': {'name': 'Hays AG', 'email_domain': 'hays.de', 'confidence': 0.9},
            'ansprechpartner': {
                'name': 'Tristan Treder',
                'email': 'tristan.treder@hays.de',
                'confidence': 0.85,
            },
            'weiterleitung': {
                'ja': True,
                'von': 'Karsten Bär',
                'email': 'baer.karsten@baer-consulting.bayern',
            },
            'titel': 'IT Network & Security Engineer – Fortinet',
            'beschreibung': 'Netzwerk und Security mit Fortinet.',
            'start': {'asap': True, 'datum': None},
            'dauer_monate': 3,
            'standort': None,
            'remote': True,
            'stundensatz_max': None,
            'skills': ['Fortinet', 'Network', 'Security'],
            'hinweise': ['Endkunde anonym'],
        }
        fields = map_extract_to_form_fields(extract)
        self.assertEqual(fields['customer_name'], 'Hays AG')
        self.assertEqual(fields['contact_name'], 'Tristan Treder')
        self.assertEqual(fields['duration_months'], 3)
        self.assertEqual(fields['location'], 'Remote')
        self.assertIsNone(fields['rate_max'])
        self.assertTrue(fields['start_asap'])
        self.assertIn('Weiterleitung von', fields['description'])
        self.assertIn('Fortinet', fields['description'])

    def test_remote_appended_to_standort(self):
        fields = map_extract_to_form_fields({
            'standort': 'Frankfurt',
            'remote': True,
            'kunde': {},
            'ansprechpartner': {},
            'start': {},
            'weiterleitung': {},
            'beschreibung': 'x',
            'skills': [],
            'hinweise': [],
        })
        self.assertEqual(fields['location'], 'Frankfurt / Remote')


class MatchingAnfragePayloadTests(TestCase):
    def test_build_payload(self):
        text = build_user_email_payload(
            'Body text hier',
            subject='WG: Test',
            outer_from='A <a@b.de>',
        )
        self.assertIn('Betreff: WG: Test', text)
        self.assertIn('Weiterleitung von / äußerer Absender', text)
        self.assertIn('A <a@b.de>', text)
        self.assertIn('Body text hier', text)


class MatchingAnfrageAsapTests(TestCase):
    def test_asap_sets_today(self):
        from datetime import date
        fields = map_extract_to_form_fields({
            'start': {'asap': True, 'datum': None},
            'kunde': {}, 'ansprechpartner': {}, 'weiterleitung': {},
            'beschreibung': 'x', 'skills': [], 'hinweise': [],
        })
        self.assertTrue(fields['start_asap'])
        self.assertEqual(fields['start_date'], date.today().isoformat())
