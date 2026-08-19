# skills

Personal [Agent Skills](https://agentskills.io) — portable `SKILL.md` skills for [Claude Code](https://code.claude.com), [OpenClaw](https://openclaw.ai), [Hermes](https://hermes-agent.nousresearch.com), and any agent that speaks the open standard.

Write a skill once, use it from every agent: `scripts/link.sh` symlinks each skill into every agent's personal skills directory, and per-skill frontmatter can restrict a skill to specific agents. This is the public half of a two-repo setup — a private sibling repo with the same layout holds skills that are mine alone.

## Install

**Claude Code** (as a plugin):

```
/plugin marketplace add soonjune/skills
```

**Any agent** (symlinks):

```sh
git clone https://github.com/soonjune/skills ~/skills
~/skills/scripts/link.sh
```

`link.sh` links every skill into each **installed** agent's skills directory (agents whose home dir is missing are skipped; set `LINK_ALL=1` to force all):

| Agent | Skills directory |
|---|---|
| Claude Code | `~/.claude/skills/`, `$CLAUDE_CONFIG_DIR/skills/` |
| OpenClaw | `~/.agents/skills/` |
| Hermes | `~/.hermes/skills/` |

Claude Code reads personal skills from whichever config directory it was launched
with, so `link.sh` links into every one it finds — the default `~/.claude` when it
exists, plus the directory `$CLAUDE_CONFIG_DIR` names. For Claude Code it also
links the repo's `output-styles/*.md` and `commands/*.md` into each config dir
(other agents have no such concept).

Pick one install route per config dir: installing the plugin **and** running
`link.sh` on the same machine loads every skill twice.

Or just copy a single skill directory — every `SKILL.md` carries its own `license` and `metadata.source`, so provenance travels with the file.

## Skills

<!-- skills:start -->
| Skill | Description | Agents |
| --- | --- | --- |
| [`natural-korean`](skills/natural-korean) | 한국어 보고서·PPT·이메일·회의록·공지·번역문·코드 주석·커밋 메시지를 작성하거나 다듬을 때 문서와 독자에 맞는 자연스러운 문체를 적용하고, "AI 티 빼줘", "AI스러운 표현 빼줘", "번역투 고쳐", "자연스럽게 써줘", "개조식으로", "말투 고쳐", "앞으로 이렇게 써" 같은 요청과 사람이 고친 문체를 로컬 취향 후보로 정리한다. | all |
| [`new-skill`](skills/new-skill) | Scaffold a new skill in this skills repository — copies the template, enforces Agent Skills spec conventions, refreshes the catalog and marketplace manifest, and relinks agent skill directories. | all |
| [`nightshift`](skills/nightshift) | Executes a user-written handoff document overnight as an unattended autonomous work session — running prioritized missions (implementation and verification, performance improvement, research, data generation, long-running job babysitting) under strict guardrails with an append-only journal, then producing a polished Korean morning report for 조간보고/scrum by a hard deadline. | all |
<!-- skills:end -->

## Anatomy of a skill

```
skills/<name>/
├── SKILL.md          # frontmatter (name, description) + instructions
├── references/       # optional: docs loaded on demand
└── scripts/          # optional: executable helpers
```

Agents load only `name` + `description` at startup and read the full body on activation (progressive disclosure), so a large skill collection stays cheap in context.

## Adding a skill

```sh
cp -r template skills/my-skill
$EDITOR skills/my-skill/SKILL.md
python3 scripts/validate.py     # Agent Skills spec conformance
python3 scripts/catalog.py      # refresh the table above + marketplace.json
scripts/link.sh                 # make it live locally
```

To restrict a skill to specific agents:

```yaml
metadata:
  agents: claude openclaw
```

## Korean output layer

`output-styles/natural-korean-understanding.md` is an always-on output style that
keeps Claude's Korean narration comprehensible (particle/ending restoration, full
sentences, common vocabulary). It complements the `natural-korean` skill: the
style governs conversation, the skill governs deliverables, and each defers to
the other in the other's territory. `evals/` holds a paired plain/styled
`claude plugin eval` suite that measures the style's effect; see `evals/README.md`.

## License

[MIT](LICENSE). Skill files also declare `license` in frontmatter so attribution survives copy-paste. `output-styles/natural-korean-understanding.md` is vendored from [snflkd/fluent-korean](https://github.com/snflkd/fluent-korean) (MIT) with local adaptations recorded in its header comment.
