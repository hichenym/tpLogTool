# 打包说明

## 打包方案

当前项目使用 **Nuitka** 进行 Windows 单文件打包，入口脚本为 `scripts/build.py`。

## 快速打包

### 推荐方式

```bash
python scripts/build.py
```

调试模式：

```bash
python scripts/build.py --debug
```

脚本会自动：
1. 更新 `query_tool/version.py` 中的 `BUILD_DATE`
2. 读取当前版本号
3. 清理旧的 Nuitka 构建目录
4. 调用 Nuitka 生成单文件 exe
5. 输出打包结果和文件大小

## 打包前检查清单

在打包前，请确认：

- [ ] 代码已测试通过
- [ ] 版本号已更新（query_tool/version.py）
- [ ] 版本历史已更新（query_tool/version.py）
- [ ] 所有文档已更新
- [ ] 代码已提交到Git
- [ ] 虚拟环境已激活
- [ ] 已清理编译文件（运行 `python scripts/clean.py`）
- [ ] 程序能正常运行（python run.py）

## 版本号更新

### 当前版本结构

```python
# query_tool/version.py
VERSION_MAJOR = 3  # 主版本号
VERSION_MINOR = 0  # 次版本号
VERSION_PATCH = 0  # 修订号
BUILD_DATE = "20260207"  # 编译日期
```

### 版本号规则

- **主版本号（MAJOR）**：重大功能更新或架构变更
- **次版本号（MINOR）**：新增功能或较大改进
- **修订号（PATCH）**：Bug修复或小改进
- **编译日期（BUILD_DATE）**：自动生成，格式 YYYYMMDD

### 更新步骤

1. 修改 `query_tool/version.py` 中的版本号
2. 更新 `VERSION_HISTORY` 添加更新说明
3. 运行 `python scripts/build.py` 自动更新编译日期并打包

## 打包依赖

打包前请确保：

- 已安装项目运行依赖：`pip install -r requirements.txt`
- 已安装 Nuitka 相关依赖：

```bash
pip install nuitka ordered-set zstandard
```

- 已安装可用的 C 编译器：
  - MinGW64（推荐）
  - 或 MSVC Build Tools

## Nuitka 关键参数说明

`scripts/build.py` 当前核心参数包括：

- `--standalone`：独立发布
- `--onefile`：打包成单文件 exe
- `--output-dir=dist`：输出到 `dist/`
- `--output-filename=TPQueryTool.exe`：固定输出文件名
- `--enable-plugin=pyqt5`：启用 PyQt5 支持
- `--windows-console-mode=disable`：默认隐藏控制台
- `--windows-console-mode=force`：调试模式显示控制台

## 打包输出

### 目录结构

```
.
├── dist/               # 打包输出目录
│   └── TPQueryTool.exe # 最终可执行文件
├── run.build/          # Nuitka 构建目录
├── run.dist/           # Nuitka 中间目录
└── run.onefile-build/  # Nuitka 单文件构建目录
```

### 文件大小

- 预期大小：约 60-80 MB
- 如果超过 100 MB，可能包含了不必要的依赖

## 打包优化

### 1. 清理编译文件

```bash
# 清除 __pycache__、*.pyc、build、dist 等编译生成的文件
python scripts/clean.py
```

这可以确保打包时不会包含旧的编译文件，减小最终的 exe 体积。

### 2. 使用干净的虚拟环境

```bash
# 创建专门用于打包的虚拟环境
python -m venv venv_build
.\venv_build\Scripts\activate

# 只安装必需的包
pip install -r requirements.txt

# 打包
python scripts/build.py
```

### 3. 使用干净的打包环境

建议单独使用打包虚拟环境，避免把不必要的依赖带入编译结果。

## 常见问题

### Q1: 打包失败，提示未安装 Nuitka

**解决**：

```bash
pip install nuitka ordered-set zstandard
```

### Q2: 打包失败，提示缺少 C 编译器

**解决**：安装 MinGW64 或 MSVC Build Tools。

### Q3: 打包后图标不显示

**原因**：图标文件路径错误或格式不正确

**解决**：
1. 确保 `resources/icons/app/logo.ico` 文件存在
2. 确保是标准的 .ico 格式
3. 重新生成资源文件：`pyrcc5 resources/icon_res.qrc -o resources/icon_res.py`

### Q4: 编译日期没有更新

**原因**：未使用自动打包脚本

**解决**：使用 `python scripts/build.py` 自动更新编译日期

## 测试打包结果

### 1. 基础测试

```bash
# 运行打包后的程序
.\dist\TPQueryTool.exe
```

### 2. 功能测试

- [ ] 程序能正常启动
- [ ] 界面显示正常
- [ ] 图标显示正常
- [ ] 版本号显示正确
- [ ] 记录页查询功能正常
- [ ] 记录页双击 SN 查看设备信息正常
- [ ] 配置读写正常
- [ ] 运维账号配置正常
- [ ] 固件账号配置正常
- [ ] 日志配置正常
- [ ] 查询功能正常
- [ ] 唤醒功能正常
- [ ] 导出功能正常
- [ ] 固件管理功能正常

### 3. 兼容性测试

- [ ] Windows 10 测试
- [ ] Windows 11 测试
- [ ] 不同分辨率测试
- [ ] 不同DPI设置测试

## 发布流程

### 1. 准备发布

```bash
# 1. 更新版本号
# 编辑 query_tool/version.py

# 2. 更新文档
# 编辑 README.md 等文档

# 3. 提交代码
git add .
git commit -m "Release V3.0.0"
git push

# 4. 创建标签
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

### 2. 打包发布

```bash
# 1. 激活虚拟环境
.\venv\Scripts\activate

# 2. 自动打包
python scripts/build.py

# 3. 测试打包结果
.\dist\查询工具.exe

# 4. 重命名文件（可选）
# 例如：查询工具_v2.0.0.exe
```

### 3. 上传发布

1. 在 GitHub 上创建 Release
2. 上传打包后的 exe 文件
3. 填写更新说明（从 version.py 复制）
4. 发布 Release

## 版本历史

### V3.0.0 (2026-02-07)
- 🔐 账号配置系统全面升级
  * 运维账号和固件账号独立配置管理
  * 使用标签页分离两个系统的账号配置
  * 支持灵活配置：允许全部为空或只配置一个平台
  * 未配置时智能提示并可直接跳转到对应标签页
  * 移除固件系统硬编码账号密码
- 📝 日志记录系统
  * 支持调试信息记录到文件
  * 日志文件按日期命名，自动轮转
  * 可在设置页面启用/禁用，实时生效
  * 完善核心模块日志记录
- 🎨 界面优化
  * 设置对话框使用标签页设计
  * 账号配置使用滚动布局
  * 每个账号组独立的验证按钮
- 🔧 技术改进
  * 固件账号配置保存到独立注册表键
  * Session缓存管理优化
  * 全局异常处理和日志记录

### v2.0.0 (2026-01-22)
- 🏗️ 重大重构：项目结构完全重组
  * 源代码集中在 query_tool/ 包
  * 资源文件集中在 resources/
  * 文档集中在 docs/
  * 脚本集中在 scripts/
  * 所有导入路径统一为 query_tool.* 格式
- ✨ 新增 GitLab 日志导出功能
  * 支持连接 GitLab 服务器
  * 支持按项目、分支、提交者筛选
  * 支持时间范围筛选
  * 支持关键词高亮导出
  * 导出为 Excel 文件（带超链接）
  * 记录最近使用的项目和分支
- � 改进
  * 图标资源路径更新为 :/icons/
  * 启动脚本 run.py 支持直接运行
  * 打包脚本更新为新的项目结构
  * 注册表名称更新为 TPQueryTool
  * 所有文档更新以反映新的项目结构
- � 文档完善
  * 13个核心文档完整覆盖所有功能
  * 详细的模块使用指南
  * 完整的打包和发布流程说明

### v1.3.0 (2026-01-22)
- ✨ 新增 GitLab 日志导出功能
- 🏗️ 完成项目结构重组（方案B）
- 📦 源代码集中在 query_tool/
- 🎨 资源文件集中在 resources/
- 📚 文档集中在 docs/
- 🔧 脚本集中在 scripts/

### v1.1.1 (2026-01-17)
- 🐛 修复重复定义save_account_config函数的问题
- 🔧 改进异常处理，使用具体异常类型
- 🛡️ 增强线程清理机制，防止崩溃
- ⏱️ 添加网络请求超时（5秒）
- 📝 优化错误日志输出
- 💪 提升代码健壮性和稳定性

### v1.1.0 (2026-01-17)
- ✨ 新增账号密码配置功能
- ✨ 新增设置界面
- 🔒 密码Base64编码存储
- 🔐 移除硬编码默认账号密码

### v1.0.0 (2026-01-15)
- 🎉 初始版本发布

## 相关文档

- [README.md](../README.md) - 项目说明
- [version-guide.md](version-guide.md) - 版本管理详细说明
- [account-config-guide.md](account-config-guide.md) - 账号配置指南
- [settings-guide.md](settings-guide.md) - 设置功能使用指南

---

**最后更新**: 2026-02-07  
**维护者**: Kiro AI Assistant
