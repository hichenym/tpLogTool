import unittest
from types import SimpleNamespace

from device_status_page_test_helper import load_device_status_page


DeviceStatusPage = load_device_status_page()


class _FakeLineEdit:
    def __init__(self, text=""):
        self._text = text

    def text(self):
        return self._text

    def setText(self, text):
        self._text = text

    def clear(self):
        self._text = ""

    def blockSignals(self, _blocked):
        return None


class _FakeCombo:
    def __init__(self, items=None, current_text=""):
        self._items = list(items or [])
        self._current_text = current_text or (self._items[0] if self._items else "")
        self.enabled = True

    def currentText(self):
        return self._current_text

    def setCurrentText(self, text):
        self._current_text = text

    def clear(self):
        self._items = []
        self._current_text = ""

    def addItem(self, text):
        self._items.append(text)
        if not self._current_text:
            self._current_text = text

    def blockSignals(self, _blocked):
        return None

    def findText(self, text):
        try:
            return self._items.index(text)
        except ValueError:
            return -1

    def setCurrentIndex(self, index):
        self._current_text = self._items[index]

    def setEnabled(self, enabled):
        self.enabled = enabled


class _FakeCheckbox:
    def __init__(self):
        self.checked = False

    def blockSignals(self, _blocked):
        return None

    def setChecked(self, checked):
        self.checked = checked


class _FakeLabel:
    def __init__(self):
        self.text_value = ""

    def setText(self, text):
        self.text_value = text


def _build_page(query_results):
    calls = []
    page = SimpleNamespace(
        STATUS_FILTER_OPTIONS=DeviceStatusPage.STATUS_FILTER_OPTIONS,
        query_results=query_results,
        filtered_results={},
        all_models=set(),
        all_versions=set(),
        current_sn_filter="",
        current_model_filter=None,
        current_status_filter=None,
        current_version_filter=None,
        sn_filter_input=_FakeLineEdit(),
        model_combo=_FakeCombo(["全部"], "全部"),
        status_combo=_FakeCombo(list(DeviceStatusPage.STATUS_FILTER_OPTIONS), "全部"),
        version_combo=_FakeCombo(["全部"], "全部"),
        select_all_checkbox=_FakeCheckbox(),
        match_count_label=_FakeLabel(),
        refresh_table_display=lambda: calls.append("refresh"),
        update_input_boxes_from_filtered_table=lambda: calls.append("update_inputs"),
        update_filtered_status_summary=lambda: calls.append("filtered_summary"),
        update_device_status_summary=lambda: calls.append("device_summary"),
        sender=lambda: None,
    )
    page._has_active_filters = lambda *args, **kwargs: DeviceStatusPage._has_active_filters(page, *args, **kwargs)
    page._matches_status_filter = DeviceStatusPage._matches_status_filter
    page.update_version_combo_by_filters = lambda selected_model, selected_status: DeviceStatusPage.update_version_combo_by_filters(
        page,
        selected_model,
        selected_status,
    )
    return page, calls


class DeviceStatusFilterTests(unittest.TestCase):
    def test_apply_filters_supports_online_status_filter(self):
        page, calls = _build_page(
            {
                0: {"sn": "SN001", "model": "M1", "version": "V1", "online": 1},
                1: {"sn": "SN002", "model": "M1", "version": "V2", "online": 0},
                2: {"sn": "SN003", "model": "M2", "version": "V3", "online": -1},
            }
        )

        DeviceStatusPage.apply_filters(page, "", "全部", "在线", "全部")

        self.assertEqual([0], list(page.filtered_results.keys()))
        self.assertEqual("在线", page.current_status_filter)
        self.assertEqual("数量: 1 / 3", page.match_count_label.text_value)
        self.assertEqual(["refresh", "update_inputs", "filtered_summary"], calls)

    def test_on_filter_changed_resets_status_when_sn_filter_is_used(self):
        page, _ = _build_page({})
        page.sn_filter_input.setText("SN0")
        page.model_combo.addItem("M1")
        page.model_combo.setCurrentText("M1")
        page.status_combo.setCurrentText("离线")
        page.version_combo.addItem("V1")
        page.version_combo.setCurrentText("V1")

        captured = []
        page.sender = lambda: page.sn_filter_input
        page.apply_filters = lambda sn_filter, selected_model, selected_status, selected_version: captured.append(
            (sn_filter, selected_model, selected_status, selected_version)
        )

        DeviceStatusPage.on_filter_changed(page)

        self.assertEqual("全部", page.model_combo.currentText())
        self.assertEqual("全部", page.status_combo.currentText())
        self.assertEqual("全部", page.version_combo.currentText())
        self.assertEqual([("sn0", "全部", "全部", "全部")], captured)

    def test_on_filter_changed_status_filter_clears_sn_and_refreshes_versions(self):
        page, _ = _build_page(
            {
                0: {"sn": "SN001", "model": "M1", "version": "V1", "online": 0},
                1: {"sn": "SN002", "model": "M1", "version": "V2", "online": 1},
            }
        )
        page.sn_filter_input.setText("SN")
        page.status_combo.setCurrentText("离线")
        page.version_combo.addItem("V1")
        page.version_combo.addItem("V2")
        page.version_combo.setCurrentText("V2")

        captured = []
        page.sender = lambda: page.status_combo
        page.apply_filters = lambda sn_filter, selected_model, selected_status, selected_version: captured.append(
            (sn_filter, selected_model, selected_status, selected_version)
        )

        DeviceStatusPage.on_filter_changed(page)

        self.assertEqual("", page.sn_filter_input.text())
        self.assertEqual("全部", page.version_combo.currentText())
        self.assertEqual([("", "全部", "离线", "全部")], captured)


if __name__ == "__main__":
    unittest.main()
