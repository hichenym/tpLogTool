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
            return _Dummy()

    class _FontMetrics(_Dummy):
        def height(self):
            return 20

        def horizontalAdvance(self, text):
            return len(str(text)) * 8

    class _Font(_Dummy):
        Normal = 0
        DemiBold = 1

    class _Palette(_Dummy):
        WindowText = 0

    class _ComboBox(_Dummy):
        NoInsert = 0

    class _Frame(_Dummy):
        VLine = 0
        Plain = 0
        NoFrame = 0

    class _SizePolicy(_Dummy):
        Expanding = 0
        Preferred = 0
        Fixed = 0
        Minimum = 0

    class _MessageBox(_Dummy):
        Yes = 0x01
        No = 0x02
        Question = 0x04

    class _QtNamespace:
        AlignRight = 0
        AlignVCenter = 0
        AlignCenter = 0
        Vertical = 0
        StrongFocus = 0
        AlignLeft = 0
        green = 0
        red = 0
        gray = 0
        darkYellow = 0
        AutoText = 0

    qtwidgets.QAction = _Dummy
    qtwidgets.QAbstractItemView = _Dummy
    qtwidgets.QApplication = _Dummy
    qtwidgets.QVBoxLayout = _Dummy
    qtwidgets.QHBoxLayout = _Dummy
    qtwidgets.QLabel = _Dummy
    qtwidgets.QPushButton = _Dummy
    qtwidgets.QLineEdit = _Dummy
    qtwidgets.QPlainTextEdit = _Dummy
    qtwidgets.QProgressBar = _Dummy
    qtwidgets.QRadioButton = _Dummy
    qtwidgets.QScrollArea = _Dummy
    qtwidgets.QSpinBox = _Dummy
    qtwidgets.QTableWidget = _Dummy
    qtwidgets.QTableWidgetItem = _Dummy
    qtwidgets.QTextEdit = _Dummy
    qtwidgets.QHeaderView = _Dummy
    qtwidgets.QCheckBox = _Dummy
    qtwidgets.QSplitter = _Dummy
    qtwidgets.QFrame = _Frame
    qtwidgets.QFileDialog = _Dummy
    qtwidgets.QMessageBox = _MessageBox
    qtwidgets.QMenu = _Dummy
    qtwidgets.QWidget = _Dummy
    qtwidgets.QComboBox = _ComboBox
    qtwidgets.QDateEdit = _Dummy
    qtwidgets.QSizePolicy = _SizePolicy

    qtcore.Qt = _QtNamespace
    qtcore.QSize = _Dummy
    qtcore.QTimer = _Dummy

    qtgui.QIcon = _Dummy
    qtgui.QColor = _Dummy
    qtgui.QFont = _Font
    qtgui.QFontMetrics = _FontMetrics
    qtgui.QPalette = _Palette

    _swap_module("PyQt5", pyqt5, originals)
    _swap_module("PyQt5.QtWidgets", qtwidgets, originals)
    _swap_module("PyQt5.QtCore", qtcore, originals)
    _swap_module("PyQt5.QtGui", qtgui, originals)


def _install_page_stubs(originals):
    import query_tool

    pages_pkg = types.ModuleType("query_tool.pages")
    pages_pkg.__path__ = [str(REPO_ROOT / "query_tool" / "pages")]
    _swap_module("query_tool.pages", pages_pkg, originals)

    base_page = types.ModuleType("query_tool.pages.base_page")

    class BasePage:
        def __init__(self, *args, **kwargs):
            pass

    base_page.BasePage = BasePage
    _swap_module("query_tool.pages.base_page", base_page, originals)

    page_registry = types.ModuleType("query_tool.pages.page_registry")
    page_registry.register_page = lambda *args, **kwargs: (lambda cls: cls)
    _swap_module("query_tool.pages.page_registry", page_registry, originals)


def _install_query_tool_stubs(originals):
    class _Dummy:
        def __init__(self, *args, **kwargs):
            pass

    class _StyleManager:
        @staticmethod
        def apply_to_widget(*args, **kwargs):
            return None

        @staticmethod
        def get_READONLY_INPUT():
            return ""

        @staticmethod
        def get_PLAINTEXT_EDIT_TABLE():
            return ""

    utils_stub = types.ModuleType("query_tool.utils")
    utils_stub.ButtonManager = _Dummy
    utils_stub.MessageManager = _Dummy
    utils_stub.ThreadManager = _Dummy
    utils_stub.StyleManager = _StyleManager
    utils_stub.TableHelper = _Dummy
    utils_stub.get_account_config = lambda: ("", "", "")
    utils_stub.DeviceQuery = _Dummy
    utils_stub.check_device_online = lambda *args, **kwargs: False
    _swap_module("query_tool.utils", utils_stub, originals)

    theme_manager_stub = types.ModuleType("query_tool.utils.theme_manager")
    theme_manager_stub.t = lambda key: key
    theme_manager_stub.theme_manager = object()
    _swap_module("query_tool.utils.theme_manager", theme_manager_stub, originals)

    runtime_cache_stub = types.ModuleType("query_tool.utils.runtime_credential_cache")
    runtime_cache_stub.get_shared_device_query = lambda *args, **kwargs: None
    _swap_module("query_tool.utils.runtime_credential_cache", runtime_cache_stub, originals)

    workers_stub = types.ModuleType("query_tool.utils.workers")
    workers_stub.QueryThread = _Dummy
    workers_stub.WakeThread = _Dummy
    workers_stub.PhoneQueryThread = _Dummy
    _swap_module("query_tool.utils.workers", workers_stub, originals)

    widgets_stub = types.ModuleType("query_tool.widgets")
    widgets_stub.PlainTextEdit = _Dummy
    widgets_stub.ClickableLineEdit = _Dummy
    widgets_stub.show_question_box = lambda *args, **kwargs: None
    widgets_stub.prompt_configure_account = lambda *args, **kwargs: None
    _swap_module("query_tool.widgets", widgets_stub, originals)


def load_device_status_page():
    module_name = "query_tool.pages._device_status_page_test"
    if module_name in sys.modules:
        return sys.modules[module_name].DeviceStatusPage

    originals = {}
    try:
        for name in ("query_tool.ui", "query_tool.ui.fluent", "query_tool.ui.widgets"):
            if name not in originals:
                originals[name] = sys.modules.get(name)
        _install_pyqt_stubs(originals)
        _install_page_stubs(originals)
        _install_query_tool_stubs(originals)

        module_path = REPO_ROOT / "query_tool" / "pages" / "device_status_page.py"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    finally:
        _restore_modules(originals)

    return module.DeviceStatusPage
