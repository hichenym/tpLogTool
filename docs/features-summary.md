# 功能总览

## 项目概述

`tpLogTool` 是一个基于 `PyQt5` 的 Windows 桌面工具，面向设备运维、远程调试、批量命令执行、固件管理、错误记录查询和 Git 提交日志导出场景。

当前主页面顺序如下：

1. 设备
2. 调试
3. 命令
4. 固件
5. 记录
6. GIT

## 页面能力

### 设备页

- 支持按 `SN / ID` 批量查询设备
- 展示设备名称、型号、SN、ID、密码、版本、在线状态等信息
- 支持批量唤醒、批量重启、批量升级、电池采集等操作
- 支持导出查询结果
- 结果表格支持右键菜单
- 可通过右键 `连接调试` 直接跳转到调试页并连接当前设备

### 调试页

- 使用 Seetong 账号和设备账号完成远程调试连接
- 自动根据 SN 查询设备密码
- 连接成功后自动发送 `syscmd start`
- 支持单设备交互式命令窗口
- 支持时间戳显示开关
- 支持在交互区直接输入并回车发送
- 支持命令历史上下切换
- 支持 `GetSystemCfg` 文件下载到本地目录
- 支持快捷命令
- 快捷命令支持添加、编辑、右键删除、拖拽排序、收起展开
- 快捷命令最多保存 50 条
- 支持连接中取消、连接后注销、右键清空交互区

### 命令页

- 面向批量设备执行命令与批量拉取日志
- 支持多 SN 输入，一行一个
- 支持多命令输入，一行一条
- 命令编辑区支持编辑/保存切换
- 默认并发 20 台设备执行
- 运行中支持取消，取消后会主动停止线程和子进程
- 每台设备会独立完成：
  - 查询设备密码
  - 登录设备
  - 顺序执行命令
  - 下载 `GetSystemCfg` 文件
  - 主动注销并结束连接
- 文件按 `下载目录/SN/文件名` 保存，已存在时直接覆盖
- 执行结果表格展示序号、SN、状态、文件、详情
- 表格支持双击复制单元格内容
- 状态与详情支持按结果着色

### 固件页

- 支持固件查询、筛选、编辑
- 使用独立固件账号登录
- 支持通过账号查询辅助填写 SN

### 记录页

- 支持按设备 SN、型号、版本、模块、错误码、时间范围查询错误记录
- 无筛选条件时禁止直接查询
- 结果中的 `设备SN` 支持双击查看设备信息
- 设备信息弹窗支持双击复制

### GIT 页

- 支持连接 Git 服务
- 支持按项目、分支、提交者、时间范围筛选提交记录
- 支持导出 Excel

## 通用能力

- 账号配置统一在设置窗口管理
- 支持三类账号：
  - 运维账号
  - Seetong 账号
  - 固件账号
- 主题支持深色/浅色切换，并保存到注册表
- 配置、历史输入、下载路径、快捷命令会保存到注册表
- 支持文件日志

## 配置存储

程序配置保存在：

```text
HKEY_CURRENT_USER\Software\TPQueryTool
```

主要配置项包括：

- 运维账号：`account_env`、`account_username`、`account_password`
- 固件账号：`firmware_username`、`firmware_password`
- Seetong 账号：`seetong_username`、`seetong_password`
- 调试页：`last_debug_sn`、`debug_download_path`、`debug_shortcuts`
- 命令页：`last_log_sn`、`log_download_path`、`log_commands`
- 通用配置：`export_path`、`phone_history`、`last_page_index`、`theme`
- Token 缓存：`env`、`username`、`token`、`refresh_token`、`timestamp`

说明：

- 账号密码当前使用 `Base64` 编码后写入注册表，不是强加密
- 调试页和命令页都会在进入功能前检查运维账号与 Seetong 账号是否已配置

## 调试模块实现

调试与命令功能复用 `query_tool/utils/siot_debug/` 下的公共模块，主要包括：

- `config.py`：SIOT 配置、DLL 路径、默认超时
- `service.py`：账号验证、设备凭据解析、调试工作线程
- `session.py`：云端鉴权、设备连接、命令发送、文件接收
- `subprocess_runner.py`：命令页使用的子进程运行封装
- `command_catalog.py`：命令类型识别
- `siot_helper.py`：开发态内部 SIOT 命令入口

当前依赖的 SIOT 动态库统一放在：

```text
query_tool/dll/
```

## 打包说明

当前本地打包使用 `scripts/build.py`，会从 `query_tool/dll` 打入所需 DLL，不再依赖旧的 `windows-siot-command-client` 目录。

## 说明

本文档仅保留当前版本的功能概览，不再记录历史代码片段和旧实现细节。
