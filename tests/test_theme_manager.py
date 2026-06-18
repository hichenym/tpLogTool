import importlib.util
import unittest
from pathlib import Path
from unittest import mock


def _load_theme_manager_module():
    module_path = Path(__file__).resolve().parents[1] / "query_tool" / "utils" / "theme_manager.py"
    spec = importlib.util.spec_from_file_location("tpquerytool_theme_manager_test_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


theme_manager_module = _load_theme_manager_module()
LIGHT_THEME = theme_manager_module.LIGHT_THEME
theme_manager = theme_manager_module.theme_manager


class ThemeManagerTests(unittest.TestCase):
    def setUp(self):
        self.original_is_dark = theme_manager._is_dark
        self.original_tokens = dict(theme_manager._tokens)

    def tearDown(self):
        theme_manager._is_dark = self.original_is_dark
        theme_manager._tokens = dict(self.original_tokens)

    def test_initialize_updates_tokens_and_skips_theme_changed_signal(self):
        events = []
        callback = lambda: events.append(True)
        theme_manager.theme_changed.connect(callback)
        try:
            with mock.patch.object(theme_manager, "_sync_fluent_theme") as sync_theme:
                theme_manager.initialize("light", lazy=False)

            self.assertFalse(theme_manager.is_dark)
            self.assertEqual(LIGHT_THEME, theme_manager._tokens)
            self.assertEqual([], events)
            sync_theme.assert_called_once_with(lazy=False)
        finally:
            theme_manager.theme_changed.disconnect(callback)


if __name__ == "__main__":
    unittest.main()
