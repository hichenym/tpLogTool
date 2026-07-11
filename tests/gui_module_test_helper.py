import importlib.util
import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _swap_module(name, module, originals):
    if name not in originals:
        originals[name] = sys.modules.get(name)
    sys.modules[name] = module


def _restore_modules(originals):
    for name, original in originals.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


def _install_pyqt_stubs(originals):
    if "PyQt5" in sys.modules:
        return

    pyqt5 = types.ModuleType("PyQt5")
    qtwidgets = types.ModuleType("PyQt5.QtWidgets")
    qtcore = types.ModuleType("PyQt5.QtCore")
    qtgui = types.ModuleType("PyQt5.QtGui")

    class _Dummy:
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, *args, **kwargs):
            return None

        def __getattr__(self, _name):
            return lambda *args, **kwargs: None

    class _Signal:
        def connect(self, *_args, **_kwargs):
            return None

        def emit(self, *_args, **_kwargs):
            return None

    class _ComboBox(_Dummy):
        NoInsert = 0

    class _TextEdit(_Dummy):
        NoWrap = 0

    class _Frame(_Dummy):
        NoFrame = 0
        HLine = 0
        StyledPanel = 0
        Sunken = 0
        VLine = 0
        Plain = 0

    class _AbstractItemView(_Dummy):
        NoEditTriggers = 0
        SelectRows = 0
        SingleSelection = 0
        ScrollPerPixel = 0

    class _Style(_Dummy):
        CE_ItemViewItem = 0

    class _MessageBox(_Dummy):
        Yes = 0x01
        No = 0x02
        Ok = 0x04
        Cancel = 0x08
        Question = 0x10
        Information = 0x20
        Warning = 0x40

        def button(self, *_args, **_kwargs):
            return _Dummy()

        def exec_(self):
            return self.Yes

    class _Application(_Dummy):
        @staticmethod
        def instance():
            return None

    class _QtNamespace:
        AlignRight = 0
        AlignVCenter = 0
        AlignLeft = 0
        AlignCenter = 0
        AlignTop = 0
        Vertical = 0
        Horizontal = 0
        StrongFocus = 0
        NoFocus = 1
        OtherFocusReason = 2
        CustomContextMenu = 3
        LeftButton = 1
        MoveAction = 4
        Popup = 5
        FramelessWindowHint = 6
        WA_ShowWithoutActivating = 7
        ScrollBarAlwaysOff = 8
        Key_Up = 9
        Key_Down = 10
        Key_Return = 11
        Key_Enter = 12
        Key_Tab = 13
        Key_Escape = 14
        Key_Delete = 15
        UserRole = 1000
        ElideMiddle = 16
        green = 17
        red = 18
        gray = 19
        darkYellow = 20

        @staticmethod
        def Orientations(_value):
            return 0

    class _EventNamespace:
        KeyPress = 1
        MouseButtonPress = 2
        FocusOut = 3

    qtwidgets.QWidget = _Dummy
    qtwidgets.QDialog = _Dummy
    qtwidgets.QApplication = _Application
    qtwidgets.QVBoxLayout = _Dummy
    qtwidgets.QHBoxLayout = _Dummy
    qtwidgets.QLabel = _Dummy
    qtwidgets.QPushButton = _Dummy
    qtwidgets.QListWidget = _Dummy
    qtwidgets.QListWidgetItem = _Dummy
    qtwidgets.QTableWidget = _Dummy
    qtwidgets.QTableWidgetItem = _Dummy
    qtwidgets.QHeaderView = _Dummy
    qtwidgets.QCheckBox = _Dummy
    qtwidgets.QSplitter = _Dummy
    qtwidgets.QFrame = _Frame
    qtwidgets.QFileDialog = _Dummy
    qtwidgets.QMessageBox = _MessageBox
    qtwidgets.QComboBox = _ComboBox
    qtwidgets.QSizePolicy = _Dummy
    qtwidgets.QGroupBox = _Dummy
    qtwidgets.QLineEdit = _Dummy
    qtwidgets.QTextEdit = _TextEdit
    qtwidgets.QLayout = _Dummy
    qtwidgets.QMenu = _Dummy
    qtwidgets.QScrollArea = _Dummy
    qtwidgets.QTabWidget = _Dummy
    qtwidgets.QAbstractItemView = _AbstractItemView
    qtwidgets.QStyledItemDelegate = _Dummy
    qtwidgets.QStyle = _Style

    qtcore.Qt = _QtNamespace
    qtcore.QEvent = _EventNamespace
    qtcore.QSize = _Dummy
    qtcore.QRect = _Dummy
    qtcore.QRectF = _Dummy
    qtcore.QPointF = _Dummy
    qtcore.QPoint = _Dummy
    qtcore.QTimer = _Dummy
    qtcore.QThread = _Dummy
    qtcore.QDateTime = _Dummy
    qtcore.QMetaObject = _Dummy
    qtcore.QMimeData = _Dummy
    qtcore.QUrl = _Dummy
    qtcore.pyqtSignal = lambda *args, **kwargs: _Signal()

    qtgui.QIcon = _Dummy
    qtgui.QColor = _Dummy
    qtgui.QDesktopServices = _Dummy
    qtgui.QDrag = _Dummy
    qtgui.QImage = _Dummy
    qtgui.QKeySequence = _Dummy
    qtgui.QPixmap = _Dummy
    qtgui.QTextCharFormat = _Dummy
    qtgui.QTextCursor = _Dummy
    qtgui.QTextDocument = _Dummy
    qtgui.QCursor = _Dummy

    _swap_module("PyQt5", pyqt5, originals)
    _swap_module("PyQt5.QtWidgets", qtwidgets, originals)
    _swap_module("PyQt5.QtCore", qtcore, originals)
    _swap_module("PyQt5.QtGui", qtgui, originals)


def _install_query_tool_package_stubs(originals):
    import query_tool

    for pkg_name in ("query_tool.pages", "query_tool.widgets", "query_tool.utils"):
        pkg = types.ModuleType(pkg_name)
        pkg.__path__ = [str(REPO_ROOT / Path(*pkg_name.split(".")))]
        _swap_module(pkg_name, pkg, originals)


def _install_page_stubs(originals):
    base_page = types.ModuleType("query_tool.pages.base_page")

    class BasePage:
        def __init__(self, *args, **kwargs):
            pass

    base_page.BasePage = BasePage
    _swap_module("query_tool.pages.base_page", base_page, originals)

    page_registry = types.ModuleType("query_tool.pages.page_registry")
    page_registry.register_page = lambda *args, **kwargs: (lambda cls: cls)
    _swap_module("query_tool.pages.page_registry", page_registry, originals)


def _install_common_utils_stubs(originals):
    class _Dummy:
        def __init__(self, *args, **kwargs):
            pass

    class _StyleManager:
        @staticmethod
        def apply_to_widget(*args, **kwargs):
            return None

        @staticmethod
        def __getattr__(_name):
            return lambda *args, **kwargs: ""

    utils_stub = types.ModuleType("query_tool.utils")
    utils_stub.StyleManager = _StyleManager
    utils_stub.config_manager = _Dummy()
    utils_stub.get_account_config = lambda: ("", "", "")
    utils_stub.get_seetong_account_config = lambda: ("", "")
    utils_stub.ButtonManager = _Dummy
    utils_stub.MessageManager = _Dummy
    utils_stub.ThreadManager = _Dummy
    utils_stub.TableHelper = _Dummy
    utils_stub.DeviceQuery = _Dummy
    utils_stub.check_device_online = lambda *args, **kwargs: False
    _swap_module("query_tool.utils", utils_stub, originals)

    config_stub = types.ModuleType("query_tool.utils.config")
    config_stub.get_account_config = lambda: ("", "", "")
    config_stub.save_account_config = lambda *args, **kwargs: True
    config_stub.get_firmware_account_config = lambda: ("", "")
    config_stub.save_firmware_account_config = lambda *args, **kwargs: True
    config_stub.get_seetong_account_config = lambda: ("", "")
    config_stub.save_seetong_account_config = lambda *args, **kwargs: True
    config_stub.get_log_config = lambda: False
    _swap_module("query_tool.utils.config", config_stub, originals)

    device_query_stub = types.ModuleType("query_tool.utils.device_query")
    device_query_stub.DeviceQuery = _Dummy
    _swap_module("query_tool.utils.device_query", device_query_stub, originals)

    style_manager_stub = types.ModuleType("query_tool.utils.style_manager")
    style_manager_stub.StyleManager = _StyleManager
    _swap_module("query_tool.utils.style_manager", style_manager_stub, originals)

    theme_manager_stub = types.ModuleType("query_tool.utils.theme_manager")
    theme_manager_stub.t = lambda key: key
    theme_manager_stub.theme_manager = types.SimpleNamespace(is_dark=True)
    _swap_module("query_tool.utils.theme_manager", theme_manager_stub, originals)

    logger_stub = types.ModuleType("query_tool.utils.logger")
    logger_stub.logger = types.SimpleNamespace(
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
        debug=lambda *args, **kwargs: None,
    )
    _swap_module("query_tool.utils.logger", logger_stub, originals)


def _install_debug_page_stubs(originals):
    _install_common_utils_stubs(originals)

    siot_debug_stub = types.ModuleType("query_tool.utils.siot_debug")
    siot_debug_stub.DEFAULT_COMMAND_TIMEOUT_MS = 1000
    siot_debug_stub.SiotDebugWorker = type("SiotDebugWorker", (), {})
    siot_debug_stub.is_getsystemcfg_command = lambda *_args, **_kwargs: False
    siot_debug_stub.is_startlogp2p_command = lambda *_args, **_kwargs: False
    siot_debug_stub.is_syscmd_family_command = lambda *_args, **_kwargs: False
    siot_debug_stub.parse_startlogp2p_level = lambda *_args, **_kwargs: None
    _swap_module("query_tool.utils.siot_debug", siot_debug_stub, originals)

    adaptive_dialog_stub = types.ModuleType("query_tool.widgets.adaptive_dialog")
    adaptive_dialog_stub.AdaptiveDialog = type("AdaptiveDialog", (), {})
    _swap_module("query_tool.widgets.adaptive_dialog", adaptive_dialog_stub, originals)

    custom_widgets_stub = types.ModuleType("query_tool.widgets.custom_widgets")
    custom_widgets_stub.prompt_configure_account = lambda *args, **kwargs: None
    custom_widgets_stub.set_dark_title_bar = lambda *args, **kwargs: None
    _swap_module("query_tool.widgets.custom_widgets", custom_widgets_stub, originals)


def _install_log_page_stubs(originals):
    _install_common_utils_stubs(originals)

    internal_launch_stub = types.ModuleType("query_tool.utils.internal_launch")
    internal_launch_stub.build_internal_command = lambda *args, **kwargs: []
    _swap_module("query_tool.utils.internal_launch", internal_launch_stub, originals)

    siot_debug_stub = types.ModuleType("query_tool.utils.siot_debug")
    siot_debug_stub.DEFAULT_COMMAND_TIMEOUT_MS = 1000
    siot_debug_stub.is_getsystemcfg_command = lambda *_args, **_kwargs: False
    siot_debug_stub.is_syscmd_family_command = lambda *_args, **_kwargs: False
    _swap_module("query_tool.utils.siot_debug", siot_debug_stub, originals)

    service_stub = types.ModuleType("query_tool.utils.siot_debug.service")
    service_stub.resolve_device_credentials = lambda *args, **kwargs: ({}, None)
    _swap_module("query_tool.utils.siot_debug.service", service_stub, originals)

    widgets_stub = types.ModuleType("query_tool.widgets")
    widgets_stub.__path__ = [str(REPO_ROOT / "query_tool" / "widgets")]
    widgets_stub.PlainTextEdit = type("PlainTextEdit", (), {})
    widgets_stub.prompt_configure_account = lambda *args, **kwargs: None
    _swap_module("query_tool.widgets", widgets_stub, originals)


def _install_custom_widgets_stubs(originals):
    _install_common_utils_stubs(originals)

    adaptive_dialog_stub = types.ModuleType("query_tool.widgets.adaptive_dialog")
    adaptive_dialog_stub.AdaptiveDialog = type("AdaptiveDialog", (), {})
    _swap_module("query_tool.widgets.adaptive_dialog", adaptive_dialog_stub, originals)


def _load_module(module_name, relative_path):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_debug_page():
    module_name = "query_tool.pages._debug_page_test"
    if module_name in sys.modules:
        return sys.modules[module_name].DebugPage

    originals = {}
    try:
        _install_pyqt_stubs(originals)
        _install_query_tool_package_stubs(originals)
        _install_page_stubs(originals)
        _install_debug_page_stubs(originals)
        module = _load_module(module_name, "query_tool/pages/debug_page.py")
    finally:
        _restore_modules(originals)

    return module.DebugPage


def load_log_page():
    module_name = "query_tool.pages._log_page_test"
    if module_name in sys.modules:
        return sys.modules[module_name].LogPage

    originals = {}
    try:
        _install_pyqt_stubs(originals)
        _install_query_tool_package_stubs(originals)
        _install_page_stubs(originals)
        _install_log_page_stubs(originals)
        module = _load_module(module_name, "query_tool/pages/log_page.py")
    finally:
        _restore_modules(originals)

    return module.LogPage


def load_custom_widgets_module():
    module_name = "query_tool.widgets._custom_widgets_test"
    if module_name in sys.modules:
        return sys.modules[module_name]

    originals = {}
    try:
        _install_pyqt_stubs(originals)
        _install_query_tool_package_stubs(originals)
        _install_custom_widgets_stubs(originals)
        module = _load_module(module_name, "query_tool/widgets/custom_widgets.py")
    finally:
        _restore_modules(originals)

    return module
