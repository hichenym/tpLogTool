import unittest
import sys
from types import SimpleNamespace
from unittest import mock

from tests.gui_module_test_helper import load_log_page


LogPage = load_log_page()


class LogPageAccountPromptTests(unittest.TestCase):
    def test_fetch_prompts_for_missing_seetong_before_parsing_inputs(self):
        prompt_calls = []
        start_calls = []
        module_path = LogPage.__module__
        module = sys.modules[module_path]
        page = SimpleNamespace(
            worker_thread=None,
            fetch_canceling=False,
            _update_fetch_button_state=lambda: None,
            summary_label=SimpleNamespace(setText=lambda *_args: None),
            show_info=lambda *_args: None,
            sn_input=SimpleNamespace(toPlainText=lambda: "SN001"),
            _parse_sn_input=lambda _text: (_ for _ in ()).throw(AssertionError("should not parse SN before Seetong check")),
            _start_execution=lambda *args, **kwargs: start_calls.append((args, kwargs)),
        )

        with mock.patch.object(module, "get_seetong_account_config", return_value=("", "")), \
             mock.patch.object(
                 module,
                 "prompt_configure_account",
                 side_effect=lambda _parent, **kwargs: prompt_calls.append(kwargs.get("account_type")),
             ):
            LogPage.on_fetch_clicked(page)

        self.assertEqual(["seetong"], prompt_calls)
        self.assertEqual([], start_calls)

    def test_collect_execution_context_prompts_for_missing_seetong_on_retry_path(self):
        prompt_calls = []
        module_path = LogPage.__module__
        module = sys.modules[module_path]
        page = SimpleNamespace(
            get_command_list=lambda: ["GetSystemCfg /tmp/test.log"],
            show_warning=lambda *_args: None,
        )

        with mock.patch.object(module, "get_account_config", return_value=("pro", "device-user", "device-pass")), \
             mock.patch.object(module, "get_seetong_account_config", return_value=("", "")), \
             mock.patch.object(
                 module,
                 "prompt_configure_account",
                 side_effect=lambda _parent, **kwargs: prompt_calls.append(kwargs.get("account_type")),
             ):
            context = LogPage._collect_execution_context(page)

        self.assertIsNone(context)
        self.assertEqual(["seetong"], prompt_calls)


if __name__ == "__main__":
    unittest.main()
