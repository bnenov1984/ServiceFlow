"""Commercial's public application contract (docs/business-os/04 rule R4).

Currently one function: the concrete implementation of service_orders'
`PaymentSummaryProvider` port. The composition root (serviceflow/main.py)
registers `get_payment_summary` into
`service_orders.contracts.register_payment_summary_provider` at startup —
commercial never imports service_orders' router or vice versa; each module
only imports the other's `contracts` module (and, for this one function,
implements a shape service_orders declared).

Internal commercial modules (`.models`, `.service`, `.router`) are
implementation detail — the `commercial-public-boundary` import-linter
contract (backend/.importlinter) blocks importing them from outside
commercial's own package (or the composition root)."""

import uuid

from sqlalchemy.orm import Session

from business_os.shared_kernel.db import TenantContext
from serviceflow.commercial import service as _service
from serviceflow.service_orders.contracts import PaymentSummary


def get_payment_summary(db: Session, ctx: TenantContext,
                        order_id: uuid.UUID) -> PaymentSummary:
    return PaymentSummary(
        paid_amount=_service.paid_amount(db, ctx, order_id),
        balance=_service.balance(db, ctx, order_id),
    )
