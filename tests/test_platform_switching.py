import base64
import os
import types
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtTest import QSignalSpy, QTest
from PyQt5.QtWidgets import QApplication

from query_tool.utils import config
from query_tool.utils.config import AccountConfig, SeetongAccountConfig
from query_tool.utils.environment import cloud_endpoints
from query_tool.utils.siot_debug import session
from query_tool.utils.siot_debug.models import CloudCredentials, DeviceCredentials
from query_tool.widgets import custom_widgets
from query_tool.widgets.environment_switch import EnvironmentSwitch


class MemoryConfig(config.ConfigManager):
    def __init__(self, values=None):
        super().__init__()
        self.values = dict(values or {})

    def _get_value(self, key, default=None):
        return self.values.get(key, default)

    def _set_value(self, key, value, value_type=None):
        self.values[key] = value
        return True


class PlatformConfigTests(unittest.TestCase):
    def test_legacy_formal_accounts_are_not_used_for_test(self):
        encoded = base64.b64encode(b'legacy-password').decode()
        manager = MemoryConfig({'account_username': 'formal-user', 'account_password': encoded, 'seetong_username': 'formal-cloud', 'seetong_password': encoded})
        self.assertEqual('formal-user', manager.load_account_config('pro').username)
        self.assertEqual('formal-cloud', manager.load_seetong_account_config('pro').username)
        self.assertEqual('', manager.load_account_config('test').username)
        self.assertEqual('', manager.load_seetong_account_config('test').username)

    def test_platform_profiles_and_active_selection_are_independent(self):
        manager = MemoryConfig()
        for env in ('pro', 'test'):
            self.assertTrue(manager.save_account_config(AccountConfig(env, env + '-admin', env + '-password')))
            self.assertTrue(manager.save_seetong_account_config(SeetongAccountConfig(env + '-cloud', env + '-password', env)))
        self.assertEqual('pro', manager.get_active_environment())
        manager.set_active_environment('test')
        self.assertEqual('test-admin', manager.load_account_config().username)
        self.assertEqual('test-cloud', manager.load_seetong_account_config().username)
        self.assertEqual('pro-admin', manager.load_account_config('pro').username)
        self.assertEqual('test', MemoryConfig(manager.values).get_active_environment())

    def test_first_start_defaults_to_formal_without_using_legacy_account_env(self):
        manager = MemoryConfig({'account_env': 'test', 'env': 'test'})
        self.assertEqual('pro', manager.get_active_environment())

    def test_invalid_saved_environment_falls_back_to_formal(self):
        manager = MemoryConfig({'active_environment': 'invalid'})
        self.assertEqual('pro', manager.get_active_environment())

    def test_environment_write_failure_keeps_current_selection(self):
        manager = MemoryConfig({'active_environment': 'pro'})
        self.assertEqual('pro', manager.get_active_environment())
        with mock.patch.object(manager, '_set_value', return_value=False):
            self.assertFalse(manager.set_active_environment('test'))
        self.assertEqual('pro', manager.get_active_environment())
        self.assertEqual('pro', manager.values['active_environment'])

    def test_switch_back_to_formal_is_restored_after_restart(self):
        manager = MemoryConfig({'active_environment': 'test'})
        self.assertTrue(manager.set_active_environment('pro'))
        self.assertEqual('pro', MemoryConfig(manager.values).get_active_environment())

    def test_legacy_test_profile_survives_saving_formal_profile(self):
        manager = MemoryConfig({'account_env': 'test', 'account_username': 'old-test', 'account_password': base64.b64encode(b'old-password').decode()})
        manager.save_account_config(AccountConfig('pro', 'formal', 'password'))
        self.assertEqual('old-test', manager.load_account_config('test').username)

    def test_cleared_profile_does_not_fall_back_to_legacy_values(self):
        manager = MemoryConfig({'account_username': 'old-formal'})
        manager.save_account_config(AccountConfig('pro', '', ''))
        self.assertEqual('', manager.load_account_config('pro').username)

    def test_write_failure_is_reported(self):
        manager = MemoryConfig()
        with mock.patch.object(manager, '_set_value', return_value=False):
            self.assertFalse(manager.save_account_config(AccountConfig('test', 'user', 'password')))

    def test_cloud_cache_is_scoped_by_platform_even_for_same_account(self):
        manager = MemoryConfig()
        for env in ('pro', 'test'):
            manager.save_seetong_cloud_cache('same-user', 'same-password', {'access_node': env + '-node'}, env=env)
        self.assertEqual('pro-node', manager.load_seetong_cloud_cache('same-user', 'same-password', 60, env='pro')['access_node'])
        self.assertEqual('test-node', manager.load_seetong_cloud_cache('same-user', 'same-password', 60, env='test')['access_node'])


class PlatformWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.manager = MemoryConfig()
        self.config_patch = mock.patch.object(config, 'config_manager', self.manager)
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)

    def make_dialog(self):
        dialog = custom_widgets.SettingsDialog()
        self.addCleanup(dialog.close)
        self.addCleanup(dialog.deleteLater)
        return dialog

    def test_switch_default_labels_keyboard_and_silent_reset(self):
        widget = EnvironmentSwitch()
        self.addCleanup(widget.close)
        spy = QSignalSpy(widget.environment_changed)
        self.assertEqual('正式', widget.text())
        QTest.keyClick(widget, Qt.Key_Right)
        self.assertEqual('测试', widget.text())
        self.assertEqual('test', spy[0][0])
        widget.set_environment('pro')
        self.assertEqual(1, len(spy))
        self.assertEqual(0, widget.thumb_position)

    def test_switch_can_be_dragged_to_test(self):
        widget = EnvironmentSwitch()
        self.addCleanup(widget.close)
        widget.show()
        QTest.mousePress(widget, Qt.LeftButton, pos=QPoint(14, 14))
        QTest.mouseMove(widget, QPoint(widget.width() - 14, 14))
        QTest.mouseRelease(widget, Qt.LeftButton, pos=QPoint(widget.width() - 14, 14))
        self.assertEqual('test', widget.environment())

    def test_compact_switch_has_round_thumb_and_text_beside_it(self):
        widget = EnvironmentSwitch()
        self.addCleanup(widget.close)
        self.assertEqual(52, widget.width())
        self.assertEqual(28, widget.height())
        thumb = widget._thumb_rect()
        self.assertEqual(thumb.width(), thumb.height())
        self.assertGreater(widget._text_rect().left(), thumb.right())
        widget.set_environment('test')
        self.assertEqual('测试', widget.text())
        self.assertLess(widget._text_rect().right(), widget._thumb_rect().left())

    def test_compact_account_switch_has_the_same_width(self):
        dialog = self.make_dialog()
        for widget in dialog.account_switches.values():
            self.assertEqual(52, widget.width())
            self.assertEqual(28, widget.height())
            thumb = widget._thumb_rect()
            self.assertEqual(thumb.width(), thumb.height())

    def test_small_switch_text_fits_and_visual_size_matches_toolbar_icons(self):
        from PyQt5.QtGui import QFontMetrics
        widget = EnvironmentSwitch()
        self.addCleanup(widget.close)
        self.assertEqual(18, widget._track_rect().height())
        self.assertLessEqual(widget._thumb_rect().width(), 18)
        metrics = QFontMetrics(widget._text_font())
        for env in ('pro', 'test'):
            widget.set_environment(env)
            self.assertLessEqual(metrics.horizontalAdvance(widget.text()), widget._text_rect().width())

    def test_platform_colors_use_teal_for_formal_and_muted_red_for_test(self):
        from query_tool.utils.theme_manager import DARK_THEME, LIGHT_THEME, theme_manager
        widget = EnvironmentSwitch()
        self.addCleanup(widget.close)
        for tokens in (DARK_THEME, LIGHT_THEME):
            with mock.patch.object(theme_manager, '_tokens', tokens):
                widget.set_environment('pro')
                self.assertEqual(tokens['accent_dim'], widget._track_color().name())
                widget.set_environment('test')
                self.assertEqual(tokens['platform_test_bg'], widget._track_color().name())
                self.assertNotEqual(tokens['status_offline'].lower(), widget._track_color().name())

    def test_account_switches_preserve_drafts_and_do_not_switch_application(self):
        dialog = self.make_dialog()
        dialog.device_username_input.setText('formal-draft')
        dialog.device_password_input.setText('formal-password')
        dialog.account_switches['device'].click()
        self.assertEqual('', dialog.device_username_input.text())
        dialog.device_username_input.setText('test-draft')
        dialog.device_password_input.setText('test-password')
        dialog.account_switches['device'].click()
        self.assertEqual('formal-draft', dialog.device_username_input.text())
        dialog.account_switches['device'].click()
        self.assertEqual('test-draft', dialog.device_username_input.text())
        self.assertEqual('pro', dialog.account_environments['seetong'])
        self.assertEqual('pro', self.manager.get_active_environment())

    def test_save_writes_both_profiles_and_keeps_active_environment(self):
        dialog = self.make_dialog()
        for account_type in ('device', 'seetong'):
            dialog.account_username_inputs[account_type].setText('formal-' + account_type)
            dialog.account_password_inputs[account_type].setText('formal-password')
            dialog.account_switches[account_type].click()
            dialog.account_username_inputs[account_type].setText('test-' + account_type)
            dialog.account_password_inputs[account_type].setText('test-password')
        with mock.patch('query_tool.utils.data_sync.sync_user_version'):
            dialog.on_save()
        self.assertEqual('formal-device', self.manager.load_account_config('pro').username)
        self.assertEqual('test-device', self.manager.load_account_config('test').username)
        self.assertEqual('test-seetong', self.manager.load_seetong_account_config('test').username)
        self.assertEqual('pro', self.manager.get_active_environment())

    def test_seetong_validation_uses_the_card_platform(self):
        dialog = self.make_dialog()
        dialog.account_switches['seetong'].click()
        dialog.seetong_username_input.setText('test-user')
        dialog.seetong_password_input.setText('test-password')
        from PyQt5.QtWidgets import QPushButton
        with mock.patch('query_tool.utils.siot_debug.validate_seetong_login', return_value=(True, 'ok')) as validate:
            dialog.on_test_account_connection(dialog.seetong_username_input, dialog.seetong_password_input, 'seetong', QPushButton('验证'))
        validate.assert_called_once_with('test-user', 'test-password', env='test')

    def test_missing_account_prompts_name_the_active_platform(self):
        self.manager.set_active_environment('test')
        prompt = custom_widgets._resolve_account_prompt_copy('device')
        self.assertIn('测试平台运维账号', prompt['text'])
        self.assertIn('测试平台Seetong账号', custom_widgets._resolve_account_prompt_copy('seetong')['title'])
        self.assertNotIn('测试平台', custom_widgets._resolve_account_prompt_copy('firmware')['text'])


class PlatformRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_main_switch_blocks_running_connections_and_clears_idle_pages(self):
        from query_tool import main
        manager = MemoryConfig()
        page = types.SimpleNamespace(is_environment_busy=mock.Mock(return_value=True), on_environment_changed=mock.Mock(), on_page_show=mock.Mock())
        widget = EnvironmentSwitch()
        window = types.SimpleNamespace(environment_switch=widget, pages=[page], findChildren=lambda kind: [], stacked_widget=types.SimpleNamespace(currentIndex=lambda: 0), setWindowTitle=mock.Mock(), on_page_status_message=mock.Mock())
        with mock.patch.object(main, 'config_manager', manager), mock.patch.object(main, 'count_running_tasks', return_value=0):
            main.MainWindow.on_environment_changed(window, 'test')
            self.assertEqual('pro', manager.get_active_environment())
            page.on_environment_changed.assert_not_called()
            page.is_environment_busy.return_value = False
            main.MainWindow.on_environment_changed(window, 'test')
        self.assertEqual('test', manager.get_active_environment())
        page.on_environment_changed.assert_called_once_with('test')
        widget.close()

    def test_main_switch_does_not_apply_selection_when_registry_write_fails(self):
        from query_tool import main
        manager = MemoryConfig({'active_environment': 'pro'})
        page = types.SimpleNamespace(is_environment_busy=lambda: False, on_environment_changed=mock.Mock())
        widget = EnvironmentSwitch(env='test')
        window = types.SimpleNamespace(environment_switch=widget, pages=[page], findChildren=lambda kind: [], on_page_status_message=mock.Mock())
        with mock.patch.object(main, 'config_manager', manager), mock.patch.object(main, 'count_running_tasks', return_value=0), mock.patch.object(manager, '_set_value', return_value=False):
            main.MainWindow.on_environment_changed(window, 'test')
        self.assertEqual('pro', manager.get_active_environment())
        self.assertEqual('pro', widget.environment())
        page.on_environment_changed.assert_not_called()
        self.assertEqual('error', window.on_page_status_message.call_args.args[1])
        widget.close()

    def test_metadata_thread_keeps_its_starting_environment(self):
        from query_tool.utils import error_record_api
        manager = MemoryConfig()
        manager.set_active_environment('test')
        with mock.patch.object(config, 'config_manager', manager):
            thread = error_record_api.MetaLoadThread()
            manager.set_active_environment('pro')
            with mock.patch.object(error_record_api, '_make_device_query') as query, mock.patch.object(error_record_api, 'fetch_model_list', return_value={}), mock.patch.object(error_record_api, 'fetch_module_list', return_value=[]):
                thread.run()
            query.assert_called_once_with('test')

    def test_sleeping_device_helper_receives_assigned_nodes_without_cloud_password(self):
        client = session.DeviceSession.__new__(session.DeviceSession)
        client.device = DeviceCredentials('SN', 'admin', 'password', env='test')
        client.cloud_credentials = CloudCredentials('client', 'test-signal:24201', 'access', 'relay', 'relay-list', 'vip-list', 3, env='test')
        client._device_is_4g = True
        client._gateway_id_4g = 'test-gateway'
        client._gateway_id = ''
        params = client._build_prepare_params()
        self.assertEqual('test-signal:24201', params['access_node'])
        self.assertEqual('test-gateway', params['gateway_id'])
        self.assertEqual('access', params['access_token'])
        self.assertEqual('vip-list', params['vip_relay_nodes'])
        self.assertNotIn('cloud_username', params)
        self.assertNotIn('cloud_password', params)

    def test_sleeping_device_helper_rejects_a_different_platform(self):
        client = session.DeviceSession.__new__(session.DeviceSession)
        client.device = DeviceCredentials('SN', 'admin', 'password', env='test')
        client.cloud_credentials = CloudCredentials('client', 'formal-node', 'access', 'relay', '', '', 3)
        with self.assertRaises(session.SiotError):
            client._build_prepare_params()

    def test_test_login_and_assigned_node_are_used_without_hardcoding(self):
        response = {'code': 200, 'data': {'accessNode': 'assigned-test-host:24201', 'accessJwtToken': 'test-access', 'signKeyVer': 3}}
        with mock.patch.object(session, '_http_post', return_value={'code': 200, 'access_token': 'test-token'}) as login, mock.patch.object(session, '_http_get', return_value=response) as access, mock.patch.object(session, 'save_cached_cloud_credentials') as save:
            credentials = session.fetch_cloud_credentials('test-user', 'test-password', force_refresh=True, env='test')
        self.assertEqual(cloud_endpoints('test')[0], login.call_args.args[0])
        self.assertEqual(cloud_endpoints('test')[1], access.call_args.args[0])
        self.assertEqual('assigned-test-host:24201', credentials.access_node)
        self.assertEqual('test', credentials.env)
        self.assertEqual('test', save.call_args.kwargs['env'])

    def test_formal_prefetch_is_not_reused_for_test_device(self):
        client = session.DeviceSession.__new__(session.DeviceSession)
        client.device = DeviceCredentials('SN', 'admin', 'password', env='test')
        client.cloud_username = 'user'
        client.cloud_password = 'password'
        client._prefetched_cloud_credentials = CloudCredentials('client', 'formal-node', 'access', 'relay', '', '', 1)
        test_credentials = CloudCredentials('client', 'test-node', 'access', 'relay', '', '', 1, env='test')
        with mock.patch.object(session, 'fetch_cloud_credentials', return_value=test_credentials) as fetch:
            resolved = client._load_cloud_credentials_for_connect(False)
        self.assertIs(test_credentials, resolved)
        self.assertEqual('test', fetch.call_args.kwargs['env'])

    def test_idle_debug_listener_does_not_block_switching(self):
        from query_tool.pages.base_page import BasePage
        page = types.SimpleNamespace(worker_thread=types.SimpleNamespace(isRunning=lambda: True))
        self.assertFalse(BasePage.is_environment_busy(page))
        page.connected = True
        self.assertTrue(BasePage.is_environment_busy(page))

    def test_metadata_completion_pending_keeps_switching_blocked(self):
        from query_tool.pages.base_page import BasePage
        page = types.SimpleNamespace(_meta_loading=True)
        self.assertTrue(BasePage.is_environment_busy(page))

    def test_delayed_old_thread_cleanup_keeps_new_thread(self):
        from query_tool.utils.thread_manager import ThreadManager
        manager = ThreadManager()
        old_thread = object()
        new_thread = object()
        manager.threads['meta'] = old_thread
        callbacks = []
        with mock.patch('query_tool.utils.thread_manager.QTimer.singleShot', side_effect=lambda delay, callback: callbacks.append(callback)):
            manager._on_thread_finished('meta', old_thread)
        manager.threads['meta'] = new_thread
        callbacks[0]()
        self.assertIs(new_thread, manager.threads['meta'])

    def test_battery_token_refresh_keeps_the_original_platform(self):
        from query_tool.utils.data_collect_api import DataCollectThread
        from query_tool.utils import device_query
        manager = MemoryConfig()
        manager.save_account_config(AccountConfig('pro', 'formal-user', 'formal-password'))
        manager.save_account_config(AccountConfig('test', 'test-user', 'test-password'))
        with mock.patch.object(config, 'config_manager', manager):
            thread = DataCollectThread('SN', 'ID', 'battery', '', '', 'old-token', 'console.seetong.com')
            manager.set_active_environment('test')
            with mock.patch.object(device_query, 'DeviceQuery', return_value=types.SimpleNamespace(init_error=None, token='new-token')) as query:
                self.assertEqual('new-token', thread._refresh_token())
            query.assert_called_once_with('pro', 'formal-user', 'formal-password', use_cache=False)


if __name__ == '__main__':
    unittest.main()
