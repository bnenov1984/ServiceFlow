"""Global search (P0-7, docs/02 §14): grouped, normalized, tenant-scoped.

Normalization is symmetric with the write path (shared_kernel.normalize): the
query is transliterated / digit-stripped the same way the shadow columns were.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from serviceflow.assets.models import Asset, AssetIdentifier
from serviceflow.customers.models import Customer
from serviceflow.service_orders.models import ServiceOrder
from serviceflow.shared_kernel.db import TenantContext, scoped
from serviceflow.shared_kernel.normalize import (
    normalize_identifier,
    normalize_phone,
    transliterate,
)

GROUP_LIMIT = 5
MIN_QUERY_LEN = 2


@dataclass(frozen=True)
class CustomerHit:
    id: uuid.UUID
    name: str
    phone: str


@dataclass(frozen=True)
class OrderHit:
    id: uuid.UUID
    number: str
    status_code: str
    customer_name: str


@dataclass(frozen=True)
class AssetHit:
    id: uuid.UUID
    label: str
    customer_id: uuid.UUID
    customer_name: str
    matched_identifier: str


@dataclass(frozen=True)
class SearchResults:
    customers: list[CustomerHit]
    orders: list[OrderHit]
    assets: list[AssetHit]


def global_search(db: Session, ctx: TenantContext, q: str) -> SearchResults:
    q = q.strip()
    if len(q) < MIN_QUERY_LEN:
        return SearchResults([], [], [])

    translit_q = transliterate(q)
    phone_q = normalize_phone(q)
    ident_q = normalize_identifier(q)

    # P1: customers by name (Cyrillic/Latin tolerant) or phone fragment.
    conditions = [Customer.name_translit.contains(translit_q)]
    if phone_q:
        conditions.append(Customer.phone_normalized.contains(phone_q))
    customers = list(db.scalars(
        scoped(select(Customer), Customer, ctx)
        .where(Customer.archived_at.is_(None), or_(*conditions))
        .order_by(Customer.name_translit).limit(GROUP_LIMIT)
    ))

    # P1: orders by human number fragment ("42", "00042", "2026-00042").
    order_rows = db.execute(
        scoped(select(ServiceOrder, Customer.name), ServiceOrder, ctx)
        .join(Customer, Customer.id == ServiceOrder.customer_id)
        .where(ServiceOrder.number.contains(q))
        .order_by(ServiceOrder.created_at.desc()).limit(GROUP_LIMIT)
    ).all()

    # P2: assets by normalized identifier fragment (IMEI/VIN/serial/рег.№).
    asset_rows: list[tuple[Asset, str, str]] = []
    if len(ident_q) >= 3:
        asset_rows = [
            (row[0], row[1], row[2])
            for row in db.execute(
                scoped(select(Asset, Customer.name, AssetIdentifier.value),
                       AssetIdentifier, ctx)
                .join(Asset, Asset.id == AssetIdentifier.asset_id)
                .join(Customer, Customer.id == Asset.customer_id)
                .where(AssetIdentifier.value_normalized.contains(ident_q))
                .limit(GROUP_LIMIT)
            ).all()
        ]

    return SearchResults(
        customers=[CustomerHit(c.id, c.name, c.phone) for c in customers],
        orders=[OrderHit(o.id, o.number, o.status_code, name) for o, name in order_rows],
        assets=[AssetHit(a.id, a.label, a.customer_id, cname, ident)
                for a, cname, ident in asset_rows],
    )
