"""Tests: Modul-/Block-Renderer ({{block}}…{{/block}}, {{content}})."""
from django.test import SimpleTestCase

from apps.abpe_email_studio.blocks_registry import (
    block_insert_syntax,
    format_inner_for_module,
    get_block,
    module_insert_syntax,
    plain_list_to_html,
    suggest_blocks_for_text,
)
from apps.abpe_email_studio.services.renderer import EmailRenderer


class BlocksRegistryTests(SimpleTestCase):
    def test_paired_syntax(self):
        syn = module_insert_syntax('fmt_aufzaehlung')
        self.assertIn('{{/block}}', syn)
        self.assertIn('Hund', syn)
        self.assertNotIn('<ul>', syn)
        self.assertNotIn('{{/block}}', module_insert_syntax('cta_blau'))
        self.assertIn('block_teilnehmer', block_insert_syntax('block_teilnehmer'))

    def test_plain_list_to_html(self):
        html = plain_list_to_html('Max, Erika')
        self.assertIn('•', html)
        self.assertIn('Max', html)
        self.assertIn('Erika', html)
        self.assertEqual(html.count('•'), 2)

    def test_format_inner_keeps_vars(self):
        html = format_inner_for_module('fmt_aufzaehlung', 'Hund\n{tier_2}\nPferd', html=True)
        self.assertIn('•', html)
        self.assertIn('Hund', html)
        self.assertIn('{tier_2}', html)
        self.assertNotIn('&lt;', html)

    def test_space_separated_words_become_bullets(self):
        html = format_inner_for_module(
            'fmt_aufzaehlung', 'Pferd Hund Schildkröte', html=True,
        )
        self.assertEqual(html.count('•'), 3)
        self.assertIn('Pferd', html)
        self.assertIn('Hund', html)
        self.assertIn('Schildkröte', html)

    def test_semicolon_list_becomes_bullets(self):
        html = format_inner_for_module(
            'fmt_aufzaehlung', 'Hund; Katze; Pferd;', html=True,
        )
        self.assertEqual(html.count('•'), 3)
        self.assertIn('Hund', html)
        self.assertIn('Katze', html)
        self.assertIn('Pferd', html)
        html2 = format_inner_for_module(
            'fmt_aufzaehlung', 'Hund;Katze;Pferd', html=True,
        )
        self.assertIn('Katze', html2)

    def test_format_key_value(self):
        html = format_inner_for_module(
            'fmt_key_value', 'Hund: 45 €\nKatze: 30 €', html=True,
        )
        self.assertIn('<strong>Hund:</strong>', html)
        self.assertIn('45 €', html)

    def test_suggest_blocks(self):
        hits = suggest_blocks_for_text('Einladung Telefonkonferenz mit Teilnehmern')
        ids = {h['id'] for h in hits}
        self.assertIn('block_teilnehmer', ids)

    def test_get_block(self):
        b = get_block('block_system_status')
        self.assertIsNotNone(b)
        self.assertEqual(b['module'], 'fmt_tabelle')


class RendererContentSlotTests(SimpleTestCase):
    def test_fill_content_slot(self):
        r = EmailRenderer()
        out = r._fill_content_slot('<div>{{content}}</div>', '<ul><li>A</li></ul>')
        self.assertEqual(out, '<div><ul><li>A</li></ul></div>')

    def test_resolve_paired_fmt_without_db(self):
        r = EmailRenderer()
        html = (
            '{{block:fmt_hinweis}}\n'
            'Wichtiger Hinweis {name}\n'
            '{{/block}}'
        )
        out = r._resolve_modules(html, {'name': 'Max'})
        self.assertIn('Wichtiger Hinweis Max', out)
        self.assertIn('#163258', out)
        self.assertNotIn('{{block:', out)
        self.assertNotIn('{{content}}', out)

    def test_resolve_aufzaehlung_plaintext(self):
        r = EmailRenderer()
        html = (
            '{{block:fmt_aufzaehlung}}\n'
            'Hund\n'
            'Katze\n'
            '{extra_tier}\n'
            '{{/block}}'
        )
        out = r._resolve_modules(html, {'extra_tier': 'Kaninchen'})
        self.assertEqual(out.count('•'), 3)
        self.assertIn('Hund', out)
        self.assertIn('Katze', out)
        self.assertIn('Kaninchen', out)
        self.assertNotIn('{{block:', out)

    def test_resolve_key_value_plaintext(self):
        r = EmailRenderer()
        html = (
            '{{block:fmt_key_value}}\n'
            'Hund: 45 €\n'
            'Katze: {futter_katze}\n'
            '{{/block}}'
        )
        out = r._resolve_modules(html, {'futter_katze': '30 €'})
        self.assertIn('<strong>Hund:</strong>', out)
        self.assertIn('45 €', out)
        self.assertIn('30 €', out)

    def test_resolve_block_teilnehmer_self_closing(self):
        r = EmailRenderer()
        html = 'Teilnehmer: {{block:block_teilnehmer}}'
        out = r._resolve_modules(html, {
            'teilnehmer_liste': 'Max Mustermann, Erika Musterfrau',
        })
        self.assertEqual(out.count('•'), 2)
        self.assertIn('Max Mustermann', out)
        self.assertIn('Erika Musterfrau', out)

    def test_resolve_block_system_status(self):
        r = EmailRenderer()
        table = '<table><tr><td>Host</td></tr></table>'
        out = r._resolve_modules('{{block:block_system_status}}', {
            'system_status_html': table,
        })
        self.assertIn(table, out)
        self.assertIn('padding:16px 24px', out)
