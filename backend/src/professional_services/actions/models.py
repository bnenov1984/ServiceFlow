"""PSNextAction — the walking skeleton's next-action record. Risk is computed
at request time (see service.compute_risk) — no persisted risk column, no
background job, no notification emission (explicitly out of scope for this
slice; PS-13's "morning per-tenant job" is future work)."""

import uuid
from datetime import date, datetime

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from business_os.shared_kernel.db import Base, TimestampMixin
from business_os.shared_kernel.ids import new_id


class PSNextAction(Base, TimestampMixin):
    __tablename__ = "ps_next_actions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ps_assignments.id"), index=True
    )
    title: Mapped[str]
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    due_on: Mapped[date]
    completed_at: Mapped[datetime | None] = mapped_column(default=None)
