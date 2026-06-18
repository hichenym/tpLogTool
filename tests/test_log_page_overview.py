import unittest
from types import SimpleNamespace
from unittest import mock

from tests.test_fluent_widget_smokes import PAGES_DIR, _isolated_page_env, _load_module


def _load_log_page_module():
    with _isolated_page_env():
        return _load_module(
            "query_tool.pages._log_page_overview_test",
            PAGES_DIR / "log_page.py",
        )


log_page_module = _load_log_page_module()
LogPage = log_page_module.LogPage
BatchLogFetchThread = log_page_module.BatchLogFetchThread


class LogPageOverviewTests(unittest.TestCase):
    def test_single_syscmd_payload_is_inlined_from_current_command(self):
        payload = {
            "total_commands": 1,
            "current_command": "syscmd uname -a",
            "detail": "执行命令: syscmd uname -a",
        }

        self.assertTrue(LogPage._should_inline_single_syscmd_overview(payload))

    def test_single_syscmd_payload_is_inlined_from_final_detail(self):
        payload = {
            "total_commands": 1,
            "current_command": "",
            "detail": "syscmd cat /tmp/test.txt: hello world",
        }

        self.assertEqual("syscmd cat /tmp/test.txt", LogPage._extract_single_syscmd_command(payload))
        self.assertTrue(LogPage._should_inline_single_syscmd_overview(payload))

    def test_getsystemcfg_payload_is_not_inlined(self):
        payload = {
            "total_commands": 1,
            "current_command": "GetSystemCfg /tmp/test.log",
            "detail": "GetSystemCfg /tmp/test.log: 成功",
        }

        self.assertFalse(LogPage._should_inline_single_syscmd_overview(payload))

    def test_multiple_commands_are_not_inlined(self):
        payload = {
            "total_commands": 2,
            "current_command": "syscmd uname -a",
            "detail": "syscmd uname -a: hello world",
        }

        self.assertFalse(LogPage._should_inline_single_syscmd_overview(payload))

    def test_inline_syscmd_overview_omits_command_prefix(self):
        payload = {
            "total_commands": 1,
            "current_command": "syscmd cat /tmp/test.txt",
            "detail": "syscmd cat /tmp/test.txt: hello world\nline2",
        }

        self.assertEqual("hello world\nline2", LogPage._extract_inline_syscmd_result_text(payload))

    def test_inline_syscmd_overview_ignores_command_only_progress_line(self):
        payload = {
            "total_commands": 1,
            "current_command": "syscmd uname -a",
            "detail": "执行命令: syscmd uname -a",
        }

        self.assertEqual("", LogPage._extract_inline_syscmd_result_text(payload))


class BatchLogFetchThreadCleanupTests(unittest.TestCase):
    def test_process_single_device_ignores_closed_stdin_during_disconnect(self):
        worker = BatchLogFetchThread(
            sn_list=["LOG-SN-001"],
            commands=["syscmd uname -a"],
            download_root="C:/temp",
            env="test",
            device_username="admin",
            device_password="123456",
            seetong_username="cloud",
            seetong_password="secret",
        )
        credentials = SimpleNamespace(
            sn="LOG-SN-001",
            username="admin",
            password="123456",
            dev_id="dev-1",
            protocol="p2p",
            is_siot=True,
        )
        process = mock.Mock()
        process.poll.return_value = None
        process.stdin = mock.Mock(closed=False)
        event_queue = object()

        with mock.patch.object(log_page_module, "resolve_device_credentials", return_value=(credentials, None)):
            with mock.patch.object(worker, "_emit_device"):
                with mock.patch.object(worker, "_start_process", return_value=(process, event_queue)):
                    with mock.patch.object(worker, "_wait_for_connect"):
                        with mock.patch.object(
                            worker,
                            "_run_command",
                            return_value={"success": True, "message": "Linux", "saved_file": "", "missing_file": ""},
                        ):
                            with mock.patch.object(
                                worker,
                                "_send_payload",
                                side_effect=ValueError("write to closed file"),
                            ) as send_payload:
                                with mock.patch.object(worker, "_drain_until_disconnected") as drain_until_disconnected:
                                    with mock.patch.object(worker, "_close_process") as close_process:
                                        with mock.patch.object(log_page_module.logger, "warning") as logger_warning:
                                            result = worker._process_single_device("LOG-SN-001")

        self.assertEqual("完成", result["status"])
        send_payload.assert_called_once_with(process, {"action": "disconnect"})
        drain_until_disconnected.assert_not_called()
        logger_warning.assert_not_called()
        close_process.assert_called_once_with(process)


if __name__ == "__main__":
    unittest.main()
