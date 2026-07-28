"""Migration #15: asset_types becomes company-scoped (ADR-BOS-011 §Decision 5,
docs/business-os/18 §6.4 — "the largest of the four proposed changes").

Before this migration, `asset_types` is global seed data: `code` is a bare
primary key, every company sees the same four types. After it, every company
owns its own copy of the type set (copy-on-provisioning, the same discipline
`ps_assignment_stages` already established for workflow-template stages —
ADR-PS-005: "stage copies, not template references"), tagged with the
RepairFlow business profile it was seeded under.

**Content is identical across all five profiles in this migration.** Per PO
decision (docs/business-os/18 §15, 28.07.2026): `automotive_repair`/
`phone_repair`/`electronics_repair`/`appliance_repair` are structural
placeholders only — no per-profile field_defs exist yet, so every company's
copy, regardless of assigned profile, gets today's exact four types (phone,
vehicle, laptop, other). The `business_profile` column exists specifically so
a future migration can seed different content per profile without another
schema change — only the seeding *logic*
(`serviceflow.assets.service.seed_default_types`) would need to branch on it.

**Single clean migration, not the additive-first (parallel-table,
cut-over-later) strategy docs/business-os/18 §6.4 recommends.** That
recommendation is written for a scenario with real production tenants whose
data must survive a rolling deployment — this project has none yet (Etap 2/3
frontend is unbuilt, docs/13; ADR-017's forward-only policy governs *deployed*
environments, which this isn't). Explicit PO decision, 28.07.2026: use one
migration now; return to additive-first for any future schema change that
touches real customer data once the platform is live.

Existing companies (there are none in any deployed environment, only
local/test data) are backfilled with their own copy of the current four
types, tagged with whatever business_profile they already have assigned
(`companies.settings.repairflow.business_profile`) or `generic_repair` if
none was ever set — companies created via `identity.service.seed_company`
predate that field entirely.

`assets.asset_type_code` (a global-code FK) becomes `assets.asset_type_id`
(a UUID FK to the new per-company `asset_types.id`) — recommended over a
compound `(company_id, code)` FK by docs/business-os/18 §6.4 itself ("to
match the rest of the schema... rather than a composite key, which nothing
else in this codebase uses" — confirmed by grep: no composite FK exists
anywhere today). The API wire contract is unaffected: `asset_type_code`
remains what clients send/receive; the app resolves it to the company-scoped
row's `id` at the boundary (serviceflow/assets/router.py).

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-28
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def _rls(table: str) -> str:
    return f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON {table}
    USING (company_id = NULLIF(current_setting('app.company_id', true), '')::uuid);
"""


# Identical to migration 0003's SEED_TYPES — migrations never import
# application code (it may change independently later), so this is a
# deliberate, frozen copy, not a re-export. `serviceflow.assets.service.
# DEFAULT_TYPES` is the runtime copy used going forward by
# `seed_default_types` for every company provisioned after this migration.
SEED_TYPES = [
    {
        "code": "phone", "name_bg": "Телефон", "icon": "smartphone", "sort": 1,
        "field_defs": [
            {"key": "brand", "label_bg": "Марка", "type": "text"},
            {"key": "model", "label_bg": "Модел", "type": "text"},
            {"key": "imei", "label_bg": "IMEI", "type": "text", "identifier_kind": "imei"},
            {"key": "serial_no", "label_bg": "Сериен №", "type": "text",
             "identifier_kind": "serial"},
            {"key": "color", "label_bg": "Цвят", "type": "text"},
        ],
    },
    {
        "code": "vehicle", "name_bg": "Автомобил", "icon": "car", "sort": 2,
        "field_defs": [
            {"key": "brand", "label_bg": "Марка", "type": "text"},
            {"key": "model", "label_bg": "Модел", "type": "text"},
            {"key": "reg_no", "label_bg": "Рег. №", "type": "text", "identifier_kind": "reg"},
            {"key": "vin", "label_bg": "VIN", "type": "text", "identifier_kind": "vin"},
            {"key": "year", "label_bg": "Година", "type": "number"},
            {"key": "mileage", "label_bg": "Пробег (км)", "type": "number"},
        ],
    },
    {
        "code": "laptop", "name_bg": "Лаптоп/Компютър", "icon": "laptop", "sort": 3,
        "field_defs": [
            {"key": "brand", "label_bg": "Марка", "type": "text"},
            {"key": "model", "label_bg": "Модел", "type": "text"},
            {"key": "serial_no", "label_bg": "Сериен №", "type": "text",
             "identifier_kind": "serial"},
        ],
    },
    {
        "code": "other", "name_bg": "Друго", "icon": "wrench", "sort": 4,
        "field_defs": [
            {"key": "description", "label_bg": "Описание", "type": "text"},
            {"key": "identifier", "label_bg": "Идентификатор", "type": "text",
             "identifier_kind": "other"},
        ],
    },
]


def upgrade() -> None:
    # 1. Add the new columns nullable first — the data migration below
    #    populates them before any NOT NULL/constraint is applied.
    op.add_column("asset_types", sa.Column("id", UUID(as_uuid=True), nullable=True))
    op.add_column("asset_types", sa.Column("company_id", UUID(as_uuid=True), nullable=True))
    op.add_column("asset_types", sa.Column("business_profile", sa.String(), nullable=True))
    op.add_column("asset_types", sa.Column(
        "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now(),
    ))
    op.add_column("asset_types", sa.Column(
        "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(),
    ))

    # 2. Drop the code-based FK and the old bare-`code` primary key *before*
    #    backfilling — not after, as this migration originally had it. The
    #    old PK enforces uniqueness on `code` alone; leaving it active during
    #    the backfill below means inserting a per-company copy of e.g.
    #    'phone' collides with the still-present original global 'phone' row
    #    (`UniqueViolation` on `pk_asset_types`) on any database that already
    #    has a company — which every real local/dev database does, just not
    #    a freshly-created empty test database, which is why this went
    #    unnoticed. The FK has to go first: Postgres refuses to drop a
    #    primary key a live foreign key still references. The
    #    `asset_type_code` *column* itself is untouched here — step 4 below
    #    still needs it to match existing assets to their company's copy.
    op.drop_constraint("fk_assets_asset_type_code", "assets", type_="foreignkey")
    op.drop_constraint("pk_asset_types", "asset_types", type_="primary")

    # 3. Every existing company gets its own copy of today's four global
    #    types, tagged with whatever business profile it already has
    #    assigned (companies provisioned before this migration existed have
    #    none — default generic_repair, ADR-BOS-011 §Decision 2). Safe now:
    #    no uniqueness constraint on `code` remains to collide with.
    op.execute("""
        INSERT INTO asset_types (id, company_id, code, name_bg, icon, sort,
                                 field_defs, business_profile, created_at, updated_at)
        SELECT gen_random_uuid(), c.id, t.code, t.name_bg, t.icon, t.sort, t.field_defs,
               COALESCE(c.settings #>> '{repairflow,business_profile}', 'generic_repair'),
               now(), now()
        FROM companies c
        CROSS JOIN asset_types t
        WHERE t.company_id IS NULL
    """)

    # 4. Point every existing asset at its own company's new copy (matched
    #    by code, which is identical across every company's copy right now)
    #    before the old global rows those assets currently reference are
    #    dropped.
    op.add_column("assets", sa.Column("asset_type_id", UUID(as_uuid=True), nullable=True))
    op.execute("""
        UPDATE assets a
        SET asset_type_id = nt.id
        FROM asset_types nt
        WHERE nt.company_id = a.company_id AND nt.code = a.asset_type_code
    """)

    # 5. assets: the now-redundant code column can go — nothing reads it
    #    after step 4, and its FK is already gone (step 2).
    op.drop_column("assets", "asset_type_code")

    # 6. Drop the original global rows — nothing references them once step 4
    #    has run and step 5 removed the last column pointing at them.
    op.execute("DELETE FROM asset_types WHERE company_id IS NULL")

    # 7. Tighten asset_types now that every remaining row has a company, and
    #    give assets its new id-based FK. (The old primary key is already
    #    gone — dropped early in step 2 — so there is no
    #    `drop_constraint("pk_asset_types", ...)` here anymore.)
    op.alter_column("asset_types", "id", nullable=False)
    op.alter_column("asset_types", "company_id", nullable=False)
    op.alter_column("asset_types", "business_profile", nullable=False)
    op.create_primary_key("pk_asset_types", "asset_types", ["id"])
    op.create_foreign_key("fk_asset_types_company_id_companies", "asset_types",
                          "companies", ["company_id"], ["id"])
    op.create_index("uq_asset_types_company_id_code", "asset_types",
                    ["company_id", "code"], unique=True)
    op.create_index("ix_asset_types_company_id", "asset_types", ["company_id"])
    op.execute(_rls("asset_types"))

    op.alter_column("assets", "asset_type_id", nullable=False)
    op.create_foreign_key("fk_assets_asset_type_id_asset_types", "assets",
                          "asset_types", ["asset_type_id"], ["id"])


def downgrade() -> None:
    # Best-effort, local-dev-reset only (docs/04 §3 / ADR-017: forward-only
    # governs *deployed* environments, not this). Restores the pre-migration
    # *shape* — a single global type per code — using migration 0003's exact
    # original seed content; it does not attempt to preserve any
    # company-specific asset_types data added since (there was never a
    # mechanism for that content to diverge before this migration existed).
    op.add_column("assets", sa.Column("asset_type_code", sa.String(), nullable=True))
    op.execute("""
        UPDATE assets a SET asset_type_code = t.code
        FROM asset_types t WHERE t.id = a.asset_type_id
    """)
    op.drop_constraint("fk_assets_asset_type_id_asset_types", "assets", type_="foreignkey")
    op.drop_column("assets", "asset_type_id")

    op.execute("DROP TABLE asset_types CASCADE")
    asset_types = op.create_table(
        "asset_types",
        sa.Column("code", sa.String(), primary_key=True),
        sa.Column("name_bg", sa.String(), nullable=False),
        sa.Column("icon", sa.String(), nullable=False, server_default=""),
        sa.Column("sort", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("field_defs", JSONB(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.bulk_insert(asset_types, SEED_TYPES)

    op.alter_column("assets", "asset_type_code", nullable=False)
    op.create_foreign_key("fk_assets_asset_type_code", "assets", "asset_types",
                          ["asset_type_code"], ["code"])
