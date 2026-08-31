"""Migration #23: vehicle identity + ownership history (Wave 3 Issue 20).

Two independent, additive changes:

1. `asset_ownership` — append-only ownership-span history per Asset.
   `Asset.customer_id` stays the current-owner pointer (unchanged);
   `ServiceOrder.asset_id`/`.customer_id` already need no change of their own
   — an order already correctly records which customer walked in *that day*,
   and `asset_id` already correctly identifies the one persistent vehicle
   regardless of who owned it then. This table adds the missing piece: a
   queryable, append-only "who owned this asset, and when" history, so an
   ownership change (`serviceflow.assets.service.transfer_owner`) never has
   to duplicate the Asset row to represent a new owner.

   Backfilled with exactly one open ownership row per already-existing asset
   (`customer_id = assets.customer_id`, `started_at = assets.created_at`,
   `ended_at = NULL`) — no asset is ever left without an ownership record.
   A partial unique index enforces at most one *open* row per asset (the
   invariant `transfer_owner` relies on when closing/opening spans).

2. A partial unique index on `asset_identifiers (company_id, value_normalized)
   WHERE kind = 'vin'` — "one normalized VIN = one vehicle Asset per tenant"
   (Issue 20's final product rule). Scoped to `kind = 'vin'` only: IMEI/
   serial/рег.№ keep today's soft-duplicate-hint behavior unchanged. Blank/
   missing VINs never reach `asset_identifiers` at all
   (`serviceflow.assets.service._extract_identifiers` already skips empty
   values), so a vehicle with no VIN entered is never blocked by this index.

   Safety: `upgrade()` checks for existing duplicate normalized VINs first
   and raises a clear, actionable error instead of letting Postgres reject
   the CREATE UNIQUE INDEX with an opaque constraint-violation trace. No
   auto-merge is performed. Alembic runs this whole migration in one
   transaction (backend/migrations/env.py has no `transaction_per_migration`),
   so a raised error here rolls back the entire migration — including the
   asset_ownership table above — leaving the database exactly at revision
   0022 until the operator resolves the conflicting rows by hand and
   re-runs.

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def _rls(table: str) -> str:
    return f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON {table}
    USING (company_id = NULLIF(current_setting('app.company_id', true), '')::uuid);
"""


def upgrade() -> None:
    # --- 1. asset_ownership -------------------------------------------------
    op.create_table(
        "asset_ownership",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id", name="fk_asset_ownership_company_id_companies"),
                  nullable=False),
        sa.Column("asset_id", UUID(as_uuid=True),
                  sa.ForeignKey("assets.id", name="fk_asset_ownership_asset_id_assets"),
                  nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True),
                  sa.ForeignKey("customers.id", name="fk_asset_ownership_customer_id_customers"),
                  nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_asset_ownership_asset_id", "asset_ownership", ["asset_id"])
    op.create_index(
        "uq_asset_ownership_open", "asset_ownership", ["asset_id"],
        unique=True, postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.execute(_rls("asset_ownership"))

    op.execute("""
        INSERT INTO asset_ownership (id, company_id, asset_id, customer_id, started_at, ended_at)
        SELECT gen_random_uuid(), company_id, id, customer_id, created_at, NULL
        FROM assets
    """)

    # --- 2. VIN uniqueness ---------------------------------------------------
    bind = op.get_bind()
    dupes = bind.execute(sa.text("""
        SELECT company_id, value_normalized, array_agg(id) AS ids, array_agg(asset_id) AS asset_ids
        FROM asset_identifiers
        WHERE kind = 'vin'
        GROUP BY company_id, value_normalized
        HAVING COUNT(*) > 1
    """)).all()
    if dupes:
        details = "; ".join(
            f"company={row.company_id} vin={row.value_normalized} "
            f"asset_identifier_ids={row.ids} asset_ids={row.asset_ids}"
            for row in dupes
        )
        raise RuntimeError(
            "Migration 0023 stopped before adding the VIN uniqueness index: "
            "duplicate normalized VINs already exist and would violate it. "
            "No automatic merge is performed — resolve these rows by hand "
            "(decide which asset is the real vehicle, clear or correct the "
            f"other's VIN) and re-run this migration. Conflicts: {details}"
        )

    op.create_index(
        "uq_asset_identifiers_vin_company_value", "asset_identifiers",
        ["company_id", "value_normalized"], unique=True,
        postgresql_where=sa.text("kind = 'vin'"),
    )


def downgrade() -> None:
    # Best-effort, local-dev-reset only (docs/04 §3 / ADR-017: forward-only
    # governs *deployed* environments, not this).
    op.drop_index("uq_asset_identifiers_vin_company_value", table_name="asset_identifiers")
    op.drop_table("asset_ownership")
