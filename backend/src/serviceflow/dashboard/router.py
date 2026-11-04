"""GET /dashboard — the four widget counts in one call (docs/02 §15, docs/09).

„Готови над N дни": OQ-W2 approved default is 5 работни дни; computed in Python
over the (small) set of ready orders — честно преброяване на работни дни, не
календарно приближение.

order-workflow-revamp WP-H (Q17b): the former today_tasks/call_tasks widgets
are gone along with the rest of the tasks feature — the "Готови от над N
работни дни" highlight above already covers the same reminder need.
"""

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select

from business_os.identity.deps import TenantDbDep, TenantDep, require_repairflow_active
from business_os.shared_kernel.db import TenantContext, scoped
from serviceflow.service_orders import statuses
from serviceflow.service_orders.models import ServiceOrder

router = APIRouter(dependencies=[Depends(require_repairflow_active)])

READY_WARN_BUSINESS_DAYS = 5


class ReadyWidget(BaseModel):
    count: int
    over_limit: int  # ready for more than READY_WARN_BUSINESS_DAYS working days


class DashboardOut(BaseModel):
    active_orders: int
    waiting_parts: int
    ready: ReadyWidget
    overdue: int


def _business_days_between(start: date, end: date) -> int:
    days = 0
    current = start
    while current < end:
        current += timedelta(days=1)
        if current.weekday() < 5:
            days += 1
    return days


def _count_orders(db: TenantDbDep, ctx: TenantContext, *conditions: object) -> int:
    stmt = scoped(select(func.count()).select_from(ServiceOrder), ServiceOrder, ctx).where(
        ServiceOrder.archived_at.is_(None), *conditions  # type: ignore[arg-type]
    )
    return db.scalar(stmt) or 0


@router.get("/dashboard")
def dashboard(db: TenantDbDep, tenant: TenantDep) -> DashboardOut:
    today = datetime.now(UTC).date()

    active = _count_orders(db, tenant, ServiceOrder.status_code.in_(statuses.OPEN))
    waiting_parts = _count_orders(db, tenant, ServiceOrder.status_code == "waiting_parts")

    ready_orders = list(db.scalars(
        scoped(select(ServiceOrder), ServiceOrder, tenant).where(
            ServiceOrder.archived_at.is_(None), ServiceOrder.status_code == "ready"
        )
    ))
    over_limit = 0
    for order in ready_orders:
        changed = order.status_changed_at or order.created_at
        if _business_days_between(changed.date(), today) > READY_WARN_BUSINESS_DAYS:
            over_limit += 1

    # Overdue per FR-11.1 / discovery 1.2: promised date past, not ready/terminal.
    active_kinds = {c for c in statuses.OPEN if statuses.kind_of(c) != statuses.Kind.READY}
    overdue = _count_orders(
        db, tenant,
        ServiceOrder.promised_on.is_not(None),
        ServiceOrder.promised_on < today,
        ServiceOrder.status_code.in_(active_kinds),
    )

    return DashboardOut(
        active_orders=active, waiting_parts=waiting_parts,
        ready=ReadyWidget(count=len(ready_orders), over_limit=over_limit),
        overdue=overdue,
    )
