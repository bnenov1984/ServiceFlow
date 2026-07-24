import uuid

from fastapi import APIRouter, Depends, HTTPException

from business_os.identity.deps import TenantDbDep, TenantDep, require_csrf
from professional_services.catalog.service import CatalogError
from professional_services.deps import require_ps_active

from . import service
from .models import PSAssignment, PSAssignmentStage
from .schemas import AssignmentCreate, AssignmentOut, StageChange, StageOut

router = APIRouter(dependencies=[Depends(require_ps_active)])


def _stage_out(stage: PSAssignmentStage) -> StageOut:
    return StageOut(id=stage.id, name=stage.name, category=stage.category, sort=stage.sort)


def _out(db: TenantDbDep, tenant: TenantDep, a: PSAssignment) -> AssignmentOut:
    current_stage = None
    if a.current_stage_id is not None:
        stage = service.get_assignment_stage(db, tenant, a.id, a.current_stage_id)
        current_stage = _stage_out(stage) if stage is not None else None
    return AssignmentOut(
        id=a.id, client_id=a.client_id, title=a.title,
        lifecycle_state=a.lifecycle_state, current_stage=current_stage,
        official_deadline_on=a.official_deadline_on,
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
    return [_out(db, tenant, a) for a in service.list_assignments(db, tenant)]


@router.post("/assignments", dependencies=[Depends(require_csrf)])
def create_assignment(
    body: AssignmentCreate, db: TenantDbDep, tenant: TenantDep
) -> AssignmentOut:
    try:
        assignment = service.create_assignment(
            db, tenant, body.client_id, body.title,
            body.official_deadline_on, body.internal_target_on, body.workflow_template_id,
        )
    except CatalogError as e:
        raise HTTPException(status_code=e.status, detail={
            "code": "assignment_create_failed", "message_key": e.message_key, "params": {},
        }) from e
    return _out(db, tenant, assignment)


@router.get("/assignments/{assignment_id}")
def get_assignment(assignment_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep) -> AssignmentOut:
    return _out(db, tenant, _get_or_404(db, tenant, assignment_id))


@router.get("/assignments/{assignment_id}/stages")
def list_assignment_stages(
    assignment_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep
) -> list[StageOut]:
    _get_or_404(db, tenant, assignment_id)
    return [_stage_out(s) for s in service.list_assignment_stages(db, tenant, assignment_id)]


@router.post("/assignments/{assignment_id}/stage", dependencies=[Depends(require_csrf)])
def change_stage(
    assignment_id: uuid.UUID, body: StageChange, db: TenantDbDep, tenant: TenantDep,
) -> AssignmentOut:
    assignment = _get_or_404(db, tenant, assignment_id)
    try:
        return _out(db, tenant, service.change_stage(
            db, tenant, assignment, body.to_stage_id, tenant.user_id,
        ))
    except service.AssignmentError as e:
        raise HTTPException(status_code=e.status, detail={
            "code": "stage_change_failed", "message_key": e.message_key, "params": {},
        }) from e
