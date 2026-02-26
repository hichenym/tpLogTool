"""
自动更新检查模块
"""
import os
import json
import requests
import threading
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta

from query_tool.utils.logger import logger


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
        self.update_strategy = data.get('update_strategy', 'prompt')
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
    
    # 缓存目录
    CACHE_DIR = Path.home() / '.TPQueryTool' / 'update'
    
    # 缓存文件
    CACHE_FILE = CACHE_DIR / 'version_cache.json'
    
    # 缓存有效期（小时）
    CACHE_DURATION = 5  # 从 24 小时改为 5 小时
    
    def __init__(self, current_version: str):
        """
        初始化更新检查器
        
        Args:
            current_version: 当前版本号，如 "3.1.0"
        """
        self.current_version = current_version
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self):
        """确保缓存目录存在"""
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
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
        except Exception as e:
            logger.error(f"版本比较失败: {e}")
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
            logger.info(f"正在从远程获取版本信息...")
            
            response = requests.get(
                url,
                timeout=10,
                headers={'User-Agent': 'TPQueryTool/3.1.0'}
            )
            response.raise_for_status()
            
            data = response.json()
            version_info = VersionInfo(data)
            
            logger.info(f"成功获取版本信息: {version_info}")
            
            # 保存到缓存
            self._save_cache(data)
            
            return version_info
            
        except requests.RequestException as e:
            logger.warning(f"获取版本信息失败: {e}")
        except Exception as e:
            logger.error(f"解析版本信息失败: {e}")
        
        # 获取失败，尝试读取缓存
        logger.warning("远程获取失败，尝试读取缓存")
        return self._load_cache()
    
    def _get_version_info_with_cache(self) -> Optional[VersionInfo]:
        """
        获取版本信息（优先使用缓存）
        
        Returns:
            VersionInfo: 版本信息，失败返回 None
        """
        # 1. 先尝试从缓存加载
        cached_info = self._load_cache()
        
        if cached_info:
            logger.info(f"使用缓存的版本信息: {cached_info}")
            return cached_info
        
        # 2. 缓存不存在或已过期，从远程获取
        logger.info("缓存不可用，从远程获取版本信息")
        return self._fetch_version_info()
    
    def _save_cache(self, data: Dict[str, Any]):
        """保存缓存"""
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'version_info': data
            }
            
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logger.debug("版本信息已缓存")
        except Exception as e:
            logger.error(f"保存缓存失败: {e}")
    
    def _load_cache(self) -> Optional[VersionInfo]:
        """加载缓存"""
        try:
            if not self.CACHE_FILE.exists():
                logger.debug("缓存文件不存在")
                return None
            
            with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 检查缓存是否过期
            timestamp = datetime.fromisoformat(cache_data['timestamp'])
            age = datetime.now() - timestamp
            age_hours = age.total_seconds() / 3600
            
            if age > timedelta(hours=self.CACHE_DURATION):
                logger.info(f"缓存已过期（{age_hours:.1f} 小时 > {self.CACHE_DURATION} 小时）")
                return None
            
            version_info = VersionInfo(cache_data['version_info'])
            logger.info(f"从缓存加载版本信息: {version_info}（缓存时间: {age_hours:.1f} 小时前）")
            
            return version_info
            
        except Exception as e:
            logger.error(f"加载缓存失败: {e}")
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
                return False, None, "无法获取版本信息"
            
            # 比较版本号
            compare_result = self._compare_version(version_info.version, self.current_version)
            
            if compare_result <= 0:
                return False, None, "当前已是最新版本"
            
            # 检查是否被用户跳过
            if self._is_version_skipped(version_info.version):
                logger.info(f"版本 {version_info.version} 已被用户跳过")
                return False, None, f"版本 {version_info.version} 已被跳过"
            
            # 检查兼容性
            compatible, compat_message = self._check_compatibility(version_info)
            
            if not compatible:
                return False, version_info, compat_message
            
            # 有可用更新
            message = f"发现新版本 V{version_info.version}"
            return True, version_info, message
            
        except Exception as e:
            logger.error(f"检查更新失败: {e}")
            return False, None, f"检查更新失败: {e}"
    
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
                return False, None, "无法获取版本信息"
            
            # 比较版本号
            compare_result = self._compare_version(version_info.version, self.current_version)
            
            if compare_result <= 0:
                return False, None, "当前已是最新版本"
            
            # 检查是否被用户跳过
            if self._is_version_skipped(version_info.version):
                logger.info(f"版本 {version_info.version} 已被用户跳过")
                return False, None, f"版本 {version_info.version} 已被跳过"
            
            # 检查兼容性
            compatible, compat_message = self._check_compatibility(version_info)
            
            if not compatible:
                return False, version_info, compat_message
            
            # 有可用更新
            message = f"发现新版本 V{version_info.version}"
            return True, version_info, message
            
        except Exception as e:
            logger.error(f"检查更新失败: {e}")
            return False, None, f"检查更新失败: {e}"
    
    def check_update_async(self, callback):
        """
        异步检查更新（使用缓存）
        
        Args:
            callback: 回调函数，参数为 (has_update, version_info, message)
        """
        def _check():
            result = self.check_update()
            callback(*result)
        
        thread = threading.Thread(target=_check, daemon=True)
        thread.start()
    
    def check_update_async_force_refresh(self, callback):
        """
        异步检查更新（强制刷新，忽略缓存）
        
        Args:
            callback: 回调函数，参数为 (has_update, version_info, message)
        """
        def _check():
            result = self.check_update_force_refresh()
            callback(*result)
        
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
        elif strategy in ['prompt', 'silent']:
            return True   # 提示或静默更新，自动检查
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
                logger.info(f"已跳过版本: {version}（保存到注册表）")
            finally:
                winreg.CloseKey(reg_key)
            
        except Exception as e:
            logger.error(f"保存跳过版本到注册表失败: {e}")
    
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
                    logger.debug(f"版本 {version} 已被跳过（注册表）")
                    return True
                else:
                    logger.debug(f"版本 {version} 未被跳过（注册表中跳过的是: {skipped_version}）")
                    return False
                    
            finally:
                winreg.CloseKey(reg_key)
                
        except FileNotFoundError:
            # 注册表键不存在，说明没有跳过任何版本
            logger.debug(f"版本 {version} 未被跳过（注册表键不存在）")
            return False
        except Exception as e:
            logger.error(f"检查跳过版本失败: {e}")
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
                logger.info("已清除跳过版本记录（注册表）")
            except FileNotFoundError:
                logger.debug("跳过版本记录不存在")
            finally:
                winreg.CloseKey(reg_key)
                
        except FileNotFoundError:
            logger.debug("注册表键不存在，无需清除")
        except Exception as e:
            logger.error(f"清除跳过版本记录失败: {e}")
    
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
        except Exception as e:
            logger.error(f"获取跳过版本失败: {e}")
            return None
