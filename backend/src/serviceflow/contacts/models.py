"""ContactRecord per docs/01 §ContactRecord, docs/02 §10, docs/08 §contacts.

Type extended with "note" beyond the four communication channels (обаждане/имейл/
съобщение/на място) — additive CHECK-constraint enum value (docs/08 §1: "cheap to
extend"), covering the PO's Etap-2 "бележки" requirement with the same mechanism
rather than a second entity. direction is required for the four channels, null
for a plain note (a note has no in/out direction).
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from business_os.shared_kernel.db import Base
from business_os.shared_kernel.ids import new_id

TYPES = ("call", "email", "message", "visit", "note")


class ContactRecord(Base):
    __tablename__ = "contact_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("service_orders.id"), default=None, index=True
    )
    type: Mapped[str]
    direction: Mapped[str | None] = mapped_column(default=None)  # in | out | null (note)
    summary: Mapped[str]
    occurred_at: Mapped[datetime]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    frozen_after: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
