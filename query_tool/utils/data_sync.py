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
    1. UpdateChecker 缓存文件
    2. 缓存不存在则远程拉取并写入缓存
    """
    def _extract(data):
        cfg = data.get('analytics', {})
        d, s = cfg.get('doc_id', ''), cfg.get('sheet_id', '')
        return (d, s) if d and s else ('', '')

    from pathlib import Path
    cache_file = Path.home() / '.TPQueryTool' / 'update' / 'version_cache.json'

    # 1. 读缓存
    try:
        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            result = _extract(cache_data.get('version_info', {}))
            if result[0]:
                return result
    except Exception:
        pass

    # 2. 缓存没有则远程拉取并写入缓存
    try:
        import requests
        from datetime import datetime
        r = requests.get(
            'https://raw.githubusercontent.com/hichenym/tpLogTool/main/version.json',
            timeout=10
        )
        if r.status_code == 200:
            version_data = r.json()
            # 写入缓存（与 UpdateChecker 格式一致）
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
            if not all([_AK, _SK, ep, ch]):
                self._log(f"配置不完整: AK={bool(_AK)} SK={bool(_SK)} ep={bool(ep)} ch={bool(ch)}")
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
                    self._log(f"同步成功: User={self.user}, Version={self.version}")
                    break
                except Exception as e:
                    self._log(f"第{attempt+1}次失败: {e}")
                    if 'LockNotObtained' in str(e) and attempt < 2:
                        time.sleep(2 * (attempt + 1))
                    else:
                        raise
        except Exception as e:
            self._log(f"最终异常: {e}")
        finally:
            self.done.emit()

    @staticmethod
    def _log(msg):
        _debug_log(msg)


def _debug_log(msg):
    """调试日志：开发环境 print，打包环境写文件"""
    try:
        import sys
        print(f"[DataSync] {msg}")
        if getattr(sys, 'frozen', False):
            log_path = os.path.join(os.path.dirname(sys.executable), 'sync_debug.log')
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def sync_user_version():
    global _last_sync_time
    try:
        now = time.time()
        if now - _last_sync_time < _SYNC_INTERVAL:
            _debug_log(f"防重复跳过: {now - _last_sync_time:.0f}s < {_SYNC_INTERVAL}s")
            return
        if _threads:
            _debug_log(f"防并发跳过: {len(_threads)} 个线程运行中")
            return

        from query_tool.utils.config import get_account_config, get_firmware_account_config
        fw, _ = get_firmware_account_config()
        _, dv, _ = get_account_config()
        user = fw or dv
        if not user:
            _debug_log("无账号配置，跳过")
            return

        _last_sync_time = now

        from query_tool.version import get_version_string
        ver = get_version_string()
        _debug_log(f"启动同步: User={user}, Version={ver}")
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
