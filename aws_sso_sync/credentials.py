"""Exports SSO session credentials and writes them into ~/.aws/credentials."""

from __future__ import annotations

import configparser
import json
import subprocess
from pathlib import Path

CREDENTIALS_FILE = Path.home() / ".aws" / "credentials"


def export_credentials(sso_profile: str) -> dict:
    result = subprocess.run(
        ["aws", "configure", "export-credentials", "--profile", sso_profile, "--format", "process"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
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
