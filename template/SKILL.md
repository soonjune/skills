---
name: my-skill
description: What this skill does AND when to use it, in one line (max 1024 chars). Include the concrete trigger words a request would contain, in every language the owner actually uses. This line sits in every agent's context at all times; the body below loads only on activation.
license: MIT
metadata:
  author: soonjune
  source: https://github.com/soonjune/skills
  # agents: claude openclaw hermes   <- optional; omit to enable for all agents
---

# My Skill

One-sentence statement of the job this skill does.

## When to use

- Situations and example requests that should trigger this skill.

## Instructions

1. Imperative, step-by-step.
2. Keep this file under 500 lines; move long reference material into `references/<topic>.md` and say when to load each file.
3. Put runnable helpers in `scripts/` and reference them by relative path.
