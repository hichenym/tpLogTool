# 功能总结

## 项目概述

`tpLogTool` 是一个基于 `PyQt5` 的 Windows 桌面工具，面向设备运维、固件管理、GitLab 日志导出和错误记录查询场景。

当前主要页面：

- 设备
- 固件
- GitLab日志
- 记录

## 当前核心功能

### 1. 设备页面

- 支持按 SN / ID 批量查询设备
- 展示设备名称、型号、SN、ID、密码、版本号、在线状态等信息
- 支持批量唤醒、批量重启、批量升级、电池采集等操作
- 支持导出结果

### 2. 固件页面

- 支持固件查询、筛选、编辑等功能
- 使用独立的固件账号配置

### 3. GitLab日志页面

- 支持 GitLab 提交记录查询
- 支持按项目、分支、提交者、时间范围筛选
- 支持导出 Excel

### 4. 记录页面

- 支持按设备SN、型号、版本、模块、错误码、时间范围筛选错误记录
- 无筛选条件时禁止直接查询，避免接口报错
- 支持分页浏览记录
- 结果表格中可双击 `设备SN` 打开设备信息弹窗
- 设备信息弹窗支持双击复制字段内容

### 5. 通用能力

- 运维账号 / 固件账号独立配置
- 主题切换
- 状态栏消息提示
- 自动更新检查与下载
- 可选文件日志

## 主要技术实现

### UI 架构

- `query_tool/main.py`：主窗口、菜单、状态栏、页面切换
- `query_tool/pages/`：各功能页面
- `query_tool/widgets/`：通用弹窗和控件

### 工具模块

- `config.py`：注册表配置管理
- `device_query.py`：设备相关接口封装
- `error_record_api.py`：错误记录查询接口
- `thread_manager.py`：后台线程管理
- `style_manager.py` / `theme_manager.py`：主题与样式管理
- `update_manager.py`：更新流程管理

### 打包与发布

- 当前本地打包使用 `Nuitka`
- 发布脚本位于 `scripts/release.py`
- 可使用 `scripts/verify_protection.py` 校验打包产物

## 当前功能特点

- 页面通过 `PageRegistry` 注册
- 多数耗时操作通过 `QThread` 在后台执行
- 设备信息、错误记录、GitLab 日志等功能已形成独立页面
- 已支持较完整的 Windows 桌面运维工具工作流

## 后续建议方向

- 进一步统一页面中的线程模型
- 提升配置存储安全性
- 优化文档与实现同步机制
- 将页面业务逻辑逐步下沉到 service 层

## 说明

本文档仅保留当前功能概览与架构说明，不再记录历史实现过程、代码片段和详细改动统计。
    
    def on_test_connection(self):
        """测试连接（根据当前标签页）"""
        current_tab = self.tab_widget.currentIndex()
        
        if current_tab == 0:  # 运维账号
            username = self.device_username_input.text().strip()
            password = self.device_password_input.text().strip()
            # 测试运维系统连接
            query = DeviceQuery('pro', username, password, use_cache=False)
            if query.token:
                self.main_window.show_success("运维账号验证成功！")
        else:  # 固件账号
            username = self.firmware_username_input.text().strip()
            password = self.firmware_password_input.text().strip()
            # 测试固件系统连接
            success, message = test_firmware_login(username, password)
            if success:
                self.main_window.show_success("固件账号验证成功！")
    
    def on_save(self):
        """保存配置（支持灵活配置）"""
        device_username = self.device_username_input.text().strip()
        device_password = self.device_password_input.text().strip()
        firmware_username = self.firmware_username_input.text().strip()
        firmware_password = self.firmware_password_input.text().strip()
        
        # 验证：单个平台的账号密码必须同时填写或同时为空
        if (device_username and not device_password) or (not device_username and device_password):
            self.main_window.show_warning("运维账号和密码必须同时填写或同时为空")
            return
        
        if (firmware_username and not firmware_password) or (not firmware_username and firmware_password):
            self.main_window.show_warning("固件账号和密码必须同时填写或同时为空")
            return
        
        # 保存配置
        device_saved = save_account_config('pro', device_username, device_password)
        firmware_saved = save_firmware_account_config(firmware_username, firmware_password)
        
        if device_saved and firmware_saved:
            self.main_window.show_success("配置已保存！")
            self.accept()
```

### 3. 未配置提示（v1.2.0）

```python
# 设备页面 - 运维账号未配置
env, username, password = get_account_config()
if not username or not password:
    msg_box = QMessageBox(self)
    msg_box.setWindowTitle('提示')
    msg_box.setText('检测到运维系统账号信息未配置，点击OK前往配置。')
    msg_box.setIcon(QMessageBox.Information)
    msg_box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    
    # 自定义按钮图标
    ok_btn = msg_box.button(QMessageBox.Ok)
    ok_btn.setText("")
    ok_btn.setIcon(QIcon(":/icons/common/ok.png"))
    ok_btn.setFixedSize(60, 32)
    
    reply = msg_box.exec_()
    if reply == QMessageBox.Ok:
        dialog = SettingsDialog(self.window())
        dialog.tab_widget.setCurrentIndex(0)  # 切换到运维账号标签页
        dialog.exec_()

# 固件页面 - 固件账号未配置
firmware_username, firmware_password = get_firmware_account_config()
if not firmware_username or not firmware_password:
    msg_box = QMessageBox(self)
    msg_box.setWindowTitle('提示')
    msg_box.setText('检测到固件系统账号信息未配置，点击OK前往配置。')
    msg_box.setIcon(QMessageBox.Information)
    msg_box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    
    # 自定义按钮图标
    ok_btn = msg_box.button(QMessageBox.Ok)
    ok_btn.setText("")
    ok_btn.setIcon(QIcon(":/icons/common/ok.png"))
    ok_btn.setFixedSize(60, 32)
    
    reply = msg_box.exec_()
    if reply == QMessageBox.Ok:
        dialog = SettingsDialog(self.window())
        dialog.tab_widget.setCurrentIndex(1)  # 切换到固件账号标签页
        dialog.exec_()
```

### 4. 固件API集成（v1.2.0）

```python
# query_tool/utils/firmware_api.py
def get_firmware_credentials():
    """从配置获取固件账号密码"""
    from .config import get_firmware_account_config
    username, password = get_firmware_account_config()
    
    # 如果配置为空，返回空值（不再使用默认值）
    if not username or not password:
        return "", ""
    
    return username, password

def login(force_new=False):
    """执行登录操作"""
    USERNAME, PASSWORD = get_firmware_credentials()
    
    # 检查账号密码是否配置
    if not USERNAME or not PASSWORD:
        print("固件账号未配置，请在设置页面配置固件账号")
        # 清除缓存的 session
        clear_session_cache()
        return None
    
    # 登录逻辑...
```

## 测试验证

### 1. 功能测试（v1.2.0）

- ✅ 运维账号配置读取正常
- ✅ 固件账号配置读取正常
- ✅ 配置保存正常
- ✅ 密码编码/解码正常
- ✅ 标签页切换正常
- ✅ 标签页样式正常
- ✅ 测试连接功能正常（两个系统）
- ✅ 未配置提示正常
- ✅ 灵活配置验证正常

### 2. 集成测试（v1.2.0）

- ✅ 设备页面使用运维账号配置正常
- ✅ 固件页面使用固件账号配置正常
- ✅ 未配置时弹窗提示正常
- ✅ 点击OK跳转到对应标签页正常
- ✅ 配置修改后立即生效

### 3. 兼容性测试（v1.2.0）

- ✅ 首次使用（无配置）正常
- ✅ 已有配置正常读取
- ✅ 只配置一个平台正常
- ✅ 配置全部为空正常
- ✅ 不同用户配置隔离

## 安全考虑

### 1. 密码存储

- ✅ 使用Base64编码（非明文）
- ⚠️ Base64不是加密，只是编码
- 💡 建议：不要在共享电脑上保存敏感账号

### 2. 权限控制

- ✅ 配置保存在当前用户注册表
- ✅ 不同用户配置互不影响
- ✅ 需要用户权限才能修改

### 3. 改进建议

如需更高安全性，可以考虑：
- 使用Windows DPAPI加密
- 使用AES加密存储
- 添加主密码保护

## 用户文档

### 1. 使用说明（v1.2.0）

- ✅ README.md 已更新
- ✅ account-config-guide.md（账号配置指南）
- ✅ settings-guide.md（设置功能使用指南）
- ✅ features-summary.md（功能实现总结）

### 2. 版本信息（v1.2.0）

- ✅ version.py 已更新到 v1.2.0
- ✅ 版本历史已添加新功能说明
- ✅ 文档更新日期：2026-02-07

## 后续优化建议

### 1. 功能增强

- [ ] 支持多账号配置
- [ ] 账号快速切换
- [ ] 记住密码选项
- [ ] 自动登录功能
- [ ] 配置导入/导出

### 2. 安全增强

- [ ] 密码加密存储（DPAPI/AES）
- [ ] 主密码保护
- [ ] 登录日志记录
- [ ] 密码强度检查
- [ ] 会话超时管理

### 3. 用户体验

- [ ] 配置备份/恢复
- [ ] 快捷键支持（Ctrl+,）
- [ ] 设置界面记住位置
- [ ] 账号配置历史记录
- [ ] 批量账号管理

### 4. 错误处理

- [ ] 网络异常重试
- [ ] Token过期自动刷新
- [ ] 配置损坏自动修复
- [ ] 详细错误日志
- [ ] 连接状态监控

## 总结

本次更新（v1.2.0）成功实现了运维账号和固件账号的独立配置管理，主要特点：

1. **双系统支持**：运维系统和固件系统账号独立配置，互不干扰
2. **标签页设计**：使用标签页分离两个系统的配置，界面清晰
3. **灵活配置**：允许全部为空或只配置一个平台，满足不同使用场景
4. **智能提示**：未配置时弹窗提示并可直接跳转到对应标签页
5. **安全可靠**：密码编码存储，用户隔离，session缓存管理
6. **文档完善**：提供详细使用说明和技术文档

该功能有效解决了固件系统账号硬编码的问题，提升了程序的可维护性和用户体验。

## 版本信息

- **版本号**：v1.2.0
- **发布日期**：2026-02-07
- **开发者**：Kiro AI Assistant
- **测试状态**：✅ 已通过测试

## 更新历史

### v1.2.0 (2026-02-07)
- ✅ 实现运维账号和固件账号独立配置
- ✅ 使用标签页分离两个系统的配置
- ✅ 支持灵活配置（全部为空或只配置一个平台）
- ✅ 未配置时智能提示并跳转到对应标签页
- ✅ 移除固件系统硬编码账号密码
- ✅ 更新相关文档

### v1.1.1 (2026-01-17)
- ✅ 实现账号密码配置功能
- ✅ 支持默认账号和自定义账号切换
- ✅ 添加测试连接功能
- ✅ 固定使用生产环境
