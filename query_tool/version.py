"""
版本信息管理模块
"""
from datetime import datetime

# 版本号配置
VERSION_MAJOR = 3  # 主版本号：重大功能更新或架构变更
VERSION_MINOR = 1  # 次版本号：新增功能或较大改进
VERSION_PATCH = 0  # 修订号：Bug修复或小改进

# 自动获取编译日期
BUILD_DATE = "20260224"

def get_version():
    """获取版本号元组"""
    return (VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH)

def get_version_string():
    """获取完整版本字符串"""
    return f"V{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH} ({BUILD_DATE})"

def get_short_version():
    """获取简短版本号"""
    return f"V{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}"

def get_build_date():
    """获取编译日期"""
    return BUILD_DATE

def get_build_date_formatted():
    """获取格式化的编译日期"""
    year = BUILD_DATE[:4]
    month = BUILD_DATE[4:6]
    day = BUILD_DATE[6:8]
    return f"{year}-{month}-{day}"

# 版本历史
VERSION_HISTORY = """
V3.1.0 (20260224)
- � GitHub Actions 自动发布
  * 配置完整的 CI/CD 工作流
  * 推送版本标签自动触发构建
  * 自动打包 Windows 可执行文件
  * 自动创建 GitHub Release
  * 自动生成 version.json 供自动更新使用
  * 从 version.py 自动提取更新日志到 Release 说明
- 📦 自动更新模块设计
  * 完整的技术方案文档（三种主流方案对比）
  * 静默更新实现指南（后台检测、下载、延迟替换）
  * 绿色版程序替换策略（批处理脚本方案）
  * 支持多源下载和容错机制
- 🛠️ 开发工具优化
  * 新增快速发布脚本 scripts/release.py
  * 自动检查 Git 状态
  * 自动创建和推送版本标签
  * 友好的交互式发布流程
- 📚 文档体系完善
  * GitHub Actions 完整使用指南
  * 自动更新技术方案分析
  * 静默更新实现指南
  * 更新策略对比文档
  * 精简文档结构，提升可读性

V3.0.0 (20260207)
- 🔐 账号配置系统全面升级
  * 运维账号和固件账号独立配置管理
  * 使用标签页分离两个系统的账号配置
  * 支持灵活配置：允许全部为空或只配置一个平台
  * 单个平台的账号密码必须同时填写或同时为空
- ✨ 智能提示系统
  * 未配置账号时弹窗提示
  * 点击OK自动跳转到对应标签页（运维/固件）
  * 提示信息清晰明确，用户体验优化
- 🏗️ 代码结构优化
  * 移除固件系统硬编码账号密码
  * 固件API模块移至 query_tool/utils/firmware_api.py
  * 新增 FirmwareAccountConfig 数据类
  * 配置管理器统一管理所有账号配置
- 🎨 界面优化
  * 标签页样式优化：选中时背景色 #505050，未选中 #2b2b2b
  * 测试连接按钮根据当前标签页测试对应系统
  * 弹窗按钮使用图标（OK/Cancel），尺寸统一 60x32
- 📚 文档完善
  * 更新 account-config-guide.md（账号配置指南）
  * 更新 settings-guide.md（设置功能使用指南）
  * 更新 features-summary.md（功能实现总结）
  * 更新 README.md 最后更新日期
- 🔧 技术改进
  * 固件账号配置保存到独立注册表键
  * Session 缓存管理优化
  * 清除缓存功能完善

V2.0.0 (20260122)
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
- 🔧 改进
  * 图标资源路径更新为 :/icons/
  * 启动脚本 run.py 支持直接运行
  * 打包脚本更新为新的项目结构
  * 注册表名称更新为 TPQueryTool
  * 所有文档更新以反映新的项目结构
- 📚 文档完善
  * 13个核心文档完整覆盖所有功能
  * 详细的模块使用指南
  * 完整的打包和发布流程说明

V1.3.0 (20260122)
- 新增 GitLab 日志导出功能
  * 支持连接 GitLab 服务器
  * 支持按项目、分支、提交者筛选
  * 支持时间范围筛选
  * 支持关键词高亮导出
  * 导出为 Excel 文件（带超链接）
  * 记录最近使用的项目和分支
- 架构优化
  * 新增 GitLab API 封装模块
  * 新增 Excel 导出工具模块
  * 页面模块化架构完善
- 配置管理
  * GitLab 配置独立存储
  * Token 加密存储
  * 支持最近记录功能

V1.2.0 (20260122)
- 全面升级深色主题
  * 所有窗口和对话框标题栏使用深色主题
  * 优化状态栏样式，移除多余边框
  * 修复滚动条背景透明问题
  * 优化表格样式，支持单元格自定义颜色
- 新增状态消息系统
  * 图标+颜色组合，清晰区分消息类型
  * 信息（蓝色ℹ）、成功（绿色✓）、警告（橙色⚠）、错误（红色✗）、进度（青色⏳）
  * 自动定时清除消息
- 界面优化
  * 输入框之间添加分割线，视觉更清晰
  * 在线状态颜色保持：在线=绿色，离线=红色
  * 优化下拉框样式
- 功能改进
  * 单个唤醒和批量唤醒完成后统一显示设备统计信息
  * 单个唤醒添加进度提示
  * 优化唤醒流程的用户反馈

V1.1.1 (20260117)
- 修复重复定义save_account_config函数的问题
- 改进异常处理，使用具体异常类型替代bare except
- 增强线程清理机制，防止窗口关闭时崩溃
- 添加网络请求超时设置（5秒），防止无限等待
- 优化错误日志输出，便于调试
- 修复PhoneQueryWorker中的空指针检查
- 提升代码健壮性和稳定性

V1.1.0 (20260117)
- 新增账号密码配置功能
- 新增设置界面（菜单栏右侧）
- 新增测试连接功能
- 密码Base64编码存储到注册表
- 支持自定义环境（生产/测试）
- 优化菜单栏布局
- 移除硬编码默认账号密码，提升安全性

V1.0.0 (20260115)
- 初始版本发布
- 支持批量查询设备信息（SN/ID）
- 支持批量唤醒设备
- 支持导出CSV数据
- 配置保存到注册表
- 智能查询避免重复
- 操作时按钮状态管理
"""

if __name__ == "__main__":
    print(f"版本号: {get_version_string()}")
    print(f"简短版本: {get_short_version()}")
    print(f"编译日期: {get_build_date_formatted()}")
    print(f"\n版本历史:\n{VERSION_HISTORY}")
