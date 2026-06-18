import importlib.util
import unittest
from pathlib import Path

from PyQt5.QtWidgets import QSpinBox


REPO_ROOT = Path(__file__).resolve().parents[1]

MIGRATED_MODULES = [
    "query_tool/pages/device_status_page.py",
    "query_tool/pages/debug_page.py",
    "query_tool/pages/log_page.py",
    "query_tool/pages/firmware_page.py",
    "query_tool/pages/gitlab_log_page.py",
    "query_tool/pages/error_record_page.py",
    "query_tool/widgets/adaptive_dialog.py",
    "query_tool/widgets/custom_widgets.py",
    "query_tool/widgets/task_center_dialog.py",
    "query_tool/widgets/update_dialog.py",
    "query_tool/widgets/reboot_dialog.py",
    "query_tool/widgets/port_mapping_dialog.py",
    "query_tool/widgets/upgrade_dialog.py",
    "query_tool/widgets/batch_upgrade_dialog.py",
    "query_tool/widgets/batch_reboot_dialog.py",
    "query_tool/widgets/collect_type_selector_dialog.py",
    "query_tool/widgets/upgrade_stress_dialog.py",
    "query_tool/widgets/battery_collect_dialog.py",
    "query_tool/widgets/edit_firmware_dialog.py",
    "query_tool/widgets/batch_battery_collect_dialog.py",
]


def _read_source(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


class FluentArchitectureTests(unittest.TestCase):
    def test_main_window_uses_fluent_navigation_shell(self):
        source = _read_source("query_tool/main.py")

        self.assertIn("from query_tool.ui import NavigationInterface", source)
        self.assertIn("self.navigation_interface = NavigationInterface(", source)
        self.assertIn("pages.register_builtin_pages()", source)
        self.assertIn("resolve_fluent_icon", source)

    def test_migrated_modules_go_through_ui_compatibility_layer(self):
        missing = []
        for relative_path in MIGRATED_MODULES:
            if "from query_tool.ui import" not in _read_source(relative_path):
                missing.append(relative_path)

        self.assertEqual([], missing)

    def test_ui_widget_alias_keeps_qt_spinbox_backend(self):
        module_path = REPO_ROOT / "query_tool" / "ui" / "widgets.py"
        spec = importlib.util.spec_from_file_location("tpquerytool_ui_widgets_test_module", module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        self.assertIs(module.SpinBox, QSpinBox)


if __name__ == "__main__":
    unittest.main()
