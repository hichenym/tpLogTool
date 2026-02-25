# 跳过版本功能 - 注册表存储方案

## 概述

跳过版本功能允许用户在发现新版本时选择"跳过此版本"，系统会记录该版本号，下次检查更新时自动过滤已跳过的版本。

从之前的文件存储方案改为注册表存储方案，提供更好的用户体验和可维护性。

## 存储位置

跳过的版本号存储在 Windows 注册表中：

```
注册表路径: HKEY_CURRENT_USER\Software\TPQueryTool\Update
键名: SkippedVersion
类型: REG_SZ (字符串)
值: 版本号（如 "3.1.0"）
```

## 设计特点

### 1. 单版本存储

- 注册表中只保存一个版本号（最新跳过的版本）
- 每次跳过新版本时会覆盖之前的记录
- 简化了数据管理，避免累积过多历史记录

### 2. 用户可控

用户可以通过以下方式管理跳过的版本：

- 直接修改注册表键值来取消跳过
- 删除注册表键来清除跳过记录
- 使用 Windows 注册表编辑器（regedit）进行管理

### 3. 自动清理

- 当用户跳过新版本时，旧的跳过记录会被自动覆盖
- 不需要手动清理历史记录

## 使用场景

### 场景 1：跳过当前版本

```
当前版本: V3.0.0
发现新版本: V3.1.0

用户操作: 点击"跳过此版本"
结果: 注册表中保存 "3.1.0"
下次检查: 不再提示 V3.1.0
```

### 场景 2：跳过后发现更新版本

```
当前版本: V3.0.0
已跳过: V3.1.0
发现新版本: V3.2.0

结果: 正常提示 V3.2.0（因为 3.2.0 != 3.1.0）
```

### 场景 3：用户想恢复更新提示

用户可以通过以下方式恢复：

1. 打开注册表编辑器（Win+R，输入 regedit）
2. 导航到 `HKEY_CURRENT_USER\Software\TPQueryTool\Update`
3. 删除 `SkippedVersion` 键值
4. 下次检查更新时会重新提示

## API 说明

### skip_version(version: str)

跳过指定版本（保存到注册表）

```python
checker = UpdateChecker("3.0.0")
checker.skip_version("3.1.0")
```

### get_skipped_version() -> Optional[str]

获取当前跳过的版本号

```python
skipped = checker.get_skipped_version()
print(f"当前跳过的版本: {skipped}")  # 输出: 3.1.0 或 None
```

### clear_skipped_version()

清除跳过的版本记录（从注册表删除）

```python
checker.clear_skipped_version()
```

### _is_version_skipped(version: str) -> bool

检查指定版本是否被跳过（内部方法）

```python
if checker._is_version_skipped("3.1.0"):
    print("该版本已被跳过")
```

## 实现细节

### 注册表操作

使用 Python 的 `winreg` 模块进行注册表操作：

```python
import winreg

# 写入
reg_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\TPQueryTool\Update")
winreg.SetValueEx(reg_key, "SkippedVersion", 0, winreg.REG_SZ, version)
winreg.CloseKey(reg_key)

# 读取
reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\TPQueryTool\Update", 0, winreg.KEY_READ)
skipped_version, _ = winreg.QueryValueEx(reg_key, "SkippedVersion")
winreg.CloseKey(reg_key)

# 删除
reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\TPQueryTool\Update", 0, winreg.KEY_WRITE)
winreg.DeleteValue(reg_key, "SkippedVersion")
winreg.CloseKey(reg_key)
```

### 错误处理

- `FileNotFoundError`: 注册表键不存在（正常情况，表示没有跳过任何版本）
- 其他异常: 记录日志但不影响程序运行

## 优势对比

### 文件存储方案（旧）

- 需要管理文件路径
- 可能累积多个历史版本
- 需要手动清理文件
- 用户不易发现和修改

### 注册表存储方案（新）

- Windows 原生支持，无需文件管理
- 只保存最新跳过的版本，自动覆盖
- 用户可以通过注册表编辑器直接管理
- 更符合 Windows 应用程序的标准做法

## 测试

运行测试脚本验证功能：

```bash
python test_skip_version.py
```

测试内容：
1. 跳过版本后不再提示
2. 清除跳过记录后重新提示
3. 多次跳过版本（覆盖行为）
4. 获取当前跳过的版本

## 注意事项

1. 只在 Windows 系统上可用（使用 winreg 模块）
2. 需要用户有权限访问 HKEY_CURRENT_USER
3. 跳过版本只影响自动更新检查，不影响手动检查
4. 用户可以随时通过注册表编辑器修改或删除跳过记录
