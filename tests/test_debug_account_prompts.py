import unittest
import sys
from types import SimpleNamespace
from unittest import mock

from tests.gui_module_test_helper import load_debug_page


DebugPage = load_debug_page()


class _DummyLineEdit:
    def __init__(self, text=""):
        self._text = text

    def text(self):
        return self._text


class _DummySignal:
    def __init__(self):
        self.calls = []

    def emit(self, *args):
        self.calls.append(args)


class DebugPageAccountPromptTests(unittest.TestCase):
    def test_connect_prompts_for_missing_seetong_before_sn_validation(self):
        prompt_calls = []
        warnings = []
        module_path = DebugPage.__module__
        module = sys.modules[module_path]
        page = SimpleNamespace(
            connecting=False,
            connected=False,
            sn_input=_DummyLineEdit(""),
            on_cancel_connect_clicked=lambda: None,
            on_disconnect_clicked=lambda: None,
            show_warning=warnings.append,
            set_connecting_state=lambda *_args: None,
            request_connect=_DummySignal(),
        )

        with mock.patch.object(module, "get_seetong_account_config", return_value=("", "")), \
             mock.patch.object(
                 module,
                 "prompt_configure_account",
                 side_effect=lambda _parent, **kwargs: prompt_calls.append(kwargs.get("account_type")),
             ):
            DebugPage.on_connect_button_clicked(page)

        self.assertEqual(["seetong"], prompt_calls)
        self.assertEqual([], warnings)
        self.assertEqual([], page.request_connect.calls)

    def test_connect_prompts_for_missing_device_account_after_seetong_check(self):
        prompt_calls = []
        module_path = DebugPage.__module__
        module = sys.modules[module_path]
        page = SimpleNamespace(
            connecting=False,
            connected=False,
            sn_input=_DummyLineEdit("SN001"),
            on_cancel_connect_clicked=lambda: None,
            on_disconnect_clicked=lambda: None,
            show_warning=lambda *_args: None,
            set_connecting_state=lambda *_args: None,
            request_connect=_DummySignal(),
        )

        with mock.patch.object(module, "get_seetong_account_config", return_value=("cloud-user", "cloud-pass")), \
             mock.patch.object(module, "get_account_config", return_value=("pro", "", "")), \
             mock.patch.object(
                 module,
                 "prompt_configure_account",
                 side_effect=lambda _parent, **kwargs: prompt_calls.append(kwargs.get("account_type")),
             ):
            DebugPage.on_connect_button_clicked(page)

        self.assertEqual(["device"], prompt_calls)
        self.assertEqual([], page.request_connect.calls)


if __name__ == "__main__":
    unittest.main()
