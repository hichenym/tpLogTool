import os
import types
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication


def _ensure_app():
    return QApplication.instance() or QApplication([])


APP = _ensure_app()


class MainNavigationInteractionTests(unittest.TestCase):
    def _create_window(self):
        from query_tool.main import MainWindow
        from query_tool.pages.base_page import BasePage

        class _DummyPageA(BasePage):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.page_name = "设备"

        class _DummyPageB(BasePage):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.page_name = "错误记录"

        app_config = types.SimpleNamespace(last_page_index=1, theme="dark")
        page_configs = [
            {"class": _DummyPageA, "name": "设备", "route_key": "dummy.device", "icon": ""},
            {"class": _DummyPageB, "name": "错误记录", "route_key": "dummy.error", "icon": ""},
        ]

        patches = (
            mock.patch("query_tool.main.PageRegistry.get_all_pages", return_value=page_configs),
            mock.patch.object(MainWindow, "_setup_system_tray", lambda self: None),
            mock.patch.object(MainWindow, "load_config", lambda self: None),
            mock.patch.object(MainWindow, "center_on_screen", lambda self: None),
            mock.patch("query_tool.main.QTimer.singleShot", lambda *args, **kwargs: None),
            mock.patch("query_tool.main.count_all_tasks", lambda: 0),
            mock.patch("query_tool.main.count_running_tasks", lambda: 0),
            mock.patch("query_tool.main.list_tasks", lambda: []),
            mock.patch("query_tool.main.config_manager.load_app_config", return_value=app_config),
            mock.patch("query_tool.main.config_manager.save_app_config", lambda *_args, **_kwargs: None),
        )

        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9]:
            window = MainWindow()
        return window

    def test_navigation_click_switches_stacked_page(self):
        window = self._create_window()

        try:
            window._periodic_update_timer.stop()
            window._task_indicator_timer.stop()
            window.show()
            APP.processEvents()

            self.assertEqual(1, window.stacked_widget.currentIndex())

            QTest.mouseClick(window.page_nav_items["dummy.device"].itemWidget, Qt.LeftButton)
            APP.processEvents()

            self.assertEqual(0, window.stacked_widget.currentIndex())
        finally:
            window.close()
            window.deleteLater()
            APP.processEvents()

    def test_navigation_uses_compact_theme_labels_and_width_fits_longest_text(self):
        from query_tool.utils.theme_manager import theme_manager

        original_is_dark = theme_manager.is_dark
        try:
            theme_manager.set_dark()
            window = self._create_window()
            window._periodic_update_timer.stop()
            window._task_indicator_timer.stop()
            window.show()
            APP.processEvents()

            self.assertEqual("浅色", window.theme_nav_item.text())
            self.assertEqual(
                window._compute_navigation_expand_width(),
                window.navigation_interface.panel.expandWidth,
            )
            self.assertEqual(0, window.navigation_interface.panel.expandAni.duration())

            theme_manager.set_light()
            window._update_theme_btn_icon()
            APP.processEvents()

            self.assertEqual("深色", window.theme_nav_item.text())
        finally:
            if 'window' in locals():
                window.close()
                window.deleteLater()
                APP.processEvents()
            if original_is_dark:
                theme_manager.set_dark()
            else:
                theme_manager.set_light()


if __name__ == "__main__":
    unittest.main()
