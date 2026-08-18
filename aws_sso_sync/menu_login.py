"""Interactive menu to sync credentials: whole tenant, or selected accounts."""

from __future__ import annotations

from .config import Account, Tenant
from .credentials import CREDENTIALS_FILE, export_credentials, update_credentials_file
from .sso import sso_login


def _select_tenant(tenants: dict[str, Tenant]):
    names = list(tenants.keys())
    if not names:
        print("\n  ⚠️  No hay tenants configurados todavía. Usa el menú de mantenimiento para crear uno.\n")
        return None, None

    print("\n  Selecciona el tenant a sincronizar:\n")
    for i, name in enumerate(names, 1):
        print(f"  [{i}] {name}  ({len(tenants[name].accounts)} cuentas)")

    all_count = sum(len(t.accounts) for t in tenants.values())
    print(f"\n  [A] Todos los tenants  ({all_count} cuentas)")
    print("  [Q] Volver\n")

    while True:
        choice = input("  Opción: ").strip().upper()
        if choice == "Q":
            return None, None
        if choice == "A":
            return "ALL", None
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(names):
                name = names[idx]
                return name, tenants[name]
        print("  ⚠️  Opción inválida, intenta de nuevo.")


def _select_accounts(tenant_name: str, tenant: Tenant) -> list[Account]:
    accounts = tenant.accounts
    if not accounts:
        print(f"\n  ⚠️  {tenant_name} no tiene cuentas configuradas todavía.\n")
        return []

    print(f"\n  Selecciona cuentas de {tenant_name}:\n")
    for i, acc in enumerate(accounts, 1):
        role = f" ({acc.role})" if acc.role else ""
        print(f"  [{i}] {acc.label}{role}")
    print("\n  [A] Todas las cuentas")
    print("  [Q] Volver\n")

    while True:
        choice = input("  Opción (ej: 1,3): ").strip().upper()
        if choice == "Q":
            return []
        if choice == "A":
            return accounts
        indices = [c.strip() for c in choice.split(",") if c.strip()]
        if indices and all(i.isdigit() and 0 < int(i) <= len(accounts) for i in indices):
            return [accounts[int(i) - 1] for i in indices]
        print("  ⚠️  Opción inválida, intenta de nuevo.")


def _sync_accounts(tenant_name: str, accounts: list[Account]) -> None:
    if not accounts:
        return

    print(f"\n┌─ {tenant_name} {'─' * max(1, 30 - len(tenant_name))}")

    if not sso_login(accounts[0].sso_profile):
        print("└─ ❌ Abortado.\n")
        return

    ok, fail = 0, 0
    for acc in accounts:
        print(f"│  🔄 [{acc.sso_profile}] → [{acc.credentials_profile}]", end=" ")
        try:
            creds = export_credentials(acc.sso_profile)
            update_credentials_file(acc.credentials_profile, creds)
            print("✅")
            ok += 1
        except Exception as e:
            print(f"❌\n│     {e}")
            fail += 1

    print(f"└─ {ok} ok" + (f"  {fail} errores" if fail else "") + "\n")


def run(tenants: dict[str, Tenant]) -> None:
    tenant_name, tenant = _select_tenant(tenants)
    if tenant_name is None:
        return

    if tenant_name == "ALL":
        for name, t in tenants.items():
            _sync_accounts(name, t.accounts)
    else:
        accounts = _select_accounts(tenant_name, tenant)
        _sync_accounts(tenant_name, accounts)

    print(f"📄 Credenciales en: {CREDENTIALS_FILE}\n")
