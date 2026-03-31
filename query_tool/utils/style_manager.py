"""
样式管理器
所有 QSS 字符串生成逻辑的唯一入口。

# 新增控件样式的步骤（只需改这一个文件）：
#
#   @classmethod
#   def get_MY_WIDGET(cls) -> str:
#       return f"QWidget {{ background: {t('bg_light')}; color: {t('text_primary')}; }}"
#
# 应用到控件：
#   StyleManager.apply(widget, "MY_WIDGET")
#
# 自定义控件自动响应主题切换，继承 ThemedWidget 并实现 refresh_theme：
#   class MyDialog(QDialog, ThemedWidget):
#       def refresh_theme(self):
#           StyleManager.apply(self.table, "TABLE")
"""
from query_tool.utils.theme_manager import theme_manager, t


# ══════════════════════════════════════════════════════════════
# ThemedWidget Mixin
# 继承此 Mixin 的控件会在主题切换时自动调用 refresh_theme()
# ══════════════════════════════════════════════════════════════

class ThemedWidget:
    """
    主题感知 Mixin。
    继承此类的 QWidget 子类会在主题切换时自动调用 refresh_theme()。
    对话框关闭时自动断开连接，不会累积信号。

    用法：
        class MyDialog(QDialog, ThemedWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                ThemedWidget.__init__(self)   # 注册主题监听
                self._init_ui()

            def refresh_theme(self):
                StyleManager.apply(self.table, "TABLE")
                StyleManager.apply(self.frame, "QUERY_FRAME")
    """

    def __init__(self):
        theme_manager.theme_changed.connect(self._on_theme_changed_mixin)
        # 如果是 QWidget 子类，在销毁时自动断开
        if hasattr(self, 'destroyed'):
            self.destroyed.connect(self._disconnect_theme)

    def _disconnect_theme(self):
        try:
            theme_manager.theme_changed.disconnect(self._on_theme_changed_mixin)
        except Exception:
            pass

    def _on_theme_changed_mixin(self):
        try:
            self.refresh_theme()
        except RuntimeError:
            # C++ 对象已被销毁，断开连接
            self._disconnect_theme()
        except Exception as e:
            from query_tool.utils.logger import logger
            logger.error(f"ThemedWidget.refresh_theme 失败 ({type(self).__name__}): {e}")

    def refresh_theme(self):
        """子类重写此方法以刷新自身样式"""
        pass


# ══════════════════════════════════════════════════════════════
# StyleManager — 所有 QSS 生成方法
# ══════════════════════════════════════════════════════════════

class StyleManager:
    """
    样式管理器。
    所有方法均为 classmethod，返回当前主题下的 QSS 字符串。

    命名规范：
        get_XXX()  → 返回 QSS 字符串
        apply()    → 直接应用到控件（推荐使用）
    """

    # ── 核心工具方法 ──────────────────────────────────────────

    @classmethod
    def apply(cls, widget, style_name: str):
        """
        应用样式到控件（推荐使用）。

        Args:
            widget:     Qt 控件
            style_name: 样式名，如 "TABLE"、"ACTION_BUTTON"

        示例：
            StyleManager.apply(self.table, "TABLE")
            StyleManager.apply(self.frame, "QUERY_FRAME")
        """
        getter = getattr(cls, f"get_{style_name}", None)
        if getter:
            widget.setStyleSheet(getter())
        else:
            from query_tool.utils.logger import logger
            logger.warning(f"StyleManager: 未找到样式 '{style_name}'")

    @classmethod
    def apply_to_widget(cls, widget, style_name: str):
        """向后兼容别名，等同于 apply()"""
        cls.apply(widget, style_name)

    @classmethod
    def get_style(cls, style_name: str) -> str:
        """获取样式字符串"""
        getter = getattr(cls, f"get_{style_name}", None)
        return getter() if getter else ""

    # ── 全局 QSS ──────────────────────────────────────────────

    @classmethod
    def build_global_stylesheet(cls) -> str:
        """构建全局 app.setStyleSheet() 的样式表"""
        return f"""
        QWidget {{
            background-color: {t('bg_dark')};
            color: {t('text_primary')};
        }}
        QTextEdit, QPlainTextEdit, QLineEdit {{
            background-color: {t('bg_light')};
            color: {t('text_primary')};
            border: 1px solid {t('border')};
            border-radius: 3px;
            padding: 4px;
            selection-background-color: {t('selection_bg')};
        }}
        QTextEdit:disabled, QPlainTextEdit:disabled, QLineEdit:disabled {{
            background-color: {t('bg_dark')};
            color: {t('text_disabled')};
            border: 1px solid {t('border_dark')};
        }}
        QComboBox {{
            background-color: {t('bg_light')};
            color: {t('text_primary')};
            border: 1px solid {t('border')};
            border-radius: 3px;
            padding: 4px;
            padding-right: 0px;
        }}
        QComboBox:hover {{ border: 1px solid {t('border')}; }}
        QComboBox:disabled {{
            background-color: {t('bg_dark')};
            color: {t('text_disabled')};
            border: 1px solid {t('border_dark')};
        }}
        QComboBox::drop-down {{
            border: none;
            background-color: {t('bg_pressed')};
            width: 24px;
            margin: 0px; padding: 0px;
            border-left: 1px solid {t('border')};
        }}
        QComboBox::drop-down:disabled {{
            background-color: {t('bg_mid')};
            border-left: 1px solid {t('border_dark')};
        }}
        QComboBox::down-arrow {{ image: none; width: 0px; }}
        QComboBox QAbstractItemView {{
            background-color: {t('bg_mid')};
            color: {t('text_primary')};
            selection-background-color: {t('selection_bg')};
            border: 1px solid {t('border')};
        }}
        QDateEdit {{
            background-color: {t('bg_light')};
            color: {t('text_primary')};
            border: 1px solid {t('border')};
            border-radius: 3px;
            padding: 4px;
        }}
        QDateEdit:hover {{ border: 1px solid {t('border')}; }}
        QDateEdit:disabled {{
            background-color: {t('bg_dark')};
            color: {t('text_disabled')};
            border: 1px solid {t('border_dark')};
        }}
        QDateEdit::drop-down {{
            border: none;
            background-color: {t('bg_pressed')};
        }}
        QDateEdit::drop-down:disabled {{ background-color: {t('bg_mid')}; }}
        QDateEdit QAbstractItemView {{
            background-color: {t('bg_mid')};
            color: {t('text_primary')};
            selection-background-color: {t('selection_bg')};
            border: 1px solid {t('border')};
        }}
        QDateTimeEdit {{
            background-color: {t('bg_light')};
            color: {t('text_primary')};
            border: 1px solid {t('border')};
            border-radius: 3px;
            padding: 4px;
        }}
        QDateTimeEdit:hover {{ border: 1px solid {t('border')}; }}
        QDateTimeEdit:disabled {{
            background-color: {t('bg_dark')};
            color: {t('text_disabled')};
            border: 1px solid {t('border_dark')};
        }}
        QDateTimeEdit::drop-down {{
            border: none;
            background-color: {t('bg_pressed')};
            width: 24px;
            border-left: 1px solid {t('border')};
        }}
        QDateTimeEdit::drop-down:disabled {{ background-color: {t('bg_mid')}; }}
        QDateTimeEdit::down-arrow {{ image: none; width: 0px; }}
        QDateTimeEdit QAbstractItemView {{
            background-color: {t('bg_mid')};
            color: {t('text_primary')};
            selection-background-color: {t('selection_bg')};
            border: 1px solid {t('border')};
        }}
        QCalendarWidget {{
            background-color: {t('bg_mid')};
            color: {t('text_primary')};
        }}
        QCalendarWidget QToolButton {{
            background-color: {t('bg_light')};
            color: {t('text_primary')};
            border: 1px solid {t('border')};
            border-radius: 3px;
        }}
        QCalendarWidget QMenu {{
            background-color: {t('bg_mid')};
            color: {t('text_primary')};
        }}
        QCalendarWidget QSpinBox {{
            background-color: {t('bg_light')};
            color: {t('text_primary')};
            border: 1px solid {t('border')};
        }}
        QCalendarWidget QWidget {{ alternate-background-color: {t('bg_light')}; }}
        QCalendarWidget QAbstractItemView:enabled {{
            background-color: {t('bg_mid')};
            color: {t('text_primary')};
            selection-background-color: {t('selection_bg')};
        }}
        QPushButton {{
            background-color: {t('bg_mid')};
            color: {t('text_primary')};
            border: 1px solid {t('border')};
            border-radius: 3px;
            padding: 5px 15px;
        }}
        QPushButton:hover {{
            background-color: {t('bg_hover')};
            border: 1px solid {t('border')};
        }}
        QPushButton:pressed {{ background-color: {t('bg_pressed')}; }}
        QPushButton:disabled {{
            background-color: {t('bg_dark')};
            color: {t('text_disabled')};
            border: 1px solid {t('border_dark')};
        }}
        QCheckBox {{
            color: {t('text_primary')};
            spacing: 5px;
        }}
        QCheckBox:disabled {{ color: {t('text_disabled')}; }}
        QCheckBox::indicator {{
            width: 16px; height: 16px;
            border: 1px solid {t('border')};
            border-radius: 3px;
            background-color: {t('bg_light')};
        }}
        QCheckBox::indicator:hover {{ border: 1px solid {t('border')}; }}
        QCheckBox::indicator:checked {{
            background-color: {t('accent')};
            border: 1px solid {t('accent')};
        }}
        QCheckBox::indicator:disabled {{
            background-color: {t('bg_dark')};
            border: 1px solid {t('border_dark')};
        }}
        QCheckBox::indicator:checked:disabled {{
            background-color: {t('accent_dim')};
            border: 1px solid {t('accent_dim')};
        }}
        QLabel {{
            color: {t('text_primary')};
            background-color: transparent;
        }}
        QStatusBar {{
            background-color: {t('bg_dark')};
            color: {t('text_primary')};
            border-top: 1px solid {t('border_dark')};
            border-right: none; border-bottom: none; border-left: none;
        }}
        QStatusBar::item {{ border: none; }}
        QStatusBar QLabel {{ border: none; }}
        QTableCornerButton::section {{
            background-color: {t('bg_dark')};
            border: 1px solid {t('border')};
        }}
        QScrollBar:vertical {{
            background-color: {t('bg_dark')};
            width: 12px; border: none; margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {t('border')};
            border-radius: 6px; min-height: 20px; margin: 2px;
        }}
        QScrollBar::handle:vertical:hover {{ background-color: {t('border_hover')}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px; background: none; border: none;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: {t('bg_dark')};
        }}
        QScrollBar:horizontal {{
            background-color: {t('bg_dark')};
            height: 12px; border: none; margin: 0px;
        }}
        QScrollBar::handle:horizontal {{
            background-color: {t('border')};
            border-radius: 6px; min-width: 20px; margin: 2px;
        }}
        QScrollBar::handle:horizontal:hover {{ background-color: {t('border_hover')}; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px; background: none; border: none;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: {t('bg_dark')};
        }}
        QDialog {{
            background-color: {t('bg_dark')};
            color: {t('text_primary')};
        }}
        QGroupBox {{
            background-color: transparent;
            color: {t('text_primary')};
            border: 1px solid {t('border')};
            border-radius: 5px;
            margin-top: 10px;
            font-weight: bold;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }}
        QFrame {{
            background-color: {t('bg_dark')};
            border: none;
        }}
        QMessageBox {{
            background-color: {t('bg_dark')};
            color: {t('text_primary')};
        }}
        QMessageBox QPushButton {{ min-width: 80px; }}
        QProgressBar {{
            border: 1px solid {t('border')};
            border-radius: 3px;
            background-color: {t('bg_mid')};
            text-align: center;
            color: {t('text_primary')};
        }}
        QProgressBar::chunk {{ background-color: {t('status_info')}; }}
        """

    # ── 组件级样式 ────────────────────────────────────────────
    # 每个方法对应一种控件，新增控件只需在此处添加新方法。

    @classmethod
    def get_MENU_BUTTON(cls) -> str:
        return f"""
        QPushButton {{
            border: none; padding: 4px 8px;
            background-color: transparent;
            color: {t('text_primary')}; font-size: 13px;
        }}
        QPushButton:hover {{ background-color: {t('bg_hover')}; }}
        QPushButton:checked {{
            background-color: {t('bg_pressed')};
            color: {t('text_primary')}; font-weight: bold;
        }}
        """

    @classmethod
    def get_SETTINGS_BUTTON(cls) -> str:
        return f"""
        QPushButton {{
            background-color: transparent;
            color: {t('text_hint')};
            border: none; border-radius: 3px; padding: 4px;
        }}
        QPushButton:hover {{
            background-color: {t('bg_hover')};
            color: {t('text_primary')};
        }}
        QPushButton:pressed {{ background-color: {t('bg_mid')}; }}
        """

    @classmethod
    def get_MENU_BAR(cls) -> str:
        return f"""
        QWidget {{
            background-color: {t('bg_dark')} !important;
            border-bottom: 1px solid {t('bg_mid')};
        }}
        """

    @classmethod
    def get_TABLE(cls) -> str:
        return f"""
        QTableWidget {{
            background-color: {t('bg_mid')};
            color: {t('text_primary')};
            gridline-color: {t('border')};
            border: 1px solid {t('border')};
            show-decoration-selected: 0;
        }}
        QTableWidget::item {{
            padding-right: 10px; border: none; outline: none;
        }}
        QTableWidget::item:selected {{
            background-color: {t('accent_select')};
            border: none; outline: none;
        }}
        QTableWidget::item:focus {{
            background-color: {t('accent_select')};
            border: none; outline: none;
        }}
        QTableWidget:focus {{
            outline: none; border: 1px solid {t('border')};
        }}
        QHeaderView::section {{
            background-color: {t('bg_dark')};
            color: {t('text_primary')};
            border: 1px solid {t('border')}; padding: 4px;
        }}
        QTableCornerButton::section {{
            background-color: {t('bg_dark')};
            border: 1px solid {t('border')};
        }}
        QScrollBar:vertical {{
            background-color: {t('bg_dark')};
            width: 12px; border: none; margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {t('border')};
            border-radius: 6px; min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{ background-color: {t('border_hover')}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """

    @classmethod
    def get_SPLITTER(cls) -> str:
        return f"""
        QSplitter::handle {{
            background-color: {t('border')};
            margin: 5px 0px 5px 0px;
        }}
        QSplitter::handle:hover {{ background-color: {t('border_hover')}; }}
        """

    @classmethod
    def get_PLAINTEXT_EDIT_TABLE(cls) -> str:
        return f"""
        QPlainTextEdit {{
            background-color: {t('bg_light')};
            color: {t('text_primary')};
            border: 1px solid {t('border')}; border-radius: 0px;
        }}
        QPlainTextEdit:focus {{
            border: 1px solid {t('border')}; outline: none;
        }}
        QScrollBar:vertical {{
            background-color: {t('bg_dark')};
            width: 12px; border: none; margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {t('border')};
            border-radius: 6px; min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{ background-color: {t('border_hover')}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """

    @classmethod
    def get_VERSION_LABEL(cls) -> str:
        return f"color: {t('text_secondary')}; padding-right: 10px; border: none; background-color: transparent;"

    @classmethod
    def get_COMBOBOX(cls) -> str:
        return f"""
        QComboBox {{
            background-color: {t('bg_light')};
            color: {t('text_primary')};
            border: 1px solid {t('border')};
            border-radius: 3px; padding: 4px; padding-right: 0px;
        }}
        QComboBox:hover {{ border: 1px solid {t('border')}; }}
        QComboBox:disabled {{
            background-color: {t('bg_dark')};
            color: {t('text_disabled')};
            border: 1px solid {t('border_dark')};
        }}
        QComboBox::drop-down {{
            border: none; background-color: {t('bg_pressed')};
            width: 24px; margin: 0px; padding: 0px;
            border-left: 1px solid {t('border')};
        }}
        QComboBox::drop-down:disabled {{
            background-color: {t('bg_mid')};
            border-left: 1px solid {t('border_dark')};
        }}
        QComboBox::down-arrow {{ image: none; width: 0px; }}
        QComboBox QAbstractItemView {{
            background-color: {t('bg_mid')};
            color: {t('text_primary')};
            selection-background-color: {t('selection_bg')};
            border: 1px solid {t('border')};
        }}
        """

    @classmethod
    def get_TAB_WIDGET(cls) -> str:
        return f"""
        QTabWidget::pane {{
            border: 1px solid {t('border')};
            background-color: {t('bg_dark')};
        }}
        QTabBar::tab {{
            background-color: {t('bg_dark')};
            color: {t('text_primary')};
            padding: 8px 20px;
            border: 1px solid {t('border')};
            border-bottom: none; margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            background-color: {t('bg_pressed')};
            color: {t('text_primary')};
            border-bottom: 1px solid {t('bg_dark')};
        }}
        QTabBar::tab:hover {{
            background-color: {t('bg_hover')};
            color: {t('text_primary')};
        }}
        """

    @classmethod
    def get_GROUP_BOX(cls) -> str:
        return f"""
        QGroupBox {{
            color: {t('text_primary')};
            font-size: 12px; font-weight: bold;
            border: 1px solid {t('border')};
            border-radius: 4px;
            margin-top: 10px; margin-bottom: 15px; padding-top: 15px;
            background-color: transparent;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px; padding: 0 5px;
        }}
        """

    @classmethod
    def get_SCROLL_AREA(cls) -> str:
        return f"""
        QScrollArea {{
            background-color: {t('bg_dark')};
            border: none;
        }}
        QScrollBar:vertical {{
            background-color: {t('bg_dark')};
            width: 12px; margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {t('border')};
            min-height: 20px; border-radius: 6px;
        }}
        QScrollBar::handle:vertical:hover {{ background-color: {t('border_hover')}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        """

    @classmethod
    def get_ACTION_BUTTON(cls) -> str:
        return f"""
        QPushButton {{
            background-color: {t('bg_light')};
            color: {t('text_primary')};
            border: 1px solid {t('border')};
            border-radius: 3px; padding: 6px 16px;
        }}
        QPushButton:hover {{
            background-color: {t('bg_hover')};
            border: 1px solid {t('border_hover')};
        }}
        QPushButton:pressed {{ background-color: {t('bg_mid')}; }}
        QPushButton:disabled {{
            background-color: {t('bg_dark')};
            color: {t('text_disabled')};
            border: 1px solid {t('border_dark')};
        }}
        """

    @classmethod
    def get_QUERY_FRAME(cls) -> str:
        return f"""
        QFrame {{
            border: 1px solid {t('border')};
            background-color: transparent;
        }}
        """

    @classmethod
    def get_READONLY_INPUT(cls) -> str:
        return f"""
        QLineEdit {{
            background-color: {t('bg_dark')};
            color: {t('text_hint')};
            border: 1px solid {t('border')};
            border-radius: 3px; padding: 4px;
        }}
        """

    @classmethod
    def get_PROGRESS_BAR(cls) -> str:
        return f"""
        QProgressBar {{
            border: 1px solid {t('border')};
            border-radius: 3px;
            background-color: {t('bg_mid')};
            text-align: center;
            color: {t('text_primary')};
            height: 20px;
        }}
        QProgressBar::chunk {{ background-color: {t('status_info')}; }}
        """

    @classmethod
    def get_CONTEXT_MENU(cls) -> str:
        return f"""
        QMenu {{
            min-width: 120px;
            background-color: {t('bg_mid')};
            color: {t('text_primary')};
            border: 1px solid {t('border')};
            padding: 2px;
        }}
        QMenu::item {{
            padding: 6px 30px 6px 6px;
            margin: 1px 2px;
            border-radius: 2px;
        }}
        QMenu::item:selected {{
            background-color: {t('selection_bg')};
            color: {t('text_primary')};
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {t('border')};
            margin: 3px 5px;
        }}
        """

    @classmethod
    def get_COMBO_LINE_EDIT_ACTIVE(cls) -> str:
        return f"""
        QLineEdit {{
            background-color: {t('bg_light')};
            color: {t('text_primary')};
            border: none; padding: 4px;
            selection-background-color: {t('selection_bg')};
        }}
        """

    @classmethod
    def get_COMBO_LINE_EDIT_INACTIVE(cls) -> str:
        return f"""
        QLineEdit {{
            background-color: transparent;
            color: {t('text_disabled')};
            border: none; padding: 4px;
        }}
        """

    # ── 向后兼容：保留旧的 build_xxx 方法名（代理到 get_XXX）────

    @classmethod
    def build_combo_line_edit_active(cls) -> str:
        return cls.get_COMBO_LINE_EDIT_ACTIVE()

    @classmethod
    def build_combo_line_edit_inactive(cls) -> str:
        return cls.get_COMBO_LINE_EDIT_INACTIVE()

    @classmethod
    def build_tab_widget(cls) -> str:
        return cls.get_TAB_WIDGET()

    @classmethod
    def build_group_box(cls) -> str:
        return cls.get_GROUP_BOX()

    @classmethod
    def build_scroll_area(cls) -> str:
        return cls.get_SCROLL_AREA()
