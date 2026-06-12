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


if __name__ == "__main__":
    unittest.main()
