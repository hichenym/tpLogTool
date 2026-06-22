"""
版本信息管理模块
"""

# 版本号配置
VERSION_MAJOR = 3  # 主版本号：重大功能更新或架构变更
VERSION_MINOR = 7  # 次版本号：新增功能或较大改进
VERSION_PATCH = 3  # 修订号：Bug修复或小改进

# 自动获取编译日期
BUILD_DATE = "20260622"

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

# 合规保留字段，内容已清空
VERSION_HISTORY = ""

if __name__ == "__main__":
    print(f"版本号: {get_version_string()}")
    print(f"简短版本: {get_short_version()}")
    print(f"编译日期: {get_build_date_formatted()}")
