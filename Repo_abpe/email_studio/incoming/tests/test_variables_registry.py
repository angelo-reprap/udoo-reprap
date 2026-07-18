"""Tests für variables_registry."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def _load_registry():
    """Django-Import wenn verfügbar, sonst Datei direkt laden (Cloud/Offline)."""
    try:
        from apps.abpe_email_studio.variables_registry import (  # type: ignore
            get_variables,
            get_sidebar_variable_groups,
            variable_count,
        )
        return get_variables, get_sidebar_variable_groups, variable_count
    except Exception:
        reg = Path(__file__).resolve().parents[1] / 'variables_registry.py'
        spec = importlib.util.spec_from_file_location(
            'abpe_email_studio_variables_registry', reg,
        )
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        return mod.get_variables, mod.get_sidebar_variable_groups, mod.variable_count


get_variables, get_sidebar_variable_groups, variable_count = _load_registry()


class VariablesRegistryTest(unittest.TestCase):

    def test_general_scope_excludes_meetme(self):
        names = {v['name'] for v in get_variables('general', '')}
        self.assertIn('name', names)
        self.assertNotIn('termin_datum', names)

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

    def test_intake_vars_present(self):
        names = {v['name'] for v in get_variables('intake', 'pipeline_success')}
        for key in ('aid', 'de_editor_url', 'skills', 'button_text'):
            self.assertIn(key, names, msg=key)

    def test_groups_dict_keys(self):
        groups = get_sidebar_variable_groups('telefon', 'meetme_invite_abstimmung')
        self.assertEqual(set(groups.keys()), {'context', 'user', 'system', 'scope'})
        scope_names = {v['name'] for v in groups['scope']}
        self.assertIn('termin_datum', scope_names)

    def test_variable_count(self):
        n = variable_count('telefon', 'meetme_invite_abstimmung')
        self.assertGreater(n, 15)


if __name__ == '__main__':
    unittest.main()
