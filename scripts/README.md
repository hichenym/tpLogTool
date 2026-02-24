# 脚本工具说明

本目录包含项目的构建、打包和清理脚本。

## 脚本列表

### 1. build.py - 打包脚本

**用途**: 将 Python 项目打包为独立的 Windows 可执行文件

**功能**:
- 编译 PyQt5 资源文件
- 使用 PyInstaller 打包应用
- 生成单文件可执行程序
- 自动处理依赖和隐藏导入

**使用方法**:
```bash
python scripts/build.py
```

**输出**:
- `dist/run.exe` - 最终的可执行文件
- `build/` - 构建临时文件
- `run.spec` - PyInstaller 规范文件

**依赖**:
- PyInstaller
- pyrcc5 (PyQt5 资源编译器)

**配置参数**:
```python
# 修改以下参数可自定义打包行为
--onefile              # 生成单文件
--windowed             # 无控制台窗口
--icon=resources/icons/app/logo.ico  # 应用图标
--hidden-import=...    # 隐藏导入
--collect-all=...      # 收集所有数据
```

**常见问题**:
- Q: 打包失败，提示找不到模块？
  A: 检查 `--hidden-import` 参数是否包含所有必需的模块

- Q: 生成的 exe 文件很大？
  A: 这是正常的，包含了所有依赖。可使用 UPX 压缩

- Q: 运行 exe 时闪退？
  A: 检查 `build.py` 中的依赖配置是否完整

---

### 2. clean.py - 清理脚本

**用途**: 清理项目中的编译文件和缓存

**功能**:
- 删除 `__pycache__` 目录
- 删除 `.pyc` 文件
- 删除 `build/` 目录
- 删除 `dist/` 目录
- 删除 `.egg-info/` 目录
- 删除 `.spec` 文件

**使用方法**:
```bash
python scripts/clean.py
```

**清理内容**:
```
__pycache__/          # Python 缓存
*.pyc                 # 编译的 Python 文件
build/                # PyInstaller 构建目录
dist/                 # PyInstaller 输出目录
*.egg-info/           # 包信息目录
*.spec                # PyInstaller 规范文件
```

**输出示例**:
```
清理 __pycache__ 目录...
  删除: query_tool/__pycache__
  删除: query_tool/pages/__pycache__
  删除: query_tool/utils/__pycache__
  删除: query_tool/widgets/__pycache__

清理 .pyc 文件...
  删除: 0 个文件

清理 build/ 目录...
  删除: build/

清理 dist/ 目录...
  删除: dist/

清理 .egg-info/ 目录...
  删除: 0 个目录

清理 .spec 文件...
  删除: 0 个文件

清理完成！
磁盘空间释放: 45.2 MB
```

**安全特性**:
- ✅ 验证输出目录存在
- ✅ 检查磁盘空间
- ✅ 显示清理统计
- ✅ 错误处理

---

## 工作流程

### 开发流程

```bash
# 1. 开发和测试
python run.py

# 2. 清理缓存
python scripts/clean.py

# 3. 提交代码
git add .
git commit -m "..."
```

### 打包流程

```bash
# 1. 清理旧的构建文件
python scripts/clean.py

# 2. 打包应用
python scripts/build.py

# 3. 测试生成的 exe
dist/run.exe

# 4. 发布
# 将 dist/run.exe 上传到发布服务器
```

---

## 脚本配置

### build.py 配置

**修改图标**:
```python
'--icon=resources/icons/app/logo.ico'
```

**修改输出名称**:
```python
'--name=TPQueryTool'  # 改为你的应用名称
```

**添加隐藏导入**:
```python
'--hidden-import=your_module'
```

### clean.py 配置

**修改清理目录**:
编辑 `CLEANUP_PATTERNS` 列表

**修改最小磁盘空间检查**:
```python
MIN_DISK_SPACE = 10 * 1024 * 1024  # 10MB
```

---

## 常见命令

### 快速打包
```bash
python scripts/clean.py && python scripts/build.py
```

### 仅清理缓存
```bash
python scripts/clean.py
```

### 仅打包（保留旧文件）
```bash
python scripts/build.py
```

### 查看清理统计
```bash
python scripts/clean.py
# 输出会显示释放的磁盘空间
```

---

## 依赖要求

### build.py 依赖
- PyInstaller >= 5.0
- pyrcc5 (PyQt5 工具)
- 所有项目依赖（见 requirements.txt）

### clean.py 依赖
- Python 3.6+
- 无外部依赖

### 安装依赖
```bash
pip install -r requirements.txt
pip install pyinstaller
```

---

## 故障排除

### 问题 1: pyrcc5 找不到

**症状**: `pyrcc5: command not found`

**解决**:
```bash
# 方法 1: 使用 Python 模块
python -m PyQt5.pyrcc5 resources/icon_res.qrc -o resources/icon_res.py

# 方法 2: 安装 PyQt5 工具
pip install PyQt5-tools
```

### 问题 2: PyInstaller 打包失败

**症状**: `ModuleNotFoundError: No module named 'xxx'`

**解决**:
1. 检查 `--hidden-import` 参数
2. 确保所有依赖已安装
3. 尝试添加 `--collect-all=xxx`

### 问题 3: 生成的 exe 无法运行

**症状**: exe 启动后立即闪退

**解决**:
1. 检查依赖配置
2. 在命令行运行 exe 查看错误信息
3. 检查资源文件路径

### 问题 4: 清理脚本报错

**症状**: `Permission denied` 或 `Access denied`

**解决**:
1. 关闭所有 Python 进程
2. 以管理员身份运行脚本
3. 检查文件权限

---

## 最佳实践

### 打包前检查清单

- [ ] 所有代码已提交
- [ ] 版本号已更新
- [ ] 依赖已更新（requirements.txt）
- [ ] 资源文件已编译（icon_res.py）
- [ ] 测试通过
- [ ] 清理脚本已运行

### 打包后检查清单

- [ ] exe 文件可以启动
- [ ] 所有功能正常
- [ ] 图标显示正确
- [ ] 没有控制台窗口
- [ ] 文件大小合理

---

## 版本历史

### v2.0.0 (2026-01-22)
- 创建 build.py 和 clean.py
- 支持 PyInstaller 打包
- 自动清理编译文件
- 完整的错误处理

### v1.0.0 (初始版本)
- 基础脚本框架

---

## 相关文档

- [快速开始](../docs/quick-start.md)
- [构建指南](../docs/build-guide.md)
- [项目结构](../docs/modules-guide.md)

---

**最后更新**: 2026-01-22  
**版本**: v2.0.0
