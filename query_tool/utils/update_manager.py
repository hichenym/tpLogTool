"""
更新管理器
统一管理更新检查、下载和安装
"""
from typing import Optional
from PyQt5.QtCore import QObject, pyqtSignal

from query_tool.utils.logger import logger
from query_tool.utils.update_checker import UpdateChecker, VersionInfo
from query_tool.utils.update_downloader import UpdateDownloader, UpdateInstaller


class UpdateManager(QObject):
    """更新管理器"""
    
    # 信号
    update_available = pyqtSignal(object)  # VersionInfo
    download_progress = pyqtSignal(int, int)  # (已下载, 总大小)
    download_finished = pyqtSignal(bool, str)  # (是否成功, 消息/文件路径)
    
    def __init__(self, current_version: str, parent=None):
        super().__init__(parent)
        
        self.current_version = current_version
        self.checker = UpdateChecker(current_version)
        self.downloader = UpdateDownloader()
        
        self.latest_version_info: Optional[VersionInfo] = None
        self.downloaded_file_path: Optional[str] = None
    
    def check_update_async(self):
        """异步检查更新"""
        def callback(has_update, version_info, message):
            if has_update:
                logger.info(f"发现新版本: {version_info}")
                self.latest_version_info = version_info
                self.update_available.emit(version_info)
            else:
                logger.info(f"检查更新: {message}")
        
        self.checker.check_update_async(callback)
    
    def check_update_sync(self):
        """同步检查更新"""
        has_update, version_info, message = self.checker.check_update()
        
        if has_update:
            self.latest_version_info = version_info
            return True, version_info, message
        else:
            return False, None, message
    
    def download_update(self, version_info: VersionInfo):
        """
        下载更新
        
        如果已有下载在进行中，则不重复下载。
        
        Args:
            version_info: 版本信息
        """
        # 检查是否已有下载在进行中
        if self.downloader.is_downloading():
            logger.warning(f"已有下载在进行中，忽略重复下载请求")
            return
        
        filename = f"TPQueryTool_{version_info.version}.exe"
        
        logger.info(f"开始下载更新: {filename}")
        
        # 获取期望的哈希值
        expected_hash = version_info.file_hash if hasattr(version_info, 'file_hash') else None
        hash_algorithm = version_info.hash_algorithm if hasattr(version_info, 'hash_algorithm') else 'sha256'
        
        if expected_hash:
            logger.info(f"将使用 {hash_algorithm.upper()} 验证文件完整性")
            logger.info(f"期望哈希: {expected_hash}")
        else:
            logger.warning("未提供文件哈希值，将跳过完整性验证")
        
        self.downloader.download(
            url=version_info.download_url,
            filename=filename,
            expected_hash=expected_hash,
            hash_algorithm=hash_algorithm,
            progress_callback=self._on_download_progress,
            finished_callback=self._on_download_finished
        )
    
    def _on_download_progress(self, downloaded: int, total: int):
        """下载进度回调"""
        self.download_progress.emit(downloaded, total)
    
    def _on_download_finished(self, success: bool, result: str):
        """下载完成回调"""
        if success:
            self.downloaded_file_path = result
            logger.info(f"下载完成: {result}")
        else:
            logger.error(f"下载失败: {result}")
        
        self.download_finished.emit(success, result)
    
    def cancel_download(self):
        """取消下载"""
        self.downloader.cancel_download()
    
    def apply_update(self, restart: bool = True):
        """
        应用更新
        
        Args:
            restart: 是否重启程序
        """
        if not self.downloaded_file_path:
            logger.error("没有可用的更新文件")
            return
        
        try:
            UpdateInstaller.apply_update(self.downloaded_file_path, restart)
        except Exception as e:
            logger.error(f"应用更新失败: {e}")
            raise
    
    def get_update_strategy(self) -> str:
        """
        获取更新策略
        
        Returns:
            str: manual, prompt, 或 silent
        """
        if self.latest_version_info:
            return self.latest_version_info.update_strategy
        
        # 尝试从缓存加载
        cached_info = self.checker._load_cache()
        if cached_info:
            return cached_info.update_strategy
        
        return 'prompt'  # 默认策略
    
    def should_auto_check(self) -> bool:
        """是否应该自动检查更新"""
        return self.checker.should_auto_check(self.latest_version_info)
    
    def skip_version(self, version: str):
        """
        跳过指定版本
        
        Args:
            version: 要跳过的版本号
        """
        self.checker.skip_version(version)
    
    def clean_old_downloads(self):
        """清理旧的下载文件"""
        self.downloader.clean_old_downloads()
