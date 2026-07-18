"""Phase 0 + Phase 1 tests."""
import json

from django.test import Client, TestCase
from django.contrib.auth import get_user_model

from apps.abpe_ki_wiz.prompt_defaults import WIZARD_PROMPT_DEFAULTS
from apps.abpe_ki_wiz.registry import get_provider, list_wizard_ids
from apps.abpe_ki_wiz.services.json_utils import parse_ai_json
from apps.abpe_ki_wiz.services.context_fetcher import (
    ABCONA_COMPANY_FALLBACK,
    detect_fact_keys,
    fetch_company_abcona,
    fetch_user_context,
    resolve_facts,
)
from apps.abpe_ki_wiz.services.prompt_builder import build_context_payload
from apps.abpe_ki_wiz.services.orchestrator import (
    _build_refine_instruction,
    _resolve_current_bodies,
    _rule_based_analyze,
)
from apps.abpe_ki_wiz.services.deepseek_client import _resolve_pbx_service, _coerce_result

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

    def test_general_greeting_briefing(self):
        r = _rule_based_analyze('email_template', 'Weihnachtsgrüße an alle Mitarbeiter mit Bibelzitat')
        self.assertEqual(r['app_scope'], 'general')
        self.assertEqual(r['event_type'], 'info')

    def test_absence_briefing(self):
        r = _rule_based_analyze('email_template', 'Abwesenheitsnotiz mit Vertretung durch Kollegin')
        self.assertEqual(r['app_scope'], 'general')


class GeneralFallbackTests(TestCase):
    def test_greeting_fallback_uses_sender_not_meetme(self):
        p = get_provider('email_template')
        out = p.generate_fallback(
            'Weihnachtsgrüße an alle Mitarbeiter',
            {
                'S1': 'general', 'S2': 'info', 'I1': 'prose',
                'G1': 'USER', 'A1': 'USER', 'M2': 'none',
                'L1': 'none', 'L3': 'none',
            },
            {},
        )
        self.assertEqual(out['source'], 'rules')
        self.assertIn('{sender_name}', out['html_body'])
        self.assertNotIn('{termin_datum}', out['html_body'])


class GenerateFallbackTests(TestCase):
    def test_meetme_invite_fallback(self):
        p = get_provider('email_template')
        out = p.generate_fallback(
            'MeetMe Einladung zur Telefon-Abstimmung mit Teilnehmerliste',
            {
                'S1': 'telefon', 'S2': 'invite', 'I1': 'bullet_list',
                'G1': 'USER', 'A1': 'USER', 'M2': 'plain',
                'L1': 'abcona_header_blau', 'L3': 'none',
            },
            {'subject': 'Termin am {termin_datum}'},
        )
        self.assertEqual(out['source'], 'rules')
        self.assertIn('{{block:abcona_header_blau}}', out['html_body'])
        self.assertIn('{termin_datum}', out['html_body'])
        self.assertIn('{teilnehmer_liste}', out['text_body'])
        self.assertIn('{{block:signature}}', out['html_body'])


class DeepSeekClientTests(TestCase):
    def test_coerce_tuple(self):
        r = _coerce_result((True, '  hello  '))
        self.assertTrue(r.success)
        self.assertEqual(r.text, 'hello')

    def test_resolve_pbx_without_crm(self):
        svc, mod = _resolve_pbx_service()
        # In Test-Umgebung ohne abpe_crm: beides None oder nur mod
        self.assertTrue(svc is None or hasattr(svc, 'summarize') or hasattr(svc, '_chat'))


class ProviderTests(TestCase):
    def test_email_provider_registered(self):
        self.assertIn('email_template', list_wizard_ids())
        p = get_provider('email_template')
        self.assertEqual(p.wizard_id, 'email_template')
        qs = p.get_question_catalog()
        self.assertGreater(len(qs), 5)

    def test_optional_m1_not_blocking(self):
        p = get_provider('email_template')
        analyze = {'missing_topics': ['M1', 'I1']}
        answers = {
            'S1': 'telefon', 'S2': 'invite', 'I1': 'bullet_list',
            'G1': 'USER', 'A1': 'USER',
        }
        pending = p.resolve_questions('', answers, analyze)
        self.assertNotIn('M1', pending)


class ContextFetcherTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='fetcher',
            password='testpass123',
            first_name='Max',
            last_name='Mustermann',
            email='max@abcona.de',
        )

    def test_fetch_user_context(self):
        facts = fetch_user_context(self.user)
        self.assertEqual(facts['sender_name'], 'Max Mustermann')
        self.assertEqual(facts['sender_email'], 'max@abcona.de')

    def test_detect_company_from_refinement(self):
        keys = detect_fact_keys(
            wizard_id='email_template',
            briefing='Weihnachtsgrüße',
            refinement='Gib die abcona e.K. Adresse im Footer ein',
        )
        self.assertIn('company_abcona', keys)
        self.assertIn('user', keys)

    def test_resolve_facts_email_template_always_has_abcona(self):
        facts = resolve_facts(
            wizard_id='email_template',
            user=self.user,
            briefing='Allgemeine Info-Mail',
        )
        self.assertIn('company_abcona', facts)
        self.assertEqual(
            facts['company_abcona']['street'],
            ABCONA_COMPANY_FALLBACK['street'],
        )
        self.assertIn('user', facts)

    def test_fetch_company_abcona_fallback(self):
        company = fetch_company_abcona()
        self.assertEqual(company['email'], 'info@abcona.de')
        self.assertIn('Bornhohl', company['address_line'])

    def test_build_context_payload_includes_facts(self):
        provider = get_provider('email_template')
        facts = resolve_facts(
            wizard_id='email_template',
            user=self.user,
            briefing='Footer mit abcona Adresse',
        )
        payload = build_context_payload(provider, {}, facts=facts)
        self.assertIn('facts', payload)
        self.assertIn('company_abcona', payload['facts'])


class RefineGenerateTests(TestCase):
    def test_build_refine_instruction_includes_html(self):
        instr = _build_refine_instruction(
            'Bibelzitat einfügen',
            current_html='<p>Hallo</p>',
            current_text='Hallo',
        )
        self.assertIn('Bibelzitat', instr)
        self.assertIn('<p>Hallo</p>', instr)
        self.assertIn('Hallo', instr)
        self.assertIn('facts.company_abcona', instr)

    def test_build_refine_instruction_abcona_address(self):
        instr = _build_refine_instruction(
            'Gib die abcona e.K. Adresse ein',
            current_html='<p>Text</p>',
        )
        self.assertIn('abcona', instr.lower())
        self.assertIn('nicht erfinden', instr.lower())

    def test_resolve_current_bodies_prefers_request_payload(self):
        session = type('S', (), {'result': {'fields': {'html_body': '<p>alt</p>'}}})()
        html, text = _resolve_current_bodies(session, '<p>neu</p>', 'neu')
        self.assertEqual(html, '<p>neu</p>')
        self.assertEqual(text, 'neu')

    def test_resolve_current_bodies_from_session_result(self):
        session = type('S', (), {
            'result': {'fields': {'html_body': '<p>session</p>', 'text_body': 'session'}},
        })()
        html, text = _resolve_current_bodies(session)
        self.assertEqual(html, '<p>session</p>')
        self.assertEqual(text, 'session')


class SpectacularSchemaTests(TestCase):
    def test_global_schema_lists_ki_wizard_generate(self):
        r = self.client.get('/api/schema/')
        self.assertEqual(r.status_code, 200, msg=r.content[:500])
        body = r.json()
        self.assertIn('openapi', body)
        paths = body.get('paths', {})
        generate_paths = [p for p in paths if '/ki-wizard/' in p and 'generate' in p]
        self.assertTrue(generate_paths, msg=f'ki-wizard generate fehlt in {list(paths)[:8]}')


class KiWizardApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='wiztest', password='testpass123')

    def test_global_openapi_schema_includes_ki_wizard_analyze(self):
        r = self.client.get('/api/schema/')
        self.assertEqual(r.status_code, 200, msg=r.content[:500])
        body = r.json()
        self.assertIn('openapi', body)
        paths = body.get('paths', {})
        analyze_paths = [p for p in paths if '/ki-wizard/' in p and 'analyze' in p]
        self.assertTrue(analyze_paths)

    def test_global_swagger_ui_html(self):
        r = self.client.get('/api/docs/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/html', r['Content-Type'])
        body = r.content.decode()
        self.assertTrue(
            'swagger' in body.lower() or 'schema' in body.lower(),
            msg='Spectacular Swagger UI erwartet',
        )

    def test_index_lists_global_schema_and_docs(self):
        r = self.client.get('/ki-wizard/')
        self.assertEqual(r.status_code, 200)
        api = r.json()['api']
        self.assertEqual(api['schema'], '/api/schema/')
        self.assertEqual(api['docs'], '/api/docs/')

    def test_health_phase1(self):
        r = self.client.get('/ki-wizard/api/health/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['phase'], 1)

    def test_wizards_includes_email_template(self):
        self.client.force_login(self.user)
        r = self.client.get('/ki-wizard/api/wizards/')
        ids = [w['wizard_id'] for w in r.json()['wizards']]
        self.assertIn('email_template', ids)

    def test_session_flow_analyze_clarify_meta(self):
        from django.core.management import call_command
        call_command('sync_wizard_prompts')

        self.client.force_login(self.user)
        create = self.client.post(
            '/ki-wizard/api/wizards/email_template/session/',
            data=json.dumps({
                'briefing': 'MeetMe Einladung zur kurzen Telefon-Abstimmung mit Teilnehmerliste',
            }),
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
                'G1': 'USER', 'A1': 'USER', 'M2': 'plain',
                'L1': 'abcona_header_blau', 'L3': 'none',
            }}),
            content_type='application/json',
        )
        self.assertEqual(clarify.status_code, 200)
        self.assertTrue(clarify.json().get('complete'))

        meta = self.client.post(f'/ki-wizard/api/session/{sid}/suggest-meta/')
        self.assertEqual(meta.status_code, 200)
        self.assertIn('suggestions', meta.json())

        generate = self.client.post(f'/ki-wizard/api/session/{sid}/generate/')
        self.assertEqual(generate.status_code, 200)
        body = generate.json()
        self.assertIn('generated', body)
        self.assertTrue(body['generated'].get('html_body'))
