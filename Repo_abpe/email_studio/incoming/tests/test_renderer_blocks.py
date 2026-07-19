"""Tests: Modul-/Block-Renderer ({{block}}…{{/block}}, {{content}}, • Bullets)."""
from django.test import SimpleTestCase

from apps.abpe_email_studio.blocks_registry import (
    FORMAT_MODULE_IDS,
    LIST_BULLET,
    block_insert_syntax,
    format_inner_for_module,
    get_block,
    module_insert_syntax,
    plain_list_to_html,
    resolve_block_identifier,
    suggest_blocks_for_text,
)
from apps.abpe_email_studio.services.renderer import EmailRenderer


class BlocksRegistryTests(SimpleTestCase):
    def test_paired_syntax(self):
        syn = module_insert_syntax('fmt_aufzaehlung')
        self.assertIn('{{/block}}', syn)
        self.assertIn('Pferd', syn)
        self.assertNotIn('<ul>', syn)
        self.assertNotIn('{{/block}}', module_insert_syntax('cta_blau'))
        self.assertEqual(module_insert_syntax('fmt_trenner'), '{{block:fmt_trenner}}')
        self.assertIn('block_teilnehmer', block_insert_syntax('block_teilnehmer'))
        self.assertIn('fmt_trenner', FORMAT_MODULE_IDS)

    def test_plain_list_to_html(self):
        html = plain_list_to_html('Max, Erika')
        self.assertIn(LIST_BULLET, html)
        self.assertIn('Max', html)
        self.assertIn('Erika', html)
        self.assertEqual(html.count(LIST_BULLET), 2)
        self.assertIn('font-size:14px', html)

    def test_format_inner_keeps_vars(self):
        html = format_inner_for_module('fmt_aufzaehlung', 'Hund\n{tier_2}\nPferd', html=True)
        self.assertIn(LIST_BULLET, html)
        self.assertIn('Hund', html)
        self.assertIn('{tier_2}', html)
        self.assertNotIn('&lt;', html)

    def test_br_from_visual_editor_becomes_bullets(self):
        """Visual/contenteditable speichert oft <br> statt Newlines."""
        html = format_inner_for_module(
            'fmt_aufzaehlung', 'Pferd<br>Hund<br>Katze', html=True,
        )
        self.assertEqual(html.count(LIST_BULLET), 3)
        self.assertIn('Pferd', html)
        self.assertIn('Katze', html)
        self.assertIn('font-size:14px', html)

    def test_div_from_visual_editor_becomes_bullets(self):
        html = format_inner_for_module(
            'fmt_aufzaehlung',
            '<div>Pferd</div><div>Hund</div><div>Katze</div>',
            html=True,
        )
        self.assertEqual(html.count(LIST_BULLET), 3)

    def test_ul_legacy_converted_to_bullets(self):
        html = format_inner_for_module(
            'fmt_aufzaehlung',
            '<ul><li>Max</li><li>Erika</li></ul>',
            html=True,
        )
        self.assertEqual(html.count(LIST_BULLET), 2)
        self.assertIn('Max', html)

    def test_space_separated_words_become_bullets(self):
        html = format_inner_for_module(
            'fmt_aufzaehlung', 'Pferd Hund Schildkröte', html=True,
        )
        self.assertEqual(html.count(LIST_BULLET), 3)

    def test_semicolon_list_becomes_bullets(self):
        html = format_inner_for_module(
            'fmt_aufzaehlung', 'Hund; Katze; Pferd;', html=True,
        )
        self.assertEqual(html.count(LIST_BULLET), 3)
        html2 = format_inner_for_module(
            'fmt_aufzaehlung', 'Hund;Katze;Pferd', html=True,
        )
        self.assertIn('Katze', html2)

    def test_format_key_value(self):
        html = format_inner_for_module(
            'fmt_key_value', 'Hund: 45 €\nKatze: 30 €', html=True,
        )
        self.assertIn('Hund:', html)
        self.assertIn('45 €', html)
        self.assertIn('font-size:14px', html)

    def test_suggest_blocks(self):
        hits = suggest_blocks_for_text('Einladung Telefonkonferenz mit Teilnehmern')
        ids = {h['id'] for h in hits}
        self.assertIn('block_teilnehmer', ids)
        hits2 = suggest_blocks_for_text('Bitte die Anhänge und PDF prüfen')
        self.assertIn('block_anhaenge', {h['id'] for h in hits2})

    def test_get_block(self):
        b = get_block('block_system_status')
        self.assertIsNotNone(b)
        self.assertEqual(b['module'], 'fmt_tabelle')
        self.assertIsNotNone(get_block('block_anhaenge'))


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
        self.assertEqual(out.count(LIST_BULLET), 3)
        self.assertIn('Hund', out)
        self.assertIn('Katze', out)
        self.assertIn('Kaninchen', out)
        self.assertIn('font-size:14px', out)
        self.assertNotIn('{{block:', out)

    def test_resolve_aufzaehlung_with_br(self):
        r = EmailRenderer()
        html = (
            '{{block:fmt_aufzaehlung}}'
            'Pferd<br>Hund<br>Katze'
            '{{/block}}'
        )
        out = r._resolve_modules(html, {})
        self.assertEqual(out.count(LIST_BULLET), 3)
        self.assertIn('Pferd', out)

    def test_resolve_key_value_plaintext(self):
        r = EmailRenderer()
        html = (
            '{{block:fmt_key_value}}\n'
            'Hund: 45 €\n'
            'Katze: {futter_katze}\n'
            '{{/block}}'
        )
        out = r._resolve_modules(html, {'futter_katze': '30 €'})
        self.assertIn('Hund:', out)
        self.assertIn('45 €', out)
        self.assertIn('30 €', out)

    def test_resolve_block_teilnehmer_self_closing(self):
        r = EmailRenderer()
        html = 'Teilnehmer: {{block:block_teilnehmer}}'
        out = r._resolve_modules(html, {
            'teilnehmer_liste': 'Max Mustermann, Erika Musterfrau',
        })
        self.assertEqual(out.count(LIST_BULLET), 2)
        self.assertIn('Max Mustermann', out)
        self.assertIn('Erika Musterfrau', out)

    def test_resolve_block_anhaenge(self):
        r = EmailRenderer()
        out = r._resolve_modules('{{block:block_anhaenge}}', {
            'dokument_1': 'CV.pdf',
            'dokument_2': 'Referenzen.pdf',
        })
        self.assertEqual(out.count(LIST_BULLET), 2)
        self.assertIn('CV.pdf', out)

    def test_resolve_block_system_status(self):
        r = EmailRenderer()
        table = '<table><tr><td>Host</td></tr></table>'
        out = r._resolve_modules('{{block:block_system_status}}', {
            'system_status_html': table,
        })
        self.assertIn(table, out)
        self.assertIn('padding:16px 24px', out)

    def test_resolve_trenner(self):
        r = EmailRenderer()
        out = r._resolve_modules('A {{block:fmt_trenner}} B', {})
        self.assertIn('border-top:1px solid #dee2e6', out)
        self.assertNotIn('{{block:fmt_trenner}}', out)

    def test_header_before_list_does_not_swallow_block(self):
        """Regression: {{block:header}}… darf fmt_aufzaehlung nicht bis {{/block}} fressen."""
        r = EmailRenderer()
        html = (
            '{{block:abcona_header_blau}}\n'
            '{{block:label_info}}\n'
            '{{block:fmt_aufzaehlung}}\n'
            'Hund\n'
            'Katze\n'
            'Maus {{/block}}\n'
            '{{block:fmt_tabelle}} Tier | Kosten\nHund | 50 €\n{{/block}}'
        )
        out = r._resolve_modules(html, {'name': 'Max'})
        self.assertEqual(out.count(LIST_BULLET), 3)
        self.assertIn('Hund', out)
        self.assertIn('Katze', out)
        self.assertIn('Maus', out)
        self.assertNotIn('{{block:fmt_aufzaehlung}}', out)

    def test_visual_div_header_before_list(self):
        r = EmailRenderer()
        html = (
            '<div>{{block:abcona_header_blau}}</div>'
            '<div>{{block:fmt_aufzaehlung}}<br>Hund<br>Katze<br>Maus {{/block}}'
            '{{block:fmt_tabelle}} Tier | Kosten Hund | 50 €{{/block}}</div>'
        )
        out = r._resolve_modules(html, {})
        self.assertEqual(out.count(LIST_BULLET), 3)
