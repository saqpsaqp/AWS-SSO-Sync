"""Optional verbose file logging, enabled only via `aws-sso-sync --logs-enabled`.

Off by default: the app-level logger gets a NullHandler so every
`logger.debug(...)` call elsewhere in the package is a cheap no-op instead
of needing to be guarded by callers.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

LOG_DIR = Path.home() / ".config" / "aws-sso-sync" / "logs"


def setup_logging(enabled: bool) -> Path | None:
    app_logger = logging.getLogger("aws_sso_sync")
    app_logger.handlers.clear()

    if not enabled:
        app_logger.addHandler(logging.NullHandler())
        app_logger.setLevel(logging.WARNING)
        return None

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.DEBUG)
    return log_path
