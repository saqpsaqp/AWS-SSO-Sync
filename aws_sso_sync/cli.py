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


def _update() -> None:
    home = os.environ.get("AWS_SSO_SYNC_HOME")
    if not home:
        print("\n  ⚠️  No se detectó AWS_SSO_SYNC_HOME (¿instalaste con install.sh?).")
        print("     Corre 'update.sh' manualmente desde tu checkout del repo.\n")
        return

    print(f"\n  🔄 Actualizando desde git en {home} ...\n")
    logger.debug("git -C %s pull --ff-only", home)
    result = subprocess.run(["git", "-C", home, "pull", "--ff-only"])
    if result.returncode != 0:
        print("\n  ❌ Falló 'git pull'. Revisa el mensaje de arriba.\n")
        return

    subprocess.run([sys.executable, "-m", "pip", "install", "-e", home, "--quiet"])
    print("\n  ✅ Actualizado.\n")


def main() -> None:
    args = _parse_args()
    log_path = setup_logging(args.logs_enabled)
    if log_path:
        print(f"📝 Logging habilitado: {log_path}\n")

    logger.debug("aws-sso-sync %s iniciando (python=%s, platform=%s)", __version__, sys.version.split()[0], platform.platform())

    check_aws_cli()

    while True:
        print("\n╔══════════════════════════════════╗")
        print("║       AWS SSO Credential Sync     ║")
        print("╚══════════════════════════════════╝\n")
        print("  [1] Sincronizar credenciales (login)")
        print("  [2] Mantenimiento (tenants y cuentas)")
        print("  [3] Actualizar aplicación")
        print("  [Q] Salir\n")

        choice = input("  Opción: ").strip().upper()
        logger.debug("Menú principal -> opción=%r", choice)
        if choice == "Q":
            print("\n👋 Hasta luego.\n")
            sys.exit(0)
        elif choice == "1":
            menu_login.run(config.load())
        elif choice == "2":
            menu_maintenance.run(config.load())
        elif choice == "3":
            _update()
        else:
            print("  ⚠️  Opción inválida, intenta de nuevo.")


if __name__ == "__main__":
    main()
