"""Discovers AWS accounts/roles visible to an SSO session's cached token.

Lets the maintenance menu offer picking accounts/roles from what the SSO
portal actually grants, instead of typing account IDs and role names by
hand. There's no public "give me my current token" command, so after
`aws sso login --sso-session <name>` we read it straight out of the AWS
CLI's own local token cache, then drive it through the standard
`aws sso list-accounts` / `list-account-roles` subcommands.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SSO_CACHE_DIR = Path.home() / ".aws" / "sso" / "cache"


def _parse_expiry(expires_at: str) -> datetime:
    return datetime.strptime(expires_at.replace("UTC", ""), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def find_cached_token(sso_start_url: str) -> str | None:
    if not SSO_CACHE_DIR.exists():
        return None

    for cache_file in SSO_CACHE_DIR.glob("*.json"):
        try:
            data = json.loads(cache_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        if data.get("startUrl") != sso_start_url or "accessToken" not in data:
            continue

        try:
            if _parse_expiry(data["expiresAt"]) <= datetime.now(timezone.utc):
                continue
        except (KeyError, ValueError):
            continue

        return data["accessToken"]

    return None


def _paged(command: list[str], list_key: str) -> list[dict]:
    items: list[dict] = []
    next_token: str | None = None

    while True:
        cmd = command + (["--next-token", next_token] if next_token else [])
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        data = json.loads(result.stdout)
        items.extend(data.get(list_key, []))
        next_token = data.get("nextToken")
        if not next_token:
            return items


def list_accounts(access_token: str, region: str) -> list[dict]:
    command = ["aws", "sso", "list-accounts", "--access-token", access_token, "--region", region, "--output", "json"]
    return _paged(command, "accountList")


def list_account_roles(access_token: str, account_id: str, region: str) -> list[dict]:
    command = [
        "aws",
        "sso",
        "list-account-roles",
        "--access-token",
        access_token,
        "--account-id",
        account_id,
        "--region",
        region,
        "--output",
        "json",
    ]
    return _paged(command, "roleList")
