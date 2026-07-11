import json
import importlib.util
import unittest
from unittest import mock
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "query_tool" / "utils" / "config.py"
SPEC = importlib.util.spec_from_file_location("query_tool.utils._config_test", MODULE_PATH)
CONFIG_MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CONFIG_MODULE)
AppConfig = CONFIG_MODULE.AppConfig
ConfigManager = CONFIG_MODULE.ConfigManager


class DebugCommandHistoryConfigTests(unittest.TestCase):
    def test_save_app_config_stores_debug_command_history_as_json(self):
        manager = ConfigManager()
        stored_values = {}

        def fake_set_value(key, value, *_args, **_kwargs):
            stored_values[key] = value
            return True

        with mock.patch.object(manager, "_set_value", side_effect=fake_set_value):
            manager.save_app_config(
                AppConfig(
                    debug_command_history=["cat /tmp/a.log", "ls /mnt/mmc"],
                )
            )

        self.assertEqual(
            ["cat /tmp/a.log", "ls /mnt/mmc"],
            json.loads(stored_values["debug_command_history"]),
        )

    def test_load_app_config_reads_debug_command_history(self):
        manager = ConfigManager()
        stored_values = {
            "debug_command_history": json.dumps(
                ["cat /tmp/a.log", "ls /mnt/mmc"],
                ensure_ascii=False,
            ),
        }

        with mock.patch.object(
            manager,
            "_get_value",
            side_effect=lambda key, default=None: stored_values.get(key, default),
        ):
            config = manager.load_app_config()

        self.assertEqual(
            ["cat /tmp/a.log", "ls /mnt/mmc"],
            config.debug_command_history,
        )


if __name__ == "__main__":
    unittest.main()
