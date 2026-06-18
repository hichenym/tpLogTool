import importlib.util
import unittest
from pathlib import Path


def _load_page_registry_module():
    module_path = Path(__file__).resolve().parents[1] / "query_tool" / "pages" / "page_registry.py"
    spec = importlib.util.spec_from_file_location("tpquerytool_page_registry_test_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


page_registry_module = _load_page_registry_module()
PageRegistry = page_registry_module.PageRegistry


class _DummyPage:
    pass


class PageRegistryTests(unittest.TestCase):
    def tearDown(self):
        PageRegistry.clear()

    def test_register_assigns_stable_default_route_key(self):
        PageRegistry.register(_DummyPage, "示例", order=1, icon=":/icons/demo.png")

        pages = PageRegistry.get_all_pages()

        self.assertEqual(1, len(pages))
        self.assertEqual(
            f"{_DummyPage.__module__}.{_DummyPage.__name__}",
            pages[0]["route_key"],
        )

    def test_register_page_respects_explicit_route_key(self):
        PageRegistry.register(_DummyPage, "示例", order=1, route_key="demo.route")

        self.assertEqual("demo.route", PageRegistry.get_all_pages()[0]["route_key"])


if __name__ == "__main__":
    unittest.main()
