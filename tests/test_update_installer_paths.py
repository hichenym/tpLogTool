import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.modules.setdefault("ddddocr", types.SimpleNamespace())

from query_tool.utils.update_downloader import UpdateInstaller


class UpdateInstallerPathTests(unittest.TestCase):
    def _assert_windows_path_equal(self, actual: str, expected: str):
        self.assertEqual(
            str(Path(actual)),
            str(Path(expected)),
        )

    def test_launcher_path_from_single_runtime_directory(self):
        runtime_exe = r"D:\software\TopSee\.tpquerytool-onefile\TPQueryTool.exe"
        expected_launcher = r"D:\software\TopSee\TPQueryTool.exe"
        expected_runtime_root = r"D:\software\TopSee\.tpquerytool-onefile"

        with patch.object(sys, "executable", runtime_exe), \
             patch.object(sys, "argv", [runtime_exe]), \
             patch.dict(
                 sys.modules,
                 {"__main__": types.SimpleNamespace()},
                 clear=False,
             ):
            launcher = UpdateInstaller.get_launcher_executable_path()
            runtime_root = UpdateInstaller.get_runtime_directory_path()

        self._assert_windows_path_equal(launcher, expected_launcher)
        self._assert_windows_path_equal(runtime_root, expected_runtime_root)

    def test_launcher_path_collapses_nested_runtime_directories(self):
        nested_runtime_exe = (
            r"D:\software\TopSee\.tpquerytool-onefile\.tpquerytool-onefile\TPQueryTool.exe"
        )
        intermediate_launcher = r"D:\software\TopSee\.tpquerytool-onefile\TPQueryTool.exe"
        expected_launcher = r"D:\software\TopSee\TPQueryTool.exe"
        expected_runtime_root = r"D:\software\TopSee\.tpquerytool-onefile"

        fake_main = types.SimpleNamespace(
            __compiled__=types.SimpleNamespace(original_argv0=intermediate_launcher)
        )

        with patch.object(sys, "executable", nested_runtime_exe), \
             patch.object(sys, "argv", [nested_runtime_exe]), \
             patch.dict(
                 sys.modules,
                 {"__main__": fake_main},
                 clear=False,
             ):
            launcher = UpdateInstaller.get_launcher_executable_path()
            runtime_root = UpdateInstaller.get_runtime_directory_path()

        self._assert_windows_path_equal(launcher, expected_launcher)
        self._assert_windows_path_equal(runtime_root, expected_runtime_root)

    def test_runtime_repair_package_points_to_outer_runtime_root_exe(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir) / "TopSee"
            outer_runtime_root = base_dir / ".tpquerytool-onefile"
            nested_runtime_root = outer_runtime_root / ".tpquerytool-onefile"
            repair_package = outer_runtime_root / "TPQueryTool.exe"
            nested_runtime_exe = nested_runtime_root / "TPQueryTool.exe"

            nested_runtime_root.mkdir(parents=True)
            repair_package.write_bytes(b"outer launcher package")
            nested_runtime_exe.write_bytes(b"nested runtime")

            fake_main = types.SimpleNamespace(
                __compiled__=types.SimpleNamespace(original_argv0=str(repair_package))
            )

            with patch.object(sys, "executable", str(nested_runtime_exe)), \
                 patch.object(sys, "argv", [str(nested_runtime_exe)]), \
                 patch.dict(
                     sys.modules,
                     {"__main__": fake_main},
                     clear=False,
                 ):
                detected_package = UpdateInstaller.get_runtime_repair_package_path()

            self.assertEqual(Path(detected_package), repair_package.resolve())

    def test_cleanup_stale_nested_runtime_dirs_removes_nested_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir) / "TopSee"
            runtime_root = base_dir / ".tpquerytool-onefile"
            stale_nested_root = runtime_root / ".tpquerytool-onefile"
            runtime_exe = runtime_root / "TPQueryTool.exe"
            stale_nested_exe = stale_nested_root / "TPQueryTool.exe"

            stale_nested_root.mkdir(parents=True)
            runtime_exe.write_bytes(b"healthy runtime")
            stale_nested_exe.write_bytes(b"stale nested runtime")

            with patch.object(sys, "executable", str(runtime_exe)), \
                 patch.object(sys, "argv", [str(runtime_exe)]), \
                 patch.dict(
                     sys.modules,
                     {"__main__": types.SimpleNamespace()},
                     clear=False,
                 ):
                removed_dirs = UpdateInstaller.cleanup_stale_nested_runtime_dirs()

            self.assertEqual([stale_nested_root.resolve()], [Path(item) for item in removed_dirs])
            self.assertFalse(stale_nested_root.exists())

    def test_find_stale_nested_runtime_dirs_handles_multiple_nested_levels_on_python38(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir) / "TopSee"
            runtime_root = base_dir / ".tpquerytool-onefile"
            stale_nested_root = runtime_root / ".tpquerytool-onefile"
            stale_deeper_root = stale_nested_root / ".tpquerytool-onefile"
            runtime_exe = runtime_root / "TPQueryTool.exe"

            stale_deeper_root.mkdir(parents=True)
            runtime_exe.write_bytes(b"healthy runtime")
            (stale_nested_root / "TPQueryTool.exe").write_bytes(b"stale nested runtime")
            (stale_deeper_root / "TPQueryTool.exe").write_bytes(b"stale deeper runtime")

            with patch.object(sys, "executable", str(runtime_exe)), \
                 patch.object(sys, "argv", [str(runtime_exe)]), \
                 patch.dict(
                     sys.modules,
                     {"__main__": types.SimpleNamespace()},
                     clear=False,
                 ):
                stale_dirs = UpdateInstaller.find_stale_nested_runtime_dirs()

            self.assertEqual([stale_nested_root.resolve()], [Path(item) for item in stale_dirs])


if __name__ == "__main__":
    unittest.main()
