#!/usr/bin/env python3
"""Regenerate the skills table in README.md (between the skills markers) and,
if present, the plugins[0].skills array in .claude-plugin/marketplace.json —
both derived from skills/*/SKILL.md frontmatter."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

rows = []
skill_dirs = []
for d in sorted((ROOT / "skills").iterdir()):
    md = d / "SKILL.md"
    if not (d.is_dir() and md.is_file()):
        continue
    skill_dirs.append(d)
    fm_match = re.match(r"^---\n(.*?)\n---", md.read_text(encoding="utf-8"), re.S)
    fm = fm_match.group(1) if fm_match else ""
    fields = dict(re.findall(r"^([A-Za-z][\w-]*):\s*(.+)$", fm, re.M))
    name = fields.get("name", d.name).strip().strip("\"'")
    desc = fields.get("description", "").strip().strip("\"'")
    desc = desc.split(". ")[0].rstrip(".") + "." if desc else ""
    agents_m = re.search(r"^\s+agents:\s*(.+)$", fm, re.M)
    agents = agents_m.group(1).strip().strip("\"'") if agents_m else "all"
    rows.append(f"| [`{name}`](skills/{d.name}) | {desc} | {agents} |")

table = (
    "\n".join(["| Skill | Description | Agents |", "| --- | --- | --- |", *rows])
    if rows
    else "_No skills yet._"
)

readme = ROOT / "README.md"
content = readme.read_text(encoding="utf-8")
new = re.sub(
    r"(<!-- skills:start -->\n).*?(<!-- skills:end -->)",
    lambda m: m.group(1) + table + "\n" + m.group(2),
    content,
    flags=re.S,
)
readme.write_text(new, encoding="utf-8")
print(f"README.md: {len(rows)} skill(s) in catalog")

mp_path = ROOT / ".claude-plugin" / "marketplace.json"
if mp_path.is_file():
    mp = json.loads(mp_path.read_text(encoding="utf-8"))
    if mp.get("plugins"):
        mp["plugins"][0]["skills"] = [f"./skills/{d.name}" for d in skill_dirs]
        mp_path.write_text(json.dumps(mp, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"marketplace.json: {len(skill_dirs)} skill(s) listed")
