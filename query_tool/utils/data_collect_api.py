"""
数据采集API封装模块
提供设备历史数据查询功能
"""

from PyQt5.QtCore import QThread, pyqtSignal
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from datetime import datetime, timezone
from query_tool.utils.logger import logger


# 数据采集类型配置（便于扩展）
COLLECT_TYPES = {
    'battery': {
        'id': 'battery',
        'name': '电池电量',
        'icon': ':/icons/device/battery.png',
        'description': '查询设备电池电量历史数据',
        'enabled': True,
        'single_dialog': 'BatteryCollectDialog',
        'batch_dialog': 'BatchBatteryCollectDialog',
    },
}


def get_enabled_collect_types():
    """获取已启用的采集类型列表"""
    return {k: v for k, v in COLLECT_TYPES.items() if v['enabled']}


def _to_utc_timestamp(time_str):
    """
    将本地时间字符串（yyyy-MM-dd HH:mm:ss，东八区）转换为UTC时间戳（秒）
    
    Args:
        time_str: 时间字符串，格式 "yyyy-MM-dd HH:mm:ss"
    Returns:
        int: UTC时间戳（秒）
    """
    # 解析本地时间（东八区 UTC+8）
    local_dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
    # 附加东八区时区信息
    from datetime import timedelta
    tz_cst = timezone(timedelta(hours=8))
    local_dt = local_dt.replace(tzinfo=tz_cst)
    # 转换为UTC时间戳
    return int(local_dt.timestamp())


class DataCollectAPI:
    """数据采集API封装"""

    @staticmethod
    def query_battery_history(sn, dev_id, start_time, end_time, token, host):
        """
        查询电池电量历史数据
        
        Args:
            sn: 设备SN
            dev_id: 设备ID（暂未使用，保留兼容）
            start_time: 开始时间（字符串格式：yyyy-MM-dd HH:mm:ss，本地东八区）
            end_time: 结束时间
            token: 认证token（Seetong-Auth header）
            host: API主机地址（如 console.seetong.com）
            
        Returns:
            {
                'success': True/False,
                'data': [
                    {'time': '2024-01-01 08:00:00', 'battery': 85},
                    ...
                ],
                'message': '成功/错误信息'
            }
        """
        try:
            # 将本地时间转换为UTC时间戳
            start_ts = _to_utc_timestamp(start_time)
            end_ts = _to_utc_timestamp(end_time)

            url = f"https://{host}/api/seetong-siot-device/console/data/report/device/battery/level/trend"

            headers = {
                "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
                "Seetong-Auth": f"bearer {token}",
                "Accept": "application/json, text/plain, */*",
            }

            params = {
                "deviceSn": sn,
                "zone": "+08:00",
                "startTimestamp": start_ts,
                "endTimestamp": end_ts,
            }

            logger.debug(f"查询电池电量: SN={sn}, start={start_ts}, end={end_ts}")

            response = requests.get(url, headers=headers, params=params, timeout=30, verify=False)

            # Token 过期，返回特定标识让调用方刷新后重试
            if response.status_code == 401:
                return {'success': False, 'data': [], 'message': 'token_expired'}

            response.raise_for_status()

            result = response.json()

            if result.get('code') == 200 and result.get('success'):
                data = result.get('data', {})
                dates = data.get('dates', [])
                levels = data.get('batteryLevels', [])

                records = [
                    {'time': t, 'battery': int(b) if b == int(b) else b}
                    for t, b in zip(dates, levels)
                ]

                return {
                    'success': True,
                    'data': records,
                    'message': f'查询成功，共 {len(records)} 条记录'
                }
            else:
                msg = result.get('msg', '查询失败')
                return {'success': False, 'data': [], 'message': msg}

        except requests.Timeout:
            return {'success': False, 'data': [], 'message': '请求超时'}
        except requests.RequestException as e:
            return {'success': False, 'data': [], 'message': f'网络错误: {str(e)}'}
        except Exception as e:
            logger.error(f"查询电池历史数据异常: {e}")
            return {'success': False, 'data': [], 'message': f'查询异常: {str(e)}'}

    @staticmethod
    def query_data_history(sn, dev_id, collect_type, start_time, end_time, token, host):
        """通用历史数据查询接口"""
        if collect_type == 'battery':
            return DataCollectAPI.query_battery_history(
                sn, dev_id, start_time, end_time, token, host
            )
        else:
            return {'success': False, 'data': [], 'message': f'不支持的采集类型: {collect_type}'}


class DataCollectThread(QThread):
    """单设备数据查询线程"""
    finished = pyqtSignal(bool, list, str)  # 成功标志, 数据列表, 消息
    log_message = pyqtSignal(str)           # 日志消息

    def __init__(self, sn, dev_id, collect_type, start_time, end_time, token, host):
        super().__init__()
        self.sn = sn
        self.dev_id = dev_id
        self.collect_type = collect_type
        self.start_time = start_time
        self.end_time = end_time
        self.token = token
        self.host = host

    def run(self):
        try:
            self.log_message.emit(f"开始查询 {self.sn} 的电池电量数据...")
            result = DataCollectAPI.query_data_history(
                self.sn, self.dev_id, self.collect_type,
                self.start_time, self.end_time,
                self.token, self.host
            )

            # Token 过期，尝试刷新后重试一次
            if not result['success'] and result.get('message') == 'token_expired':
                self.log_message.emit(f"Token已过期，正在刷新...")
                new_token = self._refresh_token()
                if new_token:
                    self.token = new_token
                    result = DataCollectAPI.query_data_history(
                        self.sn, self.dev_id, self.collect_type,
                        self.start_time, self.end_time,
                        self.token, self.host
                    )
                else:
                    result = {'success': False, 'data': [], 'message': 'Token刷新失败，请重新打开查询窗口'}

            if result['success']:
                self.log_message.emit(f"查询完成: {self.sn}，{result['message']}")
                self.finished.emit(True, result['data'], result['message'])
            else:
                self.log_message.emit(f"查询失败: {self.sn}，{result['message']}")
                self.finished.emit(False, [], result['message'])
        except Exception as e:
            logger.error(f"数据查询线程异常: {e}")
            self.log_message.emit(f"查询异常: {self.sn}，{str(e)}")
            self.finished.emit(False, [], f'查询异常: {str(e)}')

    def _refresh_token(self):
        """刷新 Token"""
        try:
            from query_tool.utils.config import get_account_config
            from query_tool.utils.device_query import DeviceQuery
            env, username, password = get_account_config()
            if not username or not password:
                return None
            dq = DeviceQuery(env, username, password, use_cache=False)
            if dq.init_error:
                logger.error(f"Token刷新失败: {dq.init_error}")
                return None
            logger.info("Token刷新成功")
            return dq.token
        except Exception as e:
            logger.error(f"Token刷新异常: {e}")
            return None


class BatchDataCollectWorker:
    """批量数据查询Worker"""

    def __init__(self, devices, collect_type, start_time, end_time,
                 token, host, max_workers=30):
        self.devices = devices
        self.collect_type = collect_type
        self.start_time = start_time
        self.end_time = end_time
        self.token = token
        self.host = host
        self.max_workers = max_workers
        self.stopped = False
        self.progress_callback = None
        self.finished_callback = None
        self.log_callback = None

    def stop(self):
        self.stopped = True

    def _refresh_token(self):
        """刷新 Token"""
        try:
            from query_tool.utils.config import get_account_config
            from query_tool.utils.device_query import DeviceQuery
            env, username, password = get_account_config()
            if not username or not password:
                return None
            dq = DeviceQuery(env, username, password, use_cache=False)
            if dq.init_error:
                logger.error(f"Token刷新失败: {dq.init_error}")
                return None
            logger.info("批量查询Token刷新成功")
            return dq.token
        except Exception as e:
            logger.error(f"Token刷新异常: {e}")
            return None

    def query_single_device(self, device):
        """查询单个设备"""
        if self.stopped:
            return None

        sn = device['sn']
        dev_id = device.get('dev_id', '')

        try:
            if self.log_callback:
                self.log_callback(f"查询中: {sn}")
            if self.progress_callback:
                self.progress_callback(sn, 'querying', 0, '查询中...')

            result = DataCollectAPI.query_data_history(
                sn, dev_id, self.collect_type,
                self.start_time, self.end_time,
                self.token, self.host
            )

            # Token 过期，刷新后重试一次
            if not result['success'] and result.get('message') == 'token_expired':
                if self.log_callback:
                    self.log_callback(f"Token已过期，正在刷新...")
                new_token = self._refresh_token()
                if new_token:
                    self.token = new_token
                    result = DataCollectAPI.query_data_history(
                        sn, dev_id, self.collect_type,
                        self.start_time, self.end_time,
                        self.token, self.host
                    )
                else:
                    result = {'success': False, 'data': [], 'message': 'Token刷新失败'}

            if result['success']:
                record_count = len(result['data'])
                if self.log_callback:
                    self.log_callback(f"成功: {sn}，{record_count} 条记录")
                if self.progress_callback:
                    self.progress_callback(sn, 'success', record_count, '查询成功')
                return {
                    'sn': sn,
                    'device_name': device.get('device_name', ''),
                    'model': device.get('model', ''),
                    'success': True,
                    'data': result['data']
                }
            else:
                if self.log_callback:
                    self.log_callback(f"失败: {sn}，{result['message']}")
                if self.progress_callback:
                    self.progress_callback(sn, 'failed', 0, result['message'])
                return {'sn': sn, 'success': False, 'message': result['message']}

        except Exception as e:
            error_msg = f'查询异常: {str(e)}'
            logger.error(f"批量查询设备 {sn} 异常: {e}")
            if self.log_callback:
                self.log_callback(f"异常: {sn}，{error_msg}")
            if self.progress_callback:
                self.progress_callback(sn, 'failed', 0, error_msg)
            return {'sn': sn, 'success': False, 'message': error_msg}

    def run(self):
        """执行批量查询"""
        success_count = 0
        fail_count = 0
        total_records = 0
        all_results = []

        total = len(self.devices)
        if self.log_callback:
            self.log_callback(f"开始批量查询，共 {total} 台设备，线程数: {self.max_workers}")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.query_single_device, device): device
                for device in self.devices
            }

            for future in as_completed(futures):
                if self.stopped:
                    break

                result = future.result()
                if result:
                    all_results.append(result)
                    if result['success']:
                        success_count += 1
                        total_records += len(result['data'])
                    else:
                        fail_count += 1

        if self.log_callback:
            self.log_callback(
                f"批量查询完成: 成功 {success_count} 台，失败 {fail_count} 台，共 {total_records} 条记录"
            )

        if self.finished_callback:
            self.finished_callback(success_count, fail_count, total_records, all_results)


class BatchDataCollectThread(QThread):
    """批量数据查询线程"""
    progress = pyqtSignal(str, str, int, str)   # SN, 状态, 记录数, 消息
    finished = pyqtSignal(int, int, int, list)   # 成功数, 失败数, 总记录数, 所有结果
    log_message = pyqtSignal(str)                # 日志消息

    def __init__(self, devices, collect_type, start_time, end_time,
                 token, host, max_workers=30):
        super().__init__()
        self.worker = BatchDataCollectWorker(
            devices, collect_type, start_time, end_time,
            token, host, max_workers
        )
        self.worker.progress_callback = self.emit_progress
        self.worker.finished_callback = self.emit_finished
        self.worker.log_callback = self.emit_log

    def emit_progress(self, sn, status, record_count, message):
        self.progress.emit(sn, status, record_count, message)

    def emit_finished(self, success_count, fail_count, total_records, all_results):
        self.finished.emit(success_count, fail_count, total_records, all_results)

    def emit_log(self, message):
        self.log_message.emit(message)

    def run(self):
        self.worker.run()

    def stop(self):
        self.worker.stop()
