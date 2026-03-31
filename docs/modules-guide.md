# 重构模块使用指南

## 📚 概述

本文档介绍如何使用已完成的重构模块，包括工具模块（utils/）和自定义控件模块（widgets/）。

## 🛠️ 工具模块（utils/）

### 1. 配置管理器（config.py）

#### 基本使用
```python
from query_tool.utils import config_manager, get_account_config, save_account_config

# 方式1：使用配置管理器（推荐）
account_config = config_manager.load_account_config()
print(account_config.username)
print(account_config.password)

# 修改配置
account_config.username = "new_user"
config_manager.save_account_config(account_config)

# 方式2：使用向后兼容函数
env, username, password = get_account_config()
save_account_config('pro', 'user', 'pass')
```

#### 应用配置
```python
# 加载应用配置
app_config = config_manager.load_app_config()
print(app_config.export_path)
print(app_config.phone_history)
print(app_config.last_page_index)
print(app_config.theme)  # 'dark' 或 'light'

# 保存应用配置
app_config.export_path = "C:/exports"
app_config.phone_history.append("13800138000")
app_config.theme = 'light'
config_manager.save_app_config(app_config)
```

### 2. 设备查询API（device_query.py）

#### 基本查询
```python
from query_tool.utils import DeviceQuery, wake_device_smart, check_device_online

# 初始化查询对象
query = DeviceQuery('pro', 'username', 'password')

# 检查初始化是否成功
if query.init_error:
    print(f"初始化失败: {query.init_error}")
else:
    # 查询设备信息
    info = query.get_device_info(dev_sn="SN123456")
    
    # 获取设备密码
    password = query.get_cloud_password(dev_id="12345")
    
    # 获取设备版本
    version = query.get_device_version(dev_id="12345")
    
    # 获取设备名称
    name = query.get_device_name(dev_id="12345")
```

#### 设备唤醒
```python
# 智能唤醒（推荐）
success = wake_device_smart(
    dev_id="12345",
    sn="SN123456",
    token=query.token,
    max_times=3
)

# 检查在线状态
is_online = check_device_online("SN123456", query.token)
```

### 3. 按钮管理器（button_manager.py）

#### 创建按钮组
```python
from query_tool.utils import ButtonManager

# 创建按钮管理器
self.btn_manager = ButtonManager()

# 创建主按钮组
self.main_buttons = self.btn_manager.create_group("main")
self.main_buttons.add(
    self.query_btn,
    self.clear_btn,
    self.batch_wake_btn,
    self.select_all_checkbox,
    self.export_btn
)

# 创建唤醒按钮组
self.wake_buttons = self.btn_manager.create_group("wake")
self.wake_buttons.add(self.wake_btn1, self.wake_btn2)
```

#### 使用按钮组
```python
# 禁用所有按钮
self.main_buttons.disable()

# 禁用并显示加载文本
self.main_buttons.disable("查询中...")

# 启用所有按钮
self.main_buttons.enable()

# 设置单个按钮文本
self.main_buttons.set_text(self.query_btn, "重新查询")
```

### 4. 消息管理器（message_manager.py）

#### 创建消息管理器
```python
from query_tool.utils import MessageManager, MessageType

# 创建消息管理器
self.msg = MessageManager(self.status_bar)
```

#### 显示不同类型的消息
```python
# 普通信息（默认2秒）
self.msg.info("就绪")

# 成功消息（默认3秒）
self.msg.success("查询完成")
self.msg.success(f"导出成功：{filename}")

# 警告消息（默认3秒）
self.msg.warning("请输入账号")
self.msg.warning("设备信息不完整")

# 错误消息（默认5秒）
self.msg.error("查询失败")
self.msg.error(f"查询失败: {error_msg}")

# 进度消息（不自动消失）
self.msg.progress("查询进度: 10/100")
self.msg.progress(f"唤醒进度: {completed}/{total}")

# 自定义显示时长
self.msg.info("自定义消息", duration=5000)  # 5秒

# 清空消息
self.msg.clear()
```

### 5. 样式管理器（style_manager.py / theme_manager.py）

项目使用双层主题架构：
- `theme_manager.py` — 只管颜色 Token（深色/浅色两套），职责单一
- `style_manager.py` — 所有 QSS 字符串生成的唯一入口，新增控件只需在这里加方法

#### 应用样式（推荐方式）
```python
from query_tool.utils import StyleManager

# 应用预定义样式（推荐）
StyleManager.apply(self.result_table, "TABLE")
StyleManager.apply(self.splitter, "SPLITTER")
StyleManager.apply(self.frame, "QUERY_FRAME")
StyleManager.apply(self.btn, "ACTION_BUTTON")

# 向后兼容写法（等同于 apply）
StyleManager.apply_to_widget(self.result_table, "TABLE")
```

#### 可用样式列表
| 样式名 | 适用控件 |
|--------|---------|
| `MENU_BUTTON` | 菜单按钮 |
| `SETTINGS_BUTTON` | 设置/图标按钮 |
| `MENU_BAR` | 顶部菜单栏容器 |
| `TABLE` | QTableWidget |
| `SPLITTER` | QSplitter |
| `PLAINTEXT_EDIT_TABLE` | QPlainTextEdit（表格风格）|
| `VERSION_LABEL` | 版本标签 |
| `COMBOBOX` | QComboBox |
| `TAB_WIDGET` | QTabWidget |
| `GROUP_BOX` | QGroupBox |
| `SCROLL_AREA` | QScrollArea |
| `ACTION_BUTTON` | 操作按钮（确认/取消等）|
| `QUERY_FRAME` | 带边框的查询条件容器 |
| `READONLY_INPUT` | 只读输入框 |
| `PROGRESS_BAR` | QProgressBar |
| `CONTEXT_MENU` | 右键菜单 |
| `COMBO_LINE_EDIT_ACTIVE` | ComboBox 内嵌 LineEdit（激活态）|
| `COMBO_LINE_EDIT_INACTIVE` | ComboBox 内嵌 LineEdit（未激活态）|

#### 获取颜色 Token
```python
from query_tool.utils.theme_manager import t

# 在 f-string 里直接使用
label.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px;")
separator.setStyleSheet(f"QFrame {{ background-color: {t('border')}; }}")

# 常用 Token
# t('bg_dark')       最深背景
# t('bg_mid')        中间背景
# t('bg_light')      较浅背景（输入框）
# t('text_primary')  主文字色
# t('text_hint')     提示文字色
# t('text_disabled') 禁用文字色
# t('border')        边框色
# t('accent')        强调色（青绿）
# t('status_online') 在线状态色
# t('status_offline')离线状态色
# t('status_pending')进行中状态色
# t('status_info')   信息蓝色
```

#### 新增控件样式（只需改 style_manager.py 一个文件）
```python
# 在 StyleManager 类里加一个 get_XXX 方法即可
@classmethod
def get_MY_WIDGET(cls) -> str:
    return f"""
    QWidget {{
        background-color: {t('bg_light')};
        color: {t('text_primary')};
        border: 1px solid {t('border')};
    }}
    """

# 使用
StyleManager.apply(my_widget, "MY_WIDGET")
```

#### ThemedWidget Mixin（自定义控件自动响应主题切换）
```python
from query_tool.utils.style_manager import ThemedWidget, StyleManager

class MyDialog(QDialog, ThemedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        ThemedWidget.__init__(self)  # 注册主题监听，控件销毁时自动断开
        self._init_ui()

    def _init_ui(self):
        self.table = QTableWidget()
        StyleManager.apply(self.table, "TABLE")
        self.frame = QFrame()
        StyleManager.apply(self.frame, "QUERY_FRAME")

    def refresh_theme(self):
        """主题切换时自动调用"""
        StyleManager.apply(self.table, "TABLE")
        StyleManager.apply(self.frame, "QUERY_FRAME")
```

#### 主题切换
```python
from query_tool.utils.theme_manager import theme_manager

# 切换主题（会自动触发所有注册了监听的控件刷新）
theme_manager.toggle()
theme_manager.set_dark()
theme_manager.set_light()

# 查询当前主题
if theme_manager.is_dark:
    print("当前是深色模式")
```

### 6. 表格工具（table_helper.py）

#### 双击复制功能
```python
from query_tool.utils import TableHelper

# 设置双击复制（推荐）
TableHelper.setup_copy_on_double_click(
    self.result_table,
    status_callback=self.msg.info,  # 消息回调
    skip_columns=[0, 9]  # 跳过选择列和操作列
)

# 或者手动连接
self.result_table.cellDoubleClicked.connect(
    lambda row, col: TableHelper.copy_cell_on_double_click(
        self.result_table, row, col, self.msg.info, [0, 9]
    )
)
```

#### 列宽自动调整
```python
# 按比例调整列宽
TableHelper.adjust_columns_proportionally(
    self.result_table,
    fixed_columns={0: 50, 9: 140},  # 固定列配置
    available_width=self.result_table.width()
)

# 在窗口resize事件中调用
def resizeEvent(self, event):
    super().resizeEvent(event)
    TableHelper.adjust_columns_proportionally(
        self.result_table,
        fixed_columns={0: 50, 9: 140},
        available_width=self.result_table.width()
    )
```

#### 导出CSV
```python
# 导出表格到CSV
try:
    count = TableHelper.export_to_csv(
        self.result_table,
        file_path="export.csv",
        columns={
            1: "设备名称",
            2: "SN",
            3: "ID",
            4: "密码"
        },
        skip_text=["查询中...", ""]
    )
    self.msg.success(f"导出成功：共{count}条数据")
except Exception as e:
    self.msg.error(f"导出失败：{str(e)}")
```

### 7. 线程管理器（thread_manager.py）

#### 创建线程管理器
```python
from query_tool.utils import ThreadManager
from query_tool.utils.workers import QueryThread, WakeThread

# 创建线程管理器
self.thread_mgr = ThreadManager()
```

#### 管理查询线程
```python
# 创建并添加查询线程
query_thread = QueryThread(sn_list, id_list, env, username, password)
query_thread.single_result.connect(self.on_single_result)
query_thread.all_done.connect(self.on_query_complete)
query_thread.progress.connect(self.msg.progress)
query_thread.error.connect(self.msg.error)

# 添加到管理器
self.thread_mgr.add("query", query_thread)
query_thread.start()

# 停止线程
self.thread_mgr.stop("query")

# 获取线程
thread = self.thread_mgr.get("query")
```

#### 管理多个线程
```python
# 添加多个线程
self.thread_mgr.add("query", query_thread)
self.thread_mgr.add("wake", wake_thread)
self.thread_mgr.add("phone_query", phone_query_thread)

# 停止所有线程
self.thread_mgr.stop_all()

# 清理已完成的线程
self.thread_mgr.cleanup_all()
```

#### 在窗口关闭时清理
```python
def closeEvent(self, event):
    """窗口关闭事件"""
    # 停止所有线程
    self.thread_mgr.stop_all(wait_ms=1000)
    event.accept()
```

### 8. 多线程Worker（workers.py）

#### 查询线程
```python
from query_tool.utils.workers import QueryThread

# 创建查询线程
query_thread = QueryThread(
    sn_list=['SN001', 'SN002'],
    id_list=['ID001', 'ID002'],
    env='pro',
    username='user',
    password='pass',
    max_workers=30
)

# 连接信号
query_thread.init_success.connect(self.on_query_init_success)
query_thread.single_result.connect(self.on_single_result)
query_thread.all_done.connect(self.on_query_complete)
query_thread.progress.connect(self.on_query_progress)
query_thread.error.connect(self.on_query_error)

# 启动线程
query_thread.start()

# 停止线程
query_thread.stop()
```

#### 唤醒线程
```python
from query_tool.utils.workers import WakeThread

# 创建唤醒线程
wake_thread = WakeThread(
    devices=[('dev_id1', 'sn1'), ('dev_id2', 'sn2')],
    query=query_object,  # 已初始化的DeviceQuery对象
    max_workers=30
)

# 连接信号
wake_thread.wake_result.connect(self.on_wake_result)
wake_thread.all_done.connect(self.on_wake_complete)
wake_thread.progress.connect(self.on_wake_progress)
wake_thread.error.connect(self.on_wake_error)

# 启动线程
wake_thread.start()
```

#### 账号查询线程
```python
from query_tool.utils.workers import PhoneQueryThread

# 创建账号查询线程
phone_query_thread = PhoneQueryThread(
    phone='13800138000',
    env='pro',
    username='user',
    password='pass'
)

# 连接信号
phone_query_thread.progress.connect(self.on_phone_query_progress)
phone_query_thread.error.connect(self.on_phone_query_error)
phone_query_thread.success.connect(self.on_phone_query_success)

# 启动线程
phone_query_thread.start()
```

## 🎨 自定义控件模块（widgets/）

### 1. ClickableLabel（可点击标签）

```python
from query_tool.widgets import ClickableLabel

# 创建可点击标签
self.version_label = ClickableLabel("  ")
self.version_label.setStyleSheet("color: gray;")

# 设置点击回调
self.version_label.clicked = self.on_version_clicked

def on_version_clicked(self):
    """版本标签点击事件"""
    self.version_label.setText(get_version_string())
    # 1秒后隐藏
    QTimer.singleShot(1000, lambda: self.version_label.setText("  "))
```

### 2. PlainTextEdit（纯文本输入框）

```python
from query_tool.widgets import PlainTextEdit

# 创建纯文本输入框
self.sn_input = PlainTextEdit()
self.sn_input.setPlaceholderText("请输入设备SN，每行一个...")

# 粘贴时自动清除格式
# 无需额外代码，控件自动处理
```

### 3. ClickableLineEdit（可双击打开目录）

```python
from query_tool.widgets import ClickableLineEdit

# 创建可双击打开目录的输入框
self.export_path_input = ClickableLineEdit()
self.export_path_input.setPlaceholderText("双击可打开目录...")
self.export_path_input.setReadOnly(True)

# 设置路径
self.export_path_input.setText("C:/exports")

# 双击自动打开目录
# 无需额外代码，控件自动处理
```

### 4. SettingsDialog（设置对话框）

```python
from query_tool.widgets import SettingsDialog

# 打开设置对话框
def on_settings_clicked(self):
    dialog = SettingsDialog(self)
    if dialog.exec_() == QDialog.Accepted:
        # 用户点击了保存
        print("配置已保存")
```

## 📝 完整示例

### 示例1：简化的查询功能

```python
from PyQt5.QtWidgets import QMainWindow, QPushButton, QTableWidget, QStatusBar
from query_tool.utils import (
    ButtonManager, MessageManager, ThreadManager,
    get_account_config, TableHelper
)
from query_tool.utils.workers import QueryThread

class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 创建管理器
        self.btn_manager = ButtonManager()
        self.msg = MessageManager(self.statusBar())
        self.thread_mgr = ThreadManager()
        
        # 创建按钮组
        self.main_buttons = self.btn_manager.create_group("main")
        self.main_buttons.add(self.query_btn, self.clear_btn)
        
        # 设置表格双击复制
        TableHelper.setup_copy_on_double_click(
            self.result_table,
            status_callback=self.msg.info,
            skip_columns=[0]
        )
    
    def on_query(self):
        """查询按钮点击"""
        # 禁用按钮
        self.main_buttons.disable("查询中...")
        
        # 获取配置
        env, username, password = get_account_config()
        
        # 创建查询线程
        query_thread = QueryThread(
            sn_list=['SN001'],
            id_list=[],
            env=env,
            username=username,
            password=password
        )
        
        # 连接信号
        query_thread.single_result.connect(self.on_single_result)
        query_thread.all_done.connect(self.on_query_complete)
        query_thread.progress.connect(self.msg.progress)
        query_thread.error.connect(self.msg.error)
        
        # 添加到管理器并启动
        self.thread_mgr.add("query", query_thread)
        query_thread.start()
    
    def on_query_complete(self):
        """查询完成"""
        self.main_buttons.enable()
        self.msg.success("查询完成")
    
    def closeEvent(self, event):
        """窗口关闭"""
        self.thread_mgr.stop_all()
        event.accept()
```

### 示例2：简化的导出功能

```python
from PyQt5.QtWidgets import QFileDialog
from query_tool.utils import TableHelper, MessageManager
from datetime import datetime

class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.msg = MessageManager(self.statusBar())
    
    def on_export_csv(self):
        """导出CSV"""
        if self.result_table.rowCount() == 0:
            self.msg.warning("没有可导出的数据")
            return
        
        # 生成默认文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"设备信息_{timestamp}.csv"
        
        # 选择保存位置
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存CSV文件",
            default_filename,
            "CSV文件 (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            # 导出
            count = TableHelper.export_to_csv(
                self.result_table,
                file_path=file_path,
                columns={
                    1: "设备名称",
                    2: "SN",
                    3: "ID",
                    4: "密码"
                },
                skip_text=["查询中..."]
            )
            
            filename = os.path.basename(file_path)
            self.msg.success(f"导出成功：{filename}（共{count}条数据）")
        except Exception as e:
            self.msg.error(f"导出失败：{str(e)}")
```

## 🎯 最佳实践

### 1. 统一使用管理器
```python
# ✅ 推荐
self.main_buttons.disable("查询中...")
self.msg.success("查询完成")

# ❌ 不推荐
self.query_btn.setEnabled(False)
self.query_btn.setText("查询中...")
self.status_bar.showMessage("✓ 查询完成", 3000)
```

### 2. 统一使用样式管理器
```python
# ✅ 推荐
StyleManager.apply_to_widget(self.menu_btn, "MENU_BUTTON")

# ❌ 不推荐
self.menu_btn.setStyleSheet("""
    QPushButton {
        border: none;
        ...
    }
""")
```

### 3. 统一使用线程管理器
```python
# ✅ 推荐
self.thread_mgr.add("query", query_thread)
self.thread_mgr.stop_all()

# ❌ 不推荐
self.query_thread = query_thread
if self.query_thread and self.query_thread.isRunning():
    self.query_thread.stop()
    self.query_thread.wait()
```

### 4. 统一使用表格工具
```python
# ✅ 推荐
TableHelper.setup_copy_on_double_click(
    self.result_table,
    status_callback=self.msg.info,
    skip_columns=[0, 9]
)

# ❌ 不推荐
def on_cell_double_clicked(self, row, column):
    if column == 0 or column == 9:
        return
    item = self.result_table.item(row, column)
    if item:
        text = item.text()
        ...
```

## 📚 参考资料

- [代码重构说明.md](./代码重构说明.md) - 详细的重构说明
- [重构进度报告.md](./重构进度报告.md) - 当前进度报告
- [Python Type Hints](https://docs.python.org/3/library/typing.html) - 类型提示文档
- [PyQt5 Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt5/) - PyQt5官方文档

---

*文档创建时间：2025-01-21*
*版本：v1.0*
