"""Tests für System-Status-Snapshot und Registry-Gruppe."""
import unittest
from unittest.mock import patch

from apps.abpe_email_studio.variables_registry import (
    GROUP_ORDER,
    get_allowed_var_names,
    get_sidebar_variable_groups,
)
from apps.abpe_email_studio.services.system_status import (
    clear_system_status_cache,
    collect_system_status,
    _fmt_bytes,
    _aggregate,
    _OK,
    _FAIL,
    _WARN,
    _NA,
)


class SystemStatusServiceTest(unittest.TestCase):

    def setUp(self):
        clear_system_status_cache()

    def test_fmt_bytes(self):
        self.assertEqual(_fmt_bytes(512), '512 B')
        self.assertEqual(_fmt_bytes(2048), '2.0 KB')
        self.assertIn('GB', _fmt_bytes(3 * 1024 ** 3))

    def test_aggregate(self):
        self.assertEqual(_aggregate(_OK, _OK), _OK)
        self.assertEqual(_aggregate(_OK, _WARN), _WARN)
        self.assertEqual(_aggregate(_OK, _FAIL), _FAIL)
        self.assertEqual(_aggregate(_NA, _NA), _NA)

    @patch('apps.abpe_email_studio.services.system_status._check_scheduler', return_value=_OK)
    @patch('apps.abpe_email_studio.services.system_status._check_celery', return_value=_OK)
    @patch('apps.abpe_email_studio.services.system_status._check_db', return_value=_OK)
    @patch(
        'apps.abpe_email_studio.services.system_status._check_disk',
        return_value=('12.4 GB', '67%', _OK),
    )
    def test_collect_keys(self, *_mocks):
        clear_system_status_cache()
        data = collect_system_status(use_cache=False)
        for key in (
            'disk_free', 'disk_used_pct', 'django_ok', 'db_ok',
            'celery_ok', 'scheduler_ok', 'system_status', 'system_status_list',
        ):
            self.assertIn(key, data)
            self.assertIsInstance(data[key], str)
        self.assertEqual(data['disk_free'], '12.4 GB')
        self.assertEqual(data['system_status'], _OK)
        self.assertIn('Celery', data['system_status_list'])

    @patch('apps.abpe_email_studio.services.system_status._check_scheduler', return_value=_OK)
    @patch('apps.abpe_email_studio.services.system_status._check_celery', return_value=_OK)
    @patch('apps.abpe_email_studio.services.system_status._check_db', return_value=_OK)
    @patch(
        'apps.abpe_email_studio.services.system_status._check_disk',
        return_value=('1 GB', '10%', _OK),
    )
    def test_cache(self, disk_mock, *_rest):
        clear_system_status_cache()
        a = collect_system_status(use_cache=True)
        b = collect_system_status(use_cache=True)
        self.assertEqual(a, b)
        self.assertEqual(disk_mock.call_count, 1)


class SystemStatusRegistryTest(unittest.TestCase):

    def test_status_in_group_order(self):
        self.assertIn('status', GROUP_ORDER)
        self.assertLess(GROUP_ORDER.index('system'), GROUP_ORDER.index('status'))

    def test_status_vars_visible(self):
        names = get_allowed_var_names('general', '')
        for key in (
            'disk_free', 'disk_used_pct', 'django_ok', 'db_ok',
            'celery_ok', 'scheduler_ok', 'system_status', 'system_status_list',
        ):
            self.assertIn(key, names)

    def test_status_sidebar_group(self):
        groups = get_sidebar_variable_groups('general', '')
        keys = [g['key'] for g in groups]
        self.assertIn('status', keys)
        status = next(g for g in groups if g['key'] == 'status')
        self.assertEqual(status['label_i18n'], 'es.vars_status')
        self.assertEqual(status['chip_class'], 'status')
        self.assertGreaterEqual(len(status['vars']), 5)


if __name__ == '__main__':
    unittest.main()
