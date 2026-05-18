from __future__ import annotations

import os
import sys
from pathlib import Path


def _is_sdk_bin_dir(path: Path) -> bool:
    path = Path(path)
    return path.is_dir() and (path / "libsiot.dll").exists() and (path / "libtps_crypt.dll").exists()


def _iter_sdk_dir_candidates():
    seen = set()

    def add(path_like):
        if not path_like:
            return
        try:
            path = Path(path_like).resolve()
        except Exception:
            return
        key = str(path).lower()
        if key in seen:
            return
        seen.add(key)
        yield path

    env_path = (os.environ.get("TPQUERYTOOL_SDK_BIN_DIR") or "").strip()
    if env_path:
        yield from add(env_path)

    current_file = Path(__file__).resolve()
    if len(current_file.parents) >= 4:
        yield from add(current_file.parents[3] / "query_tool" / "dll")

    for base in filter(None, (sys.executable, sys.argv[0] if sys.argv else "")):
        base_dir = Path(base).resolve().parent
        yield from add(base_dir / "query_tool" / "dll")
        yield from add(base_dir / "dll")

    for parent in current_file.parents:
        yield from add(parent / "query_tool" / "dll")
        yield from add(parent / "dll")


def _iter_sdk_search_roots():
    seen = set()
    current_file = Path(__file__).resolve()
    roots = []

    if len(current_file.parents) >= 4:
        roots.append(current_file.parents[3])

    for base in filter(None, (sys.executable, sys.argv[0] if sys.argv else "")):
        roots.append(Path(base).resolve().parent)

    for root in roots:
        try:
            resolved = Path(root).resolve()
        except Exception:
            resolved = Path(root)
        key = str(resolved).lower()
        if key in seen or not resolved.exists():
            continue
        seen.add(key)
        yield resolved


def resolve_sdk_bin_dir(preferred: str | Path | None = None) -> Path:
    candidates = []
    if preferred:
        candidates.append(Path(preferred))
    candidates.extend(_iter_sdk_dir_candidates())

    seen = set()
    for candidate in candidates:
        try:
            path = Path(candidate).resolve()
        except Exception:
            path = Path(candidate)
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        if _is_sdk_bin_dir(path):
            return path

    for root in _iter_sdk_search_roots():
        root_depth = len(root.parts)
        for current_root, dirnames, filenames in os.walk(root):
            current_path = Path(current_root)
            if len(current_path.parts) - root_depth > 4:
                dirnames[:] = []
                continue
            lowered_names = {name.lower() for name in filenames}
            if "libsiot.dll" in lowered_names and "libtps_crypt.dll" in lowered_names:
                return current_path

    if preferred:
        return Path(preferred)
    if candidates:
        return Path(candidates[0])
    return Path(__file__).resolve().parents[3] / "query_tool" / "dll"


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SDK_BIN_DIR = resolve_sdk_bin_dir(PROJECT_ROOT / "query_tool" / "dll")

APP_LOG_DIR = Path.home() / ".TPQueryTool" / "logs"
RUN_LOG_PATH = APP_LOG_DIR / "siot_debug_run.log"

CLOUD_LOGIN_URL = "https://app-auth.seetong.com/seetong-member-auth/oauth/token"
CLOUD_ACCESS_URL = "https://app-auth.seetong.com/seetong-client/client/access-node"
CLOUD_AUTH_BASIC = "Basic c2VldG9uZ19jbG91ZF9tZW1iZXI6c2VldG9uZ19jbG91ZF9tZW1iZXJfc2VjcmV0"

DEVICE_USERNAME = "admin"
DEVICE_GATEWAY_ID = ""

DEFAULT_COMMAND_TIMEOUT_MS = 30_000
DEFAULT_QUERY_DEVICE_DELAY_S = 0.6
DEFAULT_TEXT_RESULT_SETTLE_S = 0.15
DEFAULT_EMPTY_RESULT_SETTLE_S = 0.25
FILE_INLINE_OUTPUT_MAX_BYTES = 256 * 1024
DEFAULT_WAKEUP_INTERVAL_MS = 5_000
DEFAULT_WAKEUP_RETRY_COUNT = 6
