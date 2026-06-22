"""
SIOT internal command launcher.

开发态兼容入口，用于直接运行内部 SIOT 命令。
发布版已切换为单 exe 模式，由 `run.py` 统一分发内部命令，
不再单独构建 sidecar helper 可执行文件。
"""
from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    from query_tool.utils.siot_debug.internal_cli import dispatch_internal_command

    exit_code = dispatch_internal_command(sys.argv[1:])
    if exit_code is None:
        print("unknown internal command", file=sys.stderr)
        return 2
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
