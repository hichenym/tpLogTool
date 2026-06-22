# 设备查询工具

一个基于 `PyQt5` 的 Windows 桌面工具，面向设备运维、远程调试、批量命令执行、固件管理、错误记录查询和 Git 提交日志导出场景。

## 主要功能

### 设备页

- 批量查询设备信息，支持 `SN / ID`
- 展示在线状态、版本、设备密码等信息
- 支持唤醒、重启、升级、电池采集、导出
- 结果表格支持右键菜单
- 支持从设备页右键直接跳转到调试页连接设备

### 调试页

- 使用 Seetong 账号远程登录设备
- 自动根据 SN 查询设备密码
- 单设备交互式命令窗口
- 支持时间戳显示切换
- 支持命令历史
- 支持快捷命令、右键编辑/删除、拖拽排序
- 支持 `GetSystemCfg` 文件下载
- 连接中可取消，连接后可注销

### 命令页

- 面向多设备并发执行命令
- 支持多 SN、多命令输入
- 支持批量 `GetSystemCfg` 文件下载
- 默认并发 20 台设备
- 支持运行中取消
- 结果表格展示状态、文件、详情和执行汇总

### 固件页

- 固件查询、筛选、编辑
- 使用独立固件账号

### 记录页

- 按设备 SN、型号、版本、模块、错误码、时间范围查询错误记录
- 双击结果中的 `设备SN` 查看设备详情

### GIT 页

- 连接 Git 服务
- 按项目、分支、提交者、时间范围筛选提交记录
- 导出 Excel

## 账号体系

程序当前支持三类账号：

- 运维账号
- Seetong 账号
- 固件账号

其中：

- 设备页主要依赖运维账号
- 调试页和命令页依赖运维账号 + Seetong 账号
- 固件页依赖固件账号

## 环境要求

- Windows 操作系统
- Python 3.8+

## 安装与运行

### 创建虚拟环境

```bash
python -m venv venv
```

### 激活虚拟环境

PowerShell：

```bash
.\venv\Scripts\Activate.ps1
```

CMD：

```bash
.\venv\Scripts\activate.bat
```

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动程序

```bash
python run.py
```

## 首次使用

1. 点击右上角设置按钮
2. 在账号配置页填写账号
3. 至少按需配置：
   - 运维账号
   - Seetong 账号
   - 固件账号
4. 点击保存

配置保存在：

```text
HKEY_CURRENT_USER\Software\TPQueryTool
```

## 常用操作

### 设备查询

1. 打开“设备”页
2. 输入设备 SN 或 ID
3. 点击查询

### 调试设备

方式一：

1. 打开“调试”页
2. 输入 SN
3. 点击连接

方式二：

1. 在“设备”页右键目标设备
2. 点击“连接调试”

### 批量执行命令

1. 打开“命令”页
2. 输入 SN 列表
3. 输入命令列表
4. 选择下载目录
5. 点击运行

## 项目结构

```text
tpLogTool/
├── query_tool/
│   ├── dll/                     # 调试/命令模块依赖的 DLL
│   ├── pages/                   # 页面模块
│   │   ├── device_status_page.py
│   │   ├── debug_page.py
│   │   ├── log_page.py
│   │   ├── firmware_page.py
│   │   ├── error_record_page.py
│   │   └── gitlab_log_page.py
│   ├── utils/
│   │   ├── config.py
│   │   ├── device_query.py
│   │   ├── workers.py
│   │   └── siot_debug/          # 调试/命令公共模块
│   │       └── siot_helper.py   # 开发态内部 SIOT 命令入口
│   ├── widgets/
│   ├── main.py
│   └── version.py
├── resources/
│   ├── icons/
│   ├── icon_res.qrc
│   └── icon_res.py
├── docs/
├── scripts/
│   ├── build.py
│   └── clean.py
├── requirements.txt
└── run.py
```

## 本地打包

当前本地打包使用 `PyInstaller`：

```bash
python scripts/build.py
```

打包时会一并带上：

- `resources/icons`
- `query_tool/dll`

当前项目已经不再依赖旧的 `windows-siot-command-client` 目录。

## 配置说明

注册表中主要保存：

- 运维账号、Seetong 账号、固件账号
- 导出路径
- 调试页最近 SN、下载路径、快捷命令
- 命令页 SN 列表、命令列表、下载路径
- 主题
- Token 缓存

说明：

- 账号密码当前使用 `Base64` 编码存储，不是强加密
- 不建议在公共电脑上长期保存敏感账号

## 相关文档

- [docs/README.md](./docs/README.md)
- [docs/quick-start.md](./docs/quick-start.md)
- [docs/account-config-guide.md](./docs/account-config-guide.md)
- [docs/features-summary.md](./docs/features-summary.md)
- [docs/build-guide.md](./docs/build-guide.md)

## 开发命令

### 重新生成 Qt 资源文件

```bash
pyrcc5 resources/icon_res.qrc -o resources/icon_res.py
```

### 清理缓存和构建产物

```bash
python scripts/clean.py
```

## 注意事项

1. 调试页和命令页依赖 Seetong 云端登录
2. 调试与批量命令能力依赖 `query_tool/dll` 下的动态库
3. `GetSystemCfg` 下载文件默认按 `下载目录/SN/文件名` 保存
4. 命令页运行中支持取消，取消后状态会显示为“已取消”

## 许可证

本项目仅供内部使用
