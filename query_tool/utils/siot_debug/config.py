from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SDK_BIN_DIR = PROJECT_ROOT / "query_tool" / "dll"

APP_LOG_DIR = Path.home() / ".TPQueryTool" / "logs"
RUN_LOG_PATH = APP_LOG_DIR / "siot_debug_run.log"

CLOUD_LOGIN_URL = "https://app-auth.seetong.com/seetong-member-auth/oauth/token"
CLOUD_ACCESS_URL = "https://app-auth.seetong.com/seetong-client/client/access-node"
CLOUD_AUTH_BASIC = "Basic c2VldG9uZ19jbG91ZF9tZW1iZXI6c2VldG9uZ19jbG91ZF9tZW1iZXJfc2VjcmV0"

DEVICE_USERNAME = "admin"
DEVICE_GATEWAY_ID = ""

DEFAULT_COMMAND_TIMEOUT_MS = 30_000
DEFAULT_QUERY_DEVICE_DELAY_S = 1.0
DEFAULT_TEXT_RESULT_SETTLE_S = 0.25
DEFAULT_EMPTY_RESULT_SETTLE_S = 0.45
FILE_INLINE_OUTPUT_MAX_BYTES = 256 * 1024
DEFAULT_WAKEUP_INTERVAL_MS = 5_000
DEFAULT_WAKEUP_RETRY_COUNT = 6
