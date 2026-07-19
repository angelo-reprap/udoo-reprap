"""Tests: Modul-/Block-Renderer ({{block}}…{{/block}}, {{content}})."""
from django.test import SimpleTestCase

from apps.abpe_email_studio.blocks_registry import (
    block_insert_syntax,
    get_block,
    module_insert_syntax,
    plain_list_to_html,
    suggest_blocks_for_text,
)
from apps.abpe_email_studio.services.renderer import EmailRenderer


class BlocksRegistryTests(SimpleTestCase):
    def test_paired_syntax(self):
        self.assertIn('{{/block}}', module_insert_syntax('fmt_aufzaehlung'))
        self.assertNotIn('{{/block}}', module_insert_syntax('cta_blau'))
        self.assertIn('block_teilnehmer', block_insert_syntax('block_teilnehmer'))

    def test_plain_list_to_html(self):
        html = plain_list_to_html('Max, Erika')
        self.assertIn('<ul>', html)
        self.assertIn('<li>Max</li>', html)
        self.assertIn('<li>Erika</li>', html)

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

    def test_resolve_block_teilnehmer_self_closing(self):
        r = EmailRenderer()
        html = 'Teilnehmer: {{block:block_teilnehmer}}'
        out = r._resolve_modules(html, {
            'teilnehmer_liste': 'Max Mustermann, Erika Musterfrau',
        })
        self.assertIn('<ul>', out)
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
