import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from business_os.identity.deps import (
    TenantDbDep,
    TenantDep,
    require_csrf,
    require_subscription_ok,
)
from professional_services.deps import require_ps_active

from . import service
from .models import PSNextAction
from .schemas import NextActionCreate, NextActionOut

router = APIRouter(dependencies=[Depends(require_ps_active)])


def _out(a: PSNextAction) -> NextActionOut:
    completed = a.completed_at is not None
    risk = service.compute_risk(a.due_on, completed, datetime.now(UTC).date())
    return NextActionOut(
        id=a.id, assignment_id=a.assignment_id, title=a.title,
        owner_user_id=a.owner_user_id, due_on=a.due_on, completed=completed, risk=risk,
    )


@router.get("/next-actions")
def list_actions(
    db: TenantDbDep, tenant: TenantDep, assignment_id: uuid.UUID | None = None
) -> list[NextActionOut]:
    return [_out(a) for a in service.list_actions(db, tenant, assignment_id)]


@router.post("/next-actions",
            dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
def create_action(body: NextActionCreate, db: TenantDbDep, tenant: TenantDep) -> NextActionOut:
    return _out(service.create_action(
        db, tenant, body.assignment_id, body.title, body.owner_user_id, body.due_on,
    ))


@router.post("/next-actions/{action_id}/complete",
            dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
def complete_action(action_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep) -> NextActionOut:
    action = service.get_action(db, tenant, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message_key": "errors.ps.action_not_found", "params": {},
        })
    return _out(service.complete_action(db, action))
