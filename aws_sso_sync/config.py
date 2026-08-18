"""Persistent tenant/account configuration for aws-sso-sync.

Stored as plain JSON (stdlib only, no extra runtime dependency) at
~/.config/aws-sso-sync/config.json. This is the source of truth the
maintenance menu edits; it starts empty on first run.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "aws-sso-sync"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class Account:
    label: str
    role: str
    account_id: str
    sso_role_name: str
    sso_profile: str
    credentials_profile: str


@dataclass
class Tenant:
    sso_region: str
    sso_session: str
    sso_start_url: str
    accounts: list[Account] = field(default_factory=list)


def slugify(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", text.strip().lower())
    return text.strip("-")


def load() -> dict[str, Tenant]:
    if not CONFIG_FILE.exists():
        save({})
        return {}

    raw = json.loads(CONFIG_FILE.read_text())
    tenants: dict[str, Tenant] = {}
    for name, t in raw.get("tenants", {}).items():
        accounts = [Account(**a) for a in t.get("accounts", [])]
        tenants[name] = Tenant(
            sso_region=t["sso_region"],
            sso_session=t["sso_session"],
            sso_start_url=t["sso_start_url"],
            accounts=accounts,
        )
    return tenants


def save(tenants: dict[str, Tenant]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "tenants": {
            name: {
                "sso_region": t.sso_region,
                "sso_session": t.sso_session,
                "sso_start_url": t.sso_start_url,
                "accounts": [asdict(a) for a in t.accounts],
            }
            for name, t in tenants.items()
        }
    }
    CONFIG_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
