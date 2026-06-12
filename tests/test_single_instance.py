import tempfile
import unittest

from PyQt5.QtCore import QCoreApplication, QEventLoop, QTimer

from query_tool.utils.single_instance import SingleInstanceController, build_server_name


class SingleInstanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_build_server_name_is_stable_for_same_scope(self):
        scope_path = r"D:\software\TopSee\TPQueryTool.exe"

        self.assertEqual(build_server_name(scope_path), build_server_name(scope_path))

    def test_notify_existing_instance_triggers_activation_signal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            server_name = build_server_name(temp_dir)
            primary = SingleInstanceController(server_name)
            self.assertTrue(primary.start())

            activated = []
            loop = QEventLoop()

            def on_activated():
                activated.append(True)
                loop.quit()

            primary.activation_requested.connect(on_activated)

            try:
                self.assertTrue(
                    SingleInstanceController.notify_existing_instance(server_name, timeout_ms=1000)
                )
                QTimer.singleShot(1000, loop.quit)
                loop.exec_()
                self.assertTrue(activated)
            finally:
                primary.close()


if __name__ == "__main__":
    unittest.main()
