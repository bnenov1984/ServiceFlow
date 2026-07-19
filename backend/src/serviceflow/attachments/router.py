"""Attachment endpoints per docs/09: multipart upload, authorized file stream,
soft delete. Mounted at /api/v1 (flat + order-nested, matching docs/09's split)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from business_os.identity.deps import TenantDbDep, TenantDep, require_csrf
from business_os.shared_kernel.storage import LocalFilesystemStorage, get_local_storage
from serviceflow.attachments import service
from serviceflow.attachments.models import Attachment
from serviceflow.config import get_settings
from serviceflow.service_orders import service as orders_service

router = APIRouter()


class AttachmentOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    kind: str
    stage: str
    caption: str
    mime: str
    size: int
    has_thumbnail: bool

    @staticmethod
    def of(a: Attachment) -> "AttachmentOut":
        return AttachmentOut(
            id=a.id, order_id=a.order_id, kind=a.kind, stage=a.stage, caption=a.caption,
            mime=a.mime, size=a.size, has_thumbnail=a.thumbnail_key is not None,
        )


def _storage() -> LocalFilesystemStorage:
    settings = get_settings()
    return get_local_storage(str(settings.data_dir / "attachments"))


def _err(e: service.AttachmentError) -> HTTPException:
    return HTTPException(status_code=e.status, detail={
        "code": "attachment_error", "message_key": e.message_key, "params": {},
    })


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={
        "code": "not_found", "message_key": "errors.attachments.not_found", "params": {},
    })


@router.get("/orders/{order_id}/attachments")
def list_attachments(order_id: uuid.UUID, db: TenantDbDep,
                     tenant: TenantDep) -> list[AttachmentOut]:
    if orders_service.get(db, tenant, order_id) is None:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message_key": "errors.orders.not_found", "params": {},
        })
    return [AttachmentOut.of(a) for a in service.list_for_order(db, tenant, order_id)]


@router.post("/orders/{order_id}/attachments", dependencies=[Depends(require_csrf)],
             status_code=201)
def upload_attachment(order_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep,
                      file: Annotated[UploadFile, File()],
                      stage: Annotated[str, Form()] = "other",
                      caption: Annotated[str, Form()] = "") -> AttachmentOut:
    if orders_service.get(db, tenant, order_id) is None:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message_key": "errors.orders.not_found", "params": {},
        })
    settings = get_settings()
    data = file.file.read()  # sync read: this endpoint stays a plain def (rest of the
    # app is sync SQLAlchemy; an async def here would block the event loop instead).
    try:
        attachment = service.upload(
            db, tenant, _storage(), order_id=order_id, data=data, stage=stage,
            caption=caption, max_bytes=settings.attachments_max_bytes,
            max_per_order=settings.attachments_max_per_order,
        )
    except service.AttachmentError as e:
        raise _err(e) from e
    return AttachmentOut.of(attachment)


@router.get("/attachments/{attachment_id}/file")
def get_attachment_file(attachment_id: uuid.UUID, db: TenantDbDep, tenant: TenantDep,
                        thumb: bool = False) -> Response:
    attachment = service.get(db, tenant, attachment_id)
    if attachment is None:
        raise _not_found()
    key = (attachment.thumbnail_key if thumb and attachment.thumbnail_key
          else attachment.storage_key)
    data = _storage().get(key)
    ext = "jpg" if attachment.mime == "image/jpeg" else "pdf"
    return Response(
        content=data, media_type=attachment.mime,
        headers={"Content-Disposition": f'inline; filename="{attachment.id}.{ext}"'},
    )


@router.delete("/attachments/{attachment_id}", dependencies=[Depends(require_csrf)])
def delete_attachment(attachment_id: uuid.UUID, db: TenantDbDep,
                      tenant: TenantDep) -> dict[str, bool]:
    attachment = service.get(db, tenant, attachment_id)
    if attachment is None:
        raise _not_found()
    service.soft_delete(db, tenant, attachment)
    return {"ok": True}
