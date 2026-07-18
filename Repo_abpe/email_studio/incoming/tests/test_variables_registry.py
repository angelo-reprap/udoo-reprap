"""Tests für variables_registry."""
import unittest

from apps.abpe_email_studio.variables_registry import (
    get_variables,
    get_sidebar_variable_groups,
    variable_count,
)


class VariablesRegistryTest(unittest.TestCase):

    def test_general_scope_includes_meetme_for_sidebar(self):
        names = {v['name'] for v in get_variables('general', '')}
        self.assertIn('name', names)
        # MeetMe-Platzhalter sind katalogweit sichtbar (Werte kommen aus MeetMe-Kontext)
        self.assertIn('termin_datum', names)

    def test_telefon_scope_includes_meetme(self):
        names = {v['name'] for v in get_variables('telefon', 'meetme_invite_abstimmung')}
        for key in (
            'termin_datum', 'termin_uhrzeit', 'raum', 'einwahl_info',
            'teilnehmer_liste', 'teilnehmer_liste_html', 'title',
        ):
            self.assertIn(key, names, msg=key)

    def test_meetme_identifier_on_general_scope(self):
        names = {v['name'] for v in get_variables('general', 'meetme_invite_abstimmung')}
        self.assertIn('termin_datum', names)

    def test_groups_ordered(self):
        groups = get_sidebar_variable_groups('telefon', 'meetme_invite_abstimmung')
        keys = [g['key'] for g in groups]
        self.assertIn('meetme', keys)
        self.assertEqual(keys.index('context'), 0)
        self.assertLess(keys.index('meetme'), keys.index('user'))

    def test_variable_count(self):
        n = variable_count('telefon', 'meetme_invite_abstimmung')
        self.assertGreater(n, 15)

    def test_general_scope_group(self):
        groups = get_sidebar_variable_groups('general', '')
        keys = [g['key'] for g in groups]
        self.assertIn('scope', keys)
        self.assertIn('meetme', keys)
        scope_names = {v['name'] for g in groups if g['key'] == 'scope' for v in g['vars']}
        self.assertIn('vertretung_name', scope_names)


if __name__ == '__main__':
    unittest.main()
