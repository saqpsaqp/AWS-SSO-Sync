# aws-sso-sync

Interactive CLI that logs into AWS SSO and exports session credentials into
`~/.aws/credentials` under long-lived profile names, so tools that don't
understand `sso_session`/`sso_start_url` config (Terraform, older SDKs, etc.)
can still assume the right role via a plain
`aws_access_key_id`/`aws_secret_access_key`/`aws_session_token` profile.

It's organized around **tenants** (clients / organizations) and **accounts**
(AWS account + IAM role pairs within a tenant, e.g. Production/AdministratorAccess,
Shared/DevOps, Staging/Developer). You manage tenants and accounts from a
maintenance menu, and sync credentials for a whole tenant or just a few
selected accounts.

## Requirements

- **Linux or macOS** (WSL2 works too).
- **Python 3.9+** with `venv` available.
- **AWS CLI v2** on your `PATH` (`aws --version` must report `aws-cli/2...`).
  `aws configure export-credentials`, which this tool relies on, does not
  exist in AWS CLI v1. Install/update it from the
  [official docs](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).
- `git`, to install and later update this tool.

## Install

```bash
git clone https://github.com/saqpsaqp/AWS-SSO-Sync.git
cd AWS-SSO-Sync
./install.sh
```

`install.sh` will:

1. Verify `python3` and AWS CLI v2 are present (aborts with instructions if not).
2. **Back up** `~/.aws/credentials` to `~/.aws/credentials.backup-<timestamp>` if it already exists.
3. Create a local virtualenv at `.venv/` inside this checkout and install the
   package into it in editable mode.
4. Write an `aws-sso-sync` launcher into `~/.local/bin/aws-sso-sync`.

If `~/.local/bin` isn't already on your `PATH`, the installer prints the
exact line to add to your shell's rc file (`~/.bashrc` or `~/.zshrc`):

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Open a new terminal (or `source` your rc file) and run:

```bash
aws-sso-sync
```

## Usage

See [docs/USAGE.md](docs/USAGE.md) for the full menu walkthrough (creating
tenants/accounts, selective login, the config file format) and troubleshooting.

Quick summary of the main menu:

- **Sincronizar credenciales (login)** — pick a tenant (or all of them), then
  pick "todas las cuentas" or a comma-separated selection (e.g. `1,3`) of
  specific accounts to log in and refresh in `~/.aws/credentials`.
- **Mantenimiento (tenants y cuentas)** — create/edit/delete tenants and
  accounts. Creating an account can **discover it from the SSO portal**
  (same accounts/roles you'd see at `https://xxxx.awsapps.com/start/#/`) so
  you only pick a label and profile names, or be entered manually. Either
  way it provisions the matching `[sso-session]` / `[profile ...]` block in
  `~/.aws/config`.
- **Actualizar aplicación** — pulls the latest git revision and refreshes the
  install (same as running `./update.sh`).

Run `aws-sso-sync --logs-enabled` to write a detailed debug log for that
session to `~/.config/aws-sso-sync/logs/` — see
[docs/USAGE.md](docs/USAGE.md#debug-logging) for what it captures.

## Updating

```bash
cd aws-sso-sync   # your checkout
./update.sh
```

or use "Actualizar aplicación" from the CLI's main menu — both do a
`git pull --ff-only` followed by an editable reinstall.

## Configuration storage

- App config (tenants/accounts you create): `~/.config/aws-sso-sync/config.json`.
- AWS SSO profiles it provisions: `~/.aws/config`.
- Exported session credentials: `~/.aws/credentials`.

## License

MIT — see [LICENSE](LICENSE).
