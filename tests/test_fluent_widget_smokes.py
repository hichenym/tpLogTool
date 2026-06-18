import importlib
import importlib.util
import os
import sys
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


REPO_ROOT = Path(__file__).resolve().parents[1]
QUERY_TOOL_DIR = REPO_ROOT / "query_tool"
UTILS_DIR = QUERY_TOOL_DIR / "utils"
WIDGETS_DIR = QUERY_TOOL_DIR / "widgets"
PAGES_DIR = QUERY_TOOL_DIR / "pages"


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _ensure_app():
    from PyQt5.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


class _DummyButtonGroup:
    def __init__(self):
        self.widgets = []

    def add(self, *widgets):
        self.widgets.extend(widget for widget in widgets if widget is not None)

    def disable(self):
        for widget in self.widgets:
            widget.setEnabled(False)

    def enable(self):
        for widget in self.widgets:
            widget.setEnabled(True)

    def set_text(self, widget, text):
        if widget is not None:
            widget.setText(text)


class _DummyButtonManager:
    def __init__(self):
        self.groups = {}

    def create_group(self, name):
        group = _DummyButtonGroup()
        self.groups[name] = group
        return group


class _DummyThreadManager:
    def __init__(self):
        self.threads = {}

    def add(self, name, thread):
        self.threads[name] = thread

    def is_running(self, name):
        thread = self.threads.get(name)
        if thread is None:
            return False
        is_running = getattr(thread, "isRunning", None)
        return bool(is_running()) if callable(is_running) else False

    def stop_all(self, *args, **kwargs):
        self.threads.clear()


@contextmanager
def _isolated_query_tool_env():
    managed_names = [
        "query_tool.utils",
        "query_tool.utils.theme_manager",
        "query_tool.utils.style_manager",
        "query_tool.utils.config",
        "query_tool.utils.device_query",
        "query_tool.utils.update_checker",
        "query_tool.utils.task_center",
        "query_tool.widgets",
        "query_tool.widgets.adaptive_dialog",
        "query_tool.widgets.custom_widgets",
        "query_tool.widgets.task_center_dialog",
        "query_tool.widgets.update_dialog",
    ]
    backups = {name: sys.modules.get(name) for name in managed_names if name in sys.modules}

    import query_tool

    original_utils_attr = getattr(query_tool, "utils", None)
    original_widgets_attr = getattr(query_tool, "widgets", None)

    try:
        utils_pkg = types.ModuleType("query_tool.utils")
        utils_pkg.__path__ = [str(UTILS_DIR)]
        sys.modules["query_tool.utils"] = utils_pkg
        setattr(query_tool, "utils", utils_pkg)

        theme_mod = importlib.import_module("query_tool.utils.theme_manager")
        style_mod = importlib.import_module("query_tool.utils.style_manager")
        utils_pkg.StyleManager = style_mod.StyleManager

        widgets_pkg = types.ModuleType("query_tool.widgets")
        widgets_pkg.__path__ = [str(WIDGETS_DIR)]
        sys.modules["query_tool.widgets"] = widgets_pkg
        setattr(query_tool, "widgets", widgets_pkg)

        adaptive_mod = _load_module(
            "query_tool.widgets.adaptive_dialog",
            WIDGETS_DIR / "adaptive_dialog.py",
        )

        yield {
            "query_tool": query_tool,
            "utils_pkg": utils_pkg,
            "widgets_pkg": widgets_pkg,
            "theme_mod": theme_mod,
            "style_mod": style_mod,
            "adaptive_mod": adaptive_mod,
        }
    finally:
        for name in managed_names:
            if name in sys.modules:
                del sys.modules[name]
        for name, module in backups.items():
            sys.modules[name] = module
        if original_utils_attr is not None:
            setattr(query_tool, "utils", original_utils_attr)
        elif hasattr(query_tool, "utils"):
            delattr(query_tool, "utils")
        if original_widgets_attr is not None:
            setattr(query_tool, "widgets", original_widgets_attr)
        elif hasattr(query_tool, "widgets"):
            delattr(query_tool, "widgets")


@contextmanager
def _isolated_page_env():
    managed_names = [
        "query_tool.utils",
        "query_tool.utils.theme_manager",
        "query_tool.utils.style_manager",
        "query_tool.utils.logger",
        "query_tool.utils.internal_launch",
        "query_tool.utils.session_manager",
        "query_tool.utils.siot_debug",
        "query_tool.utils.siot_debug.service",
        "query_tool.utils.gitlab_api",
        "query_tool.utils.excel_helper",
        "query_tool.utils.runtime_credential_cache",
        "query_tool.utils.firmware_api",
        "query_tool.utils.error_record_api",
        "query_tool.utils.data_collect_api",
        "query_tool.utils.task_center",
        "query_tool.utils.upgrade_service",
        "query_tool.utils.workers",
        "query_tool.widgets",
        "query_tool.widgets.adaptive_dialog",
        "query_tool.widgets.custom_widgets",
        "query_tool.widgets.batch_upgrade_dialog",
        "query_tool.pages",
        "query_tool.pages.base_page",
        "query_tool.pages.page_registry",
        "query_tool.pages._device_status_page_smoke",
        "query_tool.pages._debug_page_smoke",
        "query_tool.pages._log_page_smoke",
        "query_tool.pages._firmware_page_smoke",
        "query_tool.pages._gitlab_log_page_smoke",
        "query_tool.pages._error_record_page_smoke",
        "winreg",
    ]
    backups = {name: sys.modules.get(name) for name in managed_names if name in sys.modules}

    import query_tool

    original_utils_attr = getattr(query_tool, "utils", None)
    original_widgets_attr = getattr(query_tool, "widgets", None)
    original_pages_attr = getattr(query_tool, "pages", None)

    try:
        utils_pkg = types.ModuleType("query_tool.utils")
        utils_pkg.__path__ = [str(UTILS_DIR)]
        utils_pkg.ButtonManager = _DummyButtonManager
        utils_pkg.ThreadManager = _DummyThreadManager
        utils_pkg.get_account_config = lambda: ("pro", "ops_user", "ops_pass")
        utils_pkg.get_firmware_account_config = lambda: ("fw_user", "fw_pass")
        utils_pkg.get_seetong_account_config = lambda: ("st_user", "st_pass")
        utils_pkg.check_device_online = lambda *args, **kwargs: False
        utils_pkg.wake_device_smart = lambda *args, **kwargs: False
        utils_pkg.TableHelper = object
        sys.modules["query_tool.utils"] = utils_pkg
        setattr(query_tool, "utils", utils_pkg)

        theme_mod = importlib.import_module("query_tool.utils.theme_manager")
        style_mod = importlib.import_module("query_tool.utils.style_manager")
        utils_pkg.StyleManager = style_mod.StyleManager

        app_config = types.SimpleNamespace(
            last_debug_sn="DBG-SN-001",
            debug_download_path="D:/tmp/debug",
            debug_shortcuts=["startlogp2p 31", "ls /mnt/nand/"],
            debug_shortcuts_initialized=True,
            export_path="D:/tmp/export.csv",
            phone_history=["13800138000", "test@example.com"],
            last_log_sn="LOG-SN-001\nLOG-SN-002",
            log_download_path="D:/tmp/logs",
            log_commands=["GetSystemCfg /mnt/nand/keylog.data", "GetSystemCfg /mnt/nand/dmsg1.txt"],
            log_commands_initialized=True,
        )

        class DummyConfigManager:
            def __init__(self, config):
                self._config = config

            def load_app_config(self):
                return self._config

            def save_app_config(self, config):
                self._config = config

        utils_pkg.config_manager = DummyConfigManager(app_config)

        logger_mod = types.ModuleType("query_tool.utils.logger")

        class _Logger:
            def debug(self, *args, **kwargs):
                return None

            def info(self, *args, **kwargs):
                return None

            def warning(self, *args, **kwargs):
                return None

            def error(self, *args, **kwargs):
                return None

        logger_mod.logger = _Logger()
        sys.modules["query_tool.utils.logger"] = logger_mod

        internal_launch_mod = types.ModuleType("query_tool.utils.internal_launch")
        internal_launch_mod.build_internal_command = lambda *args, **kwargs: ["echo", "internal"]
        sys.modules["query_tool.utils.internal_launch"] = internal_launch_mod

        session_manager_mod = types.ModuleType("query_tool.utils.session_manager")

        class DummySession:
            def post(self, *args, **kwargs):
                return types.SimpleNamespace(status_code=200, json=lambda: {"code": 200, "success": True, "data": ""})

            def get(self, *args, **kwargs):
                return types.SimpleNamespace(status_code=200, json=lambda: {})

        class DummySessionManager:
            def get_session(self, *args, **kwargs):
                return DummySession()

            def close_all(self):
                return None

        session_manager_mod.SessionManager = DummySessionManager
        session_manager_mod.session_manager = DummySessionManager()
        sys.modules["query_tool.utils.session_manager"] = session_manager_mod

        siot_debug_mod = types.ModuleType("query_tool.utils.siot_debug")
        siot_debug_mod.__path__ = []
        sys.modules["query_tool.utils.siot_debug"] = siot_debug_mod

        from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

        class DummySiotDebugWorker(QObject):
            status_message = pyqtSignal(str)
            connected = pyqtSignal(dict)
            connect_failed = pyqtSignal(str, str)
            disconnected = pyqtSignal(str)
            command_output = pyqtSignal(str)
            stream_log_output = pyqtSignal(str)
            command_progress = pyqtSignal(str)
            command_failed = pyqtSignal(str, str)
            command_finished = pyqtSignal(str)

            def connect_with_accounts(self, *args, **kwargs):
                return None

            def execute_command(self, *args, **kwargs):
                return None

            def disconnect_device(self, *args, **kwargs):
                return None

            def cancel_pending_connect(self):
                return None

            @pyqtSlot()
            def shutdown(self):
                return None

        def _command_keyword(command):
            text = str(command or "").strip()
            if not text:
                return ""
            return text.split(None, 1)[0].lower()

        siot_debug_mod.DEFAULT_COMMAND_TIMEOUT_MS = 5000
        siot_debug_mod.SiotDebugWorker = DummySiotDebugWorker
        siot_debug_mod.is_getsystemcfg_command = lambda command: _command_keyword(command) == "getsystemcfg"
        siot_debug_mod.is_startlogp2p_command = lambda command: _command_keyword(command) == "startlogp2p"
        siot_debug_mod.is_syscmd_family_command = lambda command: _command_keyword(command) in ("syscmd", "syscmdex")
        siot_debug_mod.parse_startlogp2p_level = (
            lambda command: command.strip().split(None, 1)[1].strip()
            if _command_keyword(command) == "startlogp2p" and len(command.strip().split(None, 1)) > 1
            else None
        )

        siot_debug_service_mod = types.ModuleType("query_tool.utils.siot_debug.service")
        siot_debug_service_mod.resolve_device_credentials = lambda *args, **kwargs: ("device_user", "device_pass")
        sys.modules["query_tool.utils.siot_debug.service"] = siot_debug_service_mod

        gitlab_api_mod = types.ModuleType("query_tool.utils.gitlab_api")

        class DummyGitLabAPI:
            def __init__(self, *args, **kwargs):
                pass

        gitlab_api_mod.GitLabAPI = DummyGitLabAPI
        sys.modules["query_tool.utils.gitlab_api"] = gitlab_api_mod

        excel_helper_mod = types.ModuleType("query_tool.utils.excel_helper")
        excel_helper_mod.create_gitlab_xlsx = lambda *args, **kwargs: None
        sys.modules["query_tool.utils.excel_helper"] = excel_helper_mod

        runtime_cache_mod = types.ModuleType("query_tool.utils.runtime_credential_cache")

        class DummySharedDeviceQuery:
            init_error = ""
            token = "token"

        runtime_cache_mod.get_shared_device_query = lambda *args, **kwargs: DummySharedDeviceQuery()
        sys.modules["query_tool.utils.runtime_credential_cache"] = runtime_cache_mod

        firmware_api_mod = types.ModuleType("query_tool.utils.firmware_api")
        firmware_api_mod.login = lambda *args, **kwargs: True
        firmware_api_mod.fetch_firmware_data = lambda *args, **kwargs: ([], 0, 0)
        firmware_api_mod.delete_firmware = lambda *args, **kwargs: (True, "ok")
        firmware_api_mod.get_firmware_detail = lambda *args, **kwargs: {}
        firmware_api_mod.update_firmware = lambda *args, **kwargs: (True, "ok")
        sys.modules["query_tool.utils.firmware_api"] = firmware_api_mod

        error_record_api_mod = types.ModuleType("query_tool.utils.error_record_api")

        class DummyMetaLoadThread:
            def __init__(self, *args, **kwargs):
                pass

        class DummyErrorRecordQueryThread:
            def __init__(self, *args, **kwargs):
                pass

        class DummyDeviceQuery:
            def get_device_info(self, *args, **kwargs):
                return {"success": True, "data": {"records": []}}

            def get_device_name(self, *args, **kwargs):
                return ""

            def get_cloud_password(self, *args, **kwargs):
                return ""

            def get_device_version(self, *args, **kwargs):
                return ""

        error_record_api_mod.MetaLoadThread = DummyMetaLoadThread
        error_record_api_mod.ErrorRecordQueryThread = DummyErrorRecordQueryThread
        error_record_api_mod._make_device_query = lambda: DummyDeviceQuery()
        error_record_api_mod.fetch_error_records = lambda *args, **kwargs: ([], 1, 1, 0)
        sys.modules["query_tool.utils.error_record_api"] = error_record_api_mod

        task_center_mod = types.ModuleType("query_tool.utils.task_center")
        task_center_mod.TASK_LIST_LIMIT = 20
        task_center_mod.count_all_tasks = lambda: 0
        task_center_mod.create_task = lambda *args, **kwargs: "task-1"
        task_center_mod.ensure_unique_task_name = lambda base: f"{base}-1"
        sys.modules["query_tool.utils.task_center"] = task_center_mod

        upgrade_service_mod = types.ModuleType("query_tool.utils.upgrade_service")
        upgrade_service_mod.prepare_and_send_upgrade = lambda *args, **kwargs: ("success", "ok")
        sys.modules["query_tool.utils.upgrade_service"] = upgrade_service_mod

        workers_mod = types.ModuleType("query_tool.utils.workers")

        class DummyWorkerThread:
            def __init__(self, *args, **kwargs):
                pass

        workers_mod.QueryThread = DummyWorkerThread
        workers_mod.WakeThread = DummyWorkerThread
        workers_mod.PhoneQueryThread = DummyWorkerThread
        sys.modules["query_tool.utils.workers"] = workers_mod

        data_collect_api_mod = types.ModuleType("query_tool.utils.data_collect_api")
        data_collect_api_mod.DataCollectThread = DummyWorkerThread
        data_collect_api_mod.BatchDataCollectThread = DummyWorkerThread
        data_collect_api_mod.get_enabled_collect_types = lambda: {
            "battery": {"name": "电池采集", "icon": ""},
            "storage": {"name": "存储采集", "icon": ""},
        }
        sys.modules["query_tool.utils.data_collect_api"] = data_collect_api_mod

        widgets_pkg = types.ModuleType("query_tool.widgets")
        widgets_pkg.__path__ = [str(WIDGETS_DIR)]
        sys.modules["query_tool.widgets"] = widgets_pkg
        setattr(query_tool, "widgets", widgets_pkg)

        from PyQt5.QtWidgets import QLineEdit, QMessageBox, QPlainTextEdit

        class DummyClickableLineEdit(QLineEdit):
            pass

        class DummyPlainTextEdit(QPlainTextEdit):
            pass

        class DummyEditFirmwareDialog:
            Accepted = 1

            def __init__(self, *args, **kwargs):
                pass

            def exec_(self):
                return 0

            def get_result(self):
                return None

            def should_send_upgrade_immediately(self):
                return False

        widgets_pkg.PlainTextEdit = DummyPlainTextEdit
        widgets_pkg.ClickableLineEdit = DummyClickableLineEdit
        widgets_pkg.EditFirmwareDialog = DummyEditFirmwareDialog
        widgets_pkg.prompt_configure_account = lambda *args, **kwargs: None
        widgets_pkg.show_question_box = lambda *args, **kwargs: QMessageBox.No

        adaptive_mod = _load_module(
            "query_tool.widgets.adaptive_dialog",
            WIDGETS_DIR / "adaptive_dialog.py",
        )
        widgets_pkg.AdaptiveDialog = adaptive_mod.AdaptiveDialog

        custom_widgets_mod = types.ModuleType("query_tool.widgets.custom_widgets")
        custom_widgets_mod.ClickableLineEdit = DummyClickableLineEdit
        custom_widgets_mod.set_dark_title_bar = lambda *args, **kwargs: None
        custom_widgets_mod.show_question_box = lambda *args, **kwargs: QMessageBox.No
        custom_widgets_mod.show_message_box = lambda *args, **kwargs: QMessageBox.Ok
        sys.modules["query_tool.widgets.custom_widgets"] = custom_widgets_mod

        batch_upgrade_mod = types.ModuleType("query_tool.widgets.batch_upgrade_dialog")

        class DummyBatchUpgradeThread:
            def __init__(self, *args, **kwargs):
                pass

        class DummyFirmwareQueryThread:
            def __init__(self, *args, **kwargs):
                pass

        batch_upgrade_mod.BatchUpgradeThread = DummyBatchUpgradeThread
        batch_upgrade_mod.FirmwareQueryThread = DummyFirmwareQueryThread
        sys.modules["query_tool.widgets.batch_upgrade_dialog"] = batch_upgrade_mod

        pages_pkg = types.ModuleType("query_tool.pages")
        pages_pkg.__path__ = [str(PAGES_DIR)]
        sys.modules["query_tool.pages"] = pages_pkg
        setattr(query_tool, "pages", pages_pkg)

        base_page_mod = _load_module(
            "query_tool.pages.base_page",
            PAGES_DIR / "base_page.py",
        )
        page_registry_mod = _load_module(
            "query_tool.pages.page_registry",
            PAGES_DIR / "page_registry.py",
        )
        pages_pkg.BasePage = base_page_mod.BasePage
        pages_pkg.PageRegistry = page_registry_mod.PageRegistry
        pages_pkg.register_page = page_registry_mod.register_page

        winreg_mod = types.ModuleType("winreg")
        winreg_mod.HKEY_CURRENT_USER = object()
        winreg_mod.KEY_READ = 0

        def _missing_registry_key(*args, **kwargs):
            raise FileNotFoundError()

        winreg_mod.OpenKey = _missing_registry_key
        winreg_mod.CloseKey = lambda *args, **kwargs: None
        sys.modules["winreg"] = winreg_mod

        yield {
            "query_tool": query_tool,
            "utils_pkg": utils_pkg,
            "widgets_pkg": widgets_pkg,
            "pages_pkg": pages_pkg,
            "theme_mod": theme_mod,
            "style_mod": style_mod,
            "adaptive_mod": adaptive_mod,
            "base_page_mod": base_page_mod,
            "page_registry_mod": page_registry_mod,
        }
    finally:
        for name in managed_names:
            if name in sys.modules:
                del sys.modules[name]
        for name, module in backups.items():
            sys.modules[name] = module
        if original_utils_attr is not None:
            setattr(query_tool, "utils", original_utils_attr)
        elif hasattr(query_tool, "utils"):
            delattr(query_tool, "utils")
        if original_widgets_attr is not None:
            setattr(query_tool, "widgets", original_widgets_attr)
        elif hasattr(query_tool, "widgets"):
            delattr(query_tool, "widgets")
        if original_pages_attr is not None:
            setattr(query_tool, "pages", original_pages_attr)
        elif hasattr(query_tool, "pages"):
            delattr(query_tool, "pages")


class FluentWidgetSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = _ensure_app()

    def tearDown(self):
        self.app.processEvents()

    def test_settings_dialog_refresh_theme(self):
        with _isolated_query_tool_env():
            config_mod = types.ModuleType("query_tool.utils.config")
            config_mod.get_account_config = lambda: ("pro", "device_user", "device_pass")
            config_mod.save_account_config = lambda *args, **kwargs: True
            config_mod.get_firmware_account_config = lambda: ("fw_user", "fw_pass")
            config_mod.save_firmware_account_config = lambda *args, **kwargs: True
            config_mod.get_seetong_account_config = lambda: ("st_user", "st_pass")
            config_mod.save_seetong_account_config = lambda *args, **kwargs: True
            config_mod.get_log_config = lambda: False
            config_mod.save_log_config = lambda *args, **kwargs: True
            sys.modules["query_tool.utils.config"] = config_mod

            device_query_mod = types.ModuleType("query_tool.utils.device_query")

            class DummyDeviceQuery:
                def __init__(self, *args, **kwargs):
                    self.init_error = ""

            device_query_mod.DeviceQuery = DummyDeviceQuery
            sys.modules["query_tool.utils.device_query"] = device_query_mod

            update_checker_mod = types.ModuleType("query_tool.utils.update_checker")

            class DummyChecker:
                def __init__(self, *args, **kwargs):
                    pass

                def should_auto_check(self):
                    return False

                def _load_cache(self):
                    return None

                def check_update_async_force_refresh(self, callback):
                    callback(False, None, "ok")

            update_checker_mod.UpdateChecker = DummyChecker
            sys.modules["query_tool.utils.update_checker"] = update_checker_mod

            custom_widgets_mod = _load_module(
                "query_tool.widgets.custom_widgets",
                WIDGETS_DIR / "custom_widgets.py",
            )
            dialog = custom_widgets_mod.SettingsDialog(initial_tab=2)
            try:
                dialog.refresh_theme()
                self.assertEqual(3, dialog.tab_stack.count())
                self.assertGreaterEqual(len(dialog._cards), 4)
                self.assertTrue(dialog.current_version_label.text().startswith("当前版本："))
            finally:
                dialog.close()
                dialog.deleteLater()

    def test_settings_dialog_pivot_click_switches_stack(self):
        with _isolated_query_tool_env():
            config_mod = types.ModuleType("query_tool.utils.config")
            config_mod.get_account_config = lambda: ("pro", "ops_user", "ops_pass")
            config_mod.get_firmware_account_config = lambda: ("fw_user", "fw_pass")
            config_mod.get_seetong_account_config = lambda: ("st_user", "st_pass")
            config_mod.save_account_config = lambda *args, **kwargs: True
            config_mod.save_firmware_account_config = lambda *args, **kwargs: True
            config_mod.save_seetong_account_config = lambda *args, **kwargs: True
            config_mod.get_log_config = lambda: False
            config_mod.save_log_config = lambda *args, **kwargs: True
            sys.modules["query_tool.utils.config"] = config_mod

            device_query_mod = types.ModuleType("query_tool.utils.device_query")

            class DummyDeviceQuery:
                def __init__(self, *args, **kwargs):
                    self.init_error = ""

            device_query_mod.DeviceQuery = DummyDeviceQuery
            sys.modules["query_tool.utils.device_query"] = device_query_mod

            update_checker_mod = types.ModuleType("query_tool.utils.update_checker")

            class DummyChecker:
                def __init__(self, *args, **kwargs):
                    pass

                def should_auto_check(self):
                    return False

                def _load_cache(self):
                    return None

                def check_update_async_force_refresh(self, callback):
                    callback(False, None, "ok")

            update_checker_mod.UpdateChecker = DummyChecker
            sys.modules["query_tool.utils.update_checker"] = update_checker_mod

            custom_widgets_mod = _load_module(
                "query_tool.widgets.custom_widgets",
                WIDGETS_DIR / "custom_widgets.py",
            )
            app = _ensure_app()
            dialog = custom_widgets_mod.SettingsDialog(initial_tab=0)
            try:
                dialog.show()
                app.processEvents()
                pivot_items = dialog.tab_pivot.findChildren(type(dialog.tab_pivot.currentItem()))
                self.assertEqual(3, len(pivot_items))

                QTest.mouseClick(pivot_items[1], Qt.LeftButton)
                app.processEvents()
                self.assertEqual(1, dialog.tab_stack.currentIndex())

                QTest.mouseClick(pivot_items[2], Qt.LeftButton)
                app.processEvents()
                self.assertEqual(2, dialog.tab_stack.currentIndex())
            finally:
                dialog.close()
                dialog.deleteLater()

    def test_task_center_dialog_refresh_theme(self):
        with _isolated_query_tool_env():
            task_center_mod = types.ModuleType("query_tool.utils.task_center")
            task_center_mod.TASK_STATUS_PENDING = "pending"
            task_center_mod.TASK_STATUS_RUNNING = "running"
            task_center_mod.TASK_STATUS_PAUSED = "paused"
            task_center_mod.TASK_STATUS_COMPLETED = "completed"
            task_center_mod.TASK_STATUS_FAILED = "failed"
            task_center_mod.TASK_STATUS_CANCELED = "canceled"
            task_center_mod.list_tasks = lambda: [
                {
                    "task_id": "task-1",
                    "name": "升级任务A",
                    "created_at": "2026-06-17 10:00:00",
                    "started_at": "2026-06-17 10:01:00",
                    "status": "running",
                    "progress_current": 2,
                    "progress_total": 5,
                    "result_dir": "D:/tmp/a",
                    "progress_text": "执行中",
                    "last_error": "",
                },
                {
                    "task_id": "task-2",
                    "name": "升级任务B",
                    "created_at": "2026-06-17 09:00:00",
                    "started_at": "",
                    "status": "paused",
                    "progress_current": 1,
                    "progress_total": 3,
                    "result_dir": "D:/tmp/b",
                    "progress_text": "",
                    "last_error": "等待继续",
                },
            ]
            for name in (
                "cancel_task",
                "continue_task",
                "delete_task",
                "mark_task_paused",
                "reset_task_for_execute",
                "start_task_process",
            ):
                setattr(task_center_mod, name, lambda *args, **kwargs: None)
            sys.modules["query_tool.utils.task_center"] = task_center_mod

            custom_widgets_stub = types.ModuleType("query_tool.widgets.custom_widgets")
            custom_widgets_stub.set_dark_title_bar = lambda window: None
            sys.modules["query_tool.widgets.custom_widgets"] = custom_widgets_stub

            task_center_dialog_mod = _load_module(
                "query_tool.widgets.task_center_dialog",
                WIDGETS_DIR / "task_center_dialog.py",
            )
            dialog = task_center_dialog_mod.TaskCenterDialog()
            try:
                dialog.refresh_theme()
                self.assertEqual(2, dialog.task_table.rowCount())
                self.assertIn("运行中 1 个", dialog.summary_label.text())
                self.assertEqual("taskCenterCard", dialog.task_group.objectName())
            finally:
                dialog.close()
                dialog.deleteLater()

    def test_update_dialog_refresh_theme_and_progress(self):
        with _isolated_query_tool_env():
            custom_widgets_stub = types.ModuleType("query_tool.widgets.custom_widgets")
            custom_widgets_stub.set_title_bar_theme = lambda window, dark=True: None
            sys.modules["query_tool.widgets.custom_widgets"] = custom_widgets_stub

            update_checker_mod = types.ModuleType("query_tool.utils.update_checker")

            class VersionInfo:
                def __init__(self, data):
                    self.version = data.get("version", "")
                    self.build_date = data.get("build_date", "")
                    self.file_size_mb = data.get("file_size_mb", 0)
                    self.show_change = bool(data.get("show_change", True))
                    changelog = data.get("changelog", [])
                    self.changelog = [str(item).strip() for item in changelog if str(item).strip()]

            update_checker_mod.VersionInfo = VersionInfo
            sys.modules["query_tool.utils.update_checker"] = update_checker_mod

            update_dialog_mod = _load_module(
                "query_tool.widgets.update_dialog",
                WIDGETS_DIR / "update_dialog.py",
            )
            version_info = update_checker_mod.VersionInfo(
                {
                    "version": "9.9.9",
                    "build_date": "20260617",
                    "file_size_mb": 12.5,
                    "show_change": True,
                    "changelog": ["修复主题刷新", "优化对话框卡片布局"],
                }
            )

            prompt_dialog = update_dialog_mod.UpdatePromptDialog(version_info, "9.9.8")
            download_dialog = update_dialog_mod.UpdateDownloadDialog(version_info)
            complete_dialog = update_dialog_mod.UpdateCompleteDialog(version_info)
            try:
                prompt_dialog.refresh_theme()
                self.assertEqual("发现新版本 V9.9.9", prompt_dialog.title_label.text())
                self.assertIsNotNone(prompt_dialog.change_label)

                download_dialog.refresh_theme()
                download_dialog.update_progress(1024 * 1024, 2 * 1024 * 1024)
                self.assertEqual(50, download_dialog.progress_bar.value())
                self.assertIn("已下载 1.00 MB / 2.00 MB", download_dialog.status_label.text())

                complete_dialog.refresh_theme()
                self.assertEqual("检测到功能变更", complete_dialog.title_label.text())
                self.assertIsNotNone(complete_dialog.change_label)
            finally:
                for dialog in (prompt_dialog, download_dialog, complete_dialog):
                    dialog.close()
                    dialog.deleteLater()

    def test_firmware_page_refresh_theme(self):
        with _isolated_page_env():
            firmware_page_mod = _load_module(
                "query_tool.pages._firmware_page_smoke",
                PAGES_DIR / "firmware_page.py",
            )
            page = firmware_page_mod.FirmwarePage()
            try:
                page.refresh_theme()
                self.assertEqual("新增固件", page.add_firmware_btn.text())
                self.assertEqual("查询", page.query_btn.text())
                self.assertEqual("重置", page.reset_btn.text())
                self.assertEqual(6, page.result_table.columnCount())
                self.assertEqual("[0/0]", page.page_label.text())
                self.assertIn("右键表格展开更多操作", page.tip_label.text())
            finally:
                page.close()
                page.deleteLater()

    def test_device_status_page_refresh_theme_and_load_config(self):
        with _isolated_page_env():
            device_status_page_mod = _load_module(
                "query_tool.pages._device_status_page_smoke",
                PAGES_DIR / "device_status_page.py",
            )
            page = device_status_page_mod.DeviceStatusPage()
            try:
                page.load_config()
                page.refresh_theme()
                self.assertEqual("设备查询", page.query_btn.text())
                self.assertEqual("清空结果", page.clear_btn.text())
                self.assertEqual("批量升级", page.batch_upgrade_btn.text())
                self.assertEqual(9, page.result_table.columnCount())
                self.assertEqual("D:/tmp/export.csv", page.export_path_input.text())
                self.assertGreaterEqual(page.phone_input.count(), 2)
            finally:
                page.cleanup()
                page.close()
                page.deleteLater()

    def test_debug_page_refresh_theme_and_load_config(self):
        with _isolated_page_env():
            debug_page_mod = _load_module(
                "query_tool.pages._debug_page_smoke",
                PAGES_DIR / "debug_page.py",
            )
            page = debug_page_mod.DebugPage()
            try:
                page.load_config()
                page.on_page_show()
                page.refresh_theme()
                self.assertEqual("登录", page.connect_btn.text())
                self.assertEqual("发送", page.send_btn.text())
                self.assertEqual("DBG-SN-001", page.sn_input.text())
                self.assertEqual(2, len(page.shortcut_commands))
                self.assertEqual(2, page.shortcut_flow_layout.count())
            finally:
                page.cleanup()
                page.close()
                page.deleteLater()

    def test_gitlab_log_page_refresh_theme(self):
        with _isolated_page_env():
            gitlab_log_page_mod = _load_module(
                "query_tool.pages._gitlab_log_page_smoke",
                PAGES_DIR / "gitlab_log_page.py",
            )
            page = gitlab_log_page_mod.GitLabLogPage()
            try:
                page.refresh_theme()
                self.assertEqual("连接", page.connect_btn.text())
                self.assertEqual("导出", page.export_btn.text())
                self.assertEqual("查询", page.query_btn.text())
                self.assertEqual("收起", page.toggle_conditions_btn.text())
                self.assertFalse(page.export_btn.isEnabled())
                self.assertFalse(page.query_btn.isEnabled())
                self.assertFalse(page.search_card.isVisible())
                self.assertIn("Git 提交记录", page.result_text.placeholderText())
            finally:
                page.close()
                page.deleteLater()

    def test_log_page_refresh_theme_and_load_config(self):
        with _isolated_page_env():
            log_page_mod = _load_module(
                "query_tool.pages._log_page_smoke",
                PAGES_DIR / "log_page.py",
            )
            page = log_page_mod.LogPage()
            try:
                page.on_page_show()
                page.refresh_theme()
                self.assertEqual("发送", page.fetch_btn.text())
                self.assertEqual(4, page.result_table.columnCount())
                self.assertEqual("LOG-SN-001\nLOG-SN-002", page.sn_input.toPlainText())
                self.assertIn("GetSystemCfg /mnt/nand/keylog.data", page.command_input.toPlainText())
                self.assertEqual("未选择设备", page.result_selection_label.text())
            finally:
                page.cleanup()
                page.close()
                page.deleteLater()

    def test_error_record_page_refresh_theme(self):
        with _isolated_page_env():
            error_record_page_mod = _load_module(
                "query_tool.pages._error_record_page_smoke",
                PAGES_DIR / "error_record_page.py",
            )
            page = error_record_page_mod.ErrorRecordPage()
            try:
                page.refresh_theme()
                self.assertEqual("刷新数据", page.refresh_meta_btn.text())
                self.assertEqual("查询", page.query_btn.text())
                self.assertEqual("重置", page.reset_btn.text())
                self.assertEqual(len(page.COLUMNS), page.result_table.columnCount())
                self.assertEqual("[0/0]", page.page_label.text())
                self.assertEqual("", page.total_label.text())
                self.assertFalse(page.export_csv_btn.isEnabled())
                self.assertFalse(page.export_json_btn.isEnabled())
            finally:
                page.close()
                page.deleteLater()

    def test_reboot_dialog_refresh_theme(self):
        with _isolated_page_env():
            reboot_dialog_mod = _load_module(
                "query_tool.widgets._reboot_dialog_smoke",
                WIDGETS_DIR / "reboot_dialog.py",
            )
            device_query = types.SimpleNamespace(init_error="", token="token")
            with mock.patch.object(reboot_dialog_mod.RebootDialog, "query_status", autospec=True, return_value=None):
                dialog = reboot_dialog_mod.RebootDialog("SN-001", "DEV-001", device_query)
            try:
                dialog.refresh_theme()
                self.assertEqual("确定", dialog.confirm_btn.text())
                self.assertEqual("取消", dialog.cancel_btn.text())
                self.assertIn("查询中", dialog.status_label.text())
            finally:
                dialog.close()
                dialog.deleteLater()

    def test_port_mapping_dialog_refresh_theme(self):
        with _isolated_page_env():
            port_mapping_dialog_mod = _load_module(
                "query_tool.widgets._port_mapping_dialog_smoke",
                WIDGETS_DIR / "port_mapping_dialog.py",
            )
            with mock.patch.object(port_mapping_dialog_mod.PortMappingDialog, "query_status", autospec=True, return_value=None):
                dialog = port_mapping_dialog_mod.PortMappingDialog("SN-001", "DEV-001", "设备A", object())
            try:
                dialog.refresh_theme()
                self.assertEqual("116.63.13.64", dialog.ip_input.text())
                self.assertEqual("确定", dialog.confirm_btn.text())
                self.assertEqual("取消", dialog.cancel_btn.text())
            finally:
                dialog.close()
                dialog.deleteLater()

    def test_upgrade_dialog_refresh_theme(self):
        with _isolated_page_env():
            upgrade_dialog_mod = _load_module(
                "query_tool.widgets._upgrade_dialog_smoke",
                WIDGETS_DIR / "upgrade_dialog.py",
            )
            with mock.patch.object(upgrade_dialog_mod.UpgradeDialog, "query_status", autospec=True, return_value=None), \
                    mock.patch.object(upgrade_dialog_mod.UpgradeDialog, "query_firmware", autospec=True, return_value=None):
                dialog = upgrade_dialog_mod.UpgradeDialog("SN-001", "DEV-001", "设备A", "M1", object())
            try:
                dialog.refresh_theme()
                self.assertEqual("查询", dialog.query_firmware_btn.text())
                self.assertEqual("开始升级", dialog.confirm_btn.text())
                self.assertEqual("取消", dialog.cancel_btn.text())
                self.assertEqual(6, dialog.firmware_table.columnCount())
            finally:
                dialog.close()
                dialog.deleteLater()

    def test_batch_upgrade_dialog_refresh_theme(self):
        with _isolated_page_env():
            batch_upgrade_dialog_mod = _load_module(
                "query_tool.widgets._batch_upgrade_dialog_smoke",
                WIDGETS_DIR / "batch_upgrade_dialog.py",
            )
            devices = [
                ("设备A", "SN-001", "DEV-001", "M1"),
                ("设备B", "SN-002", "DEV-002", "M1"),
            ]
            with mock.patch.object(batch_upgrade_dialog_mod.BatchUpgradeDialog, "start_initial_query", autospec=True, return_value=None), \
                    mock.patch.object(batch_upgrade_dialog_mod.BatchUpgradeDialog, "query_firmware", autospec=True, return_value=None):
                dialog = batch_upgrade_dialog_mod.BatchUpgradeDialog(devices, object(), 4)
            try:
                dialog.refresh_theme()
                self.assertEqual(2, dialog.device_table.rowCount())
                self.assertEqual("查询", dialog.query_firmware_btn.text())
                self.assertEqual("开始升级", dialog.confirm_btn.text())
                self.assertEqual("取消", dialog.cancel_btn.text())
            finally:
                dialog.close()
                dialog.deleteLater()

    def test_batch_reboot_dialog_refresh_theme(self):
        with _isolated_page_env():
            batch_reboot_dialog_mod = _load_module(
                "query_tool.widgets._batch_reboot_dialog_smoke",
                WIDGETS_DIR / "batch_reboot_dialog.py",
            )
            devices = [
                ("SN-001", "DEV-001", "设备A"),
                ("SN-002", "DEV-002", "设备B"),
            ]
            with mock.patch.object(batch_reboot_dialog_mod.BatchRebootDialog, "start_initial_query", autospec=True, return_value=None):
                dialog = batch_reboot_dialog_mod.BatchRebootDialog(devices, object(), 4)
            try:
                dialog.refresh_theme()
                self.assertEqual(2, dialog.device_table.rowCount())
                self.assertEqual("刷新状态", dialog.refresh_btn.text())
                self.assertEqual("开始重启", dialog.confirm_btn.text())
                self.assertEqual("取消", dialog.cancel_btn.text())
            finally:
                dialog.close()
                dialog.deleteLater()

    def test_collect_type_selector_dialog_refresh_theme(self):
        with _isolated_page_env():
            selector_dialog_mod = _load_module(
                "query_tool.widgets._collect_type_selector_dialog_smoke",
                WIDGETS_DIR / "collect_type_selector_dialog.py",
            )
            dialog = selector_dialog_mod.CollectTypeSelectorDialog([("设备A", "SN-001", "DEV-001", "M1")], 4, object())
            try:
                dialog.refresh_theme()
                self.assertEqual("选择采集类型", dialog.title_label.text())
                self.assertEqual(2, len(dialog.type_buttons))
                self.assertEqual("取消", dialog.cancel_btn.text())
            finally:
                dialog.close()
                dialog.deleteLater()

    def test_upgrade_stress_dialog_refresh_theme(self):
        with _isolated_page_env():
            stress_dialog_mod = _load_module(
                "query_tool.widgets._upgrade_stress_dialog_smoke",
                WIDGETS_DIR / "upgrade_stress_dialog.py",
            )
            devices = [("设备A", "SN-001", "DEV-001", "M1")]
            with mock.patch.object(stress_dialog_mod.UpgradeStressDialog, "query_firmware", autospec=True, return_value=None):
                dialog = stress_dialog_mod.UpgradeStressDialog(devices, 4)
            try:
                dialog.refresh_theme()
                self.assertEqual("M1", dialog.identifier_input.text())
                self.assertTrue(dialog.identifier_input.isReadOnly())
                self.assertEqual("启动任务", dialog.confirm_btn.text())
                self.assertEqual("取消", dialog.cancel_btn.text())
            finally:
                dialog.close()
                dialog.deleteLater()

    def test_battery_collect_dialog_refresh_theme(self):
        with _isolated_page_env():
            battery_dialog_mod = _load_module(
                "query_tool.widgets._battery_collect_dialog_smoke",
                WIDGETS_DIR / "battery_collect_dialog.py",
            )
            dialog = battery_dialog_mod.BatteryCollectDialog("SN-001", "DEV-001", "设备A", "M1", object())
            try:
                dialog.refresh_theme()
                self.assertEqual("开始查询", dialog.query_btn.text())
                self.assertEqual("导出结果", dialog.export_btn.text())
                self.assertEqual("关闭", dialog.close_btn.text())
                self.assertEqual(2, dialog.result_table.columnCount())
            finally:
                dialog.close()
                dialog.deleteLater()

    def test_batch_battery_collect_dialog_refresh_theme(self):
        with _isolated_page_env():
            batch_battery_dialog_mod = _load_module(
                "query_tool.widgets._batch_battery_collect_dialog_smoke",
                WIDGETS_DIR / "batch_battery_collect_dialog.py",
            )
            devices = [
                {"device_name": "设备A", "sn": "SN-001", "dev_id": "DEV-001", "model": "M1"},
                {"device_name": "设备B", "sn": "SN-002", "dev_id": "DEV-002", "model": "M1"},
            ]
            dialog = batch_battery_dialog_mod.BatchBatteryCollectDialog(devices, 4, object())
            try:
                dialog.refresh_theme()
                self.assertEqual(2, dialog.device_table.rowCount())
                self.assertEqual("开始查询", dialog.query_btn.text())
                self.assertEqual("导出结果", dialog.export_btn.text())
                self.assertEqual("关闭", dialog.close_btn.text())
            finally:
                dialog.close()
                dialog.deleteLater()

    def test_edit_firmware_dialog_refresh_theme(self):
        with _isolated_page_env():
            edit_firmware_dialog_mod = _load_module(
                "query_tool.widgets._edit_firmware_dialog_smoke",
                WIDGETS_DIR / "edit_firmware_dialog.py",
            )
            with mock.patch.object(edit_firmware_dialog_mod.EditFirmwareDialog, "load_data", autospec=True, return_value=None):
                dialog = edit_firmware_dialog_mod.EditFirmwareDialog(None, {})
            try:
                dialog.refresh_theme()
                self.assertEqual("选择文件", dialog.file_btn.text())
                self.assertEqual("保存", dialog.submit_btn.text())
                self.assertEqual("取消", dialog.cancel_btn.text())
                self.assertIn("固件标识", dialog.identifier_input.placeholderText())
            finally:
                dialog.close()
                dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
