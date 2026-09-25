"""Dev/staging seed: company + Owner user (self-serve registration arrives in Етап 3).

Usage:
    uv run python -m serviceflow.seed "Сервиз Демо" "Мария" maria@demo.bg парола123 [PIN]
        [--modules repairflow,professional-services]

Seeds a **single-application** company (`repairflow`) by default — the shape the
Vendor Control Plane enforces for real tenants (PO decision, 11.09.2026:
RepairFlow and PropertyFlow are mutually exclusive, never co-entitled — see
`platform_admin.service.provision_company` / `grant_entitlement`). Until
20.09.2026 this script unconditionally added `professional-services` on top,
so every dev/staging/CI tenant was co-entitled in a way provisioning forbids.

`--modules` opts a dev tenant back into that co-entitled shape deliberately —
useful for manual PropertyFlow work and for exercising the app chooser, which
IndexRoute (frontend/src/App.tsx) only reaches when both apps are active. Such
a company is **not representable in production**; don't treat it as a realistic
fixture. `repairflow` must stay in the list: `seed_company` grants it
unconditionally and revoking an entitlement is a Vendor Control Plane action by
design (ADR-BOS-010 §Decision 1), so this script cannot take it back.
"""

import argparse
import sys

# Registers the company_provisioned -> seed_default_types subscriber (import-
# time side effect, business_os.shared_kernel.events.subscribe). Without this
# import, seed_company()'s publish() below reaches zero subscribers when run
# standalone (this script never imports serviceflow.main), leaving the new
# company with no default RepairFlow asset types.
import serviceflow.assets.service  # noqa: F401,E402
from business_os.identity.service import activate_module, seed_company
from business_os.shared_kernel.db import open_session
from serviceflow.config import get_settings

# Windows consoles default to cp1252 — Cyrillic company names crashed the final
# print after a successful seed. Force UTF-8 for our own output.
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

BASE_MODULE = "repairflow"


def _parse_modules(raw: str) -> list[str]:
    modules = [m.strip() for m in raw.split(",") if m.strip()]
    if BASE_MODULE not in modules:
        raise SystemExit(
            f"--modules must include '{BASE_MODULE}': seed_company() grants it "
            "unconditionally and only the Vendor Control Plane can revoke an "
            "entitlement (ADR-BOS-010, Decision 1)."  # ASCII: this reaches
            # stderr, which stays cp1252 on a Windows console (only stdout is
            # reconfigured above), so a section sign would print as mojibake.
        )
    return modules


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m serviceflow.seed",
        description="Seed a dev/staging company with one Owner user.",
    )
    parser.add_argument("company_name")
    parser.add_argument("owner_name")
    parser.add_argument("email")
    parser.add_argument("password")
    parser.add_argument("pin", nargs="?", default=None)
    parser.add_argument(
        "--modules",
        default=BASE_MODULE,
        metavar="repairflow[,professional-services]",
        help="Comma-separated modules to activate. Defaults to repairflow only "
        "(production-realistic); adding professional-services produces a "
        "co-entitled company that provisioning would reject.",
    )
    args = parser.parse_args()
    modules = _parse_modules(args.modules)

    settings = get_settings()
    if settings.database_url is None:
        raise SystemExit("SERVICEFLOW_DATABASE_URL is not set")
    for db in open_session(settings.database_url):
        company = seed_company(
            db, args.company_name, args.owner_name, args.email, args.password, args.pin
        )
        for module_key in modules:
            if module_key != BASE_MODULE:  # seed_company already granted it
                activate_module(db, company.id, module_key)
        print(f"OK: company '{company.name}' ({company.id}) modules={modules}")


if __name__ == "__main__":
    main()
