"""Phase 0 + Phase 1 tests."""
import json

from django.test import Client, TestCase
from django.contrib.auth import get_user_model

from apps.abpe_ki_wiz.models import WizardPrompt, WizardSession
from apps.abpe_ki_wiz.prompt_defaults import WIZARD_PROMPT_DEFAULTS
from apps.abpe_ki_wiz.registry import get_provider, list_wizard_ids
from apps.abpe_ki_wiz.services.json_utils import parse_ai_json
from apps.abpe_ki_wiz.services.orchestrator import _rule_based_analyze

User = get_user_model()


class WizardPromptDefaultsTests(TestCase):
    def test_defaults_have_unique_keys(self):
        keys = [row['key'] for row in WIZARD_PROMPT_DEFAULTS]
        self.assertEqual(len(keys), len(set(keys)))


class JsonUtilsTests(TestCase):
    def test_parse_fenced_json(self):
        raw = '```json\n{"ok": true}\n```'
        self.assertEqual(parse_ai_json(raw), {'ok': True})


class RuleAnalyzeTests(TestCase):
    def test_meetme_briefing(self):
        r = _rule_based_analyze('email_template', 'MeetMe Einladung zur Telefon-Abstimmung')
        self.assertEqual(r['app_scope'], 'telefon')
        self.assertTrue(r['understood'])


class ProviderTests(TestCase):
    def test_email_provider_registered(self):
        self.assertIn('email_template', list_wizard_ids())
        p = get_provider('email_template')
        self.assertEqual(p.wizard_id, 'email_template')
        qs = p.get_question_catalog()
        self.assertGreater(len(qs), 5)


class KiWizardApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='wiztest', password='testpass123')

    def test_health_phase1(self):
        r = self.client.get('/ki-wizard/api/health/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['phase'], 1)

    def test_wizards_includes_email_template(self):
        self.client.force_login(self.user)
        r = self.client.get('/ki-wizard/api/wizards/')
        ids = [w['wizard_id'] for w in r.json()['wizards']]
        self.assertIn('email_template', ids)

    def test_session_flow_analyze_clarify(self):
        from django.core.management import call_command
        call_command('sync_wizard_prompts')

        self.client.force_login(self.user)
        create = self.client.post(
            '/ki-wizard/api/wizards/email_template/session/',
            data=json.dumps({'briefing': 'MeetMe Einladung zur kurzen Telefon-Abstimmung mit Teilnehmerliste'}),
            content_type='application/json',
        )
        self.assertEqual(create.status_code, 201)
        sid = create.json()['session_id']

        analyze = self.client.post(f'/ki-wizard/api/session/{sid}/analyze/')
        self.assertEqual(analyze.status_code, 200)
        self.assertIn('questions', analyze.json())

        clarify = self.client.post(
            f'/ki-wizard/api/session/{sid}/clarify/',
            data=json.dumps({'answers': {
                'S1': 'telefon', 'S2': 'invite', 'I1': 'bullet_list',
                'G1': 'USER', 'A1': 'USER', 'M2': 'plain', 'L1': 'abcona_header_blau', 'L3': 'none',
            }}),
            content_type='application/json',
        )
        self.assertEqual(clarify.status_code, 200)
        self.assertTrue(clarify.json().get('complete'))

        meta = self.client.post(f'/ki-wizard/api/session/{sid}/suggest-meta/')
        self.assertEqual(meta.status_code, 200)
        self.assertIn('suggestions', meta.json())
