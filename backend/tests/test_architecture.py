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

from pathlib import Path

# Import every module that defines tables so metadata is complete — mirrors
# migrations/env.py's import list (the same models Alembic autogenerate needs).
from business_os.identity import models as _identity_models  # noqa: F401
from business_os.shared_kernel.db import Base
from serviceflow.assets import models as _assets_models  # noqa: F401
from serviceflow.attachments import models as _attachments_models  # noqa: F401
from serviceflow.commercial import models as _commercial_models  # noqa: F401
from serviceflow.contacts import models as _contacts_models  # noqa: F401
from serviceflow.customers import models as _customers_models  # noqa: F401
from serviceflow.service_orders import models as _service_orders_models  # noqa: F401
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
    "companies": "business_os.identity",
    "users": "business_os.identity",
    "sessions": "business_os.identity",
    "audit_log": "business_os.identity",
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
    "payments": "serviceflow.commercial",
    "tasks": "serviceflow.tasks",
    "attachments": "serviceflow.attachments",
    "contact_records": "serviceflow.contacts",
    "timeline_events": "serviceflow.timeline",
    "ps_clients": "professional_services.clients",
    "ps_assignments": "professional_services.assignments",
    "ps_next_actions": "professional_services.actions",
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
    violations = _find_violations(live={}, declared={"ghost_table": "business_os.identity"})
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
# `from business_os.identity.deps import service` work as a bypass. This test
# checks that property directly — it is not redundant with import-linter,
# which only tracks import *statements*, not module namespace contents.


def test_identity_public_modules_do_not_reexport_internal_service() -> None:
    """deps.py and contracts.py hold their internal identity.service
    reference as `_service` (leading underscore), not `service`, precisely so
    neither module's own namespace exposes an easy re-export of it."""
    from business_os.identity import contracts, deps

    assert not hasattr(deps, "service"), (
        "identity.deps re-exposes 'service' as a public attribute again — "
        "this reopens the 'from business_os.identity.deps import service' "
        "boundary bypass documented in docs/business-os/16. Re-alias the "
        "internal import to `_service`."
    )
    assert not hasattr(contracts, "service"), (
        "identity.contracts re-exposes 'service' as a public attribute "
        "again — same bypass as above, via contracts.py instead of deps.py."
    )


# --- Commercial <-> Service Orders boundary (Invoice decision checkpoint's
# architecture boundary repair, docs/business-os/04 rule R4: "first binding
# pair: commercial <-> service_orders") ---------------------------------
#
# service_orders.contracts / commercial.contracts are the only sanctioned
# cross-module surface (backend/.importlinter contracts
# service-orders-public-boundary / commercial-public-boundary). The tests
# below exercise import-linter's own contract-checking machinery directly
# (not a reimplementation of it) against both the real graph and a
# synthetically-mutated copy, so a regression fails under plain `pytest`,
# not only under the separate `uv run lint-imports` command a dev might
# forget to run.

_BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _importlinter_report(limit_to_contracts: tuple[str, ...], graph: object = None) -> object:
    from importlinter import configuration
    from importlinter.application.use_cases import (
        _build_graph,  # noqa: SLF001 — same internal `lint_imports` itself calls
        _build_report,  # noqa: SLF001
        _register_contract_types,  # noqa: SLF001
        read_user_options,
    )

    configuration.configure()
    user_options = read_user_options(config_filename=str(_BACKEND_ROOT / ".importlinter"))
    _register_contract_types(user_options)
    if graph is None:
        graph = _build_graph(
            root_package_names=user_options.session_options["root_packages"],
            cache_dir=None, include_external_packages=False,
            exclude_type_checking_imports=False, verbose=False,
        )
    return _build_report(
        graph=graph, graph_building_duration=0, user_options=user_options,
        limit_to_contracts=limit_to_contracts, show_timings=False, verbose=False,
    )


def _real_graph() -> object:
    import grimp
    return grimp.build_graph("serviceflow", "business_os", "professional_services",
                             cache_dir=None)


def test_commercial_service_orders_boundary_contracts_currently_kept() -> None:
    """Regression guard: the two contracts introduced by the architecture
    boundary repair must stay green under pytest, not just `lint-imports`."""
    report = _importlinter_report(
        ("service-orders-public-boundary", "commercial-public-boundary"),
    )
    assert not report.contains_failures, (  # type: ignore[attr-defined]
        "commercial <-> service_orders boundary contracts are broken — "
        "run `uv run lint-imports` for the full report"
    )


def test_import_linter_catches_forbidden_commercial_to_service_orders_import() -> None:
    """Proves detection capability (not just current cleanliness): a
    synthetic direct import of a protected service_orders module from
    commercial breaks service-orders-public-boundary. Built via
    graph.add_import on a real graph, not by editing source files, so the
    test can't accidentally leave a stray import behind."""
    graph = _real_graph()
    graph.add_import(  # type: ignore[attr-defined]
        importer="serviceflow.commercial.service",
        imported="serviceflow.service_orders.models",
        line_number=1, line_contents="from serviceflow.service_orders.models import ServiceOrder",
    )
    report = _importlinter_report(("service-orders-public-boundary",), graph=graph)
    assert report.contains_failures  # type: ignore[attr-defined]


def test_import_linter_catches_forbidden_service_orders_to_commercial_import() -> None:
    """Same proof, other direction: service_orders importing a protected
    commercial module breaks commercial-public-boundary."""
    graph = _real_graph()
    graph.add_import(  # type: ignore[attr-defined]
        importer="serviceflow.service_orders.router",
        imported="serviceflow.commercial.service",
        line_number=1, line_contents="from serviceflow.commercial import service",
    )
    report = _importlinter_report(("commercial-public-boundary",), graph=graph)
    assert report.contains_failures  # type: ignore[attr-defined]


def test_no_commercial_service_orders_import_cycle() -> None:
    """commercial depends on service_orders (via .contracts, for order
    lookups/totals); service_orders must have zero dependency back — proving
    the edge is one-directional, not a cycle disguised as 'both sides only
    touch contracts.py'. The paid_amount/balance need is solved by
    service_orders owning a port that commercial implements and the
    composition root wires (serviceflow/main.py), not by an import."""
    graph = _real_graph()
    commercial_upstream = graph.find_upstream_modules(  # type: ignore[attr-defined]
        "serviceflow.commercial", as_package=True)
    service_orders_upstream = graph.find_upstream_modules(  # type: ignore[attr-defined]
        "serviceflow.service_orders", as_package=True)

    assert any(m.startswith("serviceflow.service_orders") for m in commercial_upstream), (
        "expected commercial to depend on service_orders (via .contracts) — "
        "if this fails on purpose, the DTO/port design changed and this "
        "test needs updating alongside it"
    )
    assert not any(m.startswith("serviceflow.commercial") for m in service_orders_upstream), (
        "service_orders now depends on commercial — this recreates exactly "
        "the cycle the architecture boundary repair removed"
    )


def test_commercial_service_orders_contracts_do_not_reexport_internals() -> None:
    """service_orders.contracts and commercial.contracts hold their internal
    service/lines references as `_service`/`_lines` (leading underscore),
    mirroring identity's bypass-closing convention above — so neither
    module's own namespace re-exposes an easy
    `from serviceflow.commercial.contracts import service` bypass."""
    from serviceflow.commercial import contracts as commercial_contracts
    from serviceflow.service_orders import contracts as service_orders_contracts

    assert not hasattr(service_orders_contracts, "service")
    assert not hasattr(service_orders_contracts, "lines")
    assert not hasattr(commercial_contracts, "service")
