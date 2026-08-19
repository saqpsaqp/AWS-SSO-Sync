"""Triggers `aws sso login` for a reference profile."""

from __future__ import annotations

import logging
import subprocess

from .browser import build_env
from .i18n import t

logger = logging.getLogger(__name__)


def sso_login(reference_profile: str) -> bool:
    print(t("sso.login_profile", profile=reference_profile))
    cmd = ["aws", "sso", "login", "--profile", reference_profile]
    logger.debug("Ejecutando: %s", " ".join(cmd))
    result = subprocess.run(cmd, env=build_env())
    logger.debug("returncode=%d", result.returncode)
    if result.returncode != 0:
        print(t("sso.error"))
        return False
    print(t("sso.success"))
    return True


def sso_login_session(session_name: str) -> bool:
    """Logs into an [sso-session] block directly, without needing a profile yet."""
    print(t("sso.login_session", session=session_name))
    cmd = ["aws", "sso", "login", "--sso-session", session_name]
    logger.debug("Ejecutando: %s", " ".join(cmd))
    result = subprocess.run(cmd, env=build_env())
    logger.debug("returncode=%d", result.returncode)
    if result.returncode != 0:
        print(t("sso.error"))
        return False
    print(t("sso.success"))
    return True
