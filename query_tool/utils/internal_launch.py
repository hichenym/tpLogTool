from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_ENTRY = PROJECT_ROOT / "run.py"


def _is_compiled_app() -> bool:
    return getattr(sys, "frozen", False) or "__compiled__" in globals()


def _get_current_program() -> str:
    if sys.argv and sys.argv[0]:
        return str(Path(sys.argv[0]).resolve())
    return sys.executable


def build_internal_command(*args: str) -> list[str]:
    """Build a child-process command that works in dev and packaged builds."""
    if _is_compiled_app():
        return [_get_current_program(), *args]
    return [sys.executable, str(APP_ENTRY), *args]
