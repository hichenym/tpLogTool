"""
SIOT helper launcher.

独立的内部命令入口，供发布版优先作为 sidecar helper 使用，
减少 GUI 主程序在 onefile 模式下频繁自拉起自身。
"""
from __future__ import annotations

import os
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    from query_tool.utils.siot_debug.internal_cli import dispatch_internal_command

    exit_code = dispatch_internal_command(sys.argv[1:])
    if exit_code is None:
        print("unknown internal command", file=sys.stderr)
        return 2
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
