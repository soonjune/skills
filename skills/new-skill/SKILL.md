---
name: new-skill
description: Scaffold a new skill in soonjune's skills repos (public ~/skills or private ~/skills-private) — copies the template, enforces Agent Skills spec conventions, refreshes the catalog, and relinks agent skill directories. Use when asked to create, add, or scaffold a skill (스킬 만들어줘, 새 스킬, add a skill).
license: MIT
metadata:
  author: soonjune
  source: https://github.com/soonjune/skills
---

# New Skill

Create a skill following this repo's conventions. Skills here serve multiple agents (Claude Code, OpenClaw, Hermes) through the Agent Skills open standard, wired up by symlinks.

## Steps

1. **Choose the repo.** Public `~/skills` only for shareable, polished skills; private `~/skills-private` for anything personal — finances, internal tools, half-baked experiments. Default to private when in doubt; graduating later is a plain directory copy.
2. **Name it.** Lowercase letters, digits, hyphens; max 64 chars; no leading/trailing/consecutive hyphens. The directory name must equal the frontmatter `name`.
3. **Scaffold.** From the chosen repo root: `cp -r template skills/<name>`, then edit `skills/<name>/SKILL.md`.
4. **Write the description** (max 1024 chars, one line, third person): what it does AND when to trigger, with concrete phrases in the languages the owner actually uses (Korean + English).
5. **Write the body.** Imperative instructions, under 500 lines. Long reference material goes to `references/*.md` with explicit "load this when..." pointers; runnable helpers go to `scripts/`.
6. **Cross-agent rules.** Shared skills stick to standard frontmatter fields (`name`, `description`, `license`, `compatibility`, `metadata`). To restrict a skill to some agents, set `metadata.agents: claude openclaw hermes` (space-separated subset).
7. **Validate and wire up** from the repo root:

   ```sh
   python3 scripts/validate.py && python3 scripts/catalog.py
   scripts/link.sh
   ```

8. **Commit** in that repo. Never put secrets in skill text — skill files are injected into model context; reference credential file paths or env var names instead.
