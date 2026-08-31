"""Regression tests for evals/sync_style.py."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SYNC_PATH = ROOT / "evals" / "sync_style.py"
SPEC = importlib.util.spec_from_file_location("natural_korean_sync_style", SYNC_PATH)
assert SPEC is not None and SPEC.loader is not None
sync_style = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sync_style
SPEC.loader.exec_module(sync_style)


class GeneratedCleanupTests(unittest.TestCase):
    def test_sync_removes_deleted_graders_and_orphan_styled_cases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            stale = destination / "narrate-work-styled" / "graders" / "deleted.md"
            stale.parent.mkdir(parents=True)
            stale.write_text("stale\n", encoding="utf-8")
            orphan = destination / "orphan-styled" / "graders" / "old.md"
            orphan.parent.mkdir(parents=True)
            orphan.write_text("stale\n", encoding="utf-8")

            written = sync_style.sync(destination)

            self.assertTrue(written)
            self.assertFalse(stale.exists())
            self.assertFalse((destination / "orphan-styled").exists())
            self.assertTrue(
                (destination / "narrate-work-styled" / "graders" / "style-compliance.md").is_file()
            )


if __name__ == "__main__":
    unittest.main()
