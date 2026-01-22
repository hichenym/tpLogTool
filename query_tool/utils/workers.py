"""
多线程Worker和Thread类
提供设备查询、唤醒、账号查询等后台任务
"""
from PyQt5.QtCore import QObject, QThread, pyqtSignal
from concurrent.futures import ThreadPoolExecutor, as_completed
from .device_query import DeviceQuery, wake_device_smart


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
        self._stop = False
        
    def stop(self):
        self._stop = True
        
    def query_single_device(self, row, query_type, value):
        """查询单个设备"""
        if self._stop:
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
                # 使用新接口获取在线状态
                header_info = self.query.get_device_header(sn) if sn else {}
                online_status = header_info.get('data', {}).get('onlineStatus', 0) if header_info else 0
                # 获取最后心跳时间
                last_heartbeat = self.query.get_device_last_heartbeat(dev_id) if dev_id else ''
                # 获取设备名称
                device_name = self.query.get_device_name(dev_id) if dev_id else ''
                return row, {
                    'device_name': device_name or '',
                    'sn': sn,
                    'id': str(dev_id) if dev_id else '',
                    'password': password or '',
                    'node': node_info.get('serverId', '') if node_info else '',
                    'version': version or '',
                    'online': online_status,
                    'last_heartbeat': last_heartbeat or ''
                }
            else:
                return row, {
                    'device_name': '',
                    'sn': value if query_type == 'sn' else '',
                    'id': value if query_type == 'id' else '',
                    'password': '', 'node': '', 'version': '', 'online': -1, 'last_heartbeat': ''
                }
        except Exception as e:
            return row, {
                'device_name': '',
                'sn': value if query_type == 'sn' else '',
                'id': value if query_type == 'id' else '',
                'password': '', 'node': '', 'version': '',
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
                    if self._stop:
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
        self.worker.run()
        
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
        self._stop = False
        
    def stop(self):
        self._stop = True
        
    def wake_single_device(self, dev_id, sn):
        """唤醒单个设备"""
        if self._stop:
            return dev_id, sn, False
        try:
            # 获取token
            token = self.query.token
            # 调用智能唤醒函数
            success = wake_device_smart(dev_id, sn, token, max_times=3)
            return dev_id, sn, success
        except Exception as e:
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
                    if self._stop:
                        break
                    dev_id, sn, success = future.result()
                    self.wake_result.emit(f"{sn}({dev_id})", success)
                    completed += 1
                    # 每 5 个任务或最后一个任务时更新进度
                    if completed % 5 == 0 or completed == total:
                        self.progress.emit(f"唤醒进度: {completed}/{total}")
            
            self.all_done.emit()
        except Exception as e:
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
        self.worker.run()
        
    def stop(self):
        self.worker.stop()


class PhoneQueryWorker(QObject):
    """账号查询工作器"""
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    success = pyqtSignal(list, list)  # (查询结果, 型号列表)
    
    def __init__(self, phone, env, username, password):
        super().__init__()
        self.phone = phone
        self.env = env
        self.username = username
        self.password = password
        
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
            
            # 第三步：并发查询所有设备的型号信息
            self.progress.emit(f"正在查询 {len(devices)} 台设备的型号信息...")
            
            def get_device_model(device):
                """查询单个设备的型号"""
                device_sn = device.get('deviceSn', '')
                device_name = device.get('deviceName', '')
                
                if not device_sn:
                    return {
                        "model": "未知型号",
                        "name": device_name,
                        "sn": device_sn
                    }
                
                try:
                    header_info = query.get_device_header(device_sn)
                    product_name = ""
                    if header_info and header_info.get('data'):
                        product_name = header_info['data'].get('productName', '未知型号')
                    else:
                        product_name = "未知型号"
                    
                    return {
                        "model": product_name,
                        "name": device_name,
                        "sn": device_sn
                    }
                except Exception as e:
                    return {
                        "model": "查询失败",
                        "name": device_name,
                        "sn": device_sn
                    }
            
            # 使用线程池并发查询
            results = []
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = [executor.submit(get_device_model, device) for device in devices]
                completed = 0
                for future in as_completed(futures):
                    result = future.result()
                    results.append(result)
                    completed += 1
                    # 每 5 个任务或最后一个任务时更新进度
                    if completed % 5 == 0 or completed == len(devices):
                        self.progress.emit(f"正在查询型号信息... {completed}/{len(devices)}")
            
            # 提取所有设备型号
            models = set()
            for device in results:
                if device["model"] and device["model"] not in ["未知型号", "查询失败"]:
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
    
    def __init__(self, phone, env, username, password):
        super().__init__()
        self.worker = PhoneQueryWorker(phone, env, username, password)
        self.worker.progress.connect(self.progress)
        self.worker.error.connect(self.error)
        self.worker.success.connect(self.success)
        
    def run(self):
        self.worker.run()
