#!/usr/bin/env python3
"""Unit-Tests für namazu index_emails (ohne IMAP/ES/Django)."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / 'Repo_abpe/namazu/incoming/management/commands/index_emails.py'


def _load():
    # django / elasticsearch nur für Import mocken
    for name in (
        'django', 'django.core', 'django.core.management', 'django.core.management.base',
        'elasticsearch', 'elasticsearch.helpers',
    ):
        if name not in sys.modules:
            sys.modules[name] = MagicMock()
    # BaseCommand echte Klasse-Attr stub
    base = types.ModuleType('django.core.management.base')
    class BaseCommand:  # noqa: N801
        pass
    base.BaseCommand = BaseCommand
    sys.modules['django.core.management.base'] = base

    spec = importlib.util.spec_from_file_location('index_emails', MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SaneDateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load()

    def test_ok_rfc2822(self):
        iso = self.m.sane_date_iso('Wed, 03 Jun 2026 12:00:00 +0200')
        self.assertIsNotNone(iso)
        self.assertTrue(iso.startswith('2026-06-03'))

    def test_reject_year_4501(self):
        self.assertIsNone(self.m.sane_date_iso('4501-01-01T01:00:00+01:00'))
        self.assertIsNone(self.m.sane_date_iso('Fri, 01 Jan 4501 01:00:00 +0100'))

    def test_reject_pre_2000(self):
        self.assertIsNone(self.m.sane_date_iso('Mon, 01 Jan 1990 00:00:00 +0000'))

    def test_internaldate(self):
        meta = b'1 (INTERNALDATE "03-Jun-2026 14:07:02 +0200" RFC822 {12}'
        iso = self.m._parse_internaldate(meta)
        self.assertIsNotNone(iso)
        self.assertIn('2026-06-03', iso)

    def test_size_bytes_assigned(self):
        """Regression: size_bytes muss gesetzt werden (war undefiniert)."""
        src = MOD.read_text(encoding='utf-8')
        self.assertIn('size_bytes = len(raw)', src)


class InboxSourceTests(unittest.TestCase):
    def test_sane_date_filter_in_inbox_service(self):
        path = ROOT / 'Repo_abpe/abpe_shaduler/incoming/services/inbox_service.py'
        text = path.read_text(encoding='utf-8')
        self.assertIn('_es_sane_date_filters', text)
        self.assertIn('year > 2100', text)


class TasksSyntaxTests(unittest.TestCase):
    def test_no_function_keyword(self):
        path = ROOT / 'Repo_abpe/abpe_shaduler/incoming/tasks.py'
        text = path.read_text(encoding='utf-8')
        self.assertNotIn('\nfunction ', text)
        self.assertIn('def shaduler_prozess_tick', text)
        self.assertIn('def shaduler_email_index', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
