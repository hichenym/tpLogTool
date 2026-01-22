# 版本管理指南

## 版本号规范

本项目采用语义化版本号（Semantic Versioning）：`主版本.次版本.修订号`

### 版本号说明

- **主版本号（MAJOR）**：重大功能更新或架构变更，可能不向后兼容
  - 例如：1.0.0 → 2.0.0
  - 场景：重构代码、更换框架、重大功能变更

- **次版本号（MINOR）**：新增功能或较大改进，向后兼容
  - 例如：1.0.0 → 1.1.0
  - 场景：新增功能模块、性能优化、UI改进

- **修订号（PATCH）**：Bug修复或小改进，向后兼容
  - 例如：1.0.0 → 1.0.1
  - 场景：修复Bug、文档更新、小优化

- **编译日期（BUILD_DATE）**：格式为 YYYYMMDD
  - 自动生成，表示打包时的日期
  - 例如：20260115 表示 2026年1月15日

### 完整版本示例

```
V1.0.0 (20260115)
│ │ │   └─ 编译日期
│ │ └───── 修订号
│ └─────── 次版本号
└───────── 主版本号
```

## 版本更新流程

### 1. 修改版本号

编辑 `version.py` 文件：

```python
VERSION_MAJOR = 1  # 根据更新类型修改
VERSION_MINOR = 0  # 根据更新类型修改
VERSION_PATCH = 0  # 根据更新类型修改
```

### 2. 更新版本历史

在 `version.py` 的 `VERSION_HISTORY` 中添加更新说明：

```python
VERSION_HISTORY = """
V1.1.0 (20260120)
- 新增批量导入功能
- 优化查询性能
- 修复唤醒失败的问题

V1.0.0 (20260115)
- 初始版本发布
"""
```

### 3. 自动打包

使用自动打包脚本：

```bash
python build.py
```

脚本会自动：
- 更新编译日期为当前日期
- 显示版本信息供确认
- 执行打包命令

### 4. 手动打包（可选）

如果不使用自动脚本，需要手动更新编译日期：

```python
# 在 version.py 中手动修改
BUILD_DATE = "20260120"  # 改为当前日期
```

然后执行打包：

```bash
pyinstaller 设备查询工具.spec --clean
```

## 版本发布检查清单

发布新版本前，请确认以下事项：

- [ ] 版本号已更新（version.py）
- [ ] 版本历史已更新（version.py）
- [ ] README.md 已更新
- [ ] 所有功能已测试
- [ ] 已修复已知Bug
- [ ] 代码已提交到Git
- [ ] 已创建Git标签（如 v1.0.0）
- [ ] 已打包生成exe文件
- [ ] 已测试打包后的exe
- [ ] 已上传到GitHub Releases

## 版本号更新示例

### 场景1：修复Bug

```python
# 修改前
VERSION_MAJOR = 1
VERSION_MINOR = 0
VERSION_PATCH = 0

# 修改后
VERSION_MAJOR = 1
VERSION_MINOR = 0
VERSION_PATCH = 1  # 修订号+1
```

### 场景2：新增功能

```python
# 修改前
VERSION_MAJOR = 1
VERSION_MINOR = 0
VERSION_PATCH = 5

# 修改后
VERSION_MAJOR = 1
VERSION_MINOR = 1  # 次版本号+1
VERSION_PATCH = 0  # 修订号归零
```

### 场景3：重大更新

```python
# 修改前
VERSION_MAJOR = 1
VERSION_MINOR = 5
VERSION_PATCH = 3

# 修改后
VERSION_MAJOR = 2  # 主版本号+1
VERSION_MINOR = 0  # 次版本号归零
VERSION_PATCH = 0  # 修订号归零
```

## Git标签管理

### 创建标签

```bash
# 创建带注释的标签
git tag -a v1.0.0 -m "发布版本 1.0.0"

# 推送标签到远程
git push origin v1.0.0

# 推送所有标签
git push origin --tags
```

### 查看标签

```bash
# 列出所有标签
git tag

# 查看标签详情
git show v1.0.0
```

### 删除标签

```bash
# 删除本地标签
git tag -d v1.0.0

# 删除远程标签
git push origin :refs/tags/v1.0.0
```

## 版本信息查看

### 在程序中查看

程序运行后，版本号显示在右下角状态栏

### 通过命令行查看

```bash
python version.py
```

输出示例：
```
版本号: V1.0.0 (20260115)
简短版本: V1.0.0
编译日期: 2026-01-15

版本历史:
V1.0.0 (20260115)
- 初始版本发布
...
```

## 常见问题

### Q: 编译日期没有自动更新？
A: 使用 `python build.py` 自动打包脚本，会自动更新编译日期

### Q: 如何在代码中获取版本信息？
A: 导入version模块：
```python
from version import get_version_string, get_short_version
print(get_version_string())  # V1.0.0 (20260115)
print(get_short_version())   # V1.0.0
```

### Q: 版本号显示不正确？
A: 确保已重新打包，旧的exe文件不会自动更新版本信息

### Q: 如何回退到旧版本？
A: 使用Git标签：
```bash
git checkout v1.0.0
```

## 最佳实践

1. **每次发布前更新版本号**
2. **详细记录版本历史**
3. **使用Git标签标记版本**
4. **测试后再发布**
5. **保持版本号连续性**
6. **遵循语义化版本规范**
