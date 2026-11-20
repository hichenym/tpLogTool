import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
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
subprocess_runner = _load_module(
    "query_tool.utils.siot_debug.subprocess_runner",
    "query_tool/utils/siot_debug/subprocess_runner.py",
)
CommandResult = models.CommandResult
TransferProgress = models.TransferProgress


class _FakeSession:
    def __init__(self):
        self.device = SimpleNamespace(sn="SN001")
        self.calls = []

    def execute_command(self, command, timeout_ms, progress_callback=None, stream_log_callback=None):
        self.calls.append(
            {
                "command": command,
                "timeout_ms": timeout_ms,
                "progress_callback": progress_callback,
                "stream_log_callback": stream_log_callback,
            }
        )
        if progress_callback is not None:
            progress_callback(
                TransferProgress(
                    command=command,
                    filename="config.bin",
                    start_pos=0,
                    chunk_size=512,
                    received_bytes=512,
                    packet_index=1,
                    finished=False,
                )
            )
        return CommandResult(
            command=command,
            command_kind="GetSystemCfg",
            success=True,
            display_text="",
            acknowledged=True,
            binary_payload=b"",
            filename="config.bin",
            received_bytes=512,
            streamed_packets=1,
        )


class GetSystemCfgProgressTests(unittest.TestCase):
    def test_getsystemcfg_emits_prepare_progress_before_stream_progress(self):
        session = _FakeSession()
        events = []

        def fake_emit(event, **payload):
            events.append((event, payload))

        with mock.patch.object(subprocess_runner, "_emit", side_effect=fake_emit):
            subprocess_runner._handle_command(
                session,
                {
                    "command": "GetSystemCfg /tmp/config.bin",
                    "timeout_ms": 2000,
                    "download_root": "",
                },
            )

        progress_events = [payload for event, payload in events if event == "progress"]
        self.assertEqual(2, len(progress_events))
        self.assertEqual(1, len(session.calls))
        self.assertEqual("GetSystemCfg /tmp/config.bin", session.calls[0]["command"])
        self.assertEqual(progress_events[0]["progress_id"], progress_events[1]["progress_id"])
        self.assertTrue(progress_events[0]["message"].endswith("config.bin..."))
        self.assertIn("config.bin", progress_events[1]["message"])

    def test_getsystemcfg_no_longer_issues_extra_probe_commands(self):
        session = _FakeSession()

        with mock.patch.object(subprocess_runner, "_emit"):
            subprocess_runner._handle_command(
                session,
                {
                    "command": "GetSystemCfg /tmp/config.bin",
                    "timeout_ms": 2000,
                    "download_root": "",
                },
            )

        self.assertEqual(["GetSystemCfg /tmp/config.bin"], [call["command"] for call in session.calls])


if __name__ == "__main__":
    unittest.main()
