# 图标资源说明

本目录包含应用程序使用的所有图标资源，按功能分组管理。

## 📁 目录结构

```
icon/
├── app/              # 应用图标
│   ├── logo.png      # 应用Logo (PNG格式)
│   └── logo.ico      # 应用图标 (ICO格式，用于窗口标题栏)
│
├── common/           # 通用操作图标
│   ├── search.png    # 查询按钮
│   ├── clean.png     # 清空按钮
│   ├── export.png    # 导出按钮
│   └── save.png      # 保存按钮 (预留)
│
├── device/           # 设备操作图标
│   ├── werk_up.png       # 单个设备唤醒
│   └── werk_up_all.png   # 批量设备唤醒
│
├── system/           # 系统设置图标
│   ├── setting.png   # 设置按钮
│   ├── device.png    # 设备页面图标
│   ├── user.png      # 账号页面图标
│   └── git.png       # GIT页面图标
│
└── gitlab/           # GitLab功能图标
    ├── gitlab.png    # GitLab Logo
    ├── connect.png   # 连接服务器
    ├── disconnect.png # 断开连接
    ├── browser.png   # 浏览文件
    └── export.png    # 导出日志
```

## 🎨 图标使用说明

### 应用图标 (app/)
- **logo.png**: 主窗口图标，显示在任务栏和窗口标题栏
- **logo.ico**: Windows 应用程序图标

### 通用操作 (common/)
- **search.png**: 用于"查询"按钮（状态页、设备页）
- **clean.png**: 用于"清空"按钮（状态页）
- **export.png**: 用于"导出"按钮（状态页）
- **save.png**: 预留，暂未使用

### 设备操作 (device/)
- **werk_up.png**: 单个设备唤醒按钮（状态页表格中）
- **werk_up_all.png**: 批量唤醒按钮（状态页）

### 系统设置 (system/)
- **setting.png**: 设置按钮（主窗口菜单栏右侧）
- **device.png**: 设备页面图标（菜单按钮）
- **user.png**: 账号页面图标（菜单按钮）
- **git.png**: GIT页面图标（菜单按钮）

### GitLab功能 (gitlab/)
- **gitlab.png**: GitLab Logo
- **connect.png**: 连接GitLab服务器按钮
- **disconnect.png**: 断开连接按钮
- **browser.png**: 浏览文件按钮
- **export.png**: 导出日志按钮

## 📝 使用方法

在代码中引用图标时，使用 Qt 资源系统路径：

```python
# 应用图标
QIcon(":/icon/app/logo.png")

# 通用操作
QIcon(":/icon/common/search.png")
QIcon(":/icon/common/clean.png")
QIcon(":/icon/common/export.png")

# 设备操作
QIcon(":/icon/device/werk_up.png")
QIcon(":/icon/device/werk_up_all.png")

# 系统设置
QIcon(":/icon/system/setting.png")
QIcon(":/icon/system/device.png")
QIcon(":/icon/system/user.png")
QIcon(":/icon/system/git.png")

# GitLab功能
QIcon(":/icon/gitlab/gitlab.png")
QIcon(":/icon/gitlab/connect.png")
QIcon(":/icon/gitlab/disconnect.png")
QIcon(":/icon/gitlab/browser.png")
QIcon(":/icon/gitlab/export.png")
```

## 🔄 添加新图标

1. 将图标文件放入对应的分组目录
2. 在 `icon_res.qrc` 文件中添加引用
3. 运行命令重新编译资源文件：
   ```bash
   pyrcc5 icon_res.qrc -o icon_res.py
   ```
4. 在代码中使用新图标

## 📐 图标规范

- **格式**: PNG (推荐) 或 ICO
- **尺寸**: 
  - 按钮图标: 16x16 或 18x18 像素
  - 应用图标: 32x32, 48x48, 256x256 (多尺寸)
- **背景**: 透明背景
- **颜色**: 适配深色主题，建议使用浅色图标
