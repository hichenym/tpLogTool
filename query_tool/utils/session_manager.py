"""
Session管理器
统一管理HTTP会话，复用连接，提高性能
"""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from threading import Lock
from .logger import logger


class SessionManager:
    """Session管理器（单例）"""
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self._sessions = {}
        self._sessions_lock = Lock()
        
        # 禁用SSL警告
        requests.packages.urllib3.disable_warnings()
    
    def get_session(self, key='default', max_retries=3, pool_connections=10, pool_maxsize=20):
        """
        获取或创建Session
        
        Args:
            key: Session标识
            max_retries: 最大重试次数
            pool_connections: 连接池大小
            pool_maxsize: 连接池最大连接数
        """
        with self._sessions_lock:
            if key not in self._sessions:
                session = requests.Session()
                
                # 配置重试策略
                retry_strategy = Retry(
                    total=max_retries,
                    backoff_factor=1,  # 指数退避因子
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
                )
                
                # 配置适配器 - 增加连接池大小以避免连接耗尽
                adapter = HTTPAdapter(
                    max_retries=retry_strategy,
                    pool_connections=pool_connections,
                    pool_maxsize=pool_maxsize,
                    pool_block=False  # 不阻塞，避免连接池满时的死锁
                )
                
                session.mount("http://", adapter)
                session.mount("https://", adapter)
                
                # 设置默认超时
                session.request = self._add_timeout(session.request)
                
                self._sessions[key] = session
                logger.debug(f"创建新Session: {key}")
            
            return self._sessions[key]
    
    def _add_timeout(self, request_func, default_timeout=10):
        """为请求添加默认超时"""
        def wrapper(*args, **kwargs):
            if 'timeout' not in kwargs:
                kwargs['timeout'] = default_timeout
            return request_func(*args, **kwargs)
        return wrapper
    
    def close_session(self, key='default'):
        """关闭指定Session"""
        with self._sessions_lock:
            if key in self._sessions:
                try:
                    self._sessions[key].close()
                except Exception as e:
                    logger.debug(f"关闭Session异常 {key}: {e}")
                finally:
                    del self._sessions[key]
                    logger.debug(f"关闭Session: {key}")
    
    def close_all(self):
        """关闭所有Session"""
        with self._sessions_lock:
            for key in list(self._sessions.keys()):
                try:
                    self._sessions[key].close()
                    logger.debug(f"关闭Session: {key}")
                except Exception as e:
                    logger.error(f"关闭Session失败 {key}: {e}")
                finally:
                    del self._sessions[key]
    
    def reset_session(self, key='default'):
        """重置指定Session（关闭并重新创建）"""
        self.close_session(key)
        # 下次调用 get_session 时会创建新的
        logger.debug(f"已重置Session: {key}")


# 全局Session管理器实例
session_manager = SessionManager()
