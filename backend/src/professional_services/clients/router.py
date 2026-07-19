import uuid

from fastapi import APIRouter, Depends, HTTPException

from business_os.identity.deps import TenantDbDep, TenantDep, require_csrf
from professional_services.deps import require_ps_active

from . import service
from .models import PSClient
from .schemas import ClientCreate, ClientOut

router = APIRouter(dependencies=[Depends(require_ps_active)])


def _out(c: PSClient) -> ClientOut:
    return ClientOut(id=c.id, name=c.name, kind=c.kind)


@router.get("/clients")
def list_clients(db: TenantDbDep, tenant: TenantDep) -> list[ClientOut]:
    return [_out(c) for c in service.list_clients(db, tenant)]


@router.post("/clients", dependencies=[Depends(require_csrf)])
def create_client(body: ClientCreate, db: TenantDbDep, tenant: TenantDep) -> ClientOut:
    return _out(service.create_client(db, tenant, body.name, body.kind))


@router.get("/clients/{client_id}")
def get_client(client_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep) -> ClientOut:
    client = service.get_client(db, tenant, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message_key": "errors.ps.client_not_found", "params": {},
        })
    return _out(client)
