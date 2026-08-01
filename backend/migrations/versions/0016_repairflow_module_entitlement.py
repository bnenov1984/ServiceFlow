"""Migration #16: RepairFlow becomes a real, vendor-granted entitlement
(PO decision, 01.08.2026), not an implicit baseline every company had for
free. `professional_services` already goes through the same
`companies.settings.active_modules` JSONB list
(`identity.service.is_module_active`/`activate_module`) — RepairFlow just
never had a backend guard checking it, so nothing ever needed the key to be
present. Now that `serviceflow.customers`/`assets`/`service_orders`/
`commercial`/`tasks`/`attachments`/`contacts`/`dashboard`/`search` all gate
on `require_repairflow_active`, every company that predates this migration
must be backfilled with `"repairflow"` in its `active_modules` — otherwise
every existing tenant (all local/dev/test data; no deployed environment
exists yet, same posture migration 0015 documented) is locked out of the
application it was already using.

Data-only, no schema change — unlike migration 0015, there is no RLS/FK
ceremony here, just a JSONB update on `companies.settings`, idempotent (only
touches rows that don't already have the key).

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-01
"""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE companies
        SET settings = jsonb_set(
            settings,
            '{active_modules}',
            COALESCE(settings -> 'active_modules', '[]'::jsonb) || '["repairflow"]'::jsonb
        )
        WHERE NOT (COALESCE(settings -> 'active_modules', '[]'::jsonb) @> '["repairflow"]'::jsonb)
    """)


def downgrade() -> None:
    # Best-effort, local-dev-reset only (docs/04 §3 / ADR-017: forward-only
    # governs *deployed* environments, not this) — removes "repairflow" from
    # every company's active_modules, symmetric with upgrade().
    op.execute("""
        UPDATE companies
        SET settings = jsonb_set(
            settings,
            '{active_modules}',
            (
                SELECT COALESCE(jsonb_agg(elem), '[]'::jsonb)
                FROM jsonb_array_elements(COALESCE(settings -> 'active_modules', '[]'::jsonb)) elem
                WHERE elem <> '"repairflow"'::jsonb
            )
        )
        WHERE COALESCE(settings -> 'active_modules', '[]'::jsonb) @> '["repairflow"]'::jsonb
    """)
