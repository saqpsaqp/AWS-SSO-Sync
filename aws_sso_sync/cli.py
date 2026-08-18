"""Main menu: sync credentials, maintain tenants/accounts, or self-update."""

from __future__ import annotations

import os
import subprocess
import sys

from . import config, menu_login, menu_maintenance
from .preflight import check_aws_cli


def _update() -> None:
    home = os.environ.get("AWS_SSO_SYNC_HOME")
    if not home:
        print("\n  ⚠️  No se detectó AWS_SSO_SYNC_HOME (¿instalaste con install.sh?).")
        print("     Corre 'update.sh' manualmente desde tu checkout del repo.\n")
        return

    print(f"\n  🔄 Actualizando desde git en {home} ...\n")
    result = subprocess.run(["git", "-C", home, "pull", "--ff-only"])
    if result.returncode != 0:
        print("\n  ❌ Falló 'git pull'. Revisa el mensaje de arriba.\n")
        return

    subprocess.run([sys.executable, "-m", "pip", "install", "-e", home, "--quiet"])
    print("\n  ✅ Actualizado.\n")


def main() -> None:
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
