# 设备查询工具

一个基于 PyQt5 的设备信息查询和管理工具，支持批量查询设备信息、唤醒设备、导出数据等功能。

## 功能特性

### 设备管理
- 🔍 批量查询设备信息（支持SN/ID查询）
- 📊 实时显示设备在线状态
- ⚡ 批量唤醒离线设备
- 📤 导出设备信息为CSV文件

### GitLab 日志导出（新增）
- 🔗 连接 GitLab 服务器
- 📋 查询项目提交记录
- 🔍 支持按分支、提交者、时间范围筛选
- 🎨 关键词高亮导出
- 📊 导出为 Excel 文件（带超链接）
- 💾 记录最近使用的项目和分支

### 通用功能
- ⚙️ 账号密码配置（运维账号和固件账号独立配置）
- 📝 日志记录系统（可配置调试信息输出）
- 🔄 自动更新检测（支持手动检查和自动更新）
- 💾 配置信息保存到注册表
- 🎨 友好的图形界面（深色主题）

## 环境要求

- Python 3.7+
- Windows 操作系统

## 安装步骤

### 1. 创建虚拟环境

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境 (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# 激活虚拟环境 (Windows CMD)
.\venv\Scripts\activate.bat

# 激活虚拟环境 (Linux/Mac)
source venv/bin/activate
```

### 2. 安装依赖包

```bash
pip install -r requirements.txt
```

### 3. 退出虚拟环境

```bash
deactivate
```

## 开发命令

### 导出依赖清单

```bash
pip freeze > requirements.txt
```

### UI 文件转 Python 文件

```bash
python -m PyQt5.uic.pyuic ui/mainWindow.ui -o mainWindow.py
```

### 图片资源转 Python 文件

```bash
pyrcc5 resources/icon_res.qrc -o resources/icon_res.py
```

### 清除图标缓存（Windows）

```bash
ie4uinit.exe -show
```

### 清除编译文件

```bash
# 清除 __pycache__、*.pyc、build、dist 等编译生成的文件
python scripts/clean.py
```

## 打包发布

### 🚀 快速发布新版本（推荐）

#### 方法一：使用快速发布脚本 ⭐

```bash
# 最简单的方式 - 一键发布
python scripts/release.py
```

脚本会自动引导你完成：
1. ✅ 检查 Git 状态
2. ✅ 显示当前版本和现有标签
3. ✅ 输入新版本号
4. ✅ 创建并推送标签
5. ✅ 触发 GitHub Actions 自动构建

#### 方法二：手动创建标签

```bash
# 1. 确保所有更改已提交
git add .
git commit -m "feat: 新功能描述"

# 2. 创建并推送标签
git tag v3.0.1
git push origin v3.0.1

# 3. 等待 GitHub Actions 自动构建（约 6-9 分钟）
```

GitHub Actions 会自动：
- ✅ 更新版本号和编译日期
- ✅ 打包 Windows 可执行文件
- ✅ 创建 GitHub Release
- ✅ 上传 exe 和 version.json
- ✅ 从 version.py 提取更新日志生成发布说明

构建完成后可在 [Releases](../../releases) 页面下载。

#### 发布前检查清单

- [ ] 本地测试通过
- [ ] 更新 `query_tool/version.py` 中的 `VERSION_HISTORY`
- [ ] 更新 `README.md`（如有必要）
- [ ] 更新相关文档
- [ ] 提交所有更改
- [ ] 运行 `python scripts/release.py`

#### 版本号规范

- **主版本号（Major）**: 重大功能更新或架构变更（如 `v3.0.0` → `v4.0.0`）
- **次版本号（Minor）**: 新增功能或较大改进（如 `v3.0.0` → `v3.1.0`）
- **修订号（Patch）**: Bug 修复或小改进（如 `v3.0.0` → `v3.0.1`）

#### 常见问题

**Q: 如何删除错误的标签？**
```bash
git tag -d v3.0.1              # 删除本地标签
git push origin :refs/tags/v3.0.1  # 删除远程标签
```

**Q: 构建失败怎么办？**
1. 查看 Actions 页面的详细日志
2. 修复问题后提交代码
3. 删除失败的标签并重新创建

**Q: 如何修改已发布的 Release？**
进入 Releases 页面，点击 Release 右侧的编辑按钮。

详细说明请参考：[docs/github-actions-guide.md](docs/github-actions-guide.md)

---

### 本地打包（开发测试用）

#### 版本管理

项目使用 `query_tool/version.py` 统一管理版本信息：

```python
VERSION_MAJOR = 3  # 主版本号：重大功能更新或架构变更
VERSION_MINOR = 0  # 次版本号：新增功能或较大改进
VERSION_PATCH = 0  # 修订号：Bug修复或小改进
BUILD_DATE = "20260224"  # 编译日期（自动生成）
```

版本号格式：`V主版本.次版本.修订号 (编译日期)`
例如：`V3.0.0 (20260224)`

#### 方法一：使用自动打包脚本

```bash
# 自动更新编译日期并打包
python scripts/build.py
```

脚本会自动：
1. 更新 `version.py` 中的编译日期为当前日期
2. 显示当前版本信息
3. 执行 PyInstaller 打包
4. 清理临时文件

#### 方法二：使用 spec 文件

```bash
# 清理之前的打包文件
pyinstaller 查询工具.spec --clean
```

#### 方法三：使用命令行参数

```bash
pyinstaller -F -w -i ./resources/icons/app/logo.ico --name "查询工具" run.py --noconsole
```

### 打包参数说明

- `-F` 或 `--onefile`: 打包成单个exe文件
- `-w` 或 `--windowed`: 不显示控制台窗口
- `-i`: 指定程序图标
- `--name`: 指定生成的exe文件名
- `--noconsole`: 不显示控制台（同-w）
- `--clean`: 清理临时文件

### 优化打包体积

1. **使用干净的虚拟环境**
```bash
# 创建专门用于打包的虚拟环境
python -m venv venv_build
.\venv_build\Scripts\activate

# 只安装必需的包
pip install PyQt5 requests ddddocr

# 打包
pyinstaller 设备查询工具.spec --clean
```

2. **安装 UPX 压缩工具**
   - 下载地址: https://github.com/upx/upx/releases
   - 解压后将 `upx.exe` 放到 PATH 路径中
   - 可额外减小 30-50% 体积

3. **分析打包内容**
```bash
# 使用 --onedir 模式查看打包内容
pyinstaller --onedir 设备查询工具.spec

# 查看大文件
dir /s /o-s dist\设备查询工具
```

## 项目结构

```
query-tool/
├── query_tool/                  # 主包（源代码）
│   ├── __init__.py             # 包初始化
│   ├── main.py                 # 程序入口
│   ├── version.py              # 版本信息
│   ├── pages/                  # 页面模块
│   │   ├── __init__.py
│   │   ├── base_page.py       # 页面基类
│   │   ├── page_registry.py   # 页面注册机制
│   │   ├── device_status_page.py  # 设备状态页面
│   │   ├── phone_query_page.py    # 账号查询页面
│   │   └── gitlab_log_page.py     # GitLab日志页面
│   ├── utils/                  # 工具模块
│   │   ├── __init__.py
│   │   ├── config.py          # 配置管理
│   │   ├── device_query.py    # 设备查询API
│   │   ├── workers.py         # 多线程Worker
│   │   ├── button_manager.py  # 按钮管理器
│   │   ├── message_manager.py # 消息管理器
│   │   ├── style_manager.py   # 样式管理器
│   │   ├── table_helper.py    # 表格工具
│   │   ├── thread_manager.py  # 线程管理器
│   │   ├── gitlab_api.py      # GitLab API封装
│   │   └── excel_helper.py    # Excel导出工具
│   └── widgets/                # 自定义控件
│       ├── __init__.py
│       └── custom_widgets.py  # 自定义控件
├── resources/                   # 资源文件
│   ├── icons/                  # 图标资源
│   │   ├── app/               # 应用图标
│   │   ├── common/            # 通用操作图标
│   │   ├── device/            # 设备操作图标
│   │   ├── gitlab/            # GitLab相关图标
│   │   ├── system/            # 系统设置图标
│   │   └── README.md          # 图标说明
│   ├── icon_res.qrc            # Qt资源配置
│   └── icon_res.py             # 编译后的资源
├── docs/                        # 文档目录
│   ├── README.md               # 文档索引
│   ├── quick-start.md          # 快速开始
│   ├── settings-guide.md       # 设置指南
│   ├── account-config-guide.md # 账号配置
│   ├── gitlab-quick-start.md   # GitLab快速开始
│   ├── modules-guide.md        # 模块使用指南
│   ├── gitlab-dev-guide.md     # GitLab开发指南
│   ├── gitlab-features.md      # GitLab功能清单
│   ├── features-summary.md     # 功能总结
│   ├── disabled-style-guide.md # 禁用样式说明
│   ├── dark-theme-guide.md     # 深色主题说明
│   ├── build-guide.md          # 打包说明
│   └── version-guide.md        # 版本管理指南
├── scripts/                     # 脚本目录
│   └── build.py                # 打包脚本
├── venv/                        # 虚拟环境
├── .gitignore                   # Git忽略配置
├── README.md                    # 项目说明
├── requirements.txt             # 依赖清单
└── run.py                       # 启动脚本
```



## 运行程序

### 开发模式

```bash
# 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 运行程序
python run.py
```

### 直接运行

```bash
python run.py
```

或者直接运行主文件：

```bash
python query_tool/main.py
```

### 1. 配置账号密码（首次使用必须）

首次使用程序时，需要先配置账号密码：

- 点击菜单栏右侧的"⚙️"图标按钮
- 在弹出的对话框中输入账号密码
- 可选择"测试连接"验证账号是否有效
- 点击"保存"按钮保存配置

如果未配置账号密码，查询时会自动提示您配置。

详细说明请参考：[docs/account-config-guide.md](docs/account-config-guide.md)

### 2. 查询设备信息

- 在左侧输入框输入设备SN（每行一个）
- 或在右侧输入框输入设备ID（每行一个）
- 点击"查询"按钮开始查询
- 查询结果会实时显示在下方表格中

### 3. 唤醒设备

- 勾选需要唤醒的设备
- 点击"批量唤醒"按钮
- 或点击单个设备行的"唤醒"按钮

### 4. 导出数据

- 点击"浏览"按钮选择保存目录
- 点击"导出"按钮导出CSV文件
- 文件名自动带时间戳，避免覆盖

### 5. GitLab 日志导出（新功能）

- 点击菜单栏的"Git日志"按钮切换到日志页面
- 填写 GitLab 服务器地址和 Token
- 点击"连接"按钮连接服务器
- 选择项目、分支、提交者（可选）
- 设置时间范围和关键词（可选）
- 选择保存路径
- 点击"导出"按钮导出 Excel 文件

### 6. 其他功能

- 双击表格单元格可复制内容
- 点击"清空"按钮清除所有输入和结果
- 支持全选/取消全选设备
- 页面切换自动保存状态

## 配置说明

程序配置信息保存在 Windows 注册表中：
- 路径: `HKEY_CURRENT_USER\Software\TPQueryTool`
- 包含: 账号密码、Token缓存、导出路径、日志配置等

### 账号密码配置

- 首次使用必须配置账号密码
- 点击菜单栏右侧的"⚙️"图标按钮配置
- 支持运维账号和固件账号独立配置
- 配置会保存到注册表，下次自动使用
- 支持测试连接功能，验证账号是否有效
- 密码使用Base64编码存储，非明文
- 固定使用生产环境
- 未配置时查询会自动提示

详细说明请参考：[docs/account-config-guide.md](docs/account-config-guide.md)

### 日志配置

- 支持调试信息记录到文件
- 日志文件路径：`C:\Users\<用户名>\.TPQueryTool\logs\`
- 日志文件命名：`app_YYYYMMDD.log`（按日期自动分割）
- 日志轮转：单文件最大10MB，保留3个备份
- 控制台只显示WARNING及以上级别
- 可在设置页面启用/禁用文件日志，实时生效

详细说明请参考：[docs/settings-guide.md](docs/settings-guide.md)

## 技术栈

- **GUI框架**: PyQt5
- **网络请求**: requests
- **验证码识别**: ddddocr
- **并发处理**: ThreadPoolExecutor
- **数据存储**: Windows Registry

## 注意事项

1. 首次运行需要联网获取Token
2. Token有效期为2小时，过期后自动刷新
3. 建议使用30个并发线程，平衡速度和稳定性
4. 导出的CSV文件使用UTF-8编码，Excel可直接打开

## 常见问题

### Q: 打包后体积过大？
A: 参考 [docs/build-guide.md](docs/build-guide.md) 文档进行优化，可减小到30-60MB

### Q: 图标不显示？
A: 修改icon_res.qrc后需要重新运行 `pyrcc5 icon_res.qrc -o icon_res.py`

### Q: 查询失败？
A: 检查网络连接和账号密码是否正确

### Q: 虚拟环境激活失败？
A: PowerShell需要管理员权限或执行 `Set-ExecutionPolicy RemoteSigned`

## 更新日志

### V3.0.0 (2026-02-07) - 账号配置与日志系统升级 🎉
- 🔐 **账号配置系统全面升级**
  - 运维账号和固件账号独立配置管理
  - 使用标签页分离两个系统的账号配置
  - 支持灵活配置：允许全部为空或只配置一个平台
  - 单个平台的账号密码必须同时填写或同时为空
  - 未配置时智能提示并可直接跳转到对应标签页
  - 移除固件系统硬编码账号密码，提升安全性
- 📝 **日志记录系统**
  - 支持调试信息记录到文件
  - 日志文件路径：`C:\Users\<用户名>\.TPQueryTool\logs\`
  - 日志文件按日期命名：`app_YYYYMMDD.log`
  - 日志轮转：单文件最大10MB，保留3个备份
  - 控制台只显示WARNING及以上级别
  - 可在设置页面启用/禁用，实时生效
  - 完善核心模块日志记录（配置管理、设备查询、主窗口等）
- 🎨 **界面优化**
  - 设置对话框使用标签页设计（账号配置、日志配置）
  - 标签页样式优化：选中时背景色高亮
  - 账号配置使用滚动布局，支持多个账号分组
  - 每个账号组独立的"显示密码"和"验证"按钮
  - 验证按钮点击时显示"验证中..."并禁用
- 🔧 **技术改进**
  - 固件账号配置保存到独立注册表键
  - Session缓存管理优化
  - 全局异常处理和日志记录
  - 代码结构优化，提升可维护性

### v2.0.0 (2026-01-22) - 重大重构版本 🎉
- 🏗️ **项目结构完全重组（方案B）**
  - 源代码集中在 `query_tool/` 包
  - 资源文件集中在 `resources/`
  - 文档集中在 `docs/`
  - 脚本集中在 `scripts/`
  - 所有导入路径统一为 `query_tool.*` 格式
- ✨ **新增 GitLab 日志导出功能**
  - 支持连接 GitLab 服务器
  - 支持按项目、分支、提交者筛选
  - 支持时间范围筛选
  - 支持关键词高亮导出
  - 导出为 Excel 文件（带超链接）
  - 记录最近使用的项目和分支
- 🔧 **改进**
  - 图标资源路径更新为 `:/icons/`
  - 启动脚本 `run.py` 支持直接运行
  - 打包脚本更新为新的项目结构
  - 注册表名称更新为 `TPQueryTool`
  - 所有文档更新以反映新的项目结构
- 📚 **文档完善**
  - 13个核心文档完整覆盖所有功能
  - 详细的模块使用指南
  - 完整的打包和发布流程说明

### v1.2.0 (2026-01-21) - 代码重构版本 🎉
- 🏗️ **重大重构**：项目模块化重构（已完成60%）
- 📦 新增 `utils/` 工具模块（9个文件）
  - `config.py` - 配置管理器
  - `device_query.py` - 设备查询API
  - `workers.py` - 多线程Worker
  - `button_manager.py` - 按钮管理器（新增）
  - `message_manager.py` - 消息管理器（新增）
  - `style_manager.py` - 样式管理器（新增）
  - `table_helper.py` - 表格工具（新增）
  - `thread_manager.py` - 线程管理器（新增）
- 🎨 新增 `widgets/` 自定义控件模块
- 📝 新增详细的重构文档（4个文档）
- ⚡ 减少重复代码80%，提升可维护性
- 🔧 统一接口管理，提升代码质量
- 📚 详见：[docs/features-summary.md](docs/features-summary.md)

### v1.1.1 (2026-01-17)
- 🐛 修复重复定义save_account_config函数的问题
- 🔧 改进异常处理，使用具体异常类型替代bare except
- 🛡️ 增强线程清理机制，防止窗口关闭时崩溃
- ⏱️ 添加网络请求超时设置（5秒），防止无限等待
- 📝 优化错误日志输出，便于调试
- 🔍 修复PhoneQueryWorker中的空指针检查
- 💪 提升代码健壮性和稳定性

### v1.1.0 (2026-01-17)
- ✨ 新增账号密码配置功能
- ✨ 新增设置界面（菜单栏右侧图标按钮）
- ✨ 新增测试连接功能
- 🔒 密码Base64编码存储到注册表
- 🎨 优化菜单栏布局，设置按钮仅显示图标
- 🔧 固定使用生产环境，简化配置
- 🔐 移除硬编码默认账号密码，提升安全性
- 💡 未配置账号密码时自动提示用户配置

### v1.0.0
- 初始版本发布
- 支持批量查询和唤醒
- 支持CSV导出
- 配置保存到注册表

## 许可证

本项目仅供内部使用

## 联系方式

如有问题请联系开发团队
