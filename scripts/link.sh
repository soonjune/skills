#!/usr/bin/env bash
# Symlink every skill in this repo into each installed agent's skills directory.
#
# An agent counts as installed when its home directory exists (claude: ~/.claude,
# openclaw: ~/.openclaw or ~/.agents, hermes: ~/.hermes). Set LINK_ALL=1 to link
# for every agent regardless.
#
# By default a skill is linked for every agent. Restrict one by listing agents
# in its frontmatter metadata (space-separated, unquoted):
#
#   metadata:
#     agents: claude openclaw
#
# Usage: scripts/link.sh
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
all_agents="claude openclaw hermes"

target_for() {
  case "$1" in
    claude)   echo "$HOME/.claude/skills" ;;
    openclaw) echo "$HOME/.agents/skills" ;;
    hermes)   echo "$HOME/.hermes/skills" ;;
    *)        return 1 ;;
  esac
}

agent_installed() {
  [ "${LINK_ALL:-0}" = "1" ] && return 0
  case "$1" in
    claude)   [ -d "$HOME/.claude" ] ;;
    openclaw) [ -d "$HOME/.openclaw" ] || [ -d "$HOME/.agents" ] ;;
    hermes)   [ -d "$HOME/.hermes" ] ;;
    *)        return 1 ;;
  esac
}

linked=0
for dir in "$repo_root"/skills/*/; do
  [ -f "${dir}SKILL.md" ] || continue
  name="$(basename "$dir")"

  # agents listed under metadata: in the frontmatter, else all agents
  skill_agents="$(awk '
    /^---[[:space:]]*$/ { fence++; next }
    fence >= 2 { exit }
    fence == 1 && /^[[:space:]]+agents:/ {
      sub(/^[[:space:]]+agents:[[:space:]]*/, "")
      gsub(/[",]/, " ")
      print; exit
    }
  ' "${dir}SKILL.md")"
  [ -n "$skill_agents" ] || skill_agents="$all_agents"

  for agent in $skill_agents; do
    if ! dest="$(target_for "$agent")"; then
      echo "warn: $name lists unknown agent '$agent' (known: $all_agents)" >&2
      continue
    fi
    if ! agent_installed "$agent"; then
      echo "skip: $name -> $agent (not installed; LINK_ALL=1 to force)"
      continue
    fi
    mkdir -p "$dest"
    link="$dest/$name"
    if [ -L "$link" ]; then
      current="$(readlink "$link")"
      if [ "$current" != "${dir%/}" ]; then
        echo "warn: $name -> $agent replaces existing link (was -> $current)" >&2
      fi
      rm "$link"
    elif [ -e "$link" ]; then
      echo "skip: $link exists and is not a symlink" >&2
      continue
    fi
    ln -s "${dir%/}" "$link"
    echo "linked: $name -> $agent ($link)"
    linked=$((linked + 1))
  done
done
echo "done: $linked link(s) created."
