#!/usr/bin/env python3
"""evals의 -styled 케이스를 -plain 케이스와 output style 본문에서 재생성한다.

-styled 디렉터리는 전부 생성물이다. 고치고 싶은 내용이 있으면 -plain 쪽
prompt.md·graders나 output-styles/natural-korean-understanding.md를 고친 뒤
이 스크립트를 다시 실행한다. --check는 재생성 결과와 저장소의 현재 파일이
다르면 목록을 출력하고 1로 종료한다.
"""
import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVALS = ROOT / "evals"
STYLE = ROOT / "output-styles" / "natural-korean-understanding.md"
FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)


def style_body() -> str:
    text = STYLE.read_text(encoding="utf-8")
    m = FRONTMATTER.match(text)
    if not m:
        sys.exit(f"error: {STYLE}에 frontmatter가 없다")
    text = text[m.end():]
    # 파일 머리의 HTML 주석은 출처 기록이지 지침이 아니므로 주입에서 제외한다.
    text = re.sub(r"\A\s*<!--.*?-->\s*", "\n", text, count=1, flags=re.S)
    return text.strip() + "\n"


def styled_prompt(plain_text: str, body: str) -> str:
    m = FRONTMATTER.match(plain_text)
    if not m:
        sys.exit("error: plain prompt.md에 frontmatter가 없다")
    fm = m.group(1)
    rest = plain_text[m.end():]
    indented = "\n".join(
        ("  " + line) if line.strip() else "" for line in body.splitlines()
    )
    return f"---\n{fm}\nappend_system_prompt: |\n{indented}\n---\n{rest}"


def generate(dest_root: Path) -> list[Path]:
    body = style_body()
    plains = sorted(EVALS.glob("*-plain"))
    if not plains:
        sys.exit("error: evals/에 -plain 케이스가 없다")
    written = []
    for plain in plains:
        case = plain.name[: -len("-plain")]
        styled = dest_root / f"{case}-styled"
        graders = styled / "graders"
        graders.mkdir(parents=True, exist_ok=True)
        prompt = styled / "prompt.md"
        prompt.write_text(
            styled_prompt((plain / "prompt.md").read_text(encoding="utf-8"), body),
            encoding="utf-8",
        )
        written.append(prompt)
        for g in sorted((plain / "graders").glob("*.md")):
            target = graders / g.name
            shutil.copyfile(g, target)
            written.append(target)
    return written


def check() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        generate(tmp_root)
        drift = []
        for fresh in sorted(tmp_root.rglob("*.md")):
            rel = fresh.relative_to(tmp_root)
            current = EVALS / rel
            if not current.is_file():
                drift.append(f"missing: evals/{rel}")
            elif current.read_text(encoding="utf-8") != fresh.read_text(encoding="utf-8"):
                drift.append(f"stale:   evals/{rel}")
        fresh_names = {p.relative_to(tmp_root) for p in tmp_root.rglob("*.md")}
        for current in sorted(EVALS.glob("*-styled/**/*.md")):
            rel = current.relative_to(EVALS)
            if rel not in fresh_names:
                drift.append(f"extra:   evals/{rel}")
    if drift:
        print("\n".join(drift))
        print("hint: python3 evals/sync_style.py 로 재생성한다", file=sys.stderr)
        return 1
    print("styled cases: in sync")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="재생성 없이 최신 여부만 검사")
    args = parser.parse_args()
    if args.check:
        return check()
    written = generate(EVALS)
    cases = {p.relative_to(EVALS).parts[0] for p in written}
    print(f"generated {len(written)} file(s) across {len(cases)} styled case(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
