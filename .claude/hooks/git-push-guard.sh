#!/usr/bin/env bash
# PreToolUse/Bash hook: enforces the repo's PR-only workflow.
# Blocks `git push --force`/`-f` outright, and blocks any push whose target
# is (or resolves to) master/main directly - all changes must land via a
# branch + pull request (gh pr create).
set -euo pipefail

input="$(cat)"
cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // ""')"

deny() {
  jq -n --arg reason "$1" '{
    systemMessage: ("🚫 Bloqueado: " + $reason),
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $reason
    }
  }'
  exit 0
}

# Only care about `git push` (possibly chained with other commands).
printf '%s\n' "$cmd" | grep -qE '(^|[;&|]+)[[:space:]]*git[[:space:]]+push\b' || exit 0

# Force pushes are blocked outright, to any branch.
if printf '%s\n' "$cmd" | tr ' ' '\n' | grep -qxE -- '--force(-with-lease)?|-f'; then
  deny "git push --force/-f está bloqueado por la política del repo. Si es realmente necesario, que lo ejecute el usuario manualmente fuera de Claude Code."
fi

# Explicit master/main token anywhere (origin master, HEAD:master, origin/main, ...).
if printf '%s\n' "$cmd" | tr ' /:' '\n\n\n' | grep -qxE 'master|main'; then
  deny "No se permite push directo a master/main. Crea un branch y abre un Pull Request (gh pr create)."
fi

# Bare 'git push' / 'git push origin' / 'git push -u origin' with no explicit
# branch pushes the current branch - check what that resolves to.
if printf '%s\n' "$cmd" | grep -qE '^git[[:space:]]+push([[:space:]]+(-u|--set-upstream))?([[:space:]]+origin)?[[:space:]]*$'; then
  current_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  if [ "$current_branch" = "master" ] || [ "$current_branch" = "main" ]; then
    deny "Estás en '$current_branch' y este push la actualizaría directamente. Crea un branch y abre un Pull Request (gh pr create)."
  fi
fi

exit 0
