"""Validates the AWS CLI is installed and is v2 before anything else runs.

`aws configure export-credentials` (used by credentials.py) doesn't exist in
AWS CLI v1, so this check has to happen before any sync attempt.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys

logger = logging.getLogger(__name__)

INSTALL_DOCS_URL = "https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"


def check_aws_cli() -> None:
    aws_path = shutil.which("aws")
    logger.debug("aws CLI en PATH: %s", aws_path)
    if not aws_path:
        print("❌ No se encontró el AWS CLI en el PATH.")
        print(f"   Instálalo: {INSTALL_DOCS_URL}")
        sys.exit(1)

    result = subprocess.run(["aws", "--version"], capture_output=True, text=True)
    version_output = (result.stdout or "") + (result.stderr or "")
    logger.debug("aws --version -> %s", version_output.strip())
    if "aws-cli/2" not in version_output:
        print(f"❌ Se requiere AWS CLI v2 (detectado: {version_output.strip() or 'desconocido'}).")
        print("   'aws configure export-credentials' no existe en AWS CLI v1.")
        print(f"   Instala/actualiza: {INSTALL_DOCS_URL}")
        sys.exit(1)
