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
    _fmt_uptime,
    _aggregate,
    _status_html_rows,
    _OK,
    _FAIL,
    _WARN,
    _NA,
)

STATUS_KEYS_CORE = (
    'disk_free', 'disk_used_pct', 'django_ok', 'db_ok',
    'celery_ok', 'scheduler_ok', 'system_status', 'system_status_list',
)
STATUS_KEYS_S2 = (
    'host_name', 'load_avg', 'uptime', 'memory_used_pct',
    'django_version', 'portal_env', 'cache_ok',
)
STATUS_KEYS_S3 = (
    'celery_workers', 'celery_queue_depth', 'system_status_html',
)
STATUS_KEYS_S4 = (
    'smtp_ok', 'smtp_host', 'pbx_ok', 'pbx_host', 'meetme_ok',
)


class SystemStatusServiceTest(unittest.TestCase):

    def setUp(self):
        clear_system_status_cache()

    def test_fmt_bytes(self):
        self.assertEqual(_fmt_bytes(512), '512 B')
        self.assertEqual(_fmt_bytes(2048), '2.0 KB')
        self.assertIn('GB', _fmt_bytes(3 * 1024 ** 3))

    def test_fmt_uptime(self):
        self.assertEqual(_fmt_uptime(90), '1m')
        self.assertEqual(_fmt_uptime(3700), '1h 1m')
        self.assertEqual(_fmt_uptime(90000), '1d 1h')

    def test_aggregate(self):
        self.assertEqual(_aggregate(_OK, _OK), _OK)
        self.assertEqual(_aggregate(_OK, _WARN), _WARN)
        self.assertEqual(_aggregate(_OK, _FAIL), _FAIL)
        self.assertEqual(_aggregate(_NA, _NA), _NA)
        self.assertEqual(_aggregate(_OK, _NA), _OK)

    def test_status_html_contains_ampel(self):
        html = _status_html_rows([('Disk', '12 GB', _OK), ('Cache', 'x', _FAIL)])
        self.assertIn('<table', html)
        self.assertIn('Disk', html)
        self.assertIn('#15803d', html)
        self.assertIn('#b91c1c', html)

    @patch('apps.abpe_email_studio.services.system_status._check_meetme', return_value=_OK)
    @patch(
        'apps.abpe_email_studio.services.system_status._check_pbx',
        return_value=(_OK, 'pbx:5038'),
    )
    @patch(
        'apps.abpe_email_studio.services.system_status._check_smtp',
        return_value=(_OK, 'smtp.example.de'),
    )
    @patch('apps.abpe_email_studio.services.system_status._celery_queue_depth', return_value='3')
    @patch('apps.abpe_email_studio.services.system_status._check_scheduler', return_value=_OK)
    @patch(
        'apps.abpe_email_studio.services.system_status._check_celery',
        return_value=(_OK, '2'),
    )
    @patch('apps.abpe_email_studio.services.system_status._check_cache', return_value=_OK)
    @patch('apps.abpe_email_studio.services.system_status._check_db', return_value=_OK)
    @patch('apps.abpe_email_studio.services.system_status._portal_env', return_value='production')
    @patch('apps.abpe_email_studio.services.system_status._django_version', return_value='5.0.7')
    @patch('apps.abpe_email_studio.services.system_status._uptime', return_value='2d 3h')
    @patch(
        'apps.abpe_email_studio.services.system_status._memory_used_pct',
        return_value=('55%', _OK),
    )
    @patch(
        'apps.abpe_email_studio.services.system_status._load_avg',
        return_value=('0.10 0.20 0.30', _OK),
    )
    @patch('apps.abpe_email_studio.services.system_status._host_name', return_value='ucs5')
    @patch(
        'apps.abpe_email_studio.services.system_status._check_disk',
        return_value=('12.4 GB', '67%', _OK),
    )
    def test_collect_keys(self, *_mocks):
        clear_system_status_cache()
        data = collect_system_status(use_cache=False)
        for key in STATUS_KEYS_CORE + STATUS_KEYS_S2 + STATUS_KEYS_S3 + STATUS_KEYS_S4:
            self.assertIn(key, data, msg=key)
            self.assertIsInstance(data[key], str)
        self.assertEqual(data['disk_free'], '12.4 GB')
        self.assertEqual(data['host_name'], 'ucs5')
        self.assertEqual(data['celery_workers'], '2')
        self.assertEqual(data['celery_queue_depth'], '3')
        self.assertEqual(data['smtp_ok'], _OK)
        self.assertEqual(data['smtp_host'], 'smtp.example.de')
        self.assertEqual(data['pbx_ok'], _OK)
        self.assertEqual(data['meetme_ok'], _OK)
        self.assertTrue(data['system_status'].startswith(_OK))
        self.assertIn('(', data['system_status'])  # z.B. OK (11/11)
        self.assertIn('SMTP', data['system_status_list'])
        self.assertIn('\n', data['system_status_list'])
        self.assertIn('MeetMe', data['system_status_html'])
        self.assertIn('<table', data['system_status_html'])

    @patch('apps.abpe_email_studio.services.system_status._check_meetme', return_value=_NA)
    @patch(
        'apps.abpe_email_studio.services.system_status._check_pbx',
        return_value=(_NA, _NA),
    )
    @patch(
        'apps.abpe_email_studio.services.system_status._check_smtp',
        return_value=(_OK, 'smtp'),
    )
    @patch('apps.abpe_email_studio.services.system_status._celery_queue_depth', return_value='0')
    @patch('apps.abpe_email_studio.services.system_status._check_scheduler', return_value=_OK)
    @patch(
        'apps.abpe_email_studio.services.system_status._check_celery',
        return_value=(_OK, '1'),
    )
    @patch('apps.abpe_email_studio.services.system_status._check_cache', return_value=_OK)
    @patch('apps.abpe_email_studio.services.system_status._check_db', return_value=_OK)
    @patch('apps.abpe_email_studio.services.system_status._portal_env', return_value='production')
    @patch('apps.abpe_email_studio.services.system_status._django_version', return_value='5.0')
    @patch('apps.abpe_email_studio.services.system_status._uptime', return_value='1h')
    @patch(
        'apps.abpe_email_studio.services.system_status._memory_used_pct',
        return_value=('10%', _OK),
    )
    @patch(
        'apps.abpe_email_studio.services.system_status._load_avg',
        return_value=('0.01 0.01 0.01', _OK),
    )
    @patch('apps.abpe_email_studio.services.system_status._host_name', return_value='host')
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

    def test_pbx_na_without_config(self):
        from apps.abpe_email_studio.services import system_status as ss
        with patch.object(ss, '_pbx_endpoint', return_value=None):
            ok, host = ss._check_pbx()
        self.assertEqual(ok, _NA)
        self.assertEqual(host, _NA)

    def test_aggregate_ignores_na_services(self):
        self.assertEqual(_aggregate(_OK, _NA, _OK), _OK)
        self.assertEqual(_aggregate(_OK, _FAIL, _NA), _FAIL)


class PreviewSystemStatusMergeTest(unittest.TestCase):
    """render_preview: System-Werte müssen Expand-Fallback [key] überschreiben."""

    def test_expand_then_system_vars_win(self):
        merged = {'disk_free': '[disk_free]', 'name': 'Max'}
        system = {
            'portal_url': 'https://example.test',
            'date': '18.07.2026',
            'year': '2026',
            'disk_free': '12.4 GB',
            'system_status': 'OK',
        }
        all_vars = {**merged, **system, 'subject': 'x'}
        self.assertEqual(all_vars['disk_free'], '12.4 GB')
        self.assertEqual(all_vars['system_status'], 'OK')
        self.assertEqual(all_vars['name'], 'Max')

        broken = {**system, **merged, 'subject': 'x'}
        self.assertEqual(broken['disk_free'], '[disk_free]')


class SystemStatusRegistryTest(unittest.TestCase):

    def test_status_in_group_order(self):
        self.assertIn('status', GROUP_ORDER)
        self.assertLess(GROUP_ORDER.index('system'), GROUP_ORDER.index('status'))

    def test_status_vars_visible(self):
        names = get_allowed_var_names('general', '')
        for key in STATUS_KEYS_CORE + STATUS_KEYS_S2 + STATUS_KEYS_S3 + STATUS_KEYS_S4:
            self.assertIn(key, names, msg=key)

    def test_status_sidebar_group(self):
        groups = get_sidebar_variable_groups('general', '')
        keys = [g['key'] for g in groups]
        self.assertIn('status', keys)
        status = next(g for g in groups if g['key'] == 'status')
        self.assertEqual(status['label_i18n'], 'es.vars_status')
        self.assertEqual(status['chip_class'], 'status')
        self.assertGreaterEqual(len(status['vars']), 20)


if __name__ == '__main__':
    unittest.main()
