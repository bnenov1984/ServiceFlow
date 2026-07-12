"""Migration #3: asset_types (global seed data) + assets + asset_identifiers (RLS).

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-11
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _rls(table: str) -> str:
    return f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON {table}
    USING (company_id = NULLIF(current_setting('app.company_id', true), '')::uuid);
"""


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
    asset_types = op.create_table(
        "asset_types",
        sa.Column("code", sa.String(), primary_key=True),
        sa.Column("name_bg", sa.String(), nullable=False),
        sa.Column("icon", sa.String(), nullable=False, server_default=""),
        sa.Column("sort", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("field_defs", JSONB(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.bulk_insert(asset_types, SEED_TYPES)

    op.create_table(
        "assets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id", name="fk_assets_company_id_companies"),
                  nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True),
                  sa.ForeignKey("customers.id", name="fk_assets_customer_id_customers"),
                  nullable=False),
        sa.Column("asset_type_code", sa.String(),
                  sa.ForeignKey("asset_types.code", name="fk_assets_asset_type_code"),
                  nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("field_values", JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("sensitive_values", sa.LargeBinary(), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_assets_company_id", "assets", ["company_id"])
    op.create_index("ix_assets_customer_id", "assets", ["customer_id"])
    op.execute(_rls("assets"))

    op.create_table(
        "asset_identifiers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("companies.id",
                                name="fk_asset_identifiers_company_id_companies"),
                  nullable=False),
        sa.Column("asset_id", UUID(as_uuid=True),
                  sa.ForeignKey("assets.id", name="fk_asset_identifiers_asset_id_assets",
                                ondelete="CASCADE"),
                  nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("value_normalized", sa.String(), nullable=False),
    )
    op.create_index("ix_asset_identifiers_asset_id", "asset_identifiers", ["asset_id"])
    op.create_index("ix_asset_identifiers_value", "asset_identifiers",
                    ["company_id", "value_normalized"])
    op.execute(
        "CREATE INDEX ix_asset_identifiers_value_trgm ON asset_identifiers "
        "USING gin (value_normalized gin_trgm_ops)"
    )
    op.execute(_rls("asset_identifiers"))


def downgrade() -> None:
    op.drop_table("asset_identifiers")
    op.drop_table("assets")
    op.drop_table("asset_types")
