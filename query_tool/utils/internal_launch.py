from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_ENTRY = PROJECT_ROOT / "run.py"


def _is_compiled_app() -> bool:
    return (
        getattr(sys, "frozen", False)
        or "__compiled__" in globals()
        or hasattr(sys, "nuitka_binary_dir")
    )


def _is_real_app_executable(path_like: str | None) -> bool:
    if not path_like:
        return False
    try:
        path = Path(path_like).resolve()
    except Exception:
        return False
    return path.suffix.lower() == ".exe" and path.name.lower() not in ("python.exe", "pythonw.exe")


def _get_current_program() -> str:
    if _is_compiled_app():
        # Nuitka onefile 场景优先复用当前已展开的运行体，避免每次内部命令都重新拉起外层 stub。
        for candidate in (sys.executable, sys.argv[0] if sys.argv else ""):
            if _is_real_app_executable(candidate):
                return str(Path(candidate).resolve())
    if sys.argv and sys.argv[0]:
        return str(Path(sys.argv[0]).resolve())
    return sys.executable


def build_internal_command(*args: str) -> list[str]:
    """Build a child-process command that works in dev and packaged builds."""
    if _is_compiled_app():
        return [_get_current_program(), *args]
    return [sys.executable, str(APP_ENTRY), *args]
