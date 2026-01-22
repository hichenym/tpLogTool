"""
页面模块
所有页面的基类和注册机制
"""
from .base_page import BasePage
from .page_registry import PageRegistry, register_page

# 导入所有页面（会自动注册）
from .device_status_page import DeviceStatusPage
from .phone_query_page import PhoneQueryPage
from .gitlab_log_page import GitLabLogPage

__all__ = [
    'BasePage',
    'PageRegistry',
    'register_page',
    'DeviceStatusPage',
    'PhoneQueryPage',
    'GitLabLogPage',
]
