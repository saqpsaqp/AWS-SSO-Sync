"""Exports SSO session credentials and writes them into ~/.aws/credentials."""

from __future__ import annotations

import configparser
import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

CREDENTIALS_FILE = Path.home() / ".aws" / "credentials"


def export_credentials(sso_profile: str) -> dict:
    logger.debug("Exportando credenciales para sso_profile=%r", sso_profile)
    result = subprocess.run(
        ["aws", "configure", "export-credentials", "--profile", sso_profile, "--format", "process"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.debug("  falló (returncode=%d): %s", result.returncode, result.stderr.strip())
        raise RuntimeError(result.stderr.strip())
    logger.debug("  ok")
    return json.loads(result.stdout)


def update_credentials_file(profile_name: str, creds: dict) -> None:
    config = configparser.RawConfigParser()
    if CREDENTIALS_FILE.exists():
        config.read(CREDENTIALS_FILE)
    if not config.has_section(profile_name):
        config.add_section(profile_name)
    config.set(profile_name, "aws_access_key_id", creds["AccessKeyId"])
    config.set(profile_name, "aws_secret_access_key", creds["SecretAccessKey"])
    config.set(profile_name, "aws_session_token", creds["SessionToken"])
    CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CREDENTIALS_FILE, "w") as f:
        config.write(f)
    logger.debug("Escrito perfil [%s] en %s", profile_name, CREDENTIALS_FILE)
