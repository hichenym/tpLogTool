from __future__ import annotations

import json

from .device_query import DeviceQuery, ensure_device_online_for_upgrade
from .logger import logger
from .session_manager import SessionManager


def query_device_version(device_query: DeviceQuery, dev_id: str) -> str:
    """Query the current firmware version of a device."""
    try:
        return (device_query.get_device_version(dev_id) or "").strip()
    except Exception as exc:
        logger.warning(f"查询设备版本失败 {dev_id}: {exc}")
        return ""


def send_upgrade_command(
    sn: str,
    device_identify: str,
    file_url: str,
    device_query: DeviceQuery | None = None,
    token: str | None = None,
    host: str | None = None,
    timeout: int = 10,
) -> tuple[str, str]:
    """Send the existing upgrade command and return (status, message)."""
    current_token = token or (device_query.token if device_query else None)
    current_host = host or (device_query.host if device_query else "console.seetong.com")

    if not current_token:
        return "failed", "缺少访问令牌"

    session = SessionManager().get_session()
    url = f"https://{current_host}/api/seetong-siot-device/console/device/operate/sendCommand"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
        "Seetong-Auth": current_token,
    }
    params_dict = {
        "device_identify": device_identify,
        "file_url": file_url,
    }
    payload = {
        "moduleCode": "default",
        "code": "upgrade",
        "params": json.dumps(params_dict),
        "sn": sn,
        "sourceType": "1",
    }

    response = session.post(url, json=payload, headers=headers, verify=False, timeout=timeout)
    if response.status_code != 200:
        return "failed", f"HTTP {response.status_code}"

    result = response.json()
    if result.get("code") == 200 and result.get("success"):
        return "success", "升级命令已发送"
    if result.get("code") == 20001:
        return "offline", "设备不在线，操作失败"
    return "failed", result.get("msg", "操作失败")


def prepare_and_send_upgrade(
    sn: str,
    dev_id: str,
    device_identify: str,
    file_url: str,
    device_query: DeviceQuery | None = None,
    token: str | None = None,
    host: str | None = None,
    max_wake_times: int = 3,
    timeout: int = 10,
) -> tuple[str, str]:
    """Ensure device is online first, then send the upgrade command."""
    auth_context = device_query if device_query is not None else token
    current_host = host or (device_query.host if device_query else "console.seetong.com")
    can_upgrade, status, message = ensure_device_online_for_upgrade(
        dev_id,
        sn,
        auth_context,
        current_host,
        max_wake_times=max_wake_times,
    )
    if not can_upgrade:
        return status, message

    try:
        current_token = device_query.token if device_query is not None else token
        return send_upgrade_command(
            sn,
            device_identify,
            file_url,
            device_query=device_query,
            token=current_token,
            host=current_host,
            timeout=timeout,
        )
    except Exception as exc:
        logger.error(f"升级设备 {sn} 出错: {exc}")
        return "failed", str(exc)

