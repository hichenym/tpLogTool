import os
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtTest import QSignalSpy
from PyQt5.QtWidgets import QApplication

from query_tool.pages.device_status_page import DeviceStatusPage
from query_tool.utils.config import config_manager
from query_tool.utils.workers import PhoneQueryThread


class DeviceQueryResultDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.read_patch = mock.patch.object(config_manager, '_get_value', side_effect=lambda key, default=None: default)
        self.write_patch = mock.patch.object(config_manager, '_set_value', return_value=True)
        self.read_patch.start()
        self.write_patch.start()
        self.addCleanup(self.read_patch.stop)
        self.addCleanup(self.write_patch.stop)
        self.env_patch = mock.patch.object(config_manager, '_active_environment', 'pro')
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.page = DeviceStatusPage()
        self.addCleanup(self.page.deleteLater)
        self.page.phone_input.setCurrentText('example-account')

    @staticmethod
    def results(env):
        return [
            {'env': env, 'device_name': '设备一', 'model': 'Demo', 'sn': 'SN-1', 'id': '101', 'password': 'example', 'node': 'node', 'version': 'Demo-1.0', 'online': 1, 'is_siot': True, 'last_heartbeat': '2026-11-16 12:00:00'},
            {'env': env, 'device_name': '设备二', 'model': 'Demo', 'sn': 'SN-2', 'id': '102', 'password': 'example', 'node': 'node', 'version': 'Demo-1.0', 'online': 0, 'is_siot': True, 'last_heartbeat': '2026-11-16 11:00:00'},
        ]

    def assert_delivered(self):
        self.assertEqual(2, self.page.result_table.rowCount())
        self.assertEqual('SN-1', self.page.result_table.item(0, 3).text())
        self.assertEqual('SN-2', self.page.result_table.item(1, 3).text())
        self.assertEqual(2, self.page.total_count)
        self.assertTrue(self.page.phone_query_btn.isEnabled())
        self.assertEqual('账号查询', self.page.phone_query_btn.text())
        self.assertIn('2 / 2', self.page.match_count_label.text())

    def test_formal_account_results_update_table_and_restore_button(self):
        self.page.phone_query_btn.setEnabled(False)
        self.page.phone_query_btn.setText('查询中...')
        self.page.on_phone_query_success(self.results('pro'), ['Demo'])
        self.assert_delivered()

    def test_test_platform_account_results_update_table_and_restore_button(self):
        config_manager.set_active_environment('test')
        self.page.phone_query_btn.setEnabled(False)
        self.page.phone_query_btn.setText('查询中...')
        self.page.on_phone_query_success(self.results('test'), ['Demo'])
        self.assert_delivered()

    def test_account_thread_success_signal_reaches_real_table(self):
        thread = PhoneQueryThread('example-account', 'pro', 'example-user', 'example-password')
        thread.success.connect(self.page.on_phone_query_success)
        self.page.phone_query_btn.setEnabled(False)
        thread.success.emit(self.results('pro'), ['Demo'])
        self.app.processEvents()
        self.assert_delivered()

    def test_single_device_result_with_platform_is_rendered(self):
        self.page.total_count = 1
        self.page.on_query_init_success()
        self.page.on_single_result(0, self.results('pro')[0])
        self.assertEqual('SN-1', self.page.result_table.item(0, 3).text())

    def test_results_from_other_platform_are_ignored(self):
        config_manager.set_active_environment('test')
        self.page.on_phone_query_success(self.results('pro'), ['Demo'])
        self.assertEqual(0, self.page.result_table.rowCount())

    def test_platform_change_resets_finished_account_query_button(self):
        self.page.phone_query_btn.setEnabled(False)
        self.page.phone_query_btn.setText('查询中...')
        config_manager.set_active_environment('test')
        self.page.on_environment_changed('test')
        self.assertTrue(self.page.phone_query_btn.isEnabled())
        self.assertEqual('账号查询', self.page.phone_query_btn.text())

    def test_empty_account_results_restore_button(self):
        self.page.phone_query_btn.setEnabled(False)
        self.page.phone_query_btn.setText('查询中...')
        self.page.on_phone_query_success([], [])
        self.assertTrue(self.page.phone_query_btn.isEnabled())
        self.assertEqual('账号查询', self.page.phone_query_btn.text())
        self.assertEqual(0, self.page.result_table.rowCount())

    def test_none_result_uses_existing_error_handler(self):
        messages = QSignalSpy(self.page.status_message)
        self.page.on_single_result(0, None)
        self.assertTrue(messages)
        self.assertIn('数据为空', messages[-1][0])


if __name__ == '__main__':
    unittest.main()
