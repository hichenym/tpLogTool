from __future__ import annotations

import ctypes
import json
import sys
import threading
from pathlib import Path
from typing import Sequence

from .siot_client import SdkLibraries


def dispatch_internal_command(argv: Sequence[str]) -> int | None:
    if not argv:
        return None

    command = argv[0]
    if command == "--siot-subprocess-runner":
        from .subprocess_runner import main as subprocess_runner_main

        return int(subprocess_runner_main() or 0)
    if command == "--siot-helper-prepare":
        return _run_prepare_helper(argv[1:])
    if command == "--siot-helper-probe":
        return _run_probe_helper(argv[1:])
    if command == "--upgrade-stress-runner":
        from query_tool.utils.upgrade_stress_runner import run_task

        if len(argv) < 2:
            print("missing upgrade stress task id", file=sys.stderr)
            return 220
        return int(run_task(argv[1]) or 0)
    return None


def _load_sdk_runtime(sdk_bin_dir: Path) -> SdkLibraries:
    return SdkLibraries(sdk_bin_dir)


def _run_prepare_helper(argv: Sequence[str]) -> int:
    if len(argv) != 5:
        print("invalid prepare helper arguments", file=sys.stderr)
        return 200

    sdk_bin_dir = Path(argv[0])
    params_json = argv[1]
    sn = argv[2].encode("utf-8")
    user = argv[3].encode("utf-8")
    password = argv[4].encode("utf-8")

    sdk = _load_sdk_runtime(sdk_bin_dir)
    lib = sdk.lib
    lib.Siot_CreateClient.restype = ctypes.c_void_p
    lib.Siot_CreateClient.argtypes = []
    lib.Siot_DestroyClient.restype = None
    lib.Siot_DestroyClient.argtypes = [ctypes.c_void_p]
    lib.Siot_Connect.restype = ctypes.c_int
    lib.Siot_Connect.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.Siot_Login.restype = ctypes.c_int
    lib.Siot_Login.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
    lib.Siot_Disconnect.restype = ctypes.c_int
    lib.Siot_Disconnect.argtypes = [ctypes.c_void_p]
    lib.Siot_GetLastError.restype = ctypes.c_char_p
    lib.Siot_GetLastError.argtypes = [ctypes.c_void_p]

    handle = lib.Siot_CreateClient()
    if not handle:
        print("Siot_CreateClient failed", file=sys.stderr)
        return 201

    def last_error() -> str:
        raw = lib.Siot_GetLastError(handle)
        return raw.decode("utf-8", errors="replace") if raw else "unknown error"

    try:
        ret = lib.Siot_Connect(handle, params_json.encode("utf-8"))
        if ret != 0:
            print(last_error(), file=sys.stderr)
            return 202

        ret = lib.Siot_Login(handle, sn, user, password)
        if ret != 0:
            print(last_error(), file=sys.stderr)
            return 203
        return 0
    finally:
        try:
            lib.Siot_Disconnect(handle)
        except Exception:
            pass
        lib.Siot_DestroyClient(handle)


def _run_probe_helper(argv: Sequence[str]) -> int:
    if len(argv) != 2:
        print(json.dumps({"probe_error": "invalid probe helper arguments"}, ensure_ascii=False))
        return 210

    sdk_bin_dir = Path(argv[0])
    try:
        probe = json.loads(argv[1])
    except json.JSONDecodeError as exc:
        print(json.dumps({"probe_error": f"invalid probe payload: {exc}"}, ensure_ascii=False))
        return 210

    sdk = _load_sdk_runtime(sdk_bin_dir)
    lib = sdk.lib

    TPSIOT_EventCallback = ctypes.CFUNCTYPE(
        None,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_uint8),
        ctypes.c_uint32,
        ctypes.c_void_p,
    )

    class TPSIOT_DeviceMessage(ctypes.Structure):
        _fields_ = [
            ("deviceSN", ctypes.c_char_p),
            ("buffer", ctypes.POINTER(ctypes.c_uint8)),
            ("len", ctypes.c_uint32),
            ("feedbackCode", ctypes.c_uint8),
        ]

    lib.TPSRTC_SetProperties.restype = ctypes.c_int
    lib.TPSRTC_SetProperties.argtypes = [ctypes.c_int, ctypes.c_char_p]
    lib.TPSRTC_Startup.restype = ctypes.c_int
    lib.TPSRTC_Startup.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    lib.TPSRTC_Cleanup.restype = None
    lib.TPSRTC_Cleanup.argtypes = []
    lib.TPSIOT_SetProperties.restype = ctypes.c_int
    lib.TPSIOT_SetProperties.argtypes = [ctypes.c_int, ctypes.c_char_p]
    lib.TPSIOT_Connect.restype = ctypes.c_void_p
    lib.TPSIOT_Connect.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, TPSIOT_EventCallback, ctypes.c_void_p]
    lib.TPSIOT_Close.restype = ctypes.c_int
    lib.TPSIOT_Close.argtypes = [ctypes.c_void_p]
    lib.TPSIOT_AppSend.restype = ctypes.c_int
    lib.TPSIOT_AppSend.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_char_p,
        ctypes.c_uint8,
        ctypes.c_uint8,
    ]

    TPSIOT_ROLE_APP = 2
    TPSIOT_PROTOCOL_TCP = 2
    TPSIOT_TERMINAL_NORMAL = 0
    TPSIOT_CONN_HANDSHAKED = 4
    TPSIOT_CONN_HANDSHAKED_FAILED = 5
    TPSIOT_CONN_CLOSED = 0
    TPSIOT_CONN_FAILED = 2
    TPSIOT_CONN_APP_RECEIVED_DATA = 10
    TPSIOT_FB_QUERY_DEVICE = 0x1
    TPSIOT_FB_UNREACHABLE_DEVICE = 0x2
    TPSIOT_PROPERTY_ACCESS_ADDR = 0
    TPSIOT_PROPERTY_ACCESS_PROTOCOL = 1
    TPSIOT_PROPERTY_CLIENT_ID = 2
    TPSIOT_PROPERTY_TOKEN = 4
    TPSIOT_PROPERTY_KEY_INDEX = 5
    TPSRTC_PROPERTY_ENDPOINT = 0
    TPSRTC_PROPERTY_LOGLEVEL = 1

    handshake_event = threading.Event()
    status_event = threading.Event()
    state = {"handshake": False, "status": None}

    def on_event(conn, event, err_code, data_ptr, data_len, arg):
        if event == TPSIOT_CONN_HANDSHAKED:
            state["handshake"] = True
            handshake_event.set()
            return
        if event in (TPSIOT_CONN_HANDSHAKED_FAILED, TPSIOT_CONN_CLOSED, TPSIOT_CONN_FAILED):
            handshake_event.set()
            return
        if event != TPSIOT_CONN_APP_RECEIVED_DATA or not data_ptr:
            return

        message = ctypes.cast(data_ptr, ctypes.POINTER(TPSIOT_DeviceMessage)).contents
        if message.feedbackCode == TPSIOT_FB_UNREACHABLE_DEVICE:
            state["status"] = {"online": 0, "online4g": 0, "unreachable": 1}
            status_event.set()
            return
        if message.feedbackCode != TPSIOT_FB_QUERY_DEVICE:
            return
        if not message.buffer or message.len == 0:
            return
        raw = ctypes.string_at(message.buffer, message.len)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            payload = {"probe_error": "invalid status payload"}
        state["status"] = payload
        status_event.set()

    cb = TPSIOT_EventCallback(on_event)
    conn = None
    try:
        lib.TPSRTC_SetProperties(TPSRTC_PROPERTY_ENDPOINT, probe["client_id"].encode("utf-8"))
        lib.TPSRTC_SetProperties(TPSRTC_PROPERTY_LOGLEVEL, b"off")
        ret = lib.TPSRTC_Startup(None, None, None, 0, 0)
        if ret != 0:
            print(json.dumps({"probe_error": f"TPSRTC_Startup failed: {ret}"}, ensure_ascii=False))
            return 211

        lib.TPSIOT_SetProperties(TPSIOT_PROPERTY_ACCESS_ADDR, probe["access_node"].encode("utf-8"))
        lib.TPSIOT_SetProperties(TPSIOT_PROPERTY_ACCESS_PROTOCOL, b"2")
        lib.TPSIOT_SetProperties(TPSIOT_PROPERTY_CLIENT_ID, probe["client_id"].encode("utf-8"))
        lib.TPSIOT_SetProperties(TPSIOT_PROPERTY_TOKEN, probe["access_token"].encode("utf-8"))
        lib.TPSIOT_SetProperties(TPSIOT_PROPERTY_KEY_INDEX, str(probe["key_version"]).encode("utf-8"))

        conn = lib.TPSIOT_Connect(TPSIOT_ROLE_APP, TPSIOT_PROTOCOL_TCP, TPSIOT_TERMINAL_NORMAL, cb, None)
        if not conn:
            print(json.dumps({"probe_error": "TPSIOT_Connect returned NULL"}, ensure_ascii=False))
            return 212

        if not handshake_event.wait(15.0) or not state["handshake"]:
            print(json.dumps({"probe_error": "signaling handshake failed"}, ensure_ascii=False))
            return 213

        lib.TPSIOT_AppSend(
            conn,
            TPSIOT_PROTOCOL_TCP,
            probe["sn"].encode("utf-8"),
            b"",
            None,
            0,
            b"query_dev",
            0,
            TPSIOT_FB_QUERY_DEVICE,
        )

        if not status_event.wait(5.0) or state["status"] is None:
            print(json.dumps({"probe_error": "query_dev timeout"}, ensure_ascii=False))
            return 214

        print(json.dumps(state["status"], ensure_ascii=False))
        return 0
    finally:
        if conn:
            try:
                lib.TPSIOT_Close(conn)
            except Exception:
                pass
        try:
            lib.TPSRTC_Cleanup()
        except Exception:
            pass
