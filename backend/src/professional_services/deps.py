"""Shared FastAPI dependency for every Professional Services router: gate the
whole router behind module activation (BOS-06). Inactive ⇒ 404 with a message
key, not just a hidden nav item — the API surface itself must refuse."""

from fastapi import HTTPException

from business_os.identity.contracts import is_module_active
from business_os.identity.deps import DbDep, TenantDep

MODULE_KEY = "professional-services"


def require_ps_active(tenant: TenantDep, db: DbDep) -> None:
    if not is_module_active(db, tenant.company_id, MODULE_KEY):
        raise HTTPException(status_code=404, detail={
            "code": "module_inactive",
            "message_key": "errors.ps.module_inactive",
            "params": {},
        })
