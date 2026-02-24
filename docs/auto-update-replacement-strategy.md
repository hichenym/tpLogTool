# 绿色版程序自动替换更新方案

## 核心问题

**问题**：程序正在运行时，无法直接替换自己的 exe 文件（Windows 会锁定正在运行的文件）

**解决思路**：使用辅助程序或脚本在主程序退出后完成替换

---

## 方案对比

### 方案一：批处理脚本替换（推荐）⭐

#### 工作流程
```
1. 主程序下载新版本到临时目录
2. 主程序创建批处理脚本（.bat）
3. 主程序启动批处理脚本
4. 主程序立即退出
5. 批处理脚本等待主程序完全退出
6. 批处理脚本备份旧版本
7. 批处理脚本复制新版本到当前目录
8. 批处理脚本启动新版本
9. 批处理脚本自删除
```

#### 实现代码

**Python 端（主程序）：**
```python
import os
import sys
import subprocess
from pathlib import Path

def create_update_script(new_exe_path, current_exe_path):
    """创建更新批处理脚本"""
    
    # 获取当前程序的目录和文件名
    current_dir = os.path.dirname(current_exe_path)
    exe_name = os.path.basename(current_exe_path)
    backup_name = f"{exe_name}.backup"
    
    # 批处理脚本内容
    bat_content = f'''@echo off
chcp 65001 >nul
echo 正在更新程序...

REM 等待主程序完全退出（最多等待10秒）
set /a count=0
:wait_loop
tasklist /FI "IMAGENAME eq {exe_name}" 2>NUL | find /I /N "{exe_name}">NUL
if "%ERRORLEVEL%"=="0" (
    if %count% LSS 100 (
        timeout /t 0.1 /nobreak >nul
        set /a count+=1
        goto wait_loop
    )
)

REM 备份旧版本
echo 备份旧版本...
if exist "{current_exe_path}" (
    move /Y "{current_exe_path}" "{os.path.join(current_dir, backup_name)}" >nul
)

REM 复制新版本
echo 安装新版本...
move /Y "{new_exe_path}" "{current_exe_path}" >nul

REM 检查是否成功
if exist "{current_exe_path}" (
    echo 更新成功！正在启动新版本...
    
    REM 启动新版本
    start "" "{current_exe_path}"
    
    REM 等待一下确保程序启动
    timeout /t 2 /nobreak >nul
    
    REM 删除备份（可选）
    if exist "{os.path.join(current_dir, backup_name)}" (
        del /F /Q "{os.path.join(current_dir, backup_name)}" >nul
    )
) else (
    echo 更新失败！正在恢复旧版本...
    if exist "{os.path.join(current_dir, backup_name)}" (
        move /Y "{os.path.join(current_dir, backup_name)}" "{current_exe_path}" >nul
        start "" "{current_exe_path}"
    )
    pause
)

REM 删除自己
del /F /Q "%~f0" >nul
exit
'''
    
    # 保存批处理脚本
    bat_path = os.path.join(current_dir, '_update.bat')
    with open(bat_path, 'w', encoding='gbk') as f:  # Windows 批处理使用 GBK 编码
        f.write(bat_content)
    
    return bat_path

def apply_update(new_exe_path):
    """应用更新"""
    from query_tool.utils.logger import logger
    
    try:
        # 获取当前程序路径
        if getattr(sys, 'frozen', False):
            # 打包后的 exe
            current_exe = sys.executable
        else:
            # 开发环境
            current_exe = os.path.abspath(__file__)
        
        logger.info(f"当前程序: {current_exe}")
        logger.info(f"新版本: {new_exe_path}")
        
        # 创建更新脚本
        bat_path = create_update_script(new_exe_path, current_exe)
        logger.info(f"更新脚本: {bat_path}")
        
        # 启动批处理脚本（隐藏窗口）
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        subprocess.Popen(
            [bat_path],
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        
        logger.info("更新脚本已启动，程序即将退出...")
        
        # 立即退出主程序
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"应用更新失败: {e}")
        raise
```

**使用示例：**
```python
# 在下载完成后调用
def on_download_complete(downloaded_file):
    """下载完成回调"""
    
    # 显示提示对话框
    msg_box = QMessageBox()
    msg_box.setWindowTitle("更新已下载")
    msg_box.setText("新版本已下载完成，需要重启程序才能完成更新。\n\n是否立即重启？")
    msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msg_box.setDefaultButton(QMessageBox.Yes)
    
    reply = msg_box.exec_()
    
    if reply == QMessageBox.Yes:
        # 应用更新（会自动退出程序）
        apply_update(downloaded_file)
    else:
        # 稍后更新，保存下载文件路径
        save_pending_update(downloaded_file)
```

#### 优点
- ✅ 实现简单，代码量少
- ✅ 不需要额外的可执行文件
- ✅ Windows 原生支持
- ✅ 可以自动清理
- ✅ 失败可以回滚

#### 缺点
- ⚠️ 批处理窗口可能短暂闪现（可以隐藏）
- ⚠️ 仅支持 Windows

---

### 方案二：独立更新器程序

#### 工作流程
```
1. 主程序下载新版本到临时目录
2. 主程序启动独立的更新器程序（updater.exe）
3. 主程序传递参数给更新器（旧文件路径、新文件路径）
4. 主程序立即退出
5. 更新器等待主程序退出
6. 更新器备份旧版本
7. 更新器复制新版本
8. 更新器启动新版本
9. 更新器自删除
```

#### 实现代码

**更新器程序（updater.py）：**
```python
# updater.py - 独立的更新器程序
import sys
import os
import time
import shutil
import subprocess
import psutil

def wait_for_process_exit(exe_path, timeout=10):
    """等待进程退出"""
    exe_name = os.path.basename(exe_path)
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        # 检查进程是否还在运行
        found = False
        for proc in psutil.process_iter(['name', 'exe']):
            try:
                if proc.info['name'] == exe_name:
                    found = True
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if not found:
            return True
        
        time.sleep(0.1)
    
    return False

def update_program(old_exe, new_exe):
    """执行更新"""
    try:
        print(f"正在更新程序...")
        print(f"旧版本: {old_exe}")
        print(f"新版本: {new_exe}")
        
        # 等待主程序退出
        print("等待主程序退出...")
        if not wait_for_process_exit(old_exe):
            print("警告: 主程序未完全退出，强制继续...")
        
        # 备份旧版本
        backup_path = old_exe + ".backup"
        if os.path.exists(old_exe):
            print("备份旧版本...")
            shutil.move(old_exe, backup_path)
        
        # 复制新版本
        print("安装新版本...")
        shutil.move(new_exe, old_exe)
        
        # 验证
        if os.path.exists(old_exe):
            print("更新成功！正在启动新版本...")
            
            # 启动新版本
            subprocess.Popen([old_exe])
            
            # 等待确保启动成功
            time.sleep(2)
            
            # 删除备份
            if os.path.exists(backup_path):
                try:
                    os.remove(backup_path)
                except:
                    pass
            
            print("完成！")
            return True
        else:
            print("更新失败！正在恢复...")
            if os.path.exists(backup_path):
                shutil.move(backup_path, old_exe)
                subprocess.Popen([old_exe])
            return False
            
    except Exception as e:
        print(f"更新出错: {e}")
        # 尝试恢复
        if os.path.exists(backup_path):
            try:
                shutil.move(backup_path, old_exe)
            except:
                pass
        return False

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("用法: updater.exe <旧程序路径> <新程序路径>")
        sys.exit(1)
    
    old_exe = sys.argv[1]
    new_exe = sys.argv[2]
    
    success = update_program(old_exe, new_exe)
    
    # 删除自己
    try:
        time.sleep(1)
        os.remove(sys.executable)
    except:
        pass
    
    sys.exit(0 if success else 1)
```

**主程序调用：**
```python
def apply_update_with_updater(new_exe_path):
    """使用独立更新器应用更新"""
    
    # 获取当前程序路径
    current_exe = sys.executable
    
    # 更新器路径（需要提前打包好）
    updater_path = os.path.join(os.path.dirname(current_exe), 'updater.exe')
    
    if not os.path.exists(updater_path):
        raise FileNotFoundError("找不到更新器程序")
    
    # 启动更新器
    subprocess.Popen([
        updater_path,
        current_exe,
        new_exe_path
    ])
    
    # 退出主程序
    sys.exit(0)
```

#### 优点
- ✅ 更专业，可以显示更新进度
- ✅ 可以处理复杂的更新逻辑
- ✅ 可以跨平台（需要分别打包）

#### 缺点
- ⚠️ 需要额外打包更新器程序
- ⚠️ 增加程序体积
- ⚠️ 实现复杂度较高

---

### 方案三：PowerShell 脚本（Windows 推荐）

#### 工作流程
类似批处理，但使用 PowerShell，功能更强大

#### 实现代码

```python
def create_powershell_update_script(new_exe_path, current_exe_path):
    """创建 PowerShell 更新脚本"""
    
    current_dir = os.path.dirname(current_exe_path)
    exe_name = os.path.basename(current_exe_path)
    backup_name = f"{exe_name}.backup"
    
    ps_content = f'''
# 设置编码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "正在更新程序..." -ForegroundColor Green

# 等待主程序退出
$processName = "{os.path.splitext(exe_name)[0]}"
$timeout = 10
$elapsed = 0

Write-Host "等待主程序退出..."
while ((Get-Process -Name $processName -ErrorAction SilentlyContinue) -and ($elapsed -lt $timeout)) {{
    Start-Sleep -Milliseconds 100
    $elapsed += 0.1
}}

# 备份旧版本
if (Test-Path "{current_exe_path}") {{
    Write-Host "备份旧版本..."
    Move-Item -Path "{current_exe_path}" -Destination "{os.path.join(current_dir, backup_name)}" -Force
}}

# 复制新版本
Write-Host "安装新版本..."
Move-Item -Path "{new_exe_path}" -Destination "{current_exe_path}" -Force

# 验证
if (Test-Path "{current_exe_path}") {{
    Write-Host "更新成功！正在启动新版本..." -ForegroundColor Green
    
    # 启动新版本
    Start-Process -FilePath "{current_exe_path}"
    
    # 等待启动
    Start-Sleep -Seconds 2
    
    # 删除备份
    if (Test-Path "{os.path.join(current_dir, backup_name)}") {{
        Remove-Item -Path "{os.path.join(current_dir, backup_name)}" -Force -ErrorAction SilentlyContinue
    }}
}} else {{
    Write-Host "更新失败！正在恢复..." -ForegroundColor Red
    if (Test-Path "{os.path.join(current_dir, backup_name)}") {{
        Move-Item -Path "{os.path.join(current_dir, backup_name)}" -Destination "{current_exe_path}" -Force
        Start-Process -FilePath "{current_exe_path}"
    }}
    Read-Host "按回车键退出"
}}

# 删除自己
Remove-Item -Path $PSCommandPath -Force -ErrorAction SilentlyContinue
'''
    
    # 保存 PowerShell 脚本
    ps_path = os.path.join(current_dir, '_update.ps1')
    with open(ps_path, 'w', encoding='utf-8-sig') as f:  # UTF-8 with BOM
        f.write(ps_content)
    
    return ps_path

def apply_update_with_powershell(new_exe_path):
    """使用 PowerShell 应用更新"""
    
    current_exe = sys.executable
    ps_path = create_powershell_update_script(new_exe_path, current_exe)
    
    # 启动 PowerShell 脚本（隐藏窗口）
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    
    subprocess.Popen([
        'powershell.exe',
        '-ExecutionPolicy', 'Bypass',
        '-WindowStyle', 'Hidden',
        '-File', ps_path
    ], startupinfo=startupinfo)
    
    # 退出主程序
    sys.exit(0)
```

#### 优点
- ✅ 功能强大，错误处理好
- ✅ 不需要额外程序
- ✅ 可以完全隐藏窗口
- ✅ Windows 原生支持

#### 缺点
- ⚠️ 需要 PowerShell（Windows 7+ 自带）
- ⚠️ 执行策略可能需要 Bypass

---

## 推荐方案

### 对于你的项目，推荐：**方案一（批处理脚本）**

**理由：**
1. ✅ 实现最简单，代码量最少
2. ✅ 不需要额外的可执行文件
3. ✅ Windows 全版本支持
4. ✅ 可靠性高，失败可回滚
5. ✅ 维护成本低

### 完整的更新流程

```
用户操作流程：
1. 程序启动 → 后台检测更新
2. 发现新版本 → 显示更新提示对话框
3. 用户点击"立即更新" → 后台下载（显示进度）
4. 下载完成 → 显示"立即重启"对话框
5. 用户点击"立即重启" → 程序退出，批处理接管
6. 批处理自动完成替换 → 启动新版本
7. 用户看到新版本启动 → 完成

技术流程：
1. check_update() → 检测版本
2. download_update() → 下载新版本到临时目录
3. verify_file() → 校验文件完整性
4. create_update_script() → 创建批处理脚本
5. subprocess.Popen() → 启动批处理
6. sys.exit(0) → 主程序退出
7. 批处理等待 → 主程序完全退出
8. 批处理备份 → 旧版本改名
9. 批处理复制 → 新版本到位
10. 批处理启动 → 新版本运行
11. 批处理自删除 → 清理完成
```

---

## 注意事项

### 1. 文件权限
```python
# 确保有写入权限
def check_write_permission():
    """检查程序目录是否有写入权限"""
    try:
        test_file = os.path.join(os.path.dirname(sys.executable), '.write_test')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        return True
    except:
        return False

# 如果没有权限，提示用户以管理员身份运行
if not check_write_permission():
    QMessageBox.warning(None, "权限不足", 
        "程序目录没有写入权限，请以管理员身份运行程序后再更新。")
```

### 2. 防病毒软件
- 批处理脚本可能被误报为病毒
- 建议在脚本中添加注释说明用途
- 可以考虑对脚本进行签名

### 3. 用户数据保护
```python
# 更新前提醒用户保存数据
def prompt_save_before_update():
    """更新前提醒"""
    msg = QMessageBox()
    msg.setWindowTitle("准备更新")
    msg.setText("程序即将重启以完成更新。\n\n请确保已保存所有数据。")
    msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    return msg.exec_() == QMessageBox.Ok
```

### 4. 更新失败处理
```python
# 在下次启动时检查是否有备份文件
def check_failed_update():
    """检查是否有失败的更新"""
    backup_file = sys.executable + ".backup"
    if os.path.exists(backup_file):
        # 发现备份文件，说明可能更新失败
        msg = QMessageBox()
        msg.setWindowTitle("更新状态")
        msg.setText("检测到上次更新可能未完成。\n\n是否删除备份文件？")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        
        if msg.exec_() == QMessageBox.Yes:
            try:
                os.remove(backup_file)
            except:
                pass
```

---

## 测试建议

### 测试场景
1. ✅ 正常更新流程
2. ✅ 更新过程中断电
3. ✅ 新版本文件损坏
4. ✅ 磁盘空间不足
5. ✅ 没有写入权限
6. ✅ 防病毒软件拦截
7. ✅ 用户取消更新
8. ✅ 网络中断重试

### 测试代码
```python
def test_update_process():
    """测试更新流程"""
    
    # 1. 创建测试用的新版本文件
    test_new_exe = "test_new_version.exe"
    shutil.copy(sys.executable, test_new_exe)
    
    # 2. 执行更新
    try:
        apply_update(test_new_exe)
    except Exception as e:
        print(f"更新测试失败: {e}")
    
    # 注意：这个测试会导致程序退出
```

---

**文档版本**: 1.0  
**创建日期**: 2026-02-24  
**作者**: Kiro AI Assistant
