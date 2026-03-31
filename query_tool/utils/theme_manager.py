"""
主题管理器
只负责颜色 Token 的定义和切换，不包含任何 QSS 字符串。
所有 QSS 生成逻辑统一在 style_manager.py 中。
"""
from PyQt5.QtCore import QObject, pyqtSignal


# ──────────────────────────────────────────────
# 颜色 Token 定义
# ──────────────────────────────────────────────

DARK_THEME = {
    # 背景层级
    "bg_dark":    "#2b2b2b",   # 最深背景（窗口/状态栏）
    "bg_mid":     "#3c3c3c",   # 中间背景（表格/下拉列表）
    "bg_light":   "#404040",   # 较浅背景（输入框/控件）
    "bg_hover":   "#4a4a4a",   # 悬停背景
    "bg_pressed": "#505050",   # 按下背景
    # 文字
    "text_primary":   "#e0e0e0",
    "text_secondary": "#b0b0b0",
    "text_disabled":  "#606060",
    "text_hint":      "#909090",
    # 边框
    "border":         "#555555",
    "border_dark":    "#3c3c3c",
    "border_hover":   "#6a6a6a",
    # 强调色
    "accent":         "#0d7377",
    "accent_dim":     "#0a5a5d",
    "accent_select":  "rgba(13, 115, 119, 0.3)",
    # 状态色
    "status_online":  "#00FF00",
    "status_offline": "#FF0000",
    "status_pending": "#FFA500",
    "status_info":    "#4a9eff",
    # 选中背景
    "selection_bg":   "#505050",
    # 标题栏模式
    "dark_titlebar":  True,
}

LIGHT_THEME = {
    # 背景层级
    "bg_dark":    "#f0f0f0",
    "bg_mid":     "#e0e0e0",
    "bg_light":   "#ffffff",
    "bg_hover":   "#d0d0d0",
    "bg_pressed": "#c0c0c0",
    # 文字
    "text_primary":   "#1a1a1a",
    "text_secondary": "#555555",
    "text_disabled":  "#aaaaaa",
    "text_hint":      "#888888",
    # 边框
    "border":         "#bbbbbb",
    "border_dark":    "#cccccc",
    "border_hover":   "#888888",
    # 强调色
    "accent":         "#0d7377",
    "accent_dim":     "#0a5a5d",
    "accent_select":  "rgba(13, 115, 119, 0.2)",
    # 状态色
    "status_online":  "#00aa00",
    "status_offline": "#cc0000",
    "status_pending": "#cc7700",
    "status_info":    "#1a6fcc",
    # 选中背景
    "selection_bg":   "#c8e0f0",
    # 标题栏模式
    "dark_titlebar":  False,
}


class ThemeManager(QObject):
    """全局主题管理器（单例）"""

    theme_changed = pyqtSignal()

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            instance = super().__new__(cls)
            QObject.__init__(instance)
            instance._initialized = True
            instance._is_dark = True
            instance._tokens = DARK_THEME.copy()
            cls._instance = instance
        return cls._instance

    def __init__(self):
        pass  # 单例已在 __new__ 中完整初始化

    # ── 公共 API ──────────────────────────────

    @property
    def is_dark(self) -> bool:
        return self._is_dark

    def token(self, key: str) -> str:
        """获取当前主题的颜色 token"""
        return self._tokens.get(key, "")

    def set_dark(self):
        if self._is_dark:
            return
        self._is_dark = True
        self._tokens = DARK_THEME.copy()
        self.theme_changed.emit()

    def set_light(self):
        if not self._is_dark:
            return
        self._is_dark = False
        self._tokens = LIGHT_THEME.copy()
        self.theme_changed.emit()

    def toggle(self):
        if self._is_dark:
            self.set_light()
        else:
            self.set_dark()


# ── 全局单例和快捷函数 ────────────────────────

theme_manager = ThemeManager()


def t(key: str) -> str:
    """快捷函数：获取当前主题颜色 token，用于 f-string 内联"""
    return theme_manager.token(key)
