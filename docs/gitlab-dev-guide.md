# GitLab 日志导出功能 - 开发者指南

## 概述

本文档面向开发者，详细说明 GitLab 日志导出功能的技术实现、架构设计和扩展方法。

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────┐
│         GitLabLogPage (页面层)          │
│  - UI 布局和交互                         │
│  - 用户输入处理                          │
│  - 状态管理                              │
└─────────────────┬───────────────────────┘
                  │
                  ├─────────────────────────┐
                  │                         │
         ┌────────▼────────┐      ┌────────▼────────┐
         │  GitLabAPI      │      │  ExcelHelper    │
         │  (API 层)       │      │  (工具层)       │
         │  - 网络请求     │      │  - Excel 生成   │
         │  - 数据解析     │      │  - 格式化       │
         └────────┬────────┘      └────────┬────────┘
                  │                         │
         ┌────────▼────────┐      ┌────────▼────────┐
         │  GitLab Server  │      │  Excel File     │
         │  (外部服务)     │      │  (输出文件)     │
         └─────────────────┘      └─────────────────┘
```

### 模块划分

#### 1. 页面层（pages/gitlab_log_page.py）

**职责：**
- UI 布局和控件管理
- 用户交互处理
- 状态管理和更新
- 线程协调

**关键类：**
- `GitLabLogPage` - 主页面类
- `GitLabWorkerThread` - 后台工作线程

#### 2. API 层（utils/gitlab_api.py）

**职责：**
- GitLab API 封装
- 网络请求处理
- 数据解析和转换
- 错误处理

**关键类：**
- `GitLabAPI` - API 封装类

#### 3. 工具层（utils/excel_helper.py）

**职责：**
- Excel 文件生成
- XML 结构构建
- 数据格式化
- 样式应用

**关键函数：**
- `create_gitlab_xlsx()` - 创建 Excel 文件

## 核心类详解

### GitLabLogPage 类

```python
@register_page("Git日志", order=3)
class GitLabLogPage(BasePage):
    """GitLab 日志导出页面"""
```

#### 继承关系

```
QWidget (PyQt5)
    └── BasePage (项目基类)
            └── GitLabLogPage (GitLab 页面)
```

#### 生命周期

```
创建 → 初始化UI → 加载配置 → 显示
  ↓
用户交互 ← → 后台线程
  ↓
保存配置 → 清理资源 → 销毁
```

#### 关键方法

| 方法 | 说明 | 调用时机 |
|------|------|---------|
| `__init__()` | 初始化 | 创建实例时 |
| `init_ui()` | 创建UI | 初始化时 |
| `on_page_show()` | 页面显示 | 切换到此页面时 |
| `load_config()` | 加载配置 | 初始化时 |
| `save_config()` | 保存配置 | 配置变更时 |
| `cleanup()` | 清理资源 | 页面关闭时 |

#### 状态管理

```python
# 连接状态
self.is_connected = False  # 是否已连接

# 数据状态
self.api = None            # API 实例
self.projects = []         # 项目列表
self.branches = []         # 分支列表
self.current_project = None  # 当前项目

# 配置状态
self.gitlab_server = ""    # 服务器地址
self.gitlab_token = ""     # Token
self.save_path = ""        # 保存路径
self.recent_projects = []  # 最近项目
self.recent_branches = {}  # 最近分支
```

### GitLabAPI 类

```python
class GitLabAPI:
    """GitLab API 封装"""
    
    def __init__(self, url, token):
        self.url = url.rstrip('/')
        self.token = token
        self.timeout = 10
```

#### API 方法

| 方法 | 端点 | 说明 |
|------|------|------|
| `get_all_projects()` | `/api/v4/projects` | 获取所有项目 |
| `get_branches()` | `/api/v4/projects/{id}/repository/branches` | 获取分支列表 |
| `get_commits()` | `/api/v4/projects/{id}/repository/commits` | 获取提交记录 |
| `get_commit_diff()` | `/api/v4/projects/{id}/repository/commits/{sha}/diff` | 获取文件差异 |

#### 请求流程

```
构建请求 → 发送请求 → 检查状态码 → 解析响应 → 返回数据
    ↓           ↓           ↓           ↓           ↓
  Headers   Timeout    200 OK?     JSON        List/Dict
                         ↓ No
                    抛出异常
```

#### 错误处理

```python
try:
    response = requests.get(url, headers=headers, timeout=self.timeout)
    if response.status_code != 200:
        raise Exception(f"API 错误 ({response.status_code})")
    return response.json()
except requests.exceptions.Timeout:
    raise Exception("请求超时")
except requests.exceptions.ConnectionError:
    raise Exception("无法连接到服务器")
```

### GitLabWorkerThread 类

```python
class GitLabWorkerThread(QThread):
    """GitLab 后台工作线程"""
    
    finished_signal = pyqtSignal(object)
    error_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(str)
```

#### 信号机制

```
主线程                后台线程
  │                      │
  ├─ start() ──────────→ run()
  │                      │
  │                   执行任务
  │                      │
  │  ←─ progress_signal ─┤ (进度更新)
  │                      │
  │  ←─ finished_signal ─┤ (成功完成)
  │     或                │
  │  ←─ error_signal ────┤ (失败)
  │                      │
  └─ 处理结果            结束
```

## 数据流程

### 连接流程

```
用户点击"连接"
    ↓
验证输入（服务器地址、Token）
    ↓
创建 GitLabAPI 实例
    ↓
启动后台线程获取项目列表
    ↓
    ├─ 成功 → 填充项目下拉框 → 更新按钮状态 → 保存配置
    │
    └─ 失败 → 显示错误消息 → 恢复按钮状态
```

### 查询流程

```
用户选择项目
    ↓
启动后台线程获取分支列表
    ↓
    ├─ 成功 → 填充分支下拉框
    │            ↓
    │         启动后台线程获取提交者列表
    │            ↓
    │            ├─ 成功 → 填充提交者下拉框
    │            └─ 失败 → 显示警告（不影响主流程）
    │
    └─ 失败 → 显示错误消息
```

### 导出流程

```
用户点击"导出"
    ↓
验证输入（项目、分支、保存路径）
    ↓
生成文件名（自动添加序号避免覆盖）
    ↓
启动后台线程执行导出
    ↓
获取提交记录
    ↓
按提交者筛选（可选）
    ↓
获取每个提交的文件差异
    ↓
创建 Excel 文件
    ↓
    ├─ 成功 → 显示成功消息 → 保存最近记录
    │
    └─ 失败 → 显示错误消息
```

## 配置管理

### 注册表结构

```
HKEY_CURRENT_USER\Software\TPQueryTool\GitLab
├── server (REG_SZ)              # 服务器地址
├── token (REG_SZ)               # Token（Base64加密）
├── save_path (REG_SZ)           # 保存路径
├── recent_projects (REG_SZ)     # 最近项目（JSON）
└── recent_branches (REG_SZ)     # 最近分支（JSON）
```

### 配置读写

#### 读取配置

```python
import winreg
import base64
import json

# 打开注册表键
reg_key = winreg.OpenKey(
    winreg.HKEY_CURRENT_USER,
    r"Software\TPQueryTool\GitLab",
    0,
    winreg.KEY_READ
)

# 读取服务器地址
server, _ = winreg.QueryValueEx(reg_key, "server")

# 读取 Token（解密）
token_encoded, _ = winreg.QueryValueEx(reg_key, "token")
token = base64.b64decode(token_encoded.encode()).decode()

# 读取最近项目（JSON）
recent_projects_str, _ = winreg.QueryValueEx(reg_key, "recent_projects")
recent_projects = json.loads(recent_projects_str)

winreg.CloseKey(reg_key)
```

#### 保存配置

```python
import winreg
import base64
import json

# 创建注册表键
reg_key = winreg.CreateKey(
    winreg.HKEY_CURRENT_USER,
    r"Software\TPQueryTool\GitLab"
)

# 保存服务器地址
winreg.SetValueEx(reg_key, "server", 0, winreg.REG_SZ, server)

# 保存 Token（加密）
token_encoded = base64.b64encode(token.encode()).decode()
winreg.SetValueEx(reg_key, "token", 0, winreg.REG_SZ, token_encoded)

# 保存最近项目（JSON）
recent_projects_str = json.dumps(recent_projects[:6])
winreg.SetValueEx(reg_key, "recent_projects", 0, winreg.REG_SZ, recent_projects_str)

winreg.CloseKey(reg_key)
```

## Excel 生成

### 文件结构

```
Excel 文件 (.xlsx)
├── [Content_Types].xml          # 内容类型定义
├── _rels/.rels                  # 关系定义
├── xl/
│   ├── workbook.xml            # 工作簿
│   ├── styles.xml              # 样式
│   ├── sharedStrings.xml       # 共享字符串
│   ├── worksheets/
│   │   ├── sheet1.xml          # 工作表
│   │   └── _rels/
│   │       └── sheet1.xml.rels # 超链接关系
│   └── _rels/
│       └── workbook.xml.rels   # 工作簿关系
```

### 样式定义

```xml
<cellXfs count="4">
  <!-- 样式0: 普通单元格 -->
  <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
  
  <!-- 样式1: 超链接（蓝色下划线） -->
  <xf numFmtId="0" fontId="1" fillId="0" borderId="0"/>
  
  <!-- 样式2: 高亮单元格（蓝色背景+边框） -->
  <xf numFmtId="0" fontId="0" fillId="2" borderId="1"/>
  
  <!-- 样式3: 高亮超链接（蓝色背景+边框+超链接） -->
  <xf numFmtId="0" fontId="1" fillId="2" borderId="1"/>
</cellXfs>
```

### 数据填充

```python
# 遍历提交记录
for row_idx, commit in enumerate(commits, start=1):
    # 创建行
    row_elem = ET.SubElement(sheet_data, 'row')
    row_elem.set('r', str(row_idx))
    
    # 选择样式（是否高亮）
    style = '2' if highlight else '0'
    style_link = '3' if highlight else '1'
    
    # 添加单元格（提交ID，带超链接）
    cell = ET.SubElement(row_elem, 'c')
    cell.set('r', f'A{row_idx}')
    cell.set('t', 's')  # 字符串类型
    cell.set('s', style_link)  # 应用样式
    
    # 添加超链接
    hyperlink = ET.SubElement(hyperlinks, 'hyperlink')
    hyperlink.set('ref', f'A{row_idx}')
    hyperlink.set('r:id', f'rId{row_idx}')
```

## 扩展开发

### 添加新的查询条件

1. **在 UI 中添加控件**

```python
def create_query_area(self, parent_layout):
    # ... 现有代码 ...
    
    # 添加新的筛选条件
    filter_layout = QHBoxLayout()
    filter_label = QLabel("新筛选:")
    filter_label.setFixedWidth(70)
    self.filter_combo = QComboBox()
    filter_layout.addWidget(filter_label)
    filter_layout.addWidget(self.filter_combo, 1)
    layout.addLayout(filter_layout)
```

2. **在导出时应用筛选**

```python
def do_export(self, ...):
    commits = self.api.get_commits(...)
    
    # 应用新的筛选条件
    filter_value = self.filter_combo.currentData()
    if filter_value:
        commits = [c for c in commits if c.get('field') == filter_value]
    
    # ... 继续处理 ...
```

### 添加新的导出格式

1. **创建导出函数**

```python
# utils/csv_helper.py
def create_gitlab_csv(commits, output_path):
    """导出为 CSV 格式"""
    import csv
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['提交ID', '提交消息', '提交者', '提交时间'])
        
        for commit in commits:
            writer.writerow([
                commit['short_id'],
                commit['message'],
                commit.get('author_name', ''),
                commit['committed_date'][:19]
            ])
```

2. **在页面中添加选项**

```python
# 添加格式选择
self.format_combo = QComboBox()
self.format_combo.addItem("Excel (.xlsx)", "xlsx")
self.format_combo.addItem("CSV (.csv)", "csv")

# 导出时根据格式选择
def do_export(self, ...):
    format_type = self.format_combo.currentData()
    
    if format_type == "xlsx":
        create_gitlab_xlsx(commits, save_path, keyword)
    elif format_type == "csv":
        create_gitlab_csv(commits, save_path)
```

### 添加统计功能

```python
def analyze_commits(self, commits):
    """分析提交统计"""
    stats = {
        'total': len(commits),
        'authors': {},
        'files': {}
    }
    
    for commit in commits:
        # 统计提交者
        author = commit.get('author_name', 'Unknown')
        stats['authors'][author] = stats['authors'].get(author, 0) + 1
        
        # 统计文件
        files = commit.get('files_changed', '').split('\n')
        for file in files:
            if file:
                stats['files'][file] = stats['files'].get(file, 0) + 1
    
    return stats
```

## 性能优化

### 1. 分页加载

```python
def get_all_projects(self):
    """分页获取所有项目"""
    projects = []
    page = 1
    
    while True:
        # 每页100条
        data = self.api_get('/projects', {
            'per_page': 100,
            'page': page
        })
        
        if not data:
            break
        
        projects.extend(data)
        page += 1
    
    return projects
```

### 2. 并发请求

```python
from concurrent.futures import ThreadPoolExecutor

def get_commits_parallel(self, project_paths):
    """并发获取多个项目的提交"""
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(self.api.get_commits, path, since, until): path
            for path in project_paths
        }
        
        results = {}
        for future in futures:
            path = futures[future]
            try:
                results[path] = future.result()
            except Exception as e:
                results[path] = []
        
        return results
```

### 3. 缓存机制

```python
class GitLabAPI:
    def __init__(self, url, token):
        # ... 现有代码 ...
        self._cache = {}
    
    def get_branches(self, project_path):
        """获取分支列表（带缓存）"""
        cache_key = f"branches:{project_path}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        branches = self._get_branches_from_api(project_path)
        self._cache[cache_key] = branches
        
        return branches
```

## 调试技巧

### 1. 日志输出

```python
import logging

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# 在关键位置添加日志
logger.debug(f"连接服务器: {server}")
logger.info(f"获取到 {len(projects)} 个项目")
logger.error(f"请求失败: {error}")
```

### 2. 异常捕获

```python
try:
    result = self.api.get_commits(...)
except Exception as e:
    import traceback
    logger.error(f"获取提交失败: {e}")
    logger.debug(traceback.format_exc())
    raise
```

### 3. 性能分析

```python
import time

def measure_time(func):
    """装饰器：测量函数执行时间"""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} 耗时: {end - start:.2f}秒")
        return result
    return wrapper

@measure_time
def get_all_projects(self):
    # ... 实现 ...
```

## 测试

### 单元测试

```python
import unittest
from utils.gitlab_api import GitLabAPI

class TestGitLabAPI(unittest.TestCase):
    def setUp(self):
        self.api = GitLabAPI("https://gitlab.example.com", "test-token")
    
    def test_api_get(self):
        """测试 API 请求"""
        # Mock 请求
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = [{'id': 1}]
            
            result = self.api.api_get('/projects')
            self.assertEqual(len(result), 1)
    
    def test_error_handling(self):
        """测试错误处理"""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout()
            
            with self.assertRaises(Exception) as context:
                self.api.api_get('/projects')
            
            self.assertIn("超时", str(context.exception))
```

### 集成测试

```python
def test_full_export_flow():
    """测试完整导出流程"""
    # 1. 创建页面
    page = GitLabLogPage()
    
    # 2. 设置配置
    page.server_input.setText("https://gitlab.example.com")
    page.token_input.setText("test-token")
    
    # 3. 连接服务器
    page.on_connect()
    
    # 4. 等待连接完成
    # ... 使用 QTest 等待信号 ...
    
    # 5. 选择项目和分支
    page.project_combo.setCurrentIndex(0)
    page.branch_combo.setCurrentIndex(0)
    
    # 6. 导出
    page.on_export()
    
    # 7. 验证结果
    assert os.path.exists(output_file)
```

## 常见问题

### Q: 如何添加新的 GitLab API？

A: 在 `GitLabAPI` 类中添加新方法：

```python
def get_merge_requests(self, project_path):
    """获取合并请求列表"""
    encoded = urllib.parse.quote(project_path, safe='')
    return self.api_get(f'/projects/{encoded}/merge_requests')
```

### Q: 如何修改 Excel 样式？

A: 修改 `utils/excel_helper.py` 中的 `styles` XML：

```python
styles = '''
<styleSheet>
  <fonts count="2">
    <font><sz val="11"/><name val="Calibri"/></font>
    <font><sz val="11"/><color rgb="FFFF0000"/><b/></font>  <!-- 红色加粗 -->
  </fonts>
  <!-- ... -->
</styleSheet>
'''
```

### Q: 如何添加进度条？

A: 使用 `progress_signal` 信号：

```python
# 在 Worker 线程中
for idx, commit in enumerate(commits):
    # 处理提交
    # ...
    
    # 发送进度
    progress = int((idx + 1) / len(commits) * 100)
    self.progress_signal.emit(f"处理中: {progress}%")
```

## 总结

GitLab 日志导出功能采用了清晰的分层架构和模块化设计，易于理解和扩展。关键点：

- ✅ 页面层负责 UI 和交互
- ✅ API 层负责数据获取
- ✅ 工具层负责数据处理
- ✅ 使用后台线程避免阻塞
- ✅ 完善的错误处理
- ✅ 灵活的配置管理

开发者可以基于现有架构轻松添加新功能和优化性能。
