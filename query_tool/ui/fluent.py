"""Thin wrapper around qfluentwidgets so the shell can migrate incrementally."""

from __future__ import annotations

from enum import Enum

from PyQt5.QtGui import QColor, QIcon

ACCENT_COLOR = QColor("#0D7377")

try:
    from qfluentwidgets import (
        FluentIcon,
        NavigationInterface,
        NavigationItemPosition,
        Theme,
        setTheme,
        setThemeColor,
    )

    QFLUENT_AVAILABLE = True
except Exception:
    QFLUENT_AVAILABLE = False

    class _FluentIconFallback:
        pass

    class _NavigationInterfaceFallback:  # pragma: no cover - runtime guard only
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("qfluentwidgets is not installed")

    class _NavigationPositionFallback(Enum):
        TOP = 0
        BOTTOM = 1

    class _ThemeFallback(Enum):
        LIGHT = "Light"
        DARK = "Dark"

    FluentIcon = _FluentIconFallback()
    NavigationInterface = _NavigationInterfaceFallback
    NavigationItemPosition = _NavigationPositionFallback
    Theme = _ThemeFallback

    def setTheme(*_args, **_kwargs):
        return None

    def setThemeColor(*_args, **_kwargs):
        return None


def apply_fluent_theme(is_dark: bool, lazy: bool = True) -> bool:
    """Sync the qfluentwidgets theme with the app theme when available."""
    if not QFLUENT_AVAILABLE:
        return False

    setThemeColor(ACCENT_COLOR, lazy=lazy)
    setTheme(Theme.DARK if is_dark else Theme.LIGHT, lazy=lazy)
    return True


def resolve_fluent_icon(icon_name: str, fallback_path: str = ""):
    """Return a Fluent icon when possible, otherwise fall back to a resource icon."""
    if QFLUENT_AVAILABLE and hasattr(FluentIcon, icon_name):
        return getattr(FluentIcon, icon_name)
    return QIcon(fallback_path) if fallback_path else QIcon()
