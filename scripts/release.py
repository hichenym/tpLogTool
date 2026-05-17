"""
Quick release helper.

Creates and pushes a Git tag to trigger the GitHub Actions workflow.
Supports both release tags like ``v3.0.1`` and build-only debug tags
like ``v3.0.1-debug``.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def get_current_version() -> str:
    from query_tool.version import VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH

    return f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}"


def run_command(cmd: str, check: bool = True) -> tuple[bool, str, str]:
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=check,
            cwd=PROJECT_ROOT,
        )
        return True, result.stdout.strip(), result.stderr.strip()
    except subprocess.CalledProcessError as exc:
        return False, (exc.stdout or "").strip(), (exc.stderr or "").strip()


def check_git_status() -> tuple[bool, str]:
    success, stdout, _ = run_command("git status --porcelain")
    if not success:
        return False, "无法获取 Git 状态"
    if stdout:
        return False, "有未提交的更改，请先提交后再打 tag"
    return True, "工作区干净"


def get_existing_tags() -> list[str]:
    success, stdout, _ = run_command("git tag")
    if not success:
        return []
    return [tag.strip() for tag in stdout.splitlines() if tag.strip()]


def validate_version(version: str) -> bool:
    return re.fullmatch(r"\d+\.\d+\.\d+", version) is not None


def build_tag(version: str, debug_build: bool) -> str:
    return f"v{version}-debug" if debug_build else f"v{version}"


def create_and_push_tag(tag: str) -> tuple[bool, str]:
    print(f"\n创建标签: {tag}")
    success, _, stderr = run_command(f'git tag -a {tag} -m "Release {tag}"')
    if not success:
        return False, f"创建标签失败: {stderr}"

    print("推送标签到远程仓库...")
    success, _, stderr = run_command(f"git push origin {tag}")
    if not success:
        run_command(f"git tag -d {tag}", check=False)
        return False, f"推送标签失败: {stderr}"

    return True, f"标签 {tag} 已成功推送"


def choose_build_mode() -> bool:
    print("\n选择构建模式：")
    print("  1. 正式发布（vX.Y.Z）")
    print("  2. 调试验证（vX.Y.Z-debug，只打包不发布）")

    while True:
        choice = input("请输入 1 或 2: ").strip()
        if choice == "1":
            return False
        if choice == "2":
            return True
        print("输入无效，请输入 1 或 2。")


def main() -> None:
    print("=" * 60)
    print("TPQueryTool - 快速发布脚本")
    print("=" * 60)

    print("\n检查 Git 状态...")
    success, message = check_git_status()
    if not success:
        print(f"[ERROR] {message}")
        print("\n请先提交所有更改：")
        print("  git add .")
        print('  git commit -m "your message"')
        raise SystemExit(1)
    print(f"[OK] {message}")

    current_version = get_current_version()
    print(f"\n当前版本: V{current_version}")

    existing_tags = get_existing_tags()
    if existing_tags:
        print("\n现有标签:")
        for tag in existing_tags[-5:]:
            print(f"  - {tag}")
        if len(existing_tags) > 5:
            print(f"  ... 共 {len(existing_tags)} 个标签")

    print("\n请输入要使用的版本号，格式为 x.y.z")
    print(f"建议版本号: {current_version}")

    while True:
        version_input = input("\n版本号（直接回车使用建议版本）: ").strip()
        version = version_input or current_version
        if validate_version(version):
            break
        print("[ERROR] 版本号格式错误，请使用 x.y.z，例如 3.0.1")

    debug_build = choose_build_mode()
    tag = build_tag(version, debug_build)

    if tag in existing_tags:
        print(f"\n[ERROR] 标签 {tag} 已存在")
        response = input("是否删除现有标签并重新创建？(y/n): ").strip().lower()
        if response != "y":
            print("已取消")
            raise SystemExit(0)

        print(f"\n删除本地标签 {tag}...")
        run_command(f"git tag -d {tag}", check=False)

        print(f"删除远程标签 {tag}...")
        run_command(f"git push origin :refs/tags/{tag}", check=False)

    print("\n" + "=" * 60)
    print(f"准备推送标签: {tag}")
    print("=" * 60)
    if debug_build:
        print("\n这次将触发 GitHub Actions 调试构建：")
        print("  1. 编译并打包 exe")
        print("  2. 上传 Actions Artifact")
        print("  3. 不创建 GitHub Release")
        print("  4. 不生成或提交 version.json")
    else:
        print("\n这次将触发 GitHub Actions 正式发布：")
        print("  1. 编译并打包 exe")
        print("  2. 创建 GitHub Release")
        print("  3. 生成并上传 version.json")
        print("  4. 提交 version.json 回仓库")

    response = input("\n确认继续？(y/n): ").strip().lower()
    if response != "y":
        print("已取消")
        raise SystemExit(0)

    success, message = create_and_push_tag(tag)
    if not success:
        print("\n" + "=" * 60)
        print("[ERROR] 触发失败")
        print("=" * 60)
        print(f"\n{message}")
        raise SystemExit(1)

    print("\n" + "=" * 60)
    print("[OK] 已触发工作流")
    print("=" * 60)
    print(f"\n{message}")
    print("\nGitHub Actions 已开始运行，可到仓库 Actions 页面查看进度。")
    if debug_build:
        print("构建完成后，请到本次 workflow 的 Artifacts 下载打包结果。")
    else:
        print("构建完成后，可到 Releases 页面下载正式发布产物。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n已取消")
        raise SystemExit(0)
