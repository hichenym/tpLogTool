from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import signal
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .config import config_manager
from .internal_launch import build_internal_command
from .logger import logger


TASK_STATUS_PENDING = "pending"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_PAUSED = "paused"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"
TASK_STATUS_CANCELED = "canceled"

TASK_LIST_LIMIT = 10
TASK_REGISTRY_KEY = "background_tasks_json"

RUNNING_TASK_STATUSES = {TASK_STATUS_PENDING, TASK_STATUS_RUNNING}
ACTIONABLE_TASK_STATUSES = {TASK_STATUS_PENDING, TASK_STATUS_RUNNING, TASK_STATUS_PAUSED}
FINISHED_TASK_STATUSES = {TASK_STATUS_COMPLETED, TASK_STATUS_FAILED, TASK_STATUS_CANCELED}


def get_app_data_dir() -> Path:
    root = Path.home() / ".TPQueryTool"
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_task_root_dir() -> Path:
    root = get_app_data_dir() / "tasks"
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_task_dir(task_id: str) -> Path:
    task_dir = get_task_root_dir() / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir


def get_task_meta_path(task_id: str) -> Path:
    return get_task_dir(task_id) / "task.json"


def get_task_config_path(task_id: str) -> Path:
    return get_task_dir(task_id) / "config.json"


def get_task_records_path(task_id: str) -> Path:
    return get_task_dir(task_id) / "records.jsonl"


def _utc_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _path_safe_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\\\|?*]+', "_", (name or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ._")
    return cleaned or "升级压测"


def _result_dir_timestamp(value: str | None = None) -> str:
    text = (value or "").strip()
    if text:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(text, fmt).strftime("%Y%m%d_%H%M%S")
            except ValueError:
                continue
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def build_result_dir_name(task_name: str, started_at: str | None = None) -> str:
    return f"{_path_safe_name(task_name)}_{_result_dir_timestamp(started_at)}"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        temp_path.write_text(content, encoding="utf-8")
        os.replace(str(temp_path), str(path))
        return
    except PermissionError:
        pass
    path.write_text(content, encoding="utf-8")


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error(f"读取任务文件失败 {path}: {exc}")
        return None


def _default_store() -> dict:
    return {
        "tasks": [],
    }


def _migrate_tasks_from_dirs() -> dict:
    tasks: list[dict] = []
    root = get_task_root_dir()
    if not root.exists():
        return _default_store()

    for task_dir in root.iterdir():
        if not task_dir.is_dir():
            continue
        task_meta = _read_json(task_dir / "task.json")
        if not task_meta:
            continue
        tasks.append(task_meta)

    tasks.sort(
        key=lambda item: (
            item.get("created_at", ""),
            item.get("task_id", ""),
        ),
        reverse=True,
    )
    return {"tasks": tasks}


def _load_store() -> dict:
    raw = config_manager._get_value(TASK_REGISTRY_KEY, "")
    if raw:
        try:
            store = json.loads(raw)
            if isinstance(store, dict) and isinstance(store.get("tasks"), list):
                return store
        except Exception as exc:
            logger.error(f"解析后台任务注册表 JSON 失败: {exc}")

    store = _migrate_tasks_from_dirs()
    _save_store(store)
    return store


def _save_store(store: dict) -> bool:
    try:
        return bool(config_manager._set_value(TASK_REGISTRY_KEY, json.dumps(store, ensure_ascii=False)))
    except Exception as exc:
        logger.error(f"保存后台任务注册表 JSON 失败: {exc}")
        return False


def _task_index(store: dict, task_id: str) -> int:
    for index, task in enumerate(store.get("tasks", [])):
        if str(task.get("task_id", "")) == task_id:
            return index
    return -1


def normalize_task_name(name: str) -> str:
    normalized = (name or "").strip()
    if not normalized:
        return "升级压测"
    return re.sub(r"\(\d+\)$", "", normalized).strip()


def list_tasks(statuses: Iterable[str] | None = None) -> list[dict]:
    allowed = set(statuses or [])
    tasks = list(_load_store().get("tasks", []))
    if not allowed:
        return tasks
    return [task for task in tasks if task.get("status") in allowed]


def count_running_tasks() -> int:
    return len(list_tasks(RUNNING_TASK_STATUSES))


def count_all_tasks() -> int:
    return len(list_tasks())


def ensure_unique_task_name(name: str, exclude_task_id: str | None = None) -> str:
    base_name = normalize_task_name(name)
    existing_names = []
    for task in list_tasks():
        if exclude_task_id and task.get("task_id") == exclude_task_id:
            continue
        existing_names.append(str(task.get("name", "")).strip())

    if base_name not in existing_names:
        return base_name

    max_suffix = 1
    pattern = re.compile(rf"^{re.escape(base_name)}(?:\((\d+)\))?$")
    for existing_name in existing_names:
        match = pattern.match(existing_name)
        if not match:
            continue
        suffix = match.group(1)
        if suffix:
            max_suffix = max(max_suffix, int(suffix))
    return f"{base_name}({max_suffix + 1})"


def _build_task_meta(task_id: str, task_type: str, name: str, payload: dict, task_dir: Path, output_dir: Path) -> dict:
    return {
        "task_id": task_id,
        "task_type": task_type,
        "name": name,
        "status": TASK_STATUS_PENDING,
        "created_at": _utc_now(),
        "started_at": "",
        "finished_at": "",
        "progress_text": "任务已创建，等待启动",
        "progress_current": 0,
        "progress_total": int(payload.get("total_cycles", 0) or 0),
        "pid": 0,
        "result_dir": str(output_dir),
        "task_dir": str(task_dir),
        "last_error": "",
        "summary": {
            "success": 0,
            "offline": 0,
            "wake_failed": 0,
            "failed": 0,
        },
    }


def create_task(task_type: str, name: str, payload: dict, result_root_dir: str) -> dict:
    store = _load_store()
    if len(store.get("tasks", [])) >= TASK_LIST_LIMIT:
        raise ValueError("任务列表已满，需要删除后再继续添加")

    task_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    task_dir = get_task_dir(task_id)
    created_at = _utc_now()
    output_dir = Path(result_root_dir).expanduser() / build_result_dir_name(name, created_at)
    output_dir.mkdir(parents=True, exist_ok=True)

    task_meta = _build_task_meta(task_id, task_type, name, payload, task_dir, output_dir)
    task_meta["created_at"] = created_at
    task_config = dict(payload)
    task_config.update(
        {
            "task_id": task_id,
            "task_type": task_type,
            "name": name,
            "created_at": task_meta["created_at"],
            "result_dir": str(output_dir),
            "result_root_dir": str(Path(result_root_dir).expanduser()),
            "task_dir": str(task_dir),
        }
    )

    _write_json(get_task_meta_path(task_id), task_meta)
    _write_json(get_task_config_path(task_id), task_config)
    get_task_records_path(task_id).touch(exist_ok=True)

    store["tasks"] = [task_meta] + list(store.get("tasks", []))
    _save_store(store)
    return task_meta


def load_task(task_id: str) -> dict | None:
    for task in _load_store().get("tasks", []):
        if str(task.get("task_id", "")) == task_id:
            return task
    return _read_json(get_task_meta_path(task_id))


def load_task_config(task_id: str) -> dict | None:
    return _read_json(get_task_config_path(task_id))


def update_task(task_id: str, **updates) -> dict | None:
    store = _load_store()
    index = _task_index(store, task_id)
    if index < 0:
        return None
    task_meta = dict(store["tasks"][index])
    task_meta.update(updates)
    store["tasks"][index] = task_meta
    _save_store(store)
    _write_json(get_task_meta_path(task_id), task_meta)
    return task_meta


def mark_task_started(task_id: str, pid: int) -> dict | None:
    return update_task(
        task_id,
        status=TASK_STATUS_RUNNING,
        started_at=_utc_now(),
        finished_at="",
        pid=int(pid or 0),
        progress_text="任务进行中",
    )


def mark_task_completed(task_id: str, summary: dict, last_error: str = "") -> dict | None:
    detail_text = "任务已完成" if not any(int(summary.get(key, 0) or 0) > 0 for key in ("offline", "wake_failed", "failed")) else "任务已完成，存在失败记录"
    return update_task(
        task_id,
        status=TASK_STATUS_COMPLETED,
        finished_at=_utc_now(),
        last_error=last_error,
        summary=summary,
        progress_text=detail_text,
    )


def mark_task_failed(task_id: str, message: str) -> dict | None:
    return update_task(
        task_id,
        status=TASK_STATUS_FAILED,
        finished_at=_utc_now(),
        last_error=message,
        progress_text=message or "任务失败",
    )


def mark_task_paused(task_id: str, stop_process: bool = False) -> dict | None:
    task = load_task(task_id)
    if not task or task.get("status") not in (TASK_STATUS_PENDING, TASK_STATUS_RUNNING):
        return None
    if stop_process:
        terminate_task_process(task.get("pid", 0))
    return update_task(
        task_id,
        status=TASK_STATUS_PAUSED,
        pid=0,
        progress_text="任务已暂停",
    )


def mark_task_canceled(task_id: str) -> dict | None:
    return update_task(
        task_id,
        status=TASK_STATUS_CANCELED,
        finished_at=_utc_now(),
        pid=0,
        progress_text="任务已取消",
    )


def append_task_record(task_id: str, record: dict) -> None:
    path = get_task_records_path(task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def process_is_alive(pid: int | None) -> bool:
    try:
        pid = int(pid or 0)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    except Exception:
        return True
    return True


def terminate_task_process(pid: int | None) -> bool:
    try:
        pid = int(pid or 0)
    except (TypeError, ValueError):
        return False
    if pid <= 0 or not process_is_alive(pid):
        return False

    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        else:
            os.kill(pid, signal.SIGTERM)
        return True
    except Exception as exc:
        logger.warning(f"停止任务进程失败 PID={pid}: {exc}")
        return False


def clear_task_runtime_outputs(task_id: str) -> None:
    task = load_task(task_id)
    if not task:
        return

    records_path = get_task_records_path(task_id)
    records_path.write_text("", encoding="utf-8")

    task_meta_path = get_task_meta_path(task_id)
    if not task_meta_path.parent.exists():
        task_meta_path.parent.mkdir(parents=True, exist_ok=True)

    result_dir = Path(task.get("result_dir", ""))
    if result_dir.exists():
        for file_name in ("summary.csv", "records.jsonl", "task.json"):
            file_path = result_dir / file_name
            if file_path.exists():
                try:
                    file_path.unlink()
                except Exception as exc:
                    logger.warning(f"删除旧任务结果失败 {file_path}: {exc}")


def reset_task_for_execute(task_id: str, name: str | None = None) -> dict | None:
    task = load_task(task_id)
    if not task:
        return None
    if task.get("status") in ACTIONABLE_TASK_STATUSES:
        return None
    new_name = ensure_unique_task_name(name or task.get("name", ""), exclude_task_id=task_id)
    clear_task_runtime_outputs(task_id)
    store = _load_store()
    index = _task_index(store, task_id)
    if index < 0:
        return None

    task_config = load_task_config(task_id) or {}
    restarted_at = _utc_now()
    result_root_dir = task_config.get("result_root_dir") or str(Path(task.get("result_dir", "")).parent)
    new_result_dir = Path(result_root_dir).expanduser() / build_result_dir_name(new_name, restarted_at)
    new_result_dir.mkdir(parents=True, exist_ok=True)

    updated_task = dict(store["tasks"][index])
    updated_task.update(
        {
            "name": new_name,
            "status": TASK_STATUS_PENDING,
            "created_at": restarted_at,
            "started_at": restarted_at,
            "finished_at": "",
            "progress_current": 0,
            "progress_text": "任务已创建，等待启动",
            "pid": 0,
            "result_dir": str(new_result_dir),
            "last_error": "",
            "summary": {
                "success": 0,
                "offline": 0,
                "wake_failed": 0,
                "failed": 0,
            },
        }
    )
    del store["tasks"][index]
    store["tasks"] = [updated_task] + list(store.get("tasks", []))
    _save_store(store)
    _write_json(get_task_meta_path(task_id), updated_task)

    task_config.update(
        {
            "name": new_name,
            "created_at": restarted_at,
            "result_dir": str(new_result_dir),
            "result_root_dir": str(Path(result_root_dir).expanduser()),
        }
    )
    _write_json(get_task_config_path(task_id), task_config)
    return updated_task


def start_task_process(task_id: str) -> bool:
    try:
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            build_internal_command("--upgrade-stress-runner", task_id),
            creationflags=creation_flags,
        )
        return True
    except Exception as exc:
        logger.error(f"启动任务子进程失败 {task_id}: {exc}")
        mark_task_failed(task_id, str(exc))
        return False


def continue_task(task_id: str) -> bool:
    task = load_task(task_id)
    if not task:
        return False
    if task.get("status") not in (TASK_STATUS_PAUSED, TASK_STATUS_PENDING):
        return False

    pid = int(task.get("pid", 0) or 0)
    update_task(task_id, status=TASK_STATUS_RUNNING, progress_text="任务进行中")
    if process_is_alive(pid):
        return True
    return start_task_process(task_id)


def cancel_task(task_id: str) -> bool:
    task = load_task(task_id)
    if not task:
        return False
    if task.get("status") not in (TASK_STATUS_PENDING, TASK_STATUS_RUNNING, TASK_STATUS_PAUSED):
        return False
    terminate_task_process(task.get("pid", 0))
    mark_task_canceled(task_id)
    return True


def delete_task(task_id: str) -> bool:
    store = _load_store()
    index = _task_index(store, task_id)
    if index < 0:
        return False

    task = store["tasks"][index]
    if task.get("status") in ACTIONABLE_TASK_STATUSES:
        logger.warning(f"任务仍在运行流程中，禁止删除: {task_id}")
        return False

    del store["tasks"][index]
    _save_store(store)

    task_dir = get_task_root_dir() / task_id
    if task_dir.exists():
        try:
            shutil.rmtree(task_dir)
        except Exception as exc:
            logger.error(f"删除任务目录失败 {task_dir}: {exc}")
    return True


def cleanup_finished_tasks() -> int:
    removed_count = 0
    for task in list(list_tasks(FINISHED_TASK_STATUSES)):
        task_id = task.get("task_id", "")
        if task_id and delete_task(task_id):
            removed_count += 1
    return removed_count


def pause_all_actionable_tasks(stop_processes: bool = False) -> int:
    paused_count = 0
    for task in list(list_tasks()):
        status = task.get("status")
        if status in (TASK_STATUS_PENDING, TASK_STATUS_RUNNING):
            if mark_task_paused(task.get("task_id", ""), stop_process=stop_processes):
                paused_count += 1
        elif status == TASK_STATUS_PAUSED:
            if stop_processes:
                terminate_task_process(task.get("pid", 0))
            paused_count += 1
    return paused_count
