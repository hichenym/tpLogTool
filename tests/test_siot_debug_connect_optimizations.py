import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]


def _ensure_test_packages():
    import query_tool

    if "PyQt5" not in sys.modules:
        pyqt5_pkg = types.ModuleType("PyQt5")
        qtcore_pkg = types.ModuleType("PyQt5.QtCore")

        class QObject:
            pass

        class _Signal:
            def connect(self, *args, **kwargs):
                return None

            def emit(self, *args, **kwargs):
                return None

        def pyqtSignal(*args, **kwargs):
            return _Signal()

        def pyqtSlot(*args, **kwargs):
            def decorator(func):
                return func

            return decorator

        qtcore_pkg.QObject = QObject
        qtcore_pkg.pyqtSignal = pyqtSignal
        qtcore_pkg.pyqtSlot = pyqtSlot
        pyqt5_pkg.QtCore = qtcore_pkg
        sys.modules["PyQt5"] = pyqt5_pkg
        sys.modules["PyQt5.QtCore"] = qtcore_pkg

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
connect_payload = _load_module(
    "query_tool.utils.siot_debug.connect_payload",
    "query_tool/utils/siot_debug/connect_payload.py",
)
session = _load_module("query_tool.utils.siot_debug.session", "query_tool/utils/siot_debug/session.py")
service = _load_module("query_tool.utils.siot_debug.service", "query_tool/utils/siot_debug/service.py")
subprocess_runner = _load_module(
    "query_tool.utils.siot_debug.subprocess_runner",
    "query_tool/utils/siot_debug/subprocess_runner.py",
)

CloudCredentials = models.CloudCredentials
CommandResult = models.CommandResult
DeviceCredentials = models.DeviceCredentials


class _FakeQuery:
    init_error = None

    def get_device_info(self, dev_sn=None, dev_id=None):
        return {
            "data": {
                "records": [
                    {
                        "devId": "DEV001",
                        "devSN": dev_sn or "SN001",
                    }
                ]
            }
        }

    def is_siot_platform_device(self, dev_id=None, sn=None):
        return True

    def get_cloud_password(self, dev_id):
        return "cloud-password"

    def get_device_header(self, dev_sn):
        raise AssertionError("model fallback should not request device header")

    def get_device_version(self, dev_id):
        raise AssertionError("model fallback should not request device version")


class _DummyProcess:
    stdin = None
    stdout = None

    def poll(self):
        return None


class _DummyThread:
    def __init__(self):
        self.started = False
        self.joined = False

    def start(self):
        self.started = True

    def join(self):
        self.joined = True


class _DummyPrefetcher:
    def __init__(self, credentials):
        self.credentials = credentials
        self.started = False
        self.calls = []

    def start(self):
        self.started = True
        return self

    def get(self, *, require=False):
        self.calls.append(require)
        return self.credentials


class _FakeConnectSession:
    def __init__(self):
        self.connect_calls = 0
        self.execute_calls = 0

    def connect(self, credentials, status_callback=None):
        self.connect_calls += 1

    def execute_command(self, command, timeout_ms, progress_callback=None, stream_log_callback=None):
        self.execute_calls += 1
        return CommandResult(
            command=command,
            command_kind="syscmd",
            success=False,
            display_text="",
            acknowledged=False,
            responses=[],
            streamed_packets=0,
            binary_payload=b"",
        )

    def close(self):
        return None


class SiotDebugConnectOptimizationTests(unittest.TestCase):
    def test_build_connect_payload_includes_prefetched_credentials(self):
        credentials = DeviceCredentials(
            sn="SN001",
            username="admin",
            password="device-password",
            dev_id="DEV001",
            is_siot=True,
            protocol="siot",
        )
        prefetched = CloudCredentials(
            client_id="cid",
            access_node="access-node",
            access_jwt_token="access-token",
            relay_jwt_token="relay-token",
            relay_nodes="relay-a:0",
            vip_relay_nodes="vip-a:0",
            jwt_key_version=7,
        )

        payload = connect_payload.build_connect_payload(
            device_credentials=credentials,
            cloud_username="cloud-user",
            cloud_password="cloud-pass",
            prefetched_cloud_credentials=prefetched,
        )

        self.assertEqual("connect", payload["action"])
        self.assertEqual("cid", payload["cloud"]["credentials"]["client_id"])
        self.assertEqual("SN001", payload["device"]["sn"])

    def test_resolve_device_credentials_skips_model_fallback_requests(self):
        with mock.patch.object(service, "get_shared_device_query", return_value=_FakeQuery()):
            credentials, context = service.resolve_device_credentials("SN001", "prod", "user", "pass")

        self.assertEqual("SN001", credentials.sn)
        self.assertEqual("DEV001", credentials.dev_id)
        self.assertEqual("cloud-password", credentials.password)
        self.assertEqual("", context["model"])

    def test_connect_with_accounts_passes_prefetched_cloud_credentials_to_subprocess(self):
        worker = service.SiotDebugWorker()
        prefetched = CloudCredentials(
            client_id="cid",
            access_node="access-node",
            access_jwt_token="access-token",
            relay_jwt_token="relay-token",
            relay_nodes="relay-a:0",
            vip_relay_nodes="vip-a:0",
            jwt_key_version=7,
        )
        reader_thread = _DummyThread()

        worker._send_to_process = mock.Mock()
        worker._close_process = mock.Mock()
        worker._is_connect_cancelled = mock.Mock(return_value=False)

        credentials = DeviceCredentials(
            sn="SN001",
            username="admin",
            password="device-password",
            dev_id="DEV001",
            is_siot=True,
            protocol="siot",
        )
        context = {"sn": "SN001", "protocol": "siot", "is_siot": True, "model": ""}

        prefetcher = _DummyPrefetcher(prefetched)
        with mock.patch.object(service, "CloudCredentialPrefetcher", return_value=prefetcher):
            with mock.patch.object(service, "resolve_device_credentials", return_value=(credentials, context)):
                with mock.patch.object(service.subprocess, "Popen", return_value=_DummyProcess()):
                    with mock.patch.object(service.threading, "Thread", return_value=reader_thread):
                        worker.connect_with_accounts("SN001", "prod", "user", "pass", "cloud-user", "cloud-pass")

        payload = worker._send_to_process.call_args.args[0]
        self.assertTrue(prefetcher.started)
        self.assertEqual([True], prefetcher.calls)
        self.assertEqual("cid", payload["cloud"]["credentials"]["client_id"])
        self.assertEqual("access-node", payload["cloud"]["credentials"]["access_node"])
        self.assertEqual("SN001", payload["device"]["sn"])

    def test_device_session_prefetched_credentials_and_query_wait_timeout(self):
        prefetched = CloudCredentials(
            client_id="cid",
            access_node="access-node",
            access_jwt_token="access-token",
            relay_jwt_token="relay-token",
            relay_nodes="relay-a:0",
            vip_relay_nodes="vip-a:0",
            jwt_key_version=7,
        )
        device_session = session.DeviceSession.__new__(session.DeviceSession)
        device_session._prefetched_cloud_credentials = prefetched
        device_session.cloud_username = "cloud-user"
        device_session.cloud_password = "cloud-pass"
        device_session._gateway_id = ""
        device_session._gateway_id_4g = ""
        device_session._device_online = False
        device_session._device_is_4g = False

        with mock.patch.object(session, "fetch_cloud_credentials") as fetch_mock:
            resolved = session.DeviceSession._load_cloud_credentials_for_connect(device_session, force_refresh=False)

        self.assertIs(prefetched, resolved)
        self.assertIsNone(device_session._prefetched_cloud_credentials)
        fetch_mock.assert_not_called()
        self.assertEqual(session.DEFAULT_QUERY_DEVICE_DELAY_S, session.DeviceSession._query_device_wait_timeout(device_session))

        device_session._gateway_id = "gw-1"
        self.assertEqual(0.0, session.DeviceSession._query_device_wait_timeout(device_session))

    def test_connect_with_retries_treats_empty_start_result_as_soft_success_without_retry(self):
        fake_session = _FakeConnectSession()
        credentials = DeviceCredentials(
            sn="SN001",
            username="admin",
            password="device-password",
            dev_id="DEV001",
            is_siot=True,
            protocol="siot",
        )

        returned = subprocess_runner._connect_with_retries(lambda: fake_session, credentials)

        self.assertIs(fake_session, returned)
        self.assertEqual(1, fake_session.connect_calls)
        self.assertEqual(1, fake_session.execute_calls)


if __name__ == "__main__":
    unittest.main()
