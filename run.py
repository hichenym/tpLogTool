"""
Query Tool - Launcher Script
启动查询工具
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入并运行主程序
from query_tool.main import main

if __name__ == "__main__":
    main()
