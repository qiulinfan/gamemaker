#!/bin/sh
# Skills-only Claude Code linker for the autota product checkout.
#
# Links each skills/<name> of this checkout into the Claude Code user Skill
# directory as an individually owned symlink, so local edits are visible
# immediately. It installs no agents, workflow manifests, or receipts: the
# full product integration stays Codex-only (the receipt-backed `scripts/link.sh` / `scripts/link.ps1` contract),
# and porting it to Claude Code is a separate project.
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
skills_repo_dir="$repo_root/skills"
claude_root=${CLAUDE_CONFIG_DIR:-"$HOME/.claude"}
claude_skills_dir="$claude_root/skills"

[ -d "$skills_repo_dir" ] || {
  printf 'missing product skills directory: %s\n' "$skills_repo_dir" >&2
  exit 1
}
if [ -L "$claude_skills_dir" ]; then
  printf 'conflict: %s must be a Claude Code-owned real directory, not a link\n' \
    "$claude_skills_dir" >&2
  exit 1
fi
mkdir -p "$claude_skills_dir"

# Remove links this checkout owns that are stale or renamed. Links owned by
# qlblog or other product checkouts are never touched.
for existing in "$claude_skills_dir"/*; do
  [ -L "$existing" ] || continue
  link_target=$(readlink "$existing")
  case "$link_target" in
    "$skills_repo_dir"/*) ;;
    *) continue ;;
  esac
  if [ -f "$link_target/SKILL.md" ] &&
    [ "$(basename "$link_target")" = "$(basename "$existing")" ]; then
    continue
  fi
  unlink "$existing"
  printf 'removed stale autota Skill link: %s\n' "$existing"
done

linked=0
for source_dir in "$skills_repo_dir"/*/; do
  source_dir=${source_dir%/}
  [ -f "$source_dir/SKILL.md" ] || continue
  entry_name=$(basename "$source_dir")
  destination="$claude_skills_dir/$entry_name"
  if [ -L "$destination" ]; then
    [ "$(realpath "$destination")" = "$(realpath "$source_dir")" ] || {
      printf 'conflict: %s points to %s\n' "$destination" "$(readlink "$destination")" >&2
      exit 1
    }
  elif [ -e "$destination" ]; then
    printf 'conflict: existing real file or directory is never replaced: %s\n' \
      "$destination" >&2
    exit 1
  else
    ln -s "$source_dir" "$destination"
  fi
  linked=$((linked + 1))
done

printf 'ok: linked %s autota Skills into %s (skills-only; agents and workflows stay Codex-only)\n' \
  "$linked" "$claude_skills_dir"
