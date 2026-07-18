"""Architecture boundary tests (Business OS Phase 1).

Enforces rule R5 (docs/business-os/04_DEPENDENCY_RULES.md §2): every table has
exactly one owning module, matching the ownership matrix in
docs/business-os/05_DATA_OWNERSHIP.md §1. See
docs/business-os/12_PHASE_1_IMPLEMENTATION.md for what this file enforces and
why, and how to update TABLE_OWNERS when a migration changes ownership.

Rule R3 (Core must not import a vertical/shared module) is enforced instead by
`backend/.importlinter` (`uv run lint-imports`, wired into CI) — no separate
pytest wrapper here, to avoid a second competing check for the same rule.

Pure introspection of SQLAlchemy metadata: no database connection, no
network, runs in milliseconds.
"""

# Import every module that defines tables so metadata is complete — mirrors
# migrations/env.py's import list (the same models Alembic autogenerate needs).
from serviceflow.assets import models as _assets_models  # noqa: F401
from serviceflow.attachments import models as _attachments_models  # noqa: F401
from serviceflow.contacts import models as _contacts_models  # noqa: F401
from serviceflow.customers import models as _customers_models  # noqa: F401
from serviceflow.identity import models as _identity_models  # noqa: F401
from serviceflow.service_orders import models as _service_orders_models  # noqa: F401
from serviceflow.shared_kernel.db import Base
from serviceflow.tasks import models as _tasks_models  # noqa: F401
from serviceflow.timeline import models as _timeline_models  # noqa: F401

# Table ownership per docs/business-os/05_DATA_OWNERSHIP.md §1 ("current
# owner" column). Update this map AND that document in the same PR as any
# migration that adds, moves, or repurposes a table (ADR-BOS-003).
#
# document_sequences: ownership is documented as Open (BOS-05 §1, BOS-09 Q2) —
# this map reflects the *current* code owner (service_orders), not a decision
# on where it ends up in Етап 4.
TABLE_OWNERS = {
    "companies": "serviceflow.identity",
    "users": "serviceflow.identity",
    "sessions": "serviceflow.identity",
    "audit_log": "serviceflow.identity",
    "customers": "serviceflow.customers",
    "asset_types": "serviceflow.assets",
    "assets": "serviceflow.assets",
    "asset_identifiers": "serviceflow.assets",
    "order_statuses": "serviceflow.service_orders",
    "document_sequences": "serviceflow.service_orders",  # ownership Open — BOS-05 §1
    "service_orders": "serviceflow.service_orders",
    "diagnoses": "serviceflow.service_orders",
    "part_lines": "serviceflow.service_orders",
    "labor_lines": "serviceflow.service_orders",
    "accessory_items": "serviceflow.service_orders",
    "tasks": "serviceflow.tasks",
    "attachments": "serviceflow.attachments",
    "contact_records": "serviceflow.contacts",
    "timeline_events": "serviceflow.timeline",
}


def _live_owning_modules() -> dict[str, str]:
    """table name -> the module that actually defines its mapped class,
    read from the live SQLAlchemy registry (not from TABLE_OWNERS)."""
    return {
        mapper.local_table.name: mapper.class_.__module__
        for mapper in Base.registry.mappers
        if mapper.local_table is not None
    }


def _find_violations(live: dict[str, str], declared: dict[str, str]) -> list[str]:
    """Pure comparison, kept separate from the SQLAlchemy introspection above
    so the comparison logic itself can be unit-tested against synthetic input
    (see the two tests below) before it is trusted against the real schema.
    """
    violations = []
    for table, owner_package in declared.items():
        actual_module = live.get(table)
        if actual_module is None:
            violations.append(f"{table!r}: declared in TABLE_OWNERS but not in live metadata")
            continue
        expected_module = f"{owner_package}.models"
        if actual_module != expected_module:
            violations.append(
                f"{table!r}: mapped by {actual_module!r}, expected {expected_module!r} "
                "(rule R5 — docs/business-os/04_DEPENDENCY_RULES.md; "
                "ownership — docs/business-os/05_DATA_OWNERSHIP.md §1)"
            )
    return violations


def test_find_violations_accepts_correctly_owned_table() -> None:
    """Allowed case: the table's mapped class is in its declared package."""
    live = {"customers": "serviceflow.customers.models"}
    declared = {"customers": "serviceflow.customers"}
    assert _find_violations(live, declared) == []


def test_find_violations_flags_wrong_owner() -> None:
    """Prohibited case: the table is mapped by a package other than the one
    declared as its owner — this is exactly what R5 forbids."""
    live = {"customers": "serviceflow.customers.models"}
    declared = {"customers": "serviceflow.assets"}  # wrong on purpose
    violations = _find_violations(live, declared)
    assert len(violations) == 1
    assert "customers" in violations[0]
    assert "serviceflow.assets.models" in violations[0]


def test_find_violations_flags_missing_table() -> None:
    """A table declared in TABLE_OWNERS that no longer exists in the live
    schema (e.g. dropped by a migration without updating this map)."""
    violations = _find_violations(live={}, declared={"ghost_table": "serviceflow.identity"})
    assert len(violations) == 1
    assert "ghost_table" in violations[0]


def test_ownership_map_matches_live_metadata() -> None:
    """TABLE_OWNERS must list exactly the tables that exist today — neither
    more (stale entries) nor fewer (a migration added a table without
    updating this map and docs/business-os/05)."""
    live_tables = set(Base.metadata.tables.keys())
    documented_tables = set(TABLE_OWNERS.keys())
    assert live_tables == documented_tables, (
        "TABLE_OWNERS (backend/tests/test_architecture.py) is out of sync "
        "with the live schema.\n"
        f"undocumented tables: {sorted(live_tables - documented_tables) or None}\n"
        f"stale entries (no such table): {sorted(documented_tables - live_tables) or None}\n"
        "Update TABLE_OWNERS here and docs/business-os/05_DATA_OWNERSHIP.md "
        "§1 in the same PR (ADR-BOS-003)."
    )


def test_no_table_ownership_violations() -> None:
    """R5, exercised against the real repository: every table's mapped class
    lives in its declared owning package. Zero violations at Phase 1 baseline
    (docs/business-os/11_ARCHITECTURE_REVIEW.md) — this test ratchets that."""
    violations = _find_violations(_live_owning_modules(), TABLE_OWNERS)
    assert not violations, "Table ownership violations found:\n" + "\n".join(violations)


# --- Identity public boundary (Business OS Phase 3, docs/business-os/16) ---
#
# The import-linter `identity-public-boundary` contract (backend/.importlinter)
# blocks *direct* imports of identity.models/.service/.security/.router from
# outside identity — see docs/business-os/16 for the mutation-test evidence.
# What import-linter's `protected` contract type cannot see is a *namespace*
# property: whether an approved public module (deps.py, contracts.py) itself
# re-exposes an internal name as one of its own attributes, which would let
# `from serviceflow.identity.deps import service` work as a bypass. This test
# checks that property directly — it is not redundant with import-linter,
# which only tracks import *statements*, not module namespace contents.


def test_identity_public_modules_do_not_reexport_internal_service() -> None:
    """deps.py and contracts.py hold their internal identity.service
    reference as `_service` (leading underscore), not `service`, precisely so
    neither module's own namespace exposes an easy re-export of it."""
    from serviceflow.identity import contracts, deps

    assert not hasattr(deps, "service"), (
        "identity.deps re-exposes 'service' as a public attribute again — "
        "this reopens the 'from serviceflow.identity.deps import service' "
        "boundary bypass documented in docs/business-os/16. Re-alias the "
        "internal import to `_service`."
    )
    assert not hasattr(contracts, "service"), (
        "identity.contracts re-exposes 'service' as a public attribute "
        "again — same bypass as above, via contracts.py instead of deps.py."
    )
