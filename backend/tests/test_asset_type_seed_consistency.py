"""No DB needed: guards against migration 0020's NEW_BRAND_FIELD_DEF drifting
from serviceflow.assets.service.DEFAULT_TYPES' own "vehicle" brand field_def
(Issue 23) — the migration forward-updates already-provisioned companies,
DEFAULT_TYPES seeds every company provisioned afterward; if the two ever
disagree, new and existing companies would silently end up with different
make lists."""

import importlib.util
from pathlib import Path


def _load_migration_0020() -> object:
    path = (
        Path(__file__).resolve().parents[1]
        / "migrations" / "versions" / "0020_vehicle_brand_choice_field.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0020", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_0020_new_brand_def_matches_default_types() -> None:
    from serviceflow.assets.service import DEFAULT_TYPES

    migration = _load_migration_0020()
    vehicle = next(t for t in DEFAULT_TYPES if t["code"] == "vehicle")
    live_brand = next(d for d in vehicle["field_defs"] if d["key"] == "brand")

    assert live_brand == migration.NEW_BRAND_FIELD_DEF
