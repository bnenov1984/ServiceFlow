"""Attachment per docs/01 §Attachment, docs/08 §attachments.

Belongs to a ServiceOrder, never directly to a Customer (frozen rule). Deliberately
outside the aggregate (docs/01 §4) — independent lifecycle, no shared invariants.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from serviceflow.shared_kernel.db import Base, TimestampMixin
from serviceflow.shared_kernel.ids import new_id


class Attachment(Base, TimestampMixin):
    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("service_orders.id"), index=True)
    storage_key: Mapped[str]
    thumbnail_key: Mapped[str | None] = mapped_column(default=None)
    kind: Mapped[str]  # photo | document
    stage: Mapped[str] = mapped_column(default="other", server_default="other")
    caption: Mapped[str] = mapped_column(default="", server_default="")
    mime: Mapped[str]
    size: Mapped[int]
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)
