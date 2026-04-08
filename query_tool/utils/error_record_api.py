"""
错误码记录查询 API
提供设备型号列表、模块列表、错误记录查询功能
"""
from PyQt5.QtCore import QThread, pyqtSignal
from query_tool.utils.logger import logger

BASE_URL = "https://console.seetong.com"
_BASIC_AUTH = "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA=="


def _make_device_query():
    """
    创建 DeviceQuery 实例（use_cache=True，缓存命中直接用；
    若缓存 token 已失效，DeviceQuery._request 内部会自动 401 刷新）
    """
    from query_tool.utils.config import get_account_config
    from query_tool.utils.device_query import DeviceQuery
    env, username, password = get_account_config()
    if not username or not password:
        raise RuntimeError("账号未配置，请先在设置中配置账号")
    dq = DeviceQuery(env, username, password, use_cache=True)
    if dq.init_error:
        raise RuntimeError(dq.init_error)
    return dq


def fetch_model_list(dq):
    """
    获取所有设备型号及对应版本列表，复用 DeviceQuery._request（含 401 自动刷新）
    Returns:
        {"TD53E30": ["TD53E30-3.0.x...", ...], ...}
    """
    result = dq._request(
        "/api/seetong-siot-device/console/moc/common/model/all", {}
    )
    if not result.get("success"):
        raise RuntimeError(result.get("msg", "获取型号列表失败"))
    model_map = {}
    for item in result.get("data", []):
        model = item.get("name", "")
        if not model:
            continue
        versions = [c["name"] for c in item.get("children", []) if c.get("name")]
        model_map[model] = versions
    return model_map


def fetch_module_list(dq):
    """
    获取所有错误模块，复用 DeviceQuery._request（含 401 自动刷新）
    Returns:
        [{"key": "4G", "label": "4G模块"}, ...]
    """
    result = dq._request(
        "/api/seetong-system/dict/dictionary",
        {"code": "device_errror_code_module"}
    )
    if not result.get("success"):
        raise RuntimeError(result.get("msg", "获取模块列表失败"))
    return [
        {"key": item["dictKey"], "label": item["dictValue"]}
        for item in result.get("data", [])
        if item.get("dictKey") and item.get("dictValue")
    ]


def fetch_error_records(dq, page=1, size=100, device_sn="", device_model="",
                        device_identify="", module="", error_code="",
                        start_time="", end_time=""):
    """
    查询错误码记录，复用 DeviceQuery._request（含 401 自动刷新）
    时间参数需要空格替换为 +，直接拼到 path 避免 requests 将 + 编码为 %2B
    Returns:
        (records: list, current: int, pages: int, total: int)
    """
    # 普通参数走 _request 的 params（会被 urlencode）
    params = {
        "current": page,
        "size": size,
        "deviceSn": device_sn,
        "deviceModel": device_model,
        "deviceIdentify": device_identify,
        "module": module,
        "errorCode": error_code,
    }

    # 时间参数空格→+，直接拼到 path query string，避免 requests 二次编码
    time_qs = ""
    if start_time:
        time_qs += f"&errorStartTime={start_time.replace(' ', '+')}"
    if end_time:
        time_qs += f"&errorEndTime={end_time.replace(' ', '+')}"

    api_path = f"/api/seetong-siot-device/console/moc/error/record/list?placeholder=1{time_qs}"

    result = dq._request(api_path, params)
    if not result.get("success"):
        raise RuntimeError(result.get("msg", "查询失败"))
    page_data = result.get("data", {})
    records = page_data.get("records", [])
    return (
        records,
        page_data.get("current", 1),
        page_data.get("pages", 1),
        page_data.get("total", 0),
    )


class MetaLoadThread(QThread):
    """首次进入页面时加载型号和模块元数据"""
    finished = pyqtSignal(dict, list)   # model_map, module_list
    error = pyqtSignal(str)

    def run(self):
        try:
            dq = _make_device_query()
            model_map = fetch_model_list(dq)
            module_list = fetch_module_list(dq)
            self.finished.emit(model_map, module_list)
        except Exception as e:
            logger.error(f"MetaLoadThread 异常: {e}")
            self.error.emit(str(e))


class ErrorRecordQueryThread(QThread):
    """错误记录分页查询线程"""
    finished = pyqtSignal(list, int, int, int)  # records, current, pages, total
    error = pyqtSignal(str)

    def __init__(self, page=1, size=100, device_sn="", device_model="",
                 device_identify="", module="", error_code="",
                 start_time="", end_time=""):
        super().__init__()
        self.page = page
        self.size = size
        self.device_sn = device_sn
        self.device_model = device_model
        self.device_identify = device_identify
        self.module = module
        self.error_code = error_code
        self.start_time = start_time
        self.end_time = end_time

    def run(self):
        try:
            dq = _make_device_query()
            records, current, pages, total = fetch_error_records(
                dq, self.page, self.size,
                self.device_sn, self.device_model, self.device_identify,
                self.module, self.error_code, self.start_time, self.end_time
            )
            self.finished.emit(records, current, pages, total)
        except Exception as e:
            logger.error(f"ErrorRecordQueryThread 异常: {e}")
            self.error.emit(str(e))
