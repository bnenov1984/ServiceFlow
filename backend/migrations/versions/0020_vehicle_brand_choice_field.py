"""Migration #20: vehicle asset type's `brand` field becomes a choice list
(Issue 23), forward-updating every already-provisioned company's existing
`vehicle` asset_type row — not just serviceflow.assets.service.DEFAULT_TYPES,
which only backs companies provisioned *after* this point (copy-on-
provisioning, same discipline migration 0016 documented for
`active_modules`). Historical migration 0015's own frozen SEED_TYPES snapshot
is deliberately left untouched — it already ran, backfilling only the
companies that existed before it; rewriting it now would rewrite history
without reaching a single live company.

Data-only, no schema change. Idempotent: only rewrites rows still on the old
free-text `brand` definition, so a re-run never double-applies. Only the
`vehicle` asset type's `brand` field entry within `field_defs` is touched —
every other field (`model`, `reg_no`, `vin`, `year`, `mileage`) and every
other asset type (`phone`, `laptop`, `other`) passes through byte-for-byte
unchanged (WHERE code = 'vehicle' scopes the UPDATE; the CASE inside the
jsonb_agg only rewrites the one array element whose key is "brand").
`assets.field_values` — actual vehicle records already saved with a
free-text brand — is not touched at all: this migration changes the field
*definition* a form renders against, never stored asset data, so no existing
vehicle asset is altered or lost.

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-29
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

# Identical to serviceflow.assets.service.DEFAULT_TYPES' current "vehicle"
# brand field_def (Issue 23) — migrations never import application code, so
# this is a deliberate, documented duplicate, same discipline as migration
# 0015/0016's own SEED_TYPES/active_modules literals.
NEW_BRAND_FIELD_DEF = {
    "key": "brand", "label_bg": "Марка", "type": "choice", "choices": [
        "Audi", "BMW", "Chevrolet", "Citroën", "Dacia", "Fiat", "Ford",
        "Honda", "Hyundai", "Kia", "Lada", "Land Rover", "Mazda",
        "Mercedes-Benz", "Mini", "Mitsubishi", "Nissan", "Opel",
        "Peugeot", "Renault", "Seat", "Škoda", "Subaru", "Suzuki",
        "Toyota", "Volkswagen", "Volvo", "Друго",
    ],
}

OLD_BRAND_FIELD_DEF = {"key": "brand", "label_bg": "Марка", "type": "text"}

_UPDATE_SQL = """
    UPDATE asset_types
    SET field_defs = (
        SELECT jsonb_agg(
            CASE WHEN elem->>'key' = 'brand' THEN CAST(:new_def AS jsonb) ELSE elem END
            ORDER BY ord
        )
        FROM jsonb_array_elements(field_defs) WITH ORDINALITY AS t(elem, ord)
    )
    WHERE code = 'vehicle'
      AND EXISTS (
          SELECT 1 FROM jsonb_array_elements(field_defs) e
          WHERE e->>'key' = 'brand' AND e->>'type' = :old_type
      )
"""


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(_UPDATE_SQL),
        {"new_def": json.dumps(NEW_BRAND_FIELD_DEF), "old_type": "text"},
    )


def downgrade() -> None:
    # Best-effort, local-dev-reset only (docs/04 §3 / ADR-017: forward-only
    # governs *deployed* environments, not this) — symmetric with upgrade().
    op.get_bind().execute(
        sa.text(_UPDATE_SQL),
        {"new_def": json.dumps(OLD_BRAND_FIELD_DEF), "old_type": "choice"},
    )
