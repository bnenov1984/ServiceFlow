"""Identity's public application contract, part 2 (Business OS Phase 3 —
docs/business-os/16_PHASE_3_IDENTITY_BOUNDARY.md).

Plain, non-request-scoped functions any module may call directly — as
opposed to `identity.deps`, which is FastAPI `Depends()`-wrapped and
request-scoped. Together, `deps` and `contracts` are identity's entire public
surface. Everything else in `identity` (models, service, security, router) is
implementation detail: importing it from outside `identity` is what the
identity-boundary enforcement (docs/business-os/04 rule set, `core-not-...`
family in backend/.importlinter) exists to prevent.

Internal identity module kept as `_service` (leading underscore), not
`service` — this is deliberate: it stops `from business_os.identity.contracts
import service` from working as a convenient re-export bypass of the
boundary (see docs/business-os/16 for the residual limitation this does and
does not close).

**Provisioning write surface (docs/business-os/18 §9 phase 2, added
27.07.2026).** `business_os.platform_admin` — the only module besides
`identity` itself and the composition root allowed to import this file — can
now create a company here, not just read one. Every function below that
`ProvisionCompany` composes is **non-committing**: the caller (platform_admin,
which owns the single transaction) commits exactly once, after all of them
have run, so the whole operation is atomic. Nothing here validates
RepairFlow's profile vocabulary or the module-key registry — those belong to
the caller (`platform_admin.service.VALID_BUSINESS_PROFILES`), the same way
`grant_module` never validated `module_key` even before this contract existed.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from business_os.identity import service as _service
from business_os.identity.service import ProvisioningError

__all__ = [
    "CompanyAdminMetadata",
    "CompanyProfile",
    "ProvisionedCompany",
    "ProvisioningError",
    "get_business_profile",
    "get_company_admin_metadata",
    "get_company_profile",
    "grant_module",
    "is_module_active",
    "list_companies_admin_metadata",
    "provision_company",
    "revoke_module",
    "set_business_profile",
    "set_subscription_trial",
]


@dataclass(frozen=True)
class CompanyProfile:
    """The subset of Company data another module may need (e.g. a document
    letterhead) — never the ORM model itself."""

    name: str
    requisites: dict[str, Any]


def get_company_profile(db: Session, company_id: uuid.UUID) -> CompanyProfile:
    """The only sanctioned way for another module to read company profile
    data. Company rows are RLS-exempt (ADR-016); this wraps identity's own
    compensating-control lookup (`service.get_company`) instead of letting
    callers query `Company` directly. `company_id` must be a real,
    already-validated tenant id (e.g. from `TenantContext.company_id`) —
    same invariant the original call site relied on."""
    company = _service.get_company(db, company_id)
    assert company is not None
    return CompanyProfile(name=company.name, requisites=company.requisites)


def is_module_active(db: Session, company_id: uuid.UUID, module_key: str) -> bool:
    """Module activation (BOS-06): `active_modules` inside `companies.settings`
    JSONB, no dedicated registry table yet (BOS-02 Settings precedent). The
    sanctioned way for another module's routes to gate themselves — never read
    `company.settings` directly; wraps `service.is_module_active`."""
    return _service.is_module_active(db, company_id, module_key)


@dataclass(frozen=True)
class ProvisionedCompany:
    """What `provision_company` hands back — ids only, never the ORM rows,
    and never the owner's password."""

    company_id: uuid.UUID
    owner_id: uuid.UUID


def provision_company(
    db: Session, company_name: str, owner_name: str, owner_email: str, owner_password: str,
) -> ProvisionedCompany:
    """Create a new company and its first Tenant Owner. **Non-committing** —
    the caller (`platform_admin.service.provision_company`, the single
    ProvisionCompany orchestrator, docs/business-os/18 §9 phase 2) commits
    once, after this and every other provisioning step has run, so the whole
    operation is atomic. Raises `ProvisioningError` (re-exported here, not
    swallowed) on a duplicate owner email rather than the idempotent
    "return the existing company" behavior `identity.service.seed_company`
    uses — see that function's docstring for why."""
    company, owner = _service.create_company_with_owner(
        db, company_name, owner_name, owner_email, owner_password
    )
    return ProvisionedCompany(company_id=company.id, owner_id=owner.id)


def grant_module(db: Session, company_id: uuid.UUID, module_key: str) -> None:
    """Non-committing counterpart to `identity.service.activate_module`, for
    composing inside `ProvisionCompany`'s single transaction. Idempotent, and
    validates nothing about `module_key` — same as the committing version."""
    _service._activate_module(db, company_id, module_key)


def revoke_module(db: Session, company_id: uuid.UUID, module_key: str) -> None:
    """Revokes one module entitlement (ADR-BOS-010 §Decision 1: entitlement
    mutation is Vendor Control Plane's exclusively) — the sanctioned path
    `platform_admin.service.revoke_entitlement` uses. Non-committing and
    idempotent, symmetric to `grant_module`."""
    _service._deactivate_module(db, company_id, module_key)


def set_business_profile(db: Session, company_id: uuid.UUID, profile: str) -> None:
    """Assigns the RepairFlow business profile at provisioning (ADR-BOS-011
    §Decision 3). Non-committing — composed inside `ProvisionCompany`."""
    _service.set_business_profile(db, company_id, profile)


def get_business_profile(db: Session, company_id: uuid.UUID) -> str:
    """`generic_repair` if never assigned (ADR-BOS-011 §Decision 2 default)."""
    return _service.get_business_profile(db, company_id)


def set_subscription_trial(db: Session, company_id: uuid.UUID, trial_days: int) -> datetime:
    """Baseline subscription state for a freshly provisioned company
    (ADR-BOS-012). Non-committing — composed inside `ProvisionCompany`.
    Returns the computed `trial_ends_at`."""
    return _service.set_subscription_trial(db, company_id, trial_days)


@dataclass(frozen=True)
class CompanyAdminMetadata:
    """The Vendor Control Plane's metadata-only view of one company
    (ADR-BOS-009 §Vendor data visibility) — administrative facts about the
    tenancy itself, never tenant operational data. No `active_modules` count
    of *usage* (seats in use) — that needs a tenant employee count, out of
    scope for this slice (docs/business-os/18 §9 phase 2)."""

    id: uuid.UUID
    name: str
    business_profile: str
    active_modules: list[str]
    subscription_state: str
    subscription_state_changed_at: datetime
    trial_ends_at: datetime | None
    seat_limit: int | None
    created_at: datetime


def list_companies_admin_metadata(db: Session) -> list[CompanyAdminMetadata]:
    """Backs the vendor company-list screen. Metadata only — see
    `CompanyAdminMetadata`."""
    return [_to_admin_metadata(c) for c in _service.list_companies(db)]


def get_company_admin_metadata(db: Session, company_id: uuid.UUID) -> CompanyAdminMetadata | None:
    """Backs the vendor company-detail screen. `None` for a non-existent id —
    the caller (the vendor route) turns that into a 404, existence-checked
    server-side (ADR-BOS-009 §Tenant isolation requirement, restated for the
    Control Plane), never inferred from anything client-supplied."""
    company = _service.get_company(db, company_id)
    if company is None:
        return None
    return _to_admin_metadata(company)


def _to_admin_metadata(company: Any) -> CompanyAdminMetadata:
    # Reads company.settings directly (same style get_company_profile already
    # uses for .name/.requisites) rather than calling get_business_profile(db,
    # company_id) again — that would re-query a row this function already has
    # in hand, once per company, turning the list endpoint into N+1 queries.
    repairflow: dict[str, Any] = company.settings.get("repairflow", {})
    return CompanyAdminMetadata(
        id=company.id,
        name=company.name,
        business_profile=repairflow.get("business_profile", _service.DEFAULT_BUSINESS_PROFILE),
        active_modules=list(company.settings.get("active_modules", [])),
        subscription_state=company.subscription_state,
        subscription_state_changed_at=company.subscription_state_changed_at,
        trial_ends_at=company.trial_ends_at,
        seat_limit=company.seat_limit,
        created_at=company.created_at,
    )
