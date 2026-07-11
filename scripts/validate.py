#!/usr/bin/env python3
"""Validate skills/*/SKILL.md against the Agent Skills spec (agentskills.io).

Checks the hard rules: frontmatter presence, name format (1-64 chars,
lowercase/digits/hyphens, no leading/trailing/consecutive hyphens, must match
the directory name) and description (1-1024 chars). Warns when a body exceeds
the recommended 500 lines. Simple parser: single-line frontmatter values only.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

errors: list = []
warnings: list = []

skills_root = ROOT / "skills"
skill_dirs = sorted(p for p in skills_root.iterdir() if p.is_dir()) if skills_root.is_dir() else []

for d in skill_dirs:
    md = d / "SKILL.md"
    rel = md.relative_to(ROOT)
    if not md.is_file():
        errors.append(f"{d.name}: missing SKILL.md")
        continue
    text = md.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        errors.append(f"{rel}: missing YAML frontmatter")
        continue
    fm, body = m.groups()
    fields = {}
    for line in fm.splitlines():
        km = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
        if km:
            fields[km.group(1)] = km.group(2).strip().strip("\"'")

    name = fields.get("name", "")
    desc = fields.get("description", "")
    if not name:
        errors.append(f"{rel}: name is required")
    elif len(name) > 64 or not NAME_RE.fullmatch(name):
        errors.append(
            f"{rel}: name must be 1-64 chars of lowercase letters, digits, "
            f"single hyphens (got {name!r})"
        )
    elif name != d.name:
        errors.append(f"{rel}: name {name!r} != directory name {d.name!r}")

    if not desc:
        errors.append(f"{rel}: description is required")
    elif len(desc) > 1024:
        errors.append(f"{rel}: description over 1024 chars ({len(desc)})")

    body_lines = len(body.splitlines())
    if body_lines > 500:
        warnings.append(f"{rel}: body is {body_lines} lines (>500); move detail into references/")

for w in warnings:
    print(f"warning: {w}")
if errors:
    for e in errors:
        print(f"error: {e}")
    sys.exit(1)
print(f"ok: {len(skill_dirs)} skill(s) valid")
