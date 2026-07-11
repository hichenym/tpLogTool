"""
数据同步模块
"""

import json
import time
from typing import Dict, Optional

from PyQt5.QtCore import QThread, pyqtSignal


_AK = ""
_SK = ""

_SYNC_INTERVAL = 60
_MATCH_FIELDS = ("User", "Seetong", "Update")
_last_sync_time = 0.0
_threads = []
_pending_sync_request = None


def _normalize_sync_value(value) -> str:
    return str(value or "").strip()


def _load_analytics_config():
    def _extract(data):
        cfg = data.get("analytics", {})
        doc_id, sheet_id = cfg.get("doc_id", ""), cfg.get("sheet_id", "")
        return (doc_id, sheet_id) if doc_id and sheet_id else ("", "")

    from pathlib import Path

    cache_file = Path.home() / ".TPQueryTool" / "update" / "version_cache.json"

    try:
        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                result = _extract(json.load(f).get("version_info", {}))
                if result[0]:
                    return result
    except Exception:
        pass

    try:
        import requests
        from datetime import datetime

        response = requests.get(
            "https://raw.githubusercontent.com/hichenym/tpLogTool/main/version.json",
            timeout=10,
        )
        if response.status_code == 200:
            version_data = response.json()
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "version_info": version_data,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            return _extract(version_data)
    except Exception:
        pass

    return "", ""


def _load_account_snapshot() -> Dict[str, str]:
    from query_tool.utils.config import (
        get_account_config,
        get_firmware_account_config,
        get_seetong_account_config,
    )

    seetong_username, seetong_password = get_seetong_account_config()
    firmware_username, firmware_password = get_firmware_account_config()
    env, device_username, device_password = get_account_config()
    return {
        "env": _normalize_sync_value(env),
        "device_username": _normalize_sync_value(device_username),
        "device_password": _normalize_sync_value(device_password),
        "seetong_username": _normalize_sync_value(seetong_username),
        "seetong_password": _normalize_sync_value(seetong_password),
        "firmware_username": _normalize_sync_value(firmware_username),
        "firmware_password": _normalize_sync_value(firmware_password),
    }


def _build_sync_fields(account_snapshot: Optional[Dict[str, str]] = None, version: str = "") -> Dict[str, str]:
    snapshot = dict(account_snapshot or _load_account_snapshot())

    if not version:
        from query_tool.version import get_version_string

        version = get_version_string()

    return {
        "User": _normalize_sync_value(snapshot.get("device_username")),
        "Seetong": _normalize_sync_value(snapshot.get("seetong_username")),
        "Update": _normalize_sync_value(snapshot.get("firmware_username")),
        "Version": _normalize_sync_value(version),
    }


def _has_syncable_account(fields: Dict[str, str]) -> bool:
    return any(_normalize_sync_value(fields.get(field)) for field in _MATCH_FIELDS)


def _build_sync_request(account_snapshot: Optional[Dict[str, str]] = None, version: str = "", force: bool = False):
    fields = _build_sync_fields(account_snapshot=account_snapshot, version=version)
    return {
        "fields": fields,
        "force": bool(force),
    }


class _SyncThread(QThread):
    done = pyqtSignal()

    def __init__(self, fields: Dict[str, str]):
        super().__init__()
        self.fields = dict(fields)

    def run(self):
        try:
            app_token, table_id = _load_analytics_config()
            if not all([_AK, _SK, app_token, table_id]):
                return

            from query_tool.utils.feishu_bitable import FeishuBitable
            import lark_oapi as lark

            client = FeishuBitable(
                app_id=_AK,
                app_secret=_SK,
                app_token=app_token,
                table_id=table_id,
                log_level=lark.LogLevel.ERROR,
            )
            for attempt in range(3):
                try:
                    client.add_or_update_record(match_fields=_MATCH_FIELDS, **self.fields)
                    break
                except Exception as e:
                    if "LockNotObtained" in str(e) and attempt < 2:
                        time.sleep(2 * (attempt + 1))
                    else:
                        raise
        except Exception:
            pass
        finally:
            self.done.emit()


def _start_sync_request(request) -> bool:
    global _last_sync_time

    fields = dict((request or {}).get("fields") or {})
    if not _has_syncable_account(fields):
        return False

    _last_sync_time = time.time()
    thread = _SyncThread(fields)

    def _cleanup():
        global _pending_sync_request

        try:
            _threads.remove(thread)
        except ValueError:
            pass

        next_request = _pending_sync_request
        _pending_sync_request = None

        try:
            thread.deleteLater()
        except Exception:
            pass

        if next_request:
            _start_sync_request(next_request)

    thread.done.connect(_cleanup)
    _threads.append(thread)
    thread.start()
    return True


def sync_user_version(account_snapshot: Optional[Dict[str, str]] = None, version: str = "", force: bool = False):
    global _last_sync_time, _pending_sync_request

    try:
        request = _build_sync_request(account_snapshot=account_snapshot, version=version, force=force)
        if not _has_syncable_account(request["fields"]):
            return

        now = time.time()
        for thread in list(_threads):
            try:
                if not thread.isRunning():
                    _threads.remove(thread)
            except Exception:
                try:
                    _threads.remove(thread)
                except Exception:
                    pass

        if _threads:
            if request["force"]:
                _pending_sync_request = request
            return

        if not request["force"] and now - _last_sync_time < _SYNC_INTERVAL:
            return

        _start_sync_request(request)
    except Exception:
        pass
