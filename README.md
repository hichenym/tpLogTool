# 设备查询工具

一个基于 PyQt5 的设备信息查询和管理工具，支持批量查询设备信息、唤醒设备、导出数据等功能。

## 功能特性

- 🔍 批量查询设备信息（支持SN/ID查询）
- 📊 实时显示设备在线状态
- ⚡ 批量唤醒离线设备
- 📤 导出设备信息为CSV文件
- ⚙️ 账号密码配置（支持自定义账号密码）
- 💾 配置信息保存到注册表
- 🎨 友好的图形界面

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
pyrcc5 icon_res.qrc -o icon_res.py
```

### 清除图标缓存（Windows）

```bash
ie4uinit.exe -show
```

## 打包发布

### 版本管理

项目使用 `version.py` 统一管理版本信息：

```python
VERSION_MAJOR = 1  # 主版本号：重大功能更新或架构变更
VERSION_MINOR = 0  # 次版本号：新增功能或较大改进
VERSION_PATCH = 0  # 修订号：Bug修复或小改进
BUILD_DATE = "20260115"  # 编译日期（自动生成）
```

版本号格式：`V主版本.次版本.修订号 (编译日期)`
例如：`V1.0.0 (20260115)`

### 方式一：使用自动打包脚本（推荐）

```bash
# 自动更新编译日期并打包
python build.py
```

脚本会自动：
1. 更新 `version.py` 中的编译日期为当前日期
2. 显示当前版本信息
3. 执行 PyInstaller 打包
4. 清理临时文件

### 方式二：使用 spec 文件

```bash
# 清理之前的打包文件
pyinstaller 设备查询工具.spec --clean
```

### 方式三：使用命令行参数

```bash
pyinstaller -F -w -i ./icon/logo.ico --name "设备查询工具" main.py --noconsole
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
.
├── utils/                  # 🆕 工具模块（已重构）
│   ├── config.py          # 配置管理
│   ├── device_query.py    # 设备查询API
│   ├── workers.py         # 多线程Worker
│   ├── button_manager.py  # 按钮管理器
│   ├── message_manager.py # 消息管理器
│   ├── style_manager.py   # 样式管理器
│   ├── table_helper.py    # 表格工具
│   └── thread_manager.py  # 线程管理器
├── widgets/                # 🆕 自定义控件（已重构）
│   └── custom_widgets.py  # 自定义控件
├── md/                     # 📚 文档目录
│   ├── 代码重构说明.md
│   ├── 重构进度报告.md
│   ├── 重构模块使用指南.md
│   └── 重构完成总结.md
├── icon/                   # 图标资源目录
│   ├── logo.ico           # 程序图标
│   ├── logo.png           # Logo图片
│   ├── search.png         # 搜索图标
│   ├── clean.png          # 清空图标
│   ├── save.png           # 保存图标
│   ├── export.png         # 导出图标
│   ├── werk_up.png        # 唤醒图标
│   └── werk_up_all.png    # 批量唤醒图标
├── main.py                # 主程序文件
├── icon_res.py            # 图标资源文件
├── icon_res.qrc           # Qt资源配置文件
├── 设备查询工具.spec      # PyInstaller配置文件
├── requirements.txt       # 依赖包清单
├── version.py             # 版本信息
└── README.md              # 项目说明文档
```

> **📢 重要提示**：项目正在进行模块化重构（已完成60%），新增了 `utils/` 和 `widgets/` 模块。
> 详细信息请查看 [md/重构完成总结.md](md/重构完成总结.md)

## 使用方法

### 1. 配置账号密码（首次使用必须）

首次使用程序时，需要先配置账号密码：

- 点击菜单栏右侧的"⚙️"图标按钮
- 在弹出的对话框中输入账号密码
- 可选择"测试连接"验证账号是否有效
- 点击"保存"按钮保存配置

如果未配置账号密码，查询时会自动提示您配置。

详细说明请参考：[账号密码配置说明.md](账号密码配置说明.md)

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

### 5. 其他功能

- 双击表格单元格可复制内容
- 点击"清空"按钮清除所有输入和结果
- 支持全选/取消全选设备

## 配置说明

程序配置信息保存在 Windows 注册表中：
- 路径: `HKEY_CURRENT_USER\Software\TPDevQuery`
- 包含: 账号密码、Token缓存、导出路径等配置

### 账号密码配置

- 首次使用必须配置账号密码
- 点击菜单栏右侧的"⚙️"图标按钮配置
- 配置会保存到注册表，下次自动使用
- 支持测试连接功能，验证账号是否有效
- 密码使用Base64编码存储，非明文
- 固定使用生产环境
- 未配置时查询会自动提示

详细说明请参考：[账号密码配置说明.md](账号密码配置说明.md)

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
A: 参考"打包优化说明.md"文档进行优化，可减小到30-60MB

### Q: 图标不显示？
A: 修改icon_res.qrc后需要重新运行 `pyrcc5 icon_res.qrc -o icon_res.py`

### Q: 查询失败？
A: 检查网络连接和账号密码是否正确

### Q: 虚拟环境激活失败？
A: PowerShell需要管理员权限或执行 `Set-ExecutionPolicy RemoteSigned`

## 更新日志

### v3.0.0 (2026-01-21) - 代码重构版本 🎉
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
- � 新增详细的重构文档（4个文档）
- ⚡ 减少重复代码80%，提升可维护性
- 🔧 统一接口管理，提升代码质量
- � 详见：[md/重构完成总结.md](md/重构完成总结.md)

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
