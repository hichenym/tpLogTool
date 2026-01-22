"""
页面基类
所有页面都继承此类，提供统一的接口
"""
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import pyqtSignal


class BasePage(QWidget):
    """页面基类"""
    # 统一的信号定义
    status_message = pyqtSignal(str, str, int)  # (消息, 类型, 显示时长ms)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.page_name = "未命名页面"
    
    def get_page_name(self):
        """获取页面名称（显示在菜单按钮上）"""
        return self.page_name
    
    def on_page_show(self):
        """页面显示时调用（可选重写）"""
        pass
    
    def on_page_hide(self):
        """页面隐藏时调用（可选重写）"""
        pass
    
    def load_config(self):
        """加载配置（子类可选实现）"""
        pass
    
    def save_config(self):
        """保存配置（子类可选实现）"""
        pass
    
    def cleanup(self):
        """清理资源（页面关闭时调用，可选重写）"""
        pass
    
    # 便捷的消息显示方法
    def show_info(self, message, duration=None):
        """显示信息消息"""
        self.status_message.emit(message, "info", duration or 2000)
    
    def show_success(self, message, duration=None):
        """显示成功消息"""
        self.status_message.emit(message, "success", duration or 3000)
    
    def show_warning(self, message, duration=None):
        """显示警告消息"""
        self.status_message.emit(message, "warning", duration or 3000)
    
    def show_error(self, message, duration=None):
        """显示错误消息"""
        self.status_message.emit(message, "error", duration or 5000)
    
    def show_progress(self, message):
        """显示进度消息（不自动消失）"""
        self.status_message.emit(message, "progress", 0)
