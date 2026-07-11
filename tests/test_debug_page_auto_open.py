import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests.gui_module_test_helper import load_debug_page


DebugPage = load_debug_page()


class DebugPageAutoOpenTests(unittest.TestCase):
    def _make_page_stub(self, **overrides):
        page = SimpleNamespace(
            DOWNLOAD_OUTPUT_PREFIX=DebugPage.DOWNLOAD_OUTPUT_PREFIX,
            AUTO_OPEN_TEXT_SUFFIXES=DebugPage.AUTO_OPEN_TEXT_SUFFIXES,
            last_command_source="console",
            _executing_backend_command="GetSystemCfg /tmp/test.log",
            _pending_auto_open_download_paths=[],
            _is_download_command=DebugPage._is_download_command,
            _looks_like_text_content=DebugPage._looks_like_text_content,
            append_output=lambda text, color=None: None,
        )
        for key, value in overrides.items():
            setattr(page, key, value)
        return page

    def test_collect_auto_open_download_path_for_manual_download_command(self):
        page = self._make_page_stub()
        page._should_auto_open_downloads_for_current_command = lambda: DebugPage._should_auto_open_downloads_for_current_command(page)

        DebugPage._collect_auto_open_download_path(page, "文件已下载到: C:/tmp/test.log")

        self.assertEqual([str(Path("C:/tmp/test.log"))], page._pending_auto_open_download_paths)

    def test_collect_auto_open_download_path_ignores_non_manual_or_non_download_command(self):
        page = self._make_page_stub(
            last_command_source="auto",
            _executing_backend_command="syscmd cat /tmp/test.log",
        )
        page._should_auto_open_downloads_for_current_command = lambda: DebugPage._should_auto_open_downloads_for_current_command(page)

        DebugPage._collect_auto_open_download_path(page, "文件已下载到: C:/tmp/test.log")

        self.assertEqual([], page._pending_auto_open_download_paths)

    def test_auto_open_pending_downloads_opens_text_files_only(self):
        opened = []
        messages = []
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            text_file = root / "test.log"
            text_file.write_text("hello\nworld\n", encoding="utf-8")
            binary_file = root / "test.bin"
            binary_file.write_bytes(b"\x00\x01\x02\x03")

            page = self._make_page_stub(
                _pending_auto_open_download_paths=[str(text_file), str(binary_file)],
                append_output=lambda text, color=None: messages.append(text),
            )
            page._is_text_download_file_path = lambda path: DebugPage._is_text_download_file_path(page, path)
            page._open_downloaded_file_with_default_viewer = lambda path: (opened.append(str(path)) or True)

            DebugPage._auto_open_pending_downloads(page)

        self.assertEqual([str(text_file)], opened)
        self.assertEqual([], messages)
        self.assertEqual([], page._pending_auto_open_download_paths)

    def test_auto_open_pending_downloads_appends_message_when_open_fails(self):
        messages = []
        with tempfile.TemporaryDirectory() as tmpdir:
            text_file = Path(tmpdir) / "test.txt"
            text_file.write_text("hello\n", encoding="utf-8")

            page = self._make_page_stub(
                _pending_auto_open_download_paths=[str(text_file)],
                append_output=lambda text, color=None: messages.append(text),
            )
            page._is_text_download_file_path = lambda path: True
            page._open_downloaded_file_with_default_viewer = lambda path: False

            DebugPage._auto_open_pending_downloads(page)

        self.assertEqual([f"自动打开文件失败: {text_file}"], messages)

    def test_on_command_finished_only_auto_opens_when_command_succeeds(self):
        auto_open_calls = []
        page = SimpleNamespace(
            command_running=True,
            _last_command_failed=False,
            _executing_command="GetSystemCfg /tmp/test.log",
            _executing_backend_command="GetSystemCfg /tmp/test.log",
            _pending_stream_log_state=None,
            _stream_log_active=False,
            connected=False,
            _record_successful_command=lambda command: None,
            _auto_open_pending_downloads=lambda: auto_open_calls.append("open"),
        )

        DebugPage.on_command_finished(page)
        self.assertEqual(["open"], auto_open_calls)

        page.command_running = True
        page._last_command_failed = True
        page._executing_command = "GetSystemCfg /tmp/test.log"
        page._executing_backend_command = "GetSystemCfg /tmp/test.log"
        DebugPage.on_command_finished(page)
        self.assertEqual(["open"], auto_open_calls)


if __name__ == "__main__":
    unittest.main()
