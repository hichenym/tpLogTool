# GitHub Actions 自动发布完整指南

## 📋 概述

本项目已配置 GitHub Actions 自动化工作流，可以在推送版本标签时自动完成：
- ✅ 更新版本号和编译日期
- ✅ 打包 Windows 可执行文件
- ✅ 创建 GitHub Release
- ✅ 上传 exe 和 version.json
- ✅ 从 version.py 自动提取更新日志
- ✅ 生成专业的发布说明

## 🚀 快速发布

### 方法一：使用快速发布脚本（最简单）⭐

```bash
python scripts/release.py
```

脚本会自动：
1. 检查 Git 状态
2. 显示当前版本和现有标签
3. 引导你输入新版本号
4. 创建并推送标签
5. 触发 GitHub Actions 自动构建

### 方法二：手动创建标签

```bash
# 1. 确保所有更改已提交
git add .
git commit -m "feat: 新功能描述"

# 2. 创建并推送标签
git tag v3.0.1
git push origin v3.0.1

# 3. 等待 GitHub Actions 自动构建（约 6-9 分钟）
```

## 📝 Release 说明自动生成

### 工作原理

GitHub Actions 会自动从 `query_tool/version.py` 的 `VERSION_HISTORY` 中提取对应版本的更新日志：

```python
VERSION_HISTORY = """
V3.0.1 (20260225)
- 🐛 修复某个问题
- ✨ 新增某个功能

V3.0.0 (20260224)
- 🔐 账号配置系统全面升级
- ✨ 智能提示系统
...
"""
```

### 生成的 Release 说明格式

```markdown
## 🎉 查询工具 V3.0.1

**编译日期**: 2026-02-25
**文件大小**: 168.10 MB

### 📦 下载
- [查询工具.exe](下载链接)
- [version.json](下载链接)

### 📝 更新说明

{从 version.py 自动提取的完整更新日志}

### 🚀 使用方法
1. 下载 `查询工具.exe`
2. 直接运行（无需安装）
3. 首次运行请配置账号信息

### 📚 文档
- [快速开始指南](链接)
- [完整文档](链接)

---
*此版本由 GitHub Actions 自动构建和发布*
```

### 维护建议

1. **保持格式一致**：确保每个版本的格式为 `V{major}.{minor}.{patch} ({date})`
2. **使用表情符号**：🎉 重大更新、✨ 新功能、🐛 Bug修复、🔧 技术改进
3. **发布前检查**：确保 version.py 中已添加新版本的更新日志
4. **发布后编辑**：如需修改，在 GitHub Release 页面点击编辑按钮
2. **设置 Python 环境** - Python 3.10 + pip 缓存
3. **安装依赖** - 从 requirements.txt 安装
4. **提取版本号** - 从标签提取版本信息（v3.0.1 → 3.0.1）
5. **更新 version.py** - 自动更新版本号和编译日期
6. **打包可执行文件** - 使用 PyInstaller 打包
7. **计算文件大小** - 获取 exe 文件大小
8. **生成 version.json** - 创建版本信息文件
9. **创建 Release** - 上传文件并生成发布说明
10. **提交 version.json** - 将版本文件提交回仓库

## 📄 生成的文件

### version.json 格式
```json
{
  "version": "3.0.1",
  "build_date": "20260224",
  "download_url": "https://github.com/用户名/仓库名/releases/download/v3.0.1/查询工具.exe",
  "file_size_mb": 168.06,
  "release_notes_url": "https://github.com/用户名/仓库名/releases/tag/v3.0.1",
  "min_version": "3.0.0",
  "changelog": [
    "请查看 Release 页面获取完整更新日志"
  ]
}
```

### Release 资产
- `查询工具.exe` - Windows 可执行文件
- `version.json` - 版本信息文件（供自动更新使用）

## 🔍 查看构建状态

### 方法一：Actions 页面
1. 进入仓库的 **Actions** 标签
2. 查看最新的 **Build and Release** 工作流
3. 点击查看详细日志

### 方法二：徽章（可选）
在 README.md 中添加状态徽章：
```markdown
![Build Status](https://github.com/用户名/仓库名/actions/workflows/release.yml/badge.svg)
```

## ⚠️ 注意事项

### 版本号规范
- 必须使用 `v` 前缀：`v3.0.1` ✅
- 不能省略 `v`：`3.0.1` ❌
- 建议使用语义化版本：`主版本.次版本.修订号`

### 标签管理
```bash
# 查看所有标签
git tag

# 删除本地标签
git tag -d v3.0.1

# 删除远程标签
git push origin :refs/tags/v3.0.1

# 重新创建标签（如果需要）
git tag v3.0.1
git push origin v3.0.1
```

### 构建失败处理
如果构建失败：
1. 查看 Actions 日志找到错误原因
2. 修复问题后提交代码
3. 删除失败的标签
4. 重新创建并推送标签

## 🎯 最佳实践

### 发布前检查清单
- [ ] 本地测试通过
- [ ] 更新 version.py 中的 VERSION_HISTORY
- [ ] 更新 README.md（如有必要）
- [ ] 更新相关文档
- [ ] 提交所有更改
- [ ] 创建并推送标签

### 版本号策略
- **主版本号（Major）**：重大功能更新或架构变更
- **次版本号（Minor）**：新增功能或较大改进
- **修订号（Patch）**：Bug 修复或小改进

示例：
- `v3.0.0` → `v3.0.1`：Bug 修复
- `v3.0.1` → `v3.1.0`：新增功能
- `v3.1.0` → `v4.0.0`：重大更新

## 🔧 自定义配置

### 修改构建环境
编辑 `.github/workflows/release.yml`：
```yaml
- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: '3.11'  # 修改 Python 版本
```

### 修改 Release 说明
编辑 `body` 部分：
```yaml
body: |
  ## 🎉 自定义标题
  
  自定义内容...
```

### 添加更多资产
在 `files` 部分添加：
```yaml
files: |
  dist/查询工具.exe
  version.json
  README.md
  docs/*.md
```

## 📊 构建时间

典型构建时间：
- 环境准备：1-2 分钟
- 依赖安装：2-3 分钟
- 打包构建：2-3 分钟
- 上传发布：1 分钟
- **总计**：约 6-9 分钟

## 🆘 常见问题

### Q: 构建失败提示权限错误
A: 确保仓库设置中启用了 Actions 写权限：
   Settings → Actions → General → Workflow permissions → Read and write permissions

### Q: version.json 没有提交到仓库
A: 这是正常的，如果 main 分支受保护，推送会失败。version.json 已经上传到 Release，不影响使用。

### Q: 如何修改已发布的 Release
A: 进入 Releases 页面，点击 Release 右侧的编辑按钮，可以修改说明和上传新文件。

### Q: 能否在本地测试 Actions
A: 可以使用 [act](https://github.com/nektos/act) 工具在本地运行 GitHub Actions。

## 📚 相关文档

- [GitHub Actions 官方文档](https://docs.github.com/en/actions)
- [PyInstaller 文档](https://pyinstaller.org/)
- [语义化版本规范](https://semver.org/lang/zh-CN/)

---

**最后更新**: 2026-02-24
