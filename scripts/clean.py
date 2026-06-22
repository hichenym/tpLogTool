"""清理 PyInstaller 构建产物和 Python 缓存。"""
from __future__ import annotations

import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKIP_DIR_NAMES = {".git", "venv", "env", ".venv", "__pypackages__"}


def _iter_project_files() -> tuple[list[Path], list[Path]]:
    directories: list[Path] = []
    files: list[Path] = []

    for path in PROJECT_ROOT.rglob("*"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.is_dir():
            directories.append(path)
        elif path.is_file():
            files.append(path)
    return directories, files


def _remove_path(path: Path) -> bool:
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        print(f"[OK] Delete: {path}")
        return True
    except Exception as exc:
        print(f"[ERROR] Failed to delete: {path} - {exc}")
        return False


def clean_python_cache() -> int:
    """清除 Python 缓存目录和编译文件。"""
    directories, files = _iter_project_files()
    removed = 0

    for directory in directories:
        if directory.name == "__pycache__":
            removed += int(_remove_path(directory))

    for file_path in files:
        if file_path.suffix.lower() in {".pyc", ".pyo", ".pyd"}:
            removed += int(_remove_path(file_path))

    return removed


def clean_pyinstaller_artifacts() -> int:
    """清除当前 PyInstaller 打包方案的构建产物。"""
    removed = 0

    for name in ("build", "dist"):
        path = PROJECT_ROOT / name
        if path.exists():
            removed += int(_remove_path(path))

    for path in PROJECT_ROOT.glob("*.spec"):
        removed += int(_remove_path(path))

    for path in PROJECT_ROOT.glob("*.egg-info"):
        removed += int(_remove_path(path))

    for name in (".eggs", ".pytest_cache", "htmlcov"):
        path = PROJECT_ROOT / name
        if path.exists():
            removed += int(_remove_path(path))

    for path in PROJECT_ROOT.glob(".coverage*"):
        removed += int(_remove_path(path))

    return removed


def main() -> None:
    print("=" * 60)
    print("Clean PyInstaller Artifacts")
    print("=" * 60)
    print(f"\nProject Root: {PROJECT_ROOT}\n")

    print("Cleaning Python caches...")
    cache_count = clean_python_cache()
    print(f"Deleted {cache_count} cache items\n")

    print("Cleaning PyInstaller artifacts...")
    build_count = clean_pyinstaller_artifacts()
    print(f"Deleted {build_count} build items\n")

    total_count = cache_count + build_count
    print("=" * 60)
    print(f"Clean completed! Total deleted: {total_count} items")
    print("=" * 60)


if __name__ == "__main__":
    main()
