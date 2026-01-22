"""
清除编译文件脚本
删除 __pycache__、*.pyc、build、dist 等编译生成的文件
"""
import os
import shutil
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 需要清除的目录和文件模式
PATTERNS_TO_CLEAN = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".Python",
    "build",
    "dist",
    "*.egg-info",
    ".eggs",
    ".pytest_cache",
    ".coverage",
    "htmlcov",
]

# 需要递归清除的目录
RECURSIVE_DIRS = [
    "query_tool",
    "resources",
]


def clean_pycache():
    """清除 __pycache__ 目录"""
    count = 0
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # 跳过虚拟环境
        if "venv" in root or ".git" in root:
            continue
        
        if "__pycache__" in dirs:
            pycache_path = os.path.join(root, "__pycache__")
            try:
                shutil.rmtree(pycache_path)
                print(f"[OK] Delete: {pycache_path}")
                count += 1
            except Exception as e:
                print(f"[ERROR] Failed to delete: {pycache_path} - {e}")
    
    return count


def clean_pyc_files():
    """清除 .pyc 和 .pyo 文件"""
    count = 0
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # 跳过虚拟环境
        if "venv" in root or ".git" in root:
            continue
        
        for file in files:
            if file.endswith((".pyc", ".pyo", ".pyd")):
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    print(f"[OK] Delete: {file_path}")
                    count += 1
                except Exception as e:
                    print(f"[ERROR] Failed to delete: {file_path} - {e}")
    
    return count


def clean_build_dirs():
    """清除 build 和 dist 目录"""
    count = 0
    for dir_name in ["build", "dist"]:
        dir_path = PROJECT_ROOT / dir_name
        if dir_path.exists():
            try:
                shutil.rmtree(dir_path)
                print(f"[OK] Delete: {dir_path}")
                count += 1
            except Exception as e:
                print(f"[ERROR] Failed to delete: {dir_path} - {e}")
    
    return count


def clean_egg_info():
    """清除 .egg-info 目录"""
    count = 0
    for item in PROJECT_ROOT.glob("*.egg-info"):
        try:
            shutil.rmtree(item)
            print(f"[OK] Delete: {item}")
            count += 1
        except Exception as e:
            print(f"[ERROR] Failed to delete: {item} - {e}")
    
    return count


def clean_spec_files():
    """清除 PyInstaller spec 文件"""
    count = 0
    for spec_file in PROJECT_ROOT.glob("*.spec"):
        try:
            os.remove(spec_file)
            print(f"[OK] Delete: {spec_file}")
            count += 1
        except Exception as e:
            print(f"[ERROR] Failed to delete: {spec_file} - {e}")
    
    return count


def main():
    """主函数"""
    print("=" * 60)
    print("Clean Compiled Files Script")
    print("=" * 60)
    print(f"\nProject Root: {PROJECT_ROOT}\n")
    
    total_count = 0
    
    # 清除 __pycache__
    print("Cleaning __pycache__ directories...")
    count = clean_pycache()
    total_count += count
    print(f"Deleted {count} __pycache__ directories\n")
    
    # 清除 .pyc 文件
    print("Cleaning .pyc/.pyo/.pyd files...")
    count = clean_pyc_files()
    total_count += count
    print(f"Deleted {count} compiled files\n")
    
    # 清除 build 和 dist
    print("Cleaning build and dist directories...")
    count = clean_build_dirs()
    total_count += count
    print(f"Deleted {count} directories\n")
    
    # 清除 .egg-info
    print("Cleaning .egg-info directories...")
    count = clean_egg_info()
    total_count += count
    print(f"Deleted {count} .egg-info directories\n")
    
    # 清除 spec 文件
    print("Cleaning PyInstaller spec files...")
    count = clean_spec_files()
    total_count += count
    print(f"Deleted {count} spec files\n")
    
    print("=" * 60)
    print(f"Clean completed! Total deleted: {total_count} items")
    print("=" * 60)


if __name__ == "__main__":
    main()
