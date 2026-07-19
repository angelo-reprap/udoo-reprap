"""Tests: MCID Regel-1-Validator."""
from django.test import SimpleTestCase

from apps.abpe_email_studio.blocks_registry import (
    BLOCKS,
    FORMAT_MODULE_ORDER,
    get_module_husk,
)
from apps.abpe_email_studio.services.mcid_validator import McidValidator


class McidValidatorTests(SimpleTestCase):
    def setUp(self):
        self.v = McidValidator()

    def test_ok_table(self):
        html = (
            '<table role="presentation"><tr>'
            '<td style="font-family:Arial;font-size:14px;color:#333333;">Hallo</td>'
            '</tr></table>'
        )
        r = self.v.validate(html)
        self.assertTrue(r['ok'])
        self.assertEqual(r['errors'], [])

    def test_forbidden_script_and_flex(self):
        r = self.v.validate(
            '<div style="display:flex;border-radius:8px"><script>alert(1)</script></div>'
        )
        self.assertFalse(r['ok'])
        codes = {e['code'] for e in r['errors']}
        self.assertIn('tag_script', codes)
        self.assertTrue(
            'css_flex' in codes or 'css_radius' in codes or 'css_forbidden' in codes
        )

    def test_block_tokens_ignored(self):
        r = self.v.validate(
            '{{block:abcona_header_blau}}\n'
            '<p style="font-size:14px">Text {name}</p>\n'
            '{{block:fmt_aufzaehlung}}A; B{{/block}}'
        )
        self.assertTrue(r['ok'], r)

    def test_format_husks_pass(self):
        for fmt_id in FORMAT_MODULE_ORDER:
            husk = get_module_husk(fmt_id, 'html')
            r = self.v.validate(
                husk.replace('{{content}}', 'x'), context='module',
            )
            self.assertTrue(r['ok'], f'{fmt_id}: {r}')

    def test_sidebar_order(self):
        self.assertEqual(FORMAT_MODULE_ORDER[0], 'fmt_aufzaehlung')
        self.assertEqual(FORMAT_MODULE_ORDER[-1], 'fmt_trenner')
        ids = [b['id'] for b in BLOCKS]
        self.assertEqual(ids[0], 'block_termin')
        self.assertEqual(ids[-1], 'block_system_status')
