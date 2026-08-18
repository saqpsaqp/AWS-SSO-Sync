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
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SSO_CACHE_DIR = Path.home() / ".aws" / "sso" / "cache"


def _parse_expiry(expires_at: str) -> datetime:
    # botocore has used both a "...Z" suffix and a legacy "...UTC" suffix
    # across versions; normalize either into something fromisoformat takes.
    text = expires_at.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    elif text.endswith("UTC"):
        text = text[: -len("UTC")]
    dt = datetime.fromisoformat(text)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/").lower()


def find_cached_token(sso_start_url: str) -> str | None:
    logger.debug("Buscando token cacheado para start_url=%r en %s", sso_start_url, SSO_CACHE_DIR)

    if not SSO_CACHE_DIR.exists():
        logger.debug("El directorio de caché SSO no existe todavía: %s", SSO_CACHE_DIR)
        return None

    cache_files = sorted(SSO_CACHE_DIR.glob("*.json"))
    logger.debug("Encontrados %d archivo(s) en la caché SSO", len(cache_files))
    target = _normalize_url(sso_start_url)

    for cache_file in cache_files:
        try:
            data = json.loads(cache_file.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.debug("  %s: omitido, no se pudo leer/parsear (%s)", cache_file.name, e)
            continue

        cached_start_url = data.get("startUrl")
        if "accessToken" not in data:
            logger.debug("  %s: omitido, no tiene accessToken (probablemente client registration)", cache_file.name)
            continue
        if not cached_start_url or _normalize_url(cached_start_url) != target:
            logger.debug("  %s: omitido, startUrl=%r no coincide con %r", cache_file.name, cached_start_url, sso_start_url)
            continue

        try:
            expiry = _parse_expiry(data["expiresAt"])
        except (KeyError, ValueError) as e:
            logger.debug("  %s: omitido, no se pudo parsear expiresAt=%r (%s)", cache_file.name, data.get("expiresAt"), e)
            continue

        now = datetime.now(timezone.utc)
        if expiry <= now:
            logger.debug("  %s: omitido, token expirado (expiresAt=%s, ahora=%s)", cache_file.name, expiry, now)
            continue

        logger.debug("  %s: token válido encontrado (expira %s)", cache_file.name, expiry)
        return data["accessToken"]

    logger.debug("Ningún archivo de caché tiene un token válido para start_url=%r", sso_start_url)
    return None


def _redact(cmd: list[str]) -> list[str]:
    redacted = list(cmd)
    for i, part in enumerate(redacted):
        if part == "--access-token" and i + 1 < len(redacted):
            redacted[i + 1] = "<redacted>"
    return redacted


def _paged(command: list[str], list_key: str) -> list[dict]:
    items: list[dict] = []
    next_token: str | None = None

    while True:
        cmd = command + (["--next-token", next_token] if next_token else [])
        logger.debug("Ejecutando: %s", " ".join(_redact(cmd)))
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.debug("  falló (returncode=%d): %s", result.returncode, result.stderr.strip())
            raise RuntimeError(result.stderr.strip())
        data = json.loads(result.stdout)
        page_items = data.get(list_key, [])
        logger.debug("  ok: %d elemento(s) en esta página", len(page_items))
        items.extend(page_items)
        next_token = data.get("nextToken")
        if not next_token:
            logger.debug("Total %s: %d elemento(s)", list_key, len(items))
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
