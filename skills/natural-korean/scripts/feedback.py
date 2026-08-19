#!/usr/bin/env python3
"""natural-korean-understanding A/B 실험의 판정과 세션 노출을 기록한다.

기록 위치는 learn.py의 학습 저장소와 분리된 전용 디렉터리다. 학습 저장소는
untracked 파일이 하나라도 있으면 learn.py가 동작을 거부하므로(_assert_clean),
이 로그를 그 안에 두지 않는다. 기본 위치는
${XDG_STATE_HOME:-~/.local/state}/natural-korean-ab 이고 NK_AB_DATA_DIR로
바꿀 수 있다. 판정은 "적용 전 대비 나은가"의 비교형 up/down 하나다.
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


def load(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def summarize(root: Path) -> None:
    feedback = load(root / FEEDBACK_FILE)
    exposures = load(root / EXPOSURE_FILE)
    print(f"data dir: {root}")
    header = f"{'arm':<8}{'sessions':>9}{'feedback':>9}{'up-rate':>9}{'misread':>9}"
    print(header)
    for arm in ("styled", "plain"):
        rows = [r for r in feedback if r.get("arm") == arm]
        ups = sum(1 for r in rows if r.get("verdict") == "up")
        misreads = sum(1 for r in rows if r.get("misread"))
        sessions = sum(1 for r in exposures if r.get("arm") == arm)
        rate = f"{ups / len(rows):>8.0%}" if rows else f"{'-':>8}"
        print(f"{arm:<8}{sessions:>9}{len(rows):>9}{rate}{misreads:>9}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verdict", choices=("up", "down"),
                        help="적용 전 대비 나았으면 up, 아니면 down")
    parser.add_argument("--misread", action="store_true",
                        help="Claude가 한 일을 오해한 사건이 있었음")
    parser.add_argument("--note", help="짧은 한 줄 메모 (문서 원문·경로·수치 금지)")
    parser.add_argument("--arm", choices=("styled", "plain"),
                        help="기본값은 NK_AB_ARM 환경변수, 다음은 settings의 outputStyle")
    parser.add_argument("--log-exposure", action="store_true",
                        help="세션 시작 기록만 남긴다 (래퍼가 호출)")
    parser.add_argument("--summary", action="store_true", help="arm별 집계를 출력")
    args = parser.parse_args()

    root = data_dir()
    if args.summary:
        summarize(root)
        return 0

    arm = detect_arm(args.arm)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if args.log_exposure:
        append(root / EXPOSURE_FILE, {"ts": now, "arm": arm})
        return 0

    if not args.verdict:
        parser.error("--verdict, --log-exposure, --summary 중 하나가 필요하다")
    try:
        note = learn._validate_private_text(
            args.note, field="note", minimum=1, maximum=160
        )
    except learn.LearningError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    record = {"ts": now, "arm": arm, "verdict": args.verdict, "misread": args.misread}
    if note:
        record["note"] = note
    append(root / FEEDBACK_FILE, record)
    print(f"recorded: arm={arm} verdict={args.verdict}"
          + (" misread" if args.misread else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
