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
# or, without installing:
python3 -m aws_sso_sync
```

It's interactive. There is no test suite, build step, or linter configured in this repo — verification is `python3 -m py_compile aws_sso_sync/*.py` plus manual menu walkthroughs (see `docs/USAGE.md`).

## Architecture

- **`aws_sso_sync/config.py`** — the source of truth for tenants/accounts, replacing the old hardcoded dict. Persists to `~/.config/aws-sso-sync/config.json` (plain stdlib `json`, no dependency). `Tenant` holds `sso_region`/`sso_session`/`sso_start_url` + a list of `Account` (`label`, `role`, `account_id`, `sso_role_name`, `sso_profile`, `credentials_profile`). Starts empty on first run — nothing is pre-seeded.
- **`aws_sso_sync/aws_config_writer.py`** — provisions `[sso-session <name>]` and `[profile <sso_profile>]` blocks into `~/.aws/config` via `configparser`, called when a tenant/account is created through the maintenance menu. Rewrites the whole file on every call (same trade-off as credentials.py below).
- **`aws_sso_sync/menu_login.py`** — sync menu: pick a tenant or "todos", then within a tenant pick "todas las cuentas" or a comma-separated subset (e.g. `1,3`) shown as `label (role)`. Logs in once per batch (`aws sso login` against the first selected account's `sso_profile`, since all accounts under a tenant share one SSO session) then exports/writes credentials per selected account.
- **`aws_sso_sync/menu_maintenance.py`** — create/edit/delete tenants and accounts. Creating a tenant asks for `sso_region`/`sso_start_url`/session name and writes the `[sso-session]` block; creating an account asks for label/role/account_id/IAM role name, auto-suggests `sso_profile`/`credentials_profile`, and writes the `[profile ...]` block. Deletes only touch `config.json`, never `~/.aws/config`.
- **`aws_sso_sync/credentials.py`** — `export_credentials()` (shells out to `aws configure export-credentials --format process`) and `update_credentials_file()` (upserts a section into `~/.aws/credentials` via `configparser`, rewriting the whole file — manual edits/comments there don't survive a sync). Same behavior as the original single-file script.
- **`aws_sso_sync/browser.py`** — WSL2-only Chrome detection (`is_wsl()` checks `/proc/version`); on native Linux/Mac it leaves `$BROWSER` alone and lets `aws sso login` open the system default browser.
- **`aws_sso_sync/sso.py`** — `sso_login()`, unchanged from the original script's behavior.
- **`aws_sso_sync/preflight.py`** — `check_aws_cli()`, aborts with install instructions if `aws` is missing or isn't v2 (`aws configure export-credentials` doesn't exist in v1). Runs at CLI startup and is duplicated in `install.sh` for the pre-install check.
- **`aws_sso_sync/cli.py`** — main menu (Sincronizar / Mantenimiento / Actualizar aplicación / Salir); the update option runs `git pull --ff-only` in `$AWS_SSO_SYNC_HOME` (set by the `install.sh`-generated launcher) followed by an editable reinstall.

## Installer / updater

`install.sh` validates AWS CLI v2, backs up an existing `~/.aws/credentials` to `~/.aws/credentials.backup-<timestamp>`, creates `.venv/` inside the checkout, installs the package editable, and writes a launcher to `~/.local/bin/aws-sso-sync` that exports `AWS_SSO_SYNC_HOME` before exec'ing the venv's entry point. `update.sh` (and the CLI's own "Actualizar aplicación") just `git pull --ff-only` + reinstall in that same checkout — there's no PyPI package, updates are git-based by design.

## Adding a new tenant/account

Don't edit code — use the "Mantenimiento" menu (`aws_sso_sync/menu_maintenance.py`) from the running CLI. It writes both `~/.config/aws-sso-sync/config.json` and the corresponding `~/.aws/config` blocks.
