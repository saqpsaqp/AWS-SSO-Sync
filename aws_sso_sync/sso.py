"""Triggers `aws sso login` for a reference profile."""

from __future__ import annotations

import subprocess

from .browser import build_env


def sso_login(reference_profile: str) -> bool:
    print(f"\n  🔐 SSO login → perfil: {reference_profile}")
    result = subprocess.run(
        ["aws", "sso", "login", "--profile", reference_profile],
        env=build_env(),
    )
    if result.returncode != 0:
        print("  ❌ Error durante sso login.")
        return False
    print("  ✅ Login exitoso.")
    return True


def sso_login_session(session_name: str) -> bool:
    """Logs into an [sso-session] block directly, without needing a profile yet."""
    print(f"\n  🔐 SSO login → sesión: {session_name}")
    result = subprocess.run(
        ["aws", "sso", "login", "--sso-session", session_name],
        env=build_env(),
    )
    if result.returncode != 0:
        print("  ❌ Error durante sso login.")
        return False
    print("  ✅ Login exitoso.")
    return True
