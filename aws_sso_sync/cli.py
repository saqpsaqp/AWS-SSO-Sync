"""Main menu: sync credentials, maintain tenants/accounts, or self-update."""

from __future__ import annotations

import argparse
import logging
import os
import platform
import subprocess
import sys

from . import __version__, config, menu_login, menu_maintenance
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
        print("\n  ⚠️  No se detectó AWS_SSO_SYNC_HOME (¿instalaste con install.sh?).")
        print("     Corre 'update.sh' manualmente desde tu checkout del repo.\n")
        return

    print("\n  🔄 Actualizando...")

    tag = _latest_tag(home)
    if not tag:
        print("\n  ⚠️  Todavía no hay ningún release publicado (falta un tag vX.Y.Z).\n")
        return

    # Only fast-forwards to the latest published release tag, never past it -
    # merged-but-untagged commits on master don't reach installs until
    # someone cuts a release. See CONTRIBUTING.md's "Releasing" section.
    logger.debug("git -C %s merge --ff-only %s", home, tag)
    result = subprocess.run(["git", "-C", home, "merge", "--ff-only", tag], capture_output=True, text=True)
    logger.debug("git merge stdout: %s", result.stdout.strip())
    logger.debug("git merge stderr: %s", result.stderr.strip())
    if result.returncode != 0:
        print("\n  ❌ Falló la actualización.")
        print(f"     {(result.stderr or result.stdout).strip()}\n")
        return

    pip_result = subprocess.run([sys.executable, "-m", "pip", "install", "-e", home, "--quiet"], capture_output=True, text=True)
    logger.debug("pip install stdout: %s", pip_result.stdout.strip())
    logger.debug("pip install stderr: %s", pip_result.stderr.strip())
    if pip_result.returncode != 0:
        print("\n  ❌ Falló la reinstalación del paquete.")
        print(f"     {pip_result.stderr.strip()}\n")
        return

    print(f"\n  ✅ Actualización completada ({tag}).\n")


def main() -> None:
    args = _parse_args()
    log_path = setup_logging(args.logs_enabled)
    if log_path:
        print(f"📝 Logging habilitado: {log_path}\n")

    logger.debug("aws-sso-sync %s iniciando (python=%s, platform=%s)", __version__, sys.version.split()[0], platform.platform())

    try:
        check_aws_cli()
    except KeyboardInterrupt:
        print("\n👋 Cancelado.\n")
        sys.exit(0)

    while True:
        try:
            print("\n╔══════════════════════════════════╗")
            print("║       AWS SSO Credential Sync    ║")
            print("╚══════════════════════════════════╝\n")
            print("  [1] Sincronizar credenciales (login)")
            print("  [2] Mantenimiento (tenants y cuentas)")
            print("  [3] Actualizar aplicación")
            print("  [Q] Salir\n")

            choice = input("  Opción: ").strip().upper()
            logger.debug("Menú principal -> opción=%r", choice)
            if choice == "Q":
                print("\n👋 Hasta luego.")
                print("   aws-sso-sync — Saúl Quintero (saulquintero.com.co)\n")
                sys.exit(0)
            elif choice == "1":
                menu_login.run(config.load())
            elif choice == "2":
                menu_maintenance.run(config.load())
            elif choice == "3":
                _update()
            else:
                print("  ⚠️  Opción inválida, intenta de nuevo.")
        except KeyboardInterrupt:
            # Ctrl+C at any prompt, no matter how deep in a submenu, lands
            # back here uncaught (nothing else in the call stack handles
            # it) - cancel whatever was in progress and redraw this menu.
            logger.debug("Ctrl+C recibido, cancelando y volviendo al menú principal")
            print("\n\n  ⚠️  Cancelado. Volviendo al menú principal.\n")


if __name__ == "__main__":
    main()
