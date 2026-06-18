import sys
import types
import unittest
from unittest import mock

import run as launcher


class RunLauncherTests(unittest.TestCase):
    def test_dispatch_internal_command_skips_unknown_gui_arguments(self):
        real_import = __import__

        with mock.patch.object(sys, "argv", ["run.py", "--gui"]), \
                mock.patch("builtins.__import__", wraps=real_import) as import_mock:
            result = launcher._dispatch_internal_command()

        self.assertIsNone(result)
        self.assertFalse(
            any(
                call.args and call.args[0] == "query_tool.utils.siot_debug.internal_cli"
                for call in import_mock.call_args_list
            )
        )

    def test_dispatch_internal_command_forwards_known_internal_flags(self):
        fake_internal_cli = types.ModuleType("query_tool.utils.siot_debug.internal_cli")
        fake_internal_cli.dispatch_internal_command = mock.Mock(return_value=7)

        with mock.patch.object(sys, "argv", ["run.py", "--siot-helper-probe", "target"]), \
                mock.patch.dict(
                    sys.modules,
                    {"query_tool.utils.siot_debug.internal_cli": fake_internal_cli},
                ):
            result = launcher._dispatch_internal_command()

        self.assertEqual(7, result)
        fake_internal_cli.dispatch_internal_command.assert_called_once_with(
            ["--siot-helper-probe", "target"]
        )


if __name__ == "__main__":
    unittest.main()
