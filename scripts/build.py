"""
PyInstaller 打包脚本

使用方法:
    python scripts/build.py
    python scripts/build.py --debug
"""
from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "TPQueryTool"
SPEC_FILE = f"{APP_NAME}.spec"
REQUIRED_SDK_DLLS = (
    "Funclib.dll",
    "libgcc_s_seh-1.dll",
    "libsiot.dll",
    "libstdc++-6.dll",
    "libtps_crypt.dll",
    "libwinpthread-1.dll",
)


def _project_root_path() -> Path:
    return Path(PROJECT_ROOT)


def ensure_project_root_on_path() -> None:
    """确保脚本模式运行时也能导入项目包。"""
    project_root = str(_project_root_path())
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


def configure_stdio() -> None:
    """Use UTF-8 for console output on non-UTF8 terminals."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def update_build_date() -> str:
    """更新 version.py 中的编译日期。"""
    version_file = _project_root_path() / "query_tool" / "version.py"
    content = version_file.read_text(encoding="utf-8")
    current_date = datetime.now().strftime("%Y%m%d")
    content = re.sub(r'BUILD_DATE = "\d{8}"', f'BUILD_DATE = "{current_date}"', content)
    version_file.write_text(content, encoding="utf-8")
    print(f"[OK] 已更新编译日期: {current_date}")
    return current_date


def clean_build_artifacts() -> None:
    """清理 PyInstaller 构建产物。"""
    for name in ("build", "dist", SPEC_FILE):
        path = _project_root_path() / name
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        print(f"[OK] 已清理: {path}")


def get_sdk_dll_data_args() -> list[str]:
    """显式包含设备 SDK DLL，并在缺失时提前失败。"""
    dll_dir = _project_root_path() / "query_tool" / "dll"
    if not dll_dir.is_dir():
        raise FileNotFoundError(f"DLL目录不存在: {dll_dir}")

    dll_names = sorted(path.name for path in dll_dir.glob("*.dll"))
    if not dll_names:
        raise FileNotFoundError(f"DLL目录中未找到 .dll 文件: {dll_dir}")

    lower_name_map = {name.lower(): name for name in dll_names}
    missing_required = [
        dll_name
        for dll_name in REQUIRED_SDK_DLLS
        if dll_name.lower() not in lower_name_map
    ]
    if missing_required:
        raise FileNotFoundError(f"缺少必要的SDK DLL: {', '.join(missing_required)}")

    args: list[str] = []
    for dll_name in dll_names:
        source = os.path.join("query_tool", "dll", dll_name)
        args.extend(["--add-data", f"{source};query_tool/dll"])
    return args


def get_setuptools_vendor_data_args() -> list[str]:
    """包含 setuptools vendored 依赖，避免 pkg_resources 运行时缺失。"""
    setuptools_spec = importlib.util.find_spec("setuptools")
    if setuptools_spec is None or not setuptools_spec.origin:
        raise RuntimeError("未找到 setuptools，无法定位 vendored 依赖目录")

    setuptools_vendor_dir = Path(setuptools_spec.origin).resolve().parent / "_vendor"
    if not setuptools_vendor_dir.is_dir():
        raise RuntimeError(f"setuptools vendored 目录不存在: {setuptools_vendor_dir}")

    return ["--add-data", f"{setuptools_vendor_dir};setuptools/_vendor"]


def build_exe(debug: bool = False) -> bool:
    """执行 PyInstaller 打包。"""
    print("\n开始 PyInstaller 打包...")
    clean_build_artifacts()

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        APP_NAME,
        "--icon",
        "./resources/icons/app/logo.ico",
        "--hidden-import",
        "ddddocr",
        "--hidden-import",
        "onnxruntime",
        "--hidden-import",
        "cv2",
        "--hidden-import",
        "numpy",
        "--hidden-import",
        "pkg_resources",
        "--collect-all",
        "ddddocr",
        "--collect-binaries",
        "onnxruntime",
        "--collect-data",
        "onnxruntime",
    ]

    cmd.append("--console" if debug else "--noconsole")
    cmd.extend(get_sdk_dll_data_args())
    cmd.extend(get_setuptools_vendor_data_args())
    cmd.append("run.py")

    print(f"\n执行命令: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=_project_root_path())

    exe_path = _project_root_path() / "dist" / f"{APP_NAME}.exe"
    if result.returncode == 0 and exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print("\n[OK] 打包成功!")
        print(f"[OK] 可执行文件位置: {exe_path}")
        print(f"[OK] 文件大小: {size_mb:.2f} MB")
        return True

    print("\n[ERROR] 打包失败!")
    return False


def main() -> None:
    configure_stdio()
    ensure_project_root_on_path()
    debug = "--debug" in sys.argv

    print("=" * 50)
    print("TPQueryTool - PyInstaller 打包脚本")
    print("=" * 50)

    try:
        import PyInstaller  # noqa: F401
        print("[OK] PyInstaller 已安装")
    except ImportError:
        print("[ERROR] 未安装 PyInstaller，请执行: pip install PyInstaller setuptools")
        raise SystemExit(1)

    update_build_date()

    from query_tool.version import get_version_string

    print(f"[OK] 当前版本: {get_version_string()}")

    if build_exe(debug=debug):
        print("\n" + "=" * 50)
        print("打包完成!")
        print("=" * 50)
        return

    raise SystemExit(1)


if __name__ == "__main__":
    main()
