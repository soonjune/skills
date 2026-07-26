from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "learn.py"


def git(state: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(state), *args],
        check=True,
        capture_output=True,
        text=True,
    )


class LearnCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.state = Path(self.temporary.name) / "natural-korean-state"

    def run_cli(
        self,
        *args: str,
        state: Path | None = None,
        check: bool = True,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(SCRIPT),
            "--data-dir",
            str(state or self.state),
            *args,
        ]
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        if check and result.returncode != 0:
            self.fail(
                f"command failed ({result.returncode}): {' '.join(command)}\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        return result

    def init(self) -> None:
        self.run_cli("init")

    def load(self, name: str) -> dict:
        return json.loads((self.state / name).read_text(encoding="utf-8"))

    def commit_count(self) -> int:
        return int(git(self.state, "rev-list", "--count", "HEAD").stdout.strip())

    def assert_owner_only_tree(self, root: Path) -> None:
        for directory, directories, files in os.walk(root, followlinks=False):
            for name in [".", *directories, *files]:
                path = Path(directory) if name == "." else Path(directory) / name
                mode = stat.S_IMODE(path.lstat().st_mode)
                self.assertEqual(
                    0,
                    mode & 0o077,
                    f"group/other permission on {path}: {mode:04o}",
                )

    def test_init_creates_dedicated_repo_without_remote(self) -> None:
        result = self.run_cli("init")
        self.assertIn("initialized", result.stdout)
        self.assertTrue((self.state / ".git").is_dir())
        self.assertEqual("", git(self.state, "remote").stdout)
        self.assertEqual(1, self.commit_count())
        self.assertEqual(
            "Natural Korean Local",
            git(self.state, "config", "--local", "user.name").stdout.strip(),
        )
        self.assertEqual(
            "natural-korean@localhost.invalid",
            git(self.state, "config", "--local", "user.email").stdout.strip(),
        )
        self.assertEqual(
            {"schema_version": 1, "preferences": [], "candidates": []},
            self.load("profile.json"),
        )
        self.assertEqual(0o700, stat.S_IMODE(self.state.stat().st_mode))
        for name in ("profile.json", "rules.local.json", "reviews.json"):
            self.assertEqual(0o600, stat.S_IMODE((self.state / name).stat().st_mode))
        self.assert_owner_only_tree(self.state / ".git")

    @unittest.skipUnless(os.name == "posix", "POSIX permission contract")
    def test_git_and_state_ignore_a_permissive_caller_umask(self) -> None:
        previous_umask = os.umask(0)
        try:
            self.init()
            self.run_cli(
                "record",
                "--preference",
                "보고서 제목은 짧은 명사형 사용",
                "--source",
                "explicit",
                "--durable",
            )
        finally:
            os.umask(previous_umask)
        self.assertEqual(0o700, stat.S_IMODE(self.state.stat().st_mode))
        self.assert_owner_only_tree(self.state)

    @unittest.skipUnless(os.name == "posix", "POSIX permission contract")
    def test_existing_state_with_group_or_other_access_is_refused(self) -> None:
        self.init()
        os.chmod(self.state, 0o755)
        result = self.run_cli("status", check=False)
        self.assertEqual(1, result.returncode)
        self.assertIn("owner-only", result.stderr)

    def test_explicit_durable_preference_promotes_and_commits(self) -> None:
        self.init()
        self.run_cli(
            "record",
            "--preference",
            "보고서에서는 명사형 종결 사용",
            "--source",
            "explicit",
            "--durable",
            "--genre",
            "report",
            "--avoid",
            "입니다",
            "--prefer",
            "~함",
        )
        profile = self.load("profile.json")
        self.assertEqual([], profile["candidates"])
        self.assertEqual("LOCAL-0001", profile["preferences"][0]["id"])
        rules = self.load("rules.local.json")["rules"]
        self.assertEqual(1, len(rules))
        self.assertEqual(re.escape("입니다"), rules[0]["pattern"])
        self.assertEqual(
            {
                "id",
                "title",
                "level",
                "genres",
                "scope",
                "min_hits",
                "pattern",
                "message",
                "suggestion",
                "source",
            },
            set(rules[0]),
        )
        checked = subprocess.run(
            [
                sys.executable,
                str(SKILL_DIR / "scripts" / "check.py"),
                "--state-dir",
                str(self.state),
                "--genre",
                "report",
            ],
            input="문장 끝입니다\n",
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(1, checked.returncode, checked.stderr)
        self.assertIn("LOCAL-0001", checked.stdout)
        self.assertEqual(2, self.commit_count())
        subject = git(self.state, "log", "-1", "--pretty=%s").stdout.strip()
        self.assertNotIn("명사형", subject)
        self.assertNotIn("입니다", subject)

    def test_new_preference_normalizes_all_genre_before_commit(self) -> None:
        self.init()
        self.run_cli(
            "record",
            "--preference",
            "보고서에서는 합니다체를 피함",
            "--source",
            "explicit",
            "--durable",
            "--genre",
            "all",
            "--genre",
            "report",
            "--avoid",
            "합니다",
        )
        profile = self.load("profile.json")
        self.assertEqual(["all"], profile["preferences"][0]["genres"])
        rules = self.load("rules.local.json")["rules"]
        self.assertEqual(["all"], rules[0]["genres"])

        checked = subprocess.run(
            [
                sys.executable,
                str(SKILL_DIR / "scripts" / "check.py"),
                "--state-dir",
                str(self.state),
                "--genre",
                "report",
            ],
            input="검토합니다\n",
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(1, checked.returncode, checked.stderr)
        self.assertIn("LOCAL-0001", checked.stdout)

    def test_observation_requires_distinct_confirmation_to_promote(self) -> None:
        self.init()
        base = (
            "record",
            "--preference",
            "슬라이드에서는 주어 생략",
            "--source",
            "observed",
            "--genre",
            "ppt",
            "--avoid",
            "우리는",
        )
        self.run_cli(*base)
        first = self.load("profile.json")
        self.assertEqual(1, len(first["candidates"]))
        self.assertEqual([], first["preferences"])
        unchanged = self.run_cli(*base)
        self.assertIn("unchanged", unchanged.stdout)
        self.assertEqual(2, self.commit_count())

        self.run_cli(*base, "--separate-context")
        second = self.load("profile.json")
        self.assertEqual([], second["candidates"])
        self.assertEqual(2, second["preferences"][0]["confirmations"])
        self.assertEqual(3, self.commit_count())

    def test_repeated_durable_preference_is_idempotent(self) -> None:
        self.init()
        command = (
            "record",
            "--preference",
            "이메일 인사말은 짧게 작성",
            "--source",
            "explicit",
            "--durable",
            "--genre",
            "email",
        )
        self.run_cli(*command)
        repeated = self.run_cli(*command)
        self.assertIn("unchanged", repeated.stdout)
        self.assertEqual(2, self.commit_count())

    def test_refuses_state_inside_public_checkout(self) -> None:
        forbidden = SKILL_DIR / "_must-not-create-local-state"
        self.assertFalse(forbidden.exists())
        result = self.run_cli("init", state=forbidden, check=False)
        self.assertEqual(2, result.returncode)
        self.assertIn("public skill repository", result.stderr)
        self.assertFalse(forbidden.exists())

    def test_refuses_state_inside_another_git_repository(self) -> None:
        outer = Path(self.temporary.name) / "outer"
        outer.mkdir()
        git(outer, "init", "--quiet")
        nested = outer / "natural-korean-state"
        result = self.run_cli("init", state=nested, check=False)
        self.assertEqual(2, result.returncode)
        self.assertIn("inside another Git repository", result.stderr)
        self.assertFalse(nested.exists())

    def test_refuses_state_nested_inside_a_bare_git_repository(self) -> None:
        bare = Path(self.temporary.name) / "archive.git"
        subprocess.run(
            ["git", "init", "--bare", "--quiet", str(bare)],
            check=True,
            capture_output=True,
            text=True,
        )
        nested = bare / "natural-korean-state"
        result = self.run_cli("init", state=nested, check=False)
        self.assertEqual(2, result.returncode)
        self.assertIn("inside another Git repository", result.stderr)
        self.assertFalse(nested.exists())

    def test_refuses_symlinked_git_directory(self) -> None:
        self.init()
        external_git = Path(self.temporary.name) / "external-git-dir"
        (self.state / ".git").rename(external_git)
        (self.state / ".git").symlink_to(external_git, target_is_directory=True)
        result = self.run_cli("status", check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn(".git", result.stderr)

    def test_refuses_git_directory_resolved_outside_state(self) -> None:
        separate_state = Path(self.temporary.name) / "separate-state"
        separate_state.mkdir(mode=0o700)
        os.chmod(separate_state, 0o700)
        external_git = Path(self.temporary.name) / "separate-metadata"
        subprocess.run(
            [
                "git",
                "init",
                "--quiet",
                f"--separate-git-dir={external_git}",
                str(separate_state),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        result = self.run_cli("init", state=separate_state, check=False)
        self.assertEqual(1, result.returncode)
        self.assertIn(".git directory", result.stderr)

    def test_dirty_state_and_remote_block_mutations(self) -> None:
        self.init()
        (self.state / "untracked.txt").write_text("dirty", encoding="utf-8")
        result = self.run_cli(
            "record",
            "--preference",
            "이메일 인사말은 짧게 작성",
            "--source",
            "explicit",
            "--durable",
            check=False,
        )
        self.assertEqual(1, result.returncode)
        self.assertIn("dirty", result.stderr)
        (self.state / "untracked.txt").unlink()
        git(self.state, "remote", "add", "origin", "https://example.invalid/local.git")
        result = self.run_cli(
            "review",
            "--human-reviewed",
            "--genre",
            "email",
            "--chars",
            "20",
            "--corrections",
            "0",
            "--false-positives",
            "0",
            check=False,
        )
        self.assertEqual(1, result.returncode)
        self.assertIn("must not have remotes", result.stderr)
        self.assertEqual(1, self.commit_count())

    def test_review_aggregates_only_human_reviewed_artifacts(self) -> None:
        self.init()
        unreviewed = self.run_cli(
            "review",
            "--genre",
            "report",
            "--chars",
            "100",
            "--corrections",
            "0",
            "--false-positives",
            "0",
            check=False,
        )
        self.assertNotEqual(0, unreviewed.returncode)
        self.assertEqual(1, self.commit_count())

        self.run_cli(
            "review",
            "--human-reviewed",
            "--genre",
            "report",
            "--chars",
            "100",
            "--corrections",
            "2",
            "--false-positives",
            "1",
        )
        self.run_cli(
            "review",
            "--human-reviewed",
            "--genre",
            "ppt",
            "--chars",
            "40",
            "--corrections",
            "0",
            "--false-positives",
            "2",
        )
        reviews = self.load("reviews.json")
        self.assertEqual(
            {
                "artifacts": 2,
                "chars": 140,
                "corrections": 2,
                "false_positives": 3,
            },
            reviews["totals"],
        )
        self.assertEqual(100, reviews["by_genre"]["report"]["chars"])
        self.assertEqual(1, reviews["by_genre"]["ppt"]["artifacts"])
        self.assertEqual(3, self.commit_count())
        status = self.run_cli("status", "--json")
        payload = json.loads(status.stdout)
        self.assertEqual(
            14.286,
            payload["review_rates"]["corrections_per_1000_chars"],
        )
        self.assertEqual(
            1.5,
            payload["review_rates"]["false_positives_per_artifact"],
        )
        self.assertIn("report", payload["reviews_by_genre"])

    def test_sensitive_text_is_refused_without_mutation(self) -> None:
        self.init()
        values = (
            "https://example.com 규칙을 사용",
            "담당자 user@example.com 표현 회피",
            "/Users/person/project 경로 언급 금지",
            "서버 192.168.0.10 표현 회피",
            "식별자 550e8400-e29b-41d4-a716-446655440000 제거",
            "고객 번호 123456789012 제거",
            "DOC-12345 표현 제거",
            "보고서에 적힌 수치 42를 그대로 사용",
            "가온전자 관련 표현은 일반화",
            "가온전자 매출 7조원 표현은 피함",
            "Example Bank 관련 표현은 일반화",
            "첫 줄\n둘째 줄",
        )
        for value in values:
            with self.subTest(value=value):
                result = self.run_cli(
                    "record",
                    "--preference",
                    value,
                    "--source",
                    "explicit",
                    "--durable",
                    check=False,
                )
                self.assertEqual(1, result.returncode)
        self.assertEqual(1, self.commit_count())
        self.assertEqual([], self.load("profile.json")["preferences"])

    def test_revert_uses_an_inverse_commit_and_restores_state(self) -> None:
        self.init()
        self.run_cli(
            "record",
            "--preference",
            "코드 주석은 짧은 평서문 사용",
            "--source",
            "explicit",
            "--durable",
            "--genre",
            "code",
        )
        learned = git(self.state, "rev-parse", "HEAD").stdout.strip()
        self.assertEqual(2, self.commit_count())
        result = self.run_cli("revert", learned)
        self.assertIn("reverted", result.stdout)
        self.assertEqual(3, self.commit_count())
        self.assertEqual([], self.load("profile.json")["preferences"])
        log = git(self.state, "log", "--pretty=%H").stdout.splitlines()
        self.assertIn(learned, log)
        self.assertTrue(
            git(self.state, "log", "-1", "--pretty=%s").stdout.startswith("Revert ")
        )

    def test_environment_resolution_precedence_and_missing_config(self) -> None:
        environment = os.environ.copy()
        environment.pop("NATURAL_KOREAN_DATA_DIR", None)
        environment.pop("CLAUDE_PLUGIN_DATA", None)
        missing = subprocess.run(
            [sys.executable, str(SCRIPT), "init"],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        self.assertEqual(2, missing.returncode)
        self.assertIn("NATURAL_KOREAN_DATA_DIR", missing.stderr)

        environment["CLAUDE_PLUGIN_DATA"] = str(Path(self.temporary.name) / "plugin")
        environment["NATURAL_KOREAN_DATA_DIR"] = str(
            Path(self.temporary.name) / "preferred"
        )
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "init"],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(
            (Path(environment["NATURAL_KOREAN_DATA_DIR"]) / ".git").is_dir()
        )
        self.assertFalse(
            (Path(environment["CLAUDE_PLUGIN_DATA"]) / "natural-korean").exists()
        )


if __name__ == "__main__":
    unittest.main()
