"""
Nuitka 打包脚本
将项目编译为原生 C 代码，防止反编译

使用方法:
    python scripts/build.py          # 正常打包
    python scripts/build.py --debug  # 保留控制台窗口（调试用）

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


def clean_build():
    """清理旧的构建产物"""
    dirs_to_clean = ["run.build", "run.dist", "run.onefile-build"]
    for d in dirs_to_clean:
        path = os.path.join(PROJECT_ROOT, d)
        if os.path.exists(path):
            shutil.rmtree(path)
            print(f"[OK] 已清理: {d}")


def build_nuitka(debug=False):
    """执行 Nuitka 打包"""
    print("\n开始 Nuitka 编译打包...")
    print("（首次编译较慢，约 5-15 分钟，请耐心等待）\n")

    # 动态读取版本号
    from query_tool.version import get_version
    ver = get_version()
    version_str = f"{ver[0]}.{ver[1]}.{ver[2]}.0"

    cmd = [
        sys.executable, "-m", "nuitka",

        # === 输出配置 ===
        "--standalone",                          # 独立发布，包含所有依赖
        "--onefile",                             # 打包为单个 exe
        "--output-dir=dist",                     # 输出目录
        "--output-filename=TPQueryTool.exe",     # 输出文件名

        # === Windows 配置 ===
        f"--windows-icon-from-ico={os.path.join('resources', 'icons', 'app', 'logo.ico')}",
        "--windows-company-name=TPQueryTool",
        "--windows-product-name=TPQueryTool",
        "--windows-file-description=TP Query Tool",
        f"--windows-product-version={version_str}",
        f"--windows-file-version={version_str}",

        # === 编译优化 ===
        "--assume-yes-for-downloads",            # 自动下载缺失的依赖（如 MinGW64）

        # === PyQt5 插件 ===
        "--enable-plugin=pyqt5",                 # 启用 PyQt5 支持

        # === 隐式导入（PyInstaller 中的 hidden-import） ===
        "--include-module=ddddocr",
        "--include-module=onnxruntime",
        "--include-module=cv2",
        "--include-module=numpy",
        "--include-module=lark_oapi",
        "--include-module=lark_oapi.api.bitable.v1",
        # 排除 lark_oapi 中未使用的 API 模块，大幅加速编译
        "--nofollow-import-to=lark_oapi.api.acs.*",
        "--nofollow-import-to=lark_oapi.api.admin.*",
        "--nofollow-import-to=lark_oapi.api.application.*",
        "--nofollow-import-to=lark_oapi.api.approval.*",
        "--nofollow-import-to=lark_oapi.api.attendance.*",
        "--nofollow-import-to=lark_oapi.api.authen.*",
        "--nofollow-import-to=lark_oapi.api.baike.*",
        "--nofollow-import-to=lark_oapi.api.calendar.*",
        "--nofollow-import-to=lark_oapi.api.contact.*",
        "--nofollow-import-to=lark_oapi.api.corehr.*",
        "--nofollow-import-to=lark_oapi.api.docx.*",
        "--nofollow-import-to=lark_oapi.api.drive.*",
        "--nofollow-import-to=lark_oapi.api.ehr.*",
        "--nofollow-import-to=lark_oapi.api.event.*",
        "--nofollow-import-to=lark_oapi.api.hire.*",
        "--nofollow-import-to=lark_oapi.api.human_authentication.*",
        "--nofollow-import-to=lark_oapi.api.im.*",
        "--nofollow-import-to=lark_oapi.api.lingo.*",
        "--nofollow-import-to=lark_oapi.api.mail.*",
        "--nofollow-import-to=lark_oapi.api.meeting_room.*",
        "--nofollow-import-to=lark_oapi.api.okr.*",
        "--nofollow-import-to=lark_oapi.api.optical_char_recognition.*",
        "--nofollow-import-to=lark_oapi.api.passport.*",
        "--nofollow-import-to=lark_oapi.api.performance.*",
        "--nofollow-import-to=lark_oapi.api.personal_settings.*",
        "--nofollow-import-to=lark_oapi.api.report.*",
        "--nofollow-import-to=lark_oapi.api.search.*",
        "--nofollow-import-to=lark_oapi.api.sheets.*",
        "--nofollow-import-to=lark_oapi.api.speech_to_text.*",
        "--nofollow-import-to=lark_oapi.api.task.*",
        "--nofollow-import-to=lark_oapi.api.tenant.*",
        "--nofollow-import-to=lark_oapi.api.translation.*",
        "--nofollow-import-to=lark_oapi.api.vc.*",
        "--nofollow-import-to=lark_oapi.api.verification.*",
        "--nofollow-import-to=lark_oapi.api.wiki.*",
        "--include-module=json",
        "--include-module=requests",
        "--include-module=bs4",
        "--include-module=coloredlogs",
        "--include-module=PIL",

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
        exe_path = os.path.join(PROJECT_ROOT, "dist", "TPQueryTool.exe")
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

    # 更新编译日期
    build_date = update_build_date()

    # 导入版本信息
    from query_tool.version import get_version_string
    print(f"[OK] 当前版本: {get_version_string()}")

    # 清理旧构建
    clean_build()

    # 执行打包
    success = build_nuitka(debug=debug)

    if success:
        print("\n" + "=" * 50)
        print("打包完成!")
        print("=" * 50)
    else:
        print("\n如果编译失败，常见排查步骤:")
        print("  1. 确认已安装 C 编译器 (MinGW64 或 MSVC)")
        print("  2. 尝试加 --debug 参数查看详细错误")
        print("  3. 先不加 --onefile 测试: 去掉脚本中的 --onefile 行")
        sys.exit(1)


if __name__ == "__main__":
    main()
