"""
自动打包脚本
自动更新编译日期并打包
"""
import os
import sys
import subprocess
import shutil
import importlib.util
from datetime import datetime

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


def update_build_date():
    """更新version.py中的编译日期"""
    version_file = os.path.join(project_root, "query_tool", "version.py")
    
    # 读取文件
    with open(version_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 获取当前日期
    current_date = datetime.now().strftime("%Y%m%d")
    
    # 替换BUILD_DATE
    import re
    pattern = r'BUILD_DATE = "\d{8}"'
    replacement = f'BUILD_DATE = "{current_date}"'
    content = re.sub(pattern, replacement, content)
    
    # 写回文件
    with open(version_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"[OK] 已更新编译日期: {current_date}")
    return current_date


def build_exe():
    """执行打包"""
    print("\n开始打包...")
    
    # 清理旧文件
    if os.path.exists("build"):
        print("[OK] 清理build目录")
        shutil.rmtree("build")
    if os.path.exists("dist"):
        print("[OK] 清理dist目录")
        shutil.rmtree("dist")
    if os.path.exists("TPQueryTool.spec"):
        print("[OK] 清理TPQueryTool.spec")
        os.remove("TPQueryTool.spec")

    setuptools_spec = importlib.util.find_spec("setuptools")
    if setuptools_spec is None or not setuptools_spec.origin:
        raise RuntimeError("未找到 setuptools，无法定位 vendored 依赖目录")
    setuptools_vendor_dir = os.path.join(os.path.dirname(setuptools_spec.origin), "_vendor")
    if not os.path.isdir(setuptools_vendor_dir):
        raise RuntimeError(f"setuptools vendored 目录不存在: {setuptools_vendor_dir}")
    
    # 执行打包
    # 使用 run.py 作为入口点，图标路径更新为新位置
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        "--name", "TPQueryTool",
        "--icon", "./resources/icons/app/logo.ico",
        "--hidden-import", "ddddocr",
        "--hidden-import", "onnxruntime",
        "--hidden-import", "cv2",
        "--hidden-import", "numpy",
        "--hidden-import", "lark_oapi",
        "--hidden-import", "lark_oapi.api.bitable.v1",
        "--hidden-import", "pkg_resources",
        "--hidden-import", "qfluentwidgets",
        "--hidden-import", "qframelesswindow",
        "--hidden-import", "darkdetect",
        "--hidden-import", "win32api",
        "--hidden-import", "win32con",
        "--hidden-import", "win32gui",
        "--collect-all", "ddddocr",
        "--collect-all", "qfluentwidgets",
        "--collect-all", "qframelesswindow",
        "--collect-binaries", "onnxruntime",
        "--collect-data", "onnxruntime",
        "--add-data", "./query_tool/dll;query_tool/dll",
        "--add-data", f"{setuptools_vendor_dir};setuptools/_vendor",
        "run.py",
    ]
    print(f"\n执行命令: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, cwd=project_root)
    
    if result.returncode == 0:
        print("\n[OK] 打包成功!")
        print(f"[OK] 可执行文件位置: dist/TPQueryTool.exe")
        return True
    else:
        print("\n[ERROR] 打包失败!")
        return False


def main():
    """主函数"""
    print("=" * 50)
    print("TPQueryTool - 自动打包脚本")
    print("=" * 50)
    
    # 更新编译日期
    build_date = update_build_date()
    
    # 导入版本信息
    from query_tool.version import get_version_string
    print(f"[OK] 当前版本: {get_version_string()}")
      
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
