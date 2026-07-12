"""Database base: naming conventions, timestamps, engine cache, tenant scoping.

Tenant rule (ADR-016): tenant context comes from the authenticated session only.
`scoped()` is the query chokepoint for tenant tables — handlers and services must
not filter company_id by hand.
"""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any, Protocol

from sqlalchemy import MetaData, Select, create_engine, func
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


@dataclass(frozen=True)
class TenantContext:
    """The only carrier of tenant scope. Constructed by the auth dependency —
    never from client-supplied identifiers (ADR-016)."""

    company_id: uuid.UUID
    user_id: uuid.UUID
    is_owner: bool


class HasCompanyId(Protocol):
    company_id: Any


def scoped[SelectT: Select[Any]](
    stmt: SelectT, model: type[HasCompanyId], ctx: TenantContext
) -> SelectT:
    """Tenant chokepoint: every query against a tenant table goes through here."""
    return stmt.where(model.company_id == ctx.company_id)


@lru_cache
def get_engine(database_url: str) -> Engine:
    engine = create_engine(database_url, pool_pre_ping=True)

    # Pooled connections must never carry another request's tenant scope
    # (ADR-016): clear the RLS GUC whenever a connection returns to the pool.
    from sqlalchemy import event

    @event.listens_for(engine, "checkin")
    def _reset_tenant_guc(dbapi_conn: Any, _record: Any) -> None:
        try:
            cur = dbapi_conn.cursor()
            cur.execute("RESET app.company_id")
            cur.close()
            dbapi_conn.commit()  # psycopg autobegins; leave the connection idle
        except Exception:  # noqa: BLE001 — a dying connection is the pool's problem
            pass

    return engine


def open_session(database_url: str) -> Iterator[Session]:
    factory = sessionmaker(bind=get_engine(database_url), expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
