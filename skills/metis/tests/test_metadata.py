"""Regression tests for Metis skill and plugin metadata."""

import json
from pathlib import Path
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[1]


def quoted_value(text: str, key: str) -> str:
    prefix = f"  {key}: "
    line = next(line for line in text.splitlines() if line.startswith(prefix))
    value = line.removeprefix(prefix)
    if not (value.startswith('"') and value.endswith('"')):
        raise AssertionError(f"{key} must be a quoted string")
    return value[1:-1]


class OpenAiMetadataTests(unittest.TestCase):
    def test_codex_allows_implicit_invocation(self) -> None:
        metadata = SKILL_ROOT / "agents" / "openai.yaml"
        text = metadata.read_text(encoding="utf-8")

        self.assertIn("  allow_implicit_invocation: true\n", text)
        self.assertIn("$metis", quoted_value(text, "default_prompt"))
        short_description = quoted_value(text, "short_description")
        self.assertGreaterEqual(len(short_description), 25)
        self.assertLessEqual(len(short_description), 64)


class PluginMetadataTests(unittest.TestCase):
    def test_plugin_versions_and_codex_starters(self) -> None:
        claude = json.loads(
            (REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        codex = json.loads(
            (REPO_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )

        self.assertEqual(claude["version"], "1.2.0")
        self.assertEqual(codex["version"], "1.2.0")
        self.assertEqual(claude["hooks"], "./claude-hooks/metis.json")
        self.assertLessEqual(len(codex["interface"]["defaultPrompt"]), 3)
        self.assertFalse(any(
            prompt.startswith("$metis")
            for prompt in codex["interface"]["defaultPrompt"]
        ))

    def test_claude_hook_registration(self) -> None:
        config = json.loads(
            (REPO_ROOT / "claude-hooks" / "metis.json").read_text(encoding="utf-8")
        )["hooks"]

        self.assertEqual(set(config), {"UserPromptSubmit", "PostToolUse"})
        self.assertNotIn("matcher", config["UserPromptSubmit"][0])
        self.assertEqual(config["PostToolUse"][0]["matcher"], "EnterPlanMode")
        for event in config.values():
            handler = event[0]["hooks"][0]
            self.assertEqual(handler["type"], "command")
            self.assertEqual(handler["command"], "python3")
            self.assertEqual(
                handler["args"],
                ["${CLAUDE_PLUGIN_ROOT}/skills/metis/scripts/metis_hook.py"],
            )


if __name__ == "__main__":
    unittest.main()
