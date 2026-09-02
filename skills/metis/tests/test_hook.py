"""Behavior regressions for scripts/metis_hook.py."""

import json
import subprocess
import sys
import unittest
from pathlib import Path


HOOK = Path(__file__).resolve().parents[1] / "scripts" / "metis_hook.py"


def run_hook(stdin_text: str) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin_text,
        capture_output=True,
        text=True,
    )


def payload(**fields: object) -> str:
    return json.dumps(fields)


class MetisHookTests(unittest.TestCase):
    def assert_silent(self, result: "subprocess.CompletedProcess[str]") -> None:
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_user_prompt_submit_in_plan_mode_emits_reminder(self) -> None:
        result = run_hook(payload(
            hook_event_name="UserPromptSubmit", permission_mode="plan", prompt="x"
        ))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        specific = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(specific["hookEventName"], "UserPromptSubmit")
        context = specific["additionalContext"]
        self.assertIn("metis", context)
        self.assertIn("repo-relative paths inside", context)
        self.assertIn("absolute paths outside", context)
        self.assertNotIn("\n", context)
        self.assertLessEqual(len(context), 600)
        self.assertNotIn("~/.claude", context)

    def test_user_prompt_submit_outside_plan_mode_is_silent(self) -> None:
        self.assert_silent(run_hook(payload(
            hook_event_name="UserPromptSubmit", permission_mode="default"
        )))

    def test_enter_plan_mode_tool_emits_despite_stale_mode(self) -> None:
        result = run_hook(payload(
            hook_event_name="PostToolUse",
            tool_name="EnterPlanMode",
            permission_mode="default",
        ))
        specific = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(specific["hookEventName"], "PostToolUse")

    def test_post_tool_use_outside_plan_mode_is_silent(self) -> None:
        self.assert_silent(run_hook(payload(
            hook_event_name="PostToolUse", tool_name="Read", permission_mode="default"
        )))

    def test_post_tool_use_for_another_tool_is_silent_in_plan_mode(self) -> None:
        self.assert_silent(run_hook(payload(
            hook_event_name="PostToolUse", tool_name="Read", permission_mode="plan"
        )))

    def test_unregistered_event_is_silent_even_in_plan_mode(self) -> None:
        self.assert_silent(run_hook(payload(
            hook_event_name="Stop", permission_mode="plan"
        )))

    def test_malformed_input_is_silent(self) -> None:
        self.assert_silent(run_hook("not json{{{"))

    def test_empty_input_is_silent(self) -> None:
        self.assert_silent(run_hook(""))

    def test_non_object_json_is_silent(self) -> None:
        self.assert_silent(run_hook("[]"))


if __name__ == "__main__":
    unittest.main()
