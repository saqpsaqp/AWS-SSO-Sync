# Usage guide

## Concepts

- **Tenant** — a client/organization (e.g. `Adaggio`). Holds an SSO region,
  an SSO session name, and an SSO start URL, plus a list of accounts.
- **Account** — one AWS account + IAM role pair within a tenant (e.g.
  `Producción (AdministratorAccess)`). Each account maps to:
  - `sso_profile` — the profile name written to `~/.aws/config`, used for
    `aws sso login` / `aws configure export-credentials`.
  - `credentials_profile` — the plain profile name written to
    `~/.aws/credentials` with the exported access key/secret/session token.

All of this lives in `~/.config/aws-sso-sync/config.json`, edited through the
maintenance menu — you shouldn't need to hand-edit it, but the format is
plain JSON if you ever want to inspect or script against it:

```json
{
  "tenants": {
    "Adaggio": {
      "sso_region": "us-east-1",
      "sso_session": "adaggio-sso-session",
      "sso_start_url": "https://xxxx.awsapps.com/start",
      "accounts": [
        {
          "label": "Producción",
          "role": "AdministratorAccess",
          "account_id": "111111111111",
          "sso_role_name": "AdministratorAccess",
          "sso_profile": "adaggio-produccion-sso",
          "credentials_profile": "adaggio-produccion"
        }
      ]
    }
  }
}
```

The config starts empty on first run — nothing is pre-populated.

## Main menu

```
[1] Sincronizar credenciales (login)
[2] Mantenimiento (tenants y cuentas)
[3] Actualizar aplicación
[Q] Salir
```

## 1. Sincronizar credenciales (login)

1. Pick a tenant by number, or `[A]` to sync every tenant's every account.
2. If you picked a single tenant, pick `[A]` for all its accounts, or a
   comma-separated list of indices (e.g. `1,3`) for a subset — e.g. just
   Producción and Staging of Adaggio.
3. The tool runs `aws sso login` **once**, using the first selected account's
   `sso_profile` (all accounts under a tenant are expected to share one SSO
   session, so a single browser login covers the whole batch).
4. For each selected account it runs
   `aws configure export-credentials --profile <sso_profile> --format process`
   and upserts the result into `~/.aws/credentials` under
   `[<credentials_profile>]`.

`~/.aws/credentials` is rewritten in full on every sync (via `configparser`),
so any manual edits/comments in that file won't survive the next run — this
matches how the original single-file script behaved.

## 2. Mantenimiento (tenants y cuentas)

```
[1] Crear tenant nuevo
[2] Agregar cuenta/rol a un tenant existente
[3] Editar cuenta
[4] Eliminar cuenta
[5] Eliminar tenant
[6] Ver configuración actual
[Q] Volver
```

- **Crear tenant nuevo** — asks for the SSO region, SSO start URL, and a
  session name (auto-suggested). Writes `[sso-session <name>]` into
  `~/.aws/config` and an empty tenant entry into `config.json`. Offers to add
  the first account right away.
- **Agregar cuenta/rol** — asks for a label, a role/purpose tag, the 12-digit
  AWS account ID, and the IAM role name for SSO. Profile names
  (`sso_profile`/`credentials_profile`) are auto-suggested from the tenant
  and label but editable. Writes `[profile <sso_profile>]` into
  `~/.aws/config` (referencing the tenant's `sso-session`) and appends the
  account to `config.json`.
- **Editar cuenta** — lets you change label, role tag, and
  `credentials_profile`. Changing `sso_profile`/`account_id` requires
  deleting and recreating the account (they're tied to the provisioned
  `~/.aws/config` block).
- **Eliminar cuenta / Eliminar tenant** — remove entries from `config.json`
  only. The corresponding `[profile ...]` / `[sso-session ...]` blocks in
  `~/.aws/config` are left in place; delete them by hand if you no longer
  need them.
- **Ver configuración actual** — prints every tenant and account currently
  registered.

Provisioning writes to `~/.aws/config` also rewrite that file in full via
`configparser`, so manual comments/formatting in it won't be preserved
across a create/edit.

## 3. Actualizar aplicación

Runs `git pull --ff-only` in the checkout you installed from (tracked via the
`AWS_SSO_SYNC_HOME` environment variable set by `install.sh`'s launcher),
then reinstalls the package in editable mode. Equivalent to running
`./update.sh` from your checkout directory.

If `AWS_SSO_SYNC_HOME` isn't set (e.g. you installed some other way), the
menu tells you to run `update.sh` manually.

## Troubleshooting

- **`aws-sso-sync: command not found`** — `~/.local/bin` isn't on your
  `PATH`. Add `export PATH="$HOME/.local/bin:$PATH"` to your shell rc file
  and open a new terminal, or re-run `./install.sh`, which prints the exact
  line for your shell.
- **"Se requiere AWS CLI v2"** — you have AWS CLI v1 installed, or none at
  all. `aws configure export-credentials` only exists in v2; install/upgrade
  from the
  [official docs](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).
- **Lost your previous `~/.aws/credentials`** — `install.sh` backs it up to
  `~/.aws/credentials.backup-<timestamp>` before anything else runs; check
  for that file next to it.
- **WSL2 and the browser doesn't open** — the tool auto-detects WSL and
  points `aws sso login` at Windows Chrome under `/mnt/c/...`. If it's not
  found in the standard install paths, set `BROWSER` yourself before running
  the CLI: `export BROWSER='/mnt/c/Program Files/Google/Chrome/Application/chrome.exe'`.
  On native Linux/macOS this detection is skipped entirely — the system's
  default browser is used.
