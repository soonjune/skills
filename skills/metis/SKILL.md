---
name: metis
description: Ground crucial option questions in Claude Code or Codex plan mode with clickable evidence recycled from files and URLs already opened during planning. Use when asking the user to choose architecture, module boundaries, data models, dependencies or services, security/cost/performance tradeoffs, or other hard-to-reverse approaches. Keep trivial preferences plain, and never explore solely to decorate a choice.
license: MIT
metadata:
  author: soonjune
  source: https://github.com/soonjune/skills
  agents: claude codex
---

# Metis

Make crucial planning choices reviewable: show what each option changes, the evidence already examined for it, and its tradeoff before asking the human to decide.

## Apply only to crucial decisions

- In Claude Code or Codex plan mode, use this before asking the user to choose between consequential approaches.
- A decision is **crucial** when it sets architecture or module boundaries, changes a data model or schema, adds or swaps an external dependency or service, trades off security, cost, or performance, or is hard to reverse later.
- Everything else — naming, formatting, style, ordering, pure preference — is trivial: ask plain options with no decoration.
- Ask one crucial decision at a time so its evidence stays attributable to the right options.

## Evidence contract

- **Recycle, never research for decoration.** Use only files and URLs already opened while planning. Do not re-open a file merely to harvest line numbers.
- Give every crucial option its concrete effect, up to three relevant evidence references, and one tradeoff. If an option's area was not examined, write `not yet explored` instead of inventing grounds.
- Companion reading is optional: add `See also` with zero to two already-opened references only when they materially help the comparison.
- If no option has any recycled evidence, ask the question plainly and state that limitation in one line above it.
- Keep each option block to six lines or fewer. A path without a line number is acceptable when that is all the session has.
- **Labels follow the conversation language.** The templates below use English labels (`Tradeoff:`, `See also:`, `not yet explored`); render their equivalents in the conversation language.

Immediately before the question tool, print one block per option:

```text
### <option label>
<what choosing this concretely changes — 1–2 lines>
Evidence: <0–3 clickable file or URL references>
Tradeoff: <one line>
See also: <0–2 optional companion references>
```

Omit `See also` when empty. Keep `Evidence: not yet explored` when only that option lacks grounds.

## Claude Code — AskUserQuestion

- Treat the message blocks as the primary review surface; keep option labels short and descriptions to one grounded sentence.
- Put the recommended option first and explain why in its description. Do not rely on a bare `(Recommended)` marker.
- Add an option `preview` only when the current AskUserQuestion schema explicitly exposes that field. If available, reuse the same compact block; otherwise do not send an unsupported field.
- Use bare `path:line` references and URLs in the message blocks so the terminal can linkify them. The same blocks work for single- and multi-select questions.

## Codex — request_user_input

- Print the option blocks as commentary immediately before calling `request_user_input`; its short labels and descriptions are not a rich evidence surface.
- For local files, display `path:line` but use the host's clickable Markdown file-link form with an absolute target. Use normal Markdown links for visited URLs.
- Follow the tool's current option contract, including its recommendation marker and ordering rules. If the tool is unavailable, use numbered plain-text options after the same evidence blocks.

## Record the choice

After the answer, record the chosen option and a one-line rationale in the plan file when one exists; otherwise carry that line into the proposed plan.

## Auto-activation

- When installed as the Claude Code plugin from this repository, `.claude-plugin/plugin.json` registers `claude-hooks/metis.json`. It invokes `scripts/metis_hook.py` on plan-mode prompts and after `EnterPlanMode`; the hook requires `python3` on `PATH`.
- A standalone symlink or copied skill does not modify Claude user settings. It relies on normal skill routing or explicit invocation.
- In Codex, `agents/openai.yaml` permits implicit invocation. That makes Metis eligible when the description matches; it does not guarantee selection in every planning session.

Dry-run the hook from the repository root:

```sh
echo '{"hook_event_name":"UserPromptSubmit","permission_mode":"plan"}' | python3 skills/metis/scripts/metis_hook.py
```
