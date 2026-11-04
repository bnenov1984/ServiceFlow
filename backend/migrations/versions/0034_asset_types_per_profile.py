"""Migration #34: one asset type per business profile + reg-№ identity (WP-C,
Q18, Q11).

Three independent changes:

1. **Reg-№ homoglyph fold + uniqueness.** Bulgarian plates mix Cyrillic and
   Latin look-alike letters depending on who/what typed them ("СА1234ВХ" vs
   "CA1234BX" — the same physical plate). Existing `asset_identifiers.
   value_normalized` rows of kind 'reg' are re-folded via the same
   translation table `business_os.shared_kernel.normalize.
   fold_plate_homoglyphs` now applies at write time, then (mirroring
   migration 0023's VIN pattern exactly) a pre-flight duplicate scan runs
   before a partial unique index on `(company_id, value_normalized) WHERE
   kind = 'reg'` is created — if any tenant already has two vehicles with
   the same folded reg-№, this migration stops with a clear, actionable
   error instead of letting Postgres raise an opaque constraint violation,
   and nothing else in this migration is rolled back either (one
   transaction, see migration 0023's own note on this).

2. **Per-profile asset-type seed map (Q18).** Before this migration every
   company owns an identical copy of four asset types (phone/vehicle/
   laptop/other), regardless of its business profile — a structural
   placeholder from migration 0015, explicitly left for "a future migration
   to branch on" (docs/business-os/18 §15.1). This migration is that
   branch: each business profile now seeds exactly one type match the Q18
   seed map (`serviceflow.assets.service.BUSINESS_PROFILE_ASSET_TYPES`,
   kept in sync with this file's frozen copy by hand — migrations never
   import application code). automotive_repair/generic_repair reuse their
   existing 'vehicle'/'other' codes and field_defs unchanged (no asset ever
   changes type); phone_repair's existing 'phone' type gains a new "вид"
   field; electronics_repair/appliance_repair get new types ('electronics'/
   'appliance') that never existed before.

   **Existing companies' no-longer-matching types are replaced outright**
   (PO-approved 26.10.2026, `proposal-removals-types-list.md`, reconfirmed
   03.11.2026 against the now-real production data this proposal originally
   assumed didn't exist yet — see this migration's own safety behavior
   below, which is what makes "replaced outright" safe regardless). A
   non-matching type's assets are deleted ONLY when no `service_orders` row
   references them — `service_orders.asset_id` and `asset_ownership.
   asset_id` both have no `ON DELETE` clause (RESTRICT), so a plain DELETE
   on an asset with real order history fails loudly rather than cascading;
   this migration pre-filters to exactly the assets that delete would have
   silently allowed anyway (no order history — orphaned/unused, e.g. a test
   asset created but never ordered), never attempts the rest, and leaves a
   non-matching type in place (with its assets) if it still holds any. A
   company left with more than one type after this migration is a real,
   visible signal that it has genuine cross-type history to reconcile by
   hand — not a silent data loss and not a migration failure.

3. No schema change for #2 — `asset_types`/`assets` already have every
   column this needs (migration 0015).

Revision ID: 0034
Revises: 0033
Create Date: 2026-11-04
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None

# Mirrors business_os.shared_kernel.normalize.fold_plate_homoglyphs's
# translation table exactly (migrations never import application code).
_PLATE_HOMOGLYPH_FROM = "АВЕКМНОРСТУХ"
_PLATE_HOMOGLYPH_TO = "ABEKMHOPCTYX"

# Identical to serviceflow.assets.service.BUSINESS_PROFILE_ASSET_TYPES —
# frozen copy, kept in sync by hand (see module docstring).
PROFILE_ASSET_TYPES: dict[str, dict] = {
    "automotive_repair": {
        "code": "vehicle", "name_bg": "Автомобил", "icon": "car", "sort": 1,
        "field_defs": [
            {"key": "brand", "label_bg": "Марка", "type": "choice", "choices": [
                "Audi", "BMW", "Chevrolet", "Citroën", "Dacia", "Fiat", "Ford",
                "Honda", "Hyundai", "Kia", "Lada", "Land Rover", "Mazda",
                "Mercedes-Benz", "Mini", "Mitsubishi", "Nissan", "Opel",
                "Peugeot", "Renault", "Seat", "Škoda", "Subaru", "Suzuki",
                "Toyota", "Volkswagen", "Volvo", "Друго",
            ]},
            {"key": "model", "label_bg": "Модел", "type": "text"},
            {"key": "reg_no", "label_bg": "Рег. №", "type": "text", "identifier_kind": "reg"},
            {"key": "vin", "label_bg": "VIN", "type": "text", "identifier_kind": "vin"},
            {"key": "year", "label_bg": "Година", "type": "number"},
            {"key": "mileage", "label_bg": "Пробег (км)", "type": "number"},
        ],
    },
    "phone_repair": {
        "code": "phone", "name_bg": "Телефон / таблет", "icon": "smartphone", "sort": 1,
        "field_defs": [
            {"key": "kind", "label_bg": "Вид", "type": "choice",
             "choices": ["Телефон", "Таблет"]},
            {"key": "brand", "label_bg": "Марка", "type": "text"},
            {"key": "model", "label_bg": "Модел", "type": "text"},
            {"key": "imei", "label_bg": "IMEI", "type": "text", "identifier_kind": "imei"},
            {"key": "serial_no", "label_bg": "Сериен №", "type": "text",
             "identifier_kind": "serial"},
            {"key": "color", "label_bg": "Цвят", "type": "text"},
        ],
    },
    "electronics_repair": {
        "code": "electronics", "name_bg": "Устройство", "icon": "laptop", "sort": 1,
        "field_defs": [
            {"key": "kind", "label_bg": "Вид", "type": "text"},
            {"key": "brand", "label_bg": "Марка", "type": "text"},
            {"key": "model", "label_bg": "Модел", "type": "text"},
            {"key": "serial_no", "label_bg": "Сериен №", "type": "text",
             "identifier_kind": "serial"},
        ],
    },
    "appliance_repair": {
        "code": "appliance", "name_bg": "Уред", "icon": "appliance", "sort": 1,
        "field_defs": [
            {"key": "kind", "label_bg": "Вид", "type": "text"},
            {"key": "brand", "label_bg": "Марка", "type": "text"},
            {"key": "model", "label_bg": "Модел", "type": "text"},
            {"key": "serial_no", "label_bg": "Сериен №", "type": "text",
             "identifier_kind": "serial"},
        ],
    },
    "generic_repair": {
        "code": "other", "name_bg": "Друго", "icon": "wrench", "sort": 1,
        "field_defs": [
            {"key": "description", "label_bg": "Описание", "type": "text"},
            {"key": "identifier", "label_bg": "Идентификатор", "type": "text",
             "identifier_kind": "other"},
        ],
    },
}


def upgrade() -> None:
    bind = op.get_bind()

    # --- 1a. Re-fold existing reg-№ identifiers ------------------------------
    op.execute(sa.text(
        "UPDATE asset_identifiers "
        "SET value_normalized = translate(value_normalized, :from_chars, :to_chars) "
        "WHERE kind = 'reg'"
    ).bindparams(from_chars=_PLATE_HOMOGLYPH_FROM, to_chars=_PLATE_HOMOGLYPH_TO))

    # --- 1b. Pre-flight duplicate scan, then the uniqueness index -----------
    dupes = bind.execute(sa.text("""
        SELECT company_id, value_normalized, array_agg(id) AS ids, array_agg(asset_id) AS asset_ids
        FROM asset_identifiers
        WHERE kind = 'reg'
        GROUP BY company_id, value_normalized
        HAVING COUNT(*) > 1
    """)).all()
    if dupes:
        details = "; ".join(
            f"company={row.company_id} reg={row.value_normalized} "
            f"asset_identifier_ids={row.ids} asset_ids={row.asset_ids}"
            for row in dupes
        )
        raise RuntimeError(
            "Migration 0034 stopped before adding the reg-№ uniqueness index: "
            "duplicate folded reg-№ values already exist and would violate it. "
            "No automatic merge is performed — resolve these rows by hand "
            "(decide which asset is the real vehicle, clear or correct the "
            f"other's reg-№) and re-run this migration. Conflicts: {details}"
        )
    op.create_index(
        "uq_asset_identifiers_reg_company_value", "asset_identifiers",
        ["company_id", "value_normalized"], unique=True,
        postgresql_where=sa.text("kind = 'reg'"),
    )

    # --- 2a. Upsert each company's single target type ------------------------
    for business_profile, t in PROFILE_ASSET_TYPES.items():
        op.execute(sa.text("""
            INSERT INTO asset_types (id, company_id, code, business_profile, name_bg,
                                     icon, sort, field_defs, created_at, updated_at)
            SELECT gen_random_uuid(), c.id, :code, :business_profile, :name_bg,
                   :icon, :sort, CAST(:field_defs AS jsonb), now(), now()
            FROM companies c
            WHERE COALESCE(c.settings #>> '{repairflow,business_profile}', 'generic_repair')
                  = :business_profile
            ON CONFLICT (company_id, code) DO UPDATE SET
                name_bg = EXCLUDED.name_bg, icon = EXCLUDED.icon, sort = EXCLUDED.sort,
                field_defs = EXCLUDED.field_defs, business_profile = EXCLUDED.business_profile,
                updated_at = now()
        """).bindparams(
            code=t["code"], business_profile=business_profile, name_bg=t["name_bg"],
            icon=t["icon"], sort=t["sort"], field_defs=json.dumps(t["field_defs"]),
        ))

    # --- 2b. Identify each company's now-upserted target type id ------------
    op.execute("""
        CREATE TEMP TABLE _wpc_target_type_ids AS
        SELECT at.id AS asset_type_id
        FROM asset_types at
        JOIN companies c ON c.id = at.company_id
        WHERE at.code = CASE
            COALESCE(c.settings #>> '{repairflow,business_profile}', 'generic_repair')
            WHEN 'automotive_repair' THEN 'vehicle'
            WHEN 'phone_repair' THEN 'phone'
            WHEN 'electronics_repair' THEN 'electronics'
            WHEN 'appliance_repair' THEN 'appliance'
            ELSE 'other'
        END
    """)

    # --- 2c. Delete orphaned (no order history) assets of non-matching types,
    #         and their ownership rows (asset_identifiers cascade automatically
    #         via ON DELETE CASCADE; asset_ownership does not, hence explicit). -
    op.execute("""
        CREATE TEMP TABLE _wpc_deletable_assets AS
        SELECT a.id
        FROM assets a
        WHERE a.asset_type_id NOT IN (SELECT asset_type_id FROM _wpc_target_type_ids)
          AND NOT EXISTS (SELECT 1 FROM service_orders so WHERE so.asset_id = a.id)
    """)
    op.execute("""
        DELETE FROM asset_ownership
        WHERE asset_id IN (SELECT id FROM _wpc_deletable_assets)
    """)
    op.execute("""
        DELETE FROM assets
        WHERE id IN (SELECT id FROM _wpc_deletable_assets)
    """)

    # --- 2d. Drop non-matching types now left with zero assets --------------
    # (a type that still has assets — because real order history blocked the
    # delete above — survives on purpose; see module docstring.)
    op.execute("""
        DELETE FROM asset_types at
        WHERE at.id NOT IN (SELECT asset_type_id FROM _wpc_target_type_ids)
          AND NOT EXISTS (SELECT 1 FROM assets a WHERE a.asset_type_id = at.id)
    """)

    op.execute("DROP TABLE _wpc_deletable_assets")
    op.execute("DROP TABLE _wpc_target_type_ids")


def downgrade() -> None:
    # Best-effort, local-dev-reset only (docs/04 §3 / ADR-017: forward-only
    # governs *deployed* environments, not this) — cannot restore deleted
    # non-matching types/assets or un-fold reg-№ values; only drops the index.
    op.drop_index("uq_asset_identifiers_reg_company_value", table_name="asset_identifiers")
