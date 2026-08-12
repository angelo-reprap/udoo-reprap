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
        self.assertIn('skills_required', row['system'])
        self.assertIn('skills_nice', row['system'])
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


class MatchingAnfrageSkillsTests(TestCase):
    SAMPLE = (
        'Solution Architect – Mainframe Replatforming & Cloud Advisory (m/w/d)\n'
        'Rahmeninformationen\nReferenz:179691\nEinsatzort:Remote\n'
        'Ihre Qualifikationen\n'
        ' - Mainframe-Entwicklung (COBOL, PL/I oder Assembler)\n'
        ' - Mainframe-Architekturen\n'
        ' - Rocket Enterprise Tools\n'
        ' - Mainframe-Replatforming und Modernisierung\n'
        ' - Cloud Advisory und Zielarchitekturen\n'
        ' - Agile Methoden\n'
        ' - DevOps\n'
        ' - CI/CD-Pipelines\n'
        ' - Infrastructure as Code (IaC)\n'
        ' - Coaching, Mentoring und Knowledge Transfer\n'
        'Ihre Aufgaben\n'
        ' - Konzeption von Replatforming-Lösungen\n'
        'Kurzbeschreibung\n'
        ' - Beratung und Konzeption.\n'
    )

    def test_extract_skills_from_qualifikationen(self):
        from apps.abpe_ki_wiz.providers.matching_anfrage import extract_skills_from_text
        pack = extract_skills_from_text(self.SAMPLE)
        skills_l = [s.lower() for s in pack['skills']]
        self.assertIn('cobol', skills_l)
        self.assertIn('pl/i', skills_l)
        self.assertIn('assembler', skills_l)
        self.assertTrue(
            any('mainframe' in s for s in skills_l),
            pack['skills'],
        )
        # Softskills nach hinten / nice
        nice_l = [s.lower() for s in pack['skills_nice']]
        self.assertTrue(
            any('agile' in s for s in nice_l)
            or any('coaching' in s for s in nice_l),
            pack,
        )
        # COBOL vor Coaching in Gesamtliste
        if 'cobol' in skills_l and any('coaching' in s for s in skills_l):
            self.assertLess(
                skills_l.index('cobol'),
                next(i for i, s in enumerate(skills_l) if 'coaching' in s),
            )

    def test_extract_skills_bullet_line(self):
        from apps.abpe_ki_wiz.providers.matching_anfrage import extract_skills_from_text
        text = (
            'Rolle X\n\n---\n'
            '• Skills: Mainframe-Entwicklung, COBOL, PL/I, Assembler, '
            'Cloud Advisory, Agile Methoden, Coaching\n'
        )
        pack = extract_skills_from_text(text)
        self.assertIn('COBOL', pack['skills'])
        self.assertTrue(any('Agile' in s for s in pack['skills_nice']) or
                        any(s.lower() == 'agile methoden' for s in pack['skills_nice']))

    def test_map_skills_required_nice_weights(self):
        fields = map_extract_to_form_fields({
            'kunde': {}, 'ansprechpartner': {}, 'weiterleitung': {}, 'start': {},
            'beschreibung': 'x',
            'skills_required': ['COBOL', 'PL/I', 'Assembler'],
            'skills_nice': ['Coaching', 'Agile Methoden'],
            'skills': [],
            'hinweise': [],
        })
        self.assertEqual(fields['skills'][:3], ['COBOL', 'PL/I', 'Assembler'])
        self.assertIn('Coaching', fields['skills'])
        weights = {r['name']: r['weight'] for r in fields['required_skills']}
        self.assertEqual(weights['COBOL'], 1.0)
        self.assertEqual(weights['Coaching'], 0.55)

    def test_map_falls_back_to_beschreibung_heuristik(self):
        fields = map_extract_to_form_fields({
            'kunde': {}, 'ansprechpartner': {}, 'weiterleitung': {}, 'start': {},
            'beschreibung': self.SAMPLE,
            'skills': [],
            'hinweise': [],
        })
        self.assertTrue(any('COBOL' == s or 'cobol' == s.lower() for s in fields['skills']))
        self.assertTrue(len(fields['skills']) >= 5)

    def test_fallback_provider_extracts_skills(self):
        p = MatchingAnfrageWizardProvider()
        fb = p.generate_fallback(self.SAMPLE)
        skills_l = [s.lower() for s in fb['skills']]
        self.assertIn('cobol', skills_l)
        self.assertIn('pl/i', skills_l)
        self.assertTrue(fb['skills_required'])


class MatchingAnfrageCrmMatchTests(TestCase):
    def test_teufel_not_confused_with_treder(self):
        from apps.abpe_ki_wiz.services.matching_anfrage_extract import _confident_contact
        teufel = {
            'crm_id': 'x',
            'full_name': 'Tristan Teufel',
            'email': 'info@teufel-it.de',
        }
        self.assertFalse(_confident_contact(
            teufel, 'Tristan Treder', 'tristan.treder@hays.de',
        ))
        self.assertTrue(_confident_contact(
            {
                'crm_id': 'y',
                'full_name': 'Tristan Treder',
                'email': 'tristan.treder@hays.de',
            },
            'Tristan Treder',
            'tristan.treder@hays.de',
        ))

    def test_customer_from_title_fallback(self):
        from apps.abpe_ki_wiz.providers.matching_anfrage import derive_customer_name
        name = derive_customer_name({
            'kunde': {'name': None},
            'titel': 'Hays AG - IT Network & Security Engineer – Fortinet (m/w/d)',
            'ansprechpartner': {'email': 'tristan.treder@hays.de'},
        })
        self.assertEqual(name, 'Hays AG')

    def test_contact_name_not_company_uses_email(self):
        from apps.abpe_ki_wiz.providers.matching_anfrage import map_extract_to_form_fields
        fields = map_extract_to_form_fields({
            'kunde': {'name': 'a2a Experts', 'confidence': 0.9},
            'ansprechpartner': {
                'name': 'a2a Experts',
                'email': 'bob@bobmichaels.ai',
                'phone': None,
                'confidence': 0.5,
            },
            'weiterleitung': {'ja': False},
            'titel': 'Role',
            'beschreibung': 'x'*30,
            'start': {'asap': True, 'datum': None},
            'dauer_monate': 6,
            'standort': 'FFM',
            'remote': False,
            'stundensatz_max': None,
            'skills': [],
            'hinweise': [],
        })
        self.assertEqual(fields['customer_name'], 'a2a Experts')
        self.assertEqual(fields['contact_name'], 'Bob Michaels')
        self.assertEqual(fields['contact_email'], 'bob@bobmichaels.ai')

