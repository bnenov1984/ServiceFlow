import uuid

from fastapi import APIRouter, Depends, HTTPException

from business_os.identity.deps import TenantDbDep, TenantDep, require_csrf
from professional_services.deps import require_ps_active

from . import service
from .models import PSAssignment
from .schemas import AssignmentCreate, AssignmentOut, StageChange

router = APIRouter(dependencies=[Depends(require_ps_active)])


def _out(a: PSAssignment) -> AssignmentOut:
    return AssignmentOut(
        id=a.id, client_id=a.client_id, title=a.title, stage=a.stage,
        lifecycle_state=a.lifecycle_state, official_deadline_on=a.official_deadline_on,
        internal_target_on=a.internal_target_on,
    )


def _get_or_404(db: TenantDbDep, tenant: TenantDep, assignment_id: uuid.UUID) -> PSAssignment:
    assignment = service.get_assignment(db, tenant, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message_key": "errors.ps.assignment_not_found", "params": {},
        })
    return assignment


@router.get("/assignments")
def list_assignments(db: TenantDbDep, tenant: TenantDep) -> list[AssignmentOut]:
    return [_out(a) for a in service.list_assignments(db, tenant)]


@router.post("/assignments", dependencies=[Depends(require_csrf)])
def create_assignment(
    body: AssignmentCreate, db: TenantDbDep, tenant: TenantDep
) -> AssignmentOut:
    return _out(service.create_assignment(
        db, tenant, body.client_id, body.title,
        body.official_deadline_on, body.internal_target_on,
    ))


@router.get("/assignments/{assignment_id}")
def get_assignment(assignment_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep) -> AssignmentOut:
    return _out(_get_or_404(db, tenant, assignment_id))


@router.post("/assignments/{assignment_id}/stage", dependencies=[Depends(require_csrf)])
def change_stage(
    assignment_id: uuid.UUID, body: StageChange, db: TenantDbDep, tenant: TenantDep
) -> AssignmentOut:
    assignment = _get_or_404(db, tenant, assignment_id)
    try:
        return _out(service.change_stage(db, assignment, body.to))
    except service.AssignmentError as e:
        raise HTTPException(status_code=e.status, detail={
            "code": "stage_change_failed", "message_key": e.message_key, "params": {},
        }) from e
