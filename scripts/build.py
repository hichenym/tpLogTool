"""
Nuitka 打包脚本
将项目编译为原生 C 代码，防止反编译

使用方法:
    python scripts/build.py                 # 正常打包（发布模式）
    python scripts/build.py --debug         # 保留控制台窗口（调试用）
    python scripts/build.py --fast          # 增量打包（开发模式，更快）
    python scripts/build.py --fast --debug  # 增量打包并保留控制台

前置条件:
    1. pip install nuitka ordered-set zstandard
    2. 安装 C 编译器（推荐 MinGW64 或 MSVC）
       - MinGW64: Nuitka 首次运行会提示自动下载
       - MSVC: 安装 Visual Studio Build Tools
"""
import os
import sys
import subprocess
import shutil
from datetime import datetime

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

RELEASE_OUTPUT_DIR = "dist"
FAST_OUTPUT_DIR = os.path.join("dist", "fast")
APP_NAME = "TPQueryTool"


def update_build_date():
    """更新 version.py 中的编译日期"""
    import re
    version_file = os.path.join(PROJECT_ROOT, "query_tool", "version.py")

    with open(version_file, 'r', encoding='utf-8') as f:
        content = f.read()

    current_date = datetime.now().strftime("%Y%m%d")
    content = re.sub(r'BUILD_DATE = "\d{8}"', f'BUILD_DATE = "{current_date}"', content)

    with open(version_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"[OK] 已更新编译日期: {current_date}")
    return current_date


def clean_build(output_dir=RELEASE_OUTPUT_DIR):
    """清理旧的构建产物"""
    dirs_to_clean = [
        "run.build",
        "run.dist",
        "run.onefile-build",
        os.path.join(output_dir, "run.build"),
        os.path.join(output_dir, "run.dist"),
        os.path.join(output_dir, "run.onefile-build"),
    ]
    for relative_path in dirs_to_clean:
        path = os.path.join(PROJECT_ROOT, relative_path)
        if os.path.exists(path):
            shutil.rmtree(path)
            print(f"[OK] 已清理: {relative_path}")


def get_sdk_dll_include_args():
    """显式包含 SIOT SDK DLL，避免 Nuitka 将纯 DLL 目录视为“无 data files”而跳过。"""
    dll_dir = os.path.join(PROJECT_ROOT, "query_tool", "dll")
    if not os.path.isdir(dll_dir):
        print(f"[WARN] DLL目录不存在: {dll_dir}")
        return []

    include_args = []
    dll_names = sorted(name for name in os.listdir(dll_dir) if name.lower().endswith(".dll"))
    if not dll_names:
        print(f"[WARN] DLL目录中未找到 .dll 文件: {dll_dir}")
        return []

    for dll_name in dll_names:
        source = os.path.join("query_tool", "dll", dll_name)
        target = f"query_tool/dll/{dll_name}"
        include_args.append(f"--include-data-files={source}={target}")

    print(f"[OK] 将显式包含 {len(dll_names)} 个SIOT DLL")
    for dll_name in dll_names:
        print(f"     - {dll_name}")
    return include_args


def build_nuitka(debug=False, fast=False):
    """执行 Nuitka 打包"""
    print("\n开始 Nuitka 编译打包...")
    if fast:
        print("（开发增量模式：保留构建目录，跳过 onefile 封装，以加快重复打包）\n")
    else:
        print("（首次编译较慢，约 5-15 分钟，请耐心等待）\n")

    # 动态读取版本号
    from query_tool.version import get_version
    ver = get_version()
    version_str = f"{ver[0]}.{ver[1]}.{ver[2]}.0"
    sdk_dll_args = get_sdk_dll_include_args()
    output_dir = FAST_OUTPUT_DIR if fast else RELEASE_OUTPUT_DIR

    cmd = [
        sys.executable, "-m", "nuitka",

        # === 输出配置 ===
        "--standalone",                          # 独立发布，包含所有依赖
        f"--output-dir={output_dir}",            # 输出目录
        f"--output-filename={APP_NAME}.exe",     # 输出文件名

        # === Windows 配置 ===
        f"--windows-icon-from-ico={os.path.join('resources', 'icons', 'app', 'logo.ico')}",
        "--windows-company-name=TPQueryTool",
        "--windows-product-name=TPQueryTool",
        "--windows-file-description=TP Query Tool",
        f"--windows-product-version={version_str}",
        f"--windows-file-version={version_str}",

        # === 编译优化 ===
        "--assume-yes-for-downloads",            # 自动下载缺失的依赖（如 MinGW64）
        "--jobs=4",                              # 多核并行编译，加速 C 编译阶段

        # === PyQt5 插件 ===
        "--enable-plugin=pyqt5",                 # 启用 PyQt5 支持

        # === 隐式导入（PyInstaller 中的 hidden-import） ===
        "--include-module=ddddocr",
        "--include-module=onnxruntime",
        "--include-module=cv2",
        "--include-module=numpy",
        "--include-module=lark_oapi",
        "--include-module=lark_oapi.api.bitable.v1",
        "--include-package=websockets",
        "--include-module=websockets.legacy",
        "--include-module=json",
        "--include-module=requests",
        "--include-module=ssl",
        "--include-module=_ssl",
        "--include-module=urllib.request",
        "--include-module=http.client",
        "--include-module=bs4",
        "--include-module=coloredlogs",
        "--include-module=PIL",
        "--include-package=certifi",

        # === 包含项目模块 ===
        "--include-package=query_tool",
        "--include-package=query_tool.pages",
        "--include-package=query_tool.utils",
        "--include-package=query_tool.widgets",
        "--include-package=resources",

        # === 包含资源数据文件 ===
        # ddddocr 和 onnxruntime 的模型数据
        "--include-package-data=ddddocr",
        "--include-package-data=onnxruntime",

        # === 包含项目资源文件 ===
        f"--include-data-dir={os.path.join('resources', 'icons')}=resources/icons",
    ]

    if fast:
        print(f"[FAST] 输出目录: {os.path.join(PROJECT_ROOT, output_dir)}")
        print("[FAST] 跳过清理旧构建，保留 Nuitka 中间产物以复用缓存")
        print("[FAST] 跳过 BUILD_DATE 更新时间，避免无意义的全量失效")
    else:
        cmd.extend([
            "--onefile",                         # 打包为单个 exe
            "--onefile-no-dll",                  # onefile 下使用可执行文件而不是 run.dll，便于内部子进程重启
        ])

    cmd.extend(sdk_dll_args)

    # 控制台窗口
    if debug:
        cmd.append("--windows-console-mode=force")
        print("[DEBUG] 保留控制台窗口")
    else:
        cmd.append("--windows-console-mode=disable")

    # 入口文件
    cmd.append("run.py")

    print("执行命令:")
    print(" ".join(cmd))
    print()

    result = subprocess.run(cmd, cwd=PROJECT_ROOT)

    if result.returncode == 0:
        exe_path = os.path.join(PROJECT_ROOT, output_dir, f"{APP_NAME}.exe")
        if fast and not os.path.exists(exe_path):
            dist_dir_path = os.path.join(PROJECT_ROOT, output_dir, f"{APP_NAME}.dist")
            candidate = os.path.join(dist_dir_path, f"{APP_NAME}.exe")
            if os.path.exists(candidate):
                exe_path = candidate
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"\n[OK] 打包成功!")
            print(f"[OK] 文件位置: {exe_path}")
            print(f"[OK] 文件大小: {size_mb:.2f} MB")
            return True
        else:
            print("\n[WARN] 编译完成但未找到输出文件，请检查 dist 目录")
            return False
    else:
        print("\n[ERROR] 打包失败!")
        return False


def main():
    """主函数"""
    debug = "--debug" in sys.argv
    fast = "--fast" in sys.argv

    print("=" * 50)
    print("TPQueryTool - Nuitka 打包脚本")
    print("=" * 50)

    # 检查 Nuitka 是否安装
    try:
        import nuitka
        print(f"[OK] Nuitka 已安装")
    except ImportError:
        print("[ERROR] 未安装 Nuitka，请执行: pip install nuitka ordered-set zstandard")
        sys.exit(1)

    if fast:
        print("[FAST] 开发增量模式已启用")
        print(f"[FAST] 中间产物目录将保留在: {os.path.join(PROJECT_ROOT, FAST_OUTPUT_DIR)}")
    else:
        # 更新编译日期
        update_build_date()

    # 导入版本信息
    from query_tool.version import get_version_string
    print(f"[OK] 当前版本: {get_version_string()}")

    if not fast:
        # 清理旧构建
        clean_build(output_dir=RELEASE_OUTPUT_DIR)
    else:
        print("[FAST] 跳过 clean_build()，尽量复用已有构建结果")

    # 执行打包
    success = build_nuitka(debug=debug, fast=fast)

    if success:
        print("\n" + "=" * 50)
        print("打包完成!")
        print("=" * 50)
    else:
        print("\n如果编译失败，常见排查步骤:")
        print("  1. 确认已安装 C 编译器 (MinGW64 或 MSVC)")
        print("  2. 尝试加 --debug 参数查看详细错误")
        print("  3. 开发时可先执行: python scripts/build.py --fast")
        sys.exit(1)


if __name__ == "__main__":
    main()
