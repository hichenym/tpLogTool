from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

from .config import SDK_BIN_DIR, resolve_sdk_bin_dir


class SiotError(RuntimeError):
    pass


TPSIOT_EventCallback = ctypes.CFUNCTYPE(
    None,
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.POINTER(ctypes.c_uint8),
    ctypes.c_uint32,
    ctypes.c_void_p,
)

TPSRTC_PeerEventCallback = ctypes.CFUNCTYPE(
    None,
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.POINTER(ctypes.c_uint8),
    ctypes.c_uint32,
    ctypes.c_void_p,
)

TPSRTC_RecvDataCallback = ctypes.CFUNCTYPE(
    None,
    ctypes.c_void_p,
    ctypes.c_char_p,
    ctypes.c_int,
    ctypes.POINTER(ctypes.c_uint8),
    ctypes.c_uint32,
    ctypes.c_void_p,
)

TPSRTC_SendSDPCallback = ctypes.CFUNCTYPE(
    None,
    ctypes.c_uint8,
    ctypes.c_char_p,
    ctypes.c_uint32,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_void_p,
)


class TPSIOT_DeviceMessage(ctypes.Structure):
    _fields_ = [
        ("deviceSN", ctypes.c_char_p),
        ("buffer", ctypes.POINTER(ctypes.c_uint8)),
        ("len", ctypes.c_uint32),
        ("feedbackCode", ctypes.c_uint8),
    ]


class SdkLibraries:
    def __init__(self, sdk_bin_dir: Path | None = None) -> None:
        self.sdk_bin_dir = resolve_sdk_bin_dir(sdk_bin_dir or SDK_BIN_DIR)
        self._configure_search_path()
        self.lib = self._load_library("libsiot.dll")
        self.crypt = self._load_library("libtps_crypt.dll")
        self._bind_crypto()
        self._bind_low_level()

    def _configure_search_path(self) -> None:
        if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(self.sdk_bin_dir))

    def _load_library(self, name: str):
        path = self.sdk_bin_dir / name
        if not path.exists():
            raise FileNotFoundError(f"SDK library not found: {path}")
        loader = ctypes.WinDLL if sys.platform == "win32" else ctypes.CDLL
        return loader(str(path))

    def _bind_crypto(self) -> None:
        self.crypt.TpsProtocolEncode.restype = ctypes.c_int
        self.crypt.TpsProtocolEncode.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_char_p,
        ]

        self.crypt.TpsProtocolDecode.restype = ctypes.c_int
        self.crypt.TpsProtocolDecode.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_char_p,
        ]

        self.crypt.TpsProtocolEncryptVersionNegotiate.restype = ctypes.c_int
        self.crypt.TpsProtocolEncryptVersionNegotiate.argtypes = [ctypes.c_int]

    def _bind_low_level(self) -> None:
        void_p = ctypes.c_void_p

        self.lib.TPSIOT_SetProperties.restype = ctypes.c_int
        self.lib.TPSIOT_SetProperties.argtypes = [ctypes.c_int, ctypes.c_char_p]

        self.lib.TPSIOT_Connect.restype = void_p
        self.lib.TPSIOT_Connect.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            TPSIOT_EventCallback,
            void_p,
        ]

        self.lib.TPSIOT_Close.restype = ctypes.c_int
        self.lib.TPSIOT_Close.argtypes = [void_p]

        self.lib.TPSIOT_RedirectAccess.restype = ctypes.c_int
        self.lib.TPSIOT_RedirectAccess.argtypes = [void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]

        self.lib.TPSIOT_AppSend.restype = ctypes.c_int
        self.lib.TPSIOT_AppSend.argtypes = [
            void_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_char_p,
            void_p,
            ctypes.c_uint32,
            ctypes.c_char_p,
            ctypes.c_uint8,
            ctypes.c_uint8,
        ]

        self.lib.TPSRTC_SetProperties.restype = ctypes.c_int
        self.lib.TPSRTC_SetProperties.argtypes = [ctypes.c_int, ctypes.c_char_p]

        self.lib.TPSRTC_Startup.restype = ctypes.c_int
        self.lib.TPSRTC_Startup.argtypes = [ctypes.c_char_p, void_p, void_p, ctypes.c_int, ctypes.c_int]

        self.lib.TPSRTC_Init.restype = ctypes.c_int
        self.lib.TPSRTC_Init.argtypes = [
            void_p,
            TPSRTC_SendSDPCallback,
            void_p,
            void_p,
            void_p,
        ]

        self.lib.TPSRTC_Cleanup.restype = None
        self.lib.TPSRTC_Cleanup.argtypes = []

        self.lib.TPSRTC_ConnectPeer.restype = void_p
        self.lib.TPSRTC_ConnectPeer.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_char_p,
            TPSRTC_PeerEventCallback,
            TPSRTC_RecvDataCallback,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_int,
            void_p,
            void_p,
            ctypes.c_int,
            ctypes.c_bool,
            ctypes.c_bool,
        ]

        self.lib.TPSRTC_DisconnectPeer.restype = ctypes.c_int
        self.lib.TPSRTC_DisconnectPeer.argtypes = [void_p]

        self.lib.TPSRTC_SendData.restype = ctypes.c_int
        self.lib.TPSRTC_SendData.argtypes = [
            void_p,
            void_p,
            ctypes.c_uint32,
            ctypes.c_uint8,
            ctypes.c_char_p,
        ]

        self.lib.TPSRTC_ParseAnswer.restype = ctypes.c_int
        self.lib.TPSRTC_ParseAnswer.argtypes = [void_p, ctypes.c_char_p, ctypes.c_uint32]

        self.lib.TPSRTC_ParseCandidates.restype = ctypes.c_int
        self.lib.TPSRTC_ParseCandidates.argtypes = [void_p, ctypes.c_char_p, ctypes.c_uint32]

        self.lib.TPSRTC_ParseErrorCode.restype = None
        self.lib.TPSRTC_ParseErrorCode.argtypes = [
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_uint16),
            ctypes.POINTER(ctypes.c_uint16),
        ]
