import unittest
from types import SimpleNamespace

from tests.gui_module_test_helper import load_debug_page


DebugPage = load_debug_page()


class DebugPageCommandHistoryTests(unittest.TestCase):
    def test_match_command_history_returns_prefix_matches_only(self):
        page = SimpleNamespace(
            command_history=[
                "grep test /tmp/test.log",
                "uname -a",
                "testcmd start",
                "ls /tmp",
            ],
            COMMAND_TYPES=DebugPage.COMMAND_TYPES,
            _normalize_history_command=lambda text: DebugPage._normalize_display_command(page, text),
        )

        matches = DebugPage._match_command_history(page, "te")

        self.assertEqual(
            ["testcmd start"],
            matches,
        )

    def test_handle_history_popup_key_event_enter_executes_selected_command(self):
        qt = DebugPage._handle_history_popup_key_event.__globals__["Qt"]
        applied = []
        page = SimpleNamespace(
            history_popup=SimpleNamespace(
                has_active_selection=lambda: True,
                select_prev=lambda: None,
                select_next=lambda: None,
                current_value=lambda: "testcmd start",
            ),
            _should_handle_popup_navigation=lambda *_args, **_kwargs: True,
            _apply_history_suggestion=lambda context, command, submit=False: applied.append((context, command, submit)),
        )

        handled = DebugPage._handle_history_popup_key_event(
            page,
            "input",
            "te",
            SimpleNamespace(key=lambda: qt.Key_Return),
        )
        self.assertTrue(handled)
        self.assertEqual([("input", "testcmd start", True)], applied)

    def test_handle_history_popup_key_event_enter_does_not_intercept_without_selection(self):
        qt = DebugPage._handle_history_popup_key_event.__globals__["Qt"]
        applied = []
        page = SimpleNamespace(
            history_popup=SimpleNamespace(
                has_active_selection=lambda: False,
                select_prev=lambda: None,
                select_next=lambda: None,
                current_value=lambda: "",
            ),
            _should_handle_popup_navigation=lambda *_args, **_kwargs: True,
            _apply_history_suggestion=lambda context, command, submit=False: applied.append((context, command, submit)),
        )

        handled = DebugPage._handle_history_popup_key_event(
            page,
            "input",
            "te",
            SimpleNamespace(key=lambda: qt.Key_Return),
        )

        self.assertFalse(handled)
        self.assertEqual([], applied)

    def test_handle_history_popup_key_event_tab_only_completes(self):
        qt = DebugPage._handle_history_popup_key_event.__globals__["Qt"]
        applied = []
        page = SimpleNamespace(
            history_popup=SimpleNamespace(
                has_active_selection=lambda: True,
                select_prev=lambda: None,
                select_next=lambda: None,
                current_value=lambda: "testcmd start",
            ),
            _should_handle_popup_navigation=lambda *_args, **_kwargs: True,
            _apply_history_suggestion=lambda context, command, submit=False: applied.append((context, command, submit)),
        )

        handled = DebugPage._handle_history_popup_key_event(
            page,
            "input",
            "te",
            SimpleNamespace(key=lambda: qt.Key_Tab),
        )

        self.assertTrue(handled)
        self.assertEqual([("input", "testcmd start", False)], applied)

    def test_handle_history_popup_key_event_delete_removes_selected_command(self):
        qt = DebugPage._handle_history_popup_key_event.__globals__["Qt"]
        deleted = []
        page = SimpleNamespace(
            history_popup=SimpleNamespace(
                has_active_selection=lambda: True,
                select_prev=lambda: None,
                select_next=lambda: None,
                current_value=lambda: "testcmd start",
            ),
            _should_handle_popup_navigation=lambda *_args, **_kwargs: True,
            _delete_history_suggestion=lambda context, command: deleted.append((context, command)),
        )

        handled = DebugPage._handle_history_popup_key_event(
            page,
            "input",
            "te",
            SimpleNamespace(key=lambda: qt.Key_Delete),
        )

        self.assertTrue(handled)
        self.assertEqual([("input", "testcmd start")], deleted)

    def test_apply_history_suggestion_submit_from_console_clears_current_input_before_submit(self):
        calls = []
        page = SimpleNamespace(
            console_edit=SimpleNamespace(
                clear_current_input=lambda: calls.append("clear"),
                set_current_input=lambda command: calls.append(("set", command)),
            ),
            command_input=SimpleNamespace(
                setText=lambda command: calls.append(("input_set", command)),
                setCursorPosition=lambda pos: calls.append(("cursor", pos)),
            ),
            _hide_history_suggestions=lambda: calls.append("hide"),
            _submit_command=lambda command, source="input": calls.append(("submit", command, source)),
        )

        DebugPage._apply_history_suggestion(page, "console", "testcmd start", submit=True)

        self.assertEqual(
            ["clear", "hide", ("submit", "testcmd start", "console")],
            calls,
        )

    def test_prepare_history_navigation_update_suppresses_matching_until_manual_input(self):
        page = SimpleNamespace(
            _history_suggestion_suppressed_contexts=set(),
            _history_programmatic_update_contexts=set(),
            _active_suggestion_context="input",
            _hide_history_suggestions=lambda: hidden.append("hide"),
        )
        hidden = []

        DebugPage._prepare_history_navigation_update(page, "input")

        self.assertEqual({"input"}, page._history_suggestion_suppressed_contexts)
        self.assertEqual({"input"}, page._history_programmatic_update_contexts)
        self.assertEqual(["hide"], hidden)

    def test_handle_history_input_changed_ignores_programmatic_history_update(self):
        updates = []
        page = SimpleNamespace(
            _history_programmatic_update_contexts={"input"},
            _history_suggestion_suppressed_contexts={"input"},
            _update_history_suggestions=lambda context, text: updates.append((context, text)),
        )

        DebugPage._handle_history_input_changed(page, "input", "uname -a")

        self.assertEqual([], updates)
        self.assertEqual(set(), page._history_programmatic_update_contexts)
        self.assertEqual({"input"}, page._history_suggestion_suppressed_contexts)

    def test_handle_history_input_changed_resumes_matching_after_manual_edit(self):
        updates = []
        page = SimpleNamespace(
            _history_programmatic_update_contexts=set(),
            _history_suggestion_suppressed_contexts={"input"},
            _update_history_suggestions=lambda context, text: updates.append((context, text)),
        )

        DebugPage._handle_history_input_changed(page, "input", "uname -a1")

        self.assertEqual([("input", "uname -a1")], updates)
        self.assertEqual(set(), page._history_suggestion_suppressed_contexts)

    def test_record_successful_command_deduplicates_and_moves_to_latest(self):
        persisted_history = []
        page = SimpleNamespace(
            command_history=["uname -a", "cat /tmp/test.log"],
            MAX_HISTORY=100,
            COMMAND_TYPES=DebugPage.COMMAND_TYPES,
            history_index=3,
            history_draft="draft",
            _normalize_history_command=lambda text: DebugPage._normalize_display_command(page, text),
            _persist_command_history=lambda: persisted_history.append(list(page.command_history)),
        )

        DebugPage._record_successful_command(page, "uname -a")

        self.assertEqual(
            ["cat /tmp/test.log", "uname -a"],
            page.command_history,
        )
        self.assertEqual([["cat /tmp/test.log", "uname -a"]], persisted_history)
        self.assertIsNone(page.history_index)
        self.assertEqual("", page.history_draft)

    def test_remove_command_history_entry_persists_and_resets_navigation_state(self):
        persisted_history = []
        page = SimpleNamespace(
            command_history=["uname -a", "cat /tmp/test.log"],
            COMMAND_TYPES=DebugPage.COMMAND_TYPES,
            history_index=1,
            history_draft="draft",
            _normalize_history_command=lambda text: DebugPage._normalize_display_command(page, text),
            _persist_command_history=lambda: persisted_history.append(list(page.command_history)),
        )

        removed = DebugPage._remove_command_history_entry(page, "uname -a")

        self.assertTrue(removed)
        self.assertEqual(["cat /tmp/test.log"], page.command_history)
        self.assertEqual([["cat /tmp/test.log"]], persisted_history)
        self.assertIsNone(page.history_index)
        self.assertEqual("", page.history_draft)

    def test_on_command_finished_records_only_successful_commands(self):
        recorded_commands = []
        page = SimpleNamespace(
            command_running=True,
            _last_command_failed=False,
            _executing_command="cat /tmp/test.log",
            _executing_backend_command="syscmd cat /tmp/test.log",
            _pending_stream_log_state=None,
            _stream_log_active=False,
            connected=False,
            _record_successful_command=lambda command: recorded_commands.append(command),
            _auto_open_pending_downloads=lambda: None,
        )

        DebugPage.on_command_finished(page)
        self.assertEqual(["cat /tmp/test.log"], recorded_commands)
        self.assertEqual("", page._executing_command)

        page.command_running = True
        page._last_command_failed = True
        page._executing_command = "rm /tmp/test.log"
        page._executing_backend_command = "syscmd rm /tmp/test.log"
        DebugPage.on_command_finished(page)
        self.assertEqual(["cat /tmp/test.log"], recorded_commands)
        self.assertEqual("", page._executing_command)


if __name__ == "__main__":
    unittest.main()
