import json
import unittest
from unittest import mock

from query_tool.utils.config import AppConfig, ConfigManager
from tests.test_fluent_widget_smokes import PAGES_DIR, _isolated_page_env, _load_module


def _load_log_page_class():
    with _isolated_page_env():
        module = _load_module(
            "query_tool.pages._log_page_command_config_test",
            PAGES_DIR / "log_page.py",
        )
        return module.LogPage


LogPage = _load_log_page_class()


class LogPageCommandConfigTests(unittest.TestCase):
    def test_save_app_config_stores_log_commands_as_json(self):
        manager = ConfigManager()
        stored_values = {}

        def fake_set_value(key, value, *_args, **_kwargs):
            stored_values[key] = value
            return True

        with mock.patch.object(manager, "_set_value", side_effect=fake_set_value):
            manager.save_app_config(
                AppConfig(
                    log_commands=["GetSystemCfg /tmp/a.log", "GetSystemCfg /tmp/b.log"],
                    log_commands_initialized=True,
                )
            )

        self.assertEqual(
            ["GetSystemCfg /tmp/a.log", "GetSystemCfg /tmp/b.log"],
            json.loads(stored_values["log_commands"]),
        )
        self.assertEqual("1", stored_values["log_commands_initialized"])

    def test_load_app_config_reads_json_log_commands(self):
        manager = ConfigManager()
        stored_values = {
            "log_commands": json.dumps(
                ["GetSystemCfg /tmp/a.log", "GetSystemCfg /tmp/b.log"],
                ensure_ascii=False,
            ),
            "log_commands_initialized": "1",
        }

        with mock.patch.object(
            manager,
            "_get_value",
            side_effect=lambda key, default=None: stored_values.get(key, default),
        ):
            config = manager.load_app_config()

        self.assertEqual(
            ["GetSystemCfg /tmp/a.log", "GetSystemCfg /tmp/b.log"],
            config.log_commands,
        )
        self.assertTrue(config.log_commands_initialized)

    def test_resolve_initial_command_list_uses_defaults_before_user_initialization(self):
        app_config = AppConfig(log_commands=[], log_commands_initialized=False)

        commands, should_save = LogPage._resolve_initial_command_list(app_config)

        self.assertEqual(LogPage._default_command_list(), commands)
        self.assertEqual(LogPage._default_command_list(), app_config.log_commands)
        self.assertTrue(app_config.log_commands_initialized)
        self.assertTrue(should_save)

    def test_resolve_initial_command_list_preserves_existing_custom_commands(self):
        app_config = AppConfig(
            log_commands=["GetSystemCfg /tmp/custom.log"],
            log_commands_initialized=False,
        )

        commands, should_save = LogPage._resolve_initial_command_list(app_config)

        self.assertEqual(["GetSystemCfg /tmp/custom.log"], commands)
        self.assertEqual(["GetSystemCfg /tmp/custom.log"], app_config.log_commands)
        self.assertTrue(app_config.log_commands_initialized)
        self.assertTrue(should_save)

    def test_resolve_initial_command_list_preserves_user_cleared_state(self):
        app_config = AppConfig(log_commands=[], log_commands_initialized=True)

        commands, should_save = LogPage._resolve_initial_command_list(app_config)

        self.assertEqual([], commands)
        self.assertFalse(should_save)


if __name__ == "__main__":
    unittest.main()
