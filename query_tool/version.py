"""
版本信息管理模块
"""
from datetime import datetime

# 版本号配置
VERSION_MAJOR = 3  # 主版本号：重大功能更新或架构变更
VERSION_MINOR = 0  # 次版本号：新增功能或较大改进
VERSION_PATCH = 0  # 修订号：Bug修复或小改进

# 自动获取编译日期
BUILD_DATE = "20260225"

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

# 版本历史（仅记录用户感知的重要更新、功能改进和bug修复）
VERSION_HISTORY = """
V3.0.0 (20260225)
- 账号配置系统升级：运维账号和固件账号独立配置
- 自动更新功能：后台检测、下载、安装，支持静默/提示两种模式
- 文件哈希验证：确保下载文件完整性和安全性
- 固件查询Session超时优化：从2小时改为30分钟，提升稳定性
- 下载重试机制：10次重试，5秒间隔，提升网络不稳定环境下的成功率
- 界面优化：深色主题统一、状态栏实时显示、版本信息双击查看详情

V2.0.0 (20260122)
- 新增GitLab日志导出功能：支持按项目、分支、提交者、时间范围筛选
- 项目结构重组：代码、资源、文档、脚本分离，提升可维护性
- 注册表名称更新为TPQueryTool

V1.1.0 (20260117)
- 新增账号密码配置功能
- 新增设置界面
- 新增测试连接功能
- 移除硬编码账号密码，提升安全性

V1.0.0 (20260115)
- 初始版本发布
- 支持批量查询设备信息（SN/ID）
- 支持批量唤醒设备
- 支持导出CSV数据
"""

if __name__ == "__main__":
    print(f"版本号: {get_version_string()}")
    print(f"简短版本: {get_short_version()}")
    print(f"编译日期: {get_build_date_formatted()}")
    print(f"\n版本历史:\n{VERSION_HISTORY}")
