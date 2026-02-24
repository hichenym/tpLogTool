"""
日志系统
提供统一的日志记录功能（支持控制台和可选的文件输出）
"""
import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime


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
        
        # 清除已有的处理器
        self.logger.handlers.clear()
        
        # 添加控制台处理器（只显示WARNING及以上）
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)
        console_formatter = logging.Formatter('%(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # 从配置加载文件日志设置
        self._load_file_log_config()
    
    def _load_file_log_config(self):
        """从配置加载文件日志设置"""
        try:
            from query_tool.utils.config import get_log_config
            enable_file_log = get_log_config()
            if enable_file_log:
                self.enable_file_log()
        except Exception as e:
            # 配置加载失败，忽略
            pass
    
    def enable_file_log(self):
        """启用文件日志"""
        if self._file_handler:
            # 已经启用，不重复添加
            return
        
        try:
            # 创建用户目录下的logs目录
            import os
            from pathlib import Path
            
            # 获取用户主目录
            user_home = Path.home()
            log_dir = user_home / '.TPQueryTool' / 'logs'
            
            # 创建目录（如果不存在）
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成日志文件名（按日期）
            log_file = log_dir / f'app_{datetime.now().strftime("%Y%m%d")}.log'
            
            # 创建文件处理器（滚动日志，最大10MB，保留3个备份）
            self._file_handler = RotatingFileHandler(
                str(log_file),
                maxBytes=10*1024*1024,  # 10MB
                backupCount=3,
                encoding='utf-8'
            )
            self._file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别
            
            # 文件日志格式更详细
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            self._file_handler.setFormatter(file_formatter)
            
            self.logger.addHandler(self._file_handler)
            self.info(f"文件日志已启用: {log_file}")
            
        except Exception as e:
            print(f"启用文件日志失败: {e}")
    
    def disable_file_log(self):
        """禁用文件日志"""
        if self._file_handler:
            try:
                self.info("文件日志已禁用")
                self.logger.removeHandler(self._file_handler)
                self._file_handler.close()
                self._file_handler = None
            except Exception as e:
                print(f"禁用文件日志失败: {e}")
    
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
