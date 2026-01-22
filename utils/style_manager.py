"""
样式管理器
统一管理应用程序的样式 - 深色主题
"""


class StyleManager:
    """样式管理器 - 深色主题"""
    
    # 颜色定义
    COLOR_BG_DARK = "#2b2b2b"      # 深灰背景
    COLOR_BG_MID = "#3c3c3c"       # 中灰背景
    COLOR_BG_LIGHT = "#404040"     # 浅灰背景
    COLOR_TEXT_PRIMARY = "#e0e0e0" # 主文字色
    COLOR_TEXT_SECONDARY = "#b0b0b0" # 次文字色
    COLOR_ACCENT = "#0d7377"       # 强调色（青绿）
    COLOR_HOVER = "#4a4a4a"        # 悬停色
    COLOR_BORDER = "#555555"       # 边框色
    
    # 菜单按钮样式
    MENU_BUTTON = """
        QPushButton {
            border: none;
            padding: 4px 16px;
            background-color: transparent;
            color: #e0e0e0;
            font-size: 13px;
        }
        QPushButton:hover {
            background-color: #4a4a4a;
        }
        QPushButton:checked {
            background-color: #0d7377;
            color: #ffffff;
            font-weight: bold;
        }
    """
    
    # 设置按钮样式
    SETTINGS_BUTTON = """
        QPushButton {
            background-color: #3c3c3c;
            color: #e0e0e0;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 4px;
        }
        QPushButton:hover {
            background-color: #4a4a4a;
            border: 1px solid #0d7377;
        }
        QPushButton:pressed {
            background-color: #0d7377;
        }
    """
    
    # 菜单栏样式
    MENU_BAR = """
        QWidget {
            background-color: #2b2b2b !important;
            border-bottom: 1px solid #3c3c3c;
        }
    """
    
    # 表格样式
    TABLE = """
        QTableWidget {
            background-color: #3c3c3c;
            color: #e0e0e0;
            gridline-color: #555555;
            border: 1px solid #555555;
        }
        QTableWidget::item {
            padding-right: 10px;
        }
        QTableWidget::item:selected {
            background-color: transparent;
            border: 2px solid #0d7377;
        }
        QHeaderView::section {
            background-color: #2b2b2b;
            color: #e0e0e0;
            border: 1px solid #555555;
            padding: 4px;
        }
        QTableCornerButton::section {
            background-color: #2b2b2b;
            border: 1px solid #555555;
        }
        QScrollBar:vertical {
            background-color: #2b2b2b;
            width: 12px;
            border: none;
            margin: 0px;
        }
        QScrollBar::handle:vertical {
            background-color: #555555;
            border-radius: 6px;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #0d7377;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
    """
    
    # 分隔器样式
    SPLITTER = """
        QSplitter::handle {
            background-color: #555555;
            margin: 5px 0px 5px 0px;
        }
        QSplitter::handle:hover {
            background-color: #0d7377;
        }
    """
    
    # 版本标签样式
    VERSION_LABEL = "color: #b0b0b0; padding-right: 10px; border: none; background-color: transparent;"
    
    @classmethod
    def apply_to_widget(cls, widget, style_name):
        """
        应用样式到控件
        
        Args:
            widget: Qt 控件
            style_name: 样式名称（如 "MENU_BUTTON"）
        """
        style = getattr(cls, style_name, None)
        if style:
            widget.setStyleSheet(style)
    
    @classmethod
    def get_style(cls, style_name):
        """获取样式字符串"""
        return getattr(cls, style_name, "")
