"""Interactive menu to sync credentials: whole tenant, or selected accounts."""

from __future__ import annotations

import logging

from .config import Account, Tenant
from .credentials import CREDENTIALS_FILE, export_credentials, update_credentials_file
from .i18n import t
from .sso import sso_login

logger = logging.getLogger(__name__)


def _select_tenant(tenants: dict[str, Tenant]):
    names = list(tenants.keys())
    if not names:
        print(t("login.no_tenants"))
        return None, None

    print(t("login.select_tenant"))
    for i, name in enumerate(names, 1):
        print(t("login.tenant_row", i=i, name=name, count=len(tenants[name].accounts)))

    all_count = sum(len(t.accounts) for t in tenants.values())
    print(t("login.all_tenants", count=all_count))
    print(f"  {t('common.back')}\n")

    while True:
        choice = input(t("common.option_prompt")).strip().upper()
        if choice == "Q":
            return None, None
        if choice == "A":
            return "ALL", None
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(names):
                name = names[idx]
                return name, tenants[name]
        print(f"  {t('common.invalid_option_retry')}")


def _select_accounts(tenant_name: str, tenant: Tenant) -> list[Account]:
    accounts = tenant.accounts
    if not accounts:
        print(t("login.tenant_no_accounts", tenant=tenant_name))
        return []

    print(t("login.select_accounts", tenant=tenant_name))
    for i, acc in enumerate(accounts, 1):
        role = f" ({acc.role})" if acc.role else ""
        print(f"  [{i}] {acc.label}{role}")
    print(t("login.all_accounts"))
    print(f"  {t('common.back')}\n")

    while True:
        choice = input(t("login.accounts_prompt")).strip().upper()
        if choice == "Q":
            return []
        if choice == "A":
            return accounts
        indices = [c.strip() for c in choice.split(",") if c.strip()]
        if indices and all(i.isdigit() and 0 < int(i) <= len(accounts) for i in indices):
            return [accounts[int(i) - 1] for i in indices]
        print(f"  {t('common.invalid_option_retry')}")


def _sync_accounts(tenant_name: str, accounts: list[Account]) -> None:
    if not accounts:
        return

    print(f"\n┌─ {tenant_name} {'─' * max(1, 30 - len(tenant_name))}")

    if not sso_login(accounts[0].sso_profile):
        print(t("login.sync_aborted"))
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
            logger.debug("Fallo sincronizando %s: %s", acc.sso_profile, e)
            print(f"❌\n│     {e}")
            fail += 1

    logger.debug("Sync %s: %d ok, %d errores", tenant_name, ok, fail)
    print(f"└─ {ok} ok" + (t("login.sync_summary_errors", fail=fail) if fail else "") + "\n")


def run(tenants: dict[str, Tenant]) -> None:
    tenant_name, tenant = _select_tenant(tenants)
    if tenant_name is None:
        return

    if tenant_name == "ALL":
        for name, t_ in tenants.items():
            _sync_accounts(name, t_.accounts)
    else:
        accounts = _select_accounts(tenant_name, tenant)
        _sync_accounts(tenant_name, accounts)

    print(t("login.credentials_location", path=CREDENTIALS_FILE))
