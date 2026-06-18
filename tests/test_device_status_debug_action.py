import unittest
from types import SimpleNamespace

from tests.device_status_page_test_helper import load_device_status_page


DeviceStatusPage = load_device_status_page()


class _FakeItem:
    def __init__(self, text=""):
        self._text = text

    def text(self):
        return self._text


class _FakeTable:
    def __init__(self, item_map):
        self._item_map = item_map

    def item(self, row, column):
        return self._item_map.get((row, column))


class _FakeWindow:
    def __init__(self):
        self.requested_sn = None

    def open_debug_page_for_sn(self, sn):
        self.requested_sn = sn
        return True


class DeviceStatusDebugActionTests(unittest.TestCase):
    def test_non_siot_row_can_open_debug_page(self):
        fake_window = _FakeWindow()
        info_messages = []
        warning_messages = []

        page = SimpleNamespace(
            result_table=_FakeTable({(0, 3): _FakeItem("0BE7BC56EC8E39B7")}),
            window=lambda: fake_window,
            show_warning=warning_messages.append,
            show_info=info_messages.append,
            _is_non_siot_row=lambda _row: True,
        )

        DeviceStatusPage.on_debug_single(page, 0)

        self.assertEqual("0BE7BC56EC8E39B7", fake_window.requested_sn)
        self.assertEqual(["正在切换到调试页连接设备: 0BE7BC56EC8E39B7"], info_messages)
        self.assertEqual([], warning_messages)


if __name__ == "__main__":
    unittest.main()
