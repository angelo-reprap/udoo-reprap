"""Phase 0 tests for abpe_ki_wiz."""
from django.test import Client, TestCase
from django.contrib.auth import get_user_model

from apps.abpe_ki_wiz.models import WizardPrompt
from apps.abpe_ki_wiz.prompt_defaults import WIZARD_PROMPT_DEFAULTS
from apps.abpe_ki_wiz.registry import list_wizard_ids


User = get_user_model()


class WizardPromptDefaultsTests(TestCase):
    def test_defaults_have_unique_keys(self):
        keys = [row['key'] for row in WIZARD_PROMPT_DEFAULTS]
        self.assertEqual(len(keys), len(set(keys)))

    def test_email_template_prompts_exist(self):
        keys = {row['key'] for row in WIZARD_PROMPT_DEFAULTS}
        self.assertIn('wiz_email_analyze', keys)
        self.assertIn('wiz_email_generate', keys)


class KiWizardApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='wiztest',
            password='testpass123',
        )

    def test_health_without_auth(self):
        response = self.client.get('/ki-wizard/api/health/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['service'], 'abpe_ki_wiz')

    def test_wizards_requires_login(self):
        response = self.client.get('/ki-wizard/api/wizards/')
        self.assertIn(response.status_code, (302, 401, 403))

    def test_wizards_list_when_logged_in(self):
        self.client.force_login(self.user)
        response = self.client.get('/ki-wizard/api/wizards/')
        self.assertEqual(response.status_code, 200)
        # Stub provider _stub is filtered out
        wizards = response.json().get('wizards', [])
        self.assertIsInstance(wizards, list)

    def test_sync_command_creates_prompts(self):
        from django.core.management import call_command
        call_command('sync_wizard_prompts')
        self.assertGreaterEqual(WizardPrompt.objects.count(), len(WIZARD_PROMPT_DEFAULTS))

    def test_stub_provider_registered(self):
        self.assertIn('_stub', list_wizard_ids())
