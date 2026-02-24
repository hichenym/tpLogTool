# 自动更新完整实现指南

## 📊 更新策略对比

### 三种更新方式

| 特性 | 手动更新 | 提示更新 | 静默更新 |
|------|---------|---------|---------|
| 用户操作 | 6+ 步骤 | 2 次点击 | 0 次点击 |
| 等待时间 | 需要等待 | 需要等待 | 无需等待 |
| 打断工作 | 是 | 是 | 否 |
| 更新率 | <10% | 30-50% | >90% |
| 用户体验 | 差 | 中 | 优秀 |
| 实现难度 | 低 | 中 | 高 |

### 推荐：静默更新 ⭐

**用户视角**：
1. 启动程序 → 正常使用（无任何提示）
2. （后台悄悄下载更新）
3. 关闭程序 → 正常退出
4. 再次启动 → 已经是新版本
5. （可选）显示"已更新到 V3.0.1"

**技术流程**：
1. 程序启动 → 后台线程检测更新
2. 发现新版本 → 后台下载到临时目录
3. 下载完成 → 标记"待更新"状态
4. 用户关闭 → closeEvent 触发
5. 创建批处理脚本 → 启动脚本并退出
6. 批处理等待 → 主程序完全退出
7. 批处理替换 → 新版本覆盖旧版本
8. 批处理启动 → 新版本自动运行

---

## 🎯 静默更新实现

### 1. 更新管理器

```python
# query_tool/utils/updater.py
import os
import sys
import json
import requests
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from PyQt5.QtCore import QThread, pyqtSignal
from query_tool.utils.logger import logger
from query_tool.version import get_version

class UpdateChecker(QThread):
    """后台更新检测线程"""
    
    # 信号
    update_available = pyqtSignal(dict)  # 发现新版本
    download_progress = pyqtSignal(int, int)  # 下载进度 (已下载, 总大小)
    download_complete = pyqtSignal(str)  # 下载完成 (文件路径)
    download_failed = pyqtSignal(str)  # 下载失败 (错误信息)
    
    def __init__(self):
        super().__init__()
        self.current_version = get_version()  # (3, 0, 0)
        self.cache_dir = Path.home() / '.TPQueryTool' / 'update'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 配置
        self.version_urls = [
            'https://cdn.jsdelivr.net/gh/用户名/仓库名@main/version.json',
            'https://raw.githubusercontent.com/用户名/仓库名/main/version.json',
        ]
        
        self.check_interval = timedelta(hours=12)  # 检测间隔
        self.auto_download = True  # 是否自动下载
        
    def run(self):
        """后台运行"""
        try:
            # 1. 检查是否需要检测更新
            if not self._should_check_update():
                logger.info("更新检测：跳过（缓存未过期）")
                return
            
            # 2. 检测更新
            logger.info("更新检测：开始检测...")
            update_info = self._check_update()
            
            if not update_info:
                logger.info("更新检测：已是最新版本")
                self._save_check_time()
                return
            
            logger.info(f"更新检测：发现新版本 {update_info['version']}")
            self.update_available.emit(update_info)
            
            # 3. 自动下载
            if self.auto_download:
                logger.info("更新下载：开始下载...")
                downloaded_file = self._download_update(update_info)
                
                if downloaded_file:
                    logger.info(f"更新下载：完成 {downloaded_file}")
                    self.download_complete.emit(downloaded_file)
                    
                    # 标记待更新
                    self._mark_pending_update(downloaded_file, update_info)
                else:
                    logger.error("更新下载：失败")
                    self.download_failed.emit("下载失败")
            
        except Exception as e:
            logger.error(f"更新检测异常: {e}")
    
    def _should_check_update(self):
        """是否需要检测更新"""
        cache_file = self.cache_dir / 'last_check.json'
        
        if not cache_file.exists():
            return True
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            last_check = datetime.fromisoformat(data['timestamp'])
            return datetime.now() - last_check > self.check_interval
        except:
            return True
    
    def _save_check_time(self):
        """保存检测时间"""
        cache_file = self.cache_dir / 'last_check.json'
        data = {'timestamp': datetime.now().isoformat()}
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    
    def _check_update(self):
        """检测更新"""
        for url in self.version_urls:
            try:
                response = requests.get(url, timeout=5)
                response.raise_for_status()
                remote_info = response.json()
                
                # 比较版本号
                remote_version = self._parse_version(remote_info['version'])
                if remote_version > self.current_version:
                    return remote_info
                
                return None
                
            except Exception as e:
                logger.warning(f"检测更新失败 ({url}): {e}")
                continue
        
        return None
    
    def _parse_version(self, version_str):
        """解析版本号字符串"""
        # "3.0.1" -> (3, 0, 1)
        parts = version_str.split('.')
        return tuple(int(p) for p in parts)
    
    def _download_update(self, update_info):
        """下载更新"""
        download_url = update_info['download_url']
        file_name = os.path.basename(download_url)
        save_path = self.cache_dir / file_name
        
        try:
            # 如果已经下载过，检查文件大小
            if save_path.exists():
                file_size = save_path.stat().st_size
                expected_size = int(update_info['file_size_mb'] * 1024 * 1024)
                
                if abs(file_size - expected_size) < 1024:  # 允许 1KB 误差
                    logger.info("更新下载：文件已存在，跳过下载")
                    return str(save_path)
            
            # 下载文件
            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        self.download_progress.emit(downloaded, total_size)
            
            # 验证文件大小
            if save_path.stat().st_size < total_size * 0.95:  # 允许 5% 误差
                logger.error("更新下载：文件不完整")
                save_path.unlink()
                return None
            
            return str(save_path)
            
        except Exception as e:
            logger.error(f"更新下载失败: {e}")
            if save_path.exists():
                save_path.unlink()
            return None
    
    def _mark_pending_update(self, file_path, update_info):
        """标记待更新"""
        pending_file = self.cache_dir / 'pending_update.json'
        data = {
            'file_path': file_path,
            'version': update_info['version'],
            'timestamp': datetime.now().isoformat()
        }
        
        with open(pending_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"标记待更新: {update_info['version']}")


class UpdateApplier:
    """更新应用器"""
    
    @staticmethod
    def has_pending_update():
        """检查是否有待更新"""
        cache_dir = Path.home() / '.TPQueryTool' / 'update'
        pending_file = cache_dir / 'pending_update.json'
        
        if not pending_file.exists():
            return None
        
        try:
            with open(pending_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 检查文件是否存在
            if not os.path.exists(data['file_path']):
                pending_file.unlink()
                return None
            
            return data
        except:
            return None
    
    @staticmethod
    def apply_update(new_exe_path):
        """应用更新（创建批处理脚本并退出）"""
        try:
            # 获取当前程序路径
            if getattr(sys, 'frozen', False):
                current_exe = sys.executable
            else:
                logger.warning("开发环境不支持自动更新")
                return False
            
            current_dir = os.path.dirname(current_exe)
            exe_name = os.path.basename(current_exe)
            backup_name = f"{exe_name}.backup"
            
            # 创建批处理脚本
            bat_content = f'''@echo off
chcp 65001 >nul

REM 等待主程序完全退出
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
if exist "{current_exe}" (
    move /Y "{current_exe}" "{os.path.join(current_dir, backup_name)}" >nul
)

REM 复制新版本
move /Y "{new_exe_path}" "{current_exe}" >nul

REM 检查是否成功
if exist "{current_exe}" (
    REM 启动新版本
    start "" "{current_exe}"
    
    REM 等待启动
    timeout /t 2 /nobreak >nul
    
    REM 删除备份
    if exist "{os.path.join(current_dir, backup_name)}" (
        del /F /Q "{os.path.join(current_dir, backup_name)}" >nul
    )
) else (
    REM 恢复旧版本
    if exist "{os.path.join(current_dir, backup_name)}" (
        move /Y "{os.path.join(current_dir, backup_name)}" "{current_exe}" >nul
        start "" "{current_exe}"
    )
)

REM 删除待更新标记
del /F /Q "{Path.home() / '.TPQueryTool' / 'update' / 'pending_update.json'}" >nul 2>nul

REM 删除自己
del /F /Q "%~f0" >nul
exit
'''
            
            # 保存批处理脚本
            bat_path = os.path.join(current_dir, '_update.bat')
            with open(bat_path, 'w', encoding='gbk') as f:
                f.write(bat_content)
            
            logger.info(f"更新脚本已创建: {bat_path}")
            
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
            return True
            
        except Exception as e:
            logger.error(f"应用更新失败: {e}")
            return False
    
    @staticmethod
    def clear_pending_update():
        """清除待更新标记"""
        cache_dir = Path.home() / '.TPQueryTool' / 'update'
        pending_file = cache_dir / 'pending_update.json'
        
        if pending_file.exists():
            pending_file.unlink()
```

### 2. 主窗口集成

```python
# query_tool/main.py
from PyQt5.QtWidgets import QMainWindow, QMessageBox
from PyQt5.QtCore import Qt
from query_tool.utils.updater import UpdateChecker, UpdateApplier
from query_tool.utils.logger import logger

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.update_checker = None
        self.pending_update_file = None
        
        # 启动时检查是否刚更新完成
        self.check_update_completed()
        
        # 启动后台更新检测
        self.start_update_check()
    
    def check_update_completed(self):
        """检查是否刚完成更新"""
        # 检查是否有更新完成标记
        update_completed_file = Path.home() / '.TPQueryTool' / 'update' / 'update_completed.json'
        
        if update_completed_file.exists():
            try:
                with open(update_completed_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 显示更新完成提示（可选）
                from query_tool.version import get_version_string
                QMessageBox.information(
                    self,
                    "更新完成",
                    f"程序已成功更新到 {get_version_string()}\n\n"
                    f"更新内容：\n" + "\n".join(f"• {item}" for item in data.get('changelog', [])[:5])
                )
                
                # 删除标记文件
                update_completed_file.unlink()
                
            except Exception as e:
                logger.error(f"读取更新完成标记失败: {e}")
    
    def start_update_check(self):
        """启动后台更新检测"""
        self.update_checker = UpdateChecker()
        
        # 连接信号（静默模式不需要连接 update_available）
        self.update_checker.download_complete.connect(self.on_update_downloaded)
        self.update_checker.download_failed.connect(self.on_update_failed)
        
        # 启动后台线程
        self.update_checker.start()
        
        logger.info("后台更新检测已启动")
    
    def on_update_downloaded(self, file_path):
        """更新下载完成（静默）"""
        self.pending_update_file = file_path
        logger.info(f"更新已下载: {file_path}")
        # 不显示任何提示，等待用户关闭程序
    
    def on_update_failed(self, error):
        """更新下载失败（静默）"""
        logger.error(f"更新下载失败: {error}")
        # 不显示任何提示，下次启动再试
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 检查是否有待更新
        pending = UpdateApplier.has_pending_update()
        
        if pending:
            logger.info("检测到待更新，准备应用更新...")
            
            # 应用更新（会自动退出程序）
            if UpdateApplier.apply_update(pending['file_path']):
                # 创建更新完成标记（供下次启动使用）
                self.create_update_completed_mark(pending)
                
                # 接受关闭事件，程序退出
                event.accept()
                
                # 强制退出（确保批处理脚本能接管）
                import sys
                sys.exit(0)
            else:
                logger.error("应用更新失败，正常退出")
                # 清除待更新标记
                UpdateApplier.clear_pending_update()
        
        # 正常关闭流程
        event.accept()
    
    def create_update_completed_mark(self, pending_info):
        """创建更新完成标记"""
        try:
            cache_dir = Path.home() / '.TPQueryTool' / 'update'
            mark_file = cache_dir / 'update_completed.json'
            
            # 读取 version.json 获取更新日志
            version_url = 'https://cdn.jsdelivr.net/gh/用户名/仓库名@main/version.json'
            response = requests.get(version_url, timeout=5)
            version_info = response.json()
            
            data = {
                'version': pending_info['version'],
                'timestamp': datetime.now().isoformat(),
                'changelog': version_info.get('changelog', [])
            }
            
            with open(mark_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"创建更新完成标记失败: {e}")
```

### 3. 配置选项（可选）

```python
# 在设置对话框中添加更新选项
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 自动更新选项
        self.auto_update_checkbox = QCheckBox("启用自动更新")
        self.auto_update_checkbox.setChecked(True)
        
        self.silent_update_checkbox = QCheckBox("静默更新（不提示）")
        self.silent_update_checkbox.setChecked(True)
        
        # 保存到配置
        # ...
```

## 📊 用户体验对比

### 传统更新方式
```
1. 启动程序
2. 弹窗："发现新版本，是否更新？"
3. 点击"是" → 开始下载
4. 等待下载（显示进度条）
5. 下载完成 → 弹窗："是否立即重启？"
6. 点击"是" → 程序退出
7. 等待更新脚本运行
8. 新版本启动
```
**用户操作**: 3次点击，等待下载

### 静默更新方式
```
1. 启动程序 → 正常使用
2. （后台悄悄下载）
3. 关闭程序 → 正常退出
4. 再次启动 → 已经是新版本
5. （可选）提示："已更新到 V3.0.1"
```
**用户操作**: 0次点击，无需等待

## ⚙️ 配置建议

### 1. 检测频率
```python
self.check_interval = timedelta(hours=12)  # 推荐 12 小时
```

### 2. 下载时机
```python
# 方案A：立即下载（推荐）
self.auto_download = True

# 方案B：空闲时下载
def start_download_when_idle():
    # 检测用户是否空闲（如 5 分钟无操作）
    if idle_time > 300:
        start_download()
```

### 3. 网络策略
```python
# 使用多个下载源
download_sources = [
    'https://github.com/user/repo/releases/download/v3.0.1/查询工具.exe',
    'https://ghproxy.com/https://github.com/user/repo/releases/download/v3.0.1/查询工具.exe',
]
```

## 🔒 安全考虑

### 1. 文件校验
```python
def verify_download(file_path, expected_size):
    """验证下载文件"""
    actual_size = os.path.getsize(file_path)
    
    # 大小校验
    if abs(actual_size - expected_size) > 1024:
        return False
    
    # TODO: SHA256 校验（如果 version.json 提供）
    
    return True
```

### 2. 权限检查
```python
def check_update_permission():
    """检查是否有更新权限"""
    try:
        test_file = os.path.join(os.path.dirname(sys.executable), '.write_test')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        return True
    except:
        return False
```

### 3. 回滚机制
批处理脚本已包含自动回滚逻辑，更新失败会自动恢复旧版本。

## 🧪 测试清单

- [ ] 正常更新流程
- [ ] 下载中断重试
- [ ] 磁盘空间不足
- [ ] 没有写入权限
- [ ] 更新文件损坏
- [ ] 网络完全断开
- [ ] 用户强制关闭
- [ ] 防病毒软件拦截

## 📝 总结

**静默更新的核心**：
1. ✅ 后台检测 + 后台下载
2. ✅ 不打扰用户
3. ✅ 关闭时自动替换
4. ✅ 下次启动已更新

**实现要点**：
1. 使用 QThread 后台检测
2. 下载到临时目录
3. 标记"待更新"状态
4. closeEvent 触发更新
5. 批处理脚本接管

**用户体验**：
- 无感知更新
- 零操作成本
- 始终保持最新

---

**最后更新**: 2026-02-24
