"""Validates the AWS CLI is installed and is v2 before anything else runs.

`aws configure export-credentials` (used by credentials.py) doesn't exist in
AWS CLI v1, so this check has to happen before any sync attempt.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys

from .i18n import t

logger = logging.getLogger(__name__)

INSTALL_DOCS_URL = "https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"


def check_aws_cli() -> None:
    aws_path = shutil.which("aws")
    logger.debug("aws CLI en PATH: %s", aws_path)
    if not aws_path:
        print(t("preflight.aws_not_found"))
        print(t("preflight.install_hint", url=INSTALL_DOCS_URL))
        sys.exit(1)

    result = subprocess.run(["aws", "--version"], capture_output=True, text=True)
    version_output = (result.stdout or "") + (result.stderr or "")
    logger.debug("aws --version -> %s", version_output.strip())
    if "aws-cli/2" not in version_output:
        print(t("preflight.wrong_version", version=version_output.strip() or t("preflight.unknown")))
        print(t("preflight.v1_note"))
        print(t("preflight.update_hint", url=INSTALL_DOCS_URL))
        sys.exit(1)
