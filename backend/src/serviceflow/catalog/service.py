"""CatalogItem CRUD + CSV/Excel import (ADR-BOS-013, order-workflow-revamp
WP-I). Owner-only mutations are enforced at the router layer
(`business_os.identity.deps.require_owner`), same division of labor as every
other Owner-gated endpoint in this codebase — this module only enforces data
invariants (uniqueness, valid kind/unit, archived-not-deleted).
"""

import csv
import io
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from business_os.shared_kernel.db import TenantContext, scoped
from serviceflow.catalog.models import KINDS, UNITS, CatalogItem

_KIND_BG = {"part": "част", "labor": "труд"}
_BG_KIND = {v: k for k, v in _KIND_BG.items()}
_UNIT_BG = {"pcs": "бр.", "hour": "час"}
_BG_UNIT = {v: k for k, v in _UNIT_BG.items()}

# Import file columns, in order — matches what the Owner exports/edits in a
# spreadsheet: a human-facing kind/unit vocabulary (бр./час, част/труд), not
# the internal slugs, and `sale_price` is the only required money column.
IMPORT_COLUMNS = ("kind", "name", "code", "unit", "sale_price", "unit_cost")


class CatalogError(Exception):
    def __init__(self, message_key: str, status: int = 400) -> None:
        self.message_key = message_key
        self.status = status


class CodeConflictError(Exception):
    """Raised when a create/update would give this tenant two active catalog
    rows with the same code — mirrors assets' VinConflictError/RegConflictError
    shape (one exception per uniqueness rule, carrying the conflicting row's
    id so the caller can offer a precise message)."""

    def __init__(self, existing_item_id: uuid.UUID) -> None:
        self.existing_item_id = existing_item_id


def list_items(db: Session, ctx: TenantContext, *, kind: str | None = None,
               include_archived: bool = False) -> list[CatalogItem]:
    stmt = scoped(select(CatalogItem), CatalogItem, ctx)
    if kind is not None:
        stmt = stmt.where(CatalogItem.kind == kind)
    if not include_archived:
        stmt = stmt.where(CatalogItem.archived_at.is_(None))
    return list(db.scalars(stmt.order_by(CatalogItem.name)))


def get(db: Session, ctx: TenantContext, item_id: uuid.UUID) -> CatalogItem | None:
    return db.scalar(scoped(select(CatalogItem), CatalogItem, ctx).where(
        CatalogItem.id == item_id
    ))


def get_many(db: Session, ctx: TenantContext,
            item_ids: list[uuid.UUID]) -> dict[uuid.UUID, CatalogItem]:
    if not item_ids:
        return {}
    rows = db.scalars(scoped(select(CatalogItem), CatalogItem, ctx).where(
        CatalogItem.id.in_(item_ids)
    ))
    return {i.id: i for i in rows}


def _check_code_conflict(db: Session, ctx: TenantContext, code: str | None,
                         exclude_id: uuid.UUID | None) -> None:
    if not code:
        return
    stmt = scoped(select(CatalogItem.id), CatalogItem, ctx).where(CatalogItem.code == code)
    if exclude_id is not None:
        stmt = stmt.where(CatalogItem.id != exclude_id)
    existing = db.scalar(stmt)
    if existing is not None:
        raise CodeConflictError(existing)


def create(db: Session, ctx: TenantContext, *, kind: str, name: str, unit: str,
          sale_price: Decimal, code: str | None = None,
          unit_cost: Decimal | None = None) -> CatalogItem:
    if kind not in KINDS:
        raise CatalogError("errors.catalog.invalid_kind")
    if unit not in UNITS:
        raise CatalogError("errors.catalog.invalid_unit")
    _check_code_conflict(db, ctx, code, exclude_id=None)
    item = CatalogItem(company_id=ctx.company_id, kind=kind, name=name, code=code or None,
                       unit=unit, sale_price=sale_price, unit_cost=unit_cost)
    db.add(item)
    db.commit()
    return item


def update(db: Session, ctx: TenantContext, item: CatalogItem,
          fields: dict[str, Any]) -> CatalogItem:
    if "kind" in fields and fields["kind"] not in KINDS:
        raise CatalogError("errors.catalog.invalid_kind")
    if "unit" in fields and fields["unit"] not in UNITS:
        raise CatalogError("errors.catalog.invalid_unit")
    if "code" in fields:
        _check_code_conflict(db, ctx, fields["code"], exclude_id=item.id)
    for key, value in fields.items():
        if key == "code" and value == "":
            value = None
        setattr(item, key, value)
    db.commit()
    return item


def archive(db: Session, item: CatalogItem) -> None:
    item.archived_at = datetime.now(UTC)
    db.commit()


def unarchive(db: Session, item: CatalogItem) -> None:
    item.archived_at = None
    db.commit()


# --- CSV/Excel import (Q12b) -------------------------------------------------

@dataclass(frozen=True)
class ImportRow:
    row_number: int  # 1-based, header excluded — for the Owner's own error review
    action: str  # "insert" | "update" | "error"
    kind: str = ""
    name: str = ""
    code: str | None = None
    unit: str = ""
    sale_price: str = ""
    unit_cost: str | None = None
    error: str | None = None
    # Only set for action="update" — lets the preview show what changes.
    existing_item_id: uuid.UUID | None = None


@dataclass(frozen=True)
class ImportResult:
    rows: list[ImportRow] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.rows if r.action == "error")

    @property
    def insert_count(self) -> int:
        return sum(1 for r in self.rows if r.action == "insert")

    @property
    def update_count(self) -> int:
        return sum(1 for r in self.rows if r.action == "update")


def _read_rows(data: bytes, filename: str) -> list[dict[str, str]]:
    """Returns a list of {column: raw string value} dicts, header-normalized
    to IMPORT_COLUMNS (case-insensitive, Bulgarian or English header labels
    both accepted) — one shape for both CSV and .xlsx so the rest of this
    module never branches on file format again."""
    header_aliases = {
        "kind": "kind", "вид": "kind", "тип": "kind",
        "name": "name", "име": "name", "наименование": "name",
        "code": "code", "код": "code",
        "unit": "unit", "мярка": "unit", "ед.": "unit",
        "sale_price": "sale_price", "цена": "sale_price", "продажна цена": "sale_price",
        "unit_cost": "unit_cost", "себестойност": "unit_cost", "доставна цена": "unit_cost",
    }

    def _normalize_header(raw: list[Any]) -> list[str]:
        return [header_aliases.get(str(h).strip().lower(), str(h).strip().lower())
               for h in raw]

    if filename.lower().endswith((".xlsx", ".xlsm")):
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb.active
        if ws is None:  # an empty workbook with no sheets at all
            return []
        rows_iter = ws.iter_rows(values_only=True)
        try:
            header = _normalize_header(list(next(rows_iter)))
        except StopIteration:
            return []
        out = []
        for raw_cells in rows_iter:
            if all(c is None for c in raw_cells):
                continue
            out.append({
                col: ("" if val is None else str(val))
                for col, val in zip(header, raw_cells, strict=False)
            })
        return out

    text = data.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    try:
        header = _normalize_header(next(reader))
    except StopIteration:
        return []
    out = []
    for raw_row in reader:
        if not any(c.strip() for c in raw_row):
            continue
        out.append({col: val for col, val in zip(header, raw_row, strict=False)})
    return out


def preview_import(db: Session, ctx: TenantContext, data: bytes,
                   filename: str) -> ImportResult:
    """Dry-run only — never writes. Matches an existing row by `code` when
    the imported row has one (→ update), otherwise always inserts (Q12b:
    "match by code when present → update, else insert")."""
    raw_rows = _read_rows(data, filename)
    existing_by_code = {
        i.code: i for i in list_items(db, ctx, include_archived=True) if i.code
    }
    # Tracks codes already claimed by an earlier row *in this same file* — two
    # new rows sharing a code would otherwise both come back "insert" here
    # (neither matches an *existing* DB row) and then collide on the
    # `(company_id, code)` unique index at commit time. Caught here instead,
    # as an error row, so the Owner sees it in the preview rather than a
    # failed commit.
    codes_in_file: set[str] = set()
    rows: list[ImportRow] = []
    for i, raw in enumerate(raw_rows, start=1):
        row = _validate_row(i, raw, existing_by_code, codes_in_file)
        if row.action != "error" and row.code is not None:
            codes_in_file.add(row.code)
        rows.append(row)
    return ImportResult(rows=rows)


def _validate_row(row_number: int, raw: dict[str, str],
                  existing_by_code: dict[str, CatalogItem],
                  codes_in_file: set[str]) -> ImportRow:
    kind_raw = raw.get("kind", "").strip().lower()
    kind = _BG_KIND.get(kind_raw, kind_raw)
    name = raw.get("name", "").strip()
    code = raw.get("code", "").strip() or None
    unit_raw = raw.get("unit", "").strip().lower()
    unit = _BG_UNIT.get(unit_raw, unit_raw)
    sale_price_raw = raw.get("sale_price", "").strip()
    unit_cost_raw = raw.get("unit_cost", "").strip()

    if kind not in KINDS:
        return ImportRow(row_number=row_number, action="error", kind=kind_raw, name=name,
                         code=code, error="errors.catalog.import_invalid_kind")
    if not name:
        return ImportRow(row_number=row_number, action="error", kind=kind, name=name,
                         code=code, error="errors.catalog.import_missing_name")
    if unit not in UNITS:
        return ImportRow(row_number=row_number, action="error", kind=kind, name=name,
                         code=code, error="errors.catalog.import_invalid_unit")
    try:
        sale_price = Decimal(sale_price_raw)
        if sale_price < 0:
            raise InvalidOperation
    except InvalidOperation:
        return ImportRow(row_number=row_number, action="error", kind=kind, name=name,
                         code=code, error="errors.catalog.import_invalid_price")
    unit_cost: Decimal | None = None
    if unit_cost_raw:
        try:
            unit_cost = Decimal(unit_cost_raw)
        except InvalidOperation:
            return ImportRow(row_number=row_number, action="error", kind=kind, name=name,
                             code=code, error="errors.catalog.import_invalid_cost")

    existing = existing_by_code.get(code) if code else None
    if code is not None and existing is None and code in codes_in_file:
        return ImportRow(row_number=row_number, action="error", kind=kind, name=name,
                         code=code, error="errors.catalog.import_duplicate_code_in_file")
    return ImportRow(
        row_number=row_number, action="update" if existing else "insert",
        kind=kind, name=name, code=code, unit=unit,
        sale_price=str(sale_price), unit_cost=str(unit_cost) if unit_cost is not None else None,
        existing_item_id=existing.id if existing else None,
    )


def commit_import(db: Session, ctx: TenantContext, data: bytes, filename: str) -> ImportResult:
    """Re-validates and applies — never trusts a client-supplied preview
    (the same data could have changed company-side between preview and
    commit). Rows with action="error" are skipped, not applied; every
    insert/update happens in one transaction."""
    result = preview_import(db, ctx, data, filename)
    for row in result.rows:
        if row.action == "error":
            continue
        sale_price = Decimal(row.sale_price)
        unit_cost = Decimal(row.unit_cost) if row.unit_cost is not None else None
        if row.action == "update" and row.existing_item_id is not None:
            item = get(db, ctx, row.existing_item_id)
            assert item is not None
            item.kind = row.kind
            item.name = row.name
            item.unit = row.unit
            item.sale_price = sale_price
            item.unit_cost = unit_cost
        else:
            db.add(CatalogItem(
                company_id=ctx.company_id, kind=row.kind, name=row.name, code=row.code,
                unit=row.unit, sale_price=sale_price, unit_cost=unit_cost,
            ))
    db.commit()
    return result
