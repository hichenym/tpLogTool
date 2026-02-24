"""
快速发布脚本
用于创建版本标签并触发 GitHub Actions 自动构建
"""
import os
import sys
import subprocess
import re

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def get_current_version():
    """从 version.py 获取当前版本"""
    from query_tool.version import VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH
    return f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}"


def run_command(cmd, check=True):
    """执行命令并返回输出"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=check,
            cwd=project_root
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr


def check_git_status():
    """检查 Git 状态"""
    success, stdout, _ = run_command("git status --porcelain")
    if not success:
        return False, "无法获取 Git 状态"
    
    if stdout:
        return False, "有未提交的更改，请先提交所有更改"
    
    return True, "工作区干净"


def get_existing_tags():
    """获取现有标签"""
    success, stdout, _ = run_command("git tag")
    if not success:
        return []
    return [tag.strip() for tag in stdout.split('\n') if tag.strip()]


def validate_version(version):
    """验证版本号格式"""
    pattern = r'^\d+\.\d+\.\d+$'
    return re.match(pattern, version) is not None


def create_and_push_tag(version):
    """创建并推送标签"""
    tag = f"v{version}"
    
    # 创建标签
    print(f"\n创建标签: {tag}")
    success, stdout, stderr = run_command(f'git tag -a {tag} -m "Release {tag}"')
    if not success:
        return False, f"创建标签失败: {stderr}"
    
    # 推送标签
    print(f"推送标签到远程仓库...")
    success, stdout, stderr = run_command(f"git push origin {tag}")
    if not success:
        # 如果推送失败，删除本地标签
        run_command(f"git tag -d {tag}", check=False)
        return False, f"推送标签失败: {stderr}"
    
    return True, f"标签 {tag} 已成功推送"


def main():
    """主函数"""
    print("=" * 60)
    print("TPQueryTool - 快速发布脚本")
    print("=" * 60)
    
    # 检查 Git 状态
    print("\n检查 Git 状态...")
    success, message = check_git_status()
    if not success:
        print(f"✗ {message}")
        print("\n请先提交所有更改：")
        print("  git add .")
        print('  git commit -m "your message"')
        sys.exit(1)
    print(f"✓ {message}")
    
    # 获取当前版本
    current_version = get_current_version()
    print(f"\n当前版本: V{current_version}")
    
    # 获取现有标签
    existing_tags = get_existing_tags()
    if existing_tags:
        print(f"\n现有标签:")
        for tag in existing_tags[-5:]:  # 显示最近 5 个标签
            print(f"  - {tag}")
        if len(existing_tags) > 5:
            print(f"  ... 共 {len(existing_tags)} 个标签")
    
    # 询问版本号
    print("\n" + "=" * 60)
    print("请输入要发布的版本号（格式：x.y.z）")
    print(f"建议版本号: {current_version}")
    print("=" * 60)
    
    while True:
        version_input = input("\n版本号 (直接回车使用建议版本): ").strip()
        
        # 如果直接回车，使用当前版本
        if not version_input:
            version = current_version
            break
        
        # 验证版本号格式
        if not validate_version(version_input):
            print("✗ 版本号格式错误，请使用 x.y.z 格式（如 3.0.1）")
            continue
        
        version = version_input
        break
    
    tag = f"v{version}"
    
    # 检查标签是否已存在
    if tag in existing_tags:
        print(f"\n✗ 标签 {tag} 已存在")
        response = input("是否删除现有标签并重新创建? (y/n): ").strip().lower()
        if response != 'y':
            print("已取消发布")
            sys.exit(0)
        
        # 删除本地和远程标签
        print(f"\n删除本地标签 {tag}...")
        run_command(f"git tag -d {tag}", check=False)
        
        print(f"删除远程标签 {tag}...")
        run_command(f"git push origin :refs/tags/{tag}", check=False)
    
    # 确认发布
    print("\n" + "=" * 60)
    print(f"准备发布版本: {tag}")
    print("=" * 60)
    print("\n发布后将自动触发 GitHub Actions 构建流程：")
    print("  1. 更新版本号和编译日期")
    print("  2. 打包 Windows 可执行文件")
    print("  3. 创建 GitHub Release")
    print("  4. 上传 exe 和 version.json")
    print("  5. 生成发布说明")
    print("\n构建时间约 6-9 分钟")
    print("=" * 60)
    
    response = input("\n确认发布? (y/n): ").strip().lower()
    if response != 'y':
        print("已取消发布")
        sys.exit(0)
    
    # 创建并推送标签
    success, message = create_and_push_tag(version)
    
    if success:
        print("\n" + "=" * 60)
        print("✓ 发布成功!")
        print("=" * 60)
        print(f"\n{message}")
        print("\nGitHub Actions 构建已触发，请访问以下链接查看进度：")
        
        # 尝试获取远程仓库 URL
        success, remote_url, _ = run_command("git config --get remote.origin.url")
        if success and remote_url:
            # 转换 SSH URL 为 HTTPS URL
            if remote_url.startswith("git@github.com:"):
                repo_path = remote_url.replace("git@github.com:", "").replace(".git", "")
                actions_url = f"https://github.com/{repo_path}/actions"
                release_url = f"https://github.com/{repo_path}/releases/tag/{tag}"
                print(f"  Actions: {actions_url}")
                print(f"  Release: {release_url}")
        
        print("\n提示：")
        print("  - 构建完成后，Release 页面会自动更新")
        print("  - version.json 会自动生成并上传")
        print("  - 如需修改 Release 说明，可在 Release 页面编辑")
    else:
        print("\n" + "=" * 60)
        print("✗ 发布失败")
        print("=" * 60)
        print(f"\n{message}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n已取消发布")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ 发生错误: {e}")
        sys.exit(1)
