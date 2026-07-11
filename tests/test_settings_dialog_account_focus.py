import unittest

from tests.gui_module_test_helper import load_custom_widgets_module


custom_widgets = load_custom_widgets_module()
SettingsDialog = custom_widgets.SettingsDialog


class _FakeTabWidget:
    def __init__(self):
        self.current_index = None

    def setCurrentIndex(self, index):
        self.current_index = index


class _FakeScrollBar:
    def __init__(self):
        self.value = None

    def setValue(self, value):
        self.value = value


class _FakeScrollArea:
    def __init__(self):
        self._scroll_bar = _FakeScrollBar()

    def verticalScrollBar(self):
        return self._scroll_bar


class _FakeGroup:
    def __init__(self, y_pos):
        self._y_pos = y_pos

    def y(self):
        return self._y_pos


class _FakeInput:
    def __init__(self):
        self.focus_reason = None
        self.selected = False

    def setFocus(self, reason):
        self.focus_reason = reason

    def selectAll(self):
        self.selected = True


class SettingsDialogAccountFocusTests(unittest.TestCase):
    def test_focus_target_account_group_scrolls_and_focuses_username(self):
        username_input = _FakeInput()
        dialog = type("DialogStub", (), {})()
        dialog.target_account_type = "firmware"
        dialog._target_account_scroll_scheduled = True
        dialog.tab_widget = _FakeTabWidget()
        dialog.account_group_widgets = {"firmware": _FakeGroup(88)}
        dialog.account_username_inputs = {"firmware": username_input}
        dialog.account_scroll_area = _FakeScrollArea()

        SettingsDialog.focus_target_account_group(dialog)

        self.assertEqual(0, dialog.tab_widget.current_index)
        self.assertEqual(76, dialog.account_scroll_area.verticalScrollBar().value)
        self.assertIsNotNone(username_input.focus_reason)
        self.assertTrue(username_input.selected)


if __name__ == "__main__":
    unittest.main()
