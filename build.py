"""
自动打包脚本
自动更新编译日期并打包
"""
import os
import sys
import subprocess
from datetime import datetime

def update_build_date():
    """更新version.py中的编译日期"""
    version_file = "version.py"
    
    # 读取文件
    with open(version_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 获取当前日期
    current_date = datetime.now().strftime("%Y%m%d")
    
    # 替换BUILD_DATE
    import re
    pattern = r'BUILD_DATE = datetime\.now\(\)\.strftime\("%Y%m%d"\)'
    replacement = f'BUILD_DATE = "{current_date}"'
    content = re.sub(pattern, replacement, content)
    
    # 写回文件
    with open(version_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✓ 已更新编译日期: {current_date}")
    return current_date

def build_exe():
    """执行打包"""
    print("\n开始打包...")
    
    # 清理旧文件
    if os.path.exists("build"):
        print("✓ 清理build目录")
    if os.path.exists("dist"):
        print("✓ 清理dist目录")
    
    # 执行打包
    cmd = 'pyinstaller -F -w -i ./icon/logo.ico --name "设备查询工具" main.py --noconsole'
    print(f"\n执行命令: {cmd}")
    
    result = subprocess.run(cmd, shell=True)
    
    if result.returncode == 0:
        print("\n✓ 打包成功!")
        print(f"✓ 可执行文件位置: dist/设备查询工具.exe")
        return True
    else:
        print("\n✗ 打包失败!")
        return False

def main():
    """主函数"""
    print("=" * 50)
    print("设备查询工具 - 自动打包脚本")
    print("=" * 50)
    
    # 更新编译日期
    build_date = update_build_date()
    
    # 导入版本信息
    from version import get_version_string
    print(f"✓ 当前版本: {get_version_string()}")
    
    # 询问是否继续
    response = input("\n是否继续打包? (y/n): ")
    if response.lower() != 'y':
        print("已取消打包")
        return
    
    # 执行打包
    success = build_exe()
    
    if success:
        print("\n" + "=" * 50)
        print("打包完成!")
        print("=" * 50)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
