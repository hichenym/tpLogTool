import tempfile
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.modules.setdefault("ddddocr", types.SimpleNamespace())

from query_tool.utils import update_checker as update_checker_module
from query_tool.utils.update_checker import UpdateChecker


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {"version": "9.9.9", "update_strategy": "prompt"}


class UpdateCheckerMemoryCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.temp_dir.name) / "update"
        self.cache_file = self.cache_dir / "version_cache.json"
        self.cache_dir.mkdir()
        self.cache_file.write_text('{"version_info": {}}', encoding="utf-8")
        self.dir_patch = patch.object(UpdateChecker, "LEGACY_CACHE_DIR", self.cache_dir)
        self.file_patch = patch.object(UpdateChecker, "LEGACY_CACHE_FILE", self.cache_file)
        self.dir_patch.start()
        self.file_patch.start()
        UpdateChecker._memory_cache_data = None
        UpdateChecker._memory_cache_at = None

    def tearDown(self):
        self.file_patch.stop()
        self.dir_patch.stop()
        UpdateChecker._memory_cache_data = None
        UpdateChecker._memory_cache_at = None
        self.temp_dir.cleanup()

    def test_initialization_removes_legacy_disk_cache(self):
        UpdateChecker("1.0.0")

        self.assertFalse(self.cache_dir.exists())

    def test_remote_version_info_is_kept_only_in_memory(self):
        checker = UpdateChecker("1.0.0")

        with patch.object(update_checker_module.requests, "get", return_value=_Response()):
            version_info = checker._fetch_version_info()

        self.assertEqual("9.9.9", version_info.version)
        self.assertFalse(self.cache_dir.exists())
        self.assertEqual("9.9.9", UpdateChecker.get_memory_cache_data()["version"])

    def test_remote_failure_is_silent(self):
        checker = UpdateChecker("1.0.0")

        with patch.object(update_checker_module.requests, "get", side_effect=RuntimeError("offline")):
            result = checker.check_update_force_refresh()

        self.assertEqual((False, None, ""), result)
        self.assertEqual({}, UpdateChecker.get_memory_cache_data())


if __name__ == "__main__":
    unittest.main()
