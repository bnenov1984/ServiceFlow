"""PSAssignment — walking-skeleton engagement record.

stage is a plain, hardcoded Python-level vocabulary (not a configurable
ps_workflow_templates table — that is PS's own later, out-of-scope design,
ADR-PS-005). Deliberately borrows ServiceFlow's frozen-vocabulary *pattern*
(one CHECK-constrained enum, one transition chokepoint in service.py), not
PS's real target two-axis model."""

import uuid
from datetime import date

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from business_os.shared_kernel.db import Base, TimestampMixin
from business_os.shared_kernel.ids import new_id

STAGES = ("intake", "in_progress", "waiting_client", "delivered")
LIFECYCLE_STATES = ("active", "delivered", "cancelled")


class PSAssignment(Base, TimestampMixin):
    __tablename__ = "ps_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ps_clients.id"), index=True)
    title: Mapped[str]
    stage: Mapped[str] = mapped_column(default="intake")
    lifecycle_state: Mapped[str] = mapped_column(default="active")
    official_deadline_on: Mapped[date | None] = mapped_column(default=None)
    internal_target_on: Mapped[date | None] = mapped_column(default=None)
