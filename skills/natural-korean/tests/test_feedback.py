"""Regression tests for natural-korean/scripts/feedback.py."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
FEEDBACK_PATH = SKILL_DIR / "scripts" / "feedback.py"
SPEC = importlib.util.spec_from_file_location("natural_korean_feedback", FEEDBACK_PATH)
assert SPEC is not None and SPEC.loader is not None
feedback = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = feedback
SPEC.loader.exec_module(feedback)


class LegacyCompatibilityTests(unittest.TestCase):
    def test_legacy_jsonl_is_normalized_only_while_reading(self) -> None:
        original = '{"ts":"old","arm":"styled","asked":true}\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "exposures.jsonl"
            path.write_text(original, encoding="utf-8")

            rows = feedback.load(path)

            self.assertEqual(original, path.read_text(encoding="utf-8"))
            self.assertEqual(
                {
                    "ts": "old",
                    "agent": "claude",
                    "protocol": feedback.LEGACY_PROTOCOL,
                    "arm": "styled",
                    "ask_armed": True,
                },
                rows[0],
            )

    def test_legacy_feedback_does_not_become_blind_v2(self) -> None:
        row = feedback.normalize_record(
            {"ts": "old", "arm": "styled", "verdict": "up", "misread": False}
        )
        grouped = feedback.aggregate([row], [])

        self.assertEqual(1, grouped[("claude", feedback.LEGACY_PROTOCOL, "styled")]["feedback"])
        self.assertNotIn(("claude", feedback.CLAUDE_BLIND_V2, "styled"), grouped)


class ProtocolAggregationTests(unittest.TestCase):
    def test_codex_manual_and_legacy_rows_are_separate_from_adoption(self) -> None:
        exposures = [
            {
                "agent": "claude",
                "protocol": feedback.CLAUDE_BLIND_V2,
                "arm": "styled",
                "ask_armed": True,
            },
            {
                "agent": "claude",
                "protocol": feedback.CLAUDE_BLIND_V2,
                "arm": "plain",
                "ask_armed": False,
            },
            {
                "agent": "codex",
                "protocol": feedback.CODEX_EXPLICIT_V1,
                "arm": "styled",
                "ask_armed": False,
            },
        ]
        responses = [
            {
                "agent": "claude",
                "protocol": feedback.CLAUDE_BLIND_V2,
                "arm": "styled",
                "verdict": "up",
                "misread": False,
            },
            {
                "agent": "claude",
                "protocol": feedback.CLAUDE_MANUAL_V1,
                "arm": "styled",
                "verdict": "up",
                "misread": False,
            },
            {
                "agent": "codex",
                "protocol": feedback.CODEX_EXPLICIT_V1,
                "arm": "styled",
                "verdict": "down",
                "misread": True,
            },
        ]

        grouped = feedback.aggregate(responses, exposures)

        adoption = grouped[("claude", feedback.CLAUDE_BLIND_V2, "styled")]
        self.assertEqual(
            {"sessions": 1, "ask_armed": 1, "feedback": 1, "up": 1, "misread": 0},
            adoption,
        )
        self.assertEqual(
            1,
            grouped[("claude", feedback.CLAUDE_MANUAL_V1, "styled")]["feedback"],
        )
        self.assertEqual(
            1,
            grouped[("codex", feedback.CODEX_EXPLICIT_V1, "styled")]["feedback"],
        )

    def test_summary_labels_excluded_protocols(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / feedback.EXPOSURE_FILE).write_text(
                json.dumps(
                    {
                        "ts": "new",
                        "agent": "codex",
                        "protocol": feedback.CODEX_EXPLICIT_V1,
                        "arm": "styled",
                        "ask_armed": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with redirect_stdout(io.StringIO()) as output:
                feedback.summarize(root)

        rendered = output.getvalue()
        self.assertIn("adoption: agent=claude protocol=claude-blind-v2", rendered)
        self.assertIn("other records (excluded from adoption)", rendered)
        self.assertIn("agent=codex protocol=codex-explicit-v1", rendered)


class CliRecordingTests(unittest.TestCase):
    def run_cli(self, state: Path, *args: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["NK_AB_DATA_DIR"] = str(state)
        return subprocess.run(
            [sys.executable, str(FEEDBACK_PATH), *args],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )

    def test_new_exposure_writes_agent_protocol_and_ask_armed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            result = self.run_cli(
                state,
                "--agent",
                "codex",
                "--protocol",
                feedback.CODEX_EXPLICIT_V1,
                "--arm",
                "styled",
                "--log-exposure",
                "--ask-armed",
            )
            self.assertEqual(0, result.returncode, result.stderr)
            record = json.loads((state / feedback.EXPOSURE_FILE).read_text(encoding="utf-8"))

        self.assertEqual("codex", record["agent"])
        self.assertEqual(feedback.CODEX_EXPLICIT_V1, record["protocol"])
        self.assertIs(record["ask_armed"], True)
        self.assertNotIn("asked", record)

    def test_default_feedback_is_tagged_as_claude_manual(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            result = self.run_cli(state, "--arm", "plain", "--verdict", "down")
            self.assertEqual(0, result.returncode, result.stderr)
            record = json.loads((state / feedback.FEEDBACK_FILE).read_text(encoding="utf-8"))

        self.assertEqual("claude", record["agent"])
        self.assertEqual(feedback.CLAUDE_MANUAL_V1, record["protocol"])


if __name__ == "__main__":
    unittest.main()
