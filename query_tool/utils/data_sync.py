"""
数据同步模块
"""
import json
import os
import time
from PyQt5.QtCore import QThread, pyqtSignal


_AK = ""
_SK = ""

# 防重复上报间隔（秒）
_SYNC_INTERVAL = 60

_last_sync_time = 0
_threads = []


def _load_analytics_config():
    """
    读取 analytics 配置：
    1. 本地 version.json（开发环境）
    2. UpdateChecker 缓存文件（与更新检测共享，6 小时刷新）
    3. 远程拉取（兜底）
    """
    def _extract(data):
        cfg = data.get('analytics', {})
        d, s = cfg.get('doc_id', ''), cfg.get('sheet_id', '')
        return (d, s) if d and s else ('', '')

    # 1. 本地 version.json
    try:
        import sys
        if getattr(sys, 'frozen', False):
            root = os.path.dirname(sys.executable)
        else:
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        local_path = os.path.join(root, 'version.json')
        if os.path.exists(local_path):
            with open(local_path, 'r', encoding='utf-8') as f:
                result = _extract(json.load(f))
                if result[0]:
                    return result
    except Exception:
        pass

    # 2. UpdateChecker 缓存文件
    try:
        from pathlib import Path
        cache_file = Path.home() / '.TPQueryTool' / 'update' / 'version_cache.json'
        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            result = _extract(cache_data.get('version_info', {}))
            if result[0]:
                return result
    except Exception:
        pass

    # 3. 远程拉取（兜底）
    try:
        import requests
        r = requests.get(
            'https://raw.githubusercontent.com/hichenym/tpLogTool/main/version.json',
            timeout=5
        )
        if r.status_code == 200:
            return _extract(r.json())
    except Exception:
        pass

    return '', ''


class _SyncThread(QThread):
    done = pyqtSignal()

    def __init__(self, user, version):
        super().__init__()
        self.user = user
        self.version = version

    def run(self):
        try:
            ep, ch = _load_analytics_config()
            if not all([_AK, _SK, ep, ch]):
                return
            from query_tool.utils.feishu_bitable import FeishuBitable
            import lark_oapi as lark
            client = FeishuBitable(
                app_id=_AK,
                app_secret=_SK,
                app_token=ep,
                table_id=ch,
                log_level=lark.LogLevel.ERROR,
            )
            for attempt in range(3):
                try:
                    client.add_or_update_record(User=self.user, Version=self.version)
                    break
                except Exception as e:
                    if 'LockNotObtained' in str(e) and attempt < 2:
                        time.sleep(2 * (attempt + 1))
                    else:
                        raise
        except Exception:
            pass
        finally:
            self.done.emit()


def sync_user_version():
    global _last_sync_time
    try:
        now = time.time()
        if now - _last_sync_time < _SYNC_INTERVAL:
            return
        if _threads:
            return

        from query_tool.utils.config import get_account_config, get_firmware_account_config
        fw, _ = get_firmware_account_config()
        _, dv, _ = get_account_config()
        user = fw or dv
        if not user:
            return

        _last_sync_time = now

        from query_tool.version import get_version_string
        ver = get_version_string()
        t = _SyncThread(user, ver)

        def _cleanup():
            try:
                _threads.remove(t)
            except ValueError:
                pass
            t.deleteLater()

        t.done.connect(_cleanup)
        _threads.append(t)
        t.start()
    except Exception:
        pass
