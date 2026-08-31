#!/usr/bin/env python3
"""natural-korean-understanding의 판정과 세션 노출을 기록한다.

기록 위치는 learn.py의 학습 저장소와 분리된 전용 디렉터리다. 학습 저장소는
untracked 파일이 하나라도 있으면 learn.py가 동작을 거부하므로(_assert_clean),
이 로그를 그 안에 두지 않는다. 기본 위치는
${XDG_STATE_HOME:-~/.local/state}/natural-korean-ab 이고 NK_AB_DATA_DIR로
바꿀 수 있다. 판정은 "적용 전 대비 나은가"의 비교형 up/down 하나다.

새 기록은 agent와 protocol을 명시해 Claude blind A/B, 수동 기록, Codex
명시 호출을 분리한다. 노출의 ask_armed는 실제로 질문했는지가 아니라 세션에
질문 메모를 주입했는지를 뜻한다. 기존 JSONL은 고치지 않고 읽을 때만
agent=claude, protocol=legacy-unlabeled로 호환 처리하며 asked를
ask_armed로 옮긴다.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import learn  # 메모의 PII 필터를 재사용한다

STYLE_NAME = "natural-korean-understanding"
FEEDBACK_FILE = "feedback.jsonl"
EXPOSURE_FILE = "exposures.jsonl"
CLAUDE_BLIND_V2 = "claude-blind-v2"
CLAUDE_MANUAL_V1 = "claude-manual-v1"
CODEX_EXPLICIT_V1 = "codex-explicit-v1"
LEGACY_PROTOCOL = "legacy-unlabeled"
PROTOCOL_AGENTS = {
    CLAUDE_BLIND_V2: "claude",
    CLAUDE_MANUAL_V1: "claude",
    CODEX_EXPLICIT_V1: "codex",
}


def data_dir() -> Path:
    root = os.environ.get("NK_AB_DATA_DIR")
    if not root:
        base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
        root = str(Path(base) / "natural-korean-ab")
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def detect_arm(explicit: str | None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("NK_AB_ARM")
    if env in ("styled", "plain"):
        return env
    candidates = (
        Path.cwd() / ".claude" / "settings.local.json",
        Path.cwd() / ".claude" / "settings.json",
        Path.home() / ".claude" / "settings.json",
    )
    for cfg in candidates:
        try:
            settings = json.loads(cfg.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if "outputStyle" in settings:
            return "styled" if settings["outputStyle"] == STYLE_NAME else "plain"
    return "plain"


def append(path: Path, record: dict) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    os.chmod(path, 0o600)


def normalize_record(record: dict) -> dict:
    """Return a read-compatible record without mutating the JSONL source."""
    normalized = dict(record)
    normalized.setdefault("agent", "claude")
    normalized.setdefault("protocol", LEGACY_PROTOCOL)
    if "ask_armed" not in normalized:
        normalized["ask_armed"] = bool(normalized.get("asked", False))
    normalized.pop("asked", None)
    return normalized


def load(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(normalize_record(json.loads(line)))
    return rows


def aggregate(feedback: list[dict], exposures: list[dict]) -> dict[tuple[str, str, str], dict[str, int]]:
    """Aggregate independently recorded exposure and feedback rows."""
    grouped: dict[tuple[str, str, str], dict[str, int]] = {}

    def bucket(record: dict) -> dict[str, int]:
        key = (
            str(record.get("agent", "<unknown>")),
            str(record.get("protocol", LEGACY_PROTOCOL)),
            str(record.get("arm", "<unknown>")),
        )
        return grouped.setdefault(
            key,
            {"sessions": 0, "ask_armed": 0, "feedback": 0, "up": 0, "misread": 0},
        )

    for record in exposures:
        values = bucket(record)
        values["sessions"] += 1
        values["ask_armed"] += int(bool(record.get("ask_armed")))
    for record in feedback:
        values = bucket(record)
        values["feedback"] += 1
        values["up"] += int(record.get("verdict") == "up")
        values["misread"] += int(bool(record.get("misread")))
    return grouped


def print_arm_table(grouped: dict[tuple[str, str, str], dict[str, int]], keys: list[tuple[str, str, str]]) -> None:
    header = f"{'arm':<8}{'sessions':>9}{'ask-armed':>11}{'feedback':>10}{'up-rate':>9}{'misread':>9}"
    print(header)
    for key in keys:
        values = grouped.get(
            key,
            {"sessions": 0, "ask_armed": 0, "feedback": 0, "up": 0, "misread": 0},
        )
        rate = (
            f"{values['up'] / values['feedback']:>9.0%}"
            if values["feedback"]
            else f"{'-':>9}"
        )
        print(
            f"{key[2]:<8}{values['sessions']:>9}{values['ask_armed']:>11}"
            f"{values['feedback']:>10}{rate}{values['misread']:>9}"
        )


def summarize(root: Path) -> None:
    feedback = load(root / FEEDBACK_FILE)
    exposures = load(root / EXPOSURE_FILE)
    grouped = aggregate(feedback, exposures)
    print(f"data dir: {root}")
    print(f"adoption: agent=claude protocol={CLAUDE_BLIND_V2}")
    adoption_keys = [("claude", CLAUDE_BLIND_V2, arm) for arm in ("styled", "plain")]
    print_arm_table(grouped, adoption_keys)

    other_keys = sorted(key for key in grouped if key not in adoption_keys)
    print("\nother records (excluded from adoption)")
    if not other_keys:
        print("(none)")
        return
    for agent, protocol in sorted({key[:2] for key in other_keys}):
        print(f"agent={agent} protocol={protocol}")
        keys = [key for key in other_keys if key[:2] == (agent, protocol)]
        print_arm_table(grouped, keys)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verdict", choices=("up", "down"),
                        help="적용 전 대비 나았으면 up, 아니면 down")
    parser.add_argument("--misread", action="store_true",
                        help="에이전트가 한 일을 사용자가 오해한 사건이 있었음")
    parser.add_argument("--note", help="짧은 한 줄 메모 (문서 원문·경로·수치 금지)")
    parser.add_argument("--arm", choices=("styled", "plain"),
                        help="기본값은 NK_AB_ARM 환경변수, 다음은 settings의 outputStyle")
    parser.add_argument("--agent", choices=("claude", "codex"), default="claude",
                        help="기록을 만든 에이전트 (기본 claude)")
    parser.add_argument("--protocol", choices=tuple(PROTOCOL_AGENTS),
                        help="실험·호출 프로토콜 (기본값은 에이전트의 수동/명시 프로토콜)")
    parser.add_argument("--log-exposure", action="store_true",
                        help="세션 시작 기록만 남긴다 (래퍼가 호출)")
    parser.add_argument("--ask-armed", action="store_true",
                        help="--log-exposure와 함께: 이 세션에 질문 메모가 주입되었음")
    parser.add_argument("--summary", action="store_true", help="arm별 집계를 출력")
    args = parser.parse_args()

    actions = int(bool(args.verdict)) + int(args.log_exposure) + int(args.summary)
    if actions != 1:
        parser.error("--verdict, --log-exposure, --summary 중 정확히 하나가 필요하다")
    if args.ask_armed and not args.log_exposure:
        parser.error("--ask-armed는 --log-exposure와 함께 써야 한다")
    if (args.misread or args.note) and not args.verdict:
        parser.error("--misread와 --note는 --verdict와 함께 써야 한다")

    protocol = args.protocol
    if protocol is None:
        protocol = CODEX_EXPLICIT_V1 if args.agent == "codex" else CLAUDE_MANUAL_V1
    expected_agent = PROTOCOL_AGENTS[protocol]
    if args.agent != expected_agent:
        parser.error(f"{protocol}은 agent={expected_agent} 기록에만 쓸 수 있다")

    root = data_dir()
    if args.summary:
        summarize(root)
        return 0

    arm = detect_arm(args.arm)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if args.log_exposure:
        append(
            root / EXPOSURE_FILE,
            {
                "ts": now,
                "agent": args.agent,
                "protocol": protocol,
                "arm": arm,
                "ask_armed": args.ask_armed,
            },
        )
        return 0

    try:
        note = learn._validate_private_text(
            args.note, field="note", minimum=1, maximum=160
        )
    except learn.LearningError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    record = {
        "ts": now,
        "agent": args.agent,
        "protocol": protocol,
        "arm": arm,
        "verdict": args.verdict,
        "misread": args.misread,
    }
    if note:
        record["note"] = note
    append(root / FEEDBACK_FILE, record)
    print(f"recorded: agent={args.agent} protocol={protocol} arm={arm} verdict={args.verdict}"
          + (" misread" if args.misread else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
