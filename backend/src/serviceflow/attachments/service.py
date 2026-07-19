"""Attachment operations: validate, re-encode, store, soft-delete. Every upload
is timelined (docs/01 §5: AttachmentAdded)."""

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from business_os.shared_kernel.db import TenantContext, scoped
from business_os.shared_kernel.events import DomainEvent, publish
from business_os.shared_kernel.storage import StoragePort
from serviceflow.attachments import media
from serviceflow.attachments.models import Attachment

ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp", "image/heic", "application/pdf"}
ALLOWED_STAGES = ("reception", "progress", "completed", "other")


class AttachmentError(Exception):
    def __init__(self, message_key: str, status: int = 400) -> None:
        self.message_key = message_key
        self.status = status


def _content_key(data: bytes, suffix: str = "") -> str:
    return hashlib.sha256(data).hexdigest() + suffix


def count_for_order(db: Session, ctx: TenantContext, order_id: uuid.UUID) -> int:
    return db.scalar(
        scoped(select(func.count()).select_from(Attachment), Attachment, ctx)
        .where(Attachment.order_id == order_id, Attachment.deleted_at.is_(None))
    ) or 0


def upload(db: Session, ctx: TenantContext, storage: StoragePort, *, order_id: uuid.UUID,
           data: bytes, stage: str, caption: str, max_bytes: int,
           max_per_order: int) -> Attachment:
    if stage not in ALLOWED_STAGES:
        raise AttachmentError("errors.attachments.invalid_stage")
    if len(data) > max_bytes:
        raise AttachmentError("errors.attachments.too_large", status=413)
    if count_for_order(db, ctx, order_id) >= max_per_order:
        raise AttachmentError("errors.attachments.too_many", status=409)

    mime = media.sniff_mime(data)
    if mime is None or mime not in ALLOWED_MIMES:
        raise AttachmentError("errors.attachments.unsupported_type", status=415)

    thumbnail_key: str | None = None
    if media.is_image(mime):
        # Re-encode always (docs/11 §3): strips embedded payloads, normalizes HEIC/
        # PNG/WEBP to JPEG regardless of the original claimed format.
        stored = media.reencode_image(data)
        mime = "image/jpeg"
        thumb = media.make_thumbnail(stored)
        thumbnail_key = _content_key(thumb, ".jpg")
        storage.put(thumbnail_key, thumb)
    else:
        stored = data  # PDFs: stored as-is (no re-encoding requirement documented)

    key = _content_key(stored, ".jpg" if media.is_image(mime) else ".pdf")
    storage.put(key, stored)

    attachment = Attachment(
        company_id=ctx.company_id, order_id=order_id, storage_key=key,
        thumbnail_key=thumbnail_key, kind="photo" if media.is_image(mime) else "document",
        stage=stage, caption=caption, mime=mime, size=len(stored),
        uploaded_by=ctx.user_id,
    )
    db.add(attachment)
    db.flush()
    publish(db, DomainEvent(type="attachment_added", company_id=ctx.company_id,
                            actor_user_id=ctx.user_id, order_id=order_id,
                            data={"kind": attachment.kind, "stage": stage}))
    db.commit()
    return attachment


def get(db: Session, ctx: TenantContext, attachment_id: uuid.UUID) -> Attachment | None:
    return db.scalar(
        scoped(select(Attachment), Attachment, ctx)
        .where(Attachment.id == attachment_id, Attachment.deleted_at.is_(None))
    )


def list_for_order(db: Session, ctx: TenantContext, order_id: uuid.UUID) -> list[Attachment]:
    return list(db.scalars(
        scoped(select(Attachment), Attachment, ctx)
        .where(Attachment.order_id == order_id, Attachment.deleted_at.is_(None))
        .order_by(Attachment.created_at)
    ))


def soft_delete(db: Session, ctx: TenantContext, attachment: Attachment) -> None:
    attachment.deleted_at = datetime.now(UTC)
    publish(db, DomainEvent(type="attachment_deleted", company_id=ctx.company_id,
                            actor_user_id=ctx.user_id, order_id=attachment.order_id,
                            data={}))
    db.commit()
