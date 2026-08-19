"""Interactive menu to create/edit/delete tenants and accounts (roles).

Creating a tenant/account also provisions the corresponding [sso-session]/
[profile] block in ~/.aws/config, so a freshly created account is ready for
`aws sso login` without any manual editing.
"""

from __future__ import annotations

import logging

from . import aws_config_writer, sso_discovery
from .config import Account, Tenant, save, slugify
from .i18n import t
from .sso import sso_login_session

logger = logging.getLogger(__name__)


def _input(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"  {prompt}{suffix}: ").strip()
    return value or default


def _confirm(key: str, **kwargs: object) -> bool:
    answer = input(t(key, **kwargs)).strip().lower()
    return answer == t("common.yes_char")


def _pick(items: list[dict], format_item, prompt: str) -> dict | None:
    """Numbered picker over dicts, with a free-text filter. None means cancel."""
    filtered = items
    while True:
        for i, item in enumerate(filtered, 1):
            print(f"  [{i}] {format_item(item)}")
        print(f"\n  {t('common.cancel')}")
        choice = input(t("maint.pick.prompt", prompt=prompt)).strip()
        if choice.upper() == "Q":
            return None
        if choice.isdigit():
            if 0 < int(choice) <= len(filtered):
                return filtered[int(choice) - 1]
            print(t("maint.pick.out_of_range"))
            continue
        needle = choice.lower()
        matches = [it for it in items if needle in format_item(it).lower()]
        if not matches:
            print(t("maint.pick.no_matches"))
            filtered = items
        else:
            filtered = matches
        print()


def _pick_tenant(tenants: dict[str, Tenant]) -> str | None:
    names = list(tenants.keys())
    if not names:
        print(t("maint.no_tenants"))
        return None
    for i, name in enumerate(names, 1):
        print(f"  [{i}] {name}")
    choice = input("\n  Tenant: ").strip()
    if choice.isdigit() and 0 < int(choice) <= len(names):
        return names[int(choice) - 1]
    print(t("common.invalid_option"))
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
        print(t("maint.tenant_no_accounts", tenant=tenant_name))
        return []
    for i, acc in enumerate(tenant.accounts, 1):
        role = f" ({acc.role})" if acc.role else ""
        print(f"  [{i}] {acc.label}{role} → {acc.sso_profile} / {acc.credentials_profile}")
    return tenant.accounts


def _create_tenant(tenants: dict[str, Tenant]) -> None:
    print(t("maint.create_tenant.header"))
    name = _input(t("maint.create_tenant.name_prompt"))
    if not name:
        print(t("maint.create_tenant.empty_name"))
        return
    if name in tenants:
        print(t("maint.create_tenant.duplicate", name=name))
        return

    sso_region = _input(t("maint.create_tenant.region_prompt"), "us-east-1")
    sso_start_url = _input("SSO start URL (https://xxxx.awsapps.com/start)")
    if not sso_start_url:
        print(t("maint.create_tenant.empty_url"))
        return
    sso_session = _input(t("maint.create_tenant.session_prompt"), f"{slugify(name)}-sso-session")

    logger.debug("Creando tenant %r con sso_start_url=%r sso_session=%r sso_region=%r", name, sso_start_url, sso_session, sso_region)
    aws_config_writer.ensure_sso_session(sso_session, sso_start_url, sso_region)
    tenants[name] = Tenant(sso_region=sso_region, sso_session=sso_session, sso_start_url=sso_start_url)
    save(tenants)
    print(t("maint.create_tenant.done", name=name, session=sso_session))

    if _confirm("maint.create_tenant.confirm_first_account"):
        _create_account(tenants, name)


def _register_account(tenants: dict[str, Tenant], tenant_name: str, label: str, role: str, account_id: str, sso_role_name: str) -> bool:
    tenant = tenants[tenant_name]

    duplicate = _find_duplicate(tenant, account_id, sso_role_name)
    if duplicate:
        print(t("maint.duplicate.exists", label=duplicate.label, account_id=account_id, role=sso_role_name, tenant=tenant_name))
        print(t("maint.duplicate.existing_profile", sso_profile=duplicate.sso_profile, credentials_profile=duplicate.credentials_profile))
        return False

    slug = slugify(label)
    tenant_slug = slugify(tenant_name)
    sso_profile = _input(t("maint.register.sso_profile_prompt"), f"{tenant_slug}-{slug}-sso")
    credentials_profile = _input(t("maint.register.credentials_profile_prompt"), f"{tenant_slug}-{slug}")

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
    print(t("maint.register.done", label=label, tenant=tenant_name, sso_profile=sso_profile))
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
        print(t("maint.discover.no_cached_session"))
        if not sso_login_session(tenant.sso_session):
            return False
        token = sso_discovery.find_cached_token(tenant.sso_start_url)
    if not token:
        logger.debug("Sin token disponible tras login para sso_start_url=%r", tenant.sso_start_url)
        print(t("maint.discover.no_token"))
        return False

    try:
        accounts = sso_discovery.list_accounts(token, tenant.sso_region)
    except RuntimeError as e:
        logger.debug("list_accounts falló: %s", e)
        print(t("maint.discover.list_accounts_failed", error=e))
        return False
    if not accounts:
        print(t("maint.discover.no_accounts"))
        return False

    print(t("maint.discover.accounts_available", tenant=tenant_name))
    account = _pick(accounts, lambda a: f"{a['accountId']} - {a.get('accountName', '')}", t("maint.label.account"))
    if account is None:
        return False

    try:
        roles = sso_discovery.list_account_roles(token, account["accountId"], tenant.sso_region)
    except RuntimeError as e:
        logger.debug("list_account_roles falló: %s", e)
        print(t("maint.discover.list_roles_failed", error=e))
        return False
    if not roles:
        print(t("maint.discover.no_roles"))
        return False

    print(t("maint.discover.roles_available", account=account.get("accountName", account["accountId"])))
    role = _pick(roles, lambda r: r["roleName"], t("maint.label.role"))
    if role is None:
        return False

    account_id = account["accountId"]
    role_name = role["roleName"]
    account_name = account.get("accountName", account_id)

    duplicate = _find_duplicate(tenant, account_id, role_name)
    if duplicate:
        print(t("maint.duplicate.exists", label=duplicate.label, account_id=account_id, role=role_name, tenant=tenant_name))
        print(t("maint.duplicate.existing_profile", sso_profile=duplicate.sso_profile, credentials_profile=duplicate.credentials_profile))
        return True

    print()
    label = _input(t("maint.label_prompt"), account_name)
    if not label:
        print(t("maint.empty_label"))
        return False

    _register_account(tenants, tenant_name, label, role_name, account_id, role_name)
    return True


def _create_account_manual(tenants: dict[str, Tenant], tenant_name: str) -> None:
    label = _input(t("maint.manual.label_prompt"))
    if not label:
        print(t("maint.empty_label"))
        return
    role = _input(t("maint.manual.role_prompt"))
    account_id = _input(t("maint.manual.account_id_prompt"))
    if not (account_id.isdigit() and len(account_id) == 12):
        print(t("maint.manual.invalid_account_id"))
        return
    sso_role_name = _input(t("maint.manual.sso_role_prompt"), role)

    _register_account(tenants, tenant_name, label, role, account_id, sso_role_name)


def _create_account(tenants: dict[str, Tenant], tenant_name: str | None = None) -> None:
    print(t("maint.create_account.header"))
    if not tenants:
        print(t("maint.create_account.no_tenants"))
        return

    if tenant_name is None:
        tenant_name = _pick_tenant(tenants)
        if tenant_name is None:
            return

    print(t("maint.create_account.how"))
    print(f"  {t('maint.create_account.opt_discover')}")
    print(f"  {t('maint.create_account.opt_manual')}")
    mode = input(t("common.option_prompt")).strip()

    if mode == "1":
        if _create_account_discover(tenants, tenant_name):
            return
        print(t("maint.create_account.fallback_manual"))

    _create_account_manual(tenants, tenant_name)


def _edit_account(tenants: dict[str, Tenant]) -> None:
    print(t("maint.edit.header"))
    tenant_name = _pick_tenant(tenants)
    if not tenant_name:
        return
    tenant = tenants[tenant_name]
    accounts = _list_accounts(tenant_name, tenant)
    if not accounts:
        return
    choice = input(t("maint.edit.which_account")).strip()
    if not (choice.isdigit() and 0 < int(choice) <= len(accounts)):
        print(t("common.invalid_option"))
        return
    acc = accounts[int(choice) - 1]
    acc.label = _input(t("maint.edit.label_prompt"), acc.label)
    acc.role = _input(t("maint.edit.role_prompt"), acc.role)
    acc.credentials_profile = _input(t("maint.edit.credentials_profile_prompt"), acc.credentials_profile)
    save(tenants)
    print(t("maint.edit.done"))


def _delete_account(tenants: dict[str, Tenant]) -> None:
    print(t("maint.delete_account.header"))
    tenant_name = _pick_tenant(tenants)
    if not tenant_name:
        return
    tenant = tenants[tenant_name]
    accounts = _list_accounts(tenant_name, tenant)
    if not accounts:
        return
    choice = input(t("maint.delete_account.which_account")).strip()
    if not (choice.isdigit() and 0 < int(choice) <= len(accounts)):
        print(t("common.invalid_option"))
        return
    acc = accounts[int(choice) - 1]
    if not _confirm("maint.delete_account.confirm", label=acc.label, tenant=tenant_name):
        print(t("common.cancelled"))
        return
    tenant.accounts.remove(acc)
    save(tenants)
    print(t("maint.delete_account.done", label=acc.label))
    print(t("maint.delete_account.note", profile=acc.sso_profile))


def _delete_tenant(tenants: dict[str, Tenant]) -> None:
    print(t("maint.delete_tenant.header"))
    tenant_name = _pick_tenant(tenants)
    if not tenant_name:
        return
    account_count = len(tenants[tenant_name].accounts)
    if not _confirm("maint.delete_tenant.confirm", tenant=tenant_name, count=account_count):
        print(t("common.cancelled"))
        return
    del tenants[tenant_name]
    save(tenants)
    print(t("maint.delete_tenant.done", tenant=tenant_name))
    print(t("maint.delete_tenant.note"))


def _view_config(tenants: dict[str, Tenant]) -> None:
    print(t("maint.view.header"))
    if not tenants:
        print(t("maint.view.empty"))
        return
    for name, tenant in tenants.items():
        print(f"  {name}  [{tenant.sso_region}, session={tenant.sso_session}]")
        if not tenant.accounts:
            print(t("maint.view.no_accounts"))
        for acc in tenant.accounts:
            role = f" ({acc.role})" if acc.role else ""
            print(f"    - {acc.label}{role} → {acc.sso_profile} / {acc.credentials_profile}")
    print()


def _find_duplicates(tenants: dict[str, Tenant]) -> None:
    print(t("maint.dupes.header"))
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
            print(t("maint.dupes.group", account_id=account_id, role=sso_role_name, count=len(accs)))
            for acc in accs:
                print(f"      - {acc.label} → {acc.sso_profile} / {acc.credentials_profile}")
        print()

    if not found_any:
        print(t("maint.dupes.none"))
    else:
        print(t("maint.dupes.hint"))


def run(tenants: dict[str, Tenant]) -> None:
    while True:
        print(t("maint.menu.header"))
        print(f"  {t('maint.menu.opt1')}")
        print(f"  {t('maint.menu.opt2')}")
        print(f"  {t('maint.menu.opt3')}")
        print(f"  {t('maint.menu.opt4')}")
        print(f"  {t('maint.menu.opt5')}")
        print(f"  {t('maint.menu.opt6')}")
        print(f"  {t('maint.menu.opt7')}")
        print(f"  {t('common.back')}\n")

        choice = input(t("common.option_prompt")).strip().upper()
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
            print(t("common.invalid_option"))
