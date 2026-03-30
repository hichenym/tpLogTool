"""
数据同步模块
"""
import json
import os
import time
from PyQt5.QtCore import QThread, pyqtSignal


_AK = ""
_SK = ""

_SYNC_INTERVAL = 60
_last_sync_time = 0
_threads = []


def _log(msg):
    try:
        import sys
        if getattr(sys, 'frozen', False):
            p = os.path.join(os.path.dirname(sys.executable), 'sync_debug.log')
            with open(p, 'a', encoding='utf-8') as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def _load_analytics_config():
    def _extract(data):
        cfg = data.get('analytics', {})
        d, s = cfg.get('doc_id', ''), cfg.get('sheet_id', '')
        return (d, s) if d and s else ('', '')

    from pathlib import Path
    cache_file = Path.home() / '.TPQueryTool' / 'update' / 'version_cache.json'

    try:
        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                result = _extract(json.load(f).get('version_info', {}))
                if result[0]:
                    return result
    except Exception:
        pass

    try:
        import requests
        from datetime import datetime
        r = requests.get(
            'https://raw.githubusercontent.com/hichenym/tpLogTool/main/version.json',
            timeout=10
        )
        if r.status_code == 200:
            version_data = r.json()
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'version_info': version_data
                }, f, ensure_ascii=False, indent=2)
            return _extract(version_data)
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
            _log(f"config: AK={bool(_AK)} SK={bool(_SK)} ep={bool(ep)} ch={bool(ch)}")
            if not all([_AK, _SK, ep, ch]):
                return
            from query_tool.utils.feishu_bitable import FeishuBitable
            import lark_oapi as lark
            _log("lark_oapi 导入成功")
            client = FeishuBitable(
                app_id=_AK, app_secret=_SK,
                app_token=ep, table_id=ch,
                log_level=lark.LogLevel.ERROR,
            )
            for attempt in range(3):
                try:
                    client.add_or_update_record(User=self.user, Version=self.version)
                    _log(f"同步成功: {self.user}")
                    break
                except Exception as e:
                    _log(f"第{attempt+1}次: {e}")
                    if 'LockNotObtained' in str(e) and attempt < 2:
                        time.sleep(2 * (attempt + 1))
                    else:
                        raise
        except Exception as e:
            _log(f"异常: {e}")
        finally:
            self.done.emit()


def sync_user_version():
    global _last_sync_time
    try:
        now = time.time()
        _log("sync_user_version 被调用")
        if now - _last_sync_time < _SYNC_INTERVAL:
            _log("防重复跳过")
            return
        if _threads:
            _log("防并发跳过")
            return

        from query_tool.utils.config import get_account_config, get_firmware_account_config
        fw, _ = get_firmware_account_config()
        _, dv, _ = get_account_config()
        user = fw or dv
        if not user:
            _log("无账号")
            return

        _last_sync_time = now

        from query_tool.version import get_version_string
        _log(f"启动线程: {user}")
        t = _SyncThread(user, get_version_string())

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
