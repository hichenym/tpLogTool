"""
页面模块
提供页面基类、注册表和按需页面加载。
"""
from importlib import import_module

from .base_page import BasePage
from .page_registry import PageRegistry, register_page


_PAGE_MODULES = {
    "DeviceStatusPage": ".device_status_page",
    "DebugPage": ".debug_page",
    "LogPage": ".log_page",
    "FirmwarePage": ".firmware_page",
    "GitLabLogPage": ".gitlab_log_page",
    "ErrorRecordPage": ".error_record_page",
}

_REGISTERED = False


def register_builtin_pages(force: bool = False):
    """导入内置页面模块并触发注册。"""
    global _REGISTERED
    if _REGISTERED and not force:
        return

    if force:
        PageRegistry.clear()

    for module_name in _PAGE_MODULES.values():
        import_module(module_name, __name__)

    _REGISTERED = True


def __getattr__(name):
    module_name = _PAGE_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_name, __name__)
    return getattr(module, name)


__all__ = [
    "BasePage",
    "PageRegistry",
    "register_page",
    "register_builtin_pages",
    *list(_PAGE_MODULES.keys()),
]
