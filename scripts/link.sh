#!/usr/bin/env bash
# Symlink every skill in this repo into each installed agent's skills directory.
#
# An agent counts as installed when its home directory exists (claude: ~/.claude
# or $CLAUDE_CONFIG_DIR, openclaw: ~/.openclaw or ~/.agents, hermes: ~/.hermes).
# Set LINK_ALL=1 to link for every agent regardless.
#
# Claude Code can run against more than one config directory (the default
# ~/.claude, or whatever $CLAUDE_CONFIG_DIR points at), so the claude agent
# links into every one it finds.
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

known_agent() {
  case " $all_agents " in *" $1 "*) return 0 ;; *) return 1 ;; esac
}

# Strip every trailing slash without collapsing the filesystem root. Preserve
# leading and trailing spaces instead of treating them as separators.
normalize_config_dir() {
  local d="$1"
  while [ "$d" != "/" ] && [ "${d%/}" != "$d" ]; do
    d="${d%/}"
  done
  printf '%s\n' "$d"
}

# Every Claude Code config dir to link into: the single directory
# $CLAUDE_CONFIG_DIR names (always honoured, matching how Claude Code treats
# it) plus the default ~/.claude when it exists. Normalize before dedup. Uses
# if, not bare `test && print` lists: a trailing failed test would leave the
# block with status 1, which pipefail turns into a bogus failure of the whole
# function.
claude_config_dirs() {
  {
    if [ -n "${CLAUDE_CONFIG_DIR:-}" ]; then
      normalize_config_dir "$CLAUDE_CONFIG_DIR"
    fi
    if [ -d "$HOME/.claude" ] || [ "${LINK_ALL:-0}" = "1" ]; then
      normalize_config_dir "$HOME/.claude"
    fi
  } | awk 'length($0) && !seen[$0]++'
}

# Skills directories for an agent, one per line; empty when it isn't installed.
targets_for() {
  case "$1" in
    claude)
      claude_config_dirs | while IFS= read -r d; do
        printf '%s\n' "${d%/}/skills"
      done
      ;;
    openclaw)
      { [ -d "$HOME/.openclaw" ] || [ -d "$HOME/.agents" ] || [ "${LINK_ALL:-0}" = "1" ]; } &&
        echo "$HOME/.agents/skills"
      ;;
    hermes)
      { [ -d "$HOME/.hermes" ] || [ "${LINK_ALL:-0}" = "1" ]; } &&
        echo "$HOME/.hermes/skills"
      ;;
    *) return 1 ;;
  esac
  return 0
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
    if ! known_agent "$agent"; then
      echo "warn: $name lists unknown agent '$agent' (known: $all_agents)" >&2
      continue
    fi
    dests="$(targets_for "$agent")"
    if [ -z "$dests" ]; then
      echo "skip: $name -> $agent (not installed; LINK_ALL=1 to force)"
      continue
    fi
    while IFS= read -r dest; do
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
    done <<< "$dests"
  done
done

# Claude 전용 자산: output style과 slash command 파일을 각 Claude config dir에
# 개별 파일 단위로 링크한다. 다른 에이전트에는 해당 개념이 없다.
for kind in output-styles commands; do
  src_dir="$repo_root/$kind"
  [ -d "$src_dir" ] || continue
  cfg_dirs="$(claude_config_dirs)"
  if [ -z "$cfg_dirs" ]; then
    echo "skip: $kind -> claude (not installed; LINK_ALL=1 to force)"
    continue
  fi
  while IFS= read -r cfg; do
    dest="$cfg/$kind"
    for f in "$src_dir"/*.md; do
      [ -f "$f" ] || continue
      mkdir -p "$dest"
      link="$dest/$(basename "$f")"
      if [ -L "$link" ]; then
        current="$(readlink "$link")"
        if [ "$current" != "$f" ]; then
          echo "warn: $kind/$(basename "$f") -> claude replaces existing link (was -> $current)" >&2
        fi
        rm "$link"
      elif [ -e "$link" ]; then
        echo "skip: $link exists and is not a symlink" >&2
        continue
      fi
      ln -s "$f" "$link"
      echo "linked: $kind/$(basename "$f") -> claude ($link)"
      linked=$((linked + 1))
    done
  done <<< "$cfg_dirs"
done
echo "done: $linked link(s) created."
