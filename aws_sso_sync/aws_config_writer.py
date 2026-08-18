"""Provisions [sso-session ...] and [profile ...] blocks in ~/.aws/config.

Rewrites the whole file via configparser on every call, same trade-off the
original script already accepted for ~/.aws/credentials: manual comments or
formatting in ~/.aws/config are not preserved.
"""

from __future__ import annotations

import configparser
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

AWS_CONFIG_FILE = Path.home() / ".aws" / "config"


def _read() -> configparser.RawConfigParser:
    config = configparser.RawConfigParser()
    if AWS_CONFIG_FILE.exists():
        config.read(AWS_CONFIG_FILE)
    return config


def _write(config: configparser.RawConfigParser) -> None:
    AWS_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(AWS_CONFIG_FILE, "w") as f:
        config.write(f)


def ensure_sso_session(session_name: str, sso_start_url: str, sso_region: str) -> None:
    config = _read()
    section = f"sso-session {session_name}"
    if not config.has_section(section):
        config.add_section(section)
    config.set(section, "sso_start_url", sso_start_url)
    config.set(section, "sso_region", sso_region)
    config.set(section, "sso_registration_scopes", "sso:account:access")
    _write(config)
    logger.debug("Escrito [%s] en %s (sso_start_url=%r, sso_region=%r)", section, AWS_CONFIG_FILE, sso_start_url, sso_region)


def ensure_profile(profile_name: str, session_name: str, account_id: str, role_name: str, region: str) -> None:
    config = _read()
    section = f"profile {profile_name}"
    if not config.has_section(section):
        config.add_section(section)
    config.set(section, "sso_session", session_name)
    config.set(section, "sso_account_id", account_id)
    config.set(section, "sso_role_name", role_name)
    config.set(section, "region", region)
    _write(config)
    logger.debug(
        "Escrito [%s] en %s (sso_session=%r, sso_account_id=%r, sso_role_name=%r)",
        section,
        AWS_CONFIG_FILE,
        session_name,
        account_id,
        role_name,
    )
