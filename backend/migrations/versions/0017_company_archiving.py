"""Migration #17: company archiving (logical/soft archive, never a delete).

`archived_at` is the single source of truth — nullable, no separate
`is_archived` boolean, mirroring the existing `AuthSession.revoked_at` /
`Company.trial_ends_at` convention already used throughout this schema
(a nullable timestamp *is* the flag; no companion bool ever shadows it).
`NULL` means active; any timestamp means archived since that moment.

No data is deleted or touched on any other table — users, sessions,
subscriptions, audit_log and all tenant business data are untouched by this
migration and by the archive/restore operations it enables.

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-03
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("archived_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "archived_at")
