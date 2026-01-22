"""
按钮状态管理器
统一管理按钮的启用/禁用状态
"""
from PyQt5.QtWidgets import QPushButton, QCheckBox


class ButtonGroup:
    """按钮组"""
    def __init__(self, name="default"):
        self.name = name
        self.buttons = []
        self.original_texts = {}  # 保存原始文本
    
    def add(self, *buttons):
        """添加按钮到组"""
        for btn in buttons:
            if btn not in self.buttons:
                self.buttons.append(btn)
                if isinstance(btn, QPushButton):
                    self.original_texts[btn] = btn.text()
        return self
    
    def enable(self):
        """启用所有按钮"""
        for btn in self.buttons:
            btn.setEnabled(True)
            # 恢复原始文本
            if isinstance(btn, QPushButton) and btn in self.original_texts:
                btn.setText(self.original_texts[btn])
    
    def disable(self, loading_text=None):
        """
        禁用所有按钮
        
        Args:
            loading_text: 加载中的文本（可选，如 "查询中..."）
        """
        for btn in self.buttons:
            btn.setEnabled(False)
            if loading_text and isinstance(btn, QPushButton):
                btn.setText(loading_text)
    
    def set_text(self, button, text):
        """设置按钮文本并更新原始文本"""
        if isinstance(button, QPushButton):
            button.setText(text)
            self.original_texts[button] = text


class ButtonManager:
    """按钮管理器"""
    def __init__(self):
        self.groups = {}
    
    def create_group(self, name):
        """创建按钮组"""
        group = ButtonGroup(name)
        self.groups[name] = group
        return group
    
    def get_group(self, name):
        """获取按钮组"""
        return self.groups.get(name)
    
    def enable_all(self):
        """启用所有按钮组"""
        for group in self.groups.values():
            group.enable()
    
    def disable_all(self):
        """禁用所有按钮组"""
        for group in self.groups.values():
            group.disable()
