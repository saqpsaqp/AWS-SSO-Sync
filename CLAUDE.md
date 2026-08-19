# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An installable Python CLI package (`aws_sso_sync/`) that logs into AWS SSO and exports session credentials into `~/.aws/credentials` under long-lived profile names, so tools that don't understand `sso_session`/`sso_start_url` config (e.g. Terraform, older SDKs) can still assume the right role via a plain `aws_access_key_id`/`aws_secret_access_key`/`aws_session_token` profile.

It's organized around **tenants** (clients/organizations) and **accounts** (an AWS account + IAM role pair within a tenant, e.g. `Producción (AdministratorAccess)`), managed through an interactive maintenance menu rather than a hardcoded dict. The maintenance menu also provisions the matching `[sso-session]`/`[profile ...]` blocks in `~/.aws/config` — it doesn't just assume they already exist.

The package has no runtime dependencies beyond the Python 3 standard library and the AWS CLI v2 (`aws sso login`, `aws configure export-credentials`) being installed and on `PATH`.

## Running

```bash
./install.sh          # one-time: creates .venv/, installs editable, wires ~/.local/bin/aws-sso-sync
aws-sso-sync           # after install.sh, and ~/.local/bin on PATH
aws-sso-sync --logs-enabled  # same, plus a debug log under ~/.config/aws-sso-sync/logs/
# or, without installing:
python3 -m aws_sso_sync
```

It's interactive. There is no test suite or build step — verification is `python3 -m py_compile aws_sso_sync/*.py` plus manual menu walkthroughs (see `docs/USAGE.md`). Linting/formatting is `ruff` (config in `pyproject.toml`'s `[tool.ruff]`, enforced by `.github/workflows/ci.yml`) — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Architecture

- **`aws_sso_sync/config.py`** — the source of truth for tenants/accounts, replacing the old hardcoded dict. Persists to `~/.config/aws-sso-sync/config.json` (plain stdlib `json`, no dependency). `Tenant` holds `sso_region`/`sso_session`/`sso_start_url` + a list of `Account` (`label`, `role`, `account_id`, `sso_role_name`, `sso_profile`, `credentials_profile`). Starts empty on first run — nothing is pre-seeded.
- **`aws_sso_sync/aws_config_writer.py`** — provisions `[sso-session <name>]` and `[profile <sso_profile>]` blocks into `~/.aws/config` via `configparser`, called when a tenant/account is created through the maintenance menu. Rewrites the whole file on every call (same trade-off as credentials.py below).
- **`aws_sso_sync/menu_login.py`** — sync menu: pick a tenant or "todos", then within a tenant pick "todas las cuentas" or a comma-separated subset (e.g. `1,3`) shown as `label (role)`. Logs in once per batch (`aws sso login` against the first selected account's `sso_profile`, since all accounts under a tenant share one SSO session) then exports/writes credentials per selected account.
- **`aws_sso_sync/menu_maintenance.py`** — create/edit/delete tenants and accounts. Creating a tenant asks for `sso_region`/`sso_start_url`/session name and writes the `[sso-session]` block. Creating an account offers two modes: **discover** (via `sso_discovery.py`, only asks for label + profile names — account ID/role name come from what SSO actually grants) or **manual** (label/role/account_id/IAM role name typed by hand, the fallback when discovery has nothing to work with). Either way it auto-suggests `sso_profile`/`credentials_profile` and writes the `[profile ...]` block. Deletes only touch `config.json`, never `~/.aws/config`. `_find_duplicate()` enforces that `(account_id, sso_role_name)` is unique within a tenant — the *label* is just a display name and doesn't factor in (so `Core-Networking-Env` and `core-networking-env` for the same account+role are treated as the same registration and the second is rejected, not silently duplicated). Menu option 7 ("Detectar duplicados") scans existing accounts for any pair already sharing that key, for cleaning up config that predates this check.
- **`aws_sso_sync/sso_discovery.py`** — `find_cached_token()` reads AWS CLI's own SSO token cache (`~/.aws/sso/cache/*.json`, matched by `startUrl`, checked for expiry) since there's no public "get my current token" command; `list_accounts()`/`list_account_roles()` shell out to `aws sso list-accounts`/`list-account-roles` (paginated via `nextToken`) to show exactly what the SSO portal grants, mirroring `https://xxxx.awsapps.com/start/#/`.
- **`aws_sso_sync/credentials.py`** — `export_credentials()` (shells out to `aws configure export-credentials --format process`) and `update_credentials_file()` (upserts a section into `~/.aws/credentials` via `configparser`, rewriting the whole file — manual edits/comments there don't survive a sync). Same behavior as the original single-file script.
- **`aws_sso_sync/browser.py`** — WSL2-only Chrome detection (`is_wsl()` checks `/proc/version`); on native Linux/Mac it leaves `$BROWSER` alone and lets `aws sso login` open the system default browser.
- **`aws_sso_sync/sso.py`** — `sso_login()`, unchanged from the original script's behavior.
- **`aws_sso_sync/preflight.py`** — `check_aws_cli()`, aborts with install instructions if `aws` is missing or isn't v2 (`aws configure export-credentials` doesn't exist in v1). Runs at CLI startup and is duplicated in `install.sh` for the pre-install check.
- **`aws_sso_sync/cli.py`** — main menu (Sincronizar / Mantenimiento / Actualizar aplicación / Salir); the update option fetches tags in `$AWS_SSO_SYNC_HOME` (set by the `install.sh`-generated launcher) and fast-forwards (`git merge --ff-only`) to the latest `vX.Y.Z` tag — deliberately *not* the tip of `master` — followed by an editable reinstall; see "Versioning & releases" below for why. Both subprocess calls run with `capture_output=True` — only a short "Actualizando..." / "✅ Actualización completada (vX.Y.Z)" (or the error text on failure) is printed; the raw `git`/`pip` output only goes to the `--logs-enabled` debug log, never the screen. Parses `--logs-enabled` via `argparse` and calls `logging_setup.setup_logging()` before anything else. Each main-loop iteration is wrapped in `try/except KeyboardInterrupt` — nothing in `menu_login.py`/`menu_maintenance.py` catches it, so Ctrl+C at any prompt, however deep in a submenu, propagates straight up to this one handler and lands back at the main menu instead of crashing with a traceback. The startup `check_aws_cli()` call (before the loop even starts) is wrapped separately, since it isn't covered by the loop's handler. The farewell message on "Salir" carries the author credit (`saulquintero.com.co`) — keep it if this message is ever restructured.
- **`aws_sso_sync/logging_setup.py`** — `setup_logging(enabled)` wires the `aws_sso_sync` logger to a timestamped file under `~/.config/aws-sso-sync/logs/` when `--logs-enabled` is passed, otherwise attaches a `NullHandler` so every `logger.debug(...)` call elsewhere is a cheap no-op. Every module gets its logger via `logging.getLogger(__name__)` and relies on propagation to this one — never log secrets (tokens/keys), only which files/commands were touched and why a decision was made (e.g. `sso_discovery.py`'s cache-file-by-cache-file skip reasons).

## Installer / updater

`install.sh` validates AWS CLI v2, backs up an existing `~/.aws/credentials` to `~/.aws/credentials.backup-<timestamp>`, creates `.venv/` inside the checkout, installs the package editable, and writes a launcher to `~/.local/bin/aws-sso-sync` that exports `AWS_SSO_SYNC_HOME` before exec'ing the venv's entry point. `update.sh` (and the CLI's own "Actualizar aplicación") fetch tags and fast-forward (`git merge --ff-only`) to the latest `vX.Y.Z` tag, then reinstall in that same checkout — there's no PyPI package, updates are git-based by design. This is deliberately anchored to the latest **release tag**, not `master`'s tip: commits merged to `master` (including in-progress work between releases) never reach an install until someone actually cuts a release, so what's running always matches a published, Release-noted version. If no tag exists yet, both refuse to update rather than falling back to `master`.

## Adding a new tenant/account

Don't edit code — use the "Mantenimiento" menu (`aws_sso_sync/menu_maintenance.py`) from the running CLI. It writes both `~/.config/aws-sso-sync/config.json` and the corresponding `~/.aws/config` blocks.

## Versioning & releases

`aws_sso_sync/__init__.py`'s `__version__` is the single source of truth (SemVer, `vMAJOR.MINOR.PATCH`); `pyproject.toml` reads it dynamically (`dynamic = ["version"]`, `[tool.setuptools.dynamic]`) — never hardcode a version string in `pyproject.toml` again. Bumping it and pushing a `vX.Y.Z` git tag triggers `.github/workflows/release.yml`, which creates the GitHub Release automatically (`gh release create --generate-notes`). Full process in [CONTRIBUTING.md](CONTRIBUTING.md#releasing).

## CI / security tooling

- **`.github/workflows/ci.yml`** — on every push/PR to `master`: `py_compile` syntax check, `ruff check`, `ruff format --check`.
- **`.github/workflows/codeql.yml`** — GitHub CodeQL semantic analysis on push/PR/weekly schedule.
- **`.github/dependabot.yml`** — keeps the Actions pinned in the workflows above current (there's no Python dependency file to scan; the package has zero runtime deps).
- Ruff's `S` rule set (ported from `flake8-bandit`) covers basic SAST; `S603`/`S607` are ignored project-wide in `pyproject.toml` with a comment explaining why — they'd otherwise flag every `subprocess.run(["aws", ...])`/`["git", ...])` call, which is this tool's whole purpose, not a vulnerability.
- Repo-level secret scanning / push protection / branch protection are GitHub repo *settings*, not files — see [SECURITY.md](SECURITY.md) for what's recommended but not yet turned on.

## Contribution policy (must follow)

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md) for the full text. Summary, enforced technically where noted:

- **No direct push/merge to `master`.** Every change goes through a branch + pull request (`gh pr create`), even for a single-line fix. `.claude/hooks/git-push-guard.sh` (a project `PreToolUse`/`Bash` hook, see `.claude/settings.json`) blocks direct pushes to `master`/`main` and any `--force`/`-f` push at the tool-call level — but the rule applies regardless of whether the hook is active for a given session.
- **Always branch from an up-to-date `master`.** Before creating a new feature branch, check out the default branch (`master`), fast-forward it (`git pull --ff-only origin master`), and only then `git checkout -b …`. Never start a feature from a stale local `master`.
- **Never commit/push real secrets.** No real AWS access keys, session tokens, or private key files (`.pem`/`.key`/`.pfx`/`.p12`) — this is a public repo. `.claude/hooks/git-secret-guard.sh` does a best-effort content scan on `git commit`/`git push` and blocks matches, but don't rely on it as the only safeguard.
- **Update this file (`CLAUDE.md`) in the same PR whenever you add or change a feature** — new modules, CLI flags, menu options, config fields, etc. This file goes stale fast otherwise.
- **Update `docs/USAGE.md` (and `README.md`'s menu summary if relevant) in the same PR** whenever a menu, flag, or config format changes. Users only have these two docs — there's no in-app help beyond the menus themselves.
