"""
日志系统
提供统一的日志记录功能（支持控制台和可选的文件输出）
"""
import logging
import sys
import shutil
from pathlib import Path


class Logger:
    """日志管理器"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._file_handler = None
        
        # 配置根日志记录器
        self.logger = logging.getLogger('QueryTool')
        self.logger.setLevel(logging.DEBUG)  # 设置为DEBUG以支持所有级别
        self.logger.propagate = False
        
        # 清除已有的处理器
        self.logger.handlers.clear()
        
        # 添加控制台处理器（只显示WARNING及以上）
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)
        console_formatter = logging.Formatter('%(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # 文件日志已永久关闭，同时清理旧版本遗留的操作日志。
        self._clear_log_directory()

    @staticmethod
    def _clear_log_directory():
        """删除用户目录中由应用生成的历史日志。"""
        try:
            shutil.rmtree(Path.home() / '.TPQueryTool' / 'logs', ignore_errors=True)
        except Exception:
            pass
    
    def enable_file_log(self):
        """兼容旧调用：文件日志已永久关闭。"""
        self.disable_file_log()
    
    def disable_file_log(self):
        """禁用文件日志并清理已有日志。"""
        if self._file_handler:
            try:
                self.logger.removeHandler(self._file_handler)
                self._file_handler.close()
                self._file_handler = None
            except Exception:
                pass
        self._clear_log_directory()
    
    def is_file_log_enabled(self):
        """检查文件日志是否启用"""
        return self._file_handler is not None
    
    def get_logger(self, name=None):
        """获取日志记录器"""
        if name:
            return logging.getLogger(f'QueryTool.{name}')
        return self.logger
    
    def debug(self, msg, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)
    
    def info(self, msg, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)
    
    def warning(self, msg, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)
    
    def error(self, msg, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)
    
    def critical(self, msg, *args, **kwargs):
        self.logger.critical(msg, *args, **kwargs)
    
    def exception(self, msg, *args, **kwargs):
        """记录异常信息（包含堆栈）"""
        self.logger.exception(msg, *args, **kwargs)


# 全局日志实例
logger = Logger()


def setup_exception_handler():
    """设置全局异常处理器"""
    def exception_hook(exc_type, exc_value, exc_traceback):
        """全局异常钩子"""
        if issubclass(exc_type, KeyboardInterrupt):
            # 允许 Ctrl+C 正常退出，不打印任何信息
            return
        
        logger.critical(
            "未捕获的异常",
            exc_info=(exc_type, exc_value, exc_traceback)
        )
    
    sys.excepthook = exception_hook
