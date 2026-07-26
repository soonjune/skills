#!/usr/bin/env python3
"""Check Korean deliverables against natural-korean's machine-readable rules.

The checker uses only the Python standard library.  It reports style patterns;
it does not attempt to determine who wrote a document.

Exit codes:
  0  no blocking/review finding (advisories may have been reported)
  1  at least one block/review threshold was met, or fixture regression failed
  2  invalid arguments, input, rules, or fixtures
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence


SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_RULES_PATH = SKILL_DIR / "references" / "rules.json"
DEFAULT_FIXTURES_PATH = SKILL_DIR / "references" / "fixtures.json"
LOCAL_RULES_NAME = "rules.local.json"

RULE_FIELDS = {
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
}
LEVELS = {"block", "review", "advisory"}
GENRES = {"all", "ppt", "report", "email", "code"}
SCOPES = {"document", "paragraph", "line", "document-start"}
RULE_ID_RE = re.compile(r"(?:R-[0-9]{2,}|LOCAL-[0-9]{4})\Z")

RULE_TOP_LEVEL_FIELDS = {"schema_version", "schema", "rules"}
RULE_SCHEMA_FIELDS = {"description", "rule_fields", "semantics"}
RULE_SEMANTIC_FIELDS = {
    "genre_gating",
    "scope",
    "threshold",
    "exit_status",
    "masking",
}
FIXTURE_TOP_LEVEL_FIELDS = {"schema_version", "schema", "fixtures"}
FIXTURE_SCHEMA_FIELDS = {"description", "fixture_fields", "semantics"}
FIXTURE_FIELDS = {
    "id",
    "text",
    "genre",
    "expected_rule_ids",
    "expected_exit",
}


class ConfigError(ValueError):
    """Raised for malformed rules or fixtures."""


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ConfigError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _read_json(path: Path) -> Any:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    try:
        return json.loads(raw, object_pairs_hook=_json_object)
    except ConfigError:
        raise
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"invalid JSON in {path}:{exc.lineno}:{exc.colno}: {exc.msg}"
        ) from exc


def _expect_exact_fields(
    value: dict[str, Any],
    expected: set[str],
    where: str,
    *,
    optional: set[str] | None = None,
) -> None:
    optional = optional or set()
    keys = set(value)
    unknown = sorted(keys - expected - optional)
    missing = sorted(expected - keys)
    if unknown:
        raise ConfigError(f"{where}: unknown field(s): {', '.join(unknown)}")
    if missing:
        raise ConfigError(f"{where}: missing field(s): {', '.join(missing)}")


def _expect_nonempty_string(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{where}: expected a non-empty string")
    return value


def _validate_documented_schema(schema: Any, where: str) -> None:
    if not isinstance(schema, dict):
        raise ConfigError(f"{where}: expected an object")
    _expect_exact_fields(schema, RULE_SCHEMA_FIELDS, where)
    _expect_nonempty_string(schema["description"], f"{where}.description")

    field_docs = schema["rule_fields"]
    if not isinstance(field_docs, dict):
        raise ConfigError(f"{where}.rule_fields: expected an object")
    _expect_exact_fields(field_docs, RULE_FIELDS, f"{where}.rule_fields")
    for name, doc in field_docs.items():
        _expect_nonempty_string(doc, f"{where}.rule_fields.{name}")

    semantics = schema["semantics"]
    if not isinstance(semantics, dict):
        raise ConfigError(f"{where}.semantics: expected an object")
    _expect_exact_fields(semantics, RULE_SEMANTIC_FIELDS, f"{where}.semantics")
    for name, doc in semantics.items():
        _expect_nonempty_string(doc, f"{where}.semantics.{name}")


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    level: str
    genres: tuple[str, ...]
    scope: str
    min_hits: int
    pattern: str
    message: str
    suggestion: str
    source: str
    regex: re.Pattern[str] = field(compare=False, repr=False)

    def applies_to(self, genre: str | None) -> bool:
        if genre is None:
            return "all" in self.genres
        return "all" in self.genres or genre in self.genres


def _parse_rule(value: Any, where: str) -> Rule:
    if not isinstance(value, dict):
        raise ConfigError(f"{where}: expected an object")
    _expect_exact_fields(value, RULE_FIELDS, where)

    rule_id = _expect_nonempty_string(value["id"], f"{where}.id")
    if RULE_ID_RE.fullmatch(rule_id) is None:
        raise ConfigError(
            f"{where}.id: expected R-NN... or LOCAL-NNNN, got {rule_id!r}"
        )
    title = _expect_nonempty_string(value["title"], f"{where}.title")
    level = _expect_nonempty_string(value["level"], f"{where}.level")
    if level not in LEVELS:
        raise ConfigError(
            f"{where}.level: expected one of {sorted(LEVELS)}, got {level!r}"
        )

    raw_genres = value["genres"]
    if not isinstance(raw_genres, list) or not raw_genres:
        raise ConfigError(f"{where}.genres: expected a non-empty array")
    if any(not isinstance(item, str) for item in raw_genres):
        raise ConfigError(f"{where}.genres: every genre must be a string")
    if len(set(raw_genres)) != len(raw_genres):
        raise ConfigError(f"{where}.genres: duplicate genre")
    invalid_genres = sorted(set(raw_genres) - GENRES)
    if invalid_genres:
        raise ConfigError(
            f"{where}.genres: unknown genre(s): {', '.join(invalid_genres)}"
        )
    if "all" in raw_genres and len(raw_genres) != 1:
        raise ConfigError(f"{where}.genres: 'all' cannot be combined with a genre")

    scope = _expect_nonempty_string(value["scope"], f"{where}.scope")
    if scope not in SCOPES:
        raise ConfigError(
            f"{where}.scope: expected one of {sorted(SCOPES)}, got {scope!r}"
        )

    min_hits = value["min_hits"]
    if isinstance(min_hits, bool) or not isinstance(min_hits, int) or min_hits < 1:
        raise ConfigError(f"{where}.min_hits: expected a positive integer")

    pattern = _expect_nonempty_string(value["pattern"], f"{where}.pattern")
    try:
        regex = re.compile(pattern)
    except re.error as exc:
        raise ConfigError(f"{where}.pattern: invalid regular expression: {exc}") from exc
    if regex.search("") is not None:
        raise ConfigError(f"{where}.pattern: pattern must not match an empty string")

    return Rule(
        id=rule_id,
        title=title,
        level=level,
        genres=tuple(raw_genres),
        scope=scope,
        min_hits=min_hits,
        pattern=pattern,
        message=_expect_nonempty_string(value["message"], f"{where}.message"),
        suggestion=_expect_nonempty_string(
            value["suggestion"], f"{where}.suggestion"
        ),
        source=_expect_nonempty_string(value["source"], f"{where}.source"),
        regex=regex,
    )


def load_rules(path: Path, *, require_schema: bool = True) -> list[Rule]:
    data = _read_json(path)
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be an object")
    if require_schema:
        _expect_exact_fields(data, RULE_TOP_LEVEL_FIELDS, str(path))
    else:
        _expect_exact_fields(
            data,
            {"schema_version", "rules"},
            str(path),
            optional={"schema"},
        )
    if data["schema_version"] != 1:
        raise ConfigError(f"{path}.schema_version: expected 1")
    if "schema" in data:
        _validate_documented_schema(data["schema"], f"{path}.schema")

    values = data["rules"]
    if not isinstance(values, list):
        raise ConfigError(f"{path}.rules: expected an array")
    rules = [_parse_rule(item, f"{path}.rules[{index}]") for index, item in enumerate(values)]
    seen: set[str] = set()
    for rule in rules:
        if rule.id in seen:
            raise ConfigError(f"{path}: duplicate rule id: {rule.id}")
        seen.add(rule.id)
    return rules


def merge_rules(base: Sequence[Rule], local: Sequence[Rule]) -> list[Rule]:
    merged = list(base)
    ids = {rule.id for rule in base}
    for rule in local:
        if rule.id in ids:
            raise ConfigError(f"duplicate rule id across rule files: {rule.id}")
        ids.add(rule.id)
        merged.append(rule)
    return merged


def _mask_range(buffer: list[str], start: int, end: int) -> None:
    for index in range(start, end):
        if buffer[index] not in "\r\n":
            buffer[index] = " "


_FENCE_LINE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})(.*?)(?:\r?\n)?$")
_BLOCKQUOTE_RE = re.compile(r"^[ \t]{0,3}>")


def _mask_fenced_code(text: str, buffer: list[str]) -> None:
    offset = 0
    fence_char: str | None = None
    fence_size = 0
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        match = _FENCE_LINE_RE.match(content)
        if fence_char is None:
            if match:
                token = match.group(1)
                fence_char, fence_size = token[0], len(token)
                _mask_range(buffer, offset, offset + len(line))
        else:
            _mask_range(buffer, offset, offset + len(line))
            if match:
                token = match.group(1)
                tail = match.group(2)
                if (
                    token[0] == fence_char
                    and len(token) >= fence_size
                    and not tail.strip()
                ):
                    fence_char, fence_size = None, 0
        offset += len(line)
    if offset < len(text):
        # splitlines() only misses an empty input; retained for defensive parity.
        _mask_range(buffer, offset, len(text))


def _mask_blockquotes(text: str, buffer: list[str]) -> None:
    offset = 0
    for line in text.splitlines(keepends=True):
        if _BLOCKQUOTE_RE.match(line):
            _mask_range(buffer, offset, offset + len(line))
        offset += len(line)


def _mask_inline_code(text: str, buffer: list[str]) -> None:
    offset = 0
    for line in text.splitlines(keepends=True):
        line_end = offset + len(line)
        index = offset
        while index < line_end:
            if text[index] != "`" or buffer[index] != "`":
                index += 1
                continue
            run_end = index
            while run_end < line_end and text[run_end] == "`":
                run_end += 1
            token = text[index:run_end]
            close = text.find(token, run_end, line_end)
            if close < 0:
                index = run_end
                continue
            # A closing run must have the same length, not be part of a longer run.
            if close + len(token) < line_end and text[close + len(token)] == "`":
                index = run_end
                continue
            _mask_range(buffer, index, close + len(token))
            index = close + len(token)
        offset = line_end


_QUOTE_PAIRS = {
    '"': '"',
    "'": "'",
    "“": "”",
    "‘": "’",
    "「": "」",
    "『": "』",
}


def _mask_quotes(text: str, buffer: list[str]) -> None:
    index = 0
    while index < len(text):
        opener = text[index]
        closer = _QUOTE_PAIRS.get(opener)
        if closer is None or buffer[index] != opener:
            index += 1
            continue
        if (
            opener == "'"
            and index > 0
            and index + 1 < len(text)
            and text[index - 1].isalnum()
            and text[index + 1].isalnum()
        ):
            index += 1
            continue
        cursor = index + 1
        found = -1
        while cursor < len(text) and text[cursor] not in "\r\n":
            if text[cursor] == "\\":
                cursor += 2
                continue
            if text[cursor] == closer and buffer[cursor] == closer:
                found = cursor
                break
            cursor += 1
        if found < 0:
            index += 1
            continue
        _mask_range(buffer, index, found + 1)
        index = found + 1


def mask_excluded(
    text: str,
    *,
    include_code: bool = False,
    include_quotes: bool = False,
    include_blockquotes: bool = False,
) -> str:
    """Replace excluded spans with spaces while preserving offsets and newlines."""

    buffer = list(text)
    if not include_code:
        _mask_fenced_code(text, buffer)
        _mask_inline_code(text, buffer)
    if not include_blockquotes:
        _mask_blockquotes(text, buffer)
    if not include_quotes:
        _mask_quotes(text, buffer)
    return "".join(buffer)


@dataclass(frozen=True)
class Finding:
    rule: Rule
    line: int
    column: int
    matched: str
    offset: int


@dataclass(frozen=True)
class CheckResult:
    findings: tuple[Finding, ...]

    @property
    def rule_ids(self) -> tuple[str, ...]:
        return tuple(sorted({finding.rule.id for finding in self.findings}))

    @property
    def exit_code(self) -> int:
        return int(
            any(finding.rule.level in {"block", "review"} for finding in self.findings)
        )


def _iter_scope_units(text: str, scope: str) -> Iterable[tuple[int, str]]:
    if scope == "document":
        yield 0, text
        return
    if scope == "document-start":
        first_visible = next(
            (index for index, char in enumerate(text) if not char.isspace()), None
        )
        if first_visible is not None:
            yield first_visible, text[first_visible:]
        return
    if scope == "line":
        offset = 0
        for line in text.splitlines(keepends=True):
            yield offset, line
            offset += len(line)
        if not text or (text and text[-1] in "\r\n"):
            return
        return
    if scope == "paragraph":
        offset = 0
        paragraph_start: int | None = None
        paragraph_parts: list[str] = []
        for line in text.splitlines(keepends=True):
            if line.strip():
                if paragraph_start is None:
                    paragraph_start = offset
                paragraph_parts.append(line)
            elif paragraph_start is not None:
                yield paragraph_start, "".join(paragraph_parts)
                paragraph_start, paragraph_parts = None, []
            offset += len(line)
        if paragraph_start is not None:
            yield paragraph_start, "".join(paragraph_parts)
        return
    raise AssertionError(f"unhandled scope: {scope}")


def check_text(
    text: str,
    rules: Sequence[Rule],
    *,
    genre: str | None = None,
    include_code: bool = False,
    include_quotes: bool = False,
    include_blockquotes: bool = False,
) -> CheckResult:
    if genre is not None and genre not in GENRES - {"all"}:
        raise ConfigError(f"unknown genre: {genre!r}")
    masked = mask_excluded(
        text,
        include_code=include_code,
        include_quotes=include_quotes,
        include_blockquotes=include_blockquotes,
    )
    findings: list[Finding] = []
    for rule in rules:
        if not rule.applies_to(genre):
            continue
        for unit_offset, unit in _iter_scope_units(masked, rule.scope):
            if rule.scope == "document-start":
                first = rule.regex.match(unit)
                matches = [first] if first is not None else []
            else:
                matches = list(rule.regex.finditer(unit))
            if len(matches) < rule.min_hits:
                continue
            for match in matches:
                absolute = unit_offset + match.start()
                line_start = text.rfind("\n", 0, absolute) + 1
                findings.append(
                    Finding(
                        rule=rule,
                        line=text.count("\n", 0, absolute) + 1,
                        column=absolute - line_start + 1,
                        matched=text[absolute : unit_offset + match.end()],
                        offset=absolute,
                    )
                )
    findings.sort(key=lambda finding: (finding.offset, finding.rule.id))
    return CheckResult(tuple(findings))


def _validate_fixture_schema(schema: Any, where: str) -> None:
    if not isinstance(schema, dict):
        raise ConfigError(f"{where}: expected an object")
    _expect_exact_fields(schema, FIXTURE_SCHEMA_FIELDS, where)
    _expect_nonempty_string(schema["description"], f"{where}.description")
    field_docs = schema["fixture_fields"]
    if not isinstance(field_docs, dict):
        raise ConfigError(f"{where}.fixture_fields: expected an object")
    _expect_exact_fields(field_docs, FIXTURE_FIELDS, f"{where}.fixture_fields")
    for name, doc in field_docs.items():
        _expect_nonempty_string(doc, f"{where}.fixture_fields.{name}")
    _expect_nonempty_string(schema["semantics"], f"{where}.semantics")


@dataclass(frozen=True)
class Fixture:
    id: str
    text: str
    genre: str | None
    expected_rule_ids: tuple[str, ...]
    expected_exit: int


def load_fixtures(path: Path, rules: Sequence[Rule]) -> list[Fixture]:
    data = _read_json(path)
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be an object")
    _expect_exact_fields(data, FIXTURE_TOP_LEVEL_FIELDS, str(path))
    if data["schema_version"] != 1:
        raise ConfigError(f"{path}.schema_version: expected 1")
    _validate_fixture_schema(data["schema"], f"{path}.schema")
    values = data["fixtures"]
    if not isinstance(values, list) or not values:
        raise ConfigError(f"{path}.fixtures: expected a non-empty array")

    known_rules = {rule.id for rule in rules}
    seen_ids: set[str] = set()
    covered: set[str] = set()
    fixtures: list[Fixture] = []
    for index, value in enumerate(values):
        where = f"{path}.fixtures[{index}]"
        if not isinstance(value, dict):
            raise ConfigError(f"{where}: expected an object")
        _expect_exact_fields(value, FIXTURE_FIELDS, where)
        fixture_id = _expect_nonempty_string(value["id"], f"{where}.id")
        if fixture_id in seen_ids:
            raise ConfigError(f"{path}: duplicate fixture id: {fixture_id}")
        seen_ids.add(fixture_id)
        text = value["text"]
        if not isinstance(text, str):
            raise ConfigError(f"{where}.text: expected a string")
        genre = value["genre"]
        if genre is not None and not isinstance(genre, str):
            raise ConfigError(f"{where}.genre: expected a string or null")
        if genre is not None and genre not in GENRES - {"all"}:
            raise ConfigError(f"{where}.genre: unknown genre {genre!r}")
        expected_ids = value["expected_rule_ids"]
        if not isinstance(expected_ids, list) or any(
            not isinstance(item, str) for item in expected_ids
        ):
            raise ConfigError(f"{where}.expected_rule_ids: expected an array of strings")
        if len(set(expected_ids)) != len(expected_ids):
            raise ConfigError(f"{where}.expected_rule_ids: duplicate rule id")
        unknown_rules = sorted(set(expected_ids) - known_rules)
        if unknown_rules:
            raise ConfigError(
                f"{where}.expected_rule_ids: unknown rule(s): {', '.join(unknown_rules)}"
            )
        expected_exit = value["expected_exit"]
        if isinstance(expected_exit, bool) or expected_exit not in (0, 1):
            raise ConfigError(f"{where}.expected_exit: expected 0 or 1")
        covered.update(expected_ids)
        fixtures.append(
            Fixture(
                id=fixture_id,
                text=text,
                genre=genre,
                expected_rule_ids=tuple(sorted(expected_ids)),
                expected_exit=expected_exit,
            )
        )

    missing_coverage = sorted(known_rules - covered)
    if missing_coverage:
        raise ConfigError(
            f"{path}: fixture coverage missing for rule(s): "
            + ", ".join(missing_coverage)
        )
    return fixtures


def run_fixtures(fixtures: Sequence[Fixture], rules: Sequence[Rule]) -> int:
    failures = 0
    for fixture in fixtures:
        result = check_text(fixture.text, rules, genre=fixture.genre)
        actual_ids = result.rule_ids
        if actual_ids != fixture.expected_rule_ids or result.exit_code != fixture.expected_exit:
            failures += 1
            print(
                f"FAIL {fixture.id}: expected ids={list(fixture.expected_rule_ids)} "
                f"exit={fixture.expected_exit}; got ids={list(actual_ids)} "
                f"exit={result.exit_code}"
            )
    passed = len(fixtures) - failures
    print(f"fixtures: {passed} passed, {failures} failed")
    return int(failures > 0)


def _state_dir_from_args(value: str | None) -> Path | None:
    raw = value
    if not raw:
        raw = os.environ.get("NATURAL_KOREAN_DATA_DIR")
    if not raw:
        plugin_data = os.environ.get("CLAUDE_PLUGIN_DATA")
        if plugin_data:
            raw = str(Path(plugin_data).expanduser() / "natural-korean")
    if not raw:
        # Backward-compatible fallback for early development snapshots.
        raw = os.environ.get("NATURAL_KOREAN_STATE_DIR")
    if not raw:
        return None
    if any(char in raw for char in ("\x00", "\n", "\r")):
        raise ConfigError("local data directory contains invalid characters")
    return Path(raw).expanduser()


def _load_rule_set(rules_path: Path, state_dir: Path | None) -> list[Rule]:
    rules = load_rules(rules_path)
    if state_dir is None:
        return rules
    local_path = state_dir / LOCAL_RULES_NAME
    if not local_path.exists():
        return rules
    return merge_rules(rules, load_rules(local_path, require_schema=False))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="한국어 업무 산출물의 번역투·문체·지시문 경계를 점검합니다.",
        epilog="FILE을 생략하면 stdin을 읽습니다.",
    )
    parser.add_argument("file", nargs="?", help="검사할 UTF-8 파일")
    parser.add_argument("--genre", choices=sorted(GENRES - {"all"}))
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES_PATH)
    parser.add_argument(
        "--state-dir",
        help=(
            f"{LOCAL_RULES_NAME}을 읽을 상태 디렉터리 "
            "(기본값: NATURAL_KOREAN_DATA_DIR, 그다음 "
            "CLAUDE_PLUGIN_DATA/natural-korean)"
        ),
    )
    parser.add_argument(
        "--include-code",
        action="store_true",
        help="Markdown 펜스·인라인 코드도 검사",
    )
    parser.add_argument(
        "--include-quotes",
        action="store_true",
        help="직접 인용 부호 안도 검사",
    )
    parser.add_argument(
        "--include-blockquotes",
        action="store_true",
        help="Markdown 인용문도 검사",
    )
    parser.add_argument(
        "--fixtures",
        action="store_true",
        help="회귀 fixture를 실행",
    )
    parser.add_argument(
        "--fixtures-file",
        type=Path,
        default=DEFAULT_FIXTURES_PATH,
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.fixtures:
            if args.file is not None:
                parser.error("FILE cannot be used with --fixtures")
            incompatible = (
                args.genre is not None
                or args.state_dir is not None
                or args.include_code
                or args.include_quotes
                or args.include_blockquotes
            )
            if incompatible:
                parser.error(
                    "--fixtures cannot be combined with --genre, --state-dir, "
                    "or --include-*"
                )
            # Base fixtures intentionally cover the versioned base rule set only.
            # Local rules are validated during normal checks and by their learner.
            base_rules = load_rules(args.rules)
            fixtures = load_fixtures(args.fixtures_file, base_rules)
            return run_fixtures(fixtures, base_rules)

        if args.file is not None:
            input_path = Path(args.file)
            try:
                text = input_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise ConfigError(f"cannot read {input_path}: {exc}") from exc
            label = str(input_path)
        else:
            if sys.stdin.isatty():
                parser.error("FILE or stdin input is required")
            try:
                if hasattr(sys.stdin, "buffer"):
                    text = sys.stdin.buffer.read().decode("utf-8")
                else:
                    text = sys.stdin.read()
            except (OSError, UnicodeError) as exc:
                raise ConfigError(f"cannot read stdin as UTF-8: {exc}") from exc
            label = "stdin"

        state_dir = _state_dir_from_args(args.state_dir)
        rules = _load_rule_set(args.rules, state_dir)
        result = check_text(
            text,
            rules,
            genre=args.genre,
            include_code=args.include_code,
            include_quotes=args.include_quotes,
            include_blockquotes=args.include_blockquotes,
        )
        for finding in result.findings:
            matched = " ".join(finding.matched.split())
            print(
                f"{label}:{finding.line}:{finding.column} "
                f"[{finding.rule.id} {finding.rule.level}] {matched!r} — "
                f"{finding.rule.message} {finding.rule.suggestion}"
            )
        print(
            f"summary: {len(result.findings)} hit(s), "
            f"{len(result.rule_ids)} rule(s), exit {result.exit_code}"
        )
        return result.exit_code
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
