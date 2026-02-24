"""
多线程Worker和Thread类
提供设备查询、唤醒、账号查询等后台任务
"""
from PyQt5.QtCore import QObject, QThread, pyqtSignal
from concurrent.futures import ThreadPoolExecutor, as_completed
from .device_query import DeviceQuery, wake_device_smart
from .logger import logger
from threading import Lock, Event


class QueryWorker(QObject):
    """查询工作器，管理多线程查询"""
    single_result = pyqtSignal(int, dict)  # 单个结果信号：(行号, 结果)
    all_done = pyqtSignal()  # 全部完成信号
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    init_success = pyqtSignal()  # 初始化成功信号
    
    def __init__(self, sn_list, id_list, env, username, password, max_workers=30):
        super().__init__()
        self.sn_list = sn_list
        self.id_list = id_list
        self.env = env
        self.username = username
        self.password = password
        self.query = None  # 将在run中初始化
        self.max_workers = max_workers
        self._stop_event = Event()  # 使用Event代替简单的标志
        self._lock = Lock()  # 保护共享状态
        
    def stop(self):
        """停止工作器"""
        self._stop_event.set()
        logger.debug("QueryWorker停止信号已设置")
        
    def is_stopped(self):
        """检查是否已停止"""
        return self._stop_event.is_set()
        
    def query_single_device(self, row, query_type, value):
        """查询单个设备"""
        if self.is_stopped():
            return row, None
        try:
            if query_type == 'sn':
                info = self.query.get_device_info(dev_sn=value)
            else:
                info = self.query.get_device_info(dev_id=value)
                
            records = info.get('data', {}).get('records', [])
            if records:
                record = records[0]
                dev_id = record.get('devId')
                sn = record.get('devSN', value if query_type == 'sn' else '')
                password = self.query.get_cloud_password(dev_id) if dev_id else ''
                node_info = self.query.get_access_node(dev_id=dev_id) if dev_id else {}
                # 使用新接口获取版本号
                version = self.query.get_device_version(dev_id) if dev_id else ''
                # 使用新接口获取在线状态和型号
                header_info = self.query.get_device_header(sn) if sn else {}
                online_status = header_info.get('data', {}).get('onlineStatus', -1) if header_info and header_info.get('data') else -1
                model = header_info.get('data', {}).get('productName', '') if header_info else ''
                # 获取最后心跳时间
                last_heartbeat = self.query.get_device_last_heartbeat(dev_id) if dev_id else ''
                # 获取设备名称
                device_name = self.query.get_device_name(dev_id) if dev_id else ''
                
                # 如果型号为空，尝试从版本号中提取
                if not model and version and '-' in version:
                    # 从版本号中提取型号，如 TS8864G-V4.6.1.1-Build202412190026 -> TS8864G
                    extracted_model = version.split('-')[0].strip()
                    if extracted_model:
                        model = extracted_model
                
                return row, {
                    'device_name': device_name or '',
                    'sn': sn,
                    'id': str(dev_id) if dev_id else '',
                    'password': password or '',
                    'node': node_info.get('serverId', '') if node_info else '',
                    'model': model or '',
                    'version': version or '',
                    'online': online_status,
                    'last_heartbeat': last_heartbeat or ''
                }
            else:
                return row, {
                    'device_name': '',
                    'sn': value if query_type == 'sn' else '',
                    'id': value if query_type == 'id' else '',
                    'password': '', 'node': '', 'model': '', 'version': '', 'online': -1, 'last_heartbeat': ''
                }
        except Exception as e:
            logger.error(f"查询设备失败 {value}: {e}")
            return row, {
                'device_name': '',
                'sn': value if query_type == 'sn' else '',
                'id': value if query_type == 'id' else '',
                'password': '', 'node': '', 'model': '', 'version': '',
                'online': -2, 'last_heartbeat': '', 'error': str(e)
            }
    
    def run(self):
        try:
            # 在后台线程中初始化DeviceQuery
            self.progress.emit("正在登录...")
            self.query = DeviceQuery(self.env, self.username, self.password)
            
            # 检查初始化是否成功
            if self.query.init_error:
                self.error.emit(self.query.init_error)
                return
            
            # 初始化成功，发送信号
            self.init_success.emit()
            
            # 构建任务列表：(行号, 查询类型, 值)
            tasks = []
            row = 0
            for sn in self.sn_list:
                tasks.append((row, 'sn', sn))
                row += 1
            for dev_id in self.id_list:
                tasks.append((row, 'id', dev_id))
                row += 1
            
            total = len(tasks)
            completed = 0
            
            self.progress.emit(f"开始查询 {total} 台设备...")
            
            # 使用线程池并发查询
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self.query_single_device, t[0], t[1], t[2]): t
                    for t in tasks
                }
                
                for future in as_completed(futures):
                    if self.is_stopped():
                        break
                    row, result = future.result()
                    if result:
                        self.single_result.emit(row, result)
                    completed += 1
                    # 每 5 个任务或最后一个任务时更新进度
                    if completed % 5 == 0 or completed == total:
                        self.progress.emit(f"查询进度: {completed}/{total}")
            
            self.all_done.emit()
        except Exception as e:
            self.error.emit(str(e))


class QueryThread(QThread):
    """查询线程"""
    single_result = pyqtSignal(int, dict)
    all_done = pyqtSignal()
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    init_success = pyqtSignal()  # 初始化成功信号
    
    def __init__(self, sn_list, id_list, env, username, password, max_workers=30):
        super().__init__()
        self.worker = QueryWorker(sn_list, id_list, env, username, password, max_workers)
        self.worker.single_result.connect(self.single_result)
        self.worker.all_done.connect(self.all_done)
        self.worker.progress.connect(self.progress)
        self.worker.error.connect(self.error)
        self.worker.init_success.connect(self.init_success)
        
    def run(self):
        try:
            self.worker.run()
        except KeyboardInterrupt:
            # 用户按Ctrl+C，静默处理
            logger.debug("QueryThread被用户中断")
            pass
        except Exception as e:
            # 其他异常记录日志
            logger.error(f"QueryThread异常: {e}")
            self.error.emit(str(e))
        
    def stop(self):
        self.worker.stop()


class WakeWorker(QObject):
    """唤醒工作器，管理多线程唤醒"""
    wake_result = pyqtSignal(str, bool)  # (设备标识, 是否成功)
    all_done = pyqtSignal()
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, devices, query, max_workers=30):
        super().__init__()
        self.devices = devices  # [(dev_id, sn), ...]
        self.query = query  # 已初始化的DeviceQuery对象
        self.max_workers = max_workers
        self._stop_event = Event()  # 使用Event代替简单的标志
        
    def stop(self):
        """停止工作器"""
        self._stop_event.set()
        logger.debug("WakeWorker停止信号已设置")
        
    def is_stopped(self):
        """检查是否已停止"""
        return self._stop_event.is_set()
        
    def wake_single_device(self, dev_id, sn):
        """唤醒单个设备"""
        if self.is_stopped():
            return dev_id, sn, False
        try:
            # 获取token
            token = self.query.token
            # 调用智能唤醒函数
            success = wake_device_smart(dev_id, sn, token, max_times=3)
            return dev_id, sn, success
        except Exception as e:
            logger.error(f"唤醒设备失败 {sn}({dev_id}): {e}")
            return dev_id, sn, False
    
    def run(self):
        try:
            self.progress.emit("正在初始化...")
            
            total = len(self.devices)
            completed = 0
            
            self.progress.emit(f"开始唤醒 {total} 台设备...")
            
            # 使用线程池并发唤醒
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self.wake_single_device, dev_id, sn): (dev_id, sn)
                    for dev_id, sn in self.devices
                }
                
                for future in as_completed(futures):
                    if self.is_stopped():
                        break
                    dev_id, sn, success = future.result()
                    self.wake_result.emit(f"{sn}({dev_id})", success)
                    completed += 1
                    # 每 5 个任务或最后一个任务时更新进度
                    if completed % 5 == 0 or completed == total:
                        self.progress.emit(f"唤醒进度: {completed}/{total}")
            
            self.all_done.emit()
        except Exception as e:
            logger.error(f"唤醒任务失败: {e}")
            self.error.emit(str(e))
            self.all_done.emit()


class WakeThread(QThread):
    """唤醒线程"""
    wake_result = pyqtSignal(str, bool)
    all_done = pyqtSignal()
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, devices, query, max_workers=30):
        super().__init__()
        self.worker = WakeWorker(devices, query, max_workers)
        self.worker.wake_result.connect(self.wake_result)
        self.worker.all_done.connect(self.all_done)
        self.worker.progress.connect(self.progress)
        self.worker.error.connect(self.error)
        
    def run(self):
        try:
            self.worker.run()
        except KeyboardInterrupt:
            # 用户按Ctrl+C，静默处理
            logger.debug("WakeThread被用户中断")
            pass
        except Exception as e:
            # 其他异常记录日志
            logger.error(f"WakeThread异常: {e}")
            self.error.emit(str(e))
        
    def stop(self):
        self.worker.stop()


class PhoneQueryWorker(QObject):
    """账号查询工作器"""
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    success = pyqtSignal(list, list)  # (查询结果, 型号列表)
    
    def __init__(self, phone, env, username, password, max_workers=30):
        super().__init__()
        self.phone = phone
        self.env = env
        self.username = username
        self.password = password
        self.max_workers = max_workers  # 使用可配置的线程数
        self._stop_event = Event()  # 添加停止事件
        
    def stop(self):
        """停止工作器"""
        self._stop_event.set()
        logger.debug("PhoneQueryWorker停止信号已设置")
        
    def is_stopped(self):
        """检查是否已停止"""
        return self._stop_event.is_set()
        
    def run(self):
        try:
            # 初始化查询对象
            self.progress.emit("正在登录...")
            query = DeviceQuery(self.env, self.username, self.password)
            
            if query.init_error:
                self.error.emit(query.init_error)
                return
            
            # 第一步：根据手机号查询用户ID
            self.progress.emit("正在查询用户信息...")
            user_response = query.get_user_by_mobile(self.phone)
            if not user_response or not user_response.get('data'):
                self.error.emit("未找到该手机号对应的用户")
                return
            
            records = user_response['data'].get('records', [])
            if not records:
                self.error.emit("未找到该手机号对应的用户")
                return
            
            user_id = records[0].get('id')
            if not user_id:
                self.error.emit("无法获取用户ID")
                return
            
            # 第二步：根据用户ID查询绑定设备列表
            self.progress.emit("正在查询绑定设备...")
            devices_response = query.get_user_bind_devices(user_id)
            if not devices_response or not devices_response.get('data'):
                self.error.emit("未找到该用户的绑定设备")
                return
            
            devices = devices_response['data']
            if not devices:
                self.error.emit("该用户暂无绑定设备")
                return
            
            # 第三步：并发查询所有设备的型号和版本信息
            self.progress.emit(f"正在查询 {len(devices)} 台设备的型号和版本信息...")
            
            def get_device_complete_info(device):
                """查询单个设备的完整信息"""
                # 检查是否已停止
                if self.is_stopped():
                    return None
                    
                device_sn = device.get('deviceSn', '')
                device_name = device.get('deviceName', '')
                
                if not device_sn:
                    return {
                        'device_name': device_name,
                        'sn': device_sn,
                        'id': '',
                        'password': '',
                        'node': '',
                        'model': '未知型号',
                        'version': '',
                        'online': -1,
                        'last_heartbeat': ''
                    }
                
                try:
                    # 1. 通过SN获取基本信息和dev_id
                    info = query.get_device_info(dev_sn=device_sn)
                    records = info.get('data', {}).get('records', [])
                    
                    dev_id = None
                    standard_sn = device_sn  # 默认使用原始SN
                    
                    if records:
                        record = records[0]
                        dev_id = record.get('devId')
                        # 使用从get_device_info返回的标准化SN
                        standard_sn = record.get('devSN', device_sn)
                    
                    # 2. 获取其他信息（即使dev_id为空也尝试获取型号和在线状态）
                    password = ''
                    node = ''
                    model = ''
                    version = ''
                    online_status = -1
                    last_heartbeat = ''
                    
                    # 获取型号和在线状态（使用标准化的SN）
                    try:
                        header_info = query.get_device_header(standard_sn)
                        if header_info:
                            if header_info.get('data'):
                                model = header_info['data'].get('productName', '')
                                online_status = header_info['data'].get('onlineStatus', 0)
                            elif header_info.get('code') == 20001:
                                # 设备不存在
                                model = '设备不存在'
                                online_status = -1
                    except Exception as e:
                        # 型号和在线状态获取失败
                        pass
                    
                    # 以下信息需要dev_id
                    if dev_id:
                        try:
                            # 获取密码
                            password = query.get_cloud_password(dev_id) or ''
                        except Exception as e:
                            # 密码获取失败不影响其他信息
                            pass
                        
                        try:
                            # 获取节点
                            node_info = query.get_access_node(dev_id=dev_id)
                            node = node_info.get('serverId', '') if node_info else ''
                        except Exception as e:
                            # 节点获取失败不影响其他信息
                            pass
                        
                        try:
                            # 获取版本
                            version = query.get_device_version(dev_id) or ''
                        except Exception as e:
                            # 版本获取失败不影响其他信息
                            pass
                        
                        try:
                            # 获取最后心跳
                            last_heartbeat = query.get_device_last_heartbeat(dev_id) or ''
                        except Exception as e:
                            # 心跳获取失败不影响其他信息
                            pass
                    
                    # 如果型号为空或未找到，尝试从版本号中提取
                    if not model or model in ['设备不存在', '未知型号', '查询失败', '未找到']:
                        if version and '-' in version:
                            # 从版本号中提取型号，如 TS8864G-V4.6.1.1-Build202412190026 -> TS8864G
                            extracted_model = version.split('-')[0].strip()
                            if extracted_model:
                                model = extracted_model
                    
                    return {
                        'device_name': device_name,
                        'sn': standard_sn,  # 使用标准化的SN
                        'id': str(dev_id) if dev_id else '',
                        'password': password,
                        'node': node,
                        'model': model,
                        'version': version,
                        'online': online_status,
                        'last_heartbeat': last_heartbeat
                    }
                except Exception as e:
                    return {
                        'device_name': device_name,
                        'sn': device_sn,
                        'id': '',
                        'password': '',
                        'node': '',
                        'model': '查询失败',
                        'version': '',
                        'online': -2,
                        'last_heartbeat': '',
                        'error': str(e)
                    }
            
            # 使用线程池并发查询完整信息
            results = []
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = [executor.submit(get_device_complete_info, device) for device in devices]
                completed = 0
                for future in as_completed(futures):
                    # 检查是否已停止
                    if self.is_stopped():
                        logger.debug("PhoneQueryWorker已停止，取消剩余任务")
                        break
                    
                    result = future.result()
                    if result:  # 过滤掉None结果（已停止的任务）
                        results.append(result)
                    completed += 1
                    # 每 5 个任务或最后一个任务时更新进度
                    if completed % 5 == 0 or completed == len(devices):
                        self.progress.emit(f"正在查询设备信息... {completed}/{len(devices)}")
            
            # 提取所有设备型号
            models = set()
            for device in results:
                if device.get("model") and device["model"] not in ["未知型号", "查询失败", "未找到", "设备不存在"]:
                    models.add(device["model"])
            
            # 发送成功信号
            self.success.emit(results, sorted(list(models)))
            
        except Exception as e:
            self.error.emit(f"查询失败：{str(e)}")


class PhoneQueryThread(QThread):
    """账号查询线程"""
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    success = pyqtSignal(list, list)
    
    def __init__(self, phone, env, username, password, max_workers=30):
        super().__init__()
        self.worker = PhoneQueryWorker(phone, env, username, password, max_workers)
        self.worker.progress.connect(self.progress)
        self.worker.error.connect(self.error)
        self.worker.success.connect(self.success)
    
    def stop(self):
        """停止线程"""
        if self.worker:
            self.worker.stop()
        
    def run(self):
        try:
            self.worker.run()
        except KeyboardInterrupt:
            # 用户按Ctrl+C，静默处理
            logger.debug("PhoneQueryThread被用户中断")
            pass
        except Exception as e:
            # 其他异常记录日志
            logger.error(f"PhoneQueryThread异常: {e}")
            self.error.emit(str(e))
