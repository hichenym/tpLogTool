from __future__ import annotations

import threading
import time
from dataclasses import asdict
from typing import TYPE_CHECKING, Dict, Optional

from query_tool.utils.config import config_manager

if TYPE_CHECKING:
    from query_tool.utils.device_query import DeviceQuery
    from query_tool.utils.siot_debug.models import CloudCredentials


DEVICE_QUERY_TTL_S = 90 * 60
SEETONG_CLOUD_CACHE_TTL_S = 60 * 60

_cache_lock = threading.RLock()
_device_query_cache: Dict[str, dict] = {}
_cloud_credentials_cache: Dict[str, dict] = {}


def _account_key(env: str, username: str, password: str) -> str:
    return config_manager._build_scoped_key("runtime_account", env, username, password)


def _cloud_key(username: str, password: str) -> str:
    return config_manager._build_scoped_key("runtime_cloud", username, password)


def get_shared_device_query(
    env: str,
    username: str,
    password: str,
    *,
    ttl_seconds: float = DEVICE_QUERY_TTL_S,
) -> DeviceQuery:
    """获取进程内共享的 DeviceQuery，避免各页面重复登录。"""
    from query_tool.utils.device_query import DeviceQuery

    key = _account_key(env, username, password)
    now = time.time()

    with _cache_lock:
        entry = _device_query_cache.get(key)
        if (
            entry
            and (now - entry["created_at"]) < ttl_seconds
            and not getattr(entry["query"], "init_error", None)
        ):
            return entry["query"]

    query = DeviceQuery(env, username, password)
    with _cache_lock:
        _device_query_cache[key] = {
            "query": query,
            "created_at": now,
        }
    return query


def load_cached_cloud_credentials(
    username: str,
    password: str,
    *,
    ttl_seconds: float = SEETONG_CLOUD_CACHE_TTL_S,
) -> Optional["CloudCredentials"]:
    """优先从进程内，其次从注册表加载 Seetong 云凭证缓存。"""
    key = _cloud_key(username, password)
    now = time.time()

    with _cache_lock:
        entry = _cloud_credentials_cache.get(key)
        if entry and (now - entry["created_at"]) < ttl_seconds:
            return entry["credentials"]

    payload = config_manager.load_seetong_cloud_cache(username, password, ttl_seconds)
    if not payload:
        return None

    try:
        from query_tool.utils.siot_debug.models import CloudCredentials

        credentials = CloudCredentials(**payload)
    except Exception as exc:
        config_manager.clear_seetong_cloud_cache(username, password)
        return None

    with _cache_lock:
        _cloud_credentials_cache[key] = {
            "credentials": credentials,
            "created_at": now,
        }
    return credentials


def save_cached_cloud_credentials(username: str, password: str, credentials: "CloudCredentials") -> None:
    """保存 Seetong 云凭证到进程内和注册表。"""
    key = _cloud_key(username, password)
    now = time.time()
    with _cache_lock:
        _cloud_credentials_cache[key] = {
            "credentials": credentials,
            "created_at": now,
        }
    config_manager.save_seetong_cloud_cache(username, password, asdict(credentials))


def invalidate_cached_cloud_credentials(username: str, password: str) -> None:
    """清理 Seetong 云凭证缓存。"""
    key = _cloud_key(username, password)
    with _cache_lock:
        _cloud_credentials_cache.pop(key, None)
    config_manager.clear_seetong_cloud_cache(username, password)
