"""Customers' public application contract (docs/business-os/04 rule R4/R7,
same shape as service_orders/contracts.py — the second cross-context edge,
after commercial <-> service_orders). `commercial` needs read-only buyer
data at Invoice Issue time; `customers` and `service_orders` are the same
bounded context (R6: "Service Operations... and Customers & Assets are one
vertical"), so `service_orders` itself may keep reading `customers.service`
directly, but `commercial` is a different context (docs/01 "Commercial
Documents & Invoicing") — it must go through this surface, never
`serviceflow.customers.models`/`.service` directly, mirroring the treatment
`service_orders.contracts` already got.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from business_os.shared_kernel.db import TenantContext
from serviceflow.customers import service as _service


@dataclass(frozen=True)
class CustomerSummary:
    """The subset of customer data another module may need (e.g. an Invoice
    buyer snapshot at Issue time) — never the ORM model itself."""

    id: uuid.UUID
    name: str
    is_company: bool
    company_requisites: dict[str, Any] | None


def get_customer_summary(db: Session, ctx: TenantContext,
                         customer_id: uuid.UUID) -> CustomerSummary | None:
    """The sanctioned way for another module to look up a customer. Returns
    None if the customer doesn't exist or isn't in the caller's tenant (the
    scoped() chokepoint already enforces that inside `_service.get`)."""
    customer = _service.get(db, ctx, customer_id)
    if customer is None:
        return None
    return CustomerSummary(
        id=customer.id, name=customer.name, is_company=customer.is_company,
        company_requisites=customer.company_requisites,
    )


def get_customer_summaries(db: Session, ctx: TenantContext,
                           customer_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, CustomerSummary]:
    """Batch counterpart to get_customer_summary — one query, not N. First
    consumer: commercial's central invoice list (GET /invoices), which needs
    the *live* customer name for Draft rows only — an issued row's
    customer_name comes from the invoice's own frozen buyer snapshot instead,
    never from here (see commercial/router.py's list_invoices)."""
    return {
        cid: CustomerSummary(id=c.id, name=c.name, is_company=c.is_company,
                             company_requisites=c.company_requisites)
        for cid, c in _service.get_many(db, ctx, customer_ids).items()
    }
