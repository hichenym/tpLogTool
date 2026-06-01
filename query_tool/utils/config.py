"""
配置管理器
统一管理应用程序配置（注册表）
"""
import winreg
import base64
import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import List

# 注册表路径
REGISTRY_PATH = r"Software\TPQueryTool"


@dataclass
class AccountConfig:
    """账号配置"""
    env: str = 'pro'
    username: str = ''
    password: str = ''


@dataclass
class FirmwareAccountConfig:
    """固件账号配置"""
    username: str = ''
    password: str = ''


@dataclass
class SeetongAccountConfig:
    """Seetong 账号配置"""
    username: str = ''
    password: str = ''


@dataclass
class AppConfig:
    """应用配置"""
    export_path: str = ''
    phone_history: List[str] = field(default_factory=list)
    debug_shortcuts: List[str] = field(default_factory=list)
    debug_shortcuts_initialized: bool = False
    last_debug_sn: str = ''
    debug_download_path: str = ''
    last_log_sn: str = ''
    log_download_path: str = ''
    log_commands: List[str] = field(default_factory=list)
    last_page_index: int = 0
    theme: str = 'dark'  # 'dark' 或 'light'
    tray_minimize_tip_shown: bool = False


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, registry_path=REGISTRY_PATH):
        self.registry_path = registry_path

    @staticmethod
    def _build_scoped_key(prefix, *parts):
        joined = "|".join(str(part or "") for part in parts)
        digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()
        return f"{prefix}_{digest}"
    
    def _get_value(self, key, default=None):
        """从注册表读取值"""
        reg_key = None
        try:
            reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.registry_path, 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(reg_key, key)
            return value
        except (WindowsError, FileNotFoundError, OSError):
            return default
        finally:
            if reg_key:
                try:
                    winreg.CloseKey(reg_key)
                except Exception as e:
                    from query_tool.utils.logger import logger
                    logger.debug(f"关闭注册表键失败: {e}")
    
    def _set_value(self, key, value, value_type=winreg.REG_SZ):
        """写入值到注册表"""
        reg_key = None
        try:
            reg_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.registry_path)
            winreg.SetValueEx(reg_key, key, 0, value_type, value)
            return True
        except (WindowsError, OSError) as e:
            from query_tool.utils.logger import logger
            logger.error(f"注册表写入失败: {e}")
            return False
        finally:
            if reg_key:
                try:
                    winreg.CloseKey(reg_key)
                except Exception as e:
                    from query_tool.utils.logger import logger
                    logger.debug(f"关闭注册表键失败: {e}")
    
    def load_account_config(self) -> AccountConfig:
        """加载账号配置"""
        from query_tool.utils.logger import logger
        
        logger.debug("加载运维账号配置")
        env = self._get_value('account_env', 'pro')
        username = self._get_value('account_username', '')
        password_encoded = self._get_value('account_password', '')
        
        password = ''
        if password_encoded:
            try:
                password = base64.b64decode(password_encoded.encode()).decode()
            except (ValueError, UnicodeDecodeError) as e:
                logger.error(f"密码解码失败: {e}")
                print(f"密码解码失败: {e}")
        
        if username:
            logger.info(f"运维账号配置已加载: {username}@{env}")
        else:
            logger.debug("运维账号未配置")
        
        return AccountConfig(env=env, username=username, password=password)
    
    def save_account_config(self, config: AccountConfig) -> bool:
        """保存账号配置"""
        from query_tool.utils.logger import logger
        
        logger.debug(f"保存运维账号配置: {config.username}@{config.env}")
        try:
            self._set_value('account_env', config.env)
            self._set_value('account_username', config.username)
            password_encoded = base64.b64encode(config.password.encode()).decode()
            self._set_value('account_password', password_encoded)
            logger.info(f"运维账号配置已保存: {config.username}@{config.env}")
            return True
        except Exception as e:
            logger.error(f"保存运维账号配置失败: {e}")
            print(f"保存配置失败: {e}")
            return False
    
    def load_firmware_account_config(self) -> FirmwareAccountConfig:
        """加载固件账号配置"""
        from query_tool.utils.logger import logger
        
        logger.debug("加载固件账号配置")
        username = self._get_value('firmware_username', '')
        password_encoded = self._get_value('firmware_password', '')
        
        password = ''
        if password_encoded:
            try:
                password = base64.b64decode(password_encoded.encode()).decode()
            except (ValueError, UnicodeDecodeError) as e:
                logger.error(f"固件密码解码失败: {e}")
                print(f"密码解码失败: {e}")
        
        if username:
            logger.info(f"固件账号配置已加载: {username}")
        else:
            logger.debug("固件账号未配置")
        
        return FirmwareAccountConfig(username=username, password=password)
    
    def save_firmware_account_config(self, config: FirmwareAccountConfig) -> bool:
        """保存固件账号配置"""
        from query_tool.utils.logger import logger
        
        logger.debug(f"保存固件账号配置: {config.username}")
        try:
            self._set_value('firmware_username', config.username)
            password_encoded = base64.b64encode(config.password.encode()).decode()
            self._set_value('firmware_password', password_encoded)
            logger.info(f"固件账号配置已保存: {config.username}")
            return True
        except Exception as e:
            logger.error(f"保存固件账号配置失败: {e}")
            print(f"保存固件配置失败: {e}")
            return False

    def load_firmware_file_dialog_dir(self) -> str:
        """加载固件文件选择框的起始目录。"""
        directory = str(self._get_value('firmware_file_dialog_dir', '') or '').strip()
        if directory and os.path.isdir(directory):
            return directory
        return ''

    def save_firmware_file_dialog_dir(self, directory: str) -> bool:
        """保存固件文件选择框的起始目录。"""
        normalized_dir = os.path.abspath(str(directory or '').strip())
        if not normalized_dir or not os.path.isdir(normalized_dir):
            return False
        return self._set_value('firmware_file_dialog_dir', normalized_dir)

    def load_seetong_account_config(self) -> SeetongAccountConfig:
        """加载 Seetong 账号配置"""
        from query_tool.utils.logger import logger

        logger.debug("加载 Seetong 账号配置")
        username = self._get_value('seetong_username', '')
        password_encoded = self._get_value('seetong_password', '')

        password = ''
        if password_encoded:
            try:
                password = base64.b64decode(password_encoded.encode()).decode()
            except (ValueError, UnicodeDecodeError) as e:
                logger.error(f"Seetong 密码解码失败: {e}")
                print(f"密码解码失败: {e}")

        if username:
            logger.info(f"Seetong 账号配置已加载: {username}")
        else:
            logger.debug("Seetong 账号未配置")

        return SeetongAccountConfig(username=username, password=password)

    def save_seetong_account_config(self, config: SeetongAccountConfig) -> bool:
        """保存 Seetong 账号配置"""
        from query_tool.utils.logger import logger

        logger.debug(f"保存 Seetong 账号配置: {config.username}")
        try:
            self._set_value('seetong_username', config.username)
            password_encoded = base64.b64encode(config.password.encode()).decode()
            self._set_value('seetong_password', password_encoded)
            logger.info(f"Seetong 账号配置已保存: {config.username}")
            return True
        except Exception as e:
            logger.error(f"保存 Seetong 账号配置失败: {e}")
            print(f"保存 Seetong 配置失败: {e}")
            return False
    
    def load_app_config(self) -> AppConfig:
        """加载应用配置"""
        export_path = self._get_value('export_path', '')
        phone_history_str = self._get_value('phone_history', '')
        phone_history = phone_history_str.split('|')[:5] if phone_history_str else []
        debug_shortcuts_str = self._get_value('debug_shortcuts', '')
        debug_shortcuts = self._decode_string_list(debug_shortcuts_str)
        debug_shortcuts_initialized = self._get_value('debug_shortcuts_initialized', '0') == '1'
        last_debug_sn = self._get_value('last_debug_sn', '')
        debug_download_path = self._get_value('debug_download_path', '')
        last_log_sn = self._get_value('last_log_sn', '')
        log_download_path = self._get_value('log_download_path', '')
        log_commands_str = self._get_value('log_commands', '')
        log_commands = [item for item in log_commands_str.split('|') if item] if log_commands_str else []
        last_page_index = int(self._get_value('last_page_index', '0'))
        theme = self._get_value('theme', 'dark')
        tray_minimize_tip_shown = self._get_value('tray_minimize_tip_shown', '0') == '1'
        
        return AppConfig(
            export_path=export_path,
            phone_history=phone_history,
            debug_shortcuts=debug_shortcuts,
            debug_shortcuts_initialized=debug_shortcuts_initialized,
            last_debug_sn=last_debug_sn,
            debug_download_path=debug_download_path,
            last_log_sn=last_log_sn,
            log_download_path=log_download_path,
            log_commands=log_commands,
            last_page_index=last_page_index,
            theme=theme,
            tray_minimize_tip_shown=tray_minimize_tip_shown
        )
    
    def save_app_config(self, config: AppConfig) -> bool:
        """保存应用配置"""
        try:
            self._set_value('export_path', config.export_path)
            phone_history_str = '|'.join(config.phone_history[:5])
            self._set_value('phone_history', phone_history_str)
            debug_shortcuts_str = json.dumps(config.debug_shortcuts[:50], ensure_ascii=False)
            self._set_value('debug_shortcuts', debug_shortcuts_str)
            self._set_value('debug_shortcuts_initialized', '1' if config.debug_shortcuts_initialized else '0')
            self._set_value('last_debug_sn', config.last_debug_sn)
            self._set_value('debug_download_path', config.debug_download_path)
            self._set_value('last_log_sn', config.last_log_sn)
            self._set_value('log_download_path', config.log_download_path)
            log_commands_str = '|'.join(config.log_commands[:50])
            self._set_value('log_commands', log_commands_str)
            self._set_value('last_page_index', str(config.last_page_index))
            self._set_value('theme', config.theme)
            self._set_value('tray_minimize_tip_shown', '1' if config.tray_minimize_tip_shown else '0')
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False
    
    def save_token_cache(self, env, username, token, refresh_token):
        """保存token缓存"""
        import time
        try:
            scoped_key = self._build_scoped_key("device_token", env, username)
            self._set_value(f"{scoped_key}_token", token)
            self._set_value(f"{scoped_key}_refresh_token", refresh_token)
            self._set_value(f"{scoped_key}_timestamp", str(time.time()))
            self._set_value('env', env)
            self._set_value('username', username)
            self._set_value('token', token)
            self._set_value('refresh_token', refresh_token)
            self._set_value('timestamp', str(time.time()))
            return True
        except Exception as e:
            from query_tool.utils.logger import logger
            logger.error(f"保存Token缓存失败: {e}")
            print(f"保存token缓存失败: {e}")
            return False
    
    def load_token_cache(self, env, username):
        """加载token缓存"""
        import time
        
        reg_key = None
        try:
            reg_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.registry_path,
                0,
                winreg.KEY_READ
            )
            
            scoped_key = self._build_scoped_key("device_token", env, username)
            token = self._get_value(f"{scoped_key}_token")
            refresh_token = self._get_value(f"{scoped_key}_refresh_token")
            timestamp = self._get_value(f"{scoped_key}_timestamp")

            if token and timestamp and time.time() - float(timestamp) < 7200:
                return token, refresh_token

            cached_env = self._get_value('env')
            cached_username = self._get_value('username')
            token = self._get_value('token')
            refresh_token = self._get_value('refresh_token')
            timestamp = self._get_value('timestamp')

            if cached_env == env and cached_username == username:
                if timestamp and time.time() - float(timestamp) < 7200:
                    return token, refresh_token
        except (ValueError, TypeError) as e:
            from query_tool.utils.logger import logger
            logger.debug(f"加载Token缓存失败: {e}")
        finally:
            if reg_key:
                try:
                    winreg.CloseKey(reg_key)
                except Exception as e:
                    from query_tool.utils.logger import logger
                    logger.debug(f"关闭注册表键失败: {e}")
        return None, None

    @staticmethod
    def _decode_string_list(raw_value):
        """兼容读取 JSON 数组和旧版竖线分隔列表。"""
        if not raw_value:
            return []
        text = str(raw_value).strip()
        if not text:
            return []
        try:
            payload = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, list):
            return [str(item) for item in payload if str(item).strip()]
        return [item for item in text.split('|') if item]

    def save_seetong_cloud_cache(self, username, password, payload):
        """保存 Seetong 云登录缓存。"""
        import time
        try:
            scoped_key = self._build_scoped_key(
                "seetong_cloud",
                username,
                hashlib.sha256((password or "").encode("utf-8")).hexdigest(),
            )
            payload_text = json.dumps(payload or {}, ensure_ascii=False)
            payload_encoded = base64.b64encode(payload_text.encode("utf-8")).decode("ascii")
            self._set_value(f"{scoped_key}_payload", payload_encoded)
            self._set_value(f"{scoped_key}_timestamp", str(time.time()))
            return True
        except Exception as e:
            from query_tool.utils.logger import logger
            logger.error(f"保存 Seetong 云缓存失败: {e}")
            return False

    def load_seetong_cloud_cache(self, username, password, max_age_seconds):
        """加载 Seetong 云登录缓存。"""
        import time

        try:
            scoped_key = self._build_scoped_key(
                "seetong_cloud",
                username,
                hashlib.sha256((password or "").encode("utf-8")).hexdigest(),
            )
            payload_encoded = self._get_value(f"{scoped_key}_payload")
            timestamp = self._get_value(f"{scoped_key}_timestamp")
            if not payload_encoded or not timestamp:
                return None
            if time.time() - float(timestamp) >= float(max_age_seconds):
                return None
            payload_text = base64.b64decode(payload_encoded.encode("ascii")).decode("utf-8")
            payload = json.loads(payload_text)
            if isinstance(payload, dict):
                return payload
        except Exception as e:
            from query_tool.utils.logger import logger
            logger.debug(f"加载 Seetong 云缓存失败: {e}")
        return None

    def clear_seetong_cloud_cache(self, username, password):
        """清理 Seetong 云登录缓存。"""
        reg_key = None
        try:
            scoped_key = self._build_scoped_key(
                "seetong_cloud",
                username,
                hashlib.sha256((password or "").encode("utf-8")).hexdigest(),
            )
            reg_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.registry_path,
                0,
                winreg.KEY_WRITE
            )
            for suffix in ("payload", "timestamp"):
                try:
                    winreg.DeleteValue(reg_key, f"{scoped_key}_{suffix}")
                except FileNotFoundError:
                    pass
            return True
        except Exception as e:
            from query_tool.utils.logger import logger
            logger.debug(f"清理 Seetong 云缓存失败: {e}")
            return False
        finally:
            if reg_key:
                try:
                    winreg.CloseKey(reg_key)
                except Exception:
                    pass


# 全局配置管理器实例
config_manager = ConfigManager()


# 向后兼容的函数
def get_account_config():
    """获取账号配置（向后兼容）"""
    config = config_manager.load_account_config()
    return config.env, config.username, config.password


def save_account_config(env, username, password):
    """保存账号配置（向后兼容）"""
    config = AccountConfig(env=env, username=username, password=password)
    return config_manager.save_account_config(config)


def get_firmware_account_config():
    """获取固件账号配置"""
    config = config_manager.load_firmware_account_config()
    return config.username, config.password


def save_firmware_account_config(username, password):
    """保存固件账号配置"""
    config = FirmwareAccountConfig(username=username, password=password)
    return config_manager.save_firmware_account_config(config)


def get_firmware_file_dialog_dir():
    """获取固件文件选择框起始目录。"""
    return config_manager.load_firmware_file_dialog_dir()


def save_firmware_file_dialog_dir(directory):
    """保存固件文件选择框起始目录。"""
    return config_manager.save_firmware_file_dialog_dir(directory)


def get_seetong_account_config():
    """获取 Seetong 账号配置"""
    config = config_manager.load_seetong_account_config()
    return config.username, config.password


def save_seetong_account_config(username, password):
    """保存 Seetong 账号配置"""
    config = SeetongAccountConfig(username=username, password=password)
    return config_manager.save_seetong_account_config(config)


def get_registry_value(key_name, value_name, default=None):
    """从注册表读取值（向后兼容）"""
    return config_manager._get_value(value_name, default)


def set_registry_value(key_name, value_name, value, value_type=winreg.REG_SZ):
    """写入值到注册表（向后兼容）"""
    return config_manager._set_value(value_name, value, value_type)



def get_log_config():
    """获取日志配置
    
    Returns:
        bool: 是否启用文件日志
    """
    try:
        value = config_manager._get_value('enable_file_log', '0')
        return value == '1'
    except Exception:
        return False


def save_log_config(enable_file_log):
    """保存日志配置
    
    Args:
        enable_file_log: 是否启用文件日志
    
    Returns:
        bool: 是否保存成功
    """
    try:
        value = '1' if enable_file_log else '0'
        return config_manager._set_value('enable_file_log', value)
    except Exception as e:
        from query_tool.utils.logger import logger
        logger.error(f"保存日志配置失败: {e}")
        return False
