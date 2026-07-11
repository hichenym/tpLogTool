import unittest
from types import SimpleNamespace

from tests.gui_module_test_helper import load_log_page


LogPage = load_log_page()


class _FakeToggle:
    def __init__(self, checked=False, enabled=True):
        self.checked = checked
        self.enabled = enabled

    def setChecked(self, checked):
        self.checked = bool(checked)

    def isChecked(self):
        return self.checked

    def setEnabled(self, enabled):
        self.enabled = bool(enabled)


class _FakeButton:
    def __init__(self, enabled=True):
        self.enabled = enabled

    def setEnabled(self, enabled):
        self.enabled = bool(enabled)


class _FakeLabel:
    def __init__(self, text="", visible=True):
        self.text = text
        self.visible = visible

    def setText(self, text):
        self.text = text

    def setVisible(self, visible):
        self.visible = bool(visible)


class _FakeDetailView:
    def __init__(self):
        self.cleared = False

    def clear(self):
        self.cleared = True


class _FakeTable:
    def __init__(self, row_count=0):
        self._row_count = row_count
        self.selection_cleared = False

    def rowCount(self):
        return self._row_count

    def setRowCount(self, row_count):
        self._row_count = row_count

    def clearSelection(self):
        self.selection_cleared = True


class _FakeInput:
    def __init__(self):
        self.enabled = True
        self.read_only = False

    def setEnabled(self, enabled):
        self.enabled = bool(enabled)

    def setReadOnly(self, read_only):
        self.read_only = bool(read_only)


class LogPageResetResultsTests(unittest.TestCase):
    def test_reset_result_view_clears_result_area_state(self):
        page = SimpleNamespace(
            _row_map={"SN001": 0},
            _device_payloads={"SN001": {"status": "完成"}},
            fetch_running=False,
            _result_checkbox_updating=False,
            result_table=_FakeTable(row_count=2),
            summary_label=_FakeLabel(text="执行完成", visible=True),
            detail_header_label=_FakeLabel(text="设备执行详情", visible=True),
            detail_view=_FakeDetailView(),
            result_select_all_checkbox=_FakeToggle(checked=True, enabled=True),
            result_corner_checkbox=_FakeToggle(checked=True, enabled=True),
            result_selection_label=_FakeLabel(text="已选 1 / 2"),
            retry_btn=_FakeButton(enabled=True),
            reset_btn=_FakeButton(enabled=True),
            _selected_result_rows=lambda: [],
            _get_selected_retryable_sns=lambda: [],
            _apply_result_column_widths=lambda: None,
        )
        page._update_result_selection_state = lambda: LogPage._update_result_selection_state(page)

        LogPage._reset_result_view(page)

        self.assertEqual({}, page._row_map)
        self.assertEqual({}, page._device_payloads)
        self.assertEqual(0, page.result_table.rowCount())
        self.assertTrue(page.result_table.selection_cleared)
        self.assertTrue(page.detail_view.cleared)
        self.assertEqual("等待开始", page.summary_label.text)
        self.assertFalse(page.summary_label.visible)
        self.assertEqual("设备执行详情", page.detail_header_label.text)
        self.assertFalse(page.detail_header_label.visible)
        self.assertFalse(page.result_select_all_checkbox.isChecked())
        self.assertFalse(page.result_corner_checkbox.isChecked())
        self.assertFalse(page.result_select_all_checkbox.enabled)
        self.assertFalse(page.result_corner_checkbox.enabled)
        self.assertEqual("未选择设备", page.result_selection_label.text)
        self.assertFalse(page.retry_btn.enabled)
        self.assertFalse(page.reset_btn.enabled)

    def test_update_result_selection_state_enables_reset_when_has_results(self):
        page = SimpleNamespace(
            fetch_running=False,
            _result_checkbox_updating=False,
            result_table=_FakeTable(row_count=2),
            result_select_all_checkbox=_FakeToggle(checked=False, enabled=False),
            result_corner_checkbox=_FakeToggle(checked=False, enabled=False),
            result_selection_label=_FakeLabel(),
            retry_btn=_FakeButton(enabled=False),
            reset_btn=_FakeButton(enabled=False),
            _selected_result_rows=lambda: [],
            _get_selected_retryable_sns=lambda: [],
        )

        LogPage._update_result_selection_state(page)

        self.assertTrue(page.result_select_all_checkbox.enabled)
        self.assertTrue(page.result_corner_checkbox.enabled)
        self.assertEqual("已选 0 / 2", page.result_selection_label.text)
        self.assertFalse(page.retry_btn.enabled)
        self.assertTrue(page.reset_btn.enabled)

    def test_set_running_state_disables_reset_until_execution_finishes(self):
        checkbox_enabled = []
        page = SimpleNamespace(
            fetch_btn=_FakeButton(enabled=False),
            choose_download_path_btn=_FakeButton(enabled=True),
            command_edit_btn=_FakeButton(enabled=True),
            command_input=_FakeInput(),
            sn_input=_FakeInput(),
            result_select_all_checkbox=_FakeToggle(enabled=False),
            result_corner_checkbox=_FakeToggle(enabled=False),
            retry_btn=_FakeButton(enabled=False),
            reset_btn=_FakeButton(enabled=False),
            command_editing=False,
            result_table=_FakeTable(row_count=1),
            _set_result_checkboxes_enabled=lambda enabled: checkbox_enabled.append(bool(enabled)),
            _has_selected_retryable_rows=lambda: True,
            _has_result_rows=lambda: True,
            _update_fetch_button_state=lambda: None,
        )

        LogPage._set_running_state(page, True)
        self.assertFalse(page.reset_btn.enabled)
        self.assertFalse(page.retry_btn.enabled)
        self.assertTrue(page.command_input.read_only)

        LogPage._set_running_state(page, False)
        self.assertTrue(page.reset_btn.enabled)
        self.assertTrue(page.retry_btn.enabled)
        self.assertTrue(page.command_input.read_only)
        self.assertEqual([False, True], checkbox_enabled)


if __name__ == "__main__":
    unittest.main()
