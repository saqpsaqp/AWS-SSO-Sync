#!/usr/bin/env bash
# PreToolUse/Bash hook: best-effort defense against committing/pushing real
# secrets to this public repo. Content-based (not filename-based) so it
# doesn't false-positive on files merely named *credentials*.py.
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

SECRET_RE='AKIA[0-9A-Z]{16}|aws_secret_access_key[[:space:]]*=|aws_session_token[[:space:]]*=|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----'
SUSPICIOUS_EXT_RE='\.(pem|key|pfx|p12)$'

scan_diff() {
  # $1: diff args passed to `git diff`
  local diff_out
  diff_out="$(git diff $1 -U0 2>/dev/null || true)"
  if printf '%s\n' "$diff_out" | grep -E '^\+' | grep -vE '^\+\+\+' | grep -qE "$SECRET_RE"; then
    return 0
  fi
  return 1
}

scan_names() {
  # $1: diff args passed to `git diff --name-only`
  git diff $1 --name-only 2>/dev/null | grep -qE "$SUSPICIOUS_EXT_RE"
}

if printf '%s\n' "$cmd" | grep -qE '(^|[;&|]+)[[:space:]]*git[[:space:]]+commit\b'; then
  # -a/--all also stages tracked-file modifications right before committing,
  # so the unstaged working-tree diff needs checking too in that case.
  if printf '%s\n' "$cmd" | tr ' ' '\n' | grep -qxE -- '-a|--all'; then
    if scan_diff "" || scan_names ""; then
      deny "El working tree tiene cambios sin agregar que parecen contener credenciales reales de AWS o un archivo de clave privada (.pem/.key/.pfx/.p12), y este commit usa -a/--all. Revisa 'git diff' antes de commitear."
    fi
  fi
  if scan_diff "--cached" || scan_names "--cached"; then
    deny "Lo que está en staging parece contener credenciales reales de AWS o un archivo de clave privada (.pem/.key/.pfx/.p12). Revisa 'git diff --cached' antes de commitear."
  fi
fi

if printf '%s\n' "$cmd" | grep -qE '(^|[;&|]+)[[:space:]]*git[[:space:]]+push\b'; then
  range=""
  if upstream="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)"; then
    range="${upstream}..HEAD"
  else
    branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
    if git rev-parse --verify "origin/${branch}" >/dev/null 2>&1; then
      range="origin/${branch}..HEAD"
    fi
  fi
  if [ -n "$range" ]; then
    if scan_diff "$range" || scan_names "$range"; then
      deny "Alguno de los commits que se van a pushear ($range) parece contener credenciales reales de AWS o un archivo de clave privada. Revisalo antes de pushear a este repo publico."
    fi
  fi
fi

exit 0
