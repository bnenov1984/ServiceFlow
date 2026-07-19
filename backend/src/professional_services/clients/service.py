import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from business_os.shared_kernel.db import TenantContext, scoped

from .models import PSClient


def create_client(db: Session, ctx: TenantContext, name: str, kind: str) -> PSClient:
    client = PSClient(company_id=ctx.company_id, name=name, kind=kind)
    db.add(client)
    db.commit()
    return client


def list_clients(db: Session, ctx: TenantContext) -> list[PSClient]:
    stmt = scoped(select(PSClient), PSClient, ctx).order_by(PSClient.name)
    return list(db.scalars(stmt))


def get_client(db: Session, ctx: TenantContext, client_id: uuid.UUID) -> PSClient | None:
    stmt = scoped(select(PSClient), PSClient, ctx).where(PSClient.id == client_id)
    return db.scalar(stmt)
