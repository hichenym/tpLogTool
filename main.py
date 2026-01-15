import sys
import os
import json
import time
import hashlib
import requests
import winreg
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QStatusBar, QMessageBox, QSplitter, QFrame,
    QLineEdit, QFileDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QSize, QTimer
from PyQt5.QtGui import QClipboard, QIcon, QPixmap
from concurrent.futures import ThreadPoolExecutor, as_completed
import icon_res  # 导入资源文件
from version import get_version_string  # 导入版本信息

# 禁用SSL警告
requests.packages.urllib3.disable_warnings()

# 注册表路径
REGISTRY_PATH = r"Software\TPDevQuery"


def get_registry_value(key_name, value_name, default=None):
    """从注册表读取值"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_name, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, value_name)
        winreg.CloseKey(key)
        return value
    except:
        return default

def set_registry_value(key_name, value_name, value, value_type=winreg.REG_SZ):
    """写入值到注册表"""
    try:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_name)
        winreg.SetValueEx(key, value_name, 0, value_type, value)
        winreg.CloseKey(key)
        return True
    except:
        return False


class DeviceQuery:
    """设备查询类"""
    def __init__(self, env, username, password, use_cache=True):
        self.username = username
        self.password = password
        self.host = 'console.seetong.com' if env == 'pro' else 'console-test.seetong.com'
        self.env = env
        
        if use_cache and self._load_token_cache():
            pass
        else:
            self.token, self.refresh_token = self._get_token()
            if use_cache:
                self._save_token_cache()

    def _load_token_cache(self):
        try:
            env = get_registry_value(REGISTRY_PATH, 'env')
            username = get_registry_value(REGISTRY_PATH, 'username')
            token = get_registry_value(REGISTRY_PATH, 'token')
            refresh_token = get_registry_value(REGISTRY_PATH, 'refresh_token')
            timestamp = get_registry_value(REGISTRY_PATH, 'timestamp')
            
            if env == self.env and username == self.username:
                if timestamp and time.time() - float(timestamp) < 7200:
                    self.token = token
                    self.refresh_token = refresh_token
                    return True
        except:
            pass
        return False

    def _save_token_cache(self):
        try:
            set_registry_value(REGISTRY_PATH, 'env', self.env)
            set_registry_value(REGISTRY_PATH, 'username', self.username)
            set_registry_value(REGISTRY_PATH, 'token', self.token)
            set_registry_value(REGISTRY_PATH, 'refresh_token', self.refresh_token)
            set_registry_value(REGISTRY_PATH, 'timestamp', str(time.time()))
        except:
            pass

    def _get_captcha(self):
        import ddddocr
        import base64
        
        url = f'https://{self.host}/api/seetong-auth/oauth/captcha'
        r = requests.get(url, verify=False)
        res = r.json()
        
        img_data = base64.b64decode(res['image'].split('base64,')[-1])
        ocr = ddddocr.DdddOcr(show_ad=False)
        return res['key'], ocr.classification(img_data)

    def _get_token(self, retry=3):
        for i in range(retry):
            try:
                captcha_key, captcha_code = self._get_captcha()
                url = f'https://{self.host}/api/seetong-auth/oauth/token'
                headers = {
                    "Content-Type": "application/json",
                    "Captcha-Code": captcha_code,
                    "Captcha-Key": captcha_key,
                    "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
                    "Tenant-Id": "000000",
                }
                params = {
                    "tenantId": "000000",
                    "username": self.username,
                    "password": hashlib.md5(self.password.encode()).hexdigest(),
                    "grant_type": "captcha",
                    "scope": "all",
                    "type": "account",
                }
                r = requests.post(url, params=params, headers=headers, verify=False)
                res = r.json()
                if res.get('access_token'):
                    return res['access_token'], res['refresh_token']
            except:
                pass
            time.sleep(1)
        sys.exit(1)

    def _request(self, api_path, params):
        url = f'https://{self.host}{api_path}'
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
            "Seetong-Auth": self.token,
        }
        r = requests.get(url, params=params, headers=headers, verify=False)
        if r.status_code == 401:
            self.token, self.refresh_token = self._get_token()
            self._save_token_cache()
            headers["Seetong-Auth"] = self.token
            r = requests.get(url, params=params, headers=headers, verify=False)
        return r.json()

    def get_device_info(self, dev_sn=None, dev_id=None):
        params = {"current": "1", "size": "10", "descs": "devId"}
        if dev_sn:
            params['deviceSn'] = dev_sn
        if dev_id:
            params['devId'] = dev_id
        return self._request('/api/seetong-device/device-basic-info/list', params)

    def get_cloud_password(self, dev_id):
        params = {"deviceId": dev_id, "password": hashlib.md5(self.password.encode()).hexdigest()}
        res = self._request('/api/seetong-device/device-basic-info/get-cloud-password', params)
        return res.get('data')

    def get_device_online_detail(self, dev_id):
        params = {"id": dev_id}
        return self._request('/api/seetong-devonline/siot-media/dev/detail', params)

    def get_device_header(self, dev_sn):
        params = {"sn": dev_sn}
        return self._request('/api/seetong-siot-device/console/device/header', params)

    def get_device_detail(self, dev_id):
        params = {"devId": dev_id}
        return self._request('/api/seetong-device/device-basic-info/detail', params)

    def get_device_version(self, dev_id):
        res = self.get_device_detail(dev_id)
        if res and res.get('data'):
            return res['data'].get('fileVersion', '')
        return ''

    def get_access_node(self, dev_sn=None, dev_id=None):
        if dev_sn and not dev_id:
            res = self.get_device_info(dev_sn=dev_sn)
            records = res.get('data', {}).get('records', [])
            dev_id = records[0]['devId'] if records else None
        if not dev_id:
            return None
        res = self.get_device_online_detail(dev_id)
        if not res or not res.get('data'):
            return None
        data = res['data']
        return {'serverId': data.get('serverId')}


def wake_device(dev_id, sn, token, host='console.seetong.com', times=3):
    """唤醒设备"""
    url = f'https://{host}/api/seetong-device-media-command/siot-media/command/send'
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
        "Seetong-Auth": token,
    }
    for i in range(times):
        data = {'devId': dev_id, 'type': 'LOW_POWER_WAKE', 'msg': f'wake-{i+1}'}
        try:
            r = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
        except:
            pass
        time.sleep(1)


def check_device_online(sn, token, host='console.seetong.com'):
    """查询设备在线状态"""
    try:
        url = f'https://{host}/api/seetong-siot-device/console/device/header'
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
            "Seetong-Auth": token,
        }
        params = {"sn": sn}
        r = requests.get(url, params=params, headers=headers, verify=False)
        res = r.json()
        data = res.get('data', {})
        online_status = data.get('onlineStatus', 0)
        return online_status == 1
    except:
        return False


def wake_device_smart(dev_id, sn, token, host='console.seetong.com', max_times=3):
    """智能唤醒设备：唤醒后查询状态，在线则停止，离线则继续唤醒"""
    url = f'https://{host}/api/seetong-device-media-command/siot-media/command/send'
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
        "Seetong-Auth": token,
    }
    
    for i in range(max_times):
        # 发送唤醒命令
        data = {'devId': dev_id, 'type': 'LOW_POWER_WAKE', 'msg': f'wake-{i+1}'}
        try:
            requests.post(url, data=json.dumps(data), headers=headers, verify=False)
        except:
            pass
        
        # 等待 2 秒后查询在线状态
        time.sleep(2)
        if check_device_online(sn, token, host):
            return True  # 设备已在线，停止唤醒
        
        # 如果不是最后一次，再等 1 秒后继续
        if i < max_times - 1:
            time.sleep(1)
    
    return False  # 多次唤醒后仍离线


class ClickableLabel(QLabel):
    """可点击的标签，用于显示版本信息"""
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)  # 设置鼠标指针为手型
        self.clicked = None  # 点击事件回调
        
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == Qt.LeftButton and self.clicked:
            self.clicked()
        super().mousePressEvent(event)


class PlainTextEdit(QTextEdit):
    """纯文本输入框，粘贴时自动清除格式"""
    def insertFromMimeData(self, source):
        """重写粘贴方法，只插入纯文本"""
        if source.hasText():
            self.insertPlainText(source.text())
        else:
            super().insertFromMimeData(source)


class QueryWorker(QObject):
    """查询工作器，管理多线程查询"""
    single_result = pyqtSignal(int, dict)  # 单个结果信号：(行号, 结果)
    all_done = pyqtSignal()  # 全部完成信号
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, sn_list, id_list, query, max_workers=30):
        super().__init__()
        self.sn_list = sn_list
        self.id_list = id_list
        self.query = query  # 已初始化的DeviceQuery对象
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
                return row, {
                    'sn': sn,
                    'id': str(dev_id) if dev_id else '',
                    'password': password or '',
                    'node': node_info.get('serverId', '') if node_info else '',
                    'version': version or '',
                    'online': online_status
                }
            else:
                return row, {
                    'sn': value if query_type == 'sn' else '',
                    'id': value if query_type == 'id' else '',
                    'password': '', 'node': '', 'version': '', 'online': -1
                }
        except Exception as e:
            return row, {
                'sn': value if query_type == 'sn' else '',
                'id': value if query_type == 'id' else '',
                'password': '', 'node': '', 'version': '',
                'online': -2, 'error': str(e)
            }
    
    def run(self):
        try:
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
    
    def __init__(self, sn_list, id_list, query, max_workers=30):
        super().__init__()
        self.worker = QueryWorker(sn_list, id_list, query, max_workers)
        self.worker.single_result.connect(self.single_result)
        self.worker.all_done.connect(self.all_done)
        self.worker.progress.connect(self.progress)
        self.worker.error.connect(self.error)
        
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
                    self.progress.emit(f"唤醒进度: {completed}/{total}")
            
            self.all_done.emit()
        except Exception as e:
            self.error.emit(str(e))
            
            self.all_done.emit()
        except Exception as e:
            self.error.emit(str(e))


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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("设备信息查询工具")
        self.setGeometry(100, 100, 600, 350)
        # 设置窗口最小尺寸
        self.setMinimumSize(500, 300)
        # 设置窗口图标
        self.setWindowIcon(QIcon(":/icon/logo.png"))
        self.query_thread = None
        self.wake_thread = None
        self.wake_threads = []  # 保持线程引用
        self.total_count = 0
        self.online_count = 0
        self.offline_count = 0
        self.column_width_ratios = {}  # 存储列宽比例
        self.resize_timer = None  # 用于防止频繁调整
        self.query_results = {}  # 存储查询结果 {行号: 结果}
        self.query_input_type = None  # 记录查询类型 'sn' 或 'id'
        self.query_input_list = []  # 记录输入的列表
        self.export_path = ""  # 导出路径
        self.version_timer = None  # 版本信息隐藏定时器
        self.init_ui()
        # 加载配置
        self.load_config()
        # 将窗口移到屏幕中间
        self.center_on_screen()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)  # 移除所有边距
        main_layout.setSpacing(0)  # 移除间距

        # 使用QSplitter实现可拖拽调整高度
        splitter = QSplitter(Qt.Vertical)
        
        # 顶部输入区容器
        top_widget = QFrame()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(5, 5, 5, 0)  # 只保留上左右边距
        top_layout.setSpacing(5)
        
        # 标签行
        label_layout = QHBoxLayout()
        sn_label = QLabel("输入SN（每行一个）：")
        id_label = QLabel("输入ID（每行一个）：")
        label_layout.addWidget(sn_label, 1)
        label_layout.addWidget(id_label, 1)
        label_layout.addSpacing(88)  # 为按钮区域留空
        top_layout.addLayout(label_layout)
        
        # 输入框和按钮行
        input_layout = QHBoxLayout()
        
        # SN输入框
        self.sn_input = PlainTextEdit()
        self.sn_input.setMinimumHeight(80)
        self.sn_input.setPlaceholderText("请输入设备SN，每行一个...")
        self.sn_input.setReadOnly(False)
        self.sn_input.setEnabled(True)
        self.sn_input.selectionChanged.connect(self.on_text_selection_changed)
        
        # ID输入框
        self.id_input = PlainTextEdit()
        self.id_input.setMinimumHeight(80)
        self.id_input.setPlaceholderText("请输入设备ID，每行一个...")
        self.id_input.setReadOnly(False)
        self.id_input.setEnabled(True)
        self.id_input.selectionChanged.connect(self.on_text_selection_changed)
        
        # 按钮（垂直居中）
        btn_widget = QWidget()
        btn_layout = QVBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        self.query_btn = QPushButton("查询")
        self.query_btn.setIcon(QIcon(":/icon/search.png"))
        self.query_btn.setIconSize(QSize(16, 16))  # 16x16 像素
        self.clear_btn = QPushButton("清空")
        self.clear_btn.setIcon(QIcon(":/icon/clean.png"))
        self.clear_btn.setIconSize(QSize(16, 16))  # 16x16 像素
        self.query_btn.setFixedSize(80, 35)
        self.clear_btn.setFixedSize(80, 35)
        btn_layout.addStretch()
        btn_layout.addWidget(self.query_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()
        
        input_layout.addWidget(self.sn_input, 1)
        input_layout.addWidget(self.id_input, 1)
        input_layout.addWidget(btn_widget)
        top_layout.addLayout(input_layout)
        
        # 底部结果区容器
        bottom_widget = QFrame()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(5, 0, 5, 5)  # 左右下边距统一为5px
        bottom_layout.setSpacing(5)

        # 结果区标题和批量唤醒按钮
        result_header = QHBoxLayout()
        result_label = QLabel("查询结果：(双击可复制)")
        self.batch_wake_btn = QPushButton("批量唤醒")
        self.batch_wake_btn.setIcon(QIcon(":/icon/werk_up_all.png"))
        self.batch_wake_btn.setIconSize(QSize(16, 16))  # 16x16 像素
        self.batch_wake_btn.setFixedSize(100, 35)  # 增加宽度以显示完整图片和文字
        self.select_all_checkbox = QCheckBox("全选")
        result_header.addWidget(result_label)
        result_header.addStretch()
        result_header.addWidget(self.select_all_checkbox)
        result_header.addWidget(self.batch_wake_btn)
        bottom_layout.addLayout(result_header)

        # 结果表格
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(8)
        self.result_table.setHorizontalHeaderLabels(
            ["选择", "SN", "ID", "密码", "接入节点", "版本号", "在线状态", "操作"]
        )
        # 禁用表格焦点、选中和编辑
        self.result_table.setFocusPolicy(Qt.NoFocus)
        self.result_table.setSelectionMode(QTableWidget.NoSelection)
        self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)  # 禁用编辑
        
        # 设置单元格内边距样式和选中边框，超出显示省略号
        self.result_table.setStyleSheet("""
            QTableWidget::item {
                padding-right: 10px;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            QTableWidget::item:selected {
                background-color: transparent;
                color: black;
                border: 2px solid #0078d4;
            }
        """)
        header = self.result_table.horizontalHeader()
        header.setMinimumSectionSize(50)
        
        # 设置列宽模式：固定列用Fixed，可调节列用Interactive
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # 选择列固定
        header.setSectionResizeMode(7, QHeaderView.Fixed)  # 操作列固定
        
        # 中间列设为Interactive，允许用户拖拽调节（包括在线状态列）
        for col in range(1, 7):
            header.setSectionResizeMode(col, QHeaderView.Interactive)
        
        # 初始化列宽：固定列 + 内容列均分
        self.result_table.setColumnWidth(0, 50)  # 选择列固定
        self.result_table.setColumnWidth(7, 140)  # 操作列固定
        
        # 中间6列初始均分
        available_width = 600 - 50 - 140
        col_width = available_width // 6
        for col in range(1, 7):
            self.result_table.setColumnWidth(col, col_width)
        
        # 初始化列宽比例（用于缩放）
        self.column_width_ratios = {
            1: col_width,  # SN
            2: col_width,  # ID
            3: col_width,  # 密码
            4: col_width,  # 接入节点
            5: col_width,  # 版本号
            6: col_width,  # 在线状态
        }
        
        # 禁用水平滚动条
        self.result_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # 连接单元格双击事件
        self.result_table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        # 连接表格列宽变化事件，实时更新
        header.sectionResized.connect(self.on_column_resized)
        # 连接窗口resize事件
        self.resizeEvent = self.on_window_resize
        bottom_layout.addWidget(self.result_table)
        
        # 导出区域
        export_layout = QHBoxLayout()
        export_label = QLabel("保存位置：")
        self.export_path_input = QLineEdit()
        self.export_path_input.setPlaceholderText("选择CSV文件保存目录...")
        self.export_path_input.setReadOnly(True)
        self.export_path_input.setFocusPolicy(Qt.NoFocus)  # 禁用焦点
        self.browse_btn = QPushButton("浏览")
        self.browse_btn.setIcon(QIcon(":/icon/save.png"))
        self.browse_btn.setIconSize(QSize(16, 16))
        self.browse_btn.setFixedSize(80, 30)
        self.export_btn = QPushButton("导出")
        self.export_btn.setIcon(QIcon(":/icon/export.png"))
        self.export_btn.setIconSize(QSize(16, 16))
        self.export_btn.setFixedSize(80, 30)
        
        export_layout.addWidget(export_label)
        export_layout.addWidget(self.export_path_input, 1)
        export_layout.addWidget(self.browse_btn)
        export_layout.addWidget(self.export_btn)
        bottom_layout.addLayout(export_layout)
        
        # 添加到splitter
        splitter.addWidget(top_widget)
        splitter.addWidget(bottom_widget)
        splitter.setStretchFactor(0, 1)  # 输入区初始比例
        splitter.setStretchFactor(1, 2)  # 表格区初始比例
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #a0a0a0;
                margin: 5px 0px 5px 0px;
            }
            QSplitter::handle:hover {
                background-color: #606060;
            }
        """)
        
        main_layout.addWidget(splitter)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # 在状态栏右侧添加版本号（默认隐藏）
        self.version_label = ClickableLabel("  ")  # 默认显示空格占位
        self.version_label.setStyleSheet("color: gray; padding-right: 10px;")
        self.version_label.clicked = self.on_version_clicked
        self.status_bar.addPermanentWidget(self.version_label)
        
        self.status_bar.showMessage("就绪")

        # 绑定事件
        self.query_btn.clicked.connect(self.on_query)
        self.clear_btn.clicked.connect(self.on_clear)
        self.batch_wake_btn.clicked.connect(self.on_batch_wake)
        self.select_all_checkbox.stateChanged.connect(self.on_select_all)
        self.browse_btn.clicked.connect(self.on_browse_path)
        self.export_btn.clicked.connect(self.on_export_csv)

    def on_window_resize(self, event):
        """窗口resize事件"""
        super().resizeEvent(event)
        self.adjust_table_columns()

    def showEvent(self, event):
        """窗口显示事件，初始化表格列宽"""
        super().showEvent(event)
        # 延迟调用以确保窗口已完全显示
        self.adjust_table_columns()

    def on_version_clicked(self):
        """点击版本标签时显示版本信息"""
        # 显示版本信息
        self.version_label.setText(get_version_string())
        
        # 如果已有定时器，先停止
        if self.version_timer:
            self.version_timer.stop()
        
        # 创建1秒后隐藏的定时器
        self.version_timer = QTimer()
        self.version_timer.setSingleShot(True)  # 只触发一次
        self.version_timer.timeout.connect(self.hide_version)
        self.version_timer.start(1000)  # 1秒后触发
    
    def hide_version(self):
        """隐藏版本信息"""
        self.version_label.setText("  ")  # 恢复为空格占位

    def center_on_screen(self):
        """将窗口居中显示在屏幕上"""
        from PyQt5.QtWidgets import QDesktopWidget
        screen = QDesktopWidget().screenGeometry()
        window = self.geometry()
        x = (screen.width() - window.width()) // 2
        y = (screen.height() - window.height()) // 2
        self.move(x, y)

    def on_column_resized(self, logicalIndex):
        """列宽被用户调节时，实时调整其他列以保持表格宽度与窗口一致"""
        # 跳过固定列
        if logicalIndex == 0 or logicalIndex == 7:
            return
        
        # 获取表格可用宽度（减去固定列）
        table_width = self.result_table.width()
        fixed_width = 50 + 140  # 选择列 + 操作列
        available_width = table_width - fixed_width
        
        if available_width <= 0:
            return
        
        # 计算当前内容列的总宽度
        current_total = sum(self.result_table.columnWidth(col) for col in range(1, 7))
        
        # 如果总宽度不等于可用宽度，调整其他列
        if current_total != available_width:
            # 计算差值
            diff = available_width - current_total
            
            # 从其他列均匀调整
            other_cols = [col for col in range(1, 7) if col != logicalIndex]
            if other_cols:
                adjustment_per_col = diff / len(other_cols)
                for col in other_cols:
                    current_width = self.result_table.columnWidth(col)
                    new_width = max(50, int(current_width + adjustment_per_col))
                    self.result_table.setColumnWidth(col, new_width)
        
        # 更新该列的比例
        new_width = self.result_table.columnWidth(logicalIndex)
        if logicalIndex in self.column_width_ratios:
            self.column_width_ratios[logicalIndex] = new_width

    def adjust_table_columns(self):
        """根据窗口宽度调整表格列宽，保持表格宽度与窗口一致"""
        # 获取表格可用宽度（减去固定列）
        table_width = self.result_table.width()
        fixed_width = 50 + 140  # 选择列 + 操作列
        available_width = table_width - fixed_width
        
        if available_width <= 0:
            return
        
        # 计算当前内容列的总宽度
        current_total = sum(self.result_table.columnWidth(col) for col in range(1, 7))
        
        # 如果当前总宽度不等于可用宽度，需要调整
        if current_total != available_width:
            # 计算缩放因子
            if current_total > 0:
                scale_factor = available_width / current_total
                
                # 按比例调整每列宽度
                for col in range(1, 7):
                    current_width = self.result_table.columnWidth(col)
                    new_width = max(50, int(current_width * scale_factor))
                    self.result_table.setColumnWidth(col, new_width)

    def on_query(self):
        """查询按钮点击事件"""
        sn_text = self.sn_input.toPlainText().strip()
        id_text = self.id_input.toPlainText().strip()
        
        if not sn_text and not id_text:
            self.status_bar.showMessage("请输入SN/ID信息", 3000)
            return
        
        # 解析输入的SN/ID列表
        sn_list = [line.strip() for line in sn_text.split('\n') if line.strip()]
        id_list = [line.strip() for line in id_text.split('\n') if line.strip()]
        
        # 判断查询类型：优先使用上次的查询类型，避免重复查询
        # 如果上次是SN查询，这次只查询SN（即使ID框有自动填充的数据）
        # 如果上次是ID查询，这次只查询ID（即使SN框有自动填充的数据）
        if self.query_input_type == 'sn' and sn_list:
            # 上次是SN查询，继续只查询SN
            id_list = []
            self.query_input_list = sn_list
        elif self.query_input_type == 'id' and id_list:
            # 上次是ID查询，继续只查询ID
            sn_list = []
            self.query_input_list = id_list
        else:
            # 首次查询或两个框都清空后重新输入
            if sn_list and not id_list:
                self.query_input_type = 'sn'
                self.query_input_list = sn_list
            elif id_list and not sn_list:
                self.query_input_type = 'id'
                self.query_input_list = id_list
            else:
                # 两个都有输入，不做自动填充
                self.query_input_type = None
                self.query_input_list = []
        
        # 重置查询结果
        self.query_results = {}
        
        # 禁用所有按钮，防止重复操作
        self.query_btn.setEnabled(False)
        self.query_btn.setText("查询中...")
        self.clear_btn.setEnabled(False)
        self.batch_wake_btn.setEnabled(False)
        self.select_all_checkbox.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        
        # 禁用所有已存在的唤醒按钮
        for row in range(self.result_table.rowCount()):
            btn_container = self.result_table.cellWidget(row, 7)
            wake_btn = btn_container.findChild(QPushButton) if btn_container else None
            if wake_btn:
                wake_btn.setEnabled(False)
        
        # 重置计数
        self.total_count = len(sn_list) + len(id_list)
        self.online_count = 0
        self.offline_count = 0
        
        # 预先创建表格行（按输入顺序）
        self.result_table.setRowCount(self.total_count)
        for row in range(self.total_count):
            # 复选框
            checkbox = QCheckBox()
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.result_table.setCellWidget(row, 0, checkbox_widget)
            
            # 占位显示"查询中..."
            self.result_table.setItem(row, 1, QTableWidgetItem("查询中..."))
            for col in range(2, 7):
                self.result_table.setItem(row, col, QTableWidgetItem(""))
            
            # 唤醒按钮
            wake_btn = QPushButton("唤醒")
            wake_btn.setIcon(QIcon(":/icon/werk_up.png"))
            wake_btn.setIconSize(QSize(16, 16))  # 16x16 像素
            wake_btn.setFocusPolicy(Qt.NoFocus)  # 禁用焦点
            wake_btn.setEnabled(False)  # 查询时禁用唤醒按钮
            wake_btn.clicked.connect(lambda checked, r=row: self.on_wake_single(r))
            
            # 将按钮放在容器中并居中
            btn_container = QWidget()
            btn_layout = QHBoxLayout(btn_container)
            btn_layout.addStretch()
            btn_layout.addWidget(wake_btn)
            btn_layout.addStretch()
            btn_layout.setContentsMargins(0, 0, 0, 0)  # 无边距
            btn_layout.setSpacing(0)
            self.result_table.setCellWidget(row, 7, btn_container)
        
        # 在主线程中初始化 query
        try:
            query = DeviceQuery('pro', 'yinjia', 'Yjtest123456.')
        except Exception as e:
            self.query_btn.setEnabled(True)
            self.query_btn.setText("查询")
            QMessageBox.critical(self, "错误", f"初始化失败: {e}")
            return
        
        # 启动多线程查询
        self.query_thread = QueryThread(sn_list, id_list, query, max_workers=30)
        self.query_thread.single_result.connect(self.on_single_result)
        self.query_thread.all_done.connect(self.on_query_complete)
        self.query_thread.progress.connect(self.on_query_progress)
        self.query_thread.error.connect(self.on_query_error)
        self.query_thread.start()

    def on_single_result(self, row, item):
        """单个设备查询完成，立即更新表格"""
        # 存储查询结果
        self.query_results[row] = item
        
        self.result_table.setItem(row, 1, QTableWidgetItem(item['sn']))
        self.result_table.setItem(row, 2, QTableWidgetItem(item['id']))
        self.result_table.setItem(row, 3, QTableWidgetItem(item['password']))
        self.result_table.setItem(row, 4, QTableWidgetItem(str(item['node'])))
        self.result_table.setItem(row, 5, QTableWidgetItem(item['version']))
        
        # 在线状态
        online_status = item['online']
        if online_status == 1:
            status_text = "在线"
            status_color = Qt.green
            self.online_count += 1
        elif online_status == 0:
            status_text = "离线"
            status_color = Qt.red
            self.offline_count += 1
        elif online_status == -1:
            status_text = "未找到"
            status_color = Qt.gray
        else:
            status_text = "查询失败"
            status_color = Qt.darkYellow
        
        status_item = QTableWidgetItem(status_text)
        status_item.setForeground(status_color)
        self.result_table.setItem(row, 6, status_item)

    def on_query_progress(self, msg):
        """查询进度更新"""
        self.status_bar.showMessage(msg)

    def on_query_error(self, error_msg):
        """查询出错"""
        self.query_btn.setEnabled(True)
        self.query_btn.setText("查询")
        # 启用所有按钮
        self.clear_btn.setEnabled(True)
        self.batch_wake_btn.setEnabled(True)
        self.select_all_checkbox.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        
        # 启用所有唤醒按钮
        for row in range(self.result_table.rowCount()):
            btn_container = self.result_table.cellWidget(row, 7)
            wake_btn = btn_container.findChild(QPushButton) if btn_container else None
            if wake_btn:
                wake_btn.setEnabled(True)
        
        QMessageBox.critical(self, "错误", f"查询失败: {error_msg}")
        self.status_bar.showMessage("查询失败")

    def on_query_complete(self):
        """查询完成"""
        self.query_btn.setEnabled(True)
        self.query_btn.setText("查询")
        # 启用所有按钮
        self.clear_btn.setEnabled(True)
        self.batch_wake_btn.setEnabled(True)
        self.select_all_checkbox.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        
        # 启用所有唤醒按钮
        for row in range(self.result_table.rowCount()):
            btn_container = self.result_table.cellWidget(row, 7)
            wake_btn = btn_container.findChild(QPushButton) if btn_container else None
            if wake_btn:
                wake_btn.setEnabled(True)
        
        # 确保文本框可编辑
        self.sn_input.setEnabled(True)
        self.sn_input.setReadOnly(False)
        self.id_input.setEnabled(True)
        self.id_input.setReadOnly(False)
        
        # 填充对应的输入框
        if self.query_input_type == 'sn':
            # 输入的是SN，填充ID框
            id_results = []
            for input_sn in self.query_input_list:
                # 查找对应的结果
                found = False
                for row, result in self.query_results.items():
                    if result['sn'] == input_sn:
                        id_results.append(result['id'])
                        found = True
                        break
                if not found:
                    id_results.append("不存在")
            self.id_input.setPlainText('\n'.join(id_results))
        elif self.query_input_type == 'id':
            # 输入的是ID，填充SN框
            sn_results = []
            for input_id in self.query_input_list:
                # 查找对应的结果
                found = False
                for row, result in self.query_results.items():
                    if result['id'] == input_id:
                        sn_results.append(result['sn'])
                        found = True
                        break
                if not found:
                    sn_results.append("不存在")
            self.sn_input.setPlainText('\n'.join(sn_results))
        
        self.status_bar.showMessage(
            f"查询完成：共 {self.total_count} 台设备，在线 {self.online_count} 台，离线 {self.offline_count} 台"
        )

    def load_demo_data(self, sn_list, id_list):
        """加载演示数据（已弃用，保留兼容）"""
        pass

    def on_text_selection_changed(self):
        """文本选中状态改变时的处理"""
        # 计算SN输入框选中的行数
        sn_cursor = self.sn_input.textCursor()
        sn_selected_text = sn_cursor.selectedText()
        # selectedText() 使用 \u2029 作为段落分隔符，需要转换为 \n
        sn_selected_text = sn_selected_text.replace('\u2029', '\n')
        sn_lines = len([line for line in sn_selected_text.split('\n') if line.strip()]) if sn_selected_text else 0
        
        # 计算ID输入框选中的行数
        id_cursor = self.id_input.textCursor()
        id_selected_text = id_cursor.selectedText()
        # selectedText() 使用 \u2029 作为段落分隔符，需要转换为 \n
        id_selected_text = id_selected_text.replace('\u2029', '\n')
        id_lines = len([line for line in id_selected_text.split('\n') if line.strip()]) if id_selected_text else 0
        
        # 总选中行数
        total_lines = sn_lines + id_lines
        
        # 更新状态栏
        if total_lines > 0:
            self.status_bar.showMessage(f"已选中 {total_lines} 行数据")
        else:
            self.status_bar.showMessage("就绪")

    def on_clear(self):
        """清空按钮点击事件"""
        self.sn_input.clear()
        self.id_input.clear()
        self.result_table.setRowCount(0)
        self.select_all_checkbox.setChecked(False)
        # 重置查询类型
        self.query_input_type = None
        self.query_input_list = []
        self.query_results = {}
        self.status_bar.showMessage("清空完成", 2000)

    def on_wake_single(self, row):
        """单个设备唤醒"""
        sn = self.result_table.item(row, 1).text()
        dev_id = self.result_table.item(row, 2).text()
        
        if not sn or not dev_id:
            QMessageBox.warning(self, "提示", "设备信息不完整")
            return
        
        # 清除选中状态
        self.result_table.clearSelection()
        
        # 禁用查询和清空按钮
        self.query_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        
        # 获取按钮容器中的按钮
        btn_container = self.result_table.cellWidget(row, 7)
        wake_btn = None
        if btn_container:
            wake_btn = btn_container.findChild(QPushButton)
        
        if wake_btn:
            wake_btn.setText("唤醒中...")
            wake_btn.setEnabled(False)
        
        # 在后台线程中唤醒
        self.on_batch_wake_single(dev_id, sn, row, wake_btn)

    def update_device_count(self):
        """更新设备在线/离线统计"""
        total = 0
        online = 0
        offline = 0
        
        for row in range(self.result_table.rowCount()):
            status_item = self.result_table.item(row, 6)
            if status_item:
                status_text = status_item.text()
                if status_text in ["在线", "离线"]:
                    total += 1
                    if status_text == "在线":
                        online += 1
                    else:
                        offline += 1
        
        # 更新成员变量
        self.total_count = total
        self.online_count = online
        self.offline_count = offline
        
        # 更新状态栏
        if total > 0:
            self.status_bar.showMessage(
                f"共 {total} 台设备，在线 {online} 台，离线 {offline} 台"
            )

    def on_batch_wake_single(self, dev_id, sn, row, wake_btn):
        """唤醒单个设备（后台线程）"""
        def on_wake_done(name, success):
            # 恢复按钮状态
            if wake_btn:
                wake_btn.setText("唤醒")
                wake_btn.setEnabled(True)
            
            # 启用查询和清空按钮
            self.query_btn.setEnabled(True)
            self.clear_btn.setEnabled(True)
            
            # 更新在线状态
            if success:
                # 查询最新的在线状态
                try:
                    query = DeviceQuery('pro', 'yinjia', 'Yjtest123456.')
                    is_online = check_device_online(sn, query.token)
                    status_text = "在线" if is_online else "离线"
                    status_color = Qt.green if is_online else Qt.red
                    
                    status_item = QTableWidgetItem(status_text)
                    status_item.setForeground(status_color)
                    self.result_table.setItem(row, 6, status_item)
                    
                    # 更新设备统计
                    self.update_device_count()
                except:
                    pass
        
        def on_thread_finished():
            if thread in self.wake_threads:
                self.wake_threads.remove(thread)
        
        try:
            query = DeviceQuery('pro', 'yinjia', 'Yjtest123456.')
            thread = WakeThread([(dev_id, sn)], query, max_workers=1)
            thread.wake_result.connect(on_wake_done)
            thread.finished.connect(on_thread_finished)
            self.wake_threads.append(thread)
            thread.start()
        except Exception as e:
            if wake_btn:
                wake_btn.setText("唤醒")
                wake_btn.setEnabled(True)
            # 启用查询和清空按钮
            self.query_btn.setEnabled(True)
            self.clear_btn.setEnabled(True)

    def on_batch_wake(self):
        """批量唤醒"""
        selected_devices = []
        selected_rows = []
        for row in range(self.result_table.rowCount()):
            checkbox_widget = self.result_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox and checkbox.isChecked():
                sn = self.result_table.item(row, 1).text()
                dev_id = self.result_table.item(row, 2).text()
                if sn and dev_id:
                    selected_devices.append((dev_id, sn))
                    selected_rows.append(row)
        
        if not selected_devices:
            self.status_bar.showMessage("请先选择设备", 3000)
            return
        
        # 禁用所有操作按钮
        self.query_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.batch_wake_btn.setEnabled(False)
        self.batch_wake_btn.setText("唤醒中...")
        self.select_all_checkbox.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        
        # 将所有选中设备的唤醒按钮改为"唤醒中..."并禁用
        for row in selected_rows:
            btn_container = self.result_table.cellWidget(row, 7)
            wake_btn = btn_container.findChild(QPushButton) if btn_container else None
            if wake_btn:
                wake_btn.setText("唤醒中...")
                wake_btn.setEnabled(False)
        
        # 启动多线程唤醒
        try:
            query = DeviceQuery('pro', 'yinjia', 'Yjtest123456.')
            self.wake_thread = WakeThread(selected_devices, query, max_workers=30)
            self.wake_thread.wake_result.connect(lambda name, success: self.on_wake_result(name, success, selected_rows))
            self.wake_thread.all_done.connect(self.on_wake_complete)
            self.wake_thread.progress.connect(self.on_wake_progress)
            self.wake_thread.error.connect(self.on_wake_error)
            self.wake_thread.start()
        except Exception as e:
            self.batch_wake_btn.setEnabled(True)
            self.batch_wake_btn.setText("批量唤醒")
            # 启用所有按钮
            self.query_btn.setEnabled(True)
            self.clear_btn.setEnabled(True)
            self.select_all_checkbox.setEnabled(True)
            self.browse_btn.setEnabled(True)
            self.export_btn.setEnabled(True)
            # 恢复按钮状态
            for row in selected_rows:
                btn_container = self.result_table.cellWidget(row, 7)
                wake_btn = btn_container.findChild(QPushButton) if btn_container else None
                if wake_btn:
                    wake_btn.setText("唤醒")
                    wake_btn.setEnabled(True)
            QMessageBox.critical(self, "错误", f"初始化失败: {e}")

    def on_wake_result(self, device_name, success, selected_rows=None):
        """单个设备唤醒结果"""
        status = "✓ 成功" if success else "✗ 失败"
        
        # 更新在线状态
        if success and selected_rows:
            for row in selected_rows:
                sn = self.result_table.item(row, 1).text()
                if device_name.startswith(sn):
                    try:
                        query = DeviceQuery('pro', 'yinjia', 'Yjtest123456.')
                        is_online = check_device_online(sn, query.token)
                        status_text = "在线" if is_online else "离线"
                        status_color = Qt.green if is_online else Qt.red
                        
                        status_item = QTableWidgetItem(status_text)
                        status_item.setForeground(status_color)
                        self.result_table.setItem(row, 6, status_item)
                    except:
                        pass
                    break

    def on_wake_progress(self, msg):
        """唤醒进度更新"""
        self.status_bar.showMessage(msg)

    def on_wake_error(self, error_msg):
        """唤醒出错"""
        self.batch_wake_btn.setEnabled(True)
        self.batch_wake_btn.setText("批量唤醒")
        # 启用所有按钮
        self.query_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.select_all_checkbox.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        
        QMessageBox.critical(self, "错误", f"唤醒失败: {error_msg}")
        self.status_bar.showMessage("唤醒失败")

    def on_wake_complete(self):
        """唤醒完成"""
        self.batch_wake_btn.setEnabled(True)
        self.batch_wake_btn.setText("批量唤醒")
        # 启用所有按钮
        self.query_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.select_all_checkbox.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        
        # 恢复所有唤醒按钮状态
        for row in range(self.result_table.rowCount()):
            btn_container = self.result_table.cellWidget(row, 7)
            wake_btn = btn_container.findChild(QPushButton) if btn_container else None
            if wake_btn and wake_btn.text() == "唤醒中...":
                wake_btn.setText("唤醒")
                wake_btn.setEnabled(True)
        
        # 更新设备统计
        self.update_device_count()
        
        # 等待线程完成
        if self.wake_thread:
            self.wake_thread.wait()

    def on_select_all(self, state):
        """全选/取消全选"""
        for row in range(self.result_table.rowCount()):
            checkbox_widget = self.result_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox:
                checkbox.setChecked(state == Qt.Checked)

    def on_cell_double_clicked(self, row, column):
        """单元格双击事件，自动复制内容"""
        # 跳过选择列和操作列
        if column == 0 or column == 7:
            return
        
        # 获取单元格内容
        item = self.result_table.item(row, column)
        if item:
            text = item.text()
            if text and text != "查询中...":
                # 复制到剪贴板
                clipboard = QApplication.clipboard()
                clipboard.setText(text)
                self.status_bar.showMessage(f"已复制: {text}", 2000)

    def load_config(self):
        """从注册表加载配置"""
        try:
            export_path = get_registry_value(REGISTRY_PATH, 'export_path', '')
            if export_path:
                self.export_path = export_path
                self.export_path_input.setText(export_path)
        except Exception as e:
            print(f"加载配置失败: {e}")

    def save_config(self):
        """保存配置到注册表"""
        try:
            set_registry_value(REGISTRY_PATH, 'export_path', self.export_path)
        except Exception as e:
            print(f"保存配置失败: {e}")

    def on_browse_path(self):
        """浏览按钮点击事件"""
        # 选择目录而不是文件
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择保存目录",
            self.export_path if self.export_path else ""
        )
        if dir_path:
            self.export_path = dir_path
            self.export_path_input.setText(dir_path)
            # 保存配置
            self.save_config()

    def on_export_csv(self):
        """导出CSV按钮点击事件"""
        if not self.export_path:
            self.status_bar.showMessage("请先选择保存目录", 3000)
            return
        
        if self.result_table.rowCount() == 0:
            self.status_bar.showMessage("没有可导出的数据", 3000)
            return
        
        try:
            import csv
            from datetime import datetime
            
            # 生成带时间戳的文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"设备信息_{timestamp}.csv"
            file_path = os.path.join(self.export_path, file_name)
            
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                # 写入表头
                writer.writerow(['SN', 'ID', '密码', '版本号'])
                
                # 写入数据
                exported_count = 0
                for row in range(self.result_table.rowCount()):
                    sn_item = self.result_table.item(row, 1)
                    id_item = self.result_table.item(row, 2)
                    pwd_item = self.result_table.item(row, 3)
                    ver_item = self.result_table.item(row, 5)
                    
                    sn = sn_item.text() if sn_item else ''
                    dev_id = id_item.text() if id_item else ''
                    password = pwd_item.text() if pwd_item else ''
                    version = ver_item.text() if ver_item else ''
                    
                    # 跳过空行或查询中的行
                    if sn and sn != "查询中...":
                        writer.writerow([sn, dev_id, password, version])
                        exported_count += 1
            
            self.status_bar.showMessage(f"导出成功：{file_name}（共{exported_count}条数据）", 5000)
        except Exception as e:
            self.status_bar.showMessage(f"导出失败：{str(e)}", 5000)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
