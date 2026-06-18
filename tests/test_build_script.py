import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def _load_build_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "build.py"
    spec = importlib.util.spec_from_file_location("tpquerytool_build_script_test", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_archive_build_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "archive_pyinstaller" / "build.py"
    spec = importlib.util.spec_from_file_location("tpquerytool_archive_build_script_test", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BuildScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build_script = _load_build_script_module()

    def test_get_sdk_dll_include_args_includes_funclib_like_other_sdk_dlls(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dll_dir = Path(tmpdir) / "query_tool" / "dll"
            dll_dir.mkdir(parents=True)
            for name in self.build_script.REQUIRED_SDK_DLLS:
                (dll_dir / name).write_bytes(b"")

            with mock.patch.object(self.build_script, "PROJECT_ROOT", tmpdir):
                include_args = self.build_script.get_sdk_dll_include_args()

        self.assertEqual(
            [
                f"--include-data-files={os.path.join('query_tool', 'dll', 'Funclib.dll')}=query_tool/dll/Funclib.dll",
                f"--include-data-files={os.path.join('query_tool', 'dll', 'libgcc_s_seh-1.dll')}=query_tool/dll/libgcc_s_seh-1.dll",
                f"--include-data-files={os.path.join('query_tool', 'dll', 'libsiot.dll')}=query_tool/dll/libsiot.dll",
                f"--include-data-files={os.path.join('query_tool', 'dll', 'libstdc++-6.dll')}=query_tool/dll/libstdc++-6.dll",
                f"--include-data-files={os.path.join('query_tool', 'dll', 'libtps_crypt.dll')}=query_tool/dll/libtps_crypt.dll",
                f"--include-data-files={os.path.join('query_tool', 'dll', 'libwinpthread-1.dll')}=query_tool/dll/libwinpthread-1.dll",
            ],
            include_args,
        )

    def test_get_sdk_dll_include_args_fails_fast_when_funclib_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dll_dir = Path(tmpdir) / "query_tool" / "dll"
            dll_dir.mkdir(parents=True)
            for name in self.build_script.REQUIRED_SDK_DLLS:
                if name == "Funclib.dll":
                    continue
                (dll_dir / name).write_bytes(b"")

            with mock.patch.object(self.build_script, "PROJECT_ROOT", tmpdir):
                with self.assertRaisesRegex(FileNotFoundError, "Funclib.dll"):
                    self.build_script.get_sdk_dll_include_args()

    def test_build_nuitka_keeps_fluent_packages_and_ui_package(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            expected_exe = os.path.join(
                tmpdir,
                self.build_script.RELEASE_OUTPUT_DIR,
                f"{self.build_script.APP_NAME}.exe",
            )

            def fake_exists(path):
                return path == expected_exe

            with mock.patch.object(self.build_script, "PROJECT_ROOT", tmpdir), \
                    mock.patch.object(self.build_script, "get_sdk_dll_include_args", return_value=[]), \
                    mock.patch.object(
                        self.build_script.subprocess,
                        "run",
                        return_value=mock.Mock(returncode=0),
                    ) as run_mock, \
                    mock.patch.object(self.build_script.os.path, "exists", side_effect=fake_exists), \
                    mock.patch.object(self.build_script.os.path, "getsize", return_value=8 * 1024 * 1024):
                success = self.build_script.build_nuitka(debug=False, fast=False)

        self.assertTrue(success)
        cmd = run_mock.call_args.args[0]
        self.assertIn("--include-package=query_tool.ui", cmd)
        self.assertIn("--include-package=qfluentwidgets", cmd)
        self.assertIn("--include-package=qframelesswindow", cmd)
        self.assertIn("--include-package=darkdetect", cmd)
        self.assertIn("--onefile", cmd)
        self.assertIn("--windows-console-mode=disable", cmd)
        self.assertEqual("run.py", cmd[-1])


class ArchiveBuildScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build_script = _load_archive_build_script_module()

    def test_build_exe_keeps_fluent_hidden_imports_and_sdk_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setuptools_pkg_dir = Path(tmpdir) / "fake_setuptools"
            setuptools_pkg_dir.mkdir()
            init_file = setuptools_pkg_dir / "__init__.py"
            init_file.write_text("", encoding="utf-8")
            vendor_dir = setuptools_pkg_dir / "_vendor"
            vendor_dir.mkdir()
            fake_spec = mock.Mock(origin=str(init_file))

            with mock.patch.object(
                self.build_script.importlib.util,
                "find_spec",
                return_value=fake_spec,
            ), \
                    mock.patch.object(
                        self.build_script.os.path,
                        "exists",
                        side_effect=lambda path: False,
                    ), \
                    mock.patch.object(
                        self.build_script.os.path,
                        "isdir",
                        side_effect=lambda path: path == str(vendor_dir),
                    ), \
                    mock.patch.object(
                        self.build_script.subprocess,
                        "run",
                        return_value=mock.Mock(returncode=0),
                    ) as run_mock, \
                    mock.patch.object(self.build_script.shutil, "rmtree") as rmtree_mock, \
                    mock.patch.object(self.build_script.os, "remove") as remove_mock:
                success = self.build_script.build_exe()

        self.assertTrue(success)
        rmtree_mock.assert_not_called()
        remove_mock.assert_not_called()
        cmd = run_mock.call_args.args[0]
        self.assertIn("qfluentwidgets", cmd)
        self.assertIn("qframelesswindow", cmd)
        self.assertIn("darkdetect", cmd)
        self.assertIn("./query_tool/dll;query_tool/dll", cmd)
        self.assertIn(f"{vendor_dir};setuptools/_vendor", cmd)
        self.assertEqual("run.py", cmd[-1])


if __name__ == "__main__":
    unittest.main()
