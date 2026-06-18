import importlib
import sys
import types
import unittest
from unittest import mock


class LazyImportTests(unittest.TestCase):
    def test_pages_package_stays_lazy_until_explicit_registration(self):
        import query_tool.pages as pages

        original_registered = pages._REGISTERED
        try:
            pages._REGISTERED = False
            with mock.patch.object(pages, "import_module", side_effect=lambda name, package=None: types.SimpleNamespace()) as import_mock, \
                    mock.patch.object(pages.PageRegistry, "clear") as clear_mock:
                pages.register_builtin_pages(force=True)

            self.assertEqual(
                [(module_name, "query_tool.pages") for module_name in pages._PAGE_MODULES.values()],
                [call.args for call in import_mock.call_args_list],
            )
            clear_mock.assert_called_once_with()
        finally:
            pages._REGISTERED = original_registered

    def test_utils_exports_are_loaded_on_first_attribute_access(self):
        import query_tool.utils as utils

        original_value = utils.__dict__.pop("config_manager", None)
        try:
            sentinel = object()
            fake_config_module = types.SimpleNamespace(config_manager=sentinel)
            with mock.patch.object(utils, "import_module", return_value=fake_config_module) as import_mock:
                value = utils.__getattr__("config_manager")

            self.assertIs(sentinel, value)
            self.assertIs(sentinel, utils.config_manager)
            import_mock.assert_called_once_with(".config", "query_tool.utils")
        finally:
            if original_value is not None:
                utils.config_manager = original_value
            else:
                utils.__dict__.pop("config_manager", None)

    def test_importing_pages_package_does_not_pull_in_concrete_page_modules(self):
        target_modules = [
            "query_tool.pages.device_status_page",
            "query_tool.pages.debug_page",
            "query_tool.pages.log_page",
            "query_tool.pages.firmware_page",
            "query_tool.pages.gitlab_log_page",
            "query_tool.pages.error_record_page",
        ]
        backups = {name: sys.modules.get(name) for name in target_modules if name in sys.modules}

        try:
            for name in target_modules:
                sys.modules.pop(name, None)

            importlib.import_module("query_tool.pages")

            missing = [name for name in target_modules if name in sys.modules]
            self.assertEqual([], missing)
        finally:
            for name in target_modules:
                sys.modules.pop(name, None)
            sys.modules.update(backups)


if __name__ == "__main__":
    unittest.main()
