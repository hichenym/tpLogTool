"""
版本信息管理模块
"""
from datetime import datetime

# 版本号配置
VERSION_MAJOR = 2  # 主版本号：重大功能更新或架构变更
VERSION_MINOR = 0  # 次版本号：新增功能或较大改进
VERSION_PATCH = 0  # 修订号：Bug修复或小改进

# 自动获取编译日期
BUILD_DATE = "20260122"

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
