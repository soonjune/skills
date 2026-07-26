"""Regression tests for natural-korean/scripts/check.py."""

from __future__ import annotations

import copy
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
from unittest import mock


SKILL_DIR = Path(__file__).resolve().parents[1]
CHECK_PATH = SKILL_DIR / "scripts" / "check.py"
SPEC = importlib.util.spec_from_file_location("natural_korean_check", CHECK_PATH)
assert SPEC is not None and SPEC.loader is not None
check = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = check
SPEC.loader.exec_module(check)


def rule_value(**overrides):
    value = {
        "id": "LOCAL-0001",
        "title": "test rule",
        "level": "review",
        "genres": ["all"],
        "scope": "document",
        "min_hits": 1,
        "pattern": "나쁜표현",
        "message": "검토할 표현입니다.",
        "suggestion": "뜻을 유지해 다듬으세요.",
        "source": "test",
    }
    value.update(overrides)
    return value


def make_rule(**overrides):
    return check._parse_rule(rule_value(**overrides), "test.rule")


class TemporaryJsonMixin:
    def write_json(self, directory, name, value):
        path = Path(directory) / name
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path


class BaseRulesAndFixturesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = check.load_rules(check.DEFAULT_RULES_PATH)

    def test_base_rule_ids_are_unique(self):
        ids = [rule.id for rule in self.rules]
        self.assertEqual(len(ids), len(set(ids)))

    def test_versioned_fixtures_have_full_coverage_and_pass(self):
        fixtures = check.load_fixtures(check.DEFAULT_FIXTURES_PATH, self.rules)
        with redirect_stdout(io.StringIO()) as output:
            exit_code = check.run_fixtures(fixtures, self.rules)
        self.assertEqual(exit_code, 0)
        self.assertIn("0 failed", output.getvalue())

    def test_rejected_blanket_patterns_are_absent(self):
        patterns = "\n".join(rule.pattern for rule in self.rules)
        self.assertNotIn("지게 된다", patterns)
        self.assertNotIn("를 통해", patterns)
        self.assertNotIn("것이다", patterns)

    def test_unlicensed_plan_rules_are_not_present(self):
        ids = {rule.id for rule in self.rules}
        self.assertTrue(ids.isdisjoint({"R-11", "R-12", "R-13", "R-14", "R-15", "R-16"}))

    def test_source_and_messages_make_no_authorship_claim(self):
        for rule in self.rules:
            combined = " ".join((rule.title, rule.message, rule.suggestion))
            self.assertNotIn("AI가 쓴", combined)
            self.assertNotIn("AI 생성", combined)


class MaskingTests(unittest.TestCase):
    def setUp(self):
        self.rule = make_rule(pattern="되어지", level="block", scope="document")

    def assertNoHit(self, text):
        self.assertEqual(check.check_text(text, [self.rule]).rule_ids, ())

    def test_masks_backtick_fence(self):
        self.assertNoHit("```text\n시행되어지고 있다\n```\n본문")

    def test_masks_tilde_fence(self):
        self.assertNoHit("~~~~\n시행되어지고 있다\n~~~~\n본문")

    def test_masks_inline_code(self):
        self.assertNoHit("예시: ``시행되어지고 있다``")

    def test_masks_markdown_blockquote(self):
        self.assertNoHit("  > 시행되어지고 있다\n본문")

    def test_masks_straight_and_curly_direct_quotes(self):
        self.assertNoHit('"시행되어지고 있다"와 “보여지는 문장”')

    def test_masks_korean_quote_marks(self):
        self.assertNoHit("「시행되어지고 있다」와 『보여지는 문장』")

    def test_include_code_reenables_code_spans(self):
        result = check.check_text(
            "`시행되어지고 있다`", [self.rule], include_code=True
        )
        self.assertEqual(result.rule_ids, ("LOCAL-0001",))

    def test_include_quotes_reenables_direct_quotes(self):
        result = check.check_text(
            '"시행되어지고 있다"', [self.rule], include_quotes=True
        )
        self.assertEqual(result.rule_ids, ("LOCAL-0001",))

    def test_include_blockquotes_reenables_quote_lines(self):
        result = check.check_text(
            "> 시행되어지고 있다", [self.rule], include_blockquotes=True
        )
        self.assertEqual(result.rule_ids, ("LOCAL-0001",))

    def test_masking_preserves_line_and_column(self):
        result = check.check_text(
            '"시행되어지"\n정상\n  시행되어지고 있다', [self.rule]
        )
        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].line, 3)
        self.assertEqual(result.findings[0].column, 5)


class ScopeThresholdAndGenreTests(unittest.TestCase):
    def test_document_threshold_counts_across_lines(self):
        rule = make_rule(scope="document", min_hits=3, pattern="반복")
        self.assertEqual(
            check.check_text("반복\n반복\n반복", [rule]).rule_ids,
            ("LOCAL-0001",),
        )

    def test_paragraph_threshold_does_not_cross_blank_line(self):
        rule = make_rule(scope="paragraph", min_hits=3, pattern="반복")
        result = check.check_text("반복 반복\n\n반복 반복", [rule])
        self.assertEqual(result.rule_ids, ())

    def test_paragraph_threshold_reports_only_qualifying_paragraph(self):
        rule = make_rule(scope="paragraph", min_hits=2, pattern="반복")
        result = check.check_text("반복\n\n반복 반복", [rule])
        self.assertEqual(len(result.findings), 2)
        self.assertEqual({finding.line for finding in result.findings}, {3})

    def test_line_threshold_does_not_cross_lines(self):
        rule = make_rule(scope="line", min_hits=2, pattern="반복")
        result = check.check_text("반복\n반복", [rule])
        self.assertEqual(result.rule_ids, ())

    def test_document_start_matches_after_leading_blank_lines(self):
        rule = make_rule(scope="document-start", pattern="다음은")
        result = check.check_text("\n \n다음은 문서", [rule])
        self.assertEqual(result.rule_ids, ("LOCAL-0001",))

    def test_document_start_does_not_match_later_line(self):
        rule = make_rule(scope="document-start", pattern="다음은")
        result = check.check_text("제목\n다음은 문서", [rule])
        self.assertEqual(result.rule_ids, ())

    def test_document_start_pattern_is_not_reapplied_per_line(self):
        rules = check.load_rules(check.DEFAULT_RULES_PATH)
        result = check.check_text("제목\n다음은 설명입니다", rules)
        self.assertNotIn("R-37", result.rule_ids)

    def test_unspecified_genre_only_uses_all_rules(self):
        all_rule = make_rule(id="LOCAL-0001", genres=["all"])
        ppt_rule = make_rule(id="LOCAL-0002", genres=["ppt"])
        result = check.check_text("나쁜표현", [all_rule, ppt_rule])
        self.assertEqual(result.rule_ids, ("LOCAL-0001",))

    def test_selected_genre_uses_all_and_matching_rules(self):
        all_rule = make_rule(id="LOCAL-0001", genres=["all"])
        ppt_rule = make_rule(id="LOCAL-0002", genres=["ppt"])
        result = check.check_text("나쁜표현", [all_rule, ppt_rule], genre="ppt")
        self.assertEqual(result.rule_ids, ("LOCAL-0001", "LOCAL-0002"))

    def test_unknown_genre_is_rejected_by_library_api(self):
        with self.assertRaises(check.ConfigError):
            check.check_text("본문", [make_rule()], genre="memo")

    def test_advisory_reports_without_failing(self):
        rule = make_rule(level="advisory")
        result = check.check_text("나쁜표현", [rule])
        self.assertEqual(result.rule_ids, ("LOCAL-0001",))
        self.assertEqual(result.exit_code, 0)

    def test_review_and_block_both_fail(self):
        for level in ("review", "block"):
            with self.subTest(level=level):
                result = check.check_text(
                    "나쁜표현", [make_rule(level=level)]
                )
                self.assertEqual(result.exit_code, 1)


class StrictRuleSchemaTests(TemporaryJsonMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_data = json.loads(
            check.DEFAULT_RULES_PATH.read_text(encoding="utf-8")
        )

    def load_mutation(self, mutation):
        data = copy.deepcopy(self.base_data)
        mutation(data)
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_json(directory, "rules.json", data)
            return check.load_rules(path)

    def assertMutationInvalid(self, mutation, needle=None):
        with self.assertRaises(check.ConfigError) as caught:
            self.load_mutation(mutation)
        if needle:
            self.assertIn(needle, str(caught.exception))

    def test_unknown_top_level_field_is_rejected(self):
        self.assertMutationInvalid(
            lambda data: data.update({"extra": True}), "unknown field"
        )

    def test_unknown_rule_field_is_rejected(self):
        self.assertMutationInvalid(
            lambda data: data["rules"][0].update({"extra": True}), "unknown field"
        )

    def test_missing_rule_field_is_rejected(self):
        self.assertMutationInvalid(
            lambda data: data["rules"][0].pop("message"), "missing field"
        )

    def test_duplicate_rule_id_is_rejected(self):
        self.assertMutationInvalid(
            lambda data: data["rules"].append(copy.deepcopy(data["rules"][0])),
            "duplicate rule id",
        )

    def test_duplicate_json_key_is_rejected(self):
        raw = '{"schema_version":1,"schema_version":1,"rules":[]}'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules.json"
            path.write_text(raw, encoding="utf-8")
            with self.assertRaisesRegex(check.ConfigError, "duplicate JSON key"):
                check.load_rules(path)

    def test_invalid_regex_is_rejected(self):
        self.assertMutationInvalid(
            lambda data: data["rules"][0].update({"pattern": "("}),
            "invalid regular expression",
        )

    def test_empty_matching_regex_is_rejected(self):
        self.assertMutationInvalid(
            lambda data: data["rules"][0].update({"pattern": "x*"}),
            "must not match an empty string",
        )

    def test_invalid_id_level_scope_and_genre_are_rejected(self):
        cases = (
            ("id", "BAD-1"),
            ("level", "warn"),
            ("scope", "sentence"),
            ("genres", ["memo"]),
            ("genres", ["all", "ppt"]),
        )
        for field, value in cases:
            with self.subTest(field=field, value=value):
                self.assertMutationInvalid(
                    lambda data, f=field, v=value: data["rules"][0].update({f: v})
                )

    def test_duplicate_genre_and_boolean_min_hits_are_rejected(self):
        self.assertMutationInvalid(
            lambda data: data["rules"][0].update({"genres": ["ppt", "ppt"]}),
            "duplicate genre",
        )
        self.assertMutationInvalid(
            lambda data: data["rules"][0].update({"min_hits": True}),
            "positive integer",
        )

    def test_unknown_schema_documentation_field_is_rejected(self):
        self.assertMutationInvalid(
            lambda data: data["schema"].update({"extra": "not allowed"}),
            "unknown field",
        )

    def test_non_utf8_rule_file_is_a_config_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules.json"
            path.write_bytes(b"\xff")
            with self.assertRaisesRegex(check.ConfigError, "cannot read"):
                check.load_rules(path)


class LocalRulesTests(TemporaryJsonMixin, unittest.TestCase):
    def test_local_subset_loads_and_merges(self):
        with tempfile.TemporaryDirectory() as directory:
            local_path = self.write_json(
                directory,
                check.LOCAL_RULES_NAME,
                {"schema_version": 1, "rules": [rule_value()]},
            )
            local = check.load_rules(local_path, require_schema=False)
            base = check.load_rules(check.DEFAULT_RULES_PATH)
            merged = check.merge_rules(base, local)
            self.assertIn("LOCAL-0001", {rule.id for rule in merged})

    def test_local_unknown_top_level_field_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            local_path = self.write_json(
                directory,
                check.LOCAL_RULES_NAME,
                {"schema_version": 1, "rules": [], "extra": True},
            )
            with self.assertRaisesRegex(check.ConfigError, "unknown field"):
                check.load_rules(local_path, require_schema=False)

    def test_duplicate_id_across_files_is_rejected(self):
        duplicate = make_rule(id="R-01")
        with self.assertRaisesRegex(check.ConfigError, "across rule files"):
            check.merge_rules(
                check.load_rules(check.DEFAULT_RULES_PATH), [duplicate]
            )

    def test_canonical_data_dir_environment_variable(self):
        with tempfile.TemporaryDirectory() as directory:
            self.write_json(
                directory,
                check.LOCAL_RULES_NAME,
                {"schema_version": 1, "rules": [rule_value()]},
            )
            with mock.patch.dict(
                os.environ,
                {"NATURAL_KOREAN_DATA_DIR": directory},
                clear=True,
            ):
                state_dir = check._state_dir_from_args(None)
                rules = check._load_rule_set(check.DEFAULT_RULES_PATH, state_dir)
            self.assertIn("LOCAL-0001", {rule.id for rule in rules})

    def test_plugin_data_fallback_and_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            plugin_root = Path(directory) / "plugin-data"
            expected = plugin_root / "natural-korean"
            with mock.patch.dict(
                os.environ,
                {"CLAUDE_PLUGIN_DATA": str(plugin_root)},
                clear=True,
            ):
                self.assertEqual(check._state_dir_from_args(None), expected)
                self.assertEqual(
                    check._state_dir_from_args(str(Path(directory) / "explicit")),
                    Path(directory) / "explicit",
                )

            canonical = Path(directory) / "canonical"
            with mock.patch.dict(
                os.environ,
                {
                    "NATURAL_KOREAN_DATA_DIR": str(canonical),
                    "CLAUDE_PLUGIN_DATA": str(plugin_root),
                },
                clear=True,
            ):
                self.assertEqual(check._state_dir_from_args(None), canonical)


class StrictFixtureSchemaTests(TemporaryJsonMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_data = json.loads(
            check.DEFAULT_FIXTURES_PATH.read_text(encoding="utf-8")
        )
        cls.rules = check.load_rules(check.DEFAULT_RULES_PATH)

    def assertFixtureMutationInvalid(self, mutation, needle=None):
        data = copy.deepcopy(self.fixture_data)
        mutation(data)
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_json(directory, "fixtures.json", data)
            with self.assertRaises(check.ConfigError) as caught:
                check.load_fixtures(path, self.rules)
        if needle:
            self.assertIn(needle, str(caught.exception))

    def test_unknown_fixture_field_is_rejected(self):
        self.assertFixtureMutationInvalid(
            lambda data: data["fixtures"][0].update({"extra": True}),
            "unknown field",
        )

    def test_duplicate_fixture_id_is_rejected(self):
        self.assertFixtureMutationInvalid(
            lambda data: data["fixtures"].append(
                copy.deepcopy(data["fixtures"][0])
            ),
            "duplicate fixture id",
        )

    def test_unknown_expected_rule_is_rejected(self):
        self.assertFixtureMutationInvalid(
            lambda data: data["fixtures"][0].update(
                {"expected_rule_ids": ["R-9999"]}
            ),
            "unknown rule",
        )

    def test_missing_rule_coverage_is_rejected(self):
        self.assertFixtureMutationInvalid(
            lambda data: data.update(
                {
                    "fixtures": [
                        fixture
                        for fixture in data["fixtures"]
                        if "R-01" not in fixture["expected_rule_ids"]
                    ]
                }
            ),
            "coverage missing",
        )

    def test_boolean_expected_exit_is_rejected(self):
        self.assertFixtureMutationInvalid(
            lambda data: data["fixtures"][0].update({"expected_exit": True}),
            "expected 0 or 1",
        )

    def test_non_string_genre_is_a_config_error(self):
        self.assertFixtureMutationInvalid(
            lambda data: data["fixtures"][0].update({"genre": ["report"]}),
            "expected a string or null",
        )

    def test_runner_requires_exact_id_set_and_exit(self):
        rule = make_rule(level="block")
        fixture = check.Fixture(
            id="FX",
            text="나쁜표현",
            genre=None,
            expected_rule_ids=(),
            expected_exit=0,
        )
        with redirect_stdout(io.StringIO()) as output:
            exit_code = check.run_fixtures([fixture], [rule])
        self.assertEqual(exit_code, 1)
        self.assertIn("got ids=['LOCAL-0001'] exit=1", output.getvalue())


class CliTests(TemporaryJsonMixin, unittest.TestCase):
    def run_cli(self, args, *, stdin=""):
        return subprocess.run(
            [sys.executable, str(CHECK_PATH), *args],
            input=stdin,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def run_cli_bytes(self, args, *, stdin=b""):
        return subprocess.run(
            [sys.executable, str(CHECK_PATH), *args],
            input=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_stdin_block_finding_exits_one(self):
        result = self.run_cli([], stdin="절차가 시행되어지고 있다")
        self.assertEqual(result.returncode, 1)
        self.assertIn("[R-01 block]", result.stdout)

    def test_advisory_only_exits_zero(self):
        result = self.run_cli([], stdin="내용은 크게 세 가지로 나눌 수 있다")
        self.assertEqual(result.returncode, 0)
        self.assertIn("[R-20 advisory]", result.stdout)

    def test_fixture_cli_passes(self):
        result = self.run_cli(["--fixtures"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("0 failed", result.stdout)

    def test_fixture_cli_rejects_ignored_options(self):
        result = self.run_cli(["--fixtures", "--genre", "ppt"])
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot be combined", result.stderr)

    def test_invalid_utf8_input_exits_two(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.txt"
            path.write_bytes(b"\xff")
            result = subprocess.run(
                [sys.executable, str(CHECK_PATH), str(path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"error:", result.stderr)

    def test_invalid_utf8_stdin_exits_two_without_traceback(self):
        result = self.run_cli_bytes([], stdin=b"\xff")
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"error:", result.stderr)
        self.assertIn(b"stdin", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)

    def test_unhashable_fixture_genre_exits_two_without_traceback(self):
        data = json.loads(
            check.DEFAULT_FIXTURES_PATH.read_text(encoding="utf-8")
        )
        data["fixtures"][0]["genre"] = ["report"]
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_json(directory, "fixtures.json", data)
            result = self.run_cli_bytes(
                ["--fixtures", "--fixtures-file", str(path)]
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"expected a string or null", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
