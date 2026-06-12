import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.modules.setdefault("ddddocr", types.SimpleNamespace())

from query_tool.utils.update_downloader import DownloadThread, UpdateDownloader


class UpdateDownloadLockTests(unittest.TestCase):
    def test_acquire_download_lock_cleans_stale_lock_from_exited_process(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "TPQueryTool_3.7.1.exe"
            lock_path = Path(str(save_path) + ".lock")
            lock_path.write_text("424242\n" + str(save_path) + "\n", encoding="utf-8")

            thread = DownloadThread("https://example.com/update.exe", str(save_path))
            with patch("query_tool.utils.update_downloader._is_process_active", return_value=False):
                acquired = thread._acquire_download_lock()

            self.assertTrue(acquired)
            self.assertTrue(lock_path.exists())
            lock_payload = lock_path.read_text(encoding="utf-8")
            self.assertIn(str(save_path), lock_payload)
            self.assertNotIn("424242", lock_payload)
            thread._release_download_lock()

    def test_acquire_download_lock_preserves_live_lock(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "TPQueryTool_3.7.1.exe"
            lock_path = Path(str(save_path) + ".lock")
            original_payload = "515151\n" + str(save_path) + "\n"
            lock_path.write_text(original_payload, encoding="utf-8")

            thread = DownloadThread("https://example.com/update.exe", str(save_path))
            with patch("query_tool.utils.update_downloader._is_process_active", return_value=True):
                acquired = thread._acquire_download_lock()

            self.assertFalse(acquired)
            self.assertEqual(original_payload, lock_path.read_text(encoding="utf-8"))

    def test_update_downloader_init_cleans_stale_lock_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            download_dir = Path(temp_dir)
            lock_path = download_dir / "TPQueryTool_3.7.1.exe.lock"
            lock_path.write_text("626262\n" + str(download_dir / "TPQueryTool_3.7.1.exe") + "\n", encoding="utf-8")

            with patch.object(UpdateDownloader, "DOWNLOAD_DIR", download_dir), \
                 patch("query_tool.utils.update_downloader._is_process_active", return_value=False):
                UpdateDownloader()

            self.assertFalse(lock_path.exists())


if __name__ == "__main__":
    unittest.main()
