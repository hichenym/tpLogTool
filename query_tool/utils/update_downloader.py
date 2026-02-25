"""
更新下载模块
"""
import os
import sys
import subprocess
import tempfile
import hashlib
from pathlib import Path
from typing import Optional, Callable
import requests
from PyQt5.QtCore import QThread, pyqtSignal

from query_tool.utils.logger import logger


class DownloadThread(QThread):
    """下载线程"""
    
    # 信号
    progress = pyqtSignal(int, int)  # (已下载, 总大小)
    finished = pyqtSignal(bool, str)  # (是否成功, 消息/文件路径)
    
    def __init__(self, url: str, save_path: str, expected_hash: Optional[str] = None, hash_algorithm: str = 'sha256'):
        super().__init__()
        self.url = url
        self.save_path = save_path
        self.expected_hash = expected_hash  # 期望的文件哈希值
        self.hash_algorithm = hash_algorithm  # 哈希算法（sha256, md5等）
        self._is_cancelled = False
    
    def cancel(self):
        """取消下载"""
        self._is_cancelled = True
    
    def _calculate_file_hash(self, file_path: str, algorithm: str = 'sha256') -> str:
        """
        计算文件哈希值
        
        Args:
            file_path: 文件路径
            algorithm: 哈希算法（sha256, md5等）
        
        Returns:
            str: 哈希值（十六进制字符串）
        """
        try:
            hash_obj = hashlib.new(algorithm)
            
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    hash_obj.update(chunk)
            
            return hash_obj.hexdigest()
        except Exception as e:
            logger.error(f"计算文件哈希失败: {e}")
            return ""
    
    def _verify_partial_file(self, temp_path: str) -> bool:
        """
        验证部分下载的文件是否有效（用于断点续传）
        
        如果提供了期望的哈希值，会尝试验证部分文件。
        由于无法验证部分文件的完整哈希，这里只做基本检查。
        
        Args:
            temp_path: 临时文件路径
        
        Returns:
            bool: True 表示可以继续下载，False 表示需要重新下载
        """
        if not os.path.exists(temp_path):
            return True  # 文件不存在，可以开始下载
        
        file_size = os.path.getsize(temp_path)
        
        # 如果文件太小（小于1KB），可能是损坏的，重新下载
        if file_size < 1024:
            logger.warning(f"临时文件太小 ({file_size} 字节)，可能已损坏，将重新下载")
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.error(f"删除损坏的临时文件失败: {e}")
            return True
        
        logger.info(f"临时文件大小: {file_size / 1024 / 1024:.2f} MB，将尝试断点续传")
        return True
    
    def _verify_complete_file(self, file_path: str) -> bool:
        """
        验证完整下载的文件哈希值
        
        Args:
            file_path: 文件路径
        
        Returns:
            bool: True 表示验证通过，False 表示验证失败
        """
        if not self.expected_hash:
            logger.info("未提供期望的哈希值，跳过验证")
            return True
        
        logger.info(f"开始验证文件哈希 ({self.hash_algorithm})...")
        
        actual_hash = self._calculate_file_hash(file_path, self.hash_algorithm)
        
        if not actual_hash:
            logger.error("计算文件哈希失败")
            return False
        
        logger.info(f"期望哈希: {self.expected_hash}")
        logger.info(f"实际哈希: {actual_hash}")
        
        if actual_hash.lower() == self.expected_hash.lower():
            logger.info("✓ 文件哈希验证通过")
            return True
        else:
            logger.error("✗ 文件哈希验证失败，文件可能已损坏")
            return False
    
    def run(self):
        """执行下载（带重试机制、断点续传和哈希验证）"""
        max_retries = 10
        retry_delay = 5  # 秒
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logger.info(f"重试下载 (第 {attempt + 1}/{max_retries} 次)")
                    import time
                    time.sleep(retry_delay)
                
                # 使用临时文件，下载完成后再重命名
                temp_path = self.save_path + '.tmp'
                
                # 验证部分下载的文件
                if not self._verify_partial_file(temp_path):
                    logger.warning("部分文件验证失败，将重新下载")
                    downloaded = 0
                else:
                    # 检查是否有未完成的下载（断点续传）
                    downloaded = 0
                    if os.path.exists(temp_path):
                        downloaded = os.path.getsize(temp_path)
                        logger.info(f"发现未完成的下载，已下载 {downloaded / 1024 / 1024:.2f} MB，尝试断点续传")
                    else:
                        logger.info(f"开始下载...")
                
                # 设置请求头支持断点续传
                headers = {
                    'User-Agent': 'TPQueryTool/3.1.0',
                    'Accept': 'application/octet-stream'
                }
                
                # 如果有已下载的部分，添加 Range 头
                if downloaded > 0:
                    headers['Range'] = f'bytes={downloaded}-'
                
                # 使用更长的超时时间
                # connect timeout: 10秒, read timeout: 300秒(5分钟)
                response = requests.get(
                    self.url,
                    stream=True,
                    timeout=(10, 300),
                    headers=headers,
                    allow_redirects=True
                )
                
                # 检查是否支持断点续传
                if downloaded > 0:
                    if response.status_code == 206:
                        # 206 Partial Content - 支持断点续传
                        logger.info("服务器支持断点续传，继续下载")
                        mode = 'ab'  # 追加模式
                    elif response.status_code == 200:
                        # 200 OK - 不支持断点续传，重新下载
                        logger.warning("服务器不支持断点续传，重新下载")
                        downloaded = 0
                        mode = 'wb'  # 覆盖模式
                        # 删除旧的临时文件
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                    else:
                        response.raise_for_status()
                        mode = 'wb'
                else:
                    response.raise_for_status()
                    mode = 'wb'
                
                # 获取总大小
                if 'content-length' in response.headers:
                    content_length = int(response.headers['content-length'])
                    total_size = downloaded + content_length
                elif 'content-range' in response.headers:
                    # Content-Range: bytes 1000-2000/3000
                    content_range = response.headers['content-range']
                    total_size = int(content_range.split('/')[-1])
                else:
                    total_size = downloaded
                
                logger.info(f"总大小: {total_size / 1024 / 1024:.2f} MB, 已下载: {downloaded / 1024 / 1024:.2f} MB")
                
                # 确保目录存在
                os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
                
                # 下载文件
                with open(temp_path, mode) as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if self._is_cancelled:
                            logger.info("下载已取消")
                            # 不删除临时文件，保留用于断点续传
                            self.finished.emit(False, "下载已取消")
                            return
                        
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            self.progress.emit(downloaded, total_size)
                
                logger.info(f"下载完成，开始验证文件...")
                
                # 验证文件哈希
                if not self._verify_complete_file(temp_path):
                    # 哈希验证失败
                    logger.error("文件哈希验证失败，删除损坏的文件")
                    try:
                        os.remove(temp_path)
                    except Exception as e:
                        logger.error(f"删除损坏文件失败: {e}")
                    
                    # 如果还有重试机会，继续重试
                    if attempt < max_retries - 1:
                        logger.info("将重新下载...")
                        continue
                    else:
                        self.finished.emit(False, "文件哈希验证失败，文件可能已损坏")
                        return
                
                # 下载完成且验证通过，重命名临时文件
                if os.path.exists(self.save_path):
                    os.remove(self.save_path)
                os.rename(temp_path, self.save_path)
                
                logger.info(f"下载完成: {self.save_path} ({downloaded / 1024 / 1024:.2f} MB)")
                self.finished.emit(True, self.save_path)
                return  # 成功，退出重试循环
                
            except requests.exceptions.Timeout as e:
                logger.error(f"下载超时 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    self.finished.emit(False, f"下载超时，已重试 {max_retries} 次")
            
            except requests.exceptions.ConnectionError as e:
                logger.error(f"连接失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    self.finished.emit(False, f"网络连接失败，请检查网络连接或稍后重试")
            
            except requests.exceptions.HTTPError as e:
                logger.error(f"HTTP 错误: {e}")
                # HTTP 错误不重试（如 404）
                self.finished.emit(False, f"下载失败: {e}")
                return
            
            except Exception as e:
                logger.error(f"下载失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    self.finished.emit(False, f"下载失败: {str(e)}")


class UpdateDownloader:
    """更新下载器"""
    
    # 下载目录
    DOWNLOAD_DIR = Path.home() / '.TPQueryTool' / 'downloads'
    
    def __init__(self):
        self._ensure_download_dir()
        self._clean_temp_files()  # 清理残留的临时文件
        self.download_thread: Optional[DownloadThread] = None
        self._is_downloading = False  # 标记是否正在下载
        self._current_download_url = None  # 当前下载的 URL
    
    def _ensure_download_dir(self):
        """确保下载目录存在"""
        self.DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    def _clean_temp_files(self):
        """清理残留的临时文件（可选：保留用于断点续传）"""
        try:
            temp_files = list(self.DOWNLOAD_DIR.glob('*.tmp'))
            if temp_files:
                logger.info(f"发现 {len(temp_files)} 个临时文件")
                for temp_file in temp_files:
                    # 检查文件大小和修改时间
                    file_size = temp_file.stat().st_size
                    file_age_hours = (Path(temp_file).stat().st_mtime - 
                                     __import__('time').time()) / -3600
                    
                    # 只删除超过 24 小时的临时文件（保留最近的用于断点续传）
                    if file_age_hours > 24:
                        try:
                            temp_file.unlink()
                            logger.info(f"已删除过期临时文件: {temp_file.name} (已存在 {file_age_hours:.1f} 小时)")
                        except Exception as e:
                            logger.warning(f"删除临时文件失败 {temp_file.name}: {e}")
                    else:
                        logger.info(f"保留临时文件用于断点续传: {temp_file.name} ({file_size / 1024 / 1024:.1f} MB)")
        except Exception as e:
            logger.error(f"清理临时文件失败: {e}")
    
    def download(
        self,
        url: str,
        filename: str,
        expected_hash: Optional[str] = None,
        hash_algorithm: str = 'sha256',
        progress_callback: Optional[Callable[[int, int], None]] = None,
        finished_callback: Optional[Callable[[bool, str], None]] = None
    ) -> DownloadThread:
        """
        下载文件
        
        如果已有相同 URL 的下载在进行中，则复用现有下载线程。
        
        Args:
            url: 下载链接
            filename: 保存的文件名
            expected_hash: 期望的文件哈希值（可选）
            hash_algorithm: 哈希算法（默认 sha256）
            progress_callback: 进度回调 (已下载, 总大小)
            finished_callback: 完成回调 (是否成功, 消息/文件路径)
        
        Returns:
            DownloadThread: 下载线程
        """
        # 检查是否已有相同 URL 的下载在进行中
        if self._is_downloading and self._current_download_url == url:
            logger.info(f"相同 URL 的下载已在进行中，复用现有下载线程")
            
            # 连接新的回调
            if progress_callback:
                self.download_thread.progress.connect(progress_callback)
            
            if finished_callback:
                self.download_thread.finished.connect(finished_callback)
            
            return self.download_thread
        
        # 如果有其他下载在进行中，先取消
        if self._is_downloading and self.download_thread:
            logger.warning(f"取消之前的下载，开始新的下载")
            self.cancel_download()
        
        save_path = str(self.DOWNLOAD_DIR / filename)
        
        self.download_thread = DownloadThread(url, save_path, expected_hash, hash_algorithm)
        self._is_downloading = True
        self._current_download_url = url
        
        # 连接完成信号以更新下载状态
        def on_finished(success, result):
            self._is_downloading = False
            self._current_download_url = None
            if finished_callback:
                finished_callback(success, result)
        
        if progress_callback:
            self.download_thread.progress.connect(progress_callback)
        
        self.download_thread.finished.connect(on_finished)
        
        self.download_thread.start()
        
        return self.download_thread
    
    def cancel_download(self):
        """取消下载"""
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.cancel()
            self.download_thread.wait()
        
        self._is_downloading = False
        self._current_download_url = None
    
    def is_downloading(self) -> bool:
        """
        检查是否正在下载
        
        Returns:
            bool: True 表示正在下载，False 表示没有下载
        """
        return self._is_downloading and self.download_thread and self.download_thread.isRunning()
    
    def get_downloaded_file(self, filename: str) -> Optional[Path]:
        """
        获取已下载的文件
        
        Args:
            filename: 文件名
        
        Returns:
            Path: 文件路径，不存在返回 None
        """
        file_path = self.DOWNLOAD_DIR / filename
        return file_path if file_path.exists() else None
    
    def clean_old_downloads(self, keep_latest: int = 1):
        """
        清理旧的下载文件
        
        Args:
            keep_latest: 保留最新的几个文件
        """
        try:
            files = sorted(
                self.DOWNLOAD_DIR.glob('*.exe'),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            # 删除旧文件
            for file in files[keep_latest:]:
                try:
                    file.unlink()
                    logger.info(f"已删除旧文件: {file}")
                except Exception as e:
                    logger.error(f"删除文件失败 {file}: {e}")
        
        except Exception as e:
            logger.error(f"清理下载目录失败: {e}")
    
    def clean_all_temp_files(self):
        """清理所有临时文件（不考虑时间）"""
        try:
            temp_files = list(self.DOWNLOAD_DIR.glob('*.tmp'))
            if temp_files:
                logger.info(f"清理所有临时文件: {len(temp_files)} 个")
                for temp_file in temp_files:
                    try:
                        temp_file.unlink()
                        logger.info(f"已删除临时文件: {temp_file.name}")
                    except Exception as e:
                        logger.warning(f"删除临时文件失败 {temp_file.name}: {e}")
        except Exception as e:
            logger.error(f"清理临时文件失败: {e}")


class UpdateInstaller:
    """更新安装器"""
    
    @staticmethod
    def create_update_script(new_exe_path: str, current_exe_path: str, restart: bool = True) -> str:
        """
        创建更新脚本
        
        Args:
            new_exe_path: 新版本 exe 路径
            current_exe_path: 当前 exe 路径
            restart: 是否重启程序
        
        Returns:
            str: 脚本文件路径
        """
        # 创建临时批处理脚本
        script_content = f"""@echo off
chcp 65001 >nul
echo 正在更新程序...

:: 等待主程序退出
timeout /t 2 /nobreak >nul

:: 备份当前版本
if exist "{current_exe_path}.bak" del "{current_exe_path}.bak"
move "{current_exe_path}" "{current_exe_path}.bak"

:: 复制新版本
copy "{new_exe_path}" "{current_exe_path}"

:: 检查是否成功
if exist "{current_exe_path}" (
    echo 更新成功！
    :: 删除备份
    del "{current_exe_path}.bak"
    :: 删除下载的文件
    del "{new_exe_path}"
) else (
    echo 更新失败，恢复备份...
    move "{current_exe_path}.bak" "{current_exe_path}"
)

"""
        
        if restart:
            script_content += f"""
:: 重启程序
start "" "{current_exe_path}"
"""
        
        script_content += """
:: 删除脚本自身
del "%~f0"
"""
        
        # 保存脚本
        script_path = os.path.join(tempfile.gettempdir(), 'tpquerytool_update.bat')
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        logger.info(f"更新脚本已创建: {script_path}")
        
        return script_path
    
    @staticmethod
    def apply_update(new_exe_path: str, restart: bool = True):
        """
        应用更新
        
        Args:
            new_exe_path: 新版本 exe 路径
            restart: 是否重启程序
        """
        try:
            logger.info("=" * 60)
            logger.info("开始应用更新")
            logger.info(f"新版本文件: {new_exe_path}")
            logger.info(f"是否重启: {restart}")
            
            # 检查文件是否存在
            if not os.path.exists(new_exe_path):
                error_msg = f"更新文件不存在: {new_exe_path}"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)
            
            # 获取文件大小
            file_size = os.path.getsize(new_exe_path)
            logger.info(f"文件大小: {file_size / 1024 / 1024:.2f} MB")
            
            # 获取当前 exe 路径
            if getattr(sys, 'frozen', False):
                # 打包后的 exe
                current_exe_path = sys.executable
                logger.info(f"当前程序: {current_exe_path}")
            else:
                # 开发环境，不执行更新
                logger.warning("=" * 60)
                logger.warning("检测到开发环境（未打包），跳过更新")
                logger.warning("如需测试更新功能，请使用打包后的 exe")
                logger.warning("=" * 60)
                raise RuntimeError("开发环境不支持自动更新")
            
            # 创建更新脚本
            logger.info("创建更新脚本...")
            script_path = UpdateInstaller.create_update_script(
                new_exe_path,
                current_exe_path,
                restart
            )
            
            logger.info(f"更新脚本: {script_path}")
            
            # 执行脚本并退出程序
            logger.info("启动更新脚本...")
            subprocess.Popen(
                ['cmd', '/c', script_path],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            logger.info("更新脚本已启动，程序即将退出")
            logger.info("=" * 60)
            
            # 退出当前程序
            sys.exit(0)
            
        except Exception as e:
            logger.error(f"应用更新失败: {e}", exc_info=True)
            raise
