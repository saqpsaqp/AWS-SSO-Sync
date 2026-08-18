"""Triggers `aws sso login` for a reference profile."""

from __future__ import annotations

import logging
import subprocess

from .browser import build_env

logger = logging.getLogger(__name__)


def sso_login(reference_profile: str) -> bool:
    print(f"\n  🔐 SSO login → perfil: {reference_profile}")
    cmd = ["aws", "sso", "login", "--profile", reference_profile]
    logger.debug("Ejecutando: %s", " ".join(cmd))
    result = subprocess.run(cmd, env=build_env())
    logger.debug("returncode=%d", result.returncode)
    if result.returncode != 0:
        print("  ❌ Error durante sso login.")
        return False
    print("  ✅ Login exitoso.")
    return True


def sso_login_session(session_name: str) -> bool:
    """Logs into an [sso-session] block directly, without needing a profile yet."""
    print(f"\n  🔐 SSO login → sesión: {session_name}")
    cmd = ["aws", "sso", "login", "--sso-session", session_name]
    logger.debug("Ejecutando: %s", " ".join(cmd))
    result = subprocess.run(cmd, env=build_env())
    logger.debug("returncode=%d", result.returncode)
    if result.returncode != 0:
        print("  ❌ Error durante sso login.")
        return False
    print("  ✅ Login exitoso.")
    return True
