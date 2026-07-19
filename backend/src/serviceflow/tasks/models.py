"""Task per docs/01 §Task, docs/08 §tasks. Deliberately outside the ServiceOrder
aggregate (docs/01 §4) — independent lifecycle, no shared invariants with status."""

import uuid
from datetime import date, datetime

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from business_os.shared_kernel.db import Base, TimestampMixin
from business_os.shared_kernel.ids import new_id


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("service_orders.id"), default=None, index=True
    )
    title: Mapped[str]
    is_done: Mapped[bool] = mapped_column(default=False)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    due_on: Mapped[date | None] = mapped_column(default=None)
    note: Mapped[str] = mapped_column(default="", server_default="")
    is_call: Mapped[bool] = mapped_column(default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    completed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)
