"""Main menu: sync credentials, maintain tenants/accounts, or self-update."""

from __future__ import annotations

import argparse
import logging
import os
import platform
import subprocess
import sys

from . import __version__, config, i18n, menu_login, menu_maintenance
from .i18n import t
from .logging_setup import setup_logging
from .preflight import check_aws_cli

logger = logging.getLogger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="aws-sso-sync")
    parser.add_argument(
        "--logs-enabled",
        action="store_true",
        help="Escribe un log detallado de la sesión en ~/.config/aws-sso-sync/logs/",
    )
    return parser.parse_args(argv)


def _language_menu() -> None:
    # Deliberately not translated via t(): if the current language is the
    # wrong one, this screen still has to be readable so the user can find
    # their way back to their own language.
    print("\n  Idioma / Language:\n")
    codes = i18n.available_languages()
    for i, code in enumerate(codes, 1):
        marker = " ✓" if code == i18n.get_language() else ""
        print(f"  [{i}] {i18n.LANGUAGE_NAMES[code]}{marker}")
    print("  [Q] Cancelar / Cancel")

    choice = input("\n  Opción / Option: ").strip().upper()
    if choice == "Q" or not choice:
        return
    if choice.isdigit() and 0 < int(choice) <= len(codes):
        lang = codes[int(choice) - 1]
        i18n.set_language(lang)
        config.save_language(lang)
        print(f"\n  ✅ {t('cli.language.saved', name=i18n.LANGUAGE_NAMES[lang])}\n")
        return
    print("\n  ⚠️  Opción inválida / Invalid option\n")


def _latest_tag(home: str) -> str | None:
    fetch_result = subprocess.run(["git", "-C", home, "fetch", "--tags", "--quiet"], capture_output=True, text=True)
    logger.debug("git fetch stdout: %s", fetch_result.stdout.strip())
    logger.debug("git fetch stderr: %s", fetch_result.stderr.strip())

    tag_result = subprocess.run(
        ["git", "-C", home, "tag", "--list", "v*.*.*", "--sort=-v:refname"],
        capture_output=True,
        text=True,
    )
    tags = tag_result.stdout.split()
    logger.debug("Tags encontrados: %r", tags)
    return tags[0] if tags else None


def _update() -> None:
    home = os.environ.get("AWS_SSO_SYNC_HOME")
    if not home:
        print(t("cli.update.no_home"))
        print(t("cli.update.no_home_hint"))
        return

    print(t("cli.update.updating"))

    tag = _latest_tag(home)
    if not tag:
        print(t("cli.update.no_release"))
        return

    # Only fast-forwards to the latest published release tag, never past it -
    # merged-but-untagged commits on master don't reach installs until
    # someone cuts a release. See CONTRIBUTING.md's "Releasing" section.
    logger.debug("git -C %s merge --ff-only %s", home, tag)
    result = subprocess.run(["git", "-C", home, "merge", "--ff-only", tag], capture_output=True, text=True)
    logger.debug("git merge stdout: %s", result.stdout.strip())
    logger.debug("git merge stderr: %s", result.stderr.strip())
    if result.returncode != 0:
        print(t("cli.update.failed"))
        print(f"     {(result.stderr or result.stdout).strip()}\n")
        return

    pip_result = subprocess.run([sys.executable, "-m", "pip", "install", "-e", home, "--quiet"], capture_output=True, text=True)
    logger.debug("pip install stdout: %s", pip_result.stdout.strip())
    logger.debug("pip install stderr: %s", pip_result.stderr.strip())
    if pip_result.returncode != 0:
        print(t("cli.update.reinstall_failed"))
        print(f"     {pip_result.stderr.strip()}\n")
        return

    print(t("cli.update.done", tag=tag))


def main() -> None:
    args = _parse_args()
    log_path = setup_logging(args.logs_enabled)
    i18n.set_language(config.load_language())
    if log_path:
        print(t("cli.logging_enabled", path=log_path))

    logger.debug("aws-sso-sync %s iniciando (python=%s, platform=%s)", __version__, sys.version.split()[0], platform.platform())

    try:
        check_aws_cli()
    except KeyboardInterrupt:
        print(t("cli.cancelled_startup"))
        sys.exit(0)

    while True:
        try:
            print("\n╔══════════════════════════════════╗")
            print("║       AWS SSO Credential Sync    ║")
            print("╚══════════════════════════════════╝\n")
            print(f"  {t('cli.menu.sync')}")
            print(f"  {t('cli.menu.maintenance')}")
            print(f"  {t('cli.menu.update')}")
            print(f"  {t('cli.menu.language')}")
            print(f"  {t('cli.menu.exit')}\n")

            choice = input(t("common.option_prompt")).strip().upper()
            logger.debug("Menú principal -> opción=%r", choice)
            if choice == "Q":
                print(t("cli.farewell"))
                print("   aws-sso-sync — Saúl Quintero (saulquintero.com.co)\n")
                sys.exit(0)
            elif choice == "1":
                menu_login.run(config.load())
            elif choice == "2":
                menu_maintenance.run(config.load())
            elif choice == "3":
                _update()
            elif choice == "4":
                _language_menu()
            else:
                print(f"  {t('common.invalid_option_retry')}")
        except KeyboardInterrupt:
            # Ctrl+C at any prompt, no matter how deep in a submenu, lands
            # back here uncaught (nothing else in the call stack handles
            # it) - cancel whatever was in progress and redraw this menu.
            logger.debug("Ctrl+C recibido, cancelando y volviendo al menú principal")
            print(t("cli.cancelled"))


if __name__ == "__main__":
    main()
