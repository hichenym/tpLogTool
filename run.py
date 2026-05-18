"""
Query Tool - Launcher Script
启动查询工具
"""
from __future__ import annotations

import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _set_windows_appusermodel_id() -> None:
    """为 GUI 进程设置稳定的 Windows 任务栏身份。"""
    if sys.platform != "win32":
        return

    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TPQueryTool.Desktop")
    except Exception:
        pass


def _dispatch_internal_command() -> int | None:
    from query_tool.utils.siot_debug.internal_cli import dispatch_internal_command

    return dispatch_internal_command(sys.argv[1:])


if __name__ == "__main__":
    _set_windows_appusermodel_id()
    exit_code = _dispatch_internal_command()
    if exit_code is not None:
        raise SystemExit(exit_code)

    from query_tool.main import main

    main()
