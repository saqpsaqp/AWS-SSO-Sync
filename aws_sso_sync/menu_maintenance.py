"""Interactive menu to create/edit/delete tenants and accounts (roles).

Creating a tenant/account also provisions the corresponding [sso-session]/
[profile] block in ~/.aws/config, so a freshly created account is ready for
`aws sso login` without any manual editing.
"""

from __future__ import annotations

from . import aws_config_writer
from .config import Account, Tenant, save, slugify


def _input(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"  {prompt}{suffix}: ").strip()
    return value or default


def _pick_tenant(tenants: dict[str, Tenant]) -> str | None:
    names = list(tenants.keys())
    if not names:
        print("\n  ⚠️  No hay tenants configurados.\n")
        return None
    for i, name in enumerate(names, 1):
        print(f"  [{i}] {name}")
    choice = input("\n  Tenant: ").strip()
    if choice.isdigit() and 0 < int(choice) <= len(names):
        return names[int(choice) - 1]
    print("  ⚠️  Opción inválida.\n")
    return None


def _list_accounts(tenant_name: str, tenant: Tenant) -> list[Account]:
    if not tenant.accounts:
        print(f"\n  {tenant_name} no tiene cuentas.\n")
        return []
    for i, acc in enumerate(tenant.accounts, 1):
        role = f" ({acc.role})" if acc.role else ""
        print(f"  [{i}] {acc.label}{role} → {acc.sso_profile} / {acc.credentials_profile}")
    return tenant.accounts


def _create_tenant(tenants: dict[str, Tenant]) -> None:
    print("\n  ── Crear tenant nuevo ──\n")
    name = _input("Nombre del tenant (ej: Adaggio)")
    if not name:
        print("  ⚠️  Nombre vacío, cancelado.\n")
        return
    if name in tenants:
        print(f"  ⚠️  Ya existe un tenant llamado '{name}'.\n")
        return

    sso_region = _input("Región AWS del SSO (ej: us-east-1)", "us-east-1")
    sso_start_url = _input("SSO start URL (https://xxxx.awsapps.com/start)")
    if not sso_start_url:
        print("  ⚠️  SSO start URL requerida, cancelado.\n")
        return
    sso_session = _input("Nombre de la sso-session", f"{slugify(name)}-sso-session")

    aws_config_writer.ensure_sso_session(sso_session, sso_start_url, sso_region)
    tenants[name] = Tenant(sso_region=sso_region, sso_session=sso_session, sso_start_url=sso_start_url)
    save(tenants)
    print(f"\n  ✅ Tenant '{name}' creado. Bloque [sso-session {sso_session}] escrito en ~/.aws/config.\n")

    if input("  ¿Agregar la primera cuenta ahora? (s/N): ").strip().lower() == "s":
        _create_account(tenants, name)


def _create_account(tenants: dict[str, Tenant], tenant_name: str | None = None) -> None:
    print("\n  ── Agregar cuenta/rol ──\n")
    if not tenants:
        print("  ⚠️  No hay tenants. Crea uno primero.\n")
        return

    if tenant_name is None:
        tenant_name = _pick_tenant(tenants)
        if tenant_name is None:
            return

    tenant = tenants[tenant_name]
    label = _input("Etiqueta visible (ej: Producción)")
    if not label:
        print("  ⚠️  Etiqueta vacía, cancelado.\n")
        return
    role = _input("Rol / propósito (ej: AdministratorAccess)")
    account_id = _input("Account ID de AWS (12 dígitos)")
    if not (account_id.isdigit() and len(account_id) == 12):
        print("  ⚠️  Account ID inválido (deben ser 12 dígitos), cancelado.\n")
        return
    sso_role_name = _input("Nombre del IAM Role para SSO (ej: AdministratorAccess)", role)

    slug = slugify(label)
    tenant_slug = slugify(tenant_name)
    sso_profile = _input("Nombre de perfil SSO en ~/.aws/config", f"{tenant_slug}-{slug}-sso")
    credentials_profile = _input("Nombre de perfil en ~/.aws/credentials", f"{tenant_slug}-{slug}")

    aws_config_writer.ensure_profile(sso_profile, tenant.sso_session, account_id, sso_role_name, tenant.sso_region)
    tenant.accounts.append(
        Account(
            label=label,
            role=role,
            account_id=account_id,
            sso_role_name=sso_role_name,
            sso_profile=sso_profile,
            credentials_profile=credentials_profile,
        )
    )
    save(tenants)
    print(f"\n  ✅ Cuenta '{label}' agregada a {tenant_name}. Bloque [profile {sso_profile}] escrito en ~/.aws/config.\n")


def _edit_account(tenants: dict[str, Tenant]) -> None:
    print("\n  ── Editar cuenta ──\n")
    tenant_name = _pick_tenant(tenants)
    if not tenant_name:
        return
    tenant = tenants[tenant_name]
    accounts = _list_accounts(tenant_name, tenant)
    if not accounts:
        return
    choice = input("\n  Cuenta a editar: ").strip()
    if not (choice.isdigit() and 0 < int(choice) <= len(accounts)):
        print("  ⚠️  Opción inválida.\n")
        return
    acc = accounts[int(choice) - 1]
    acc.label = _input("Etiqueta", acc.label)
    acc.role = _input("Rol / propósito", acc.role)
    acc.credentials_profile = _input("Perfil en ~/.aws/credentials", acc.credentials_profile)
    save(tenants)
    print("\n  ✅ Cuenta actualizada. (Cambiar sso_profile/account_id requiere eliminar y recrear.)\n")


def _delete_account(tenants: dict[str, Tenant]) -> None:
    print("\n  ── Eliminar cuenta ──\n")
    tenant_name = _pick_tenant(tenants)
    if not tenant_name:
        return
    tenant = tenants[tenant_name]
    accounts = _list_accounts(tenant_name, tenant)
    if not accounts:
        return
    choice = input("\n  Cuenta a eliminar: ").strip()
    if not (choice.isdigit() and 0 < int(choice) <= len(accounts)):
        print("  ⚠️  Opción inválida.\n")
        return
    acc = accounts[int(choice) - 1]
    if input(f"  ¿Confirmas eliminar '{acc.label}' de {tenant_name}? (s/N): ").strip().lower() != "s":
        print("  Cancelado.\n")
        return
    tenant.accounts.remove(acc)
    save(tenants)
    print(f"\n  ✅ Cuenta '{acc.label}' eliminada de la configuración de aws-sso-sync.")
    print(f"     Nota: el perfil [profile {acc.sso_profile}] sigue en ~/.aws/config; bórralo a mano si ya no lo necesitas.\n")


def _delete_tenant(tenants: dict[str, Tenant]) -> None:
    print("\n  ── Eliminar tenant ──\n")
    tenant_name = _pick_tenant(tenants)
    if not tenant_name:
        return
    account_count = len(tenants[tenant_name].accounts)
    if input(f"  ¿Confirmas eliminar el tenant '{tenant_name}' y sus {account_count} cuentas de la config? (s/N): ").strip().lower() != "s":
        print("  Cancelado.\n")
        return
    del tenants[tenant_name]
    save(tenants)
    print(f"\n  ✅ Tenant '{tenant_name}' eliminado de la configuración de aws-sso-sync.")
    print("     Nota: los bloques en ~/.aws/config no se tocan; bórralos a mano si ya no los necesitas.\n")


def _view_config(tenants: dict[str, Tenant]) -> None:
    print("\n  ── Configuración actual ──\n")
    if not tenants:
        print("  (vacío)\n")
        return
    for name, tenant in tenants.items():
        print(f"  {name}  [{tenant.sso_region}, session={tenant.sso_session}]")
        if not tenant.accounts:
            print("    (sin cuentas)")
        for acc in tenant.accounts:
            role = f" ({acc.role})" if acc.role else ""
            print(f"    - {acc.label}{role} → {acc.sso_profile} / {acc.credentials_profile}")
    print()


def run(tenants: dict[str, Tenant]) -> None:
    while True:
        print("\n  ── Mantenimiento ──\n")
        print("  [1] Crear tenant nuevo")
        print("  [2] Agregar cuenta/rol a un tenant existente")
        print("  [3] Editar cuenta")
        print("  [4] Eliminar cuenta")
        print("  [5] Eliminar tenant")
        print("  [6] Ver configuración actual")
        print("  [Q] Volver\n")

        choice = input("  Opción: ").strip().upper()
        if choice == "Q":
            return
        elif choice == "1":
            _create_tenant(tenants)
        elif choice == "2":
            _create_account(tenants)
        elif choice == "3":
            _edit_account(tenants)
        elif choice == "4":
            _delete_account(tenants)
        elif choice == "5":
            _delete_tenant(tenants)
        elif choice == "6":
            _view_config(tenants)
        else:
            print("  ⚠️  Opción inválida.\n")
