"""
自动更新检查模块
"""
import requests
import threading
import shutil
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta

def _flag_is_true(value: Any, default: bool = False) -> bool:
    """Only bool True or string 'true' should be treated as enabled."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value is True
    return str(value).strip().lower() == "true"


def _normalize_update_strategy(value: Any, default: str = "prompt") -> str:
    """Normalize update strategy and fallback to auto for invalid values."""
    if value is None:
        return default

    normalized = str(value).strip().lower()
    valid_values = {"manual", "prompt", "silent", "auto"}
    if normalized in valid_values:
        return normalized
    return "auto"


class VersionInfo:
    """版本信息"""
    
    def __init__(self, data: Dict[str, Any]):
        self.version = data.get('version', '')
        self.build_date = data.get('build_date', '')
        self.download_url = data.get('download_url', '')
        self.file_size_mb = data.get('file_size_mb', 0)
        self.file_size_bytes = data.get('file_size_bytes', 0)
        self.file_hash = data.get('file_hash', '')
        self.hash_algorithm = data.get('hash_algorithm', 'sha256')
        self.checksum_url = data.get('checksum_url', '')
        self.release_notes_url = data.get('release_notes_url', '')
        self.min_version = data.get('min_version')
        self.update_strategy = _normalize_update_strategy(
            data.get('update_strategy'),
            default='prompt',
        )
        self.show_change = _flag_is_true(data.get('show_change'), default=True)
        # 兼容远程返回的 changelog 可能为字符串或列表。
        # 需要保证 self.changelog 为字符串列表，UI 侧按条目展示。
        changelog = data.get('changelog', [])
        if isinstance(changelog, str):
            # 按行拆分，忽略空行并去除首尾空白
            lines = [line.strip() for line in changelog.splitlines()]
            self.changelog = [ln for ln in lines if ln]
        elif isinstance(changelog, list):
            # 确保每个元素为字符串，去除空元素并做 strip
            processed = []
            for item in changelog:
                try:
                    s = str(item).strip()
                    if s:
                        processed.append(s)
                except Exception:
                    continue
            self.changelog = processed
        else:
            # 兜底：将其转换为字符串并按行拆分
            try:
                s = str(changelog)
                lines = [line.strip() for line in s.splitlines()]
                self.changelog = [ln for ln in lines if ln]
            except Exception:
                self.changelog = []
    
    def __str__(self):
        return f"V{self.version} ({self.build_date})"


class UpdateChecker:
    """更新检查器"""
    
    # GitHub Raw URL
    VERSION_URL = "https://raw.githubusercontent.com/hichenym/tpLogTool/main/version.json"
    
    # 仅用于清理历史版本留下的磁盘缓存；新版本绝不创建该目录或文件。
    LEGACY_CACHE_DIR = Path.home() / '.TPQueryTool' / 'update'
    LEGACY_CACHE_FILE = LEGACY_CACHE_DIR / 'version_cache.json'
    
    # 缓存有效期（小时）
    CACHE_DURATION = 6
    _memory_cache_data: Optional[Dict[str, Any]] = None
    _memory_cache_at: Optional[datetime] = None
    _memory_cache_lock = threading.Lock()
    
    def __init__(self, current_version: str):
        """
        初始化更新检查器
        
        Args:
            current_version: 当前版本号，如 "3.1.0"
        """
        self.current_version = current_version
        self.clear_legacy_cache()

    @classmethod
    def clear_legacy_cache(cls):
        """删除旧版落盘更新缓存，避免在用户目录留下更新信息。"""
        try:
            shutil.rmtree(cls.LEGACY_CACHE_DIR, ignore_errors=True)
        except Exception:
            pass
    
    def _compare_version(self, version1: str, version2: str) -> int:
        """
        比较两个版本号
        
        Args:
            version1: 版本号1
            version2: 版本号2
        
        Returns:
            int: 1 表示 version1 > version2
                 0 表示 version1 == version2
                -1 表示 version1 < version2
        """
        try:
            v1_parts = [int(x) for x in version1.split('.')]
            v2_parts = [int(x) for x in version2.split('.')]
            
            # 补齐长度
            while len(v1_parts) < 3:
                v1_parts.append(0)
            while len(v2_parts) < 3:
                v2_parts.append(0)
            
            for i in range(3):
                if v1_parts[i] > v2_parts[i]:
                    return 1
                elif v1_parts[i] < v2_parts[i]:
                    return -1
            
            return 0
        except Exception:
            return 0
    
    def _fetch_version_info(self) -> Optional[VersionInfo]:
        """
        从远程获取版本信息
        
        Returns:
            VersionInfo: 版本信息，失败返回 None
        """
        # 只使用 GitHub Raw URL
        url = self.VERSION_URL
        
        try:
            response = requests.get(
                url,
                timeout=10,
                headers={'User-Agent': 'TPQueryTool/3.1.0'}
            )
            response.raise_for_status()
            
            data = response.json()
            version_info = VersionInfo(data)

            # 仅缓存到当前进程内存，绝不写入用户目录。
            self._save_cache(data)
            
            return version_info
            
        except Exception:
            # 仓库不可访问或响应异常时静默失效，不影响主程序。
            return None
    
    def _get_version_info_with_cache(self) -> Optional[VersionInfo]:
        """
        获取版本信息（优先使用缓存）
        
        Returns:
            VersionInfo: 版本信息，失败返回 None
        """
        # 优先使用当前进程内存中的版本信息。
        cached_info = self._load_cache()
        if cached_info:
            return cached_info
        return self._fetch_version_info()
    
    def _save_cache(self, data: Dict[str, Any]):
        """保存到进程内存。"""
        with self._memory_cache_lock:
            type(self)._memory_cache_data = dict(data)
            type(self)._memory_cache_at = datetime.now()

    @classmethod
    def get_memory_cache_data(cls) -> Dict[str, Any]:
        """返回未过期的进程内存缓存副本。"""
        with cls._memory_cache_lock:
            if (
                not cls._memory_cache_data
                or not cls._memory_cache_at
                or datetime.now() - cls._memory_cache_at > timedelta(hours=cls.CACHE_DURATION)
            ):
                return {}
            return dict(cls._memory_cache_data)
    
    def _load_cache(self) -> Optional[VersionInfo]:
        """从进程内存加载有效缓存。"""
        try:
            with self._memory_cache_lock:
                cache_data = type(self)._memory_cache_data
                cached_at = type(self)._memory_cache_at
            if not cache_data or not cached_at:
                return None
            if datetime.now() - cached_at > timedelta(hours=self.CACHE_DURATION):
                return None
            return VersionInfo(cache_data)
        except Exception:
            return None
    
    def _check_compatibility(self, version_info: VersionInfo) -> Tuple[bool, str]:
        """
        检查版本兼容性
        
        Args:
            version_info: 版本信息
        
        Returns:
            Tuple[bool, str]: (是否兼容, 提示信息)
        """
        if not version_info.min_version:
            return True, ""
        
        if self._compare_version(self.current_version, version_info.min_version) < 0:
            message = (
                f"当前版本 V{self.current_version} 无法直接升级到 V{version_info.version}\n"
                f"需要先升级到 V{version_info.min_version} 或更高版本"
            )
            return False, message
        
        return True, ""
    
    def check_update(self) -> Tuple[bool, Optional[VersionInfo], str]:
        """
        检查更新（优先使用缓存，5小时后更新）
        
        Returns:
            Tuple[bool, Optional[VersionInfo], str]:
                - has_update: 是否有更新
                - version_info: 版本信息（如果有更新）
                - message: 提示信息
        """
        try:
            # 优先使用缓存的版本信息
            version_info = self._get_version_info_with_cache()
            
            if not version_info:
                return False, None, ""
            
            # 比较版本号
            compare_result = self._compare_version(version_info.version, self.current_version)
            
            if compare_result <= 0:
                return False, None, "当前已是最新版本"
            
            # 检查是否被用户跳过
            if self._is_version_skipped(version_info.version):
                return False, None, f"版本 {version_info.version} 已被跳过"
            
            # 检查兼容性
            compatible, compat_message = self._check_compatibility(version_info)
            
            if not compatible:
                return False, version_info, compat_message
            
            # 有可用更新
            message = f"发现新版本 V{version_info.version}"
            return True, version_info, message
            
        except Exception:
            return False, None, ""
    
    def check_update_force_refresh(self) -> Tuple[bool, Optional[VersionInfo], str]:
        """
        强制从远程检查更新（忽略缓存）
        
        Returns:
            Tuple[bool, Optional[VersionInfo], str]:
                - has_update: 是否有更新
                - version_info: 版本信息（如果有更新）
                - message: 提示信息
        """
        try:
            # 强制从远程获取最新版本信息
            version_info = self._fetch_version_info()
            
            if not version_info:
                return False, None, ""
            
            # 比较版本号
            compare_result = self._compare_version(version_info.version, self.current_version)
            
            if compare_result <= 0:
                return False, None, "当前已是最新版本"
            
            # 检查是否被用户跳过
            if self._is_version_skipped(version_info.version):
                return False, None, f"版本 {version_info.version} 已被跳过"
            
            # 检查兼容性
            compatible, compat_message = self._check_compatibility(version_info)
            
            if not compatible:
                return False, version_info, compat_message
            
            # 有可用更新
            message = f"发现新版本 V{version_info.version}"
            return True, version_info, message
            
        except Exception:
            return False, None, ""
    
    def check_update_async(self, callback):
        """
        异步检查更新（使用缓存）
        
        Args:
            callback: 回调函数，参数为 (has_update, version_info, message)
        """
        def _check():
            try:
                callback(*self.check_update())
            except Exception:
                pass
        
        thread = threading.Thread(target=_check, daemon=True)
        thread.start()
    
    def check_update_async_force_refresh(self, callback):
        """
        异步检查更新（强制刷新，忽略缓存）
        
        Args:
            callback: 回调函数，参数为 (has_update, version_info, message)
        """
        def _check():
            try:
                callback(*self.check_update_force_refresh())
            except Exception:
                pass
        
        thread = threading.Thread(target=_check, daemon=True)
        thread.start()
    
    def should_auto_check(self, version_info: Optional[VersionInfo] = None) -> bool:
        """
        根据更新策略判断是否应该自动检查
        
        Args:
            version_info: 版本信息（可选）
        
        Returns:
            bool: True 应该自动检查，False 不应该
        """
        if version_info is None:
            # 如果没有版本信息，尝试从缓存加载
            version_info = self._load_cache()
        
        if version_info is None:
            # 没有缓存，默认自动检查
            return True
        
        strategy = version_info.update_strategy
        
        if strategy == 'manual':
            return False  # 手动更新，不自动检查
        elif strategy in ['prompt', 'silent', 'auto']:
            return True   # 提示、静默下载、自动更新，自动检查
        else:
            return True   # 默认自动检查
    
    def skip_version(self, version: str):
        """
        跳过指定版本（保存到注册表）
        
        Args:
            version: 要跳过的版本号
        """
        try:
            import winreg
            
            # 打开或创建注册表键
            reg_key = winreg.CreateKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\TPQueryTool\Update"
            )
            
            try:
                # 设置跳过的版本号
                winreg.SetValueEx(reg_key, "SkippedVersion", 0, winreg.REG_SZ, version)
            finally:
                winreg.CloseKey(reg_key)
            
        except Exception:
            pass
    
    def _is_version_skipped(self, version: str) -> bool:
        """
        检查版本是否被跳过（从注册表读取）
        
        Args:
            version: 版本号
        
        Returns:
            bool: True 已跳过，False 未跳过
        """
        try:
            import winreg
            
            # 打开注册表键
            reg_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\TPQueryTool\Update",
                0,
                winreg.KEY_READ
            )
            
            try:
                # 读取跳过的版本号
                skipped_version, _ = winreg.QueryValueEx(reg_key, "SkippedVersion")
                
                if skipped_version == version:
                    return True
                else:
                    return False
                    
            finally:
                winreg.CloseKey(reg_key)
                
        except FileNotFoundError:
            # 注册表键不存在，说明没有跳过任何版本
            return False
        except Exception:
            return False
    
    def clear_skipped_version(self):
        """清除跳过的版本记录（从注册表删除）"""
        try:
            import winreg
            
            # 打开注册表键
            reg_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\TPQueryTool\Update",
                0,
                winreg.KEY_WRITE
            )
            
            try:
                # 删除跳过版本的值
                winreg.DeleteValue(reg_key, "SkippedVersion")
            except FileNotFoundError:
                pass
            finally:
                winreg.CloseKey(reg_key)
                
        except FileNotFoundError:
            pass
        except Exception:
            pass
    
    def get_skipped_version(self) -> Optional[str]:
        """
        获取当前跳过的版本号
        
        Returns:
            str: 跳过的版本号，如果没有则返回 None
        """
        try:
            import winreg
            
            reg_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\TPQueryTool\Update",
                0,
                winreg.KEY_READ
            )
            
            try:
                skipped_version, _ = winreg.QueryValueEx(reg_key, "SkippedVersion")
                return skipped_version
            finally:
                winreg.CloseKey(reg_key)
                
        except FileNotFoundError:
            return None
        except Exception:
            return None
