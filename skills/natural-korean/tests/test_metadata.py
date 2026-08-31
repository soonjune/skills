"""Regression tests for product-specific natural-korean metadata."""

from pathlib import Path
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]


class OpenAiMetadataTests(unittest.TestCase):
    def test_codex_requires_explicit_invocation(self) -> None:
        metadata = SKILL_ROOT / "agents" / "openai.yaml"

        self.assertEqual(
            metadata.read_text(encoding="utf-8"),
            "interface:\n"
            '  display_name: "Natural Korean"\n'
            '  short_description: "한국어 문서와 Codex 대화 서술을 자연스럽게 다듬습니다."\n'
            '  default_prompt: "Use $natural-korean to polish this Korean document while preserving its meaning."\n'
            "policy:\n"
            "  allow_implicit_invocation: false\n",
        )


if __name__ == "__main__":
    unittest.main()
