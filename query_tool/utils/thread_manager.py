"""
线程管理器
统一管理后台线程
"""
from PyQt5.QtCore import QThread


class ThreadManager:
    """线程管理器"""
    
    def __init__(self):
        self.threads = {}  # {name: thread}
    
    def add(self, name, thread):
        """
        添加线程
        
        Args:
            name: 线程名称
            thread: QThread 实例
        """
        # 如果已存在同名线程，先停止
        if name in self.threads:
            self.stop(name)
        
        self.threads[name] = thread
        return thread
    
    def get(self, name):
        """获取线程"""
        return self.threads.get(name)
    
    def stop(self, name, wait_ms=1000):
        """
        停止线程
        
        Args:
            name: 线程名称
            wait_ms: 等待时间（毫秒）
        """
        thread = self.threads.get(name)
        if thread and thread.isRunning():
            if hasattr(thread, 'stop'):
                thread.stop()
            thread.wait(wait_ms)
    
    def stop_all(self, wait_ms=1000):
        """停止所有线程"""
        for name in list(self.threads.keys()):
            self.stop(name, wait_ms)
    
    def cleanup(self, name):
        """清理已完成的线程"""
        thread = self.threads.get(name)
        if thread and not thread.isRunning():
            del self.threads[name]
    
    def cleanup_all(self):
        """清理所有已完成的线程"""
        for name in list(self.threads.keys()):
            self.cleanup(name)
