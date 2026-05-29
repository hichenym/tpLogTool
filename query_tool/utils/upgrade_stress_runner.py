from __future__ import annotations

import csv
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from .device_query import DeviceQuery
from .logger import logger
from .task_center import (
    append_task_record,
    load_task_config,
    load_task,
    mark_task_completed,
    mark_task_canceled,
    mark_task_failed,
    mark_task_started,
    TASK_STATUS_CANCELED,
    TASK_STATUS_PAUSED,
    update_task,
)
from .upgrade_service import prepare_and_send_upgrade, query_device_version


SUMMARY_KEYS = ("success", "offline", "wake_failed", "failed")


def _normalize(value: str) -> str:
    return (value or "").strip().lower()


def _firmware_matches_version(firmware: dict, current_version: str) -> bool:
    version = _normalize(current_version)
    identifier = _normalize(firmware.get("identifier", ""))
    return bool(version and identifier and (version == identifier or identifier in version or version in identifier))


def _select_target_firmware(mode: str, current_version: str, firmwares: list[dict], cycle_index: int) -> tuple[dict | None, str]:
    if not firmwares:
        return None, "未选择固件"
    if mode == "single":
        return firmwares[0], ""
    if len(firmwares) < 2:
        return None, "互升模式需要选择两个固件"

    first, second = firmwares[0], firmwares[1]
    if _firmware_matches_version(first, current_version):
        return second, ""
    if _firmware_matches_version(second, current_version):
        return first, ""
    return None, "当前版本不属于互升版本集合"


def _build_record(
    task_name: str,
    cycle_index: int,
    device: dict,
    current_version: str,
    target_firmware: dict | None,
    status: str,
    message: str,
) -> dict:
    return {
        "recorded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "task_name": task_name,
        "cycle": cycle_index,
        "device_name": device.get("device_name", ""),
        "model": device.get("model", ""),
        "sn": device.get("sn", ""),
        "dev_id": str(device.get("dev_id", "")),
        "current_version": current_version,
        "target_version": (target_firmware or {}).get("identifier", ""),
        "download_url": (target_firmware or {}).get("download_url", ""),
        "result": status,
        "message": message,
    }


def _write_summary_csv(result_dir: str, records: list[dict]) -> None:
    result_path = Path(result_dir)
    result_path.mkdir(parents=True, exist_ok=True)
    csv_path = result_path / "summary.csv"
    fieldnames = [
        "recorded_at",
        "task_name",
        "cycle",
        "device_name",
        "model",
        "sn",
        "dev_id",
        "current_version",
        "target_version",
        "result",
        "message",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow({key: record.get(key, "") for key in fieldnames})


def _append_result_record(result_dir: str, record: dict) -> None:
    result_path = Path(result_dir)
    result_path.mkdir(parents=True, exist_ok=True)
    records_path = result_path / "records.jsonl"
    with records_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _write_result_task_snapshot(result_dir: str, task_config: dict, summary: dict) -> None:
    result_path = Path(result_dir)
    result_path.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "task_id": task_config.get("task_id", ""),
        "name": task_config.get("name", ""),
        "task_type": task_config.get("task_type", ""),
        "mode": task_config.get("mode", ""),
        "interval_seconds": task_config.get("interval_seconds", 0),
        "total_cycles": task_config.get("total_cycles", 0),
        "summary": summary,
    }
    (result_path / "task.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_existing_records(result_dir: str) -> list[dict]:
    records_path = Path(result_dir) / "records.jsonl"
    if not records_path.exists():
        return []
    records: list[dict] = []
    try:
        with records_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception:
        return []
    return records


def _process_single_device(task_name: str, cycle_index: int, mode: str, device_query: DeviceQuery, device: dict, firmwares: list[dict]) -> dict:
    current_version = query_device_version(device_query, str(device.get("dev_id", "")))
    target_firmware, select_error = _select_target_firmware(mode, current_version, firmwares, cycle_index)
    if target_firmware is None:
        return _build_record(task_name, cycle_index, device, current_version, None, "failed", select_error)

    status, message = prepare_and_send_upgrade(
        str(device.get("sn", "")),
        str(device.get("dev_id", "")),
        target_firmware.get("identifier", ""),
        target_firmware.get("download_url", ""),
        device_query=device_query,
        max_wake_times=3,
    )
    return _build_record(task_name, cycle_index, device, current_version, target_firmware, status, message)


def _wait_for_task_ready(task_id: str) -> bool:
    """Wait while the task is paused and stop when canceled/deleted."""
    while True:
        task = load_task(task_id)
        if not task:
            return False
        status = str(task.get("status", "")).strip()
        if status == TASK_STATUS_PAUSED:
            time.sleep(1)
            continue
        if status == TASK_STATUS_CANCELED:
            return False
        return True


def run_task(task_id: str) -> int:
    """Execute one upgrade stress task."""
    task_config = load_task_config(task_id)
    if not task_config:
        logger.error(f"未找到压测任务配置: {task_id}")
        mark_task_failed(task_id, "未找到任务配置")
        return 2

    task_state = load_task(task_id) or {}
    resume_from_cycle = 1
    existing_summary = {key: 0 for key in SUMMARY_KEYS}
    existing_records: list[dict] = []
    if task_state.get("status") == TASK_STATUS_PAUSED:
        resume_from_cycle = max(1, int(task_state.get("progress_current", 0) or 0) + 1)
        for key in SUMMARY_KEYS:
            existing_summary[key] = int(task_state.get("summary", {}).get(key, 0) or 0)
        existing_records = _load_existing_records(str(task_state.get("result_dir", "")))

    mark_task_started(task_id, os.getpid())

    env = task_config.get("env", "pro")
    username = task_config.get("username", "")
    password = task_config.get("password", "")
    if not username or not password:
        mark_task_failed(task_id, "运维账号未配置完整")
        return 3

    device_query = DeviceQuery(env, username, password)
    if device_query.init_error:
        mark_task_failed(task_id, device_query.init_error)
        return 4

    devices = list(task_config.get("devices", []))
    firmwares = list(task_config.get("firmwares", []))
    mode = task_config.get("mode", "single")
    total_cycles = max(1, int(task_config.get("total_cycles", 1) or 1))
    interval_seconds = max(0, int(task_config.get("interval_seconds", 0) or 0))
    max_workers = max(1, int(task_config.get("max_workers", 1) or 1))
    task_name = task_config.get("name", "升级压测")
    summary = dict(existing_summary)
    all_records: list[dict] = list(existing_records)

    try:
        update_task(
            task_id,
            pid=os.getpid(),
            progress_total=total_cycles,
            progress_text=f"任务开始，共 {len(devices)} 台设备，{total_cycles} 轮",
        )

        for cycle_index in range(resume_from_cycle, total_cycles + 1):
            if not _wait_for_task_ready(task_id):
                mark_task_canceled(task_id)
                return 6
            update_task(
                task_id,
                progress_text=f"第 {cycle_index}/{total_cycles} 轮进行中",
            )

            with ThreadPoolExecutor(max_workers=min(max_workers, len(devices) or 1)) as executor:
                futures = {
                    executor.submit(
                        _process_single_device,
                        task_name,
                        cycle_index,
                        mode,
                        device_query,
                        device,
                        firmwares,
                    ): device
                    for device in devices
                }
                for future in as_completed(futures):
                    if not _wait_for_task_ready(task_id):
                        executor.shutdown(wait=False, cancel_futures=True)
                        mark_task_canceled(task_id)
                        return 6
                    record = future.result()
                    all_records.append(record)
                    append_task_record(task_id, record)
                    _append_result_record(task_config.get("result_dir", ""), record)

                    status = record.get("result", "failed")
                    if status not in summary:
                        status = "failed"
                    summary[status] += 1
                    update_task(task_id, summary=summary)

            update_task(
                task_id,
                progress_current=cycle_index,
                summary=summary,
                progress_text=f"第 {cycle_index}/{total_cycles} 轮完成",
            )

            if cycle_index < total_cycles and interval_seconds > 0:
                update_task(
                    task_id,
                    progress_text=f"第 {cycle_index} 轮完成，等待 {interval_seconds} 秒后进入下一轮",
                )
                waited = 0
                while waited < interval_seconds:
                    if not _wait_for_task_ready(task_id):
                        mark_task_canceled(task_id)
                        return 6
                    time.sleep(1)
                    waited += 1

        _write_summary_csv(task_config.get("result_dir", ""), all_records)
        _write_result_task_snapshot(task_config.get("result_dir", ""), task_config, summary)
        mark_task_completed(task_id, summary)
        return 0
    except Exception as exc:
        logger.exception(f"执行升级压测任务失败: {task_id}")
        mark_task_failed(task_id, str(exc))
        return 5
