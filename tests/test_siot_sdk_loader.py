import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]


def _ensure_test_packages():
    import query_tool

    if "query_tool.utils" not in sys.modules:
        utils_pkg = types.ModuleType("query_tool.utils")
        utils_pkg.__path__ = [str(REPO_ROOT / "query_tool" / "utils")]
        sys.modules["query_tool.utils"] = utils_pkg

    if "query_tool.utils.siot_debug" not in sys.modules:
        siot_debug_pkg = types.ModuleType("query_tool.utils.siot_debug")
        siot_debug_pkg.__path__ = [str(REPO_ROOT / "query_tool" / "utils" / "siot_debug")]
        sys.modules["query_tool.utils.siot_debug"] = siot_debug_pkg


def _load_module(module_name: str, relative_path: str):
    _ensure_test_packages()
    if module_name in sys.modules:
        return sys.modules[module_name]

    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_load_module("query_tool.utils.siot_debug.config", "query_tool/utils/siot_debug/config.py")
siot_client = _load_module("query_tool.utils.siot_debug.siot_client", "query_tool/utils/siot_debug/siot_client.py")
internal_cli = _load_module("query_tool.utils.siot_debug.internal_cli", "query_tool/utils/siot_debug/internal_cli.py")


class _FakeFunction:
    def __init__(self):
        self.restype = None
        self.argtypes = None


class _FakeLibrary:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self._functions = {}

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name not in self._functions:
            self._functions[name] = _FakeFunction()
        return self._functions[name]


class SiotSdkLoaderTests(unittest.TestCase):
    def test_sdk_libraries_keeps_dll_directory_handles_and_preloads_runtime_dependencies(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sdk_dir = Path(tmpdir)
            for name in (
                "libsiot.dll",
                "libtps_crypt.dll",
                "libgcc_s_seh-1.dll",
                "libstdc++-6.dll",
                "libwinpthread-1.dll",
            ):
                (sdk_dir / name).write_bytes(b"")

            load_order = []
            dll_dir_handle = object()

            def fake_load(path):
                load_order.append(Path(path).name.lower())
                return _FakeLibrary(path)

            with mock.patch.object(siot_client, "SDK_BIN_DIR", sdk_dir):
                with mock.patch.object(siot_client, "PROJECT_ROOT", sdk_dir.parent):
                    with mock.patch.object(siot_client, "resolve_sdk_bin_dir", return_value=sdk_dir):
                        with mock.patch.object(
                            siot_client.os,
                            "add_dll_directory",
                            return_value=dll_dir_handle,
                        ) as add_dir_mock:
                            with mock.patch.object(siot_client.SdkLibraries, "_load", side_effect=fake_load):
                                sdk = siot_client.SdkLibraries(sdk_dir)

            add_dir_mock.assert_called_once_with(str(sdk_dir.resolve()))
            self.assertEqual([dll_dir_handle], sdk._dll_dir_handles)
            self.assertEqual(
                [
                    "libgcc_s_seh-1.dll",
                    "libstdc++-6.dll",
                    "libwinpthread-1.dll",
                    "libtps_crypt.dll",
                    "libsiot.dll",
                ],
                load_order,
            )
            self.assertIs(sdk.crypt, sdk._loaded_libraries["libtps_crypt.dll"])
            self.assertIs(sdk.lib, sdk._loaded_libraries["libsiot.dll"])

    def test_internal_cli_loader_reuses_sdk_libraries_wrapper(self):
        fake_sdk = object()
        with mock.patch.object(internal_cli, "SdkLibraries", return_value=fake_sdk) as sdk_mock:
            loaded = internal_cli._load_sdk_runtime(Path("C:/sdk"))

        sdk_mock.assert_called_once_with(Path("C:/sdk"))
        self.assertIs(fake_sdk, loaded)


if __name__ == "__main__":
    unittest.main()
