"""PSWorkflowTemplate / PSWorkflowTemplateStage — org-configurable workflow
vocabulary (ADR-PS-005). Stages are copied onto each assignment at creation
(professional_services.assignments); editing a template afterwards never
touches assignments that already copied it."""

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from business_os.shared_kernel.db import Base, TimestampMixin
from business_os.shared_kernel.ids import new_id

# Code-owned (ADR-PS-005): org-configurable stage *names* sit on top of these
# five fixed categories — never itself org-configurable.
STAGE_CATEGORIES = ("work", "waiting_client", "waiting_documents", "review", "delivery")


class PSWorkflowTemplate(Base, TimestampMixin):
    __tablename__ = "ps_workflow_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    name: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)


class PSWorkflowTemplateStage(Base, TimestampMixin):
    __tablename__ = "ps_workflow_template_stages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ps_workflow_templates.id"), index=True
    )
    name: Mapped[str]
    category: Mapped[str]
    sort: Mapped[int]
