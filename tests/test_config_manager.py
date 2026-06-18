import importlib.util
import unittest
from pathlib import Path
from unittest import mock


def _load_config_module():
    module_path = Path(__file__).resolve().parents[1] / "query_tool" / "utils" / "config.py"
    spec = importlib.util.spec_from_file_location("tpquerytool_config_test_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


config_module = _load_config_module()
ConfigManager = config_module.ConfigManager


class ConfigManagerTests(unittest.TestCase):
    def test_load_app_config_tolerates_legacy_bool_like_strings(self):
        values = {
            "export_path": "D:/tmp/out.csv",
            "phone_history": "13800138000|13900139000",
            "debug_shortcuts": '["cmd1"]',
            "debug_shortcuts_initialized": "True",
            "last_debug_sn": "DBG-001",
            "debug_download_path": "D:/tmp/debug",
            "last_log_sn": "LOG-001",
            "log_download_path": "D:/tmp/log",
            "log_commands": '["GetSystemCfg /mnt/nand/keylog.data"]',
            "log_commands_initialized": "False",
            "last_page_index": "True",
            "theme": "LIGHT",
            "tray_minimize_tip_shown": "yes",
        }
        manager = ConfigManager()

        with mock.patch.object(manager, "_get_value", side_effect=lambda key, default=None: values.get(key, default)):
            app_config = manager.load_app_config()

        self.assertEqual("D:/tmp/out.csv", app_config.export_path)
        self.assertEqual(["13800138000", "13900139000"], app_config.phone_history)
        self.assertEqual(["cmd1"], app_config.debug_shortcuts)
        self.assertTrue(app_config.debug_shortcuts_initialized)
        self.assertFalse(app_config.log_commands_initialized)
        self.assertEqual(1, app_config.last_page_index)
        self.assertEqual("light", app_config.theme)
        self.assertTrue(app_config.tray_minimize_tip_shown)

    def test_load_app_config_falls_back_on_invalid_integer_and_theme(self):
        manager = ConfigManager()
        values = {
            "last_page_index": "not-a-number",
            "theme": "blue",
        }

        with mock.patch.object(manager, "_get_value", side_effect=lambda key, default=None: values.get(key, default)):
            app_config = manager.load_app_config()

        self.assertEqual(0, app_config.last_page_index)
        self.assertEqual("dark", app_config.theme)


if __name__ == "__main__":
    unittest.main()
