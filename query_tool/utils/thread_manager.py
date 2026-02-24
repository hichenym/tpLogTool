"""
线程管理器
统一管理后台线程，确保正确清理
"""
from PyQt5.QtCore import QThread, QTimer
from .logger import logger


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
        
        # 线程完成后自动清理
        thread.finished.connect(lambda: self._on_thread_finished(name))
        
        logger.debug(f"添加线程: {name}")
        return thread
    
    def _on_thread_finished(self, name):
        """线程完成回调"""
        thread = self.threads.get(name)
        if thread:
            # 延迟删除，确保所有信号处理完成
            QTimer.singleShot(100, lambda: self._cleanup_thread(name))
    
    def _cleanup_thread(self, name):
        """清理线程"""
        thread = self.threads.get(name)
        if thread:
            try:
                # 不再调用deleteLater，因为线程已经在外部调用了
                # thread.deleteLater()
                del self.threads[name]
                logger.debug(f"清理线程: {name}")
            except RuntimeError as e:
                # 线程对象已被删除
                logger.debug(f"线程 {name} 已被删除: {e}")
                if name in self.threads:
                    del self.threads[name]
            except Exception as e:
                logger.error(f"清理线程失败 {name}: {e}")
    
    def get(self, name):
        """获取线程"""
        return self.threads.get(name)
    
    def stop(self, name, wait_ms=2000, force=True):
        """
        停止线程
        
        Args:
            name: 线程名称
            wait_ms: 等待时间（毫秒）
            force: 超时后是否强制终止
        """
        thread = self.threads.get(name)
        if not thread:
            return
        
        try:
            # 检查线程是否还在运行（可能已被deleteLater删除）
            if not thread.isRunning():
                # 线程已停止，直接清理
                if name in self.threads:
                    del self.threads[name]
                return
            
            # 调用线程的stop方法（如果有）
            if hasattr(thread, 'stop'):
                thread.stop()
            
            # 请求线程退出
            thread.quit()
            
            # 等待线程结束
            if not thread.wait(wait_ms):
                logger.warning(f"线程 {name} 在 {wait_ms}ms 内未结束")
                if force:
                    # 强制终止（不推荐，但作为最后手段）
                    thread.terminate()
                    thread.wait(1000)
                    logger.warning(f"强制终止线程: {name}")
            else:
                logger.debug(f"停止线程: {name}")
        except RuntimeError as e:
            # 线程对象已被删除
            logger.debug(f"线程 {name} 已被删除: {e}")
            if name in self.threads:
                del self.threads[name]
        except Exception as e:
            logger.error(f"停止线程失败 {name}: {e}")
    
    def stop_all(self, wait_ms=2000, force=True):
        """停止所有线程"""
        logger.info(f"停止所有线程，共 {len(self.threads)} 个")
        for name in list(self.threads.keys()):
            self.stop(name, wait_ms, force)
    
    def cleanup(self, name):
        """清理已完成的线程"""
        thread = self.threads.get(name)
        if not thread:
            return
        
        try:
            if not thread.isRunning():
                self._cleanup_thread(name)
        except RuntimeError as e:
            # 线程对象已被删除
            logger.debug(f"线程 {name} 已被删除: {e}")
            if name in self.threads:
                del self.threads[name]
        except Exception as e:
            logger.error(f"清理线程失败 {name}: {e}")
    
    def cleanup_all(self):
        """清理所有已完成的线程"""
        for name in list(self.threads.keys()):
            self.cleanup(name)
    
    def is_running(self, name):
        """检查线程是否在运行"""
        thread = self.threads.get(name)
        if not thread:
            return False
        
        try:
            return thread.isRunning()
        except RuntimeError:
            # 线程对象已被删除
            if name in self.threads:
                del self.threads[name]
            return False
    
    def count(self):
        """获取线程数量"""
        return len(self.threads)

