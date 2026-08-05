"""Regression tests for product-specific natural-korean metadata."""

from pathlib import Path
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]


class OpenAiMetadataTests(unittest.TestCase):
    def test_codex_requires_explicit_invocation(self) -> None:
        metadata = SKILL_ROOT / "agents" / "openai.yaml"

        self.assertEqual(
            metadata.read_text(encoding="utf-8"),
            "policy:\n  allow_implicit_invocation: false\n",
        )


if __name__ == "__main__":
    unittest.main()
