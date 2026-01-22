# 程序启动速度优化方案

## 当前启动流程分析

### 启动时间瓶颈（预估）

| 阶段 | 耗时 | 原因 |
|------|------|------|
| Python 解释器启动 | ~500ms | 系统级别 |
| 导入 PyQt5 | ~800ms | 大型 GUI 框架 |
| 导入 requests | ~200ms | 网络库 |
| 导入 ddddocr | ~1500-2000ms | **重型 OCR 库** |
| 导入其他模块 | ~300ms | 配置、工具等 |
| UI 初始化 | ~400ms | 创建窗口、按钮等 |
| 页面注册 | ~200ms | 3 个页面的初始化 |
| **总计** | **~4000-4500ms** | **4-4.5 秒** |

### 主要瓶颈

1. **ddddocr 导入** (~1500-2000ms)
   - 位置: `query_tool/utils/device_query.py` 第 10 行
   - 原因: 加载 ONNX 模型和 CV2 依赖
   - 使用频率: 仅在登录时使用一次

2. **PyQt5 导入** (~800ms)
   - 位置: `query_tool/main.py` 第 12-16 行
   - 原因: 大型 GUI 框架
   - 无法优化（必需）

3. **requests 导入** (~200ms)
   - 位置: `query_tool/main.py` 第 18 行
   - 原因: 网络库
   - 使用频率: 仅在查询时使用

## 优化方案

### 方案 1: 延迟导入 ddddocr（推荐）⭐⭐⭐⭐⭐

**优化效果**: 减少 1500-2000ms (~40-50%)

**实现方式**:
```python
# 修改前
import ddddocr

def solve_captcha(self, res):
    ocr = ddddocr.DdddOcr(show_ad=False)
    return res['key'], ocr.classification(img_data)

# 修改后
def solve_captcha(self, res):
    import ddddocr  # 延迟导入
    ocr = ddddocr.DdddOcr(show_ad=False)
    return res['key'], ocr.classification(img_data)
```

**优点**:
- 启动速度快 40-50%
- 仅在需要时加载
- 无需修改其他代码

**缺点**:
- 首次登录时会有延迟（但用户已看到 UI）

**影响范围**:
- `query_tool/utils/device_query.py` - 1 处修改

---

### 方案 2: 延迟导入 requests（可选）⭐⭐⭐

**优化效果**: 减少 200ms (~5%)

**实现方式**:
```python
# 修改前
import requests

# 修改后
def _request(self, ...):
    import requests  # 延迟导入
    ...
```

**优点**:
- 启动速度快 5%
- 仅在查询时加载

**缺点**:
- 首次查询时会有微小延迟

**影响范围**:
- `query_tool/utils/device_query.py` - 1 处修改
- `query_tool/utils/gitlab_api.py` - 1 处修改

---

### 方案 3: 延迟初始化页面（可选）⭐⭐⭐

**优化效果**: 减少 200-300ms (~5-7%)

**实现方式**:
```python
# 修改前
def init_ui(self):
    for page_info in PageRegistry.get_pages():
        page = page_info['class'](self)  # 立即创建
        self.pages.append(page)

# 修改后
def init_ui(self):
    for page_info in PageRegistry.get_pages():
        # 延迟创建页面（点击时才创建）
        pass

def on_page_button_clicked(self, page_info):
    if page_info['name'] not in self.pages:
        page = page_info['class'](self)  # 延迟创建
        self.pages[page_info['name']] = page
```

**优点**:
- 启动速度快 5-7%
- 只创建用户需要的页面

**缺点**:
- 首次切换页面时会有延迟
- 需要修改页面管理逻辑

**影响范围**:
- `query_tool/main.py` - 多处修改

---

### 方案 4: 使用 PyInstaller 优化（打包时）⭐⭐⭐⭐

**优化效果**: 减少 500-800ms (~10-20%)

**实现方式**:
```bash
# 修改 scripts/build.py
pyinstaller \
    --onefile \
    --windowed \
    --optimize=2 \  # 添加优化级别
    --strip \       # 移除调试符号
    --upx-dir=... \ # 使用 UPX 压缩
    run.py
```

**优点**:
- 启动速度快 10-20%
- 无需修改代码
- 仅影响打包后的程序

**缺点**:
- 仅对打包后的程序有效
- 需要安装 UPX

**影响范围**:
- `scripts/build.py` - 修改打包参数

---

### 方案 5: 预加载关键模块（可选）⭐⭐

**优化效果**: 减少 100-200ms (~2-5%)

**实现方式**:
```python
# 在后台线程中预加载
def preload_modules():
    import threading
    def _preload():
        import cv2
        import numpy
    threading.Thread(target=_preload, daemon=True).start()

# 在 UI 显示后调用
QTimer.singleShot(100, preload_modules)
```

**优点**:
- 启动速度快 2-5%
- 用户看不到延迟

**缺点**:
- 后台占用 CPU
- 效果有限

---

## 推荐优化方案

### 立即实施（快速见效）

1. **方案 1: 延迟导入 ddddocr** ⭐⭐⭐⭐⭐
   - 效果: 减少 40-50% (~1500-2000ms)
   - 难度: 简单
   - 风险: 低
   - **优先级: 最高**

### 后续优化（可选）

2. **方案 2: 延迟导入 requests** ⭐⭐⭐
   - 效果: 减少 5% (~200ms)
   - 难度: 简单
   - 风险: 低
   - **优先级: 中**

3. **方案 4: PyInstaller 优化** ⭐⭐⭐⭐
   - 效果: 减少 10-20% (~500-800ms)
   - 难度: 简单
   - 风险: 低
   - **优先级: 中**

### 不推荐（收益不大）

- 方案 3: 延迟初始化页面（用户体验差）
- 方案 5: 预加载模块（效果有限）

## 优化后的启动时间

### 仅实施方案 1
- **启动时间**: ~2500-3000ms (减少 40-50%)
- **用户体验**: UI 快速显示，登录时有微小延迟

### 实施方案 1 + 2 + 4
- **启动时间**: ~1500-2000ms (减少 55-65%)
- **用户体验**: 非常快速，首次查询有微小延迟

## 实施步骤

### 第一步: 实施方案 1（延迟导入 ddddocr）
1. 修改 `query_tool/utils/device_query.py`
2. 将 `import ddddocr` 移到 `solve_captcha()` 方法内
3. 测试登录功能

### 第二步: 实施方案 2（延迟导入 requests）
1. 修改 `query_tool/utils/device_query.py`
2. 修改 `query_tool/utils/gitlab_api.py`
3. 测试查询功能

### 第三步: 实施方案 4（PyInstaller 优化）
1. 修改 `scripts/build.py`
2. 添加 `--optimize=2` 和 `--strip` 参数
3. 重新打包测试

---

**建议**: 先实施方案 1，效果最显著。其他方案可根据实际需求后续实施。

**更新日期**: 2026-01-22  
**版本**: v2.0.0
