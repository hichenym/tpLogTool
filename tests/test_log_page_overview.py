import unittest

from query_tool.pages.log_page import LogPage


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


if __name__ == "__main__":
    unittest.main()
