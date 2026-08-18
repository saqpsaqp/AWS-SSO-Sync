# Security Policy

## What this tool touches

`aws-sso-sync` writes plaintext AWS session credentials (access key,
secret key, session token) to `~/.aws/credentials`, and SSO
session/profile configuration to `~/.aws/config` — this is inherent to how
the AWS CLI itself stores credentials (`aws configure export-credentials`,
`aws sso login`); this tool doesn't invent a new storage format or
location. Nothing is ever sent anywhere other than to AWS's own SSO/STS
endpoints via the AWS CLI, and to the local files above. There is no
telemetry, no external logging endpoint, and no network call this tool
makes on its own beyond invoking `aws`.

The optional `--logs-enabled` debug log
(`~/.config/aws-sso-sync/logs/`) redacts `--access-token` values before
writing subprocess commands to the log, and never writes access keys,
secret keys, or session tokens. If you find a case where it doesn't,
that's a bug — report it (see below).

## Reporting a vulnerability

Please **do not** open a public GitHub issue for a security problem.
Use [GitHub's private security advisory feature](../../security/advisories/new)
on this repository instead, or contact the maintainer directly. Include:

- The version/commit you're using.
- Steps to reproduce.
- What you'd expect to happen instead.

## Repo-level safeguards

- **No direct pushes to `master`/`main`, and no force-pushes.** Enforced
  for Claude Code sessions via `.claude/hooks/git-push-guard.sh`; enable
  branch protection on GitHub so it's enforced for everyone else too. See
  [CONTRIBUTING.md](CONTRIBUTING.md).
- **Best-effort secret scanning** on `git commit`/`git push` via
  `.claude/hooks/git-secret-guard.sh` (content-based: AWS access key IDs,
  `aws_secret_access_key`/`aws_session_token` assignments, PEM private key
  headers, and `.pem`/`.key`/`.pfx`/`.p12` files). This is a safety net,
  not a substitute for reviewing your own diffs — it only runs inside
  Claude Code sessions, and pattern-based scanning can miss things.
- `install.sh` backs up any existing `~/.aws/credentials` before this tool
  ever writes to it.
- **Static analysis on every push/PR**: `.github/workflows/ci.yml` runs
  [ruff](https://docs.astral.sh/ruff/) lint (including its `S` security
  rule set, ported from `flake8-bandit`) and format checks;
  `.github/workflows/codeql.yml` runs GitHub's [CodeQL](https://codeql.github.com/)
  semantic analysis on push, PR, and weekly on a schedule. Both post
  findings as PR checks / the repo's Security tab.
- **Dependency updates**: `.github/dependabot.yml` keeps the GitHub
  Actions versions in the workflows above current. There's no Python
  dependency file to scan — the package has zero runtime dependencies
  beyond the standard library and the AWS CLI itself.
- **Recommended, not yet enabled by this repo's files** (these are GitHub
  repo settings, not something a committed file can turn on): enable
  [secret scanning and push protection](../../settings/security_analysis)
  under Settings → Code security, and branch protection on `master`
  requiring the CI/CodeQL checks and a PR review before merging.
