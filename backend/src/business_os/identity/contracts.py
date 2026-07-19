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
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from business_os.identity import service as _service


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
