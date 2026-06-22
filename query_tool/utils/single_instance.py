"""应用单实例控制。"""
from __future__ import annotations

import hashlib
import os
import sys
from typing import Optional

from PyQt5.QtCore import QObject, QIODevice, pyqtSignal
from PyQt5.QtNetwork import QAbstractSocket, QLocalServer, QLocalSocket


def _normalize_scope_path(path: str) -> str:
    """标准化作用域路径，保证同一安装目录生成稳定实例名。"""
    normalized = os.path.abspath(path or "")
    return os.path.normcase(normalized)


def build_server_name(scope_path: str) -> str:
    """根据程序路径生成稳定的本地服务器名。"""
    normalized = _normalize_scope_path(scope_path)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"TPQueryTool.Desktop.{digest}"


def get_current_scope_path() -> str:
    """获取当前应用实例作用域路径。"""
    for candidate in (sys.argv[0] if sys.argv else "", sys.executable, __file__):
        if candidate:
            return _normalize_scope_path(candidate)
    return _normalize_scope_path("TPQueryTool")


class SingleInstanceController(QObject):
    """通过 QLocalServer/QLocalSocket 实现单实例和唤醒现有窗口。"""

    activation_requested = pyqtSignal()

    def __init__(self, server_name: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.server_name = server_name
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._handle_new_connection)

    @classmethod
    def for_current_app(cls, parent: Optional[QObject] = None) -> "SingleInstanceController":
        return cls(build_server_name(get_current_scope_path()), parent=parent)

    @classmethod
    def notify_existing_instance(cls, server_name: str, timeout_ms: int = 800) -> bool:
        """向已运行实例发送激活请求。"""
        socket = QLocalSocket()
        socket.connectToServer(server_name, QIODevice.WriteOnly)
        if not socket.waitForConnected(timeout_ms):
            return False

        try:
            return True
        finally:
            socket.disconnectFromServer()
            socket.waitForDisconnected(100)

    def start(self) -> bool:
        """开始监听激活请求。"""
        if self._server.isListening():
            return True

        if self._server.listen(self.server_name):
            return True

        if self._server.serverError() == QAbstractSocket.AddressInUseError:
            QLocalServer.removeServer(self.server_name)
            return self._server.listen(self.server_name)

        return False

    def close(self) -> None:
        """停止监听并清理本地服务器。"""
        if self._server.isListening():
            self._server.close()
        QLocalServer.removeServer(self.server_name)

    def _handle_new_connection(self) -> None:
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket is None:
                continue
            try:
                self.activation_requested.emit()
            finally:
                socket.disconnectFromServer()
                socket.deleteLater()
