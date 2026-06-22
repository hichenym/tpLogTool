# 脚本工具说明

本目录包含项目当前使用的构建与清理脚本。

## 脚本列表

### 1. `build.py` - PyInstaller 打包脚本

**用途**：将 Python 项目打包为独立的 Windows 可执行文件。

**功能**：

- 自动写入 `query_tool/version.py` 中的 `BUILD_DATE`
- 使用 PyInstaller 生成单文件 `exe`
- 自动包含 OCR、ONNX、OpenCV、SDK DLL 等依赖
- 输出固定文件名 `TPQueryTool.exe`

**使用方法**：

```bash
python scripts/build.py
python scripts/build.py --debug
```

**输出**：

- `dist/TPQueryTool.exe` - 最终可执行文件
- `build/` - PyInstaller 中间目录
- `TPQueryTool.spec` - PyInstaller 生成的 spec 文件

**依赖**：

- PyInstaller
- setuptools
- 所有运行依赖（见 `requirements.txt`）

**说明**：

- `--debug`：保留控制台窗口，便于排查启动问题
- 正常打包默认关闭控制台窗口

### 2. `clean.py` - 清理脚本

**用途**：清理当前 PyInstaller 打包方案产生的构建产物和 Python 缓存。

**功能**：

- 删除 `__pycache__` 目录
- 删除 `.pyc/.pyo/.pyd` 文件
- 删除 `build/`、`dist/`
- 删除 `.egg-info/`、`.eggs/`
- 删除 `.spec`、`.coverage*`
- 删除 `.pytest_cache/`、`htmlcov/`

**使用方法**：

```bash
python scripts/clean.py
```

## 常见命令

### 快速打包

```bash
python scripts/clean.py
python scripts/build.py
```

### 仅清理缓存和构建产物

```bash
python scripts/clean.py
```

## 依赖要求

### `build.py` 依赖

- PyInstaller
- setuptools
- 所有运行依赖（见 `requirements.txt`）

### `clean.py` 依赖

- Python 3.9+
- 无额外第三方依赖

### 安装依赖

```bash
pip install -r requirements.txt
```

## 相关文档

- [快速开始](../docs/quick-start.md)
- [构建指南](../docs/build-guide.md)
- [项目结构](../docs/modules-guide.md)

最后更新：2026-06-22
