"""Interactive menu to create/edit/delete tenants and accounts (roles).

Creating a tenant/account also provisions the corresponding [sso-session]/
[profile] block in ~/.aws/config, so a freshly created account is ready for
`aws sso login` without any manual editing.
"""

from __future__ import annotations

import logging

from . import aws_config_writer, sso_discovery
from .config import Account, Tenant, save, slugify
from .sso import sso_login_session

logger = logging.getLogger(__name__)


def _input(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"  {prompt}{suffix}: ").strip()
    return value or default


def _pick(items: list[dict], format_item, prompt: str) -> dict | None:
    """Numbered picker over dicts, with a free-text filter. None means cancel."""
    filtered = items
    while True:
        for i, item in enumerate(filtered, 1):
            print(f"  [{i}] {format_item(item)}")
        print("\n  [Q] Cancelar")
        choice = input(f"\n  {prompt} (o escribe texto para filtrar): ").strip()
        if choice.upper() == "Q":
            return None
        if choice.isdigit():
            if 0 < int(choice) <= len(filtered):
                return filtered[int(choice) - 1]
            print("  ⚠️  Número fuera de rango.\n")
            continue
        needle = choice.lower()
        matches = [it for it in items if needle in format_item(it).lower()]
        if not matches:
            print("  ⚠️  Sin resultados para ese filtro, mostrando lista completa.\n")
            filtered = items
        else:
            filtered = matches
        print()


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


def _find_duplicate(tenant: Tenant, account_id: str, sso_role_name: str) -> Account | None:
    """An (account_id, sso_role_name) pair identifies a unique AWS account+role
    within a tenant - the label is just a display name and shouldn't factor in
    (e.g. 'Core-Networking-Env' vs 'core-networking-env' is the same account+role)."""
    for acc in tenant.accounts:
        if acc.account_id == account_id and acc.sso_role_name == sso_role_name:
            return acc
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

    logger.debug("Creando tenant %r con sso_start_url=%r sso_session=%r sso_region=%r", name, sso_start_url, sso_session, sso_region)
    aws_config_writer.ensure_sso_session(sso_session, sso_start_url, sso_region)
    tenants[name] = Tenant(sso_region=sso_region, sso_session=sso_session, sso_start_url=sso_start_url)
    save(tenants)
    print(f"\n  ✅ Tenant '{name}' creado. Bloque [sso-session {sso_session}] escrito en ~/.aws/config.\n")

    if input("  ¿Agregar la primera cuenta ahora? (s/N): ").strip().lower() == "s":
        _create_account(tenants, name)


def _register_account(tenants: dict[str, Tenant], tenant_name: str, label: str, role: str, account_id: str, sso_role_name: str) -> bool:
    tenant = tenants[tenant_name]

    duplicate = _find_duplicate(tenant, account_id, sso_role_name)
    if duplicate:
        print(f"\n  ⚠️  Ya existe '{duplicate.label}' para la cuenta {account_id} + rol '{sso_role_name}' en {tenant_name}.")
        print(f"     Perfil existente: {duplicate.sso_profile} / {duplicate.credentials_profile}. No se agregó un duplicado.\n")
        return False

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
    return True


def _create_account_discover(tenants: dict[str, Tenant], tenant_name: str) -> bool:
    """Picks account + role from what the SSO portal actually grants. Returns False to fall back to manual entry."""
    tenant = tenants[tenant_name]
    logger.debug(
        "Descubrir cuentas/roles para tenant=%r sso_start_url=%r sso_session=%r sso_region=%r",
        tenant_name,
        tenant.sso_start_url,
        tenant.sso_session,
        tenant.sso_region,
    )

    token = sso_discovery.find_cached_token(tenant.sso_start_url)
    if not token:
        print("\n  No hay una sesión SSO activa en caché; se abrirá el login.")
        if not sso_login_session(tenant.sso_session):
            return False
        token = sso_discovery.find_cached_token(tenant.sso_start_url)
    if not token:
        logger.debug("Sin token disponible tras login para sso_start_url=%r", tenant.sso_start_url)
        print("  ⚠️  No se pudo obtener el token de la sesión SSO.\n")
        return False

    try:
        accounts = sso_discovery.list_accounts(token, tenant.sso_region)
    except RuntimeError as e:
        logger.debug("list_accounts falló: %s", e)
        print(f"  ⚠️  No se pudieron listar las cuentas: {e}\n")
        return False
    if not accounts:
        print("  ⚠️  El SSO no reporta cuentas visibles para este usuario.\n")
        return False

    print(f"\n  Cuentas disponibles en {tenant_name}:\n")
    account = _pick(accounts, lambda a: f"{a['accountId']} - {a.get('accountName', '')}", "Cuenta")
    if account is None:
        return False

    try:
        roles = sso_discovery.list_account_roles(token, account["accountId"], tenant.sso_region)
    except RuntimeError as e:
        logger.debug("list_account_roles falló: %s", e)
        print(f"  ⚠️  No se pudieron listar los roles: {e}\n")
        return False
    if not roles:
        print("  ⚠️  No hay roles SSO visibles para esa cuenta.\n")
        return False

    print(f"\n  Roles disponibles en {account.get('accountName', account['accountId'])}:\n")
    role = _pick(roles, lambda r: r["roleName"], "Rol")
    if role is None:
        return False

    account_id = account["accountId"]
    role_name = role["roleName"]
    account_name = account.get("accountName", account_id)

    duplicate = _find_duplicate(tenant, account_id, role_name)
    if duplicate:
        print(f"\n  ⚠️  Ya existe '{duplicate.label}' para la cuenta {account_id} + rol '{role_name}' en {tenant_name}.")
        print(f"     Perfil existente: {duplicate.sso_profile} / {duplicate.credentials_profile}. No se agregó un duplicado.\n")
        return True

    print()
    label = _input("Etiqueta visible", account_name)
    if not label:
        print("  ⚠️  Etiqueta vacía, cancelado.\n")
        return False

    _register_account(tenants, tenant_name, label, role_name, account_id, role_name)
    return True


def _create_account_manual(tenants: dict[str, Tenant], tenant_name: str) -> None:
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

    _register_account(tenants, tenant_name, label, role, account_id, sso_role_name)


def _create_account(tenants: dict[str, Tenant], tenant_name: str | None = None) -> None:
    print("\n  ── Agregar cuenta/rol ──\n")
    if not tenants:
        print("  ⚠️  No hay tenants. Crea uno primero.\n")
        return

    if tenant_name is None:
        tenant_name = _pick_tenant(tenants)
        if tenant_name is None:
            return

    print("\n  ¿Cómo quieres agregar la cuenta?\n")
    print("  [1] Descubrir cuentas y roles vía SSO (recomendado)")
    print("  [2] Ingresar manualmente\n")
    mode = input("  Opción: ").strip()

    if mode == "1":
        if _create_account_discover(tenants, tenant_name):
            return
        print("  Pasando a ingreso manual...\n")

    _create_account_manual(tenants, tenant_name)


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


def _find_duplicates(tenants: dict[str, Tenant]) -> None:
    print("\n  ── Detectar duplicados (misma cuenta + mismo rol) ──\n")
    found_any = False
    for tenant_name, tenant in tenants.items():
        groups: dict[tuple[str, str], list[Account]] = {}
        for acc in tenant.accounts:
            groups.setdefault((acc.account_id, acc.sso_role_name), []).append(acc)

        dup_groups = {key: accs for key, accs in groups.items() if len(accs) > 1}
        if not dup_groups:
            continue

        found_any = True
        print(f"  {tenant_name}:")
        for (account_id, sso_role_name), accs in dup_groups.items():
            print(f"    Cuenta {account_id} + rol '{sso_role_name}' ({len(accs)} registros):")
            for acc in accs:
                print(f"      - {acc.label} → {acc.sso_profile} / {acc.credentials_profile}")
        print()

    if not found_any:
        print("  No se encontraron duplicados.\n")
    else:
        print("  Usa [4] Eliminar cuenta para quitar los registros redundantes que no quieras conservar.\n")


def run(tenants: dict[str, Tenant]) -> None:
    while True:
        print("\n  ── Mantenimiento ──\n")
        print("  [1] Crear tenant nuevo")
        print("  [2] Agregar cuenta/rol a un tenant existente")
        print("  [3] Editar cuenta")
        print("  [4] Eliminar cuenta")
        print("  [5] Eliminar tenant")
        print("  [6] Ver configuración actual")
        print("  [7] Detectar duplicados (cuenta + rol)")
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
        elif choice == "7":
            _find_duplicates(tenants)
        else:
            print("  ⚠️  Opción inválida.\n")
