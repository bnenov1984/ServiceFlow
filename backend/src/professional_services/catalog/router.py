import uuid

from fastapi import APIRouter, Depends, HTTPException

from business_os.identity.deps import (
    TenantDbDep,
    TenantDep,
    require_csrf,
    require_subscription_ok,
)
from professional_services.deps import require_ps_active

from . import service
from .models import PSWorkflowTemplate
from .schemas import WorkflowTemplateCreate, WorkflowTemplateOut, WorkflowTemplateStageOut

router = APIRouter(dependencies=[Depends(require_ps_active)])


def _out(db: TenantDbDep, tenant: TenantDep, template: PSWorkflowTemplate) -> WorkflowTemplateOut:
    stages = service.list_template_stages(db, tenant, template.id)
    return WorkflowTemplateOut(
        id=template.id, name=template.name, is_active=template.is_active,
        stages=[
            WorkflowTemplateStageOut(id=s.id, name=s.name, category=s.category, sort=s.sort)
            for s in stages
        ],
    )


@router.get("/workflow-templates")
def list_templates(db: TenantDbDep, tenant: TenantDep) -> list[WorkflowTemplateOut]:
    return [_out(db, tenant, t) for t in service.list_templates(db, tenant)]


@router.post("/workflow-templates",
            dependencies=[Depends(require_csrf), Depends(require_subscription_ok)])
def create_template(
    body: WorkflowTemplateCreate, db: TenantDbDep, tenant: TenantDep
) -> WorkflowTemplateOut:
    try:
        template = service.create_template(
            db, tenant, body.name, [(s.name, s.category) for s in body.stages],
        )
    except service.CatalogError as e:
        raise HTTPException(status_code=e.status, detail={
            "code": "template_create_failed", "message_key": e.message_key, "params": {},
        }) from e
    return _out(db, tenant, template)


@router.get("/workflow-templates/{template_id}")
def get_template(
    template_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep
) -> WorkflowTemplateOut:
    template = service.get_template(db, tenant, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message_key": "errors.ps.template_not_found", "params": {},
        })
    return _out(db, tenant, template)
