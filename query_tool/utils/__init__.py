"""
工具模块
提供配置管理、设备查询、线程管理等工具。

为避免导入 query_tool.utils 时立即拉起所有可选依赖，这里改为按属性懒加载。
"""
from importlib import import_module


_EXPORTS = {
    "config_manager": (".config", "config_manager"),
    "get_account_config": (".config", "get_account_config"),
    "save_account_config": (".config", "save_account_config"),
    "get_seetong_account_config": (".config", "get_seetong_account_config"),
    "save_seetong_account_config": (".config", "save_seetong_account_config"),
    "REGISTRY_PATH": (".config", "REGISTRY_PATH"),
    "DeviceQuery": (".device_query", "DeviceQuery"),
    "wake_device": (".device_query", "wake_device"),
    "check_device_online": (".device_query", "check_device_online"),
    "wake_device_smart": (".device_query", "wake_device_smart"),
    "ensure_device_online_for_upgrade": (".device_query", "ensure_device_online_for_upgrade"),
    "ButtonManager": (".button_manager", "ButtonManager"),
    "ButtonGroup": (".button_manager", "ButtonGroup"),
    "MessageManager": (".message_manager", "MessageManager"),
    "MessageType": (".message_manager", "MessageType"),
    "StyleManager": (".style_manager", "StyleManager"),
    "theme_manager": (".theme_manager", "theme_manager"),
    "TableHelper": (".table_helper", "TableHelper"),
    "ThreadManager": (".thread_manager", "ThreadManager"),
    "GitLabAPI": (".gitlab_api", "GitLabAPI"),
    "create_gitlab_xlsx": (".excel_helper", "create_gitlab_xlsx"),
    "logger": (".logger", "logger"),
    "Logger": (".logger", "Logger"),
    "session_manager": (".session_manager", "session_manager"),
    "SessionManager": (".session_manager", "SessionManager"),
    "firmware_login": (".firmware_api", "login"),
    "fetch_firmware_data": (".firmware_api", "fetch_firmware_data"),
    "delete_firmware": (".firmware_api", "delete_firmware"),
    "get_firmware_detail": (".firmware_api", "get_firmware_detail"),
    "update_firmware": (".firmware_api", "update_firmware"),
    "test_firmware_login": (".firmware_api", "test_firmware_login"),
    "clear_firmware_cache": (".firmware_api", "clear_session_cache"),
}


def __getattr__(name):
    export = _EXPORTS.get(name)
    if export is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = export
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


__all__ = list(_EXPORTS.keys())
