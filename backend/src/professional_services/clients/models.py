"""PSClient — walking-skeleton client record. Deliberately separate from
ServiceFlow's Customer (different domain, ADR-PS-003 in the module's own
docs); no shared entity, no shared table."""

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from business_os.shared_kernel.db import Base, TimestampMixin
from business_os.shared_kernel.ids import new_id

KINDS = ("person", "company")


class PSClient(Base, TimestampMixin):
    __tablename__ = "ps_clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    name: Mapped[str]
    kind: Mapped[str] = mapped_column(default="person")
