"""Browser handling for `aws sso login`.

Only WSL2 needs help: there's no local browser, so we point BROWSER at a
Windows-side Chrome binary under /mnt/c/. Native Linux/Mac installs are left
alone so `aws sso login` opens the system's default browser on its own.
"""

from __future__ import annotations

import os
from pathlib import Path

CHROME_PATHS = [
    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
    "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    f"/mnt/c/Users/{os.environ.get('USER', '')}/AppData/Local/Google/Chrome/Application/chrome.exe",
]


def is_wsl() -> bool:
    proc_version = Path("/proc/version")
    if not proc_version.exists():
        return False
    return "microsoft" in proc_version.read_text().lower()


def find_chrome() -> str | None:
    for path in CHROME_PATHS:
        if Path(path).exists():
            return path
    return None


def build_env() -> dict:
    env = os.environ.copy()
    if not is_wsl() or "BROWSER" in env:
        return env

    chrome = find_chrome()
    if chrome:
        env["BROWSER"] = chrome
    else:
        print("  ⚠️  WSL detectado pero no se encontró Chrome de Windows en las rutas estándar.")
        print("     Setea manualmente: export BROWSER='/mnt/c/...chrome.exe'")
    return env
