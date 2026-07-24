import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from business_os.shared_kernel.db import TenantContext, scoped

from .models import STAGE_CATEGORIES, PSWorkflowTemplate, PSWorkflowTemplateStage


class CatalogError(Exception):
    def __init__(self, message_key: str, status: int = 400) -> None:
        self.message_key = message_key
        self.status = status


def create_template(
    db: Session, ctx: TenantContext, name: str, stages: list[tuple[str, str]],
) -> PSWorkflowTemplate:
    """stages: ordered (name, category) pairs; sort is assigned from list order.
    A template with no stages cannot be copied onto an assignment, so at
    least one is required here (PS-23 §9)."""
    if not stages:
        raise CatalogError("errors.ps.template_needs_stages")
    for _, category in stages:
        if category not in STAGE_CATEGORIES:
            raise CatalogError("errors.ps.invalid_stage_category")

    template = PSWorkflowTemplate(company_id=ctx.company_id, name=name)
    db.add(template)
    db.flush()
    for sort, (stage_name, category) in enumerate(stages):
        db.add(PSWorkflowTemplateStage(
            company_id=ctx.company_id, template_id=template.id,
            name=stage_name, category=category, sort=sort,
        ))
    db.commit()
    return template


def list_templates(db: Session, ctx: TenantContext) -> list[PSWorkflowTemplate]:
    stmt = scoped(select(PSWorkflowTemplate), PSWorkflowTemplate, ctx).where(
        PSWorkflowTemplate.is_active.is_(True)
    ).order_by(PSWorkflowTemplate.created_at)
    return list(db.scalars(stmt))


def get_template(
    db: Session, ctx: TenantContext, template_id: uuid.UUID
) -> PSWorkflowTemplate | None:
    stmt = scoped(select(PSWorkflowTemplate), PSWorkflowTemplate, ctx).where(
        PSWorkflowTemplate.id == template_id
    )
    return db.scalar(stmt)


def list_template_stages(
    db: Session, ctx: TenantContext, template_id: uuid.UUID
) -> list[PSWorkflowTemplateStage]:
    stmt = scoped(select(PSWorkflowTemplateStage), PSWorkflowTemplateStage, ctx).where(
        PSWorkflowTemplateStage.template_id == template_id
    ).order_by(PSWorkflowTemplateStage.sort)
    return list(db.scalars(stmt))
