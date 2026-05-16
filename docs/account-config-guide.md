# 账号配置说明

## 功能概述

程序当前支持三类账号独立配置：

- 运维账号
- Seetong 账号
- 固件账号

三类配置统一保存在 Windows 注册表中，并在需要时由不同页面按需读取。

## 打开方式

1. 打开主程序
2. 点击右上角设置按钮
3. 进入账号配置页

## 各账号用途

### 运维账号

用于：

- 设备页查询设备信息
- 根据 SN 查询设备密码
- 状态、唤醒、电池、重启、升级等设备接口

### Seetong 账号

用于：

- 调试页远程登录设备
- 命令页批量连接设备并执行命令
- Seetong 云端登录验证

### 固件账号

用于：

- 固件页查询固件
- 固件编辑、上传等功能

## 配置规则

- 单个平台的账号和密码必须同时填写或同时为空
- 运维账号可单独配置
- Seetong 账号可单独配置
- 固件账号可单独配置
- 调试页与命令页运行时必须同时具备运维账号和 Seetong 账号

## 验证方式

设置页支持对各账号分别验证：

- 运维账号：验证运维接口登录
- Seetong 账号：按调试模块的云端登录流程验证
- 固件账号：验证固件系统登录

## 配置保存位置

```text
HKEY_CURRENT_USER\Software\TPQueryTool
```

## 注册表字段

### 运维账号

- `account_env`
- `account_username`
- `account_password`

### 固件账号

- `firmware_username`
- `firmware_password`

### Seetong 账号

- `seetong_username`
- `seetong_password`

### 应用配置

- `export_path`
- `phone_history`
- `debug_shortcuts`
- `last_debug_sn`
- `debug_download_path`
- `last_log_sn`
- `log_download_path`
- `log_commands`
- `last_page_index`
- `theme`

### Token 缓存

- `env`
- `username`
- `token`
- `refresh_token`
- `timestamp`

## 调试页和命令页的配置保存

### 调试页

会保存：

- 最近一次输入的设备 SN
- 下载目录
- 快捷命令列表

说明：

- 快捷命令最多保存 50 条
- 会按当前拖拽顺序保存

### 命令页

会保存：

- SN 列表文本
- 下载目录
- 命令列表

说明：

- 命令列表最多保存 50 条
- 会保留多行文本格式

## 未配置时的提示

### 设备页

缺少运维账号时，会提示用户先配置运维账号。

### 调试页

缺少运维账号或 Seetong 账号时，会弹出提示框，并引导用户进入账号配置页。

### 命令页

缺少运维账号或 Seetong 账号时，会弹出提示框，并引导用户进入账号配置页。

### 固件页

缺少固件账号时，会提示用户先配置固件账号。

## 安全说明

1. 当前密码保存方式是 `Base64` 编码，不是强加密
2. 配置仅保存在当前 Windows 用户下
3. 不同用户之间互不影响
4. 不建议在公共电脑长期保存敏感账号

## 常见问题

### Q: 修改配置后需要重启程序吗？

A: 不需要。保存后新配置会在后续操作中直接生效。

### Q: Seetong 账号为什么在设备页里用不到？

A: 设备页主要走运维接口；Seetong 账号主要用于调试页和命令页远程连接设备。

### Q: 调试页为什么既要运维账号又要 Seetong 账号？

A: 运维账号用于根据 SN 查询设备信息和设备密码，Seetong 账号用于云端登录和建立 SIOT 连接，二者缺一不可。

### Q: 配置为什么会自动恢复？

A: 因为界面状态和账号信息都保存在注册表中，程序启动时会自动读取。

### Q: 命令页的 SN 和命令为什么不会丢？

A: 这两部分内容会保存到 `last_log_sn` 和 `log_commands`。

## 相关代码位置

- 配置管理：[query_tool/utils/config.py](/D:/GIT/tpLogTool/query_tool/utils/config.py)
- 设置对话框：[query_tool/widgets/custom_widgets.py](/D:/GIT/tpLogTool/query_tool/widgets/custom_widgets.py)
- 调试页：[query_tool/pages/debug_page.py](/D:/GIT/tpLogTool/query_tool/pages/debug_page.py)
- 命令页：[query_tool/pages/log_page.py](/D:/GIT/tpLogTool/query_tool/pages/log_page.py)
