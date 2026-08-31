#!/usr/bin/env python3
"""Inject a concise Metis reminder while Claude Code is in plan mode.

Configured by claude-hooks/metis.json for UserPromptSubmit and for
PostToolUse matching EnterPlanMode. Reads hook JSON on stdin and stays silent
on unrelated or malformed input so it cannot disturb the session.
"""

import json
import sys

REMINDER = (
    "[metis] Plan mode: for CRUCIAL decision questions (architecture, data "
    "model, dependency, security/cost, hard-to-reverse), show every option's "
    "concrete effect, tradeoff, and clickable evidence recycled from files "
    "or URLs already opened this session. Companion links are optional (0-2) "
    "and only when useful. Mark unexamined options 'not yet explored'; never "
    "research just to decorate; keep trivial choices plain."
)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        event = payload.get("hook_event_name")
        prompting_in_plan = (
            event == "UserPromptSubmit" and payload.get("permission_mode") == "plan"
        )
        entering_plan = (
            event == "PostToolUse" and payload.get("tool_name") == "EnterPlanMode"
        )
        if not (prompting_in_plan or entering_plan):
            return
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": event,
                "additionalContext": REMINDER,
            }
        }))
    except Exception:
        pass


if __name__ == "__main__":
    main()
