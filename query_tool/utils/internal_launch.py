from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_ENTRY = PROJECT_ROOT / "run.py"


def build_internal_command(*args: str) -> list[str]:
    """Build a child-process command that works in dev and packaged builds."""
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, str(APP_ENTRY), *args]
