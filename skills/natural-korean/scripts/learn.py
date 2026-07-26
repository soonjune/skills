#!/usr/bin/env python3
"""Keep natural-korean preferences in a private, local, versioned state directory.

The public skill checkout contains code and baseline guidance only. This helper
stores abstract preferences and aggregate review metrics in a dedicated Git
repository selected by the caller.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Sequence


SCHEMA_VERSION = 1
PROFILE_FILE = "profile.json"
RULES_FILE = "rules.local.json"
REVIEWS_FILE = "reviews.json"
TRACKED_FILES = (PROFILE_FILE, RULES_FILE, REVIEWS_FILE)
RECORD_GENRES = ("all", "ppt", "report", "email", "code")
ARTIFACT_GENRES = ("ppt", "report", "email", "code")
SOURCES = ("explicit", "correction", "observed")
LOCAL_GIT_NAME = "Natural Korean Local"
LOCAL_GIT_EMAIL = "natural-korean@localhost.invalid"
LOCAL_ID_RE = re.compile(r"^LOCAL-(\d{4})$")
COMMIT_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")

URL_RE = re.compile(r"(?i)(?:\bhttps?://|\bwww\.)\S+")
EMAIL_RE = re.compile(
    r"(?i)(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])"
)
UUID_RE = re.compile(
    r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}\b"
)
IPV4_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
IPV6_TOKEN_RE = re.compile(r"(?<![0-9A-Fa-f:])[0-9A-Fa-f:]{3,}(?![0-9A-Fa-f:])")
POSIX_PATH_RE = re.compile(r"(?<![\w./])/(?:[^/\s]+/)*[^/\s]*")
WINDOWS_PATH_RE = re.compile(r"(?i)(?:\b[A-Z]:[\\/]|\\\\[^\\\s]+\\)")
LONG_NUMERIC_ID_RE = re.compile(r"(?<!\d)\d{8,}(?!\d)")
LABELED_ID_RE = re.compile(
    r"(?i)\b(?:doc(?:ument)?|ticket|issue|case)[\s:#_-]*[A-Z0-9_-]{3,}\b"
)
UPPER_ID_RE = re.compile(r"\b[A-Z]{2,12}[-_]\d{3,}\b")
DIGIT_RE = re.compile(r"\d")
KOREAN_LEGAL_ORG_RE = re.compile(
    r"(?:주식회사|유한회사|사단법인|재단법인|\([주株]\))"
)
KOREAN_ORG_SUFFIX_RE = re.compile(
    r"(?<![가-힣A-Za-z0-9])"
    r"[가-힣A-Za-z][가-힣A-Za-z0-9·&.-]{1,30}"
    r"(?:전자|그룹|은행|증권|보험|카드|텔레콤|모빌리티|솔루션즈?|테크|"
    r"대학교|연구원|재단|협회|공사|공단|본부|센터|사업부)"
    r"(?![가-힣A-Za-z0-9])"
)
ENGLISH_ORG_RE = re.compile(
    r"\b(?:[A-Z][A-Za-z0-9&.-]*\s+){1,4}"
    r"(?:Inc|Corp|Corporation|Company|Co|Ltd|LLC|Group|Bank|"
    r"University|Foundation)\.?\b"
)

SCRIPT_PATH = Path(__file__).resolve()
SKILL_DIR = SCRIPT_PATH.parents[1]


class LearningError(RuntimeError):
    """Expected, user-actionable failure."""


class ConfigurationError(LearningError):
    """Missing or unsafe state-directory configuration."""


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    excluded = {
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_COMMON_DIR",
        "GIT_CEILING_DIRECTORIES",
        "GIT_DISCOVERY_ACROSS_FILESYSTEM",
        "GIT_NAMESPACE",
        "GIT_TEMPLATE_DIR",
    }
    for name in list(env):
        if name in excluded or name.startswith("GIT_CONFIG_"):
            env.pop(name, None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["LC_ALL"] = "C"
    return env


def _run_git(
    directory: Path,
    args: Sequence[str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = [
        "git",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "commit.gpgsign=false",
        "-c",
        "core.sharedRepository=0",
        "-C",
        str(directory),
        *args,
    ]
    try:
        options: dict[str, Any] = {
            "check": False,
            "capture_output": True,
            "text": True,
            "env": _git_env(),
        }
        if os.name == "posix":
            options["umask"] = 0o077
        result = subprocess.run(command, **options)
    except FileNotFoundError as exc:
        raise LearningError("git is required but was not found") from exc
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise LearningError(detail)
    return result


def _public_repo_root() -> Path:
    result = _run_git(SKILL_DIR, ("rev-parse", "--show-toplevel"), check=False)
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip()).resolve()
    return SKILL_DIR


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _enclosing_git_root(path: Path) -> Path | None:
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    result = _run_git(probe, ("rev-parse", "--show-toplevel"), check=False)
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip()).resolve()
    git_dir = _run_git(probe, ("rev-parse", "--absolute-git-dir"), check=False)
    if git_dir.returncode == 0 and git_dir.stdout.strip():
        # A bare repository has no top-level worktree. A path below a regular
        # repository's .git directory has the same property. Both are unsafe
        # parents for a second repository.
        return Path(git_dir.stdout.strip()).resolve()
    return None


def resolve_data_dir(explicit: str | None) -> Path:
    raw = explicit
    if not raw:
        raw = os.environ.get("NATURAL_KOREAN_DATA_DIR")
    if not raw:
        plugin_data = os.environ.get("CLAUDE_PLUGIN_DATA")
        if plugin_data:
            raw = str(Path(plugin_data).expanduser() / "natural-korean")
    if not raw:
        raise ConfigurationError(
            "no local data directory configured; pass --data-dir, set "
            "NATURAL_KOREAN_DATA_DIR, or set CLAUDE_PLUGIN_DATA"
        )
    if "\x00" in raw or "\n" in raw or "\r" in raw:
        raise ConfigurationError("the local data directory contains invalid characters")
    state = Path(raw).expanduser().resolve()
    public_root = _public_repo_root()
    if _is_within(state, public_root):
        raise ConfigurationError(
            f"refusing local learning state inside the public skill repository: {public_root}"
        )
    enclosing_root = _enclosing_git_root(state)
    if enclosing_root is not None and enclosing_root != state:
        raise ConfigurationError(
            "refusing local learning state inside another Git repository: "
            f"{enclosing_root}"
        )
    return state


def _empty_profile() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "preferences": [],
        "candidates": [],
    }


def _empty_rules() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "schema": {
            "description": "Machine-loadable literal rules generated from the private local profile.",
            "rule_fields": {
                "id": "A unique LOCAL-NNNN identifier.",
                "title": "The abstract local preference.",
                "level": "One of block, review, or advisory.",
                "genres": "The deliverable genres to which the rule applies.",
                "scope": "The text unit in which matches are counted.",
                "min_hits": "The number of matches needed in one scope unit.",
                "pattern": "A Python regular expression escaped from the avoid literal.",
                "message": "The abstract preference shown when the rule matches.",
                "suggestion": "A short preferred literal or a generic safe direction.",
                "source": "A non-sensitive marker identifying local profile data.",
            },
            "semantics": {
                "genre_gating": "The all genre applies everywhere; other genres apply only when selected.",
                "scope": "Generated literal rules inspect each physical line.",
                "threshold": "Generated literal rules report after one match.",
                "exit_status": "Generated review findings produce checker exit status 1.",
                "masking": "The checker applies its standard quotation and code masking.",
            },
        },
        "rules": [],
    }


def _metric_bucket() -> dict[str, int]:
    return {
        "artifacts": 0,
        "chars": 0,
        "corrections": 0,
        "false_positives": 0,
    }


def _empty_reviews() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "totals": _metric_bucket(),
        "by_genre": {},
    }


def _effective_uid() -> int:
    getter = getattr(os, "geteuid", None)
    if os.name != "posix" or getter is None:
        raise LearningError(
            "private local learning state requires POSIX ownership and mode controls"
        )
    return int(getter())


def _assert_private_entry(
    path: Path,
    *,
    description: str,
    require_directory: bool | None = None,
) -> os.stat_result:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise LearningError(f"missing {description}: {path}") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise LearningError(f"{description} must not be a symlink: {path}")
    if require_directory is True and not stat.S_ISDIR(metadata.st_mode):
        raise LearningError(f"{description} must be a directory: {path}")
    if require_directory is False and not stat.S_ISREG(metadata.st_mode):
        raise LearningError(f"{description} must be a regular file: {path}")
    if metadata.st_uid != _effective_uid():
        raise LearningError(f"{description} must be owned by the current user: {path}")
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise LearningError(
            f"{description} grants group/other access; owner-only permissions are required: {path}"
        )
    return metadata


def _assert_private_state_root(state: Path) -> None:
    metadata = _assert_private_entry(
        state, description="local state directory", require_directory=True
    )
    if stat.S_IMODE(metadata.st_mode) != 0o700:
        raise LearningError(
            "local state directory must have exact POSIX mode 0700: "
            f"{state} (found {stat.S_IMODE(metadata.st_mode):04o})"
        )


def _assert_private_git_tree(git_dir: Path) -> None:
    _assert_private_entry(
        git_dir, description="Git directory", require_directory=True
    )
    for root, directories, files in os.walk(git_dir, followlinks=False):
        root_path = Path(root)
        for name in directories:
            _assert_private_entry(
                root_path / name,
                description="Git metadata directory",
                require_directory=True,
            )
        for name in files:
            _assert_private_entry(
                root_path / name,
                description="Git metadata file",
                require_directory=False,
            )


def _atomic_json_write(path: Path, value: Any) -> None:
    if path.is_symlink():
        raise LearningError(f"refusing to replace symlinked state file: {path.name}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
        except OSError:
            directory_fd = None
        if directory_fd is not None:
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _load_json(path: Path) -> dict[str, Any]:
    _assert_private_entry(
        path, description=f"state file {path.name}", require_directory=False
    )
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError as exc:
        raise LearningError(f"missing state file: {path.name}; run init") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise LearningError(f"invalid state file {path.name}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise LearningError(f"unsupported or invalid schema in {path.name}")
    return value


def _assert_dedicated_repo(state: Path) -> None:
    _assert_private_state_root(state)
    marker = state / ".git"
    try:
        marker_metadata = marker.lstat()
    except FileNotFoundError as exc:
        raise LearningError(
            f"not an initialized local learning repository: {state}; run init"
        ) from exc
    if stat.S_ISLNK(marker_metadata.st_mode):
        raise LearningError("the local repository .git entry must not be a symlink")
    if not stat.S_ISDIR(marker_metadata.st_mode):
        raise LearningError(
            "the local repository must use a real .git directory inside the state root"
        )

    expected_git_dir = marker.resolve()
    git_dir_result = _run_git(state, ("rev-parse", "--absolute-git-dir"))
    git_dir = Path(git_dir_result.stdout.strip()).resolve()
    if git_dir != expected_git_dir or not _is_within(git_dir, state):
        raise LearningError(
            "the resolved Git directory must be the state root's own .git directory"
        )

    common_result = _run_git(state, ("rev-parse", "--git-common-dir"))
    common_raw = Path(common_result.stdout.strip())
    common_dir = (
        common_raw.resolve()
        if common_raw.is_absolute()
        else (state / common_raw).resolve()
    )
    if common_dir != expected_git_dir:
        raise LearningError("Git common metadata must remain inside the state .git directory")

    object_result = _run_git(state, ("rev-parse", "--git-path", "objects"))
    object_raw = Path(object_result.stdout.strip())
    object_dir = (
        object_raw.resolve()
        if object_raw.is_absolute()
        else (state / object_raw).resolve()
    )
    expected_object_dir = (expected_git_dir / "objects").resolve()
    if (
        object_dir != expected_object_dir
        or not _is_within(object_dir, expected_git_dir)
    ):
        raise LearningError("Git objects must remain inside the state .git directory")

    alternates = expected_git_dir / "objects" / "info" / "alternates"
    if alternates.exists():
        try:
            configured_alternates = alternates.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError) as exc:
            raise LearningError("could not validate Git object alternates") from exc
        if configured_alternates:
            raise LearningError("Git object alternates are not allowed")

    result = _run_git(state, ("rev-parse", "--show-toplevel"))
    top_level = Path(result.stdout.strip()).resolve()
    if top_level != state.resolve():
        raise LearningError("the data directory must be the root of its dedicated git repository")
    _assert_private_git_tree(expected_git_dir)


def _assert_no_remote(state: Path) -> None:
    remotes = _run_git(state, ("remote",)).stdout.split()
    if remotes:
        raise LearningError(
            "local learning repository must not have remotes; remove: "
            + ", ".join(sorted(remotes))
        )


def _assert_local_identity(state: Path) -> None:
    name = _run_git(
        state, ("config", "--local", "--get", "user.name"), check=False
    ).stdout.strip()
    email = _run_git(
        state, ("config", "--local", "--get", "user.email"), check=False
    ).stdout.strip()
    if name != LOCAL_GIT_NAME or email != LOCAL_GIT_EMAIL:
        raise LearningError(
            "local learning repository has an unexpected Git identity; "
            "run init on a new empty data directory"
        )


def _assert_clean(state: Path) -> None:
    status = _run_git(
        state, ("status", "--porcelain=v1", "--untracked-files=all")
    ).stdout
    if status:
        raise LearningError(
            "local learning repository is dirty; commit, revert, or remove those changes first"
        )


def _validate_repo(state: Path, *, require_clean: bool) -> None:
    _assert_dedicated_repo(state)
    _assert_no_remote(state)
    _assert_local_identity(state)
    if require_clean:
        _assert_clean(state)


def _commit(state: Path, message: str, files: Sequence[str]) -> str:
    _run_git(state, ("add", "--", *files))
    staged = _run_git(state, ("diff", "--cached", "--quiet"), check=False)
    if staged.returncode == 0:
        raise LearningError("the requested mutation produced no state change")
    if staged.returncode != 1:
        raise LearningError(staged.stderr.strip() or "could not inspect staged state")
    _run_git(state, ("commit", "--quiet", "-m", message, "--", *files))
    _assert_clean(state)
    _assert_dedicated_repo(state)
    return _run_git(state, ("rev-parse", "--short", "HEAD")).stdout.strip()


def _validate_state_files(state: Path) -> None:
    profile = _load_json(state / PROFILE_FILE)
    reviews = _load_json(state / REVIEWS_FILE)
    rules = _load_json(state / RULES_FILE)
    if not isinstance(profile.get("preferences"), list) or not isinstance(
        profile.get("candidates"), list
    ):
        raise LearningError("invalid profile.json collections")
    if not isinstance(reviews.get("totals"), dict) or not isinstance(
        reviews.get("by_genre"), dict
    ):
        raise LearningError("invalid reviews.json aggregates")
    if not isinstance(rules.get("rules"), list):
        raise LearningError("invalid rules.local.json rules")


def command_init(state: Path) -> str:
    if state.exists():
        _assert_private_state_root(state)
        if (state / ".git").exists():
            _validate_repo(state, require_clean=True)
            _validate_state_files(state)
            return "already initialized"
        if any(state.iterdir()):
            raise LearningError("init requires a new or empty data directory")
    else:
        _effective_uid()
        state.mkdir(parents=True, mode=0o700)
        # mode= is still filtered by the caller's umask. Set the exact mode
        # before any state or Git data is written.
        os.chmod(state, 0o700)
        _assert_private_state_root(state)

    _run_git(state, ("init", "--quiet", "--initial-branch=main"))
    _assert_dedicated_repo(state)
    _assert_no_remote(state)
    _assert_clean(state)
    _run_git(state, ("config", "--local", "user.name", LOCAL_GIT_NAME))
    _run_git(
        state,
        ("config", "--local", "user.email", LOCAL_GIT_EMAIL),
    )
    _run_git(state, ("config", "--local", "commit.gpgsign", "false"))
    _atomic_json_write(state / PROFILE_FILE, _empty_profile())
    _atomic_json_write(state / RULES_FILE, _empty_rules())
    _atomic_json_write(state / REVIEWS_FILE, _empty_reviews())
    commit = _commit(
        state,
        "natural-korean: initialize local learning state",
        TRACKED_FILES,
    )
    return f"initialized ({commit})"


def _normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).strip().split())


def _contains_ip(value: str) -> bool:
    for match in IPV4_RE.finditer(value):
        try:
            ipaddress.ip_address(match.group(0))
        except ValueError:
            continue
        return True
    for match in IPV6_TOKEN_RE.finditer(value):
        token = match.group(0)
        if ":" not in token:
            continue
        try:
            ipaddress.ip_address(token)
        except ValueError:
            continue
        return True
    return False


def _validate_private_text(
    value: str | None,
    *,
    field: str,
    minimum: int,
    maximum: int,
) -> str | None:
    if value is None:
        return None
    if "\n" in value or "\r" in value or "\x00" in value:
        raise LearningError(f"{field} must be a single line")
    normalized = _normalize_text(value)
    if not minimum <= len(normalized) <= maximum:
        raise LearningError(
            f"{field} must be between {minimum} and {maximum} characters"
        )
    sensitive_reason = None
    if URL_RE.search(normalized):
        sensitive_reason = "URL"
    elif EMAIL_RE.search(normalized):
        sensitive_reason = "email address"
    elif UUID_RE.search(normalized):
        sensitive_reason = "UUID"
    elif POSIX_PATH_RE.search(normalized) or WINDOWS_PATH_RE.search(normalized):
        sensitive_reason = "absolute path"
    elif _contains_ip(normalized):
        sensitive_reason = "IP address"
    elif LONG_NUMERIC_ID_RE.search(normalized):
        sensitive_reason = "long numeric identifier"
    elif LABELED_ID_RE.search(normalized) or UPPER_ID_RE.search(normalized):
        sensitive_reason = "document-like identifier"
    elif DIGIT_RE.search(normalized):
        sensitive_reason = "numeric content; generalize it without the value"
    elif (
        KOREAN_LEGAL_ORG_RE.search(normalized)
        or KOREAN_ORG_SUFFIX_RE.search(normalized)
        or ENGLISH_ORG_RE.search(normalized)
    ):
        sensitive_reason = "organization-like name; generalize it before recording"
    if sensitive_reason:
        raise LearningError(f"{field} contains a prohibited {sensitive_reason}")
    return normalized


def _next_local_id(profile: dict[str, Any]) -> str:
    numbers: list[int] = []
    for collection_name in ("preferences", "candidates"):
        for item in profile[collection_name]:
            if isinstance(item, dict):
                match = LOCAL_ID_RE.fullmatch(str(item.get("id", "")))
                if match:
                    numbers.append(int(match.group(1)))
    number = max(numbers, default=0) + 1
    if number > 9999:
        raise LearningError("local preference ID space is exhausted")
    return f"LOCAL-{number:04d}"


def _instruction_key(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _merge_genres(existing: list[str], incoming: list[str]) -> list[str]:
    values = set(existing) | set(incoming)
    if "all" in values:
        return ["all"]
    return [genre for genre in RECORD_GENRES if genre in values]


def _merge_sources(existing: list[str], source: str) -> list[str]:
    values = set(existing)
    values.add(source)
    return [item for item in SOURCES if item in values]


def _make_record(
    identifier: str,
    instruction: str,
    genres: list[str],
    avoid: str | None,
    prefer: str | None,
    source: str,
) -> dict[str, Any]:
    return {
        "id": identifier,
        "instruction": instruction,
        "genres": genres,
        "avoid": avoid,
        "prefer": prefer,
        "confirmations": 1,
        "sources": [source],
    }


def _find_record(profile: dict[str, Any], instruction: str) -> tuple[str, int] | None:
    key = _instruction_key(instruction)
    for collection_name in ("preferences", "candidates"):
        for index, item in enumerate(profile[collection_name]):
            if _instruction_key(str(item.get("instruction", ""))) == key:
                return collection_name, index
    return None


def _rules_from_profile(profile: dict[str, Any]) -> dict[str, Any]:
    output = _empty_rules()
    for preference in profile["preferences"]:
        avoid = preference.get("avoid")
        if not avoid:
            continue
        prefer = preference.get("prefer") or ""
        instruction = preference["instruction"]
        output["rules"].append(
            {
                "id": preference["id"],
                "title": instruction,
                "level": "review",
                "genres": preference["genres"],
                "scope": "line",
                "min_hits": 1,
                "pattern": re.escape(avoid),
                "message": instruction,
                "suggestion": prefer
                or "이 표현을 피하고 등록된 로컬 선호를 따르세요.",
                "source": "local-profile",
            }
        )
    return output


def command_record(
    state: Path,
    *,
    preference: str,
    source: str,
    durable: bool,
    separate_context: bool,
    genres: list[str],
    avoid: str | None,
    prefer: str | None,
) -> str:
    _validate_repo(state, require_clean=True)
    _validate_state_files(state)
    if durable and source != "explicit":
        raise LearningError("--durable is only valid with --source explicit")
    if separate_context and source == "explicit":
        raise LearningError(
            "--separate-context is for repeated correction/observed evidence"
        )
    instruction = _validate_private_text(
        preference, field="preference", minimum=4, maximum=160
    )
    assert instruction is not None
    avoid_value = _validate_private_text(
        avoid, field="avoid literal", minimum=1, maximum=64
    )
    prefer_value = _validate_private_text(
        prefer, field="prefer literal", minimum=1, maximum=64
    )
    normalized_genres = _merge_genres([], genres or ["all"])

    profile = _load_json(state / PROFILE_FILE)
    found = _find_record(profile, instruction)
    promote_now = source == "explicit" and durable
    action: str

    if found is None:
        record = _make_record(
            _next_local_id(profile),
            instruction,
            normalized_genres,
            avoid_value,
            prefer_value,
            source,
        )
        if promote_now:
            profile["preferences"].append(record)
            action = "promoted"
        else:
            profile["candidates"].append(record)
            action = "candidate"
    else:
        collection_name, index = found
        record = profile[collection_name][index]
        record_before = json.dumps(record, ensure_ascii=False, sort_keys=True)
        if collection_name == "preferences" and not (
            separate_context or promote_now
        ):
            return f"unchanged {record['id']} (already promoted)"
        if collection_name == "candidates" and not (
            separate_context or promote_now
        ):
            return (
                f"unchanged {record['id']} "
                "(repeat with --separate-context to confirm distinct evidence)"
            )
        record["genres"] = _merge_genres(record["genres"], normalized_genres)
        record["sources"] = _merge_sources(record["sources"], source)
        if avoid_value is not None:
            if record.get("avoid") not in (None, avoid_value):
                raise LearningError(
                    "the repeated preference has a conflicting avoid literal"
                )
            record["avoid"] = avoid_value
        if prefer_value is not None:
            if record.get("prefer") not in (None, prefer_value):
                raise LearningError(
                    "the repeated preference has a conflicting prefer literal"
                )
            record["prefer"] = prefer_value
        if separate_context:
            record["confirmations"] = int(record.get("confirmations", 1)) + 1
        if collection_name == "candidates" and (
            promote_now or record["confirmations"] >= 2
        ):
            profile["candidates"].pop(index)
            profile["preferences"].append(record)
            action = "promoted"
        else:
            action = "confirmed"
        if (
            collection_name == "preferences"
            and json.dumps(record, ensure_ascii=False, sort_keys=True) == record_before
        ):
            return f"unchanged {record['id']} (already promoted)"

    profile["preferences"].sort(key=lambda item: item["id"])
    profile["candidates"].sort(key=lambda item: item["id"])
    rules = _rules_from_profile(profile)
    _atomic_json_write(state / PROFILE_FILE, profile)
    _atomic_json_write(state / RULES_FILE, rules)
    record_id = record["id"]
    commit = _commit(
        state,
        f"natural-korean: record {record_id} {action}",
        (PROFILE_FILE, RULES_FILE),
    )
    return f"{action} {record_id} ({commit})"


def _validate_metric_bucket(value: Any, name: str) -> None:
    if not isinstance(value, dict):
        raise LearningError(f"invalid review aggregate: {name}")
    for field in ("artifacts", "chars", "corrections", "false_positives"):
        if not isinstance(value.get(field), int) or value[field] < 0:
            raise LearningError(f"invalid review aggregate: {name}.{field}")


def command_review(
    state: Path,
    *,
    human_reviewed: bool,
    genre: str,
    chars: int,
    corrections: int,
    false_positives: int,
) -> str:
    _validate_repo(state, require_clean=True)
    _validate_state_files(state)
    if not human_reviewed:
        raise LearningError(
            "review metrics require --human-reviewed; never record an unreviewed zero"
        )
    if chars <= 0:
        raise LearningError("--chars must be greater than zero")
    if corrections < 0 or false_positives < 0:
        raise LearningError("review counts must be non-negative")

    reviews = _load_json(state / REVIEWS_FILE)
    _validate_metric_bucket(reviews.get("totals"), "totals")
    bucket = reviews["by_genre"].setdefault(genre, _metric_bucket())
    _validate_metric_bucket(bucket, genre)
    increments = {
        "artifacts": 1,
        "chars": chars,
        "corrections": corrections,
        "false_positives": false_positives,
    }
    for field, amount in increments.items():
        reviews["totals"][field] += amount
        bucket[field] += amount
    _atomic_json_write(state / REVIEWS_FILE, reviews)
    commit = _commit(
        state,
        f"natural-korean: review {genre} artifact",
        (REVIEWS_FILE,),
    )
    return f"reviewed {genre} artifact ({commit})"


def _review_rates(bucket: dict[str, int]) -> dict[str, float | None]:
    chars = bucket["chars"]
    artifacts = bucket["artifacts"]
    return {
        "corrections_per_1000_chars": (
            round(bucket["corrections"] * 1000 / chars, 3) if chars else None
        ),
        "false_positives_per_artifact": (
            round(bucket["false_positives"] / artifacts, 3)
            if artifacts
            else None
        ),
    }


def _status_payload(state: Path) -> dict[str, Any]:
    _validate_repo(state, require_clean=False)
    _validate_state_files(state)
    profile = _load_json(state / PROFILE_FILE)
    reviews = _load_json(state / REVIEWS_FILE)
    dirty = bool(
        _run_git(
            state, ("status", "--porcelain=v1", "--untracked-files=all")
        ).stdout
    )
    return {
        "data_dir": str(state),
        "dirty": dirty,
        "preferences": len(profile["preferences"]),
        "candidates": len(profile["candidates"]),
        "reviews": reviews["totals"],
        "review_rates": _review_rates(reviews["totals"]),
        "reviews_by_genre": reviews["by_genre"],
        "head": _run_git(state, ("rev-parse", "--short", "HEAD")).stdout.strip(),
    }


def command_status(state: Path, *, as_json: bool) -> str:
    payload = _status_payload(state)
    if as_json:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
    reviews = payload["reviews"]
    rates = payload["review_rates"]
    correction_rate = rates["corrections_per_1000_chars"]
    false_positive_rate = rates["false_positives_per_artifact"]
    return (
        f"{payload['preferences']} preferences, {payload['candidates']} candidates; "
        f"{reviews['artifacts']} reviewed artifacts, {reviews['chars']} chars, "
        f"{reviews['corrections']} corrections, "
        f"{reviews['false_positives']} false positives; "
        f"{correction_rate if correction_rate is not None else 'n/a'} "
        "corrections/1k chars, "
        f"{false_positive_rate if false_positive_rate is not None else 'n/a'} "
        "false positives/artifact; "
        f"head {payload['head']}; "
        f"{'dirty' if payload['dirty'] else 'clean'}"
    )


def command_history(state: Path, *, limit: int) -> str:
    _validate_repo(state, require_clean=False)
    if not 1 <= limit <= 1000:
        raise LearningError("--limit must be between 1 and 1000")
    return _run_git(
        state,
        (
            "log",
            f"-n{limit}",
            "--date=short",
            "--pretty=format:%h%x09%ad%x09%s",
        ),
    ).stdout.rstrip()


def command_revert(state: Path, *, commit: str) -> str:
    _validate_repo(state, require_clean=True)
    _validate_state_files(state)
    if not COMMIT_RE.fullmatch(commit):
        raise LearningError("revert COMMIT must be a 7-40 character hexadecimal commit ID")
    resolved = _run_git(
        state, ("rev-parse", "--verify", f"{commit}^{{commit}}")
    ).stdout.strip()
    parents = _run_git(state, ("rev-list", "--parents", "-n", "1", resolved)).stdout.split()
    if len(parents) < 2:
        raise LearningError("refusing to revert the initialization commit")
    result = _run_git(state, ("revert", "--no-edit", resolved), check=False)
    if result.returncode != 0:
        _run_git(state, ("revert", "--abort"), check=False)
        detail = result.stderr.strip() or result.stdout.strip() or "git revert failed"
        raise LearningError(detail)
    _validate_state_files(state)
    _assert_clean(state)
    _assert_dedicated_repo(state)
    new_head = _run_git(state, ("rev-parse", "--short", "HEAD")).stdout.strip()
    return f"reverted {resolved[:12]} ({new_head})"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Version private natural-korean preferences outside the public skill checkout."
    )
    parser.add_argument(
        "--data-dir",
        help=(
            "local state repository (otherwise NATURAL_KOREAN_DATA_DIR, then "
            "CLAUDE_PLUGIN_DATA/natural-korean)"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="initialize the dedicated local Git repository")

    record = subparsers.add_parser("record", help="record an abstract style preference")
    record.add_argument("--preference", required=True, help="abstract preference, never raw text")
    record.add_argument("--source", required=True, choices=SOURCES)
    record.add_argument(
        "--durable",
        action="store_true",
        help="mark an explicit preference as lasting and promote it immediately",
    )
    record.add_argument(
        "--separate-context",
        action="store_true",
        help="confirm repeated correction/observed evidence came from another reviewed context",
    )
    record.add_argument(
        "--genre",
        action="append",
        choices=RECORD_GENRES,
        default=[],
        help="rule genre; repeat for more than one (default: all)",
    )
    record.add_argument("--avoid", help="optional short literal to flag")
    record.add_argument("--prefer", help="optional short replacement literal")

    review = subparsers.add_parser(
        "review", help="aggregate one completed human review"
    )
    review.add_argument("--human-reviewed", action="store_true", required=True)
    review.add_argument("--genre", required=True, choices=ARTIFACT_GENRES)
    review.add_argument("--chars", required=True, type=int)
    review.add_argument("--corrections", required=True, type=int)
    review.add_argument("--false-positives", required=True, type=int)

    status = subparsers.add_parser("status", help="show local learning status")
    status.add_argument("--json", action="store_true")

    history = subparsers.add_parser("history", help="show sanitized local Git history")
    history.add_argument("--limit", type=int, default=20)

    revert = subparsers.add_parser("revert", help="inverse a learning commit with git revert")
    revert.add_argument("commit")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        state = resolve_data_dir(args.data_dir)
        if args.command == "init":
            result = command_init(state)
        elif args.command == "record":
            result = command_record(
                state,
                preference=args.preference,
                source=args.source,
                durable=args.durable,
                separate_context=args.separate_context,
                genres=args.genre,
                avoid=args.avoid,
                prefer=args.prefer,
            )
        elif args.command == "review":
            result = command_review(
                state,
                human_reviewed=args.human_reviewed,
                genre=args.genre,
                chars=args.chars,
                corrections=args.corrections,
                false_positives=args.false_positives,
            )
        elif args.command == "status":
            result = command_status(state, as_json=args.json)
        elif args.command == "history":
            result = command_history(state, limit=args.limit)
        elif args.command == "revert":
            result = command_revert(state, commit=args.commit)
        else:  # pragma: no cover - argparse enforces the command set.
            raise LearningError(f"unsupported command: {args.command}")
    except ConfigurationError as exc:
        print(f"natural-korean: configuration error: {exc}", file=sys.stderr)
        return 2
    except LearningError as exc:
        print(f"natural-korean: error: {exc}", file=sys.stderr)
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
