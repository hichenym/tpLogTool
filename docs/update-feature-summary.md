# 自动更新功能总结

## 功能概览

TPQueryTool 支持完整的自动更新功能，包括版本检查、下载、安装和重启。

## 更新流程

### 用户视角

```
程序启动
  ↓
后台检查更新（2秒后）
  ↓
如果有新版本
  ↓
弹出更新提示对话框
  ├─ 立即更新 → 后台下载（状态栏显示进度）→ 完成后弹出重启对话框
  ├─ 稍后提醒 → 下次启动再提示
  └─ 跳过此版本 → 记录跳过，不再提示此版本
```

### 下载体验

点击"立即更新"后：
1. 对话框关闭，回到主界面
2. 状态栏显示：`正在下载更新 V3.1.0...`
3. 实时更新进度：`正在下载更新: 45.2 MB / 173.1 MB (26%)`
4. 下载完成：`✓ 更新下载完成`
5. 弹出重启对话框

**优势**：
- 不阻塞主界面
- 可以继续使用程序
- 进度信息清晰
- 体验流畅

## 四种更新策略

### 1. prompt（提示更新）- 默认

- 启动时自动检查更新
- 发现新版本时弹出提示
- 用户决定是否更新
- 适合大多数用户

### 2. silent（静默更新）

- 启动时自动检查更新
- 发现新版本时后台下载
- 下载完成后提示
- 关闭程序时自动安装
- 适合企业环境

### 3. manual（手动更新）

- 不自动检查更新
- 用户手动点击"检查更新"
- 适合离线环境或特殊需求

### 4. auto（自动下载并自动安装）

- 启动时自动检查更新
- 发现新版本时后台下载
- 下载完成后自动进入安装/重启流程
- 程序重启时如果检测到本地已有下载完成的更新包，会继续自动安装
- 仅在当前运行方式支持自动覆盖安装时完整生效；不支持自动安装的运行方式会保留安装包并提示手动处理

## 跳过版本功能

### 使用场景

- 某个版本有已知问题，暂时不想升级
- 等待更稳定的版本
- 当前版本满足需求

### 使用方法

1. 更新提示对话框中点击"跳过此版本"
2. 系统将版本号保存到 Windows 注册表
3. 下次启动不再提示该版本
4. 如果有更新的版本，仍会正常提示

### 存储位置

**注册表路径**：
```
HKEY_CURRENT_USER\Software\TPQueryTool\Update
键名: SkippedVersion
类型: REG_SZ (字符串)
值: 版本号（如 "3.1.0"）
```

### 管理跳过记录

**查看跳过的版本**：
1. 打开注册表编辑器（Win+R，输入 regedit）
2. 导航到 `HKEY_CURRENT_USER\Software\TPQueryTool\Update`
3. 查看 `SkippedVersion` 键值

**清除跳过记录**：
1. 在注册表编辑器中删除 `SkippedVersion` 键值
2. 或使用程序提供的清除功能（如果实现）

**特点**：
- 只保存最新跳过的版本（新跳过会覆盖旧记录）
- 用户可以直接修改注册表来管理
- 符合 Windows 应用程序的标准做法

## 配置文件

### version.json 格式

```json
{
  "version": "3.1.0",
  "build_date": "20260224",
  "download_url": "https://github.com/hichenym/tpLogTool/releases/download/v3.1.0/TPQueryTool.exe",
  "file_size_mb": 173.06,
  "release_notes_url": "https://github.com/hichenym/tpLogTool/releases/tag/v3.1.0",
  "min_version": "3.0.0",
  "update_strategy": "prompt",
  "show_change": true,
  "changelog": [
    "🚀 新功能1",
    "🐛 修复问题2",
    "✨ 改进3"
  ]
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| version | string | 版本号（如 "3.1.0"） |
| build_date | string | 编译日期（如 "20260224"） |
| download_url | string | 下载地址（GitHub Release） |
| file_size_mb | number | 文件大小（MB） |
| release_notes_url | string | 发布说明链接 |
| min_version | string | 最低兼容版本（可选） |
| update_strategy | string | 更新策略。支持 `manual`、`prompt`、`silent`、`auto` |
| show_change | bool | 是否在更新相关弹窗中展示变更内容区域。仅对实际出现的弹窗生效 |
| changelog | array | 更新日志列表 |

### `update_strategy` 取值说明

- `manual`：不参与启动自动检查，只能由用户在设置页手动触发检查。
- `prompt`：启动自动检查；发现新版本后弹出更新提示框，由用户决定是否下载。
- `silent`：启动自动检查；发现新版本后后台下载；下载完成后提示用户重启安装。
- `auto`：启动自动检查；发现新版本后后台下载；下载完成后自动进入安装/重启流程。

### `show_change` 与 `update_strategy` 的关系

- `show_change=true` 仅表示“如果当前流程会弹出更新相关对话框，则允许展示变更内容区域”。
- `show_change=false` 表示弹窗中隐藏变更内容区域。
- `show_change` 不会覆盖 `update_strategy` 的主流程。
- 因此当 `update_strategy=auto` 时，正常自动更新链路不会因为 `show_change=true` 而额外弹出提示框。

## 下载优化

### 重试机制

- 最多重试 3 次
- 每次重试间隔 2 秒
- 自动切换下载源（如果配置了镜像）

### 超时配置

- 连接超时：10 秒
- 读取超时：300 秒（5 分钟）

### 临时文件机制

- 下载到 `.tmp` 文件
- 完成后重命名为正式文件
- 避免下载中断导致文件损坏

### 错误处理

详细的错误分类和提示：
- 网络连接失败
- 下载超时
- 文件校验失败
- 磁盘空间不足

## 安装和重启

### 安装流程

1. 下载完成后，文件保存在临时目录
2. 用户选择"立即重启"
3. 程序创建批处理脚本
4. 批处理脚本等待程序退出
5. 替换旧文件
6. 启动新版本
7. 清理临时文件

### 批处理脚本示例

```batch
@echo off
timeout /t 2 /nobreak > nul
move /y "临时文件.exe" "TPQueryTool.exe"
start "" "TPQueryTool.exe"
del "%~f0"
```

## 手动检查更新

### 在设置中检查

1. 点击右上角设置按钮
2. 切换到"关于"标签页
3. 点击"检查更新"按钮
4. 等待检查结果

### 检查结果

- **有新版本**：显示版本信息，弹出更新提示对话框
- **已是最新版本**：显示提示消息
- **检查失败**：显示错误信息

## 缓存机制

### 版本信息缓存

- 缓存文件：`~/.TPQueryTool/update/version_cache.json`
- 缓存有效期：24 小时
- 网络失败时使用缓存

### 跳过版本记录

- 存储位置：Windows 注册表 `HKEY_CURRENT_USER\Software\TPQueryTool\Update\SkippedVersion`
- 持久化存储
- 只保存最新跳过的版本
- 用户可通过注册表编辑器管理

## 网络配置

### 版本信息 URL

**主 URL（CDN，优先）**：
```
https://cdn.jsdelivr.net/gh/hichenym/tpLogTool@main/version.json
```

**备用 URL（GitHub Raw）**：
```
https://raw.githubusercontent.com/hichenym/tpLogTool/main/version.json
```

### 下载 URL

从 `version.json` 中的 `download_url` 字段获取：
```
https://github.com/hichenym/tpLogTool/releases/download/v3.1.0/TPQueryTool.exe
```

## 日志记录

### 日志位置

```
C:\Users\<用户名>\.TPQueryTool\logs\tpquerytool_YYYYMMDD.log
```

### 关键日志

```
INFO - 程序启动: TPQueryTool V3.0.0
INFO - 开始检查更新...
INFO - 发现新版本: V3.1.0 (20260224)
INFO - 用户选择立即更新
INFO - 开始下载更新: 3.1.0
INFO - 下载完成: C:\Users\...\TPQueryTool_3.1.0.exe
INFO - 用户选择立即重启，应用更新...
```

## 故障排查

### 检查更新失败

**可能原因**：
- 网络连接问题
- GitHub 访问受限
- 防火墙阻止

**解决方法**：
1. 检查网络连接
2. 尝试访问 GitHub
3. 配置代理（如果需要）
4. 查看日志文件

### 下载失败

**可能原因**：
- 网络不稳定
- 下载超时
- 磁盘空间不足

**解决方法**：
1. 检查网络连接
2. 检查磁盘空间
3. 重试下载
4. 手动下载安装

### 安装失败

**可能原因**：
- 文件被占用
- 权限不足
- 杀毒软件阻止

**解决方法**：
1. 关闭程序
2. 以管理员身份运行
3. 临时关闭杀毒软件
4. 手动替换文件

## 相关文档

- [自动更新实现方案](auto-update-implementation.md)
- [静默更新指南](silent-update-guide.md)
- [更新策略指南](update-strategy-guide.md)
- [网络问题排查](update-network-troubleshooting.md)
- [UI 改进说明](update-ui-improvements.md)
- [快速参考](update-quick-reference.md)

## 开发者参考

### 核心模块

1. `query_tool/utils/update_checker.py` - 版本检查
2. `query_tool/utils/update_downloader.py` - 下载管理
3. `query_tool/utils/update_manager.py` - 更新管理器
4. `query_tool/widgets/update_dialog.py` - 更新对话框

### 关键类

- `UpdateChecker` - 版本检查器
- `UpdateDownloader` - 下载器
- `UpdateManager` - 更新管理器
- `UpdateInstaller` - 安装器
- `VersionInfo` - 版本信息

### 信号和槽

```python
# UpdateManager 信号
update_available = pyqtSignal(object)  # 发现新版本
download_progress = pyqtSignal(int, int)  # 下载进度
download_finished = pyqtSignal(bool, str)  # 下载完成

# 主窗口槽函数
on_update_available(version_info)  # 处理新版本
on_download_progress(downloaded, total)  # 更新进度
on_download_finished(success, result)  # 处理完成
```

## 测试

### 测试脚本

```bash
# 测试更新检查
python test_update.py

# 测试下载重试
python test_download_retry.py

# 测试跳过版本
python test_skip_version.py

# 测试设置页面更新
python test_settings_update.py
```

### 手动测试

1. 修改 `version.json` 中的版本号
2. 启动程序
3. 观察更新提示
4. 测试各种操作
5. 查看日志

## 版本历史

### V3.1.0 (2026-02-24)
- ✅ 实现完整的自动更新功能
- ✅ 支持四种更新策略
- ✅ 添加下载重试机制
- ✅ 优化下载超时配置
- ✅ 实现跳过版本功能
- ✅ 优化下载进度显示（状态栏）

### V3.0.0 (2026-02-20)
- 初始版本
- 基础功能实现
