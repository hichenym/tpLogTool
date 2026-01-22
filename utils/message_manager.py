"""
消息管理器
统一管理状态栏消息的显示
"""
from enum import Enum


class MessageType(Enum):
    """消息类型"""
    INFO = "info"       # 普通信息
    SUCCESS = "success" # 成功
    WARNING = "warning" # 警告
    ERROR = "error"     # 错误
    PROGRESS = "progress" # 进度


class MessageManager:
    """消息管理器"""
    
    # 消息图标映射
    ICONS = {
        MessageType.INFO: "ℹ",
        MessageType.SUCCESS: "✓",
        MessageType.WARNING: "⚠",
        MessageType.ERROR: "✗",
        MessageType.PROGRESS: "⏳"
    }
    
    # 消息颜色映射
    COLORS = {
        MessageType.INFO: "#2196F3",      # 蓝色
        MessageType.SUCCESS: "#4CAF50",   # 绿色
        MessageType.WARNING: "#FF9800",   # 橙色
        MessageType.ERROR: "#F44336",     # 红色
        MessageType.PROGRESS: "#00BCD4"   # 青色
    }
    
    # 默认显示时长（毫秒）
    DURATIONS = {
        MessageType.INFO: 2000,
        MessageType.SUCCESS: 3000,
        MessageType.WARNING: 3000,
        MessageType.ERROR: 5000,
        MessageType.PROGRESS: 0  # 进度消息不自动消失
    }
    
    def __init__(self, status_label):
        """
        初始化消息管理器
        
        Args:
            status_label: QLabel 实例（用于显示状态消息）
        """
        self.status_label = status_label
        self.timer = None
    
    def show(self, message, msg_type=MessageType.INFO, duration=None):
        """
        显示消息
        
        Args:
            message: 消息内容
            msg_type: 消息类型
            duration: 显示时长（毫秒），None 则使用默认值
        """
        icon = self.ICONS.get(msg_type, "")
        color = self.COLORS.get(msg_type, "#e0e0e0")
        
        # 使用HTML格式化消息，添加图标和颜色
        formatted_msg = f'<span style="color: {color}; font-weight: bold;">{icon}</span> <span style="color: {color};">{message}</span>'
        
        self.status_label.setText(formatted_msg)
        
        if duration is None:
            duration = self.DURATIONS.get(msg_type, 2000)
        
        # 如果有定时器在运行，先停止
        if self.timer:
            self.timer.stop()
        
        # 如果duration > 0，设置定时器自动清空
        if duration > 0:
            from PyQt5.QtCore import QTimer
            self.timer = QTimer()
            self.timer.setSingleShot(True)
            self.timer.timeout.connect(self.clear)
            self.timer.start(duration)
    
    def info(self, message, duration=None):
        """显示普通信息"""
        self.show(message, MessageType.INFO, duration)
    
    def success(self, message, duration=None):
        """显示成功消息"""
        self.show(message, MessageType.SUCCESS, duration)
    
    def warning(self, message, duration=None):
        """显示警告消息"""
        self.show(message, MessageType.WARNING, duration)
    
    def error(self, message, duration=None):
        """显示错误消息"""
        self.show(message, MessageType.ERROR, duration)
    
    def progress(self, message):
        """显示进度消息（不自动消失）"""
        self.show(message, MessageType.PROGRESS)
    
    def clear(self):
        """清空消息"""
        self.status_label.setText("")
        if self.timer:
            self.timer.stop()
            self.timer = None
