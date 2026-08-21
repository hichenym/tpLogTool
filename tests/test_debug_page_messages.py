import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from query_tool.pages.debug_page import DebugPage


class _DummyLineEdit:
    def __init__(self, text=""):
        self._text = text

    def text(self):
        return self._text


class DebugPageMessageTests(unittest.TestCase):
    def _make_page_stub(self, sn=""):
        return SimpleNamespace(
            current_context={},
            sn_input=_DummyLineEdit(sn),
            SUPPRESSED_CONNECT_MESSAGES=DebugPage.SUPPRESSED_CONNECT_MESSAGES,
            SUPPRESSED_CONNECT_PREFIXES=DebugPage.SUPPRESSED_CONNECT_PREFIXES,
        )

    def test_offline_failure_message_is_normalized_to_device_offline(self):
        sn = "0BBB5E6EEC0339BA"
        page = self._make_page_stub(sn=sn)

        message = DebugPage._format_connect_result_message(
            page,
            "连接失败",
            detail=f"设备：{sn}不在线",
        )

        self.assertEqual(f"连接失败 {sn}: 设备离线", message)

    def test_legacy_p2p_noise_messages_are_suppressed(self):
        page = self._make_page_stub()

        self.assertTrue(
            DebugPage._should_suppress_output(
                page,
                "检测到非SIOT设备，正在使用P2P协议连接...",
            )
        )
        self.assertTrue(
            DebugPage._should_suppress_output(
                page,
                "P2P服务器登录成功，正在建立设备通道...",
            )
        )

    def test_query_and_p2p_login_success_messages_remain_visible(self):
        page = self._make_page_stub()

        self.assertFalse(DebugPage._should_suppress_output(page, "查询到非SIOT设备"))
        self.assertFalse(DebugPage._should_suppress_output(page, "P2P服务器登录成功"))

    def test_connected_message_does_not_include_protocol_detail(self):
        page = SimpleNamespace(
            sn_input=MagicMock(),
            console_edit=MagicMock(),
            command_input=MagicMock(),
            command_type_combo=MagicMock(),
            update_connect_button=MagicMock(),
            update_shortcut_controls=MagicMock(),
            update_send_button=MagicMock(),
            append_output=MagicMock(),
            _flush_pending_output=MagicMock(),
            show_success=MagicMock(),
        )
        page._format_connect_result_message = lambda result, sn="", detail="", model="": (
            DebugPage._format_connect_result_message(page, result, sn, detail, model)
        )

        DebugPage.on_connected(
            page,
            {"sn": "0C2811E3A2983A9C", "connected_protocol": "tpsrtc"},
        )

        page.append_output.assert_called_once_with("连接成功 0C2811E3A2983A9C")


if __name__ == "__main__":
    unittest.main()
