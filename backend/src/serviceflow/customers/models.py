"""Customer per docs/01 (entity) and docs/08 §customers. First RLS-covered table."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from business_os.shared_kernel.db import Base, TimestampMixin
from business_os.shared_kernel.ids import new_id


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    name: Mapped[str]
    phone: Mapped[str]
    phone2: Mapped[str | None] = mapped_column(default=None)
    email: Mapped[str | None] = mapped_column(default=None)
    is_company: Mapped[bool] = mapped_column(default=False)
    company_requisites: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    notes: Mapped[str] = mapped_column(default="", server_default="")
    # Shadow columns (ADR-010) — maintained by the service layer, never by hand.
    phone_normalized: Mapped[str] = mapped_column(index=True)
    name_translit: Mapped[str] = mapped_column(index=True)
    anonymized_at: Mapped[datetime | None] = mapped_column(default=None)
    archived_at: Mapped[datetime | None] = mapped_column(default=None)
    row_version: Mapped[int] = mapped_column(default=1, server_default=text("1"))
