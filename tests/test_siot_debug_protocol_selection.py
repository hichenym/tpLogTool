import importlib.util
import unittest
import ctypes
import sys
import tempfile
import types
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]


def _ensure_test_packages():
    import query_tool

    if "query_tool.utils" not in sys.modules:
        utils_pkg = types.ModuleType("query_tool.utils")
        utils_pkg.__path__ = [str(REPO_ROOT / "query_tool" / "utils")]
        sys.modules["query_tool.utils"] = utils_pkg

    if "query_tool.utils.device_query" not in sys.modules:
        device_query_stub = types.ModuleType("query_tool.utils.device_query")

        class DeviceQuery:
            def __init__(self, *args, **kwargs):
                self.init_error = None

        device_query_stub.DeviceQuery = DeviceQuery
        sys.modules["query_tool.utils.device_query"] = device_query_stub

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


models = _load_module("query_tool.utils.siot_debug.models", "query_tool/utils/siot_debug/models.py")
p2p_session = _load_module("query_tool.utils.siot_debug.p2p_session", "query_tool/utils/siot_debug/p2p_session.py")
subprocess_runner = _load_module(
    "query_tool.utils.siot_debug.subprocess_runner",
    "query_tool/utils/siot_debug/subprocess_runner.py",
)
DeviceCredentials = models.DeviceCredentials


class DebugProtocolSelectionTests(unittest.TestCase):
    def test_non_siot_device_uses_p2p_without_seetong_account(self):
        credentials = DeviceCredentials(
            sn="SN001",
            username="admin",
            password="pwd",
            dev_id="DEV001",
            is_siot=False,
            protocol="p2p",
        )

        factories = subprocess_runner._build_session_factories(credentials, "", "")

        self.assertEqual(["p2p"], [name for name, _ in factories])
        self.assertIs(factories[0][1], subprocess_runner.P2PDeviceSession)

    def test_siot_device_requires_seetong_account(self):
        credentials = DeviceCredentials(
            sn="SN001",
            username="admin",
            password="pwd",
            dev_id="DEV001",
            is_siot=True,
            protocol="siot",
        )

        with self.assertRaisesRegex(RuntimeError, "Seetong"):
            subprocess_runner._build_session_factories(credentials, "", "")

    def test_auto_protocol_prefers_siot_then_falls_back_to_p2p(self):
        credentials = DeviceCredentials(
            sn="SN001",
            username="admin",
            password="pwd",
            dev_id="DEV001",
            is_siot=None,
            protocol="auto",
        )

        factories = subprocess_runner._build_session_factories(
            credentials,
            "cloud-user",
            "cloud-pass",
        )

        self.assertEqual(["siot", "p2p"], [name for name, _ in factories])

    def test_auto_protocol_without_seetong_only_uses_p2p(self):
        credentials = DeviceCredentials(
            sn="SN001",
            username="admin",
            password="pwd",
            dev_id="DEV001",
            is_siot=None,
            protocol="auto",
        )

        factories = subprocess_runner._build_session_factories(credentials, "", "")

        self.assertEqual(["p2p"], [name for name, _ in factories])

    def test_p2p_login_device_list_parse_warning_is_treated_as_benign(self):
        self.assertTrue(
            p2p_session._is_benign_p2p_login_return_code(
                p2p_session.P2P_LOGIN_DEVICE_LIST_PARSE_WARNING
            )
        )

    def test_p2p_login_failed_warning_payload_formats_cleanly(self):
        payload = p2p_session.P2P_LOGIN_DEVICE_LIST_PARSE_WARNING.to_bytes(
            4,
            byteorder="little",
            signed=True,
        )
        buffer = ctypes.create_string_buffer(payload)

        message = p2p_session.P2PDeviceSession._build_p2p_error(
            p2p_session.TPS_MSG_NOTIFY_LOGIN_FAILED,
            buffer,
            len(payload),
        )

        self.assertIn("解析告警", message)
        self.assertIn(str(p2p_session.P2P_LOGIN_DEVICE_LIST_PARSE_WARNING), message)

    def test_p2p_offline_with_device_id_payload_maps_to_device_offline(self):
        payload = b"31576446\x00\x00\x00"
        buffer = ctypes.create_string_buffer(payload)

        message = p2p_session.P2PDeviceSession._build_p2p_error(
            p2p_session.TPS_MSG_P2P_OFFLINE,
            buffer,
            len(payload),
        )

        self.assertEqual("设备离线", message)

    def test_p2p_thread_exit_with_device_id_payload_uses_generic_message(self):
        payload = b"31576446\x00\x00\x00"
        buffer = ctypes.create_string_buffer(payload)

        message = p2p_session.P2PDeviceSession._build_p2p_error(
            p2p_session.TPS_MSG_NOTIFY_P2P_THREAD_EXIT,
            buffer,
            len(payload),
        )

        self.assertEqual("P2P会话线程已退出", message)

    def test_p2p_sdk_resolution_no_longer_falls_back_to_repo_tmp_directory(self):
        with mock.patch.object(p2p_session, "_is_p2p_sdk_dir", return_value=False):
            path = p2p_session.resolve_p2p_sdk_dir()

        self.assertEqual(
            (p2p_session.PROJECT_ROOT / "query_tool" / "dll").resolve(),
            path.resolve(),
        )

    def test_p2p_sdk_resolution_falls_back_to_recursive_search_in_packaged_layout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sdk_dir = root / "TPQueryTool.dist" / "query_tool" / "dll"
            sdk_dir.mkdir(parents=True)
            (sdk_dir / "Funclib.dll").write_bytes(b"")

            with mock.patch.object(p2p_session, "_iter_p2p_sdk_candidates", return_value=[]):
                with mock.patch.object(p2p_session, "_iter_p2p_search_roots", return_value=[root]):
                    path = p2p_session.resolve_p2p_sdk_dir()

            self.assertEqual(sdk_dir.resolve(), path.resolve())


if __name__ == "__main__":
    unittest.main()
