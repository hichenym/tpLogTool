# 图标资源说明

本目录包含项目使用的图标资源，统一按功能归类到 `resources/icons` 下，避免在 `resources` 根目录散落图片文件。

## 目录结构

```text
resources/icons/
├── app/       # 应用图标
├── common/    # 通用按钮与状态图标
├── device/    # 设备相关功能图标
├── gitlab/    # GitLab 页面图标
└── system/    # 左侧页面入口图标
```

## 当前分组

### `app/`
- `logo.png`: 应用 Logo
- `logo.ico`: Windows 窗口与打包图标

### `common/`
- `search.png`: 查询
- `clean.png`: 清空
- `export.png`: 导出
- `save.png`: 保存
- `add.png`: 新增
- `delete.png`: 删除
- `edit.png`: 编辑
- `run.png`: 执行
- `send.png`: 发送
- `expand.png`: 展开/收起
- `timestamp.png`: 时间戳开关
- `connect.png`: 登录
- `connectting.png`: 连接中/取消
- `disconnect.png`: 注销
- `dir.png`: 目录选择
- `ok.png`: 确认
- `cancel.png`: 取消

### `device/`
- `battery.png`: 电池查询
- `collect.png`: 采集/命令入口
- `firmware.png`: 固件页面
- `nat.png`: NAT
- `reboot.png`: 重启
- `reflash.png`: 刷机
- `upgrade.png`: 升级
- `werk_up.png`: 单设备唤醒
- `werk_up_all.png`: 批量唤醒

### `gitlab/`
- `gitlab.png`: GitLab 页面
- `connect.png`: GitLab 连接
- `disconnect.png`: GitLab 断开
- `browser.png`: 浏览
- `export.png`: 导出

### `system/`
- `setting.png`: 设置页
- `device.png`: 设备页
- `git.png`: Git 页
- `user.png`: 账号页
- `record.png`: 记录页
- `console.png`: 调试页
- `cmd.png`: 命令页

## 使用方式

代码中统一使用 Qt 资源路径 `:/icons/...`：

```python
QIcon(":/icons/common/run.png")
QIcon(":/icons/common/edit.png")
QIcon(":/icons/system/console.png")
QIcon(":/icons/system/cmd.png")
```

## 新增图标流程

1. 将图标放入对应分类目录。
2. 在 `resources/icon_res.qrc` 中增加 `<file>` 项。
3. 重新生成 `resources/icon_res.py`：

```bash
pyrcc5 resources/icon_res.qrc -o resources/icon_res.py
```
