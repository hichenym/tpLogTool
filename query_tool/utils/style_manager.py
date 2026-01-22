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
            padding: 4px 8px;
            background-color: transparent;
            color: #e0e0e0;
            font-size: 13px;
        }
        QPushButton:hover {
            background-color: #4a4a4a;
        }
        QPushButton:checked {
            background-color: #505050;
            color: #ffffff;
            font-weight: bold;
        }
    """
    
    # 设置按钮样式（低调不明显）
    SETTINGS_BUTTON = """
        QPushButton {
            background-color: transparent;
            color: #909090;
            border: none;
            border-radius: 3px;
            padding: 4px;
        }
        QPushButton:hover {
            background-color: #4a4a4a;
            color: #e0e0e0;
        }
        QPushButton:pressed {
            background-color: #3c3c3c;
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
            show-decoration-selected: 0;
        }
        QTableWidget::item {
            padding-right: 10px;
            border: none;
            outline: none;
        }
        QTableWidget::item:selected {
            background-color: rgba(13, 115, 119, 0.3);
            border: none;
            outline: none;
        }
        QTableWidget::item:focus {
            background-color: rgba(13, 115, 119, 0.3);
            border: none;
            outline: none;
        }
        QTableWidget:focus {
            outline: none;
            border: 1px solid #555555;
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
            background-color: #6a6a6a;
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
            background-color: #6a6a6a;
        }
    """
    
    # 版本标签样式
    VERSION_LABEL = "color: #b0b0b0; padding-right: 10px; border: none; background-color: transparent;"
    
    # 下拉框样式
    COMBOBOX = """
        QComboBox {
            background-color: #404040;
            color: #e0e0e0;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 4px;
            padding-right: 0px;
        }
        QComboBox:hover {
            border: 1px solid #555555;
        }
        QComboBox:disabled {
            background-color: #2b2b2b;
            color: #606060;
            border: 1px solid #3c3c3c;
        }
        QComboBox::drop-down {
            border: none;
            background-color: #505050;
            width: 24px;
            margin: 0px;
            padding: 0px;
            border-left: 1px solid #555555;
        }
        QComboBox::drop-down:disabled {
            background-color: #3c3c3c;
            border-left: 1px solid #3c3c3c;
        }
        QComboBox::down-arrow {
            image: none;
            width: 0px;
        }
        QComboBox QAbstractItemView {
            background-color: #3c3c3c;
            color: #e0e0e0;
            selection-background-color: #505050;
            border: 1px solid #555555;
        }
    """
    
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
